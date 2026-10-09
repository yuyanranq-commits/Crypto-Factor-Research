import pandas as pd
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
ret_std=close.pct_change(fill_method=None).std().sort_values()
print(ret_std.head(15))
#Remove coins
stable_like=ret_std[ret_std<0.005].index.tolist()
diag['base']=diag.index.str.split('/').str[0]
suspect=diag[diag['base'].str.endswith('B')&
             (pd.to_datetime(diag['crypto listing date'])>='2025-01-01')]
print('Suspicious stock tokens:',suspect.index.tolist())
keep=[]
stock_tokens=[s for s in suspect.index if s not in keep]
too_short=diag.index[diag['valid days']<30].tolist()
drop=set(stable_like)|set(too_short)|set(stock_tokens)
print(f"Numbers of remaining stablecoins: {len(stable_like)}  Stock tokens: {len(stock_tokens)}  "
      f"Lack of data: {len(too_short)}  Sum: {len(drop)}")
close_clean = close.drop(columns=list(drop), errors='ignore')
volume_clean = volume.drop(columns=list(drop), errors='ignore')
print("Strictly increasing",close_clean.index.is_monotonic_increasing)
print("duplicating days",close_clean.index.duplicated().sum())
print('final shape:',close_clean.shape)
close_clean.to_csv('data/close_clean.csv')
volume_clean.to_csv('data/volume_clean.csv')