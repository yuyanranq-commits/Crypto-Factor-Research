import pandas as pd
close=pd.read_csv('D:/python-practise/data-analyse/crypto/close_clean.csv',index_col=0, parse_dates=True)
volume=pd.read_csv('D:/python-practise/data-analyse/crypto/volume_clean.csv',index_col=0, parse_dates=True)
returns=close.pct_change()
momentum_raw=close.pct_change(20)
def cross_sectional_zscore(df):
    return df.sub(df.mean(axis=1),axis=0).div(df.std(axis=1), axis=0)
mom_z=cross_sectional_zscore(momentum_raw)
mom_factor=mom_z.shift(1)

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
print("IC without look-ahead bias:", quick_ic(mom_z, returns))      # 大概率虚高
print("IC with 1-period lag:", quick_ic(mom_factor, returns))    # 回落到真实水平

#vol_factor
import numpy as np
volatility_raw = returns.rolling(window=20).std()
volatility_raw=volatility_raw.replace([np.inf,-np.inf],np.nan)
vol_z = cross_sectional_zscore(volatility_raw)
vol_factor = vol_z.shift(1)
print("IC without look-ahead bias:", quick_ic(vol_z, returns))        # 复用上周的 quick_ic 函数
print("IC with 1-period lag:", quick_ic(vol_factor, returns))

#rev_factor
reversal_raw = -close.pct_change(5)
reversal_raw = reversal_raw.replace([np.inf, -np.inf], np.nan)   # 保险起见
rev_z = cross_sectional_zscore(reversal_raw)
rev_factor = rev_z.shift(1)
print("IC without look-ahead bias:", quick_ic(rev_z, returns))
print("IC with 1-period lag:", quick_ic(rev_factor, returns))

dollar_volume=volume*close
adv=dollar_volume.rolling(20).mean().shift(1)
THRESHOLD=10_000_000
tradable=(adv>=THRESHOLD).fillna(False).astype(bool)
mom_factor=mom_factor.where(tradable)
vol_factor=vol_factor.where(tradable)
rev_factor=rev_factor.where(tradable)
before = mom_z.notna().sum().sum()          # Use mom_z to be the base
after  = mom_factor.notna().sum().sum()
print(f"raw: {before}, filtered: {after}, filter out: {(before-after)/before:.1%}")
daily_count = mom_factor.notna().sum(axis=1)
print(f"Daily Candidate Pool Size：Medium {daily_count.median():.0f}，Min {daily_count.min():.0f}")

stable_start = '2020-11-22'
daily_count = mom_factor.notna().sum(axis=1)
valid = daily_count.loc[stable_start:]
print(f" After 2020-11-22：Medium {valid.median():.0f}，Min {valid.min():.0f}，Mean {valid.mean():.1f}")

mom_factor = mom_factor.dropna(axis=1, how='all')
vol_factor = vol_factor.dropna(axis=1, how='all')
rev_factor = rev_factor.dropna(axis=1, how='all')
mom_factor.to_csv('D:/python-practise/data-analyse/crypto/mom_factor.csv')
vol_factor.to_csv('D:/python-practise/data-analyse/crypto/vol_factor.csv')
rev_factor.to_csv('D:/python-practise/data-analyse/crypto/rev_factor.csv')