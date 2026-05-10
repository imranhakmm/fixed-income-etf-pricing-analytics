# Fixed Income ETF Fair Value & Basket Analytics

An interview-ready Streamlit dashboard for fixed-income ETF pricing analysis, built around an IEF-style Treasury basket.

The app demonstrates how a junior fixed-income trading analyst might:

- estimate fair value from a constituent bond basket,
- inspect duration, convexity, and DV01 exposure,
- monitor premium / discount versus market price,
- test NAV sensitivity under rate shocks,
- and flag liquidity or concentration risk in a desk-friendly format.

## Why this matters for a fixed-income ETF trading role

ETF pricing teams and trading desks care about the same questions this dashboard answers:

- Is the ETF rich or cheap to the underlying basket?
- How sensitive is NAV to a parallel move in yields?
- Which holdings dominate duration and price risk?
- Does liquidity justify a haircut or wider execution range?
- How much of the move is due to rates versus basket composition?

This project is intentionally concise and practical. It looks like the kind of prototype a trading analyst would build to support daily marks, monitoring, and discussion with traders.

## Methodology

The dashboard uses a simplified but transparent workflow:

1. Load a synthetic Treasury holdings basket for an IEF-style ETF.
2. Compute basket fair value as the weighted average of clean prices.
3. Estimate bond price changes using a duration-convexity approximation:
   `dP/P ≈ -duration * dy + 0.5 * convexity * dy^2`
4. Aggregate the shocked bond prices back into portfolio NAV.
5. Calculate weighted duration, convexity, DV01 proxy, bid/ask, and liquidity score.
6. Show maturity bucket exposure, top holdings, NAV sensitivity, and a duration-vs-yield scatter.

The steepener / flattener selector applies a simple maturity-based curve twist, while the bid/ask toggle applies a conservative liquidity haircut to the basket.

## Assumptions and limitations

This is a desk-style educational model, not a production pricer.

- Holdings are synthetic and manually created inside the repo.
- No live iShares data or external market API is used.
- Yield shocks use a simplified duration-convexity approximation.
- The curve twist is heuristic, not a full Treasury curve bootstrapping model.
- The app works with clean prices only and does not model carry, roll-down, dividends, or creation/redemption mechanics.

Those constraints are deliberate: the goal is to demonstrate judgment, clarity, and market intuition rather than over-engineering a toy dashboard.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository named `fixed-income-etf-pricing-analytics`.
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud) and sign in with GitHub.
3. Select **New app**.
4. Choose the repository, branch, and set the main file path to `app.py`.
5. Confirm that `requirements.txt` is in the repo root.
6. Deploy.

Because the app uses only local CSV data and standard Python packages, it is straightforward to deploy without secrets or API keys.

## Future improvements

If I extended this into a more production-like tool, the next steps would be:

- live holdings ingestion,
- real bond pricing curve,
- Treasury curve bootstrapping,
- AP creation / redemption workflow,
- index rebalance logic,
- richer liquidity model.

## Files

- `app.py` - Streamlit dashboard logic and analytics
- `data/sample_ief_holdings.csv` - synthetic Treasury basket
- `requirements.txt` - minimal dependencies for Streamlit Cloud

