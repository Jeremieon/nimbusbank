// Client-side mirror of services/accounts/app/fx.py. Used ONLY for the live
// "you send X → they get Y" preview on the transfer form and for summing the
// dashboard total into USD. The server (accounts-service) stays authoritative
// on execution — this table just keeps the preview honest.
export const FX_USD_PER_UNIT = {
  USD: 1.0,
  EUR: 1.08,
  GBP: 1.27,
  JPY: 0.0067,
  KES: 0.0078,
}

// Convert an integer-cents amount from one currency to another, matching the
// server's round(amount * fx[from] / fx[to]).
export function convertCents(amountCents, fromCcy, toCcy) {
  const fromRate = FX_USD_PER_UNIT[fromCcy] ?? 1.0
  const toRate = FX_USD_PER_UNIT[toCcy] ?? 1.0
  const rate = fromRate / toRate
  return { cents: Math.round(amountCents * rate), rate }
}

// Every balance in this lab is stored as an integer "cents" value and shown
// as value/100, regardless of the currency's real minor unit — keeps the
// convention uniform across USD/EUR/GBP/JPY. Intl handles the symbol and the
// per-currency decimal places.
export function formatMoney(cents, currency = 'USD') {
  const amount = (Number(cents) || 0) / 100
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currency}`
  }
}

// Sum a list of accounts into a single USD figure (in cents) for the
// dashboard's headline total.
export function totalInUsdCents(accts) {
  return accts.reduce((sum, a) => {
    const { cents } = convertCents(a.balance_cents, a.currency || 'USD', 'USD')
    return sum + cents
  }, 0)
}

export function maskAccountNumber(number) {
  if (!number) return ''
  const tail = number.slice(-4)
  return `•••• ${tail}`
}
