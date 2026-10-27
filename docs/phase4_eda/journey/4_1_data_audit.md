# 4.1 Data audit and readiness

Notebook: notebooks/phase4_eda/04_01_data_audit.ipynb
Data version: data-2025-03-23 (weeks 2021-01-04 → 2025-03-17, 231 series, 47,236 weekly rows)

## Purpose
Before believing any pattern, check that the data is fit for purpose, along the four
standard data-quality dimensions:

| Dimension | Question |
|---|---|
| Completeness | Is everything there? Does every series have the history it should? |
| Validity | Are the values sensible? |
| Consistency | Do the tables agree with each other? |
| Timeliness | Is the data current, and how stable are the latest weeks? |

The audit has no business hypotheses of its own: it decides whether the data can be analysed at all.

Setup used by every step:
```python
wk = L.weekly_enriched()                       # sales_weekly + geography + product + calendar
FIRST_WEEK, LAST_WEEK = wk["week_start"].min(), wk["week_start"].max()

prof = (wk.groupby(["series", "province", "region", "sku_id", "sku_name", "container"], as_index=False)
          .agg(first=("week_start", "min"), last=("week_start", "max"),
               weeks=("week_start", "size"),
               zero_weeks=("volume_hl", lambda s: int((s == 0).sum())),
               total_hl=("volume_hl", "sum")))
prof["zero_share"] = (prof["zero_weeks"] / prof["weeks"]).round(3)
prof["starts_late"] = prof["first"] > FIRST_WEEK
prof["ends_early"] = prof["last"] < LAST_WEEK
```
`prof` has one row per series describing its history: first and last week, number of weeks,
zero weeks (active but no sales) and total volume.

---

## 4.1.1 Completeness: does every series have the history it should?

### Main question
Does every series cover the whole period? Which series start late or end early, and why?

### Why it matters
A model learns seasonality from history: it needs at least one full year, ideally two.
A series that starts in 2024 cannot teach the model about 2023's summer; a series that
ends early must not be forecast at all.

### Example
A product launched in April 2024 has 51 weeks of history: less than one summer. A model
trained only on its own history cannot know what its next summer looks like.

### The journey

**1. How many series have full history?**
```python
print(f"{len(prof)} series | full history: {(~prof.starts_late & ~prof.ends_early).sum()} "
      f"| start late: {prof.starts_late.sum()} | end early: {prof.ends_early.sum()}")
prof["weeks"].describe()
```
```
231 series | full history: 190 | start late: 30 | end early: 11
weeks: min 51 · 25% 220 · median 220 · 75% 220 · max 220 · mean 204.5
```
**Reading:** at least three quarters of the series have all 220 weeks. The minimum of 51
weeks is BUDWEISER LATA 350ML, launched 1 April 2024.

**2. Do the late starters and early enders match launches and discontinuations?**
```python
prof[prof["starts_late"]].groupby("first").agg(series=("series", "size"), skus=("sku_name", ...))
prof[prof["ends_early"]].groupby("last").agg(series=("series", "size"), skus=("sku_name", ...))
```
| First week | Series | Product | Explanation |
|---|---|---|---|
| 2021-01-11 … 2021-02-01 | 9 | Corona, Spaten, Original, Antarctica, Stella (existing products) | ? (see step 3) |
| 2022-03-07 / 03-21 | 2 / 1 | ORIGINAL LONG NECK 330ML | launched 7 Mar 2022 |
| 2022-10-03 / 10-17 | 3 / 1 | SPATEN LATA 269ML | launched 3 Oct 2022 |
| 2023-06-05 / 06-12 | 4 / 1 | BUDWEISER LATA 269ML | launched 5 Jun 2023 |
| 2024-04-01 | 9 | BUDWEISER LATA 350ML | launched 1 Apr 2024 (all states) |

| Last week | Series | Product | Explanation |
|---|---|---|---|
| 2022-12-19 | 4 | BUDWEISER LATA 473ML | discontinued 25 Dec 2022 |
| 2023-08-21 | 3 | STELLA ARTOIS LATA 350ML | discontinued 27 Aug 2023 |
| 2024-06-24 | 4 | SPATEN GARRAFA 600ML | discontinued 30 Jun 2024 |

**Reading:** all 11 early enders stop exactly in their discontinuation week; 21 late
starters are launches. But 9 late starters are products that existed all along.

**3. Why do 9 existing products start late? (emergent question Q-10)**
Their zero_share is high (27–67%): they are sparse. Their first order simply came 1–4
weeks after the data starts. The weekly table starts each series at its first sale, so the
zero weeks before that first order are missing. The same happens in 3 launched series whose
first order came 1–2 weeks after launch.

