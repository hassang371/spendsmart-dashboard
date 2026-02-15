import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import officeCrypto from 'officecrypto-tool';

const MAX_DECRYPT_FILE_BYTES = 10 * 1024 * 1024;

// Helper to validate auth token
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

  // Verify auth with Supabase
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
    const formData = await req.formData();
    const file = formData.get('file') as File | null;
    const password = formData.get('password') as string | null;

    if (!file) {
      return NextResponse.json({ error: 'File is required' }, { status: 400 });
    }
    if (!password) {
      return NextResponse.json({ error: 'Password is required' }, { status: 400 });
    }

    let buffer: Buffer;
    if (typeof (file as File).arrayBuffer === 'function') {
      buffer = Buffer.from(await (file as File).arrayBuffer());
    } else if (typeof (file as File).text === 'function') {
      buffer = Buffer.from(await (file as File).text());
    } else if (typeof file === 'string') {
      buffer = Buffer.from(file);
    } else if (file && typeof file === 'object') {
      buffer = Buffer.alloc(0);
    } else {
      return NextResponse.json({ error: 'Invalid file payload' }, { status: 400 });
    }

    if (buffer.length > MAX_DECRYPT_FILE_BYTES) {
      return NextResponse.json({ error: 'File too large' }, { status: 413 });
    }

    // Check if it's actually encrypted
    const isEncrypted = await officeCrypto.isEncrypted(buffer);
    if (!isEncrypted) {
      // If not encrypted, just return the file as is?
      // Or warn the client? Client logic should only call this if it failed initially.
      // Let's assume client knows what it's doing and just return original.
      return new NextResponse(new Uint8Array(buffer), {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${file.name}"`,
        },
      });
    }

    // Decrypt
    try {
      const decryptedBuffer = await officeCrypto.decrypt(buffer, { password });
      return new NextResponse(new Uint8Array(decryptedBuffer), {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${file.name}"`,
        },
      });
    } catch (decryptError: unknown) {
      console.error('Decryption failed:', decryptError);
      return NextResponse.json(
        { error: 'Incorrect password or decryption failed.' },
        { status: 400 }
      );
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected server error';
    console.error('[/api/decrypt-xlsx] Uncaught error:', message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
};
