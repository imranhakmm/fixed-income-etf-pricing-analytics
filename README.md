# Fixed Income ETF Fair Value & Basket Analytics Tool

## Overview

This project is a Streamlit dashboard for analysing the fair value, rate sensitivity, liquidity profile and basket composition of a fixed-income ETF.

The purpose of this project is not to build a production-grade ETF pricing engine. It is to demonstrate the core analytical workflow behind fixed-income ETF basket valuation: aggregating constituent-level bond data, estimating rate sensitivity, comparing estimated fair value to market price, and diagnosing liquidity/concentration risks.

The example uses a simplified Treasury ETF-style basket inspired by intermediate-maturity U.S. Treasury ETFs. The holdings data is synthetic but structured to resemble the type of bond-level data a trading analyst might use when analysing ETF fair value.

## Why I built this

My previous experience is in algorithmic execution analytics, where I analysed order flow, benchmark performance, slippage, market-data quality and trading-system behaviour across futures markets.

This project extends that experience upstream into fixed-income ETF pricing. Instead of only analysing how orders execute, the dashboard looks at how a bond ETF’s underlying basket drives fair value, NAV sensitivity and potential rich/cheap signals versus the market price.

I built this to demonstrate three things:

1. The ability to translate a trading-desk problem into a working analytical tool.
2. Understanding of the basic mechanics behind fixed-income ETF basket valuation.
3. Practical Python/dashboarding skills for pricing, diagnostics and decision support.

## What the dashboard does

The dashboard estimates and visualises:

- Basket-level fair value
- Market price versus estimated fair value
- Premium/discount to estimated fair value
- Weighted duration and convexity
- DV01 proxy
- NAV sensitivity to yield shocks
- Maturity bucket exposure
- Top holding concentration
- Basic liquidity diagnostics using bid/ask spread and liquidity score
- Holding-level shocked prices under rate scenarios

The tool is designed as a simplified prototype of the type of workflow a trading analyst might use to understand how ETF fair value changes as rates move.

## Methodology

### 1. Basket fair value

The ETF fair value is approximated as the weighted sum of constituent bond clean prices:

```text
ETF Fair Value = Σ(weight_i × price_i)
```

where each bond’s contribution is determined by its portfolio weight.

This gives a transparent approximation of basket value. In a production setting, the estimate would also need to account for accrued interest, cash balances, issuer-published NAV, real-time bond marks, creation/redemption costs, financing, transaction costs and market liquidity.

### 2. Duration-convexity shock pricing

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

### 3. Weighted duration and convexity

ETF-level duration and convexity are estimated as weighted averages of the constituent-level values:

```text
Weighted Duration = Σ(weight_i × duration_i)
Weighted Convexity = Σ(weight_i × convexity_i)
```

This gives a high-level view of the ETF’s sensitivity to rate moves.

### 4. DV01 proxy

DV01 is approximated as:

```text
DV01 ≈ ETF Fair Value × Weighted Duration × 0.0001
```

This estimates the change in ETF value for a 1bp move in yields.

This is a simplified portfolio-level DV01 approximation, useful for understanding rate exposure directionally.

### 5. Premium / discount

The ETF market price is compared against the estimated basket fair value:

```text
Premium / Discount = (Market Price - Estimated Fair Value) / Estimated Fair Value
```

Interpretation:

- Positive value: ETF appears rich versus estimated basket fair value
- Negative value: ETF appears cheap versus estimated basket fair value
- Near zero: ETF market price is close to estimated fair value

This is not a trading signal by itself. In real markets, the premium/discount would need to be interpreted alongside bid/ask spreads, liquidity, creation/redemption costs, stale bond marks, market volatility and inventory considerations.

## Key assumptions

This project intentionally uses a simplified model. The main assumptions are:

- Holdings are synthetic and manually created.
- Clean prices are treated as representative of bond fair value.
- Basket weights are fixed.
- Duration and convexity are provided as inputs.
- Yield shocks are applied directly to each bond.
- Parallel rate shocks are the main scenario.
- Liquidity is approximated using bid/ask spread and a simple liquidity score.
- No accrued interest is included.
- No dirty price calculation is included.
- No live Treasury curve bootstrapping is performed.
- No issuer NAV, iNAV or official PCF data is used.
- No creation/redemption transaction cost model is included.
- No financing, tax, settlement or balance-sheet effects are modelled.

These assumptions make the model transparent and easy to inspect, but they also mean the output should be interpreted as an educational approximation rather than a tradable production price.

## Why this is relevant to fixed-income ETF trading

A fixed-income ETF trading analyst needs to understand how ETF fair value connects to the underlying bond basket.

This project demonstrates a simplified version of that workflow:

- Aggregating constituent-level bond data into ETF-level fair value
- Estimating how rate moves affect NAV through duration and convexity
- Comparing ETF market price against estimated basket value
- Identifying concentration and liquidity risks inside the basket
- Building tools that help traders diagnose pricing, risk and relative-value questions quickly

The dashboard is deliberately practical: it focuses on transparent calculations, interpretable outputs and desk-relevant diagnostics rather than unnecessary model complexity.

## Example interpretation

The dashboard can be used to answer questions such as:

- Is the ETF trading rich or cheap versus the estimated basket value?
- How sensitive is the ETF to a 10bp move in rates?
- Which holdings contribute most to basket concentration?
- Is the ETF mostly exposed to 7-10 year maturities or does it have meaningful exposure elsewhere?
- How much could liquidity costs affect confidence in the fair-value estimate?
- How does the NAV change under different rate-shock scenarios?

## Limitations

This is not a production fixed-income ETF pricing system.

Important limitations include:

- Synthetic holdings instead of live issuer PCF/holdings files
- Simplified duration-convexity pricing rather than full cashflow discounting
- No fitted Treasury curve
- No accrued interest or dirty price treatment
- No real-time dealer marks
- No executable bid/offer data
- No creation/redemption basket modelling
- No AP transaction cost estimate
- No treatment of stale bond pricing
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

This project is an educational approximation of fixed-income ETF basket analytics. It uses synthetic holdings and simplified duration-convexity pricing. It is not intended to produce tradable prices, investment advice or production-grade ETF valuations.
