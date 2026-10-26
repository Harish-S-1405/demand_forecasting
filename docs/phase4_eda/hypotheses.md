# Hypothesis register

Written BEFORE analysis, from business knowledge (Phase 0).
Results and decisions are filled in as each workstream completes.
A rejected hypothesis is a finding, not a failure.

| ID | Hypothesis (business expectation) | Test | Decision rule (if true) | Result |
|---|---|---|---|---|
| H1 | Volume is concentrated: the top 20% of series carry at least 70% of HL | Pareto curve | Report accuracy per segment, not only in total | |
| H2 | Summer (Dec–Feb) is the peak in every region | STL seasonal component by region | One seasonal feature set for all regions; otherwise region-specific | |
| H3 | The seasonal swing is largest in the South, smallest in the North-East | STL seasonal amplitude by region | Interact season with region | |
| H4 | Seasonality is stable across years | Seasonal index per year | Lag-52 and seasonal naive will be strong baselines | |
| H5 | Premium brands grow faster than mainstream brands | Trend by brand group | Add a brand-group trend feature | |
| H6 | Sell-in rises BEFORE Carnival (pre-load) and dips after it | Event study, weeks −3 to +2 | Holiday windows −2..+1 from the real calendar | |
| H7 | The Carnival effect is strongest in the North-East | Event study by region | Holiday x region interaction | |
| H8 | São João matters only in the North-East | Event study by region | Region-specific holiday feature | |
| H9 | Hotter-than-normal weeks sell more, beyond seasonality | Regression of deseasonalised volume on temperature anomaly | Temperature-anomaly feature, short lags only | |
| H10 | Promotion spikes are followed by a sell-in dip | Event study around detected spikes | Post-spike features; cap spikes in training | |
| H11 | Spikes can be detected without a promotion calendar | Precision / recall against the answer key | Use the detector in the outlier step if recall is at least 70% | |
| H12 | Launches ramp up over several weeks | Launch curves | "Weeks since launch" feature; minimum-history rule | |
| H13 | A minority of series are intermittent or lumpy, with a small volume share | ADI / CV² and volume share | Separate models and evaluation for sparse series | |
| H14 | Restatements touch only recent weeks | Revision depth from restatements | As-of training; the latest week treated as provisional | |
