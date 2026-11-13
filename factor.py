import pandas as pd
import numpy as np
from utils import load_prices
# Asset-level prices from delisting/load_db.py: renames chained, redenominations adjusted, halts held through
close, dollar_volume, traded = load_prices()
returns = close.pct_change(fill_method=None)
# One-day returns only (the asset traded today and yesterday), so a halt's multi-day move does not inflate volatility
one_day_returns = returns.where(traded & traded.shift(1, fill_value=False))
mom_raw=close.pct_change(periods=20,fill_method=None)
vol_raw = one_day_returns.rolling(window=20, min_periods=15).std().replace([np.inf, -np.inf], np.nan)
rev_raw = -close.pct_change(periods=5, fill_method=None).replace([np.inf, -np.inf], np.nan)
def make_factors(df,dollar_volume,traded,threshold=10_000_000,shift=True):
    adv = dollar_volume.rolling(window=20, min_periods=15).mean().shift(1)
    if shift:
        df_base=df.shift(1)
    else:
        df_base = df
    # A position for day t is set at the close of t-1, so the asset must have traded on t-1
    tradable = (adv >= threshold) & traded.shift(1, fill_value=False)
    df_t = df_base.where(tradable)
    def cross_sectional_zscore(df1):
        return df1.sub(df1.mean(axis=1), axis=0).div(df1.std(axis=1), axis=0)
    df_z = cross_sectional_zscore(df_t)
    return df_z
mom=make_factors(mom_raw,dollar_volume,traded,shift=False)
mom_factor=make_factors(mom_raw,dollar_volume,traded,shift=True)
vol=make_factors(vol_raw,dollar_volume,traded,shift=False)
vol_factor=make_factors(vol_raw,dollar_volume,traded,shift=True)
rev=make_factors(rev_raw,dollar_volume,traded,shift=False)
rev_factor=make_factors(rev_raw,dollar_volume,traded,shift=True)

from scipy.stats import spearmanr
def quick_ic(factor, ret):
    ics = []
    for date in factor.index:
        f, r = factor.loc[date], ret.loc[date]
        mask = f.notna() & r.notna()
        if mask.sum() > 5:
            ics.append(spearmanr(f[mask], r[mask]).correlation)
    return pd.Series(ics).mean()
#mom_factor
print("Momentum IC with look-ahead bias:", quick_ic(mom, returns))
print("Momentum IC with 1-period lag:", quick_ic(mom_factor, returns))
#vol_factor
print("Volatility IC with look-ahead bias:", quick_ic(vol, returns))
print("Volatility IC with 1-period lag:", quick_ic(vol_factor, returns))
#rev_factor
print("Reversal IC with look-ahead bias:", quick_ic(rev, returns))
print("Reversal IC with 1-period lag:", quick_ic(rev_factor, returns))

before = mom_raw.shift(1).notna().sum().sum()
after  = mom_factor.notna().sum().sum()
print(f"raw: {before}, filtered: {after}, filter out: {(before-after)/before:.1%}")
daily_count = mom_factor.notna().sum(axis=1)
print(f"Daily Candidate Pool Size：Medium {daily_count.median():.0f}，Min {daily_count.min():.0f}")

stable_start = '2020-11-22'
valid = daily_count.loc[stable_start:]
print(f" After 2020-11-22：Medium {valid.median():.0f}，Min {valid.min():.0f}，Mean {valid.mean():.1f}")

mom_factor = mom_factor.dropna(axis=1, how='all')
vol_factor = vol_factor.dropna(axis=1, how='all')
rev_factor = rev_factor.dropna(axis=1, how='all')
mom_factor.to_csv('data/mom_factor.csv')
vol_factor.to_csv('data/vol_factor.csv')
rev_factor.to_csv('data/rev_factor.csv')

