import pandas as pd
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / 'delisting'

# prices: wide CSVs from dataclean.py -> one row per (ts, symbol)
close = pd.read_csv(ROOT / 'data' / 'close_clean.csv', index_col=0)
volume = pd.read_csv(ROOT / 'data' / 'volume_clean.csv', index_col=0)
close = close.reset_index().melt(id_vars='ts', var_name='symbol', value_name='close')
volume = volume.reset_index().melt(id_vars='ts', var_name='symbol', value_name='volume')
prices = pd.merge(close, volume, on=['ts', 'symbol'], how='left').dropna(subset=['close'])
prices['ts'] = pd.to_datetime(prices['ts'], utc=True).dt.tz_localize(None).dt.date

con = duckdb.connect(str(HERE / 'crypto.duckdb'))
con.register('prices_df', prices)
con.execute('CREATE OR REPLACE TABLE prices AS SELECT * FROM prices_df')
con.execute('CREATE OR REPLACE TABLE sample_window AS SELECT MIN(ts) AS sample_start, MAX(ts) AS sample_end FROM prices')

labels_path = (HERE / 'labels' / 'exit_labels.csv').as_posix()
con.execute(f"CREATE OR REPLACE TABLE exit_labels AS SELECT * FROM read_csv_auto('{labels_path}')")

# assets: follow rename chains back to the first ticker (STRAT -> STRAX -> STRAX2 all get STRAT)
renames = con.execute("SELECT symbol, successor FROM exit_labels WHERE exit_type = 'rename'").df()
prev = dict(zip(renames['successor'], renames['symbol']))


def find_root(s):
    while s in prev:
        s = prev[s]
    return s


symbols = con.execute('SELECT DISTINCT symbol FROM prices').df()['symbol']
assets = pd.DataFrame({'symbol': symbols, 'asset_id': symbols.map(find_root)})
con.register('assets_df', assets)
con.execute('CREATE OR REPLACE TABLE assets AS SELECT * FROM assets_df')

for f in ['01_daily.sql', '02_lifetimes.sql', '03_panel.sql']:
    con.execute((HERE / 'sql' / f).read_text(encoding='utf-8'))

for t in ['prices', 'daily', 'lifetimes', 'panel']:
    print(f"{t:10s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>9,} rows")

# integrity checks: stop the build if any fails
one = lambda sql: con.execute(sql).fetchone()[0]

n = one("SELECT COUNT(*) FROM lifetimes WHERE stopped AND exit_type NOT IN ('delisting', 'rename', 'merger')")
assert n == 0, f'{n} stopped tickers have no exit label'

n = one('SELECT COUNT(*) FROM (SELECT symbol, month_start FROM panel GROUP BY ALL HAVING COUNT(*) > 1)')
assert n == 0, f'{n} duplicate (symbol, month) rows in panel'

n = one('SELECT COUNT(*) FROM (SELECT asset_id, month_start FROM panel GROUP BY ALL HAVING COUNT(*) > 1)')
assert n == 0, f'{n} (asset, month) rows where two tickers of one asset overlap'

n = one('SELECT COUNT(*) FROM panel WHERE stop_age <= start_age')
assert n == 0, f'{n} empty intervals in panel'

events = one('SELECT SUM(event::INT) FROM panel')
delisted = one("SELECT COUNT(*) FROM lifetimes WHERE exit_type = 'delisting' AND delist_scope = 'token'")
assert events == delisted, f'{events} event rows but {delisted} delisted tokens'

print(f'all checks passed: {events} delistings, {one("SELECT COUNT(DISTINCT asset_id) FROM panel")} assets')
con.close()