| Week | What really happened | What the weekly table shows |
|---|---|---|
| 4 Jan 2021 | product available, no order | no row: the series "does not exist yet" |
| 11 Jan 2021 | first order | first row |

### Where our thinking changed
| We assumed | The data showed |
|---|---|
| Late starters are launches | 21 are; 9 are existing sparse products cut short by our own "start at first sale" rule |

### Final insights
- **I-01:** history is complete for 190 of 231 series; all early enders and launch starters
  match the product lifecycle; 12 sparse series lose 1–4 real zero weeks at their start.
- **I-02:** history ranges from 51 to 220 weeks; BUDWEISER LATA 350ML has less than a year.

### What it means for modelling
- Pipeline fix **PF-01**: start each series at the data start (existing products) or at its
  launch week (launched products), not at its first sale.
- Series with less than 52 weeks need a cold-start approach (a global model using product
  attributes, or similar-product history).

---

## 4.1.2 Coverage and sparsity: where are the gaps, and what drives them?

### Main question
Across all series and weeks, where does the data have sales, zero weeks, or no series at all,
and what explains the pattern?

### Why it matters
Series with many zero weeks are hard to forecast. Knowing where they sit tells us where
accuracy will be lower, and why, before any model is built.

### Example
| Week | SP · Brahma can | RS · keg |
|---|---|---|
| 1–8 | 1,050 · 1,120 · 980 · 1,010 · 1,090 · 1,060 · 990 · 1,040 | 0 · 30 · 0 · 0 · 45 · 0 · 28 · 0 |
| Zero weeks | 0 of 8 | 5 of 8 |

The SP can sells every week (easy to forecast); the keg only when someone places an order.

### Method box: zero_share and the "sparse" working definition
- zero_share = zero weeks ÷ weeks in the series' active life (e.g. 5 ÷ 8 = 62%).
- **Sparse (working definition for this audit):** zero_share above 20%, i.e. more than
  about 1 week in 5 without sales. The formal segments (ADI/CV²) come in 4.8.
- **Coverage heatmap:** one row per series, one column per week; blue = sales,
  orange = zero week, white = not active.

### The journey

**1. What does the whole dataset look like?** (fig_4_1_coverage_heatmap.png)
```python
grid = state.pivot_table(index="series", columns="week_start", values="state", aggfunc="max", fill_value=0)
ax.imshow(grid.values, ...)
```
**Reading:** no white columns (no missing weeks) and no white holes inside rows (no series
disappears and returns). White staircases on the left are launches; white blocks on the right
are discontinuations. Orange speckles are concentrated in the Nordeste and Sul blocks; Sudeste
is almost solid blue. To be quantified.

**2. By region**
```python
by_region = (prof.assign(sparse=prof["zero_share"] > 0.2).groupby("region").agg(...))
```
| Region | Series | Sparse | Zero weeks | Volume share |
|---|---|---|---|---|
| Sudeste | 95 | 5 (5%) | 2.9% | 60.7% |
| Nordeste | 64 | 17 (27%) | 13.2% | 17.2% |
| Sul | 72 | 20 (28%) | 13.1% | 22.1% |

**Our assumption at this point:** sparsity is a regional effect (Nordeste and Sul).

**3. By province: is it really region?**
```python
def summarise(prof, by, sparse_threshold=0.2): ...
summarise(prof, ["region", "province"])
```
| Province | Volume | Zero weeks |
|---|---|---|
| SP | 36.3% | 1.4% |
| RJ | 13.6% | 6.3% |
| MG | 10.8% | 1.3% |
| RS | 9.3% | 9.5% |
| PR | 8.6% | 12.5% |
| BA | 6.4% | 14.4% |
| PE | 5.8% | 14.7% |
| CE | 5.1% | 10.3% |
| SC | 4.1% | 18.0% |

**Reading:** zero weeks rise as market size falls, across regions: within Sul, RS (9.5%)
differs strongly from SC (18.0%); PR behaves like the Nordeste states. The regional effect was
really a market-size effect. One exception: RJ is bigger than MG but has more zero weeks.

**4. Why is RJ sparser than MG? (emergent question Q-11)**
**Our guess:** RJ sells a wider range (31 vs 26 products), so more slow long-tail products.
```python
prof[prof["province"].isin(["RJ", "MG"]) & (prof["zero_share"] > 0.2)]
only_rj = prof[(prof["province"] == "RJ") & prof["sku_name"].isin(rj - mg)]
```
| Sparse series | Product | Zero weeks | Total HL |
|---|---|---|---|
| RJ·34938 | BRAHMA keg | 68% | 24,741 |
| RJ·82428 | BUDWEISER keg | 59% | 21,955 |
| RJ·13353 | ANTARCTICA keg | 54% | 12,275 |
| MG·84911 | SPATEN keg | 32% | 6,788 |

