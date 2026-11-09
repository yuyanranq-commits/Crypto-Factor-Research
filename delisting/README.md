# Which Binance Tokens Get Delisted? A Survival Analysis

A point-in-time database of every Binance USDT spot token from 2020 to October 2026, and a time-varying Cox model
of which tokens get delisted. The database is built in SQL (DuckDB); the model uses `lifelines`.

## Main findings

| | Result |
|---|---|
| Data | 587 tickers chained into 544 assets; 25,090 token-months; 136 delistings |
| Labels | 192 tickers stopped trading: 144 delistings (8 of them only the USDT pair), 43 renames, 5 mergers, labeled by hand with sources |
| Strongest signal | 1 SD more trading volume → delisting hazard × **0.27** (95% CI 0.20–0.37) |
| Age matters | For tokens under 2 years old, a deep drawdown raises the hazard (HR 3.75); for older tokens, high volatility does (HR 1.85) |
| Out of sample | Trained before 2025, tested on 2025–26: AUC **0.728** vs 0.697 for volume alone; each month's riskiest 10% of tokens contains 34% of the delistings |

![Hazard ratios](figures/hazard_ratios.png)

## Pipeline

```
load_db.py                 builds crypto.duckdb and fails if any integrity check fails
labels/exit_labels.csv     192 exits: delisting / rename / merger, scope, successor, source URL
sql/01_daily.sql           trailing features per token-day (30/90/180-day windows, drawdown)
sql/02_lifetimes.sql       one row per ticker: first/last trade, exit type, asset_id, left truncation
sql/03_panel.sql           token-month panel with start/stop intervals and features as of each cutoff
survival_analysis.ipynb    data checks, Cox model, proportional hazards, robustness, out-of-sample test
```

```bash
python dataclean.py            # from the repository root; writes data/close_clean.csv, data/volume_clean.csv
python delisting/load_db.py
cd delisting && jupyter nbconvert --to notebook --execute --inplace survival_analysis.ipynb
```

## Design choices

**Delisting vs rename.** A ticker that stops trading is often not a failure: MATIC became POL, FTM became S.
Renames are chained into one asset, and age keeps counting across the rename. Mergers are censored. Only token-level
delistings are events; the 8 cases where Binance removed only the USDT pair are tested as a robustness check.

**No look-ahead.** Every feature window looks backward, and an `ASOF JOIN … ON cutoff > ts` takes the last trading day
strictly before each cutoff. The notebook recomputes 800 values from raw prices in pandas: 0 mismatches.

**Lagged features.** Delisted tokens trade a median 1.51× more in their last 30 days than in the 60 days before,
because the delisting is announced in advance. The model uses features from 30 days before each month starts.

![Exits by year](figures/exits_by_year.png)

## Model checks

- **Proportional hazards.** Interacting every feature with log(age) finds that the effects of volatility and drawdown change
  with age (LR test p = 0.0001), so the main model lets them differ for tokens under 2 years old. The pattern holds with a 3-year cutoff.
- **Robustness.** Hazard ratios keep their sign and rough size when USDT-pair removals are added as events, uncertain labels are dropped,
  left-truncated tokens are dropped, or unlagged features are used (`results_robustness.csv`).
- **Out of sample.** The age interactions were found on the full sample. Before 2025 alone the proportional hazards test finds
  nothing (p = 0.68), so the fair out-of-sample model is the five features without interactions (AUC 0.728).
  With the interactions it reaches 0.772, which is optimistic.

![Out-of-sample risk deciles](figures/oos_risk_deciles.png)

## Limitations

- Delistings come in same-day batches, so events are not independent and the confidence intervals are probably too narrow.
- 136 events is a small sample, and only 17 delisted tokens were under two years old.
- Tokens Binance had removed before the data was pulled are missing, so early years undercount delistings.
- Only USDT pairs on Binance spot are covered. 21 rename labels have no source link.
