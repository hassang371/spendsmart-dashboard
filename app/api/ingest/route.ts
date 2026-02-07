import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "../../../lib/supabase/admin";
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
});

const UuidSchema = z.string().uuid();

type TransactionInsert = {
    user_id: string;
    transaction_date: string;
    description: string;
    amount: number;
    category: string;
    type: string;
    created_at: string;
};

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

function normalizeType(value: string | undefined, amount: number): string {
    if (!value) {
        return inferType(amount);
    }

    const normalized = value.trim().toLowerCase();
    if (normalized === "income" || normalized === "expense") {
        return normalized;
    }

    return inferType(amount);
}

function buildFingerprint(transaction: Pick<TransactionInsert, "user_id" | "transaction_date" | "description" | "amount">) {
    return [
        transaction.user_id,
        transaction.transaction_date,
        transaction.description.trim().toLowerCase(),
        transaction.amount.toFixed(2),
    ].join("|");
}

async function transactionAlreadyExists(transaction: TransactionInsert) {
    if (!supabaseAdmin) {
        return false;
    }

    const { data, error } = await supabaseAdmin
        .from("transactions")
        .select("id")
        .eq("user_id", transaction.user_id)
        .eq("transaction_date", transaction.transaction_date)
        .eq("description", transaction.description)
        .eq("amount", transaction.amount)
        .limit(1);

    if (error) {
        throw new Error(`Duplicate check failed: ${error.message}`);
    }

    return Boolean(data && data.length > 0);
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

    const parsedTransactions: TransactionInsert[] = [];
    const errors: Array<{ row: Record<string, unknown>; error: string }> = [];
    const fingerprints = new Set<string>();

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

        const transaction: TransactionInsert = {
            user_id: userId,
            transaction_date: transactionDate.toISOString(),
            description: result.data.Description,
            amount,
            category: result.data.Category || "Uncategorized",
            type: normalizeType(result.data.Type, amount),
            created_at: new Date().toISOString(),
        };

        const fingerprint = buildFingerprint(transaction);
        if (fingerprints.has(fingerprint)) {
            continue;
        }

        fingerprints.add(fingerprint);
        parsedTransactions.push(transaction);
    }

    const transactionsToInsert: TransactionInsert[] = [];
    let skippedDuplicates = 0;

    for (const transaction of parsedTransactions) {
        const exists = await transactionAlreadyExists(transaction);
        if (exists) {
            skippedDuplicates += 1;
            continue;
        }

        transactionsToInsert.push(transaction);
    }

    if (!transactionsToInsert.length) {
        return {
            response: NextResponse.json(
                {
                    success: false,
                    inserted: 0,
                    skipped_duplicates: skippedDuplicates,
                    failed: errors.length,
                    errors,
                    message: "No new valid transactions found",
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

    const { error } = await supabaseAdmin.from("transactions").insert(transactionsToInsert);

    if (error) {
        return {
            response: NextResponse.json({ error: error.message }, { status: 500 }),
        };
    }

    return {
        response: NextResponse.json({
            success: true,
            inserted: transactionsToInsert.length,
            skipped_duplicates: skippedDuplicates,
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

    const userAccessToken = getBearerToken(req);
    if (!userAccessToken) {
        return NextResponse.json({ error: "Missing bearer token" }, { status: 401 });
    }

    if (!supabaseAdmin) {
        return NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY is not configured" }, { status: 500 });
    }

    const {
        data: { user },
        error: userError,
    } = await supabaseAdmin.auth.getUser(userAccessToken);

    if (userError || !user) {
        return NextResponse.json({ error: "Invalid bearer token" }, { status: 401 });
    }

    try {
        const body = await req.json();
        const payload = IngestRequestSchema.safeParse(body);

        if (!payload.success) {
            return NextResponse.json({ error: payload.error.flatten() }, { status: 400 });
        }

        const { response } = await ingestCsv(payload.data.csv, user.id);
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

    const userIdCheck = UuidSchema.safeParse(defaultUserId);
    if (!userIdCheck.success) {
        return NextResponse.json({ error: "INGEST_DEFAULT_USER_ID must be a valid UUID" }, { status: 500 });
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
        const { response } = await ingestCsv(csv, userIdCheck.data);
        return response;
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unexpected server error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
};
