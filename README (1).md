# Crypto Factor Research on a Survivorship-Bias-Free Universe

Daily cross-sectional factor research on Binance USDT spot pairs, 2020-01 to 2026-10.
The universe includes coins that were later delisted, and each day only coins that were liquid *at that time* can be traded.

The main point of the project is that the universe definition changes the conclusions a lot.
An earlier version used about 30 coins that are large today. On that universe an equal-weighted basket returned +42% a year.
On the point-in-time universe built here, the same basket returned **−33% a year**.

## Main findings

| | Result |
|---|---|
| Universe | ~690 USDT spot pairs scraped (198 already delisted); 571 coins enter the tradable universe at some point; median 78 tradable coins per day |
| Survivorship bias | Equal-weighted benchmark CAGR **+42%** (today's large coins) vs **−33%** (point-in-time universe) |
| Volatility factor | Rank IC **−0.12**: low-volatility coins outperform. Still −0.11 after neutralizing for size |
| Low-vol long-only | CAGR 9.8%, Sharpe 0.50 vs benchmark CAGR −33%, Sharpe −0.02 |
| Momentum | Time-series momentum beats cross-sectional momentum at every lookback (30–180 days). Cross-sectional momentum loses money at every lookback |
| Caveats | The long-short result (NAV ×354 after costs) comes almost entirely from shorting high-vol coins in 2025–26 and is not realistic. Low-vol long-only is negative in the last 30% of the sample |

## Pipeline

```
scraper2.py    Binance USDT spot pairs (incl. delisted) -> data/raw/*.csv -> data/wide_close.csv, wide_volume.csv
dataclean.py   split reused tickers, drop stablecoins / stock tokens / too-short series -> data/close_clean.csv
factor.py      momentum, volatility, reversal factors; liquidity filter; look-ahead check -> data/*_factor.csv
utils.py       performance_stats (CAGR, Sharpe, MDD)
backtest.ipynb   volatility factor: quantiles, long-short, long-only vs benchmark, size neutralization, diagnostics
backtest2.ipynb  time-series vs cross-sectional momentum, 30/60/90/180-day lookbacks
```

### 1. Data (`scraper2.py`)

- All Binance spot markets with quote USDT, **including inactive (delisted) ones**. Most tutorials start from today's top coins, which only keeps the survivors.
- Excludes stablecoins, fiat and gold tokens, wrapped BTC/ETH, and leveraged tokens (BTCUP, ETHDOWN, …).
- Daily OHLCV from 2020-01-01 via `ccxt`. Each pair is saved to its own file, so the download can resume after interruptions.

### 2. Cleaning (`dataclean.py`)

- **Ticker reuse.** Binance sometimes reuses a symbol for a different asset. For example, LUNA/USDT before and after the 2022 collapse. If a series has a gap longer than 7 days, the part after the gap becomes a new column (LUNA → LUNA2).
- **Stablecoins.** Coins with daily return std < 0.005 are dropped.
- **Tokenized stocks.** Symbols ending in "B" and listed in 2025 or later are dropped.
- **Short series.** Coins with fewer than 30 valid days are dropped.

### 3. Factors and tradable universe (`factor.py`)

| Factor | Definition |
|---|---|
| Momentum | 20-day return |
| Volatility | 20-day std of daily returns (at least 15 observations) |
| Reversal | minus 5-day return |

- **Tradable universe.** On each day, a coin is tradable only if its 20-day average dollar volume, measured up to the previous day, is ≥ $10M. This removes about 74% of coin-days and leaves a median of 78 coins per day. The sample starts on 2020-11-22, once the universe is stable.
- **No look-ahead.** Factors are shifted by one day. The z-score is computed only within that day's tradable coins.
- **Control experiment.** Without the one-day lag, the IC is badly inflated, because the day-*t* return appears in both the factor and the target:

| Factor | IC, no lag (wrong) | IC, 1-day lag |
|---|---|---|
| Momentum | +0.106 | −0.046 |
| Volatility | −0.100 | −0.114 |
| Reversal | −0.330 | +0.032 |

(These ICs use the full sample from 2020. The backtest notebook starts on 2020-11-22, where the volatility IC is −0.119.)

### 4. Volatility factor (`backtest.ipynb`)

Mean daily return by volatility quintile (Q1 = lowest vol):

| Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|
| +0.100% | +0.078% | +0.040% | +0.049% | **−0.285%** |

Most of the effect sits in the highest-volatility quintile.

**Long-only low-vol (Q1) vs equal-weighted tradable universe**

| | CAGR | Sharpe | Max drawdown | Ann. vol |
|---|---|---|---|---|
| Low-vol long (Q1) | 9.8% | 0.50 | −89% | 73% |
| Benchmark | −33.0% | −0.02 | −99% | 87% |

The benchmark has a Sharpe near zero but a CAGR of −33%. At 87% annual volatility, the volatility drag is large enough to turn a roughly zero average daily return into heavy compounding losses.

**Stability.** The long leg has a Sharpe of 0.86 in the first 70% of the sample and −0.63 in the last 30%.

![Low-vol long vs benchmark](figures/Low-Vol%20Long%20vs.%20Equal-Weighted%20Market%20Benchmark.png)

**Long-short (long Q1, short Q5)**

Final NAV is 803 before costs and 354 after 10bp costs, with daily turnover of 0.38.
This number should not be taken at face value:

- Almost all of it comes from the short leg in 2025–26. In those two years the Q5 basket fell about 97% each year. The decline was broad (mean ≈ median daily return), not driven by a few collapses.
- 2022 also had a large short opportunity: Q5 fell 95%. But in 2021 Q5 rose 186%, and the short leg lost most of its capital first. Because returns compound, the gains in 2022 only brought the NAV back to around where it started. This is path dependence.
- Shorting small altcoins on spot is often not possible. Perpetual swaps add funding costs. The real short leg would earn much less.

![Long vs short leg](figures/long%20Q1%20vs%20short%20Q5.png)

### 5. Momentum: time-series vs cross-sectional (`backtest2.ipynb`)

- **Time-series (TS).** Long a coin if its own past L-day return is positive, short otherwise.
- **Cross-sectional (CS).** Long if the coin's return is above that day's cross-sectional median, short otherwise. The median, not the mean, is used because returns are right-skewed. Splitting on the mean would leave the book net short.
- Both strategies are weighted to gross exposure 1 and charged 10bp on turnover. Both are compared from the same start date.

| Lookback | TS Sharpe | CS Sharpe | TS CAGR | CS CAGR | TS turnover | CS turnover |
|---|---|---|---|---|---|---|
| 30 | **0.70** | −0.22 | 26.9% | −5.9% | 0.20 | 0.21 |
| 60 | 0.39 | −0.72 | 5.6% | −14.2% | 0.16 | 0.17 |
| 90 | 0.36 | −0.69 | 3.5% | −13.7% | 0.13 | 0.15 |
| 180 | 0.04 | −0.66 | −15.5% | −13.2% | 0.12 | 0.13 |

- TS momentum is better at every lookback, and shorter lookbacks work better.
- Average net exposure of TS is only about +0.03, so the result is not just being long the market.
- Cross-sectional momentum loses money at every horizon. In this universe, coins that outperformed their peers tend to give it back.

![TS vs CS momentum](figures/Time-Series%20Momentum%20vs%20Cross-Sectional%20Momentum.png)

## Limitations

- **Statistical significance.** With about 6 years of daily data, the standard error of an annualized Sharpe ratio is roughly 1/√6 ≈ 0.4. The low-vol Sharpe of 0.50 is therefore not statistically different from zero. No correction is made for testing several factors and lookbacks.
- **Costs.** The cost model is a flat 10bp on turnover. There is no slippage model, no market impact, and no funding or borrow cost for shorts.
- **Data scope.** One exchange (Binance spot) only, and daily bars only.
- **Thin recent universe.** In 2026 the average tradable universe is about 40 coins, so each quintile has only ~8 coins.
- **Cleaning rules.** Thresholds such as std < 0.005, the 7-day gap and the "B" suffix rule are simple heuristics, checked by hand on this dataset.

## How to run

```bash
pip install -r requirements.txt
python scraper2.py     # Binance API returns HTTP 451 from US IPs; run this on a non-US server
python dataclean.py
python factor.py
# then run backtest.ipynb and backtest2.ipynb (Restart & Run All); figures are saved to figures/
```

Run all scripts from the repository root. Raw data is not committed (`data/` is in `.gitignore`).
