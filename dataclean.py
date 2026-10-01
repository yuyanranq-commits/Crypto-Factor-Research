import pandas as pd
close=pd.read_csv('D:/python-practise/data-analyse/crypto/wide-close.csv')
volume=pd.read_csv('D:/python-practise/data-analyse/crypto/wide-volume.csv')
close = close.set_index('ts')
close.index = pd.to_datetime(close.index)
volume=volume.set_index('ts')
volume.index = pd.to_datetime(volume.index)
report = {}
for col in close.columns:
    s = close[col]
    fv = s.first_valid_index()
    lv = s.last_valid_index()
    if fv is None:
        report[col] = {'state':'empty','valid days':0}
        continue
    span = s.loc[fv:lv]                      # from listing day to current
    report[col] = {
        'crypto listing date': fv.date(),
        'valid days': int(s.notna().sum()),
        'Post-listing vacuum': int(span.isna().sum()),
        'Vacuum Proportion': round(span.isna().mean(), 3),
    }

diag = pd.DataFrame(report).T.sort_values('valid days')
print(diag)
drop=['DAI/USDT','XAUT/USDT','PAXG/USDT']
close_clean=close.drop(columns=drop)
volume_clean=volume.drop(columns=drop)
print("Strictly increasing",close_clean.index.is_monotonic_increasing)
print("duplicating days",close_clean.index.duplicated().sum())
close_clean.to_csv("D:/python-practise/data-analyse/crypto/close_clean.csv")
volume_clean.to_csv("D:/python-practise/data-analyse/crypto/volume_clean.csv")