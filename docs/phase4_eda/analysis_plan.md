# Phase 4: Data diagnostic, analysis plan

Data version: data-2025-03-23 (weeks 2021-01-04 → 2025-03-17, 231 series)

## Objective
Understand what drives weekly sell-in, assess whether the data is fit for forecasting,
and turn every finding into a modelling decision for Phases 5–8.

## Scope
- Data: data/processed (sales_weekly, sales_daily, weather_weekly, masters, holidays,
  restatements), at one tagged data version (data-YYYY-MM-DD).
- Grain: province x SKU x week (Monday–Sunday). 9 states, 3 regions, 40 SKUs, ~231 series.
- Out of scope: features, models, benchmarks (Phase 5 onwards).

## Workstreams and key questions
| # | Workstream | Key questions |
|---|---|---|
| 4.1 | Data audit & readiness | Is the data complete, valid, consistent and timely? Gaps, launches, corrections? |
| 4.2 | Portfolio structure | Where is the volume? How concentrated is it? ABC–XYZ classes? |
| 4.3 | Time-series anatomy | Trend, seasonality by region, stability across years, structural breaks |
| 4.4 | Calendar & events | Carnival, Christmas, São João: size, timing, region; moving holidays |
| 4.5 | External drivers | Weather effect beyond seasonality, per °C, by region |
| 4.6 | Promotions & anomalies | Frequency, lift, post-promotion dip; detectable without a calendar? |
| 4.7 | Lifecycle | Launch ramps, discontinuations, cannibalisation |
| 4.8 | Forecastability & hierarchy | Predictability per series; noise vs aggregation level |
| 4.9 | Source behaviour | How often and how deep the client restates history; trust in the latest weeks |

## Method principles
- Planned hypotheses are written before analysis (hypotheses.md) and their results recorded honestly.
- Emergent questions are welcome (question_log.md), but an emergent finding becomes a decision
  only after it holds on data it was not discovered on (another year, region, or the answer key).
- Effects are quantified with uncertainty (confidence intervals) and checked across years and regions.
- Methods are validated against the synthetic answer key before being trusted on real data.
- Every insight (I-xx) states its modelling implication; every decision (D-xx) cites its evidence.
- Analysis reads data/processed and never writes to data/.

## Deliverables
Data readiness scorecard · insight log · decision log · challenges & mitigations ·
executive summary (1 page) · dashboard · interview pack.

## Sign-off checklist (before Phase 5)
- [ ] Readiness scorecard has no red item without a mitigation
- [ ] Every planned hypothesis has a recorded result
- [ ] Every insight has a modelling implication
- [ ] Every emergent finding used in a decision has been confirmed on other data
- [ ] Decision log covers: segmentation, outlier policy, feature list, forecast level,
      evaluation rules, as-of rule
- [ ] Executive summary reviewed