Of the 10 products RJ sells but MG doesn't, 9 have zero weeks of 0%.
**Reading:** the long-tail guess is rejected. RJ's extra zeros come from three high-volume
kegs ordered in big, irregular batches. All 4 sparse series in RJ and MG are kegs.

**5. Is it kegs everywhere? (emergent question Q-12)**
```python
summarise(prof, "container")
summarise(prof.assign(is_keg=...), ["province", "is_keg"])   # pivoted: zero weeks, keg vs can/bottle
```
| Container | Series | Sparse | Zero weeks | Volume |
|---|---|---|---|---|
| can | 126 | 12 | 4.5% | 64.6% |
| bottle | 61 | 8 | 6.6% | 27.3% |
| keg | 44 | 22 | 23.3% | 8.1% |

| Province | Cans/bottles zero weeks | Kegs zero weeks |
|---|---|---|
| SP / RJ / MG | 0.0% / 0.0% / 0.0% | 6.0% / 30.0% / 5.3% |
| RS / PR | 4.5% / 8.2% | 30.4% / 25.5% |
| BA / PE / CE | 13.3% / 9.9% / 5.9% | 18.9% / 43.5% / 33.2% |
| SC | 11.1% | 53.5% |

**Reading:** two drivers that add up. Cans and bottles never miss a week in the big markets but
do in smaller ones (market size). Kegs miss weeks almost everywhere except SP and MG (container).
A keg in a small province (SC: 53.5%) is the hardest case.

### Where our thinking changed
| Step | We thought | The data said |
|---|---|---|
| Region table | Nordeste and Sul are sparse | partly true… |
| Province table | it's market size, not region | true for cans and bottles… |
| RJ vs MG | RJ has a long tail of small products | rejected: high-volume kegs ordered in batches |
| Container table | n/a | two drivers, container and market size, adding up |

### Final insights
- **I-03:** Sudeste carries 60.7% of volume and is dense; Nordeste and Sul hold 37 of the 42
  sparse series.
- **I-04:** sparsity follows market size more than region (SP 1.4% … SC 18.0% zero weeks).
- **I-05:** RJ's sparsity comes from high-volume lumpy kegs, not a long tail: sparse ≠ small.
- **I-06:** sparsity has two drivers, container (kegs) and market size, that add up.

### What it means for modelling
- Overall volume-weighted accuracy will be driven by Sudeste (SP alone is 36%); report accuracy
  by province and by container, not only in total.
- Segment series by their own behaviour (ADI/CV²), not by region or container label.
- Give a global model both container type and a market-size signal.
- Lumpy kegs carry real volume (8.1% in total, up to 25k HL per series): they need
  intermittent-demand methods and must not be dismissed as low-impact.

---

## 4.1.3 Validity: are the numbers believable?

### Main question
Are the weekly volumes sensible, or do some values look impossible or suspiciously extreme?
For every extreme week: real business event, or data error?

### Why it matters
A data error left in teaches the model something that never happened; a real big week
removed as an "error" hides real demand. We must tell the two apart.

### Example
| Week (SP · Brahma can, typical ~1,000 HL) | HL | x typical | Probably |
|---|---|---|---|
| Normal | 1,020 | 1.0x | normal |
| Promotion | 1,900 | 1.9x | real |
| Before Carnival | 1,450 | 1.5x | real |
| Strange | 102,000 | 102x | error: litres typed instead of HL |

### Method box: median, MAD and the robust z-score
One series, five weeks: 100, 105, 98, 102, **300**

| Measure | Formula | Result |
|---|---|---|
| Median | middle of 98, 100, 102, 105, 300 | 102 |
| Ratio to median | 300 ÷ 102 | 2.9x |
| Absolute deviations | \|x − 102\| | 2, 3, 4, 0, 198 |
| MAD | median of 0, 2, 3, 4, 198 | 3 |
| Robust z of the 300 week | (300 − 102) ÷ (1.4826 × 3) | 44.5 |

With the ordinary mean (141) and standard deviation (88.9), z = (300 − 141) ÷ 88.9 = 1.8: the
300 hides itself by pulling up the mean and the spread. The robust z flags it clearly.
1.4826 scales the MAD so it is comparable to a standard deviation for normal data.

### The journey

**1. Impossible values?**
```python
print("missing:", v.isna().sum(), "| negative:", (v < 0).sum(), f"| zero: {(v == 0).sum()} ({(v == 0).mean():.1%})")
```
```
missing: 0 | negative: 0 | zero: 4230 (9.0%)
```
No missing or negative values. 9% of weekly rows are zero weeks (sparse series contribute many).

