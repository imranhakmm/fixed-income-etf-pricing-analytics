from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
ETF_FILE_MAP = {
    "IEF": APP_DIR / "data" / "ief_holdings_realistic.csv",
    "LQD": APP_DIR / "data" / "lqd_holdings_realistic.csv",
}
ETF_LABEL_MAP = {
    "IEF (Treasury)": "IEF",
    "LQD (IG Credit)": "LQD",
}
ETF_DEFAULT_PD_BP = {
    "IEF": 4.0,
    "LQD": 18.0,
}
DEFAULT_STALENESS_SECONDS = 15
STALE_MARK_WARNING_SECONDS = 60
DEFAULT_PORTFOLIO_NOTIONAL_USD = 10_000_000
TY_DV01_PER_BP_USD = 76.0  # Approximate TY futures DV01 per 1 bp using a CTD-style desk assumption.
CDX_IG_DV01_PER_BP_USD = 4500.0  # Approximate CDX IG DV01 per 1 bp for $10mm index notional.
PD_DISPLAY_OPTIONS = ["bp", "%"]

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
    "This is an educational approximation of fixed-income ETF basket analytics and iNAV monitoring. "
    "It uses realistic illustrative baskets, simplified AP economics, and duration-convexity pricing. "
    "It is not intended to replace issuer iNAV, executable AP cost models, or production-grade ETF valuations."
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        :root {
            --app-font-sans: 'Inter', sans-serif;
            --app-font-mono: 'JetBrains Mono', monospace;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
            font-family: var(--app-font-sans);
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }
        [data-testid="stSidebar"] {
            background: #F6F8FB;
            color: #102A43;
            border-right: 1px solid #D8E0E8;
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
            color: #102A43 !important;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"],
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *,
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background-color: #FFFFFF !important;
            color: #102A43 !important;
            border-color: #D8E0E8 !important;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
            opacity: 1 !important;
        }
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #D8E0E8;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        [data-testid="stMetricValue"] {
            color: #102A43;
            font-family: var(--app-font-mono);
            font-weight: 600;
            letter-spacing: -0.03em;
        }
        [data-testid="stMetricLabel"] {
            color: #52606D;
            font-size: 0.88rem;
            font-family: var(--app-font-sans);
        }
        [data-testid="stMetricDelta"] {
            font-family: var(--app-font-mono);
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
            background: rgba(15, 23, 42, 0.06);
            color: #0F172A;
            border-radius: 6px;
            padding: 0.08rem 0.34rem;
        }
        .stMarkdown pre code {
            background: transparent;
            padding: 0;
        }
        .subtle-note {
            color: #52606D;
            font-size: 0.95rem;
            line-height: 1.4;
        }
        .stale-caption {
            margin-top: 0.15rem;
            color: #9B2C2C;
            font-size: 0.8rem;
            line-height: 1.2;
        }
        .signal-card {
            border-radius: 14px;
            border: 1px solid #D8E0E8;
            padding: 0.9rem 1rem;
            background: #FFFFFF;
        }
        .signal-card__label {
            color: #52606D;
            font-size: 0.88rem;
            margin-bottom: 0.35rem;
        }
        .signal-card__value {
            font-family: var(--app-font-mono);
            font-size: 1.75rem;
            font-weight: 600;
            color: #102A43;
        }
        .signal-positive .signal-card__value {
            color: #1D6F42;
        }
        .signal-negative .signal-card__value {
            color: #9B2C2C;
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

    df = df[REQUIRED_COLUMNS].copy()
    for column in NUMERIC_COLUMNS:
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

    today = pd.Timestamp.today().normalize()
    df["weight_share"] = df["weight_pct"] / weight_sum
    df["years_to_maturity"] = ((df["maturity"] - today).dt.days / 365.25).clip(lower=0)
    df["bucket"] = df["years_to_maturity"].apply(assign_bucket)
    df["maturity_label"] = df["maturity"].dt.strftime("%Y-%m-%d")
    df = df.sort_values("weight_pct", ascending=False).reset_index(drop=True)

    return df, messages


@st.cache_data(show_spinner=False)
def load_sample_holdings(etf_code: str) -> pd.DataFrame:
    return pd.read_csv(ETF_FILE_MAP[etf_code])


def load_holdings(uploaded_file, etf_code: str) -> tuple[pd.DataFrame, str, list[str]]:
    if uploaded_file is None:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        return prepared, f"Illustrative {etf_code} basket", messages

    try:
        raw_df = pd.read_csv(uploaded_file)
        prepared, messages = prepare_holdings(raw_df)
        return prepared, "Uploaded holdings", messages
    except ValueError as exc:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        messages = [f"{exc} Falling back to the bundled {etf_code} basket."] + messages
        return prepared, f"Illustrative {etf_code} basket", messages
    except Exception as exc:
        sample_df = load_sample_holdings(etf_code)
        prepared, messages = prepare_holdings(sample_df)
        messages = [f"Could not read the uploaded CSV ({exc}). Falling back to the bundled {etf_code} basket."] + messages
        return prepared, f"Illustrative {etf_code} basket", messages


def weighted_average(df: pd.DataFrame, column: str) -> float:
    return float((df["weight_share"] * df[column]).sum())


def get_default_last_trade(etf_code: str, inav_proxy: float) -> float:
    return round(inav_proxy * (1.0 + ETF_DEFAULT_PD_BP[etf_code] / 10000.0), 2)


def dv01_per_10mm_from_per_100(dv01_per_100: float) -> float:
    return dv01_per_100 * (DEFAULT_PORTFOLIO_NOTIONAL_USD / 100.0)


def compute_cdx_ig_hedge_notional(dv01_per_10mm: float) -> float:
    return round((dv01_per_10mm / CDX_IG_DV01_PER_BP_USD) * DEFAULT_PORTFOLIO_NOTIONAL_USD)


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
    shock_grid = np.arange(-100, 101, 1)
    values = []
    for shock_bp in shock_grid:
        shocked_value, _ = compute_portfolio_value(df, float(shock_bp), scenario, liquidity_penalty_pct)
        shock_factor = shocked_value / gross_base_value if gross_base_value else 1.0
        values.append(base_nav * shock_factor)
    return pd.DataFrame({"shock_bp": shock_grid, "implied_nav": values})


def build_bucket_chart_data(df: pd.DataFrame) -> pd.DataFrame:
    bucket_df = df.groupby("bucket", as_index=False)["weight_pct"].sum()
    bucket_df["bucket"] = pd.Categorical(bucket_df["bucket"], categories=BUCKET_ORDER, ordered=True)
    bucket_df = bucket_df.sort_values("bucket")
    full = pd.DataFrame({"bucket": BUCKET_ORDER}).merge(bucket_df, on="bucket", how="left")
    full["weight_pct"] = full["weight_pct"].fillna(0.0)
    return full


def build_top_holdings(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return df.nlargest(n, "weight_pct").sort_values("weight_pct", ascending=True).copy()


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
            ("CDX IG hedge", f"${metrics['cdx_ig_hedge_notional']:,.0f} CDX IG notional / $10mm", None)
        )
    hedge_cols = st.columns(len(hedge_specs))
    for col, (label, value, delta) in zip(hedge_cols, hedge_specs):
        with col:
            st.metric(label, value, delta=delta)

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
    direction = "rich" if metrics["premium_discount_bp"] > 0 else "cheap"
    dominant_bucket = bucket_df.sort_values("weight_pct", ascending=False).iloc[0]
    return [
        f"Last trade is {abs(metrics['premium_discount_bp']):.1f} bp {direction} to the basket iNAV proxy at {metrics['inav_proxy']:.2f}.",
        f"Portfolio DV01 is ${metrics['dv01_per_100']:.3f} per $100, which scales to roughly ${metrics['dv01_per_10mm']:,.0f} per bp on a $10mm line item.",
        f"The basket is concentrated in the {dominant_bucket['bucket']} bucket ({dominant_bucket['weight_pct']:.1f}%) with top-5 weight at {metrics['top_5_concentration']:.1f}%.",
        f"Current marks are {int(metrics['staleness_seconds'])} seconds old and the weighted bond bid/ask is {metrics['weighted_bid_ask_bps']:.2f} bp.",
    ]


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
        template="plotly_white",
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
        template="plotly_white",
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
    selected_nav = float(curve_df.loc[curve_df["shock_bp"] == current_shock_bp, "implied_nav"].iloc[0])
    fig.add_trace(
        go.Scatter(
            x=[current_shock_bp],
            y=[selected_nav],
            mode="markers",
            marker=dict(size=11, color=PALETTE[1], line=dict(color="white", width=1.5)),
            name="Selected shock",
        )
    )
    fig.add_vline(x=current_shock_bp, line_width=1, line_dash="dash", line_color="#708090")
    fig.add_hline(y=current_nav, line_width=1, line_dash="dot", line_color="#A0AEC0")
    fig.update_layout(
        template="plotly_white",
        title="NAV Sensitivity Under Parallel Shocks",
        xaxis_title="Parallel shock (bp)",
        yaxis_title="Implied NAV",
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
        legend_title_text="",
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
        template="plotly_white",
        title="Duration vs. Yield",
        xaxis_title="Yield (%)",
        yaxis_title="Duration (yrs)",
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
        legend_title_text="Maturity bucket",
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


def main() -> None:
    st.set_page_config(
        page_title="Fixed Income ETF Fair Value & Basket Analytics",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    st.title("Fixed Income ETF Fair Value & Basket Analytics")
    st.caption("Basket-level pricing, iNAV proxy monitoring, DV01, curve shock sensitivity and basket diagnostics for Treasury and IG credit ETFs.")
    st.info(DISCLAIMER)

    selected_etf_label = st.sidebar.radio("ETF", options=list(ETF_LABEL_MAP.keys()), index=0)
    selected_etf_code = ETF_LABEL_MAP[selected_etf_label]
    st.sidebar.markdown("### Controls")
    st.sidebar.caption(
        "Upload a custom CSV or use the bundled realistic illustrative basket. Required columns: "
        + ", ".join(REQUIRED_COLUMNS)
        + "."
    )
    uploaded_file = st.sidebar.file_uploader("Upload custom holdings CSV", type=["csv"])

    holdings_df, data_source_label, load_messages = load_holdings(uploaded_file, selected_etf_code)
    inav_proxy = weighted_average(holdings_df, "clean_price")

    data_seed = f"{selected_etf_code}:{data_source_label}:{len(holdings_df)}:{round(inav_proxy, 4)}"
    if st.session_state.get("_snapshot_seed") != data_seed:
        st.session_state.last_trade_input = get_default_last_trade(selected_etf_code, inav_proxy)
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
        index=0,
    )

    weighted_duration = weighted_average(holdings_df, "duration")
    weighted_convexity = weighted_average(holdings_df, "convexity")
    weighted_bid_ask_bps = weighted_average(holdings_df, "bid_ask_bps")
    weighted_liquidity_score = weighted_average(holdings_df, "liquidity_score")
    top_5_concentration = float(holdings_df.nlargest(5, "weight_pct")["weight_pct"].sum())
    dv01_per_100 = inav_proxy * weighted_duration * 0.0001
    dv01_per_10mm = dv01_per_10mm_from_per_100(dv01_per_100)
    ty_hedge_contracts = round(dv01_per_10mm / TY_DV01_PER_BP_USD)
    cdx_ig_hedge_notional = compute_cdx_ig_hedge_notional(dv01_per_10mm) if selected_etf_code == "LQD" else None
    premium_discount_pct = (market_price - inav_proxy) / inav_proxy * 100.0
    premium_discount_bp = premium_discount_pct * 100.0

    current_shocked_gross_value, shocked_prices = compute_portfolio_value(
        holdings_df,
        float(parallel_shock_bp),
        curve_scenario,
        liquidity_penalty_pct=0.0,
    )
    current_shocked_nav = inav_proxy * (current_shocked_gross_value / inav_proxy)
    nav_move_pct = ((current_shocked_nav - inav_proxy) / inav_proxy * 100.0) if inav_proxy else 0.0

    metrics = {
        "inav_proxy": inav_proxy,
        "last_trade": market_price,
        "staleness_seconds": staleness_seconds,
        "weighted_duration": weighted_duration,
        "weighted_convexity": weighted_convexity,
        "dv01_per_100": dv01_per_100,
        "dv01_per_10mm": dv01_per_10mm,
        "ty_hedge_contracts": ty_hedge_contracts,
        "cdx_ig_hedge_notional": cdx_ig_hedge_notional,
        "premium_discount_pct": premium_discount_pct,
        "premium_discount_bp": premium_discount_bp,
        "top_5_concentration": top_5_concentration,
        "weighted_bid_ask_bps": weighted_bid_ask_bps,
        "weighted_liquidity_score": weighted_liquidity_score,
        "current_shocked_nav": current_shocked_nav,
    }

    make_metric_cards(metrics=metrics, etf_code=selected_etf_code)

    st.markdown("---")
    st.subheader("Basket diagnostics")

    bucket_df = build_bucket_chart_data(holdings_df)
    top_holdings_df = build_top_holdings(holdings_df, n=10)
    sensitivity_df = compute_sensitivity_curve(
        holdings_df,
        base_nav=inav_proxy,
        scenario=curve_scenario,
        liquidity_penalty_pct=0.0,
    )

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
    interp_col, desk_col = st.columns(2)
    with interp_col:
        st.subheader("Interpretation")
        interpretation_bullets = format_interpretation(metrics, bucket_df)
        st.markdown("\n".join(f"- {bullet}" for bullet in interpretation_bullets))
    with desk_col:
        st.subheader("Desk relevance")
        st.markdown(
            "\n".join(
                [
                    "- Basket valuation to approximate iNAV from constituent bond marks.",
                    "- DV01 and hedge sizing to map ETF risk into TY futures or CDX IG trader units.",
                    "- Premium/discount monitoring to compare last trade against a live basket proxy rather than a static NAV input.",
                    "- Liquidity and concentration diagnostics to support AP-style execution, hedging and basis discussions.",
                    "- A compact prototype that mirrors how a fixed-income ETF desk frames iNAV, basis and hedge questions intraday.",
                ]
            )
        )

    st.caption(
        f"Model summary: iNAV ${inav_proxy:,.2f} | last trade ${market_price:,.2f} | duration {weighted_duration:.2f} yrs | "
        f"convexity {weighted_convexity:.1f} | weighted liquidity score {weighted_liquidity_score:.2f}/5."
    )


if __name__ == "__main__":
    main()
