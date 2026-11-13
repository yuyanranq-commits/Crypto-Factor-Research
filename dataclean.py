import pandas as pd
import numpy as np
close=pd.read_csv('data/wide_close.csv')
volume=pd.read_csv('data/wide_volume.csv')

close = close.set_index('ts')
close.index = pd.to_datetime(close.index)
volume=volume.set_index('ts')
volume.index = pd.to_datetime(volume.index)

def split_on_gap(close, volume, max_gap=7):
    """If a coin's data gap exceeds max_gap days, treat the data after the split as a new coin"""
    new_close, new_volume = {}, {}
    for col in close.columns:
        s = close[col].dropna()
        seg = (s.index.to_series().diff().dt.days > max_gap).cumsum()
        for k, part in s.groupby(seg):
            name = col if k == 0 else col.replace('/', f'{k+1}/')
            new_close[name] = part
            new_volume[name] = volume[col].loc[part.index]
    return pd.DataFrame(new_close).reindex(close.index), pd.DataFrame(new_volume).reindex(close.index)
cols_before = close.columns
close, volume = split_on_gap(close, volume)
new_cols = close.columns.difference(cols_before)
print(f"Split columns by long breaks：{len(cols_before)} -> {close.shape[1]} ")
print("Split columns：", new_cols.tolist())

report = {}
for col in close.columns:
    s = close[col]
    fv = s.first_valid_index()
    lv = s.last_valid_index()
    if fv is None:
        report[col] = {'state':'empty','valid days':0}
        continue
    span = s.loc[fv:lv]
    report[col] = {
        'crypto listing date': fv.date(),
        'valid days': int(s.notna().sum()),
        'Post-listing vacuum': int(span.isna().sum()),
        'Vacuum Proportion': round(span.isna().mean(), 3),
    }
diag = pd.DataFrame(report).T.sort_values('valid days')
print(diag)

#Looking for residual stablecoins
returns = close.pct_change(fill_method=None)
ret_std=returns.std().sort_values()
print(ret_std.head(15))

# A second stablecoin test. The standard deviation is pulled up by a single depeg spike
# (AEUR, a euro stablecoin, briefly hit 2.89 in 2024 and slipped through the std filter).
# The MEDIAN absolute daily move ignores one-off spikes: AEUR = 0.27%, the next lowest coin (TRX) = 1.28%.
ret_mad = returns.abs().median().sort_values()
print(ret_mad.head(5))

#Remove coins
stable_like=ret_std[ret_std<0.005].index.tolist()
stable_like += [c for c in ret_mad[ret_mad < 0.005].index if c not in stable_like]

# Leveraged tokens whose whole name is BULL or BEAR. The scraper's is_leveraged() only
# catches names like ETHBULL (a base coin + suffix), so plain BULL/BEAR got through.
# Checking that the prefix is itself a coin avoids false hits like SYRUP (ends in "UP").
bases = {c.split('/')[0] for c in close.columns}
def is_leveraged_name(base):
    if base in {'BULL', 'BEAR'}:
        return True
    return any(base.endswith(sfx) and base[:-len(sfx)] in bases for sfx in ['UP', 'DOWN', 'BULL', 'BEAR'])
leveraged = [c for c in close.columns if is_leveraged_name(c.split('/')[0])]

# Derivatives of another coin (staked or wrapped versions) are excluded by name, with the reason, like WBETH/BETH
# in the scraper. A high return correlation is only a hint: it can flag two different coins that moved together,
# and it is measured over the whole sample, so it would use future prices to decide who enters the sample.
# The scan below prints candidates for a manual check and deletes nothing.
DERIVATIVES = {'BNSOL/USDT': "Binance's staked SOL (return correlation with SOL 0.999)"}
def high_correlation_pairs(returns, threshold=0.98, min_days=90):
    has = returns.notna()
    cols = returns.columns
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            both = has[a] & has[b]
            if both.sum() < min_days:
                continue
            corr = np.corrcoef(returns.loc[both, a], returns.loc[both, b])[0, 1]
            if corr > threshold:
                listed = 'excluded' if a in DERIVATIVES or b in DERIVATIVES else 'check by hand'
                print(f'high correlation: {a} ~ {b}  corr={corr:.4f} over {both.sum()} days ({listed})')
high_correlation_pairs(returns)
duplicates = [c for c in DERIVATIVES if c in close.columns]

diag['base']=diag.index.str.split('/').str[0]
suspect=diag[diag['base'].str.endswith('B')&
             (pd.to_datetime(diag['crypto listing date'])>='2025-01-01')]
print('Suspicious stock tokens:',suspect.index.tolist())
# YB (YieldBasis) is a crypto token whose ticker happens to end in B
keep=['YB/USDT']
stock_tokens=[s for s in suspect.index if s not in keep]
# No minimum-history filter: whether a coin has 30 days of data is only known 30 days after it lists, so dropping
# short series would remove exactly the coins that failed fast (survivorship bias). factor.py and the delisting
# panel already require enough past data at each date.
drop=set(stable_like)|set(stock_tokens)|set(leveraged)|set(duplicates)
print(f"Numbers of remaining stablecoins: {len(stable_like)}  Stock tokens: {len(stock_tokens)}  "
      f"Leveraged: {len(leveraged)}  Derivatives: {len(duplicates)}  Sum: {len(drop)}")
print('Leveraged:', leveraged, ' Derivatives:', duplicates)
close_clean = close.drop(columns=list(drop), errors='ignore')
volume_clean = volume.drop(columns=list(drop), errors='ignore')
print("Strictly increasing",close_clean.index.is_monotonic_increasing)
print("duplicating days",close_clean.index.duplicated().sum())
print('final shape:',close_clean.shape)
close_clean.to_csv('data/close_clean.csv')
volume_clean.to_csv('data/volume_clean.csv')
