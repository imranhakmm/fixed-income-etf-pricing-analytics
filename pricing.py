from __future__ import annotations

import pandas as pd


DEFAULT_FACE_VALUE = 100.0
DEFAULT_COUPON_FREQUENCY = 2
BUMP_BP = 0.01


def _coupon_period_months(freq: int) -> int:
    return int(12 / freq)


def _infer_coupon_period_months(cashflows: list[tuple[pd.Timestamp, float]]) -> int:
    if len(cashflows) >= 2:
        first_date, second_date = cashflows[0][0], cashflows[1][0]
        return max(1, (second_date.year - first_date.year) * 12 + (second_date.month - first_date.month))
    return _coupon_period_months(DEFAULT_COUPON_FREQUENCY)


def _accrued_interest(
    coupon_pct: float,
    settlement_date: pd.Timestamp,
    next_coupon_date: pd.Timestamp,
    period_months: int,
    face: float,
    freq: int,
) -> float:
    previous_coupon_date = next_coupon_date - pd.DateOffset(months=period_months)
    period_days = max(1, (next_coupon_date - previous_coupon_date).days)
    accrued_days = max(0, (settlement_date - previous_coupon_date).days)
    coupon_amount = face * (coupon_pct / 100.0) / freq
    return coupon_amount * (accrued_days / period_days)


def build_cashflows(
    coupon_pct: float,
    maturity_date,
    settlement_date,
    face: float = DEFAULT_FACE_VALUE,
    freq: int = DEFAULT_COUPON_FREQUENCY,
) -> list[tuple[pd.Timestamp, float]]:
    settlement_ts = pd.Timestamp(settlement_date).normalize()
    maturity_ts = pd.Timestamp(maturity_date).normalize()
    period_months = _coupon_period_months(freq)

    payment_dates: list[pd.Timestamp] = []
    current_date = maturity_ts
    while current_date > settlement_ts:
        payment_dates.append(current_date)
        current_date -= pd.DateOffset(months=period_months)

    payment_dates.reverse()
    coupon_amount = face * (coupon_pct / 100.0) / freq
    cashflows: list[tuple[pd.Timestamp, float]] = []
    for idx, payment_date in enumerate(payment_dates):
        principal = face if idx == len(payment_dates) - 1 else 0.0
        cashflows.append((payment_date, coupon_amount + principal))
    return cashflows


def price_from_ytm(
    cashflows: list[tuple[pd.Timestamp, float]],
    ytm_pct: float,
    settlement_date,
) -> float:
    settlement_ts = pd.Timestamp(settlement_date).normalize()
    if not cashflows:
        return DEFAULT_FACE_VALUE

    freq = DEFAULT_COUPON_FREQUENCY
    period_months = _infer_coupon_period_months(cashflows)
    coupon_amount = min(amount for _, amount in cashflows)
    face = cashflows[-1][1] - coupon_amount
    if face <= 0:
        face = DEFAULT_FACE_VALUE
    coupon_pct = coupon_amount * freq / face * 100.0

    discount_rate = ytm_pct / 100.0 / freq
    dirty_price = 0.0
    for payment_date, amount in cashflows:
        year_fraction = (payment_date - settlement_ts).days / 365.25
        dirty_price += amount / ((1.0 + discount_rate) ** (freq * year_fraction))

    accrued = _accrued_interest(
        coupon_pct=coupon_pct,
        settlement_date=settlement_ts,
        next_coupon_date=cashflows[0][0],
        period_months=period_months,
        face=face,
        freq=freq,
    )
    return dirty_price - accrued


def duration_convexity_from_ytm(
    cashflows: list[tuple[pd.Timestamp, float]],
    ytm_pct: float,
    settlement_date,
) -> tuple[float, float]:
    price_0 = price_from_ytm(cashflows, ytm_pct, settlement_date)
    price_up = price_from_ytm(cashflows, ytm_pct + BUMP_BP, settlement_date)
    price_down = price_from_ytm(cashflows, ytm_pct - BUMP_BP, settlement_date)
    dy = BUMP_BP / 100.0
    modified_duration = (price_down - price_up) / (2.0 * price_0 * dy)
    convexity = (price_down + price_up - 2.0 * price_0) / (price_0 * (dy**2))
    return modified_duration, convexity
