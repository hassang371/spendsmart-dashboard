import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";

const ImportTransactionSchema = z.object({
  transaction_date: z.string().min(1),
  amount: z.number(),
  currency: z.string().min(1).max(8),
  description: z.string().min(1),
  merchant_name: z.string().min(1),
  category: z.string().min(1),
  payment_method: z.string().min(1),
  status: z.string().min(1),
  raw_data: z.record(z.string(), z.unknown()),
});

const ImportRequestSchema = z.object({
  transactions: z.array(ImportTransactionSchema).min(1).max(5000),
});

function buildFingerprint(transactionDate: string, amount: number, description: string): string {
  return `${transactionDate.slice(0, 19)}|${amount.toFixed(2)}|${description.trim().toLowerCase()}`;
}

function getBearerToken(req: NextRequest): string | null {
  const authHeader = req.headers.get("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return null;
  }

  return authHeader.slice(7).trim();
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not configured`);
  }
  return value;
}

export const POST = async (req: NextRequest) => {
  const userAccessToken = getBearerToken(req);
  if (!userAccessToken) {
    return NextResponse.json({ error: "Missing bearer token" }, { status: 401 });
  }

  let supabase;
  try {
    const supabaseUrl = requireEnv("NEXT_PUBLIC_SUPABASE_URL");
    const supabaseAnonKey = requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");

    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      global: {
        headers: {
          Authorization: `Bearer ${userAccessToken}`,
        },
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Supabase environment is not configured";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return NextResponse.json({ error: "Invalid bearer token" }, { status: 401 });
  }

  try {
    const body = await req.json();
    const parsedPayload = ImportRequestSchema.safeParse(body);

    if (!parsedPayload.success) {
      return NextResponse.json({ error: parsedPayload.error.flatten() }, { status: 400 });
    }

    const rows = parsedPayload.data.transactions.map((tx) => ({
      user_id: user.id,
      transaction_date: tx.transaction_date,
      amount: tx.amount,
      currency: tx.currency,
      description: tx.description,
      merchant_name: tx.merchant_name,
      category: tx.category,
      payment_method: tx.payment_method,
      status: tx.status,
      raw_data: tx.raw_data,
    }));

    const dedupedRows: typeof rows = [];
    const incomingFingerprints = new Set<string>();
    for (const row of rows) {
      const fingerprint = buildFingerprint(row.transaction_date, row.amount, row.description);
      if (incomingFingerprints.has(fingerprint)) continue;
      incomingFingerprints.add(fingerprint);
      dedupedRows.push(row);
    }

    const rowsToInsert = dedupedRows;
    const skippedDuplicates = rows.length - dedupedRows.length;

    if (!rowsToInsert.length) {
      return NextResponse.json({ success: true, inserted: 0, skipped_duplicates: skippedDuplicates });
    }

    const { error } = await supabase.from("transactions").insert(rowsToInsert);
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      inserted: rowsToInsert.length,
      skipped_duplicates: skippedDuplicates,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected server error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
};
