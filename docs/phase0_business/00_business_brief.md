# Business Brief: Weekly Demand Forecasting

## 1. Problem
A brewer has to decide today how much beer to brew, package and ship for weeks
it has not seen yet. Ordering materials, brewing, fermenting, packaging and
transport take weeks, so production follows the forecast, not actual demand.

- Forecast too high: excess stock, storage cost, cash tied up, ageing beer written off.
- Forecast too low: empty shelves, lost sales, unhappy customers, expensive emergency production.

Today's forecasts come from the planning platform's built-in model library.
They are not systematically compared with alternatives or tuned to each demand pattern.

## 2. Goal
Build a forecasting system that beats the current statistical forecasts at the
moments decisions are made, and prove it with accuracy and bias measured on a
rolling backtest.

## 3. Users and decisions
| User | Decision | Forecast they use |
|---|---|---|
| Demand planners | Adjust the system forecast into the consensus forecast | Weekly (ST) |
| Supply / production planners | Production runs, packaging, warehouse allocation | ST, locks at lag 2 |
| Procurement / brewing | Cans, malt, brewing schedule | ST, locks at lag 4 |
| Finance and leadership | Budget, capacity, targets (monthly S&OP) | Monthly (LT) |

## 4. Scope
- **Target:** weekly sell-in (shipments to distributors and retailers), in hectolitres (HL).
  Sell-out may be used later as an input signal.
- **Grain:** province x SKU (about 250 series).
  Product hierarchy SKU -> pack -> brand -> beverage type; geography province -> region -> country.
- **Horizon:** ST = 12 weeks, weekly buckets starting Monday. LT (monthly, 12 months) is a later extension.
- **Cycle:** a new forecast every Monday, using sales up to the previous Sunday.
- **Lag convention:** lag = (target week - cycle date) in weeks; the cycle's own week is lag 0.
- **Data:** synthetic data in the planning platform's export format
  (8 provinces, 40 SKUs, Jan 2021 - Sep 2024) with real weather data;
  later a public retail dataset as a second market.

## 5. Demand drivers
- Seasonality: Brazilian summer peak (Dec-Feb), winter low (Jun-Aug), different by province.
- Holidays and events: Carnival (moving date), New Year, Christmas, regional holidays.
- Weather: hot weeks sell more. Only information available at forecast time is used.
- Promotions and price: spikes followed by dips; sell-in pre-loading before peaks.
- Trend, product launches and discontinuations, distribution changes.
- Demand patterns: smooth, erratic, intermittent or lumpy (ADI / CV2), evaluated per segment.

## 6. KPIs
- **Accuracy** = 1 - sum(|forecast - actual|) / sum(actual)  (1 - WMAPE)
- **Bias** = (sum(forecast) - sum(actual)) / sum(actual); positive = over-forecast
- Reported row-level at **lag 2 and lag 4**, plus the full lag 0-11 curve;
  by segment, brand, province and cycle.
- Always compared with a simple benchmark (seasonal naive) and the current forecasts.

## 7. Baseline
The incumbent is a library of statistical and ML models of the kind a planning
platform provides (moving average, Holt-Winters, Croston, tree models).
In this project, statistical benchmark models built locally play that role.
Their lag-2 and lag-4 accuracy and bias are the bar to beat.

## 8. Success criteria
A challenger replaces the current champion only if, on a rolling backtest of at
least 12 weekly cycles:
1. Lag-2 and lag-4 accuracy are higher than both the benchmark and the champion.
2. |Bias| at lag 2 and lag 4 stays below 5%.
3. No major demand segment gets worse by more than 2 accuracy points.

Then: shadow run alongside the current forecast before any switch.

## 9. Risks and constraints
- **Frozen window:** forecasts inside about 2 weeks cannot change production,
  so short-lag accuracy overstates value.
- **Promotions not in the data:** spikes the model cannot explain; handled by
  outlier capping until a promotion calendar is available.
- **New and discontinued SKUs:** little or no history; SKU codes may be replaced.
- **Sparse SKUs:** hard for every model; may need intermittent-demand methods or a coarser level.
- **Data quality:** upstream formats, units or codes can change; inputs are validated before training.
- **Information leakage:** each backtest cycle uses only data available at its cutoff.

## 10. Assumptions to confirm
- Production locks at lag 2, materials and brewing at lag 4.
- The real target ("Actual Base") is sell-in shipments; its unit is unconfirmed.
- What the incumbent "Hyb LPP" model is.
