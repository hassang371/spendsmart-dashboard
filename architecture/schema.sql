-- Protocol: B.L.A.S.T. / Phase 3

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    description TEXT,
    merchant_name TEXT,
    category TEXT DEFAULT 'Uncategorized',
    payment_method TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raw_data JSONB,
    
    -- Constraints
    CONSTRAINT transactions_amount_check CHECK (amount != 0)
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);

-- 3. RLS Policies
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only view their own transactions
CREATE POLICY "Users can view own transactions" 
ON transactions FOR SELECT 
USING (auth.uid() = user_id);

-- Policy: Users can insert their own transactions
CREATE POLICY "Users can insert own transactions" 
ON transactions FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update own transactions
CREATE POLICY "Users can update own transactions" 
ON transactions FOR UPDATE 
USING (auth.uid() = user_id);

-- Policy: Users can delete own transactions
CREATE POLICY "Users can delete own transactions" 
ON transactions FOR DELETE 
USING (auth.uid() = user_id);
