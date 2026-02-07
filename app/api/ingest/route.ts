import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "../../../lib/supabase";
import Papa from "papaparse";
import { z } from "zod";

const TransactionSchema = z.object({
    Date: z.string().min(1),
    Description: z.string().min(1),
    Amount: z.union([z.string(), z.number()]), // CSV might be string
    Category: z.string().optional(),
    Type: z.string().optional(),
});

const IngestRequestSchema = z.object({
    csv: z.string().min(1),
    userId: z.string().uuid(),
});

function parseAmount(value: string | number): number | null {
    if (typeof value === "number") {
        return Number.isFinite(value) ? value : null;
    }

    let cleaned = value.trim();
    let isNegative = false;

    if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
        isNegative = true;
        cleaned = cleaned.slice(1, -1);
    }

    cleaned = cleaned.replace(/[$,\s]/g, "");
    const parsed = Number.parseFloat(cleaned);
    if (Number.isNaN(parsed)) {
        return null;
    }

    return isNegative ? -parsed : parsed;
}

function inferType(amount: number): "income" | "expense" {
    return amount >= 0 ? "income" : "expense";
}

async function ingestCsv(csvData: string, userId: string) {
    const parsed = Papa.parse<Record<string, unknown>>(csvData, {
        header: true,
        skipEmptyLines: true,
    });

    if (parsed.errors.length > 0) {
        return {
            response: NextResponse.json({ error: "CSV parsing failed", details: parsed.errors }, { status: 400 }),
        };
    }

    const validTransactions: Array<Record<string, unknown>> = [];
    const errors: Array<{ row: Record<string, unknown>; error: string }> = [];

    for (const row of parsed.data) {
        const result = TransactionSchema.safeParse(row);

        if (!result.success) {
            errors.push({ row, error: result.error.flatten().formErrors.join("; ") || "Invalid row" });
            continue;
        }

        const amount = parseAmount(result.data.Amount);
        if (amount === null) {
            errors.push({ row, error: "Amount is not a valid number" });
            continue;
        }

        const transactionDate = new Date(result.data.Date);
        if (Number.isNaN(transactionDate.getTime())) {
            errors.push({ row, error: "Date is invalid" });
            continue;
        }

        const transaction: Record<string, unknown> = {
            user_id: userId,
            transaction_date: transactionDate.toISOString(),
            description: result.data.Description,
            amount,
            category: result.data.Category || "Uncategorized",
            created_at: new Date().toISOString(),
        };

        if (result.data.Type) {
            transaction.type = result.data.Type;
        } else {
            transaction.type = inferType(amount);
        }

        validTransactions.push(transaction);
    }

    if (!validTransactions.length) {
        return {
            response: NextResponse.json(
                {
                    success: false,
                    inserted: 0,
                    failed: errors.length,
                    errors,
                    message: "No valid transactions found",
                },
                { status: 400 },
            ),
        };
    }

    if (!supabaseAdmin) {
        return {
            response: NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY is not configured" }, { status: 500 }),
        };
    }

    const { error } = await supabaseAdmin.from("transactions").insert(validTransactions);

    if (error) {
        return {
            response: NextResponse.json({ error: error.message }, { status: 500 }),
        };
    }

    return {
        response: NextResponse.json({
            success: true,
            inserted: validTransactions.length,
            failed: errors.length,
            errors,
        }),
    };
}

function getBearerToken(req: NextRequest): string | null {
    const authHeader = req.headers.get("authorization");
    if (!authHeader?.startsWith("Bearer ")) {
        return null;
    }
    return authHeader.slice(7).trim();
}

export const POST = async (req: NextRequest) => {
    const ingestApiKey = process.env.INGEST_API_KEY;
    if (!ingestApiKey) {
        return NextResponse.json({ error: "INGEST_API_KEY is not configured" }, { status: 500 });
    }

    const providedKey = req.headers.get("x-ingest-key");
    if (providedKey !== ingestApiKey) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    try {
        const body = await req.json();
        const payload = IngestRequestSchema.safeParse(body);

        if (!payload.success) {
            return NextResponse.json({ error: payload.error.flatten() }, { status: 400 });
        }

        const { response } = await ingestCsv(payload.data.csv, payload.data.userId);
        return response;
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unexpected server error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
};

export const GET = async (req: NextRequest) => {
    const cronSecret = process.env.CRON_SECRET || process.env.INGEST_CRON_SECRET;
    if (!cronSecret) {
        return NextResponse.json(
            { error: "CRON_SECRET (or INGEST_CRON_SECRET) is not configured" },
            { status: 500 },
        );
    }

    const bearerToken = getBearerToken(req);
    if (bearerToken !== cronSecret) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const sourceUrl = process.env.INGEST_CSV_URL;
    const defaultUserId = process.env.INGEST_DEFAULT_USER_ID;

    if (!sourceUrl || !defaultUserId) {
        return NextResponse.json(
            { error: "INGEST_CSV_URL and INGEST_DEFAULT_USER_ID must be configured for cron ingestion" },
            { status: 500 },
        );
    }

    try {
        const sourceResponse = await fetch(sourceUrl, { cache: "no-store" });
        if (!sourceResponse.ok) {
            return NextResponse.json(
                { error: `Failed to fetch CSV source (${sourceResponse.status})` },
                { status: 502 },
            );
        }

        const csv = await sourceResponse.text();
        const { response } = await ingestCsv(csv, defaultUserId);
        return response;
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unexpected server error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
};
