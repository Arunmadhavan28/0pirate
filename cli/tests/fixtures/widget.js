// Fixture: JavaScript always takes the regex fallback path (no JS parser).
// Fail-closed contract: identifiers must still be hidden; only reserved
// words (function, return, new, class) may survive for readability.
const apiKey = "sk_live_51MzQ92Jk3L9s8D7f6G5h4J3k2L1";

function processStripePayment(amount, currency) {
  const ledger = new ProprietaryLedger();
  const tax = 100 / amount;
  return ledger.settle(amount + tax, currency);
}

class ProprietaryLedger {
  settle(total, currency) {
    return total;
  }
}
