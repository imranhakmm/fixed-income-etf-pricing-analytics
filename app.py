from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pricing import build_cashflows, duration_convexity_from_ytm


APP_DIR = Path(__file__).resolve().parent
APP_TIMESTAMP = pd.Timestamp.now(tz="Europe/London")
APP_DATE = APP_TIMESTAMP.tz_localize(None).normalize()
ETF_FILE_MAP = {
    "IEF": APP_DIR / "data" / "ief_holdings_realistic.csv",
    "LQD": APP_DIR / "data" / "lqd_holdings_realistic.csv",
}
ETF_LABEL_MAP = {
    "IEF (Treasury)": "IEF",
    "LQD (IG Credit)": "LQD",
}
ETF_DEFAULT_PD_BP = {
    "IEF": 3.0,
    "LQD": 18.0,
}
DEFAULT_STALENESS_SECONDS = 15
STALE_MARK_WARNING_SECONDS = 60
EVALUATED_MARK_SWITCH_SECONDS = 30
SENSITIVITY_SHOCK_RANGE_BP = 300
DEFAULT_PORTFOLIO_NOTIONAL_USD = 10_000_000
TY_DV01_PER_BP_USD = 76.0  # Approximate TY futures DV01 per 1 bp using a CTD-style desk assumption.
CDX_IG_DV01_PER_BP_USD = 4500.0  # Approximate CDX IG DV01 per 1 bp for $10mm index notional.
SPREAD_DURATION_FACTOR = 0.95  # IG corporate spread duration ≈ rates duration in benign credit regimes; refine per-bond in production.
PD_DISPLAY_OPTIONS = ["bp", "%"]
PD_HISTORY_LOOKBACK_DAYS = 90
PD_HISTORY_DAILY_SD_BP = {
    "IEF": 1.0,
    "LQD": 5.0,
}

REQUIRED_COLUMNS = [
    "cusip",
    "description",
    "maturity",
    "coupon",
    "weight_pct",
    "clean_price",
    "yield_pct",
    "duration",
    "convexity",
    "bid_ask_bps",
    "liquidity_score",
]
OPTIONAL_COLUMNS = ["spread_duration"]

NUMERIC_COLUMNS = [
    "coupon",
    "weight_pct",
    "clean_price",
    "yield_pct",
    "duration",
    "convexity",
    "bid_ask_bps",
    "liquidity_score",
]
OPTIONAL_NUMERIC_COLUMNS = ["spread_duration"]

BUCKET_ORDER = ["0-3y", "3-5y", "5-7y", "7-10y", "10y+"]
CURVE_TWISTS = {
    "None": (0.0, 0.0),
    "Bull steepener": (-15.0, -5.0),
    "Bear steepener": (5.0, 15.0),
    "Bull flattener": (-5.0, -15.0),
    "Bear flattener": (15.0, 5.0),
}

PALETTE = ["#0F4C81", "#1D6F42", "#556B8E", "#8AA1B1", "#B08968"]
DISCLAIMER = (
    "Educational prototype using illustrative ETF baskets, simplified AP economics and duration-convexity pricing."
)