**2. Unit errors?**
```
mean 204.5 · median 129.6 · 99% 1,221.4 · max 4,021.1 HL
```
The maximum is ~3x the 99th percentile. A litres-for-HL mistake would show ~100,000. None.

**3. Which weeks are extreme for their own series?**
```python
med = g.transform("median"); mad = g.transform(lambda s: (s - s.median()).abs().median())
nz["ratio_to_median"] = nz["volume_hl"] / med
nz["robust_z"] = (nz["volume_hl"] - med) / (1.4826 * mad)
```
```
weeks > 3x median: 745 · > 10x: 13 · robust z > 5: 241
```
10 of the 13 weeks above 10x are batch orders in sparse series (premium cans and bottles, kegs,
small provinces). 3 are in series with no zero weeks (RS Spaten 473 can, RS Budweiser long neck,
SP Corona keg), all in the Christmas/New Year summer peak.
**Our assumption at this point:** those 3 series are steady, so their 10x weeks may be errors.

**4. Are those three real? (emergent question Q-13)**
Method: check the promotion calendar (answer key; on real data, ask the commercial team),
the weeks around the extreme, and the same week last year.
```python
extreme = nz[nz["ratio_to_median"] > 10].merge(promo[["series", "week_start", "uplift"]], how="left", ...)
```
```
promotion = False for all 13
```
| Series | Weekly HL around the extreme |
|---|---|
| RS · Spaten 473 can | 3.8 · 20.2 · 44.9 · 553.8 · 97.4 · 4.2 · 70.1 |
| RS · Budweiser long neck | 1.7 · 414.8 · 19.3 · 966.2 · 51.8 · 109.6 · 2.1 |
| SP · Corona keg | 117.7 · 49.9 · … · 788.4 · 15.3 · 2.2 · 49.5 |

Not promotions (those lift a week by at most ~2x) and not isolated spikes: these series swing
from ~2 to ~1,000 HL all the time. They sell every week, in wildly varying amounts: erratic.

### Where our thinking changed
| We assumed | The data showed |
|---|---|
| No zero weeks = steady | wrong: frequency and size variability are separate; these series are erratic |
| Their 10x weeks might be errors | real ordering behaviour |
| The biggest spikes would be promotions | none of the 13 is a promotion; promotions are moderate |

### Final insights
- **I-07:** values are valid; no missing, negative or unit-error values; extremes are real.
- **I-08:** how often a series sells and how variable its size is are separate dimensions;
  the biggest spikes come from ordering behaviour, not promotions.

### What it means for modelling
- No global outlier cap: detection must use each series' seasonal expectation and be segment-aware (4.6).
- Segment with both ADI and CV² (4.8); erratic series will be hard to forecast.
- Promotion spike detection should target moderate lifts.

---

## 4.1.4 Consistency: do the tables agree with each other?

### Main question
Do the processed tables fit together: totals, master lists, weather, holidays, product lifecycle?

### Why it matters
Later phases join these tables. A missing master code drops sales from every "by brand" view;
missing weather or holidays leave holes in features; a calendar that stops too early means the
model forecasts future weeks as if nothing were a holiday.

### Example
If the weekly step lost 47,000 HL, the weekly total would be 9,612,000 instead of 9,659,000 HL.
If the holiday calendar stopped in December 2024, a forecast for spring 2025 would miss Easter.

### Method box: "trust, but verify"
The pipeline already validates the raw data. The audit re-checks the final processed tables
independently, which catches bugs in the checker itself or in steps after it.

### The journey
```python
# 1 weekly vs daily total · 2 codes in masters · 3 weather per province-week
# 4 holiday calendar vs forecast horizon (last week + 13 weeks) · 5 sales outside SKU life
```
```
1. weekly total 9,659,113.6 HL | daily total 9,659,113.6 HL
2. provinces missing from master: set() | SKUs missing from master: set()
3. province-weeks without weather: 0
4. holidays cover 2020-01-01 → 2030-12-25 | needed at least until 2025-06-16
5. weeks with sales outside the SKU's life: 0
```
**Reading:** all five checks pass, exactly.

### Final insight
- **I-09:** the processed tables are fully consistent.

### What it means for modelling
- Joins are safe; weather and holiday features will have full coverage, including the horizon.
- When real data arrives, the client's holiday calendar must also reach 12+ weeks ahead.

---

## Still to do in 4.1
- 4.1.5 Timeliness: how current is the data, and how stable are the latest weeks?
- 4.1.6 Data readiness scorecard and the pipeline fix PF-01.
