import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createHash } from 'crypto';
import { z } from 'zod';

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
  filename: z.string().optional(),
  file_hash: z.string().optional(),
});

function buildFingerprint(
  transactionDate: string,
  amount: number,
  merchant: string,
  description: string,
  paymentMethod: string,
  reference: string
): string {
  const normalizedDate = transactionDate.slice(0, 19);
  const raw = `${normalizedDate}|${amount.toFixed(2)}|${merchant.trim().toUpperCase()}|${description
    .trim()
    .toUpperCase()}|${paymentMethod.trim().toUpperCase()}|${reference.trim().toUpperCase()}`;
  return createHash('sha256').update(raw).digest('hex');
}

/** Ensure date string is ISO 8601 (YYYY-MM-DD) for PostgreSQL timestamptz */
function normalizeDate(dateStr: string): string {
  // Already ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
  if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
    return dateStr;
  }
  // DD/MM/YYYY or DD-MM-YYYY format
  const dmyMatch = dateStr.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
  if (dmyMatch) {
    return `${dmyMatch[3]}-${dmyMatch[2].padStart(2, '0')}-${dmyMatch[1].padStart(2, '0')}`;
  }
  // "7 Feb 2026, 17:13" style
  const parsed = new Date(dateStr);
  if (!isNaN(parsed.getTime())) {
    return parsed.toISOString();
  }
  return dateStr;
}

function getBearerToken(req: NextRequest): string | null {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
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
    return NextResponse.json({ error: 'Missing bearer token' }, { status: 401 });
  }

  let supabase;
  try {
    const supabaseUrl = requireEnv('NEXT_PUBLIC_SUPABASE_URL');
    const supabaseAnonKey = requireEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY');

    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      global: {
        headers: {
          Authorization: `Bearer ${userAccessToken}`,
        },
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Supabase environment is not configured';
    return NextResponse.json({ error: message }, { status: 500 });
  }

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return NextResponse.json({ error: 'Invalid bearer token' }, { status: 401 });
  }

  try {
    const body = await req.json();
    const parsedPayload = ImportRequestSchema.safeParse(body);

    if (!parsedPayload.success) {
      console.error(
        '[/api/import] Zod validation failed:',
        JSON.stringify(parsedPayload.error.flatten(), null, 2)
      );
      return NextResponse.json({ error: parsedPayload.error.flatten() }, { status: 400 });
    }

    const rows = parsedPayload.data.transactions
      // Bug 2 fix: Filter out amount=0 rows (violates CHECK constraint)
      .filter(tx => tx.amount !== 0)
      .map(tx => {
        const normalizedDate = normalizeDate(tx.transaction_date);
        const rawReference =
          typeof tx.raw_data?.['reference'] === 'string'
            ? tx.raw_data['reference']
            : typeof tx.raw_data?.['ref'] === 'string'
              ? tx.raw_data['ref']
              : '';
        const fingerprint = buildFingerprint(
          normalizedDate,
          tx.amount,
          tx.merchant_name,
          tx.description,
          tx.payment_method,
          rawReference
        );
        return {
          user_id: user.id,
          transaction_date: normalizedDate,
          amount: tx.amount,
          currency: tx.currency,
          description: tx.description,
          merchant_name: tx.merchant_name,
          category: tx.category,
          payment_method: tx.payment_method,
          status: tx.status,
          raw_data: tx.raw_data,
          // Bug 4 fix: Populate fingerprint and type columns
          fingerprint,
          type: tx.amount >= 0 ? 'credit' : 'debit',
        };
      });

    const dedupedRows: typeof rows = [];
    const incomingFingerprints = new Set<string>();
    for (const row of rows) {
      if (incomingFingerprints.has(row.fingerprint)) continue;
      incomingFingerprints.add(row.fingerprint);
      dedupedRows.push(row);
    }

    const rowsToInsert = dedupedRows;
    const skippedDuplicates = rows.length - dedupedRows.length;
    const skippedZeroAmount = parsedPayload.data.transactions.length - rows.length;

    if (!rowsToInsert.length) {
      return NextResponse.json({
        success: true,
        inserted: 0,
        skipped_duplicates: skippedDuplicates,
        skipped_zero_amount: skippedZeroAmount,
      });
    }

    // Insert in batches of 500 to avoid payload size limits and timeouts
    const BATCH_SIZE = 500;
    let totalInserted = 0;
    for (let i = 0; i < rowsToInsert.length; i += BATCH_SIZE) {
      const batch = rowsToInsert.slice(i, i + BATCH_SIZE);
      const { error } = await supabase.from('transactions').insert(batch);
      if (error) {
        console.error(
          `[/api/import] Supabase insert error (batch ${Math.floor(i / BATCH_SIZE) + 1}):`,
          error.message,
          error.details,
          error.hint
        );
        return NextResponse.json({ error: error.message }, { status: 500 });
      }
      totalInserted += batch.length;
    }

    // Bug 6 fix: Track in uploaded_files table
    const filename = parsedPayload.data.filename;
    const fileHash = parsedPayload.data.file_hash;
    if (filename && fileHash) {
      await supabase.from('uploaded_files').insert({
        user_id: user.id,
        file_hash: fileHash,
        filename,
        upload_type: 'training',
      });
    }

    return NextResponse.json({
      success: true,
      inserted: totalInserted,
      skipped_duplicates: skippedDuplicates,
      skipped_zero_amount: skippedZeroAmount,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected server error';
    console.error('[/api/import] Uncaught error:', message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
};