def get_plotly_template() -> str:
    """Return plotly template matching Streamlit theme base."""
    try:
        return "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
    except Exception:
        return "plotly_white"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        :root {
            --app-font-sans: 'Inter', sans-serif;
            --app-font-mono: 'JetBrains Mono', monospace;
            --bg-base: #FFFFFF;
            --bg-surface: #FFFFFF;
            --bg-sidebar: #F6F8FB;
            --border: #D8E0E8;
            --text-primary: #102A43;
            --text-secondary: #52606D;
            --accent: #0F4C81;
            --shadow: rgba(15, 23, 42, 0.04);
            --inline-code-bg: rgba(15, 23, 42, 0.06);
            --inline-code-text: #0F172A;
            --danger: #9B2C2C;
            --success: #1D6F42;
            --alert-bg: #EAF2FF;
            --tab-active: var(--accent);
            --plot-grid: rgba(148, 163, 184, 0.32);
            --plot-reference: rgba(112, 128, 144, 0.9);
        }

        .stApp[data-theme="dark"] {
            --bg-base: #0F1B2E;
            --bg-surface: #1A2740;
            --bg-sidebar: #14213D;
            --border: #2A3A5C;
            --text-primary: #E6EDF7;
            --text-secondary: #9BAACE;
            --accent: #3D7AB8;
            --shadow: rgba(0, 0, 0, 0.22);
            --inline-code-bg: rgba(230, 237, 247, 0.08);
            --inline-code-text: #E6EDF7;
            --danger: #F28B82;
            --success: #7CD992;
            --alert-bg: var(--bg-surface);
            --tab-active: var(--accent);
            --plot-grid: rgba(155, 170, 206, 0.22);
            --plot-reference: rgba(155, 170, 206, 0.8);
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg-base: #0F1B2E;
                --bg-surface: #1A2740;
                --bg-sidebar: #14213D;
                --border: #2A3A5C;
                --text-primary: #E6EDF7;
                --text-secondary: #9BAACE;
                --accent: #3D7AB8;
                --shadow: rgba(0, 0, 0, 0.22);
                --inline-code-bg: rgba(230, 237, 247, 0.08);
                --inline-code-text: #E6EDF7;
                --danger: #F28B82;
                --success: #7CD992;
                --alert-bg: var(--bg-surface);
                --tab-active: var(--accent);
                --plot-grid: rgba(155, 170, 206, 0.22);
                --plot-reference: rgba(155, 170, 206, 0.8);
            }
        }

        .stApp[data-theme="light"] {
            --bg-base: #FFFFFF;
            --bg-surface: #FFFFFF;
            --bg-sidebar: #F6F8FB;
            --border: #D8E0E8;
            --text-primary: #102A43;
            --text-secondary: #52606D;
            --accent: #0F4C81;
            --shadow: rgba(15, 23, 42, 0.04);
            --inline-code-bg: rgba(15, 23, 42, 0.06);
            --inline-code-text: #0F172A;
            --danger: #9B2C2C;
            --success: #1D6F42;
            --alert-bg: #EAF2FF;
            --tab-active: var(--accent);
            --plot-grid: rgba(148, 163, 184, 0.32);
            --plot-reference: rgba(112, 128, 144, 0.9);
        }

        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
            font-family: var(--app-font-sans);
            color: var(--text-primary);
        }

        .stApp, [data-testid="stAppViewContainer"] {
            background: var(--bg-base);
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }
        [data-testid="stSidebar"] {
            background: var(--bg-sidebar);
            color: var(--text-primary);
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] li,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stMarkdown * {
            color: var(--text-primary) !important;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"],
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *,
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background-color: var(--bg-surface) !important;
            color: var(--text-primary) !important;
            border-color: var(--border) !important;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] svg,
        [data-testid="stSidebar"] svg {
            color: var(--text-secondary) !important;
            fill: var(--text-secondary) !important;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp li, .stApp label, .stApp span, .stApp div, .stApp small {
            color: var(--text-primary);
        }
        [data-testid="stMetric"] {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.55rem 0.75rem;
            min-width: 150px;
            box-shadow: 0 1px 2px var(--shadow);
        }
        [data-testid="stMetricValue"] {
            color: var(--text-primary);
            font-family: var(--app-font-mono);
            font-weight: 600;
            letter-spacing: -0.03em;
            font-size: 1.4rem;
            white-space: nowrap;
            overflow: visible;
            text-overflow: clip;
        }
        [data-testid="stMetricLabel"] {
            color: var(--text-secondary);
            font-size: 0.88rem;
            font-family: var(--app-font-sans);
        }
        [data-testid="stMetricDelta"] {
            font-family: var(--app-font-mono);
        }
        [data-testid="stAlert"] {
            background: var(--alert-bg);
            color: var(--text-primary);
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
        }
        [data-testid="stAlert"] * {
            color: var(--text-primary) !important;
        }
        button[role="tab"] {
            color: var(--text-secondary) !important;
        }
        button[role="tab"][aria-selected="true"] {
            color: var(--text-primary) !important;
            border-bottom-color: var(--tab-active) !important;
            box-shadow: inset 0 -2px 0 var(--tab-active);
        }
        h1, h2, h3, h4, h5, h6, p, li, label, span, div, button, input, textarea, select, small {
            font-family: var(--app-font-sans);
            letter-spacing: -0.02em;
        }
        code, pre, kbd, samp, tt, .stCode, [data-testid="stCodeBlock"], .highlight {
            font-family: var(--app-font-mono) !important;
        }
        .stMarkdown code {
            font-family: var(--app-font-mono) !important;
            background: var(--inline-code-bg);
            color: var(--inline-code-text);
            border-radius: 6px;
            padding: 0.08rem 0.34rem;
        }
        .stMarkdown pre code {
            background: transparent;
            padding: 0;
        }
        .subtle-note {
            color: var(--text-secondary);
            font-size: 0.95rem;
            line-height: 1.4;
        }
        .stale-caption {
            margin-top: 0.15rem;
            color: var(--danger);
            font-size: 0.8rem;
            line-height: 1.2;
        }
        .signal-card {
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 0.9rem 1rem;
            background: var(--bg-surface);
        }
        .signal-card__label {
            color: var(--text-secondary);
            font-size: 0.88rem;
            margin-bottom: 0.35rem;
        }
        .signal-card__value {
            font-family: var(--app-font-mono);
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        .signal-positive .signal-card__value {
            color: var(--success);
        }
        .signal-negative .signal-card__value {
            color: var(--danger);
        }
        .compact-metric-card {
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 0.55rem 0.75rem;
            background: var(--bg-surface);
            box-shadow: 0 1px 2px var(--shadow);
            min-height: 104px;
            min-width: 150px;
        }
        .compact-metric-label {
            color: var(--text-secondary);
            font-size: 0.88rem;
            margin-bottom: 0.2rem;
        }
        .compact-metric-value {
            font-family: var(--app-font-mono);
            font-size: 1.18rem;
            font-weight: 700;
            line-height: 1.12;
            white-space: nowrap;
            overflow: visible;
            text-overflow: clip;
            color: var(--text-primary);
            display: inline;
        }
        .compact-metric-secondary {
            font-family: var(--app-font-mono);
            font-size: 1.0rem;
            font-weight: 600;
            line-height: 1.12;
            white-space: nowrap;
            overflow: visible;
            text-overflow: clip;
            color: var(--text-secondary);
            margin-top: 0;
            margin-left: 0.32rem;
            display: inline;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def assign_bucket(years_to_maturity: float) -> str:
    if years_to_maturity < 3:
        return "0-3y"
    if years_to_maturity < 5:
        return "3-5y"
    if years_to_maturity < 7:
        return "5-7y"
    if years_to_maturity < 10:
        return "7-10y"
    return "10y+"


def scenario_curve_adjustment(years: np.ndarray, scenario: str) -> np.ndarray:
    short_bp, long_bp = CURVE_TWISTS[scenario]
    clipped = np.clip(years, 1.0, 10.0)
    return np.interp(clipped, [1.0, 10.0], [short_bp, long_bp])


def prepare_holdings(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = raw_df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        required = ", ".join(REQUIRED_COLUMNS)
        raise ValueError(
            "Uploaded CSV is missing required columns: "
            + ", ".join(missing)
            + f". Required columns: {required}."
        )

    optional_columns = [column for column in OPTIONAL_COLUMNS if column in df.columns]
    df = df[[*REQUIRED_COLUMNS, *optional_columns]].copy()
    for column in NUMERIC_COLUMNS:
        df[column] = to_numeric(df[column])
    for column in OPTIONAL_NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = to_numeric(df[column])
    df["maturity"] = pd.to_datetime(df["maturity"], errors="coerce")

    critical_cols = ["cusip", "description", "maturity", *NUMERIC_COLUMNS]
    invalid_mask = df[critical_cols].isna().any(axis=1)
    messages: list[str] = []
    if invalid_mask.any():
        invalid_count = int(invalid_mask.sum())
        messages.append(f"Dropped {invalid_count} row(s) with invalid or blank values in the uploaded CSV.")
        df = df.loc[~invalid_mask].copy()

    if df.empty:
        raise ValueError("No valid rows remain after cleaning the uploaded CSV.")

    df["cusip"] = df["cusip"].astype(str).str.strip()
    df["description"] = df["description"].astype(str).str.strip()

    weight_sum = float(df["weight_pct"].sum())
    if not np.isfinite(weight_sum) or weight_sum <= 0:
        raise ValueError("weight_pct must sum to a positive number.")
    if abs(weight_sum - 100.0) > 0.5:
        messages.append(f"weight_pct sums to {weight_sum:.2f}; calculations will be normalized to 100%.")

    today = APP_DATE
    df["weight_share"] = df["weight_pct"] / weight_sum
    df["years_to_maturity"] = ((df["maturity"] - today).dt.days / 365.25).clip(lower=0)
    df["bucket"] = df["years_to_maturity"].apply(assign_bucket)
    df["maturity_label"] = df["maturity"].dt.strftime("%Y-%m-%d")
    df = df.sort_values("weight_pct", ascending=False).reset_index(drop=True)

    return df, messages


@st.cache_data(show_spinner=False)
def load_sample_holdings(etf_code: str) -> pd.DataFrame:
    return pd.read_csv(ETF_FILE_MAP[etf_code])


def apply_etf_specific_fields(df: pd.DataFrame, etf_code: str) -> pd.DataFrame:
    adjusted_df = df.copy()
    if etf_code == "LQD":
        adjusted_df["spread_duration"] = adjusted_df["duration"] * SPREAD_DURATION_FACTOR
    return adjusted_df


def load_holdings(uploaded_file, etf_code: str) -> tuple[pd.DataFrame, str, list[str]]:
    if uploaded_file is None:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        prepared = apply_etf_specific_fields(prepared, etf_code)
        return prepared, f"Illustrative {etf_code} basket", messages

    try:
        raw_df = pd.read_csv(uploaded_file)
        prepared, messages = prepare_holdings(raw_df)
        prepared = apply_etf_specific_fields(prepared, etf_code)
        return prepared, "Uploaded holdings", messages
    except ValueError as exc:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        prepared = apply_etf_specific_fields(prepared, etf_code)
        messages = [f"{exc} Falling back to the bundled {etf_code} basket."] + messages
        return prepared, f"Illustrative {etf_code} basket", messages
    except Exception as exc:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        prepared = apply_etf_specific_fields(prepared, etf_code)
        messages = [f"Could not read the uploaded CSV ({exc}). Falling back to the bundled {etf_code} basket."] + messages
        return prepared, f"Illustrative {etf_code} basket", messages


def weighted_average(df: pd.DataFrame, column: str) -> float:
    return float((df["weight_share"] * df[column]).sum())


def weighted_nav_from_series(df: pd.DataFrame, price_series: pd.Series) -> float:
    return float((df["weight_share"] * price_series).sum())


def get_default_last_trade(etf_code: str, inav_proxy: float) -> float:
    return round(inav_proxy * (1.0 + ETF_DEFAULT_PD_BP[etf_code] / 10000.0), 2)


def dv01_per_10mm_from_per_100(dv01_per_100: float) -> float:
    return dv01_per_100 * (DEFAULT_PORTFOLIO_NOTIONAL_USD / 100.0)


def compute_credit_dv01_per_10mm(inav_proxy: float, weighted_spread_duration: float) -> float:
    return inav_proxy * weighted_spread_duration * 0.0001 * (DEFAULT_PORTFOLIO_NOTIONAL_USD / 100.0)


def compute_cdx_ig_overlay_notional(credit_dv01_per_10mm: float) -> float:
    return (credit_dv01_per_10mm / CDX_IG_DV01_PER_BP_USD) * DEFAULT_PORTFOLIO_NOTIONAL_USD


def build_synthetic_pd_history(etf_code: str, current_pd_bp: float) -> pd.DataFrame:
    history_dates = pd.bdate_range(end=APP_DATE, periods=PD_HISTORY_LOOKBACK_DAYS)
    rng = np.random.default_rng(stable_seed_from_cusip(f"{etf_code}-pd-history"))
    pd_changes = rng.normal(0.0, PD_HISTORY_DAILY_SD_BP[etf_code], len(history_dates))
    pd_levels = np.cumsum(pd_changes)
    pd_levels = pd_levels - pd_levels[-1] + current_pd_bp
    history_df = pd.DataFrame({"date": history_dates, "pd_bp": pd_levels})
    mean_bp = float(history_df["pd_bp"].mean())
    sigma_bp = float(history_df["pd_bp"].std(ddof=0))
    history_df["mean_bp"] = mean_bp
    history_df["upper_band_bp"] = mean_bp + (2.0 * sigma_bp)
    history_df["lower_band_bp"] = mean_bp - (2.0 * sigma_bp)
    return history_df


def apply_cashflow_risk_overrides(df: pd.DataFrame, settlement_date: pd.Timestamp) -> pd.DataFrame:
    overridden_df = df.copy()
    durations: list[float] = []
    convexities: list[float] = []
    for row in overridden_df.itertuples(index=False):
        cashflows = build_cashflows(
            coupon_pct=float(row.coupon),
            maturity_date=row.maturity,
            settlement_date=settlement_date,
        )
        duration, convexity = duration_convexity_from_ytm(
            cashflows=cashflows,
            ytm_pct=float(row.yield_pct),
            settlement_date=settlement_date,
        )
        durations.append(duration)
        convexities.append(convexity)
    overridden_df["duration"] = durations
    overridden_df["convexity"] = convexities
    return overridden_df


def stable_seed_from_cusip(cusip: str) -> int:
    return int(hashlib.sha256(cusip.encode("utf-8")).hexdigest()[:8], 16)


def build_pricing_waterfall(df: pd.DataFrame, staleness_seconds: int) -> tuple[pd.DataFrame, dict]:
    pricing_df = df.copy()
    stale_factor = min(staleness_seconds / EVALUATED_MARK_SWITCH_SECONDS, 1.0)
    pricing_df["last_trade_price"] = pricing_df["clean_price"]
    pricing_df["evaluated_price"] = pricing_df["last_trade_price"] - (
        (pricing_df["bid_ask_bps"] / 2.0 / 10000.0) * pricing_df["last_trade_price"] * stale_factor
    )
    pricing_df["chosen_price"] = np.where(
        staleness_seconds < EVALUATED_MARK_SWITCH_SECONDS,
        pricing_df["last_trade_price"],
        pricing_df["evaluated_price"],
    )

    nav_last_trade = weighted_nav_from_series(pricing_df, pricing_df["last_trade_price"])
    nav_evaluated = weighted_nav_from_series(pricing_df, pricing_df["evaluated_price"])
    nav_chosen = weighted_nav_from_series(pricing_df, pricing_df["chosen_price"])
    evaluated_deltas_bp = ((pricing_df["evaluated_price"] - pricing_df["last_trade_price"]) / pricing_df["last_trade_price"]) * 10000.0
    return pricing_df, {
        "nav_last_trade": nav_last_trade,
        "nav_evaluated": nav_evaluated,
        "nav_chosen": nav_chosen,
        "nav_last_trade_bp": 0.0,
        "nav_evaluated_bp": (nav_evaluated / nav_last_trade - 1.0) * 10000.0,
        "nav_chosen_bp": (nav_chosen / nav_last_trade - 1.0) * 10000.0,
        "basket_dispersion_bp": float(evaluated_deltas_bp.std(ddof=0)),
        "stale_factor": stale_factor,
    }


def compute_ap_economics(
    df: pd.DataFrame,
    inav_proxy: float,
    last_trade: float,
    financing_bp: float,
    cross_bp: float,
) -> dict:
    half_spread_adjustment = (df["bid_ask_bps"] / 2.0 / 100.0) * (df["clean_price"] / 100.0)
    basket_bid_nav = weighted_nav_from_series(df, df["clean_price"] - half_spread_adjustment)
    basket_offer_nav = weighted_nav_from_series(df, df["clean_price"] + half_spread_adjustment)
    create_cost_bp = (basket_offer_nav / inav_proxy - 1.0) * 10000.0 + financing_bp + cross_bp
    redeem_cost_bp = (1.0 - basket_bid_nav / inav_proxy) * 10000.0 + financing_bp + cross_bp
    etf_premium_bp = (last_trade - inav_proxy) / inav_proxy * 10000.0
    create_arb_bp = etf_premium_bp - create_cost_bp
    redeem_arb_bp = -etf_premium_bp - redeem_cost_bp
    return {
        "basket_bid_nav": basket_bid_nav,
        "basket_offer_nav": basket_offer_nav,
        "create_cost_bp": create_cost_bp,
        "redeem_cost_bp": redeem_cost_bp,
        "etf_premium_bp": etf_premium_bp,
        "create_arb_bp": create_arb_bp,
        "redeem_arb_bp": redeem_arb_bp,
    }


def compute_bond_shocked_price(row: pd.Series, effective_shock_bp: float) -> float:
    dy = effective_shock_bp / 10000.0
    pct_change = (-row["duration"] * dy) + (0.5 * row["convexity"] * (dy**2))
    return float(row["clean_price"] * (1.0 + pct_change))


def compute_portfolio_value(df: pd.DataFrame, shock_bp: float, scenario: str, liquidity_penalty_pct: float) -> tuple[float, pd.Series]:
    curve_bp = scenario_curve_adjustment(df["years_to_maturity"].to_numpy(), scenario)
    total_bp = shock_bp + curve_bp
    dy = total_bp / 10000.0
    shock_pct = (-df["duration"] * dy) + (0.5 * df["convexity"] * (dy**2))
    shocked_price = df["clean_price"] * (1.0 + shock_pct)
    shocked_value = float((df["weight_share"] * shocked_price).sum())
    shocked_value *= 1.0 - liquidity_penalty_pct
    return shocked_value, shocked_price


def compute_sensitivity_curve(
    df: pd.DataFrame,
    base_nav: float,
    scenario: str,
    liquidity_penalty_pct: float,
) -> pd.DataFrame:
    gross_base_value = float((df["weight_share"] * df["clean_price"]).sum())
    weighted_duration = weighted_average(df, "duration")
    shock_grid = np.arange(-SENSITIVITY_SHOCK_RANGE_BP, SENSITIVITY_SHOCK_RANGE_BP + 1, 1)
    values = []
    linear_values = []
    for shock_bp in shock_grid:
        shocked_value, _ = compute_portfolio_value(df, float(shock_bp), scenario, liquidity_penalty_pct)
        shock_factor = shocked_value / gross_base_value if gross_base_value else 1.0
        values.append(base_nav * shock_factor)
        linear_values.append(base_nav * (1.0 - (weighted_duration * shock_bp / 10000.0)))
    return pd.DataFrame({"shock_bp": shock_grid, "implied_nav": values, "linear_nav": linear_values})


def build_bucket_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    bucket_df = df.groupby("bucket", as_index=False)["weight_pct"].sum()
    bucket_df["bucket"] = pd.Categorical(bucket_df["bucket"], categories=BUCKET_ORDER, ordered=True)
    bucket_df = bucket_df.sort_values("bucket")
    full = pd.DataFrame({"bucket": BUCKET_ORDER}).merge(bucket_df, on="bucket", how="left")
    full["weight_pct"] = full["weight_pct"].fillna(0.0)
    return full


def build_top_holdings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df.nlargest(n, "weight_pct").sort_values("weight_pct", ascending=True).copy()


def build_dv01_contributors(df: pd.DataFrame) -> pd.DataFrame:
    contributors = df.copy()
    contributors["dv01_per_100"] = contributors["weight_share"] * contributors["clean_price"] * contributors["duration"] * 0.0001
    contributors["dv01_per_10mm"] = contributors["dv01_per_100"] * (DEFAULT_PORTFOLIO_NOTIONAL_USD / 100.0)
    return contributors.nlargest(10, "dv01_per_10mm").sort_values("dv01_per_10mm", ascending=True)


def make_metric_cards(
    metrics: dict,
    etf_code: str,
) -> None:
    headline_cols = st.columns(4)
    with headline_cols[0]:
        st.metric("iNAV (basket)", f"${metrics['inav_proxy']:,.2f}")
    with headline_cols[1]:
        st.metric("Last trade", f"${metrics['last_trade']:,.2f}")
    with headline_cols[2]:
        st.segmented_control(
            "P/D display",
            options=PD_DISPLAY_OPTIONS,
            default="bp",
            key="pd_display_unit",
            label_visibility="collapsed",
        )
        pd_display_unit = st.session_state.get("pd_display_unit", "bp")
        pd_label = "P/D (bps)" if pd_display_unit == "bp" else "P/D (%)"
        pd_value = (
            f"{metrics['premium_discount_bp']:+.1f} bp"
            if pd_display_unit == "bp"
            else f"{metrics['premium_discount_pct']:+.3f}%"
        )
        st.metric(pd_label, pd_value, delta=f"{metrics['last_trade'] - metrics['inav_proxy']:+.2f} vs iNAV")
        if metrics["staleness_seconds"] > STALE_MARK_WARNING_SECONDS:
            st.markdown('<div class="stale-caption">stale basket marks</div>', unsafe_allow_html=True)
    with headline_cols[3]:
        st.metric("Staleness (s)", f"{int(metrics['staleness_seconds'])}")

    risk_specs = [
        ("Weighted duration", f"{metrics['weighted_duration']:.2f} yrs", None),
        ("Weighted convexity", f"{metrics['weighted_convexity']:.1f}", None),
    ]
    risk_cols = st.columns(len(risk_specs))
    for col, (label, value, delta) in zip(risk_cols, risk_specs):
        with col:
            st.metric(label, value, delta=delta)

    hedge_specs = [
        (
            "DV01",
            f"${metrics['dv01_per_100']:.3f} / $100  ·  ${metrics['dv01_per_10mm']:,.0f} / $10mm",
            None,
        ),
        ("TY hedge", f"{metrics['ty_hedge_contracts']} TY contracts / $10mm", None),
    ]
    if etf_code == "LQD":
        hedge_specs.append(
            ("CDX IG overlay", f"${metrics['cdx_ig_overlay_notional'] / 1_000_000:.1f}mm / $10mm", None)
        )
    hedge_cols = st.columns(len(hedge_specs))
    for col, (label, value, delta) in zip(hedge_cols, hedge_specs):
        with col:
            if label == "DV01":
                render_compact_metric_tile(label, f"${metrics['dv01_per_100']:.3f} / $100", f"${metrics['dv01_per_10mm']:,.0f} / $10mm")
            elif label == "TY hedge":
                render_compact_metric_tile(label, f"{metrics['ty_hedge_contracts']} TY contracts", "per $10mm")
            elif label == "CDX IG overlay":
                render_compact_metric_tile(label, f"${metrics['cdx_ig_overlay_notional'] / 1_000_000:.1f}mm", "/ $10mm")
            else:
                st.metric(label, value, delta=delta)
    if etf_code == "LQD":
        st.caption("Sized off credit spread DV01, not rates DV01.")

    tertiary_specs = [
        ("Weighted bid/ask", f"{metrics['weighted_bid_ask_bps']:.2f} bps", None),
        ("Top 5 concentration", f"{metrics['top_5_concentration']:.1f}%", None),
        ("Liquidity score", f"{metrics['weighted_liquidity_score']:.2f} / 5", None),
    ]
    tertiary_cols = st.columns(len(tertiary_specs))
    for col, (label, value, delta) in zip(tertiary_cols, tertiary_specs):
        with col:
            st.metric(label, value, delta=delta)


def format_interpretation(
    metrics: dict,
    bucket_df: pd.DataFrame,
) -> list[str]:
    bullets: list[str] = []
    abs_pd_bp = abs(metrics["premium_discount_bp"])
    weighted_bid_ask = metrics["weighted_bid_ask_bps"]
    rich_or_cheap = "rich" if metrics["premium_discount_bp"] > 0 else "cheap"
    dominant_bucket = bucket_df.sort_values("weight_pct", ascending=False).iloc[0]

    if abs_pd_bp < 5 and weighted_bid_ask < 5:
        bullets.append("Basket trades within market frictions; no AP edge available.")
    elif abs_pd_bp > 30 and weighted_bid_ask < 10:
        bullets.append(
            f"Persistent {rich_or_cheap} dislocation in a tight basket; check inventory and recency before sizing."
        )
    elif abs_pd_bp > 50 and weighted_bid_ask > 20:
        bullets.append("Wide P/D in an illiquid basket; likely stale marks, do not act without iNAV refresh.")
    else:
        bullets.append(
            f"Moderate {rich_or_cheap} basis versus the basket proxy; tradeability depends more on basket liquidity than on headline P/D alone."
        )

    if metrics["create_arb_bp"] > 0:
        bullets.append(
            f"Create-side economics are positive at {metrics['create_arb_bp']:+.1f} bp after financing and crossing costs."
        )
    elif metrics["redeem_arb_bp"] > 0:
        bullets.append(
            f"Redeem-side economics are positive at {metrics['redeem_arb_bp']:+.1f} bp after financing and crossing costs."
        )
    else:
        bullets.append("Neither create nor redeem clears estimated costs at current marks.")

    if metrics["curve_scenario"] != "None":
        if dominant_bucket["bucket"] in {"7-10y", "10y+"}:
            bullets.append(
                f"{metrics['curve_scenario']} scenario risk is driven by the long end because {dominant_bucket['bucket']} bonds carry {dominant_bucket['weight_pct']:.1f}% of the basket."
            )
        else:
            bullets.append(
                f"{metrics['curve_scenario']} scenario risk is concentrated in the intermediate bucket, so front-to-belly curve moves dominate P&L."
            )
    else:
        bullets.append(
            f"Basket concentration is moderate: top five holdings are {metrics['top_5_concentration']:.1f}% and the dominant bucket is {dominant_bucket['bucket']}."
        )

    bullets.append(
        f"Rates hedge with {metrics['ty_hedge_contracts']} TY contracts neutralises parallel rate DV01; residual exposure is curve and basis."
    )
    return bullets[:4]


def plot_bucket_exposure(bucket_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        bucket_df,
        x="bucket",
        y="weight_pct",
        text="weight_pct",
        color="bucket",
        category_orders={"bucket": BUCKET_ORDER},
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    fig.update_layout(
        template=get_plotly_template(),
        title="Maturity Bucket Exposure",
        xaxis_title="Remaining maturity bucket",
        yaxis_title="Weight (%)",
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        height=360,
    )
    fig.update_yaxes(range=[0, max(100, float(bucket_df["weight_pct"].max()) * 1.2)])
    return fig


def plot_top_holdings(top_holdings: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        top_holdings,
        x="weight_pct",
        y="description",
        orientation="h",
        text="weight_pct",
        color_discrete_sequence=[PALETTE[0]],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
    fig.update_layout(
        template=get_plotly_template(),
        title="Top Holdings by Weight",
        xaxis_title="Weight (%)",
        yaxis_title="Holding",
        margin=dict(l=10, r=10, t=50, b=10),
        height=360,
        showlegend=False,
    )
    return fig


def plot_sensitivity_curve(curve_df: pd.DataFrame, current_shock_bp: int, current_nav: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=curve_df["shock_bp"],
            y=curve_df["implied_nav"],
            mode="lines",
            line=dict(color=PALETTE[0], width=3),
            name="Implied NAV",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=curve_df["shock_bp"],
            y=curve_df["linear_nav"],
            mode="lines",
            line=dict(color=PALETTE[2], width=2, dash="dash"),
            name="Duration only (linear)",
        )
    )
    selected_nav = float(curve_df.loc[curve_df["shock_bp"] == current_shock_bp, "implied_nav"].iloc[0])
    fig.add_trace(
        go.Scatter(
            x=[current_shock_bp],
            y=[selected_nav],
            mode="markers",
            marker=dict(size=11, color=PALETTE[1], line=dict(color="rgba(255,255,255,0.92)", width=1.5)),
            name="Selected shock",
        )
    )
    fig.add_vline(x=current_shock_bp, line_width=1, line_dash="dash", line_color="rgba(112, 128, 144, 0.85)")
    fig.add_hline(y=current_nav, line_width=1, line_dash="dot", line_color="rgba(160, 174, 192, 0.9)")
    fig.update_layout(
        template=get_plotly_template(),
        title="NAV Sensitivity Under Parallel Shocks",
        xaxis_title="Parallel shock (bp)",
        yaxis_title="Implied NAV",
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
        legend_title_text="",
    )
    return fig


def plot_pd_history(history_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history_df["date"],
            y=history_df["pd_bp"],
            mode="lines",
            line=dict(color=PALETTE[0], width=2.5),
            name="P/D",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history_df["date"],
            y=history_df["upper_band_bp"],
            mode="lines",
            line=dict(color="rgba(148, 163, 184, 0.9)", width=1, dash="dash"),
            name="+2σ band",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history_df["date"],
            y=history_df["lower_band_bp"],
            mode="lines",
            line=dict(color="rgba(148, 163, 184, 0.9)", width=1, dash="dash"),
            fill="tonexty",
            fillcolor="rgba(148, 163, 184, 0.14)",
            name="-2σ band",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history_df["date"],
            y=history_df["mean_bp"],
            mode="lines",
            line=dict(color=PALETTE[1], width=1.5, dash="dot"),
            name="Mean",
        )
    )
    fig.update_layout(
        template=get_plotly_template(),
        title="Premium / Discount History",
        xaxis_title="Date",
        yaxis_title="P/D (bp)",
        margin=dict(l=10, r=10, t=50, b=10),
        height=320,
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def plot_duration_yield_scatter(df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        df,
        x="yield_pct",
        y="duration",
        size="weight_pct",
        color="bucket",
        hover_name="description",
        hover_data={
            "cusip": True,
            "weight_pct": ":.2f",
            "yield_pct": ":.2f",
            "duration": ":.2f",
            "liquidity_score": ":.2f",
            "bucket": True,
        },
        size_max=28,
        color_discrete_sequence=PALETTE,
        category_orders={"bucket": BUCKET_ORDER},
    )
    fig.update_layout(
        template=get_plotly_template(),
        title="Duration vs. Yield",
        xaxis_title="Yield (%)",
        yaxis_title="Duration (yrs)",
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
        legend_title_text="Maturity bucket",
    )
    return fig


def plot_dv01_contributors(contributors_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        contributors_df,
        x="dv01_per_10mm",
        y="description",
        orientation="h",
        text="dv01_per_10mm",
        color_discrete_sequence=[PALETTE[2]],
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        template=get_plotly_template(),
        title="Top DV01 Contributors",
        xaxis_title="DV01 per $10mm",
        yaxis_title="Holding",
        margin=dict(l=10, r=10, t=50, b=10),
        height=360,
        showlegend=False,
    )
    return fig


def style_holdings_table(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    display["maturity"] = display["maturity"].dt.strftime("%Y-%m-%d")
    numeric_cols = ["weight_pct", "clean_price", "shocked_price", "yield_pct", "duration", "convexity", "bid_ask_bps", "liquidity_score"]
    for column in numeric_cols:
        if column in display.columns:
            display[column] = display[column].astype(float).round(2)
    return display[
        [
            "cusip",
            "description",
            "maturity",
            "bucket",
            "weight_pct",
            "clean_price",
            "shocked_price",
            "yield_pct",
            "duration",
            "convexity",
            "bid_ask_bps",
            "liquidity_score",
        ]
    ]


def style_pricing_detail_table(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    price_columns = [
        "weight_pct",
        "clean_price",
        "last_trade_price",
        "evaluated_price",
        "chosen_price",
        "bid_ask_bps",
    ]
    for column in price_columns:
        display[column] = display[column].astype(float).round(3 if "price" in column else 2)
    return display[
        [
            "cusip",
            "description",
            "weight_pct",
            "clean_price",
            "last_trade_price",
            "evaluated_price",
            "chosen_price",
            "bid_ask_bps",
        ]
    ]


def style_dv01_contributors_table(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    numeric_columns = ["weight_pct", "duration", "yield_pct", "dv01_per_100", "dv01_per_10mm"]
    for column in numeric_columns:
        display[column] = display[column].astype(float).round(3 if "dv01" in column else 2)
    return display[
        [
            "cusip",
            "description",
            "weight_pct",
            "yield_pct",
            "duration",
            "dv01_per_100",
            "dv01_per_10mm",
        ]
    ]


def render_signal_tile(label: str, value: float) -> None:
    signal_class = "signal-neutral"
    if value > 0:
        signal_class = "signal-positive"
    elif value < -10:
        signal_class = "signal-negative"
    st.markdown(
        f"""
        <div class="signal-card {signal_class}">
            <div class="signal-card__label">{label}</div>
            <div class="signal-card__value">{value:+.1f} bp</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_compact_metric_tile(label: str, primary_value: str, secondary_value: str | None = None) -> None:
    secondary_html = ""
    if secondary_value:
        secondary_html = f'<div class="compact-metric-secondary">{secondary_value}</div>'
    st.markdown(
        f"""
        <div class="compact-metric-card">
            <div class="compact-metric-label">{label}</div>
            <div class="compact-metric-value">{primary_value}</div>
            {secondary_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Fixed Income ETF Fair Value & Basket Analytics",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    st.title("Fixed Income ETF Fair Value & Basket Analytics")
    st.caption(f"As of {APP_TIMESTAMP:%Y-%m-%d %H:%M} London")
    st.caption("Basket-level pricing, iNAV proxy monitoring, DV01, curve shock sensitivity and basket diagnostics for Treasury and IG credit ETFs.")
    st.info(DISCLAIMER)

    selected_etf_label = st.sidebar.radio("ETF", options=list(ETF_LABEL_MAP.keys()), index=0)
    selected_etf_code = ETF_LABEL_MAP[selected_etf_label]
    if st.session_state.get("_cashflow_seed") != selected_etf_code:
        st.session_state.compute_duration_from_cashflows = selected_etf_code == "IEF"
        st.session_state._cashflow_seed = selected_etf_code
    st.sidebar.markdown("### Controls")
    st.sidebar.caption(
        "Upload a custom CSV or use the bundled realistic illustrative basket. Required columns: "
        + ", ".join(REQUIRED_COLUMNS)
        + "."
    )
    uploaded_file = st.sidebar.file_uploader("Upload custom holdings CSV", type=["csv"])

    holdings_df, data_source_label, load_messages = load_holdings(uploaded_file, selected_etf_code)
    compute_duration_from_cashflows = st.sidebar.toggle(
        "Compute duration from cashflows",
        key="compute_duration_from_cashflows",
    )
    settlement_date = APP_DATE
    if compute_duration_from_cashflows:
        holdings_df = apply_cashflow_risk_overrides(holdings_df, settlement_date)
        holdings_df = apply_etf_specific_fields(holdings_df, selected_etf_code)

    base_basket_nav = weighted_average(holdings_df, "clean_price")

    data_seed = f"{selected_etf_code}:{data_source_label}:{len(holdings_df)}:{round(base_basket_nav, 4)}"
    if st.session_state.get("_snapshot_seed") != data_seed:
        st.session_state.last_trade_input = get_default_last_trade(selected_etf_code, base_basket_nav)
        st.session_state.staleness_seconds = DEFAULT_STALENESS_SECONDS
        st.session_state._snapshot_seed = data_seed

    for message in load_messages:
        st.sidebar.warning(message)

    st.sidebar.success(f"Using {data_source_label.lower()}.")

    st.sidebar.markdown("### Snapshot")
    market_price = st.sidebar.number_input(
        "ETF last trade ($)",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="last_trade_input",
    )
    staleness_seconds = st.sidebar.slider(
        "Basket marks staleness (seconds)",
        min_value=0,
        max_value=300,
        step=1,
        key="staleness_seconds",
    )

    st.sidebar.markdown("### Rate shock")
    parallel_shock_bp = st.sidebar.slider(
        "Parallel yield shock (bp)",
        min_value=-100,
        max_value=100,
        value=0,
        step=1,
    )
    curve_scenario = st.sidebar.selectbox(
        "Steepener / flattener shock",
        options=list(CURVE_TWISTS.keys()),
        index=list(CURVE_TWISTS.keys()).index("None"),
        key="curve_scenario",
    )
    st.sidebar.markdown("### AP assumptions")
    financing_bp = st.sidebar.number_input(
        "Financing (bp)",
        min_value=0.0,
        value=5.0,
        step=0.5,
        format="%.1f",
        key="financing_bp",
    )
    cross_bp = st.sidebar.number_input(
        "Crossing / fees (bp)",
        min_value=0.0,
        value=1.0,
        step=0.5,
        format="%.1f",
        key="cross_bp",
    )

    weighted_duration = weighted_average(holdings_df, "duration")
    weighted_convexity = weighted_average(holdings_df, "convexity")
    weighted_spread_duration = weighted_average(holdings_df, "spread_duration") if "spread_duration" in holdings_df.columns else 0.0
    weighted_bid_ask_bps = weighted_average(holdings_df, "bid_ask_bps")
    weighted_liquidity_score = weighted_average(holdings_df, "liquidity_score")
    top_5_concentration = float(holdings_df.nlargest(5, "weight_pct")["weight_pct"].sum())
    pricing_detail_df, pricing_waterfall_metrics = build_pricing_waterfall(holdings_df, int(staleness_seconds))
    inav_proxy = pricing_waterfall_metrics["nav_chosen"]
    gross_base_value = weighted_nav_from_series(holdings_df, holdings_df["clean_price"])
    dv01_per_100 = inav_proxy * weighted_duration * 0.0001
    dv01_per_10mm = dv01_per_10mm_from_per_100(dv01_per_100)
    ty_hedge_contracts = round(dv01_per_10mm / TY_DV01_PER_BP_USD)
    credit_dv01_per_10mm = (
        compute_credit_dv01_per_10mm(inav_proxy, weighted_spread_duration) if selected_etf_code == "LQD" else None
    )
    cdx_ig_overlay_notional = (
        compute_cdx_ig_overlay_notional(credit_dv01_per_10mm) if credit_dv01_per_10mm is not None else None
    )
    premium_discount_pct = (market_price - inav_proxy) / inav_proxy * 100.0
    premium_discount_bp = premium_discount_pct * 100.0
    ap_economics = compute_ap_economics(
        holdings_df,
        inav_proxy=inav_proxy,
        last_trade=market_price,
        financing_bp=financing_bp,
        cross_bp=cross_bp,
    )

    current_shocked_gross_value, shocked_prices = compute_portfolio_value(
        holdings_df,
        float(parallel_shock_bp),
        curve_scenario,
        liquidity_penalty_pct=0.0,
    )
    current_shocked_nav = inav_proxy * (current_shocked_gross_value / gross_base_value) if gross_base_value else current_shocked_gross_value
    nav_move_pct = ((current_shocked_nav - inav_proxy) / inav_proxy * 100.0) if inav_proxy else 0.0

    metrics = {
        "inav_proxy": inav_proxy,
        "last_trade": market_price,
        "staleness_seconds": staleness_seconds,
        "weighted_duration": weighted_duration,
        "weighted_convexity": weighted_convexity,
        "weighted_spread_duration": weighted_spread_duration,
        "dv01_per_100": dv01_per_100,
        "dv01_per_10mm": dv01_per_10mm,
        "credit_dv01_per_10mm": credit_dv01_per_10mm,
        "ty_hedge_contracts": ty_hedge_contracts,
        "cdx_ig_overlay_notional": cdx_ig_overlay_notional,
        "premium_discount_pct": premium_discount_pct,
        "premium_discount_bp": premium_discount_bp,
        "top_5_concentration": top_5_concentration,
        "weighted_bid_ask_bps": weighted_bid_ask_bps,
        "weighted_liquidity_score": weighted_liquidity_score,
        "current_shocked_nav": current_shocked_nav,
        "curve_scenario": curve_scenario,
        "create_arb_bp": ap_economics["create_arb_bp"],
        "redeem_arb_bp": ap_economics["redeem_arb_bp"],
    }

    bucket_df = build_bucket_chart_data(holdings_df)
    top_holdings_df = build_top_holdings(holdings_df, n=10)
    dv01_contributors_df = build_dv01_contributors(holdings_df)
    sensitivity_df = compute_sensitivity_curve(
        holdings_df,
        base_nav=inav_proxy,
        scenario=curve_scenario,
        liquidity_penalty_pct=0.0,
    )
    pd_history_df = build_synthetic_pd_history(selected_etf_code, premium_discount_bp)
    interpretation_bullets = format_interpretation(metrics, bucket_df)

    overview_tab, sensitivity_tab, ap_tab, hedging_tab, method_tab = st.tabs(
        ["Overview", "Sensitivity", "AP economics", "Hedging", "Method"]
    )

    with overview_tab:
        make_metric_cards(metrics=metrics, etf_code=selected_etf_code)
        if compute_duration_from_cashflows:
            st.caption("Duration computed from cashflows.")

        st.plotly_chart(plot_pd_history(pd_history_df), use_container_width=True)
        st.caption(
            "Illustrative - synthetic history. The series is a seeded random walk with daily P/D volatility "
            f"set to about {PD_HISTORY_DAILY_SD_BP[selected_etf_code]:.0f} bp for {selected_etf_code}."
        )

        interp_col, desk_col = st.columns(2)
        with interp_col:
            st.subheader("Interpretation")
            st.markdown("\n".join(f"- {bullet}" for bullet in interpretation_bullets))
        with desk_col:
            st.subheader("Desk relevance")
            st.markdown(
                "\n".join(
                    [
                        "- Basket valuation to approximate iNAV from constituent bond marks.",
                        "- DV01 and hedge sizing to map ETF risk into TY futures or a CDX IG credit overlay.",
                        "- Premium/discount monitoring to compare last trade against a live basket proxy rather than a static NAV input.",
                        "- Liquidity and concentration diagnostics to support AP-style execution, hedging and basis discussions.",
                        "- A compact prototype that mirrors how a fixed-income ETF desk frames iNAV, basis and hedge questions intraday.",
                    ]
                )
            )

        st.caption(
            f"Model summary: iNAV ${inav_proxy:,.2f}; last trade ${market_price:,.2f}; duration {weighted_duration:.2f} yrs; "
            f"convexity {weighted_convexity:.1f}; weighted liquidity score {weighted_liquidity_score:.2f}/5."
        )

    with sensitivity_tab:
        st.subheader("Basket diagnostics")
        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            st.plotly_chart(plot_bucket_exposure(bucket_df), use_container_width=True)
        with chart_col_2:
            st.plotly_chart(plot_top_holdings(top_holdings_df), use_container_width=True)

        st.plotly_chart(
            plot_sensitivity_curve(
                sensitivity_df,
                current_shock_bp=parallel_shock_bp,
                current_nav=inav_proxy,
            ),
            use_container_width=True,
        )

        lower_col_1, lower_col_2 = st.columns([1.05, 1.25])
        with lower_col_1:
            st.plotly_chart(plot_duration_yield_scatter(holdings_df), use_container_width=True)
        with lower_col_2:
            display_df = holdings_df.copy()
            display_df["shocked_price"] = shocked_prices
            st.markdown("### Holdings table")
            st.dataframe(
                style_holdings_table(display_df),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Selected shock = {parallel_shock_bp:+d} bp with scenario '{curve_scenario}'. "
                f"Current shocked iNAV = ${current_shocked_nav:,.2f} ({nav_move_pct:+.2f}%)."
            )

        st.markdown("---")
        st.subheader("Basket pricing detail")
        nav_cols = st.columns(4)
        nav_specs = [
            ("iNAV at last trade", pricing_waterfall_metrics["nav_last_trade"], pricing_waterfall_metrics["nav_last_trade_bp"]),
            ("iNAV at evaluated", pricing_waterfall_metrics["nav_evaluated"], pricing_waterfall_metrics["nav_evaluated_bp"]),
            ("iNAV chosen", pricing_waterfall_metrics["nav_chosen"], pricing_waterfall_metrics["nav_chosen_bp"]),
            ("Basket dispersion (bp)", pricing_waterfall_metrics["basket_dispersion_bp"], None),
        ]
        for col, (label, value, bp_diff) in zip(nav_cols, nav_specs):
            with col:
                if label == "Basket dispersion (bp)":
                    st.metric(label, f"{value:.2f} bp")
                else:
                    st.metric(label, f"${value:,.2f}", delta=f"{bp_diff:+.2f} bp vs last-trade basket")
        st.caption("Cross-sectional stdev of evaluated marks vs last-trade across the basket.")
        st.caption(
            f"Chosen marks switch from last-trade prints to evaluated marks once basket staleness exceeds {EVALUATED_MARK_SWITCH_SECONDS} seconds."
        )
        st.dataframe(
            style_pricing_detail_table(pricing_detail_df),
            use_container_width=True,
            hide_index=True,
        )

    with ap_tab:
        st.subheader("AP economics")
        signal_cols = st.columns(2)
        with signal_cols[0]:
            render_signal_tile("Create arb (bp)", ap_economics["create_arb_bp"])
        with signal_cols[1]:
            render_signal_tile("Redeem arb (bp)", ap_economics["redeem_arb_bp"])

        ap_detail_cols = st.columns(4)
        ap_specs = [
            ("Basket bid NAV", f"${ap_economics['basket_bid_nav']:.2f}", None),
            ("Basket offer NAV", f"${ap_economics['basket_offer_nav']:.2f}", None),
            ("Create cost", f"{ap_economics['create_cost_bp']:.1f} bp", None),
            ("Redeem cost", f"{ap_economics['redeem_cost_bp']:.1f} bp", None),
        ]
        for col, (label, value, delta) in zip(ap_detail_cols, ap_specs):
            with col:
                st.metric(label, value, delta=delta)
        st.caption(
            "Create/redeem economics compare the ETF last trade against the basket proxy after half-spread, financing and crossing assumptions."
        )

    with hedging_tab:
        st.subheader("Hedge construction")
        hedge_summary_cols = st.columns(5 if selected_etf_code == "LQD" else 3)
        hedge_summaries = [
            ("DV01 / $100", f"${dv01_per_100:.3f}"),
            ("DV01 / $10mm", f"${dv01_per_10mm:,.0f}"),
            ("TY hedge", f"{ty_hedge_contracts} contracts"),
        ]
        if selected_etf_code == "LQD":
            hedge_summaries.extend(
                [
                    ("Spread duration", f"{weighted_spread_duration:.2f} yrs"),
                    ("CDX IG overlay", f"${cdx_ig_overlay_notional / 1_000_000:.1f}mm"),
                ]
            )
        for col, (label, value) in zip(hedge_summary_cols, hedge_summaries):
            with col:
                st.metric(label, value)
        if selected_etf_code == "LQD":
            st.caption("Sized off credit spread DV01, not rates DV01.")

        hedge_text_col, hedge_chart_col = st.columns([0.9, 1.1])
        with hedge_text_col:
            st.markdown(
                "\n".join(
                    [
                        "- Parallel-rate DV01 is translated into TY contracts using a $76 per bp desk assumption for the hedge future.",
                        "- The hedge is sized on a $10mm ETF risk unit so the number maps to an AP-style inventory conversation.",
                        "- TY neutralises first-order rates risk; residual P&L remains in curve shape, credit basis and mark quality.",
                        "- For LQD, the CDX IG overlay is sized off spread DV01 using a simple spread-duration factor.",
                    ]
                )
            )
        with hedge_chart_col:
            st.plotly_chart(plot_dv01_contributors(dv01_contributors_df), use_container_width=True)

        st.dataframe(
            style_dv01_contributors_table(dv01_contributors_df),
            use_container_width=True,
            hide_index=True,
        )

    with method_tab:
        st.subheader("Method")
        st.markdown("### iNAV")
        st.latex(r"\mathrm{iNAV} = \sum_i w_i \cdot P_i^{\mathrm{chosen}}")
        st.latex(
            rf"P_i^{{\mathrm{{chosen}}}} = \begin{{cases}} P_i^{{\mathrm{{last}}}}, & \text{{if staleness}} < {EVALUATED_MARK_SWITCH_SECONDS}\text{{s}} \\ P_i^{{\mathrm{{eval}}}}, & \text{{otherwise}} \end{{cases}}"
        )
        st.caption("The headline basket mark uses last-trade bond prices until the basket is treated as stale, then flips to evaluated marks.")

        st.markdown("### Cashflow pricing")
        st.latex(r"P(y) = \sum_{t=1}^{T} \frac{CF_t}{\left(1 + \frac{y}{m}\right)^{m \tau_t}}")
        st.latex(r"D_{\mathrm{mod}} \approx -\frac{P(y+\Delta y) - P(y-\Delta y)}{2 P(y)\Delta y}")
        st.latex(r"C \approx \frac{P(y-\Delta y) + P(y+\Delta y) - 2P(y)}{P(y)(\Delta y)^2}")
        st.caption("For Treasury holdings, duration and convexity can be recomputed from coupon cashflows using a numerical ±1 bp reprice.")

        st.markdown("### Duration-Convexity Reprice")
        st.latex(r"\frac{\Delta P}{P} \approx -D \cdot \Delta y + \frac{1}{2} C \cdot (\Delta y)^2")
        st.caption("Scenario NAV applies the duration-convexity approximation bond by bond, then aggregates back to the ETF level.")

        st.markdown("### AP Economics")
        st.latex(r"\mathrm{create\_cost}_{bp} = \left(\frac{\mathrm{NAV}_{offer}}{\mathrm{iNAV}} - 1\right)\times 10{,}000 + \mathrm{financing}_{bp} + \mathrm{cross}_{bp}")
        st.latex(r"\mathrm{redeem\_cost}_{bp} = \left(1 - \frac{\mathrm{NAV}_{bid}}{\mathrm{iNAV}}\right)\times 10{,}000 + \mathrm{financing}_{bp} + \mathrm{cross}_{bp}")
        st.latex(r"\mathrm{create\_arb}_{bp} = \mathrm{P/D}_{bp} - \mathrm{create\_cost}_{bp}")
        st.latex(r"\mathrm{redeem\_arb}_{bp} = -\mathrm{P/D}_{bp} - \mathrm{redeem\_cost}_{bp}")
        st.caption("Positive create arb means the ETF is rich enough to create and sell; positive redeem arb means it is cheap enough to buy and redeem.")

        st.markdown("### Hedging")
        st.latex(r"N_{\mathrm{TY}} = \mathrm{round}\left(\frac{\mathrm{DV01}^{rates}_{portfolio}}{\mathrm{DV01}_{TY}}\right)")
        st.latex(r"D_{spread} = 0.95 \times D_{rates}")
        st.latex(r"\mathrm{DV01}^{credit}_{portfolio} = \mathrm{iNAV} \cdot D_{spread} \cdot 10^{-4} \cdot \frac{10{,}000{,}000}{100}")
        st.latex(r"\mathrm{CDX\ overlay\ notional} = \frac{\mathrm{DV01}^{credit}_{portfolio}}{\mathrm{DV01}_{CDX\ IG}} \times 10{,}000{,}000")
        st.caption("The TY leg neutralises parallel rates DV01, while the CDX IG overlay is a separate credit-risk anchor for LQD-style baskets.")

        st.markdown("### References")
        st.markdown(
            "\n".join(
                [
                    "1. Kevin Pan and Yao Zeng, *ETF Arbitrage under Liquidity Mismatch* (working paper widely cited in 2022 bond ETF/AP discussions).",
                    "2. Ananth Madhavan and Aleksander Sobczyk, *Price Dynamics and Liquidity of Exchange-Traded Funds*.",
                    "3. Vladyslav Sushko and Grant Turner, *The Implications of Passive Investing for Securities Markets*, BIS Quarterly Review, March 2018.",
                ]
            )
        )
        st.markdown(
            "This is not a production ETF pricing engine. It uses illustrative holdings, simplified AP economics and duration-convexity pricing rather than full cashflow discounting against a fitted curve. It is not intended to replace issuer iNAV, executable AP cost models, or production-grade ETF valuations."
        )


if __name__ == "__main__":
    main()
