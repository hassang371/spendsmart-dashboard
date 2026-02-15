/**
 * Batch category update API endpoint
 *
 * Enables the hybrid import architecture by allowing background classification
 * to update categories after transactions have been inserted.
 *
 * @see docs/plans/2026-02-14-hybrid-import-architecture.md
 */

import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * Maximum number of updates allowed in a single request
 */
const MAX_BATCH_SIZE = 500;

/**
 * Request body for batch category updates
 */
interface UpdateCategoriesRequest {
  updates: Array<{
    description: string;
    category: string;
  }>;
}

/**
 * Response for batch category updates
 */
interface UpdateCategoriesResponse {
  success: boolean;
  updatedCount: number;
  error?: string;
}

/**
 * Extract bearer token from request headers
 */
function getBearerToken(req: NextRequest): string | null {
  const authHeader = req.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return null;
  }
  return authHeader.slice(7).trim();
}

/**
 * Require environment variable
 */
function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not configured`);
  }
  return value;
}

/**
 * POST /api/transactions/update-categories
 *
 * Updates transaction categories in batch by matching on description.
 * This is used by the background classification flow to update categories
 * after transactions have been inserted.
 *
 * @param request - NextRequest containing updates array
 * @returns JSON response with success status and updated count
 *
 * @example
 * // Request body:
 * {
 *   "updates": [
 *     { "description": "SWIGGY ORDER #12345", "category": "Food" },
 *     { "description": "ZOMATO ORDER #11111", "category": "Food" }
 *   ]
 * }
 *
 * // Response:
 * { "success": true, "updatedCount": 2 }
 */
export async function POST(request: NextRequest): Promise<NextResponse<UpdateCategoriesResponse>> {
  try {
    // 1. Get bearer token from request
    const userAccessToken = getBearerToken(request);
    if (!userAccessToken) {
      return NextResponse.json(
        { success: false, updatedCount: 0, error: 'Missing bearer token' },
        { status: 401 }
      );
    }

    // 2. Create Supabase client with user's access token
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
      return NextResponse.json(
        { success: false, updatedCount: 0, error: message },
        { status: 500 }
      );
    }

    // 3. Authenticate user
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json(
        { success: false, updatedCount: 0, error: 'Invalid bearer token' },
        { status: 401 }
      );
    }

    // 4. Parse and validate request body
    let body: UpdateCategoriesRequest;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        { success: false, updatedCount: 0, error: 'Invalid JSON body' },
        { status: 400 }
      );
    }

    // 5. Validate updates array
    if (!body.updates || !Array.isArray(body.updates)) {
      return NextResponse.json(
        { success: false, updatedCount: 0, error: 'Missing or invalid "updates" array' },
        { status: 400 }
      );
    }

    if (body.updates.length === 0) {
      return NextResponse.json(
        { success: false, updatedCount: 0, error: 'Updates array is empty' },
        { status: 400 }
      );
    }

    if (body.updates.length > MAX_BATCH_SIZE) {
      return NextResponse.json(
        {
          success: false,
          updatedCount: 0,
          error: `Updates exceed maximum batch size of ${MAX_BATCH_SIZE}`,
        },
        { status: 400 }
      );
    }

    // 6. Validate each update entry
    for (let i = 0; i < body.updates.length; i++) {
      const update = body.updates[i];
      if (!update.description || typeof update.description !== 'string') {
        return NextResponse.json(
          { success: false, updatedCount: 0, error: `Update at index ${i} missing "description"` },
          { status: 400 }
        );
      }
      if (!update.category || typeof update.category !== 'string') {
        return NextResponse.json(
          { success: false, updatedCount: 0, error: `Update at index ${i} missing "category"` },
          { status: 400 }
        );
      }
    }

    // 7. Group updates by category for efficient batch queries
    const updatesByCategory = new Map<string, string[]>();
    for (const { description, category } of body.updates) {
      const existing = updatesByCategory.get(category);
      if (existing) {
        existing.push(description);
      } else {
        updatesByCategory.set(category, [description]);
      }
    }

    // 8. Execute batch updates
    let totalUpdated = 0;
    const errors: string[] = [];

    for (const [category, descriptions] of updatesByCategory) {
      const { count: matchingCount, error: countError } = await supabase
        .from('transactions')
        .select('id', { count: 'exact', head: true })
        .in('description', descriptions)
        .eq('user_id', user.id);

      if (countError) {
        errors.push(`Failed to count category "${category}": ${countError.message}`);
        continue;
      }

      const { error: updateError } = await supabase
        .from('transactions')
        .update({ category })
        .in('description', descriptions)
        .eq('user_id', user.id);

      if (updateError) {
        errors.push(`Failed to update category "${category}": ${updateError.message}`);
      } else {
        totalUpdated += matchingCount ?? 0;
      }
    }

    // 9. Return response
    if (errors.length > 0) {
      return NextResponse.json(
        {
          success: false,
          updatedCount: totalUpdated,
          error: errors.join('; '),
        },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      updatedCount: totalUpdated,
    });
  } catch (error) {
    console.error('Error in update-categories endpoint:', error);
    return NextResponse.json(
      {
        success: false,
        updatedCount: 0,
        error: 'Internal server error',
      },
      { status: 500 }
    );
  }
}
