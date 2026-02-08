
export interface Transaction {
    id: string;
    amount: number;
    transaction_date: string;
    merchant_name: string;
    description?: string;
    category: string;
    user_id?: string; // Should be removed
}

export interface AnonymizedTransaction {
    amount: number;
    date: string;
    category: string;
    merchant: string; // May be masked
    description?: string; // PII scrubbed
}

interface PrivacyOptions {
    maskMerchant?: boolean;
    scrubDescription?: boolean;
}

/**
 * Anonymizes a transaction for AI processing.
 * Strips user IDs and potentially masks merchant names/descriptions.
 */
export function anonymizeTransaction(
    tx: Transaction,
    options: PrivacyOptions = { maskMerchant: false, scrubDescription: true }
): AnonymizedTransaction {
    let merchant = tx.merchant_name;
    let description = tx.description || "";

    // 1. Mask Merchant if requested
    if (options.maskMerchant) {
        // If strict privacy, just use the category as the merchant name
        // e.g. "Starbucks" -> "Food & Drink_Merchant"
        merchant = `${tx.category}_Merchant`;
    }

    // 2. Scrub PII from Description (Emails, Phone Numbers)
    if (options.scrubDescription && description) {
        // Basic redaction regex
        const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
        const phoneRegex = /\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g;

        description = description
            .replace(emailRegex, "[EMAIL_REDACTED]")
            .replace(phoneRegex, "[PHONE_REDACTED]");
    }

    return {
        amount: tx.amount,
        date: tx.transaction_date, // Keep date for time-series analysis
        category: tx.category,
        merchant: merchant,
        description: description || undefined,
    };
}

/**
 * Batch anonymization
 */
export function anonymizeDataset(
    transactions: Transaction[],
    options?: PrivacyOptions
): AnonymizedTransaction[] {
    return transactions.map(tx => anonymizeTransaction(tx, options));
}
