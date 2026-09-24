"""Static FX table for NimbusBank's multi-currency demo.

Rates are expressed as **USD per 1 unit** of the currency, so a value of
1.08 for EUR means 1 EUR = 1.08 USD. accounts-service is authoritative for
conversion: transfers-service records a transfer, then calls
/internal/apply-transfer here, which is the single place money actually
moves and currency actually converts.

LAB-ONLY: these are fixed, made-up rates baked into the image — no live FX
feed, no spread, no fees. The frontend hardcodes the same table purely for a
client-side "you send X, they get Y" preview; this module stays the source
of truth on execution.
"""

# USD per 1 unit of the currency.
FX_USD_PER_UNIT: dict[str, float] = {
    "USD": 1.00,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
    "KES": 0.0078,
}


def convert(amount_cents: int, from_ccy: str, to_ccy: str) -> tuple[int, float]:
    """Convert an integer-cents amount from one currency to another.

    Returns (converted_amount_cents, fx_rate) where fx_rate is the effective
    from->to multiplier (fx[from] / fx[to]). Unknown currencies fall back to
    USD so a stray value can never crash a transfer in this lab.
    """
    from_rate = FX_USD_PER_UNIT.get(from_ccy, 1.00)
    to_rate = FX_USD_PER_UNIT.get(to_ccy, 1.00)
    fx_rate = from_rate / to_rate
    converted = round(amount_cents * fx_rate)
    return int(converted), fx_rate
