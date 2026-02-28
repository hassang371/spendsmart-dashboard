export interface SbiParseResult {
  merchant: string;
  cleanDescription: string;
  type: 'upi' | 'pos' | 'atm' | 'inb' | 'cash_deposit' | 'unknown';
  meta: Record<string, string>;
}

// Known merchants for fuzzy matching against truncated SBI fields
const sbiKnownMerchants: [string, string[]][] = [
  ['Swiggy Instamart', ['swiggy instamart', 'instamart']],
  ['Swiggy', ['swiggy']],
  ['Zomato', ['zomato', 'zomatofo', 'payzomato', 'zomatofood', 'zomato-ord']],
  ['Uber', ['uber']],
  ['Ola', ['ola', 'olacabs', 'olamon']],
  ['Rapido', ['rapido']],
  ['Blinkit', ['blinkit']],
  ['Zepto', ['zepto', 'zeptonow']],
  ['BigBasket', ['bigbasket']],
  ['Amazon', ['amazon', 'amzn', 'amazonpay']],
  ['Flipkart', ['flipkart']],
  ['Myntra', ['myntra']],
  ['Netflix', ['netflix']],
  ['Spotify', ['spotify']],
  ['YouTube', ['youtube', 'google']],
  ['Jio', ['jio', 'reliance']],
  ['Airtel', ['airtel']],
  ['PhonePe', ['phonepe', 'phonpe']],
  ['Paytm', ['paytm', 'one97communica', 'one97']],
  ['Google Pay', ['googlepay', 'gpay']],
  ['CRED', ['cred']],
  ['Dunzo', ['dunzo']],
  ['Dream11', ['dream11']],
  ['Groww', ['groww']],
  ['Zerodha', ['zerodha']],
  ['Slice', ['slice']],
  ['Meesho', ['meesho']],
  ['Nykaa', ['nykaa']],
  ['BookMyShow', ['bookmyshow']],
  ['IRCTC', ['irctc']],
  ['MakeMyTrip', ['makemytrip']],
  ['Ixigo', ['ixigo']],
  ['BESCOM', ['bescom']],
  ["Domino's", ['dominos', 'domino']],
  ["McDonald's", ['mcdonalds', 'mcdonald']],
  ['KFC', ['kfc']],
  ['Starbucks', ['starbucks']],
  ['Burger King', ['burgerking', 'burger king']],
];

/**
 * Match a set of text fields against known merchants.
 * Returns the official merchant name or null if no match.
 */
function matchKnownMerchant(...fields: string[]): string | null {
  // Combine all fields, collapse spaces, lowercase
  const combined = fields.join(' ').replace(/\s+/g, '').toLowerCase();
  for (const [official, aliases] of sbiKnownMerchants) {
    for (const alias of aliases) {
      if (combined.includes(alias)) {
        return official;
      }
    }
  }
  // Also try each field individually (for shorter aliases that need word context)
  const text = fields.join(' ').toLowerCase();
  for (const [official, aliases] of sbiKnownMerchants) {
    for (const alias of aliases) {
      if (text.includes(alias)) {
        return official;
      }
    }
  }
  return null;
}

/** Clean up a raw name from SBI fixed-width formatting */
function cleanName(raw: string): string {
  return raw
    .replace(/\s{2,}/g, ' ')
    .replace(/[._-]+$/, '')
    .trim();
}

