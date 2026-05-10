# Fixed Income ETF Fair Value & Basket Analytics Tool

## Overview

This project is a Streamlit dashboard for analysing the fair value, rate sensitivity, liquidity profile and basket composition of a fixed-income ETF.

The purpose of this project is not to build a production-grade ETF pricing engine. It is to demonstrate the core analytical workflow behind fixed-income ETF basket valuation: aggregating constituent-level bond data, estimating rate sensitivity, comparing estimated fair value to market price, and diagnosing liquidity/concentration risks.

The app includes two realistic illustrative baskets: an IEF-style intermediate Treasury basket and an LQD-style investment-grade credit basket. The holdings are manually curated rather than sourced live from issuer files, but the shapes, weights, maturities, spreads and risk measures are designed to look like the kind of basket inputs a trading analyst would inspect intraday.

## Why I built this

My previous experience is in algorithmic execution analytics, where I analysed order flow, benchmark performance, slippage, market-data quality and trading-system behaviour across futures markets.

This project extends that experience upstream into fixed-income ETF pricing. Instead of only analysing how orders execute, the dashboard looks at how a bond ETF’s underlying basket drives fair value, NAV sensitivity and potential rich/cheap signals versus the market price.

I built this to demonstrate three things:

1. The ability to translate a trading-desk problem into a working analytical tool.
2. Understanding of the basic mechanics behind fixed-income ETF basket valuation.
3. Practical Python/dashboarding skills for pricing, diagnostics and decision support.

## What the dashboard does

The dashboard estimates and visualises:

- Basket-level fair value / iNAV-style basket value
- Market price versus iNAV proxy
- Premium/discount to iNAV proxy
- Weighted duration and convexity
- DV01 in trader units
- TY hedge sizing and CDX IG hedge notional
- NAV sensitivity to yield shocks
- Basket-mark staleness diagnostics and evaluated-price waterfall
- Maturity bucket exposure
- Top holding concentration
- Basic liquidity diagnostics using bid/ask spread and liquidity score
- AP create/redeem economics
- Holding-level shocked prices under rate scenarios

The tool is designed as a simplified prototype of the type of workflow a trading analyst might use to understand how ETF fair value changes as rates move.

## Methodology

### 1. Basket fair value / iNAV proxy

The ETF basket value is approximated as the weighted sum of constituent bond clean prices:

```text
iNAV Proxy = Σ(weight_i × price_i)
```

where each bond’s contribution is determined by its portfolio weight.

This gives a transparent approximation of an intraday basket mark. In a production setting, the estimate would also need to account for accrued interest, cash balances, issuer-published NAV, live dealer marks, creation/redemption costs, financing, transaction costs and market liquidity.

The dashboard also tracks basket-mark staleness and switches between last-trade marks and small deterministic evaluated-price adjustments when the basket is treated as stale. That is still a simplification, but it is closer to how an ETF desk thinks about intraday iNAV quality than a static NAV input.

### 2. Cashflow-based duration and convexity

For the Treasury basket, the app can recompute duration and convexity directly from coupon cashflows and yield-to-maturity.

Cashflows are built from the bond coupon schedule and repriced numerically at ±1bp around the input yield. Modified duration and convexity are then derived from the bumped prices rather than treated purely as static CSV inputs.

This keeps the risk measures inspectable and makes the Treasury workflow look more like a small pricing tool than a static dashboard.

### 3. Duration-convexity shock pricing

Each bond is repriced using a standard duration-convexity approximation:

```text
ΔP / P ≈ -Duration × Δy + 0.5 × Convexity × Δy²
```

where:

- ΔP / P is the approximate percentage price change
- Duration measures first-order sensitivity to yield changes
- Convexity captures second-order curvature
- Δy is the yield shock in decimal form

This allows the dashboard to estimate how the ETF basket value changes under parallel yield shocks.

For example, if yields rise by 10bp, longer-duration bonds should fall more than shorter-duration bonds, all else equal. The ETF-level shocked fair value is then calculated by aggregating the shocked prices across the basket.

### 4. Weighted duration and convexity

ETF-level duration and convexity are estimated as weighted averages of the constituent-level values:

```text
Weighted Duration = Σ(weight_i × duration_i)
Weighted Convexity = Σ(weight_i × convexity_i)
```

This gives a high-level view of the ETF’s sensitivity to rate moves.

### 5. DV01 and hedge construction

DV01 is approximated as:

```text
DV01 ≈ ETF Fair Value × Weighted Duration × 0.0001
```

This estimates the change in ETF value for a 1bp move in yields.

In the app, DV01 is displayed both per $100 face and per $10mm portfolio risk unit so that the output maps to trading-desk language rather than only academic notation.

For the Treasury basket, that DV01 is translated into an indicative TY futures hedge ratio. For the credit basket, the dashboard also shows the equivalent CDX IG notional needed to neutralise credit risk in broad trader units.

This is still a simplified portfolio-level DV01 approximation, but it is much closer to how a trader would frame the hedge question.

### 6. Premium / discount versus iNAV

The ETF last trade is compared against the basket iNAV proxy:

```text
Premium / Discount = (Last Trade - iNAV Proxy) / iNAV Proxy
```

Interpretation:

- Positive value: ETF appears rich versus basket value
- Negative value: ETF appears cheap versus basket value
- Near zero: ETF market price is close to the basket proxy

This is not a trading signal by itself. In real markets, the premium/discount would need to be interpreted alongside bid/ask spreads, liquidity, creation/redemption costs, stale bond marks, market volatility and inventory considerations.

### 7. AP economics

The dashboard includes a simplified Authorised Participant economics panel.

Basket bid and offer NAVs are estimated by applying half the bond bid/ask spread to each holding, then layering on financing and crossing assumptions. From there, the app calculates indicative create and redeem economics in basis points:

- Create arb: useful when the ETF trades rich enough to cover basket offer costs
- Redeem arb: useful when the ETF trades cheap enough to cover basket bid costs

This does not claim to be an executable AP model. It is a desk-style sanity check on whether the observed ETF basis clears plausible market frictions.

## Key assumptions

This project intentionally uses a simplified model. The main assumptions are:

- Holdings are realistic illustrative baskets rather than live issuer PCF files.
- Clean prices are treated as representative of bond fair value.
- Basket weights are fixed.
- Treasury duration and convexity can be recomputed from cashflows; otherwise they are treated as inputs.
- Yield shocks are applied directly to each bond.
- Parallel rate shocks are the main scenario.
- Evaluated marks are a small deterministic adjustment rather than a real vendor pricing feed.
- Liquidity is approximated using bid/ask spread and a simple liquidity score.
- No accrued interest is included.
- No dirty price calculation is included.
- No live Treasury curve bootstrapping is performed.
- No issuer NAV, official iNAV or official PCF data is used.
- AP economics are stylised and not based on executable dealer runs.
- No financing, tax, settlement or balance-sheet effects are modelled.

These assumptions make the model transparent and easy to inspect, but they also mean the output should be interpreted as an educational approximation rather than a tradable production price.

## Why this is relevant to fixed-income ETF trading

A fixed-income ETF trading analyst needs to understand how ETF fair value connects to the underlying bond basket.

This project demonstrates a simplified version of that workflow:

- Aggregating constituent-level bond data into an ETF-level iNAV proxy
- Estimating how rate moves affect basket value through duration and convexity
- Translating basket DV01 into hedge ratios that a trader can actually use
- Comparing ETF market price against the basket proxy and checking if the basis clears AP frictions
- Identifying concentration and liquidity risks inside the basket
- Building tools that help traders diagnose pricing, risk and relative-value questions quickly

The dashboard is deliberately practical: it focuses on transparent calculations, interpretable outputs and desk-relevant diagnostics rather than unnecessary model complexity.

## Example interpretation

The dashboard can be used to answer questions such as:

- Is the ETF trading rich or cheap versus the basket iNAV proxy?
- Does that basis actually clear create or redeem costs after estimated frictions?
- How sensitive is the ETF to a 10bp move in rates?
- How many TY contracts would neutralise the portfolio DV01?
- Which holdings contribute most to basket concentration?
- Are the basket marks fresh enough to trust the headline premium/discount?
- Is the ETF mostly exposed to 7-10 year maturities or does it have meaningful exposure elsewhere?
- How much could liquidity costs affect confidence in the iNAV estimate?
- How does the NAV change under different rate-shock scenarios?

## Limitations

This is not a production fixed-income ETF pricing system.

Important limitations include:

- Realistic illustrative holdings instead of live issuer PCF/holdings files
- Simplified duration-convexity shock pricing instead of full curve-based bond pricing
- iNAV proxy rather than official issuer iNAV
- No fitted Treasury curve
- No accrued interest or dirty price treatment
- No real-time dealer or evaluated marks feed
- No executable bid/offer data
- No true creation/redemption basket modelling
- No AP transaction-cost calibration from dealer runs
- Stylised stale-mark logic rather than real mark-aging controls
- No index rebalance or corporate action logic
- No historical backtesting of premium/discount signals

The value of the project is in demonstrating the analytical workflow, not in claiming production-level pricing accuracy.

## Future improvements

Possible extensions:

- Ingest live ETF holdings from issuer files
- Pull live ETF market prices
- Add Treasury curve bootstrapping
- Price bonds from cashflows instead of using clean price inputs
- Add accrued interest and dirty price support
- Model creation/redemption baskets
- Estimate AP transaction costs
- Add bid/offer-based fair value bands
- Include historical premium/discount analysis
- Add index methodology and rebalance logic
- Include scenario analysis for curve steepeners and flatteners
- Add database storage for daily basket snapshots

## How to run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

## Deployment

This app can be deployed on Streamlit Community Cloud:

1. Push the repository to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app from the GitHub repository.
4. Set the main file path to:

```text
app.py
```

5. Deploy the app and share the public URL.

## Disclaimer

This project is an educational approximation of fixed-income ETF basket analytics and iNAV monitoring. It uses realistic illustrative baskets, simplified AP economics and duration-convexity pricing. It is not intended to replace issuer iNAV, executable AP cost models, investment advice or production-grade ETF valuations.