export function parseSbiDescription(description: string): SbiParseResult {
  // 1. UPI Transactions
  // Format: (WDL|DEP) TFR UPI/(DR|CR)/<UTR>/<NAME>/<BANK>/<UPI_ID>/<APP>... <REF> AT <BRANCH>
  const upiRegex =
    /^(WDL|DEP) TFR\s+UPI\/(DR|CR)\/([^\/]+)\/([^\/]+)\/([^\/]+)\/([^\/]+)\/([^\s\/]+)/;
  const upiMatch = description.match(upiRegex);
  if (upiMatch) {
    const [, , mode, utr, rawName, bank, rawUpiId, rawApp] = upiMatch;
    const name = cleanName(rawName);
    const upiId = cleanName(rawUpiId);
    const app = cleanName(rawApp);
    const isCredit = mode === 'CR';

    // Try to match a known merchant from all available fields
    const knownMerchant = matchKnownMerchant(name, upiId, app);
    const merchant = knownMerchant || name;

    const cleanDesc = isCredit ? `UPI Received from ${merchant}` : `UPI Transfer to ${merchant}`;

    return {
      merchant,
      cleanDescription: cleanDesc,
      type: 'upi',
      meta: { utr, bank, mode, app },
    };
  }

  // 2. POS Transactions
  // Example: POS ATM PURCH OTHPG 3155010693 17Pho*PHONEPE RECHARGE BANGALORE
  const posRegex = /^POS ATM PURCH\s+(\S+)\s+(\S+)\s+(.*)$/;
  const posMatch = description.match(posRegex);
  if (posMatch) {
    const [, gateway, ref, remaining] = posMatch;
    const parts = remaining.split(/\s+/).filter(Boolean);
    const location = parts.length > 1 ? parts.pop()! : '';
    const merchantRaw = parts.join(' ');

    // Clean up: "17Pho*PHONEPE RECHARGE" -> "PHONEPE RECHARGE"
    let merchant = merchantRaw
      .replace(/^\d+[a-zA-Z0-9]*\*/, '')
      .replace(/^\*/, '')
      .trim();

    // Check against known merchants
    const knownMerchant = matchKnownMerchant(merchant, merchantRaw);
    if (knownMerchant) merchant = knownMerchant;

    return {
      merchant,
      cleanDescription: `POS Purchase at ${merchant}${location ? ` (${location})` : ''}`,
      type: 'pos',
      meta: { ref, location, gateway },
    };
  }

  // 3. ATM Withdrawals
  const atmRegex = /^ATM WDL\s+ATM CASH\s+(.*)$/;
  const atmMatch = description.match(atmRegex);
  if (atmMatch) {
    const rest = atmMatch[1];
    const parts = rest.split(/\s+/).filter(Boolean);
    let atmId = parts[0];
    let locationStart = 1;

    if (parts.length > 1 && parts[1].length <= 3) {
      atmId = `${parts[0]} ${parts[1]}`;
      locationStart = 2;
    }
    const location = parts.slice(locationStart).join(' ');

    return {
      merchant: 'ATM Withdrawal',
      cleanDescription: `ATM Cash Withdrawal${location ? ` at ${location}` : ''}`,
      type: 'atm',
      meta: { atmId, location },
    };
  }

  // 4. Internet Banking
  const inbRegex = /^WDL TFR\s+INB\s+(.*?)(?:\.\.\.|\s+AT\s+\d+)/;
  const inbMatch = description.match(inbRegex);
  if (inbMatch) {
    const [, merchantPart] = inbMatch;
    let merchant = cleanName(merchantPart);
    const knownMerchant = matchKnownMerchant(merchant);
    if (knownMerchant) merchant = knownMerchant;

    const prefix = merchant.startsWith('Gift') ? 'Online Transfer:' : 'Online Transfer to';

    return {
      merchant,
      cleanDescription: `${prefix} ${merchant}`,
      type: 'inb',
      meta: {},
    };
  }

  // 5. Cash Deposits
  if (description.startsWith('CASH DEPOSIT SELF')) {
    const branch = description.replace(/^CASH DEPOSIT SELF\s+AT\s*/, '').trim();
    return {
      merchant: 'Self Deposit',
      cleanDescription: `Cash Deposit${branch ? ` at ${branch}` : ''}`,
      type: 'cash_deposit',
      meta: { branch },
    };
  }

  // CDM: CEMTEX DEP <REF> ...
  const cdmRegex = /^CEMTEX DEP\s+(\S+)/;
  const cdmMatch = description.match(cdmRegex);
  if (cdmMatch) {
    const [, ref] = cdmMatch;
    // Check rest of description for merchant hints
    const knownMerchant = matchKnownMerchant(description);
    return {
      merchant: knownMerchant || 'Cash Deposit Machine',
      cleanDescription: knownMerchant
        ? `CDM Deposit via ${knownMerchant} (Ref: ${ref})`
        : `CDM Deposit (Ref: ${ref})`,
      type: 'cash_deposit',
      meta: { ref },
    };
  }

  // 6. DEP TFR patterns (refunds, VISA-IN-RMT, etc.)
  const depTfrRegex = /^DEP TFR\s+(.*)/;
  const depTfrMatch = description.match(depTfrRegex);
  if (depTfrMatch) {
    const rest = depTfrMatch[1];
    // Check for known merchant in the full text
    const knownMerchant = matchKnownMerchant(rest);
    if (knownMerchant) {
      return {
        merchant: knownMerchant,
        cleanDescription: `Refund from ${knownMerchant}`,
        type: 'upi',
        meta: {},
      };
    }
  }

  // 7. WDL TFR patterns not caught above (charges, misc)
  const wdlTfrRegex = /^WDL TFR\s+(.*)/;
  const wdlTfrMatch = description.match(wdlTfrRegex);
  if (wdlTfrMatch) {
    const rest = wdlTfrMatch[1];
    const knownMerchant = matchKnownMerchant(rest);
    if (knownMerchant) {
      return {
        merchant: knownMerchant,
        cleanDescription: `Payment to ${knownMerchant}`,
        type: 'upi',
        meta: {},
      };
    }
  }

  // Fallback
  return {
    merchant: 'Unknown',
    cleanDescription: description,
    type: 'unknown',
    meta: {},
  };
}
