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
renames = con.execute("SELECT symbol, successor, swap_ratio FROM exit_labels WHERE exit_type = 'rename'").df()
assert renames['swap_ratio'].notna().all(), 'every rename needs a swap_ratio'
prev = dict(zip(renames['successor'], renames['symbol']))


def find_root(s):
    while s in prev:
        s = prev[s]
    return s


symbols = con.execute('SELECT DISTINCT symbol FROM prices').df()['symbol']
assets = pd.DataFrame({'symbol': symbols, 'asset_id': symbols.map(find_root)})
con.register('assets_df', assets)
con.execute('CREATE OR REPLACE TABLE assets AS SELECT * FROM assets_df')

# adjustments: dated price adjustments per asset, like stock splits. ratio = new tokens per old token.
# A rename takes effect on the successor's first trading day; a redenomination that kept the ticker
# (SUN, QUICK, ...) on its ex_date. On any day, price x product(ratio of adjustments up to that day)
# = price per original token, so a rename or redenomination leaves no jump in the series.
redenom_path = (HERE / 'labels' / 'redenominations.csv').as_posix()
con.execute(f"CREATE OR REPLACE TABLE redenominations AS SELECT * FROM read_csv_auto('{redenom_path}')")
con.execute('''
    CREATE OR REPLACE TABLE adjustments AS
    SELECT a.asset_id, min(p.ts) AS ex_date, e.swap_ratio AS ratio, 'rename' AS kind
    FROM exit_labels e
    JOIN assets a ON a.symbol = e.symbol
    JOIN prices p ON p.symbol = e.successor
    WHERE e.exit_type = 'rename'
    GROUP BY a.asset_id, e.swap_ratio
    UNION ALL
    SELECT a.asset_id, CAST(r.ex_date AS DATE), CAST(r.swap_ratio AS DOUBLE), 'redenomination'
    FROM redenominations r
    JOIN assets a ON a.symbol = r.symbol
''')

for f in ['01_daily.sql', '02_lifetimes.sql', '03_panel.sql']:
    con.execute((HERE / 'sql' / f).read_text(encoding='utf-8'))

for t in ['prices', 'daily', 'lifetimes', 'panel']:
    print(f"{t:10s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>9,} rows")

# integrity checks: stop the build if any fails
one = lambda sql: con.execute(sql).fetchone()[0]

n = one("SELECT COUNT(*) FROM lifetimes WHERE stopped AND exit_type NOT IN ('delisting', 'rename', 'merger')")
assert n == 0, f'{n} stopped tickers have no exit label'

n = one('SELECT COUNT(*) FROM (SELECT asset_id, ts FROM daily GROUP BY ALL HAVING COUNT(*) > 1)')
assert n == 0, f'{n} days where two tickers of one asset both trade'

# the official swap ratio should match the price jump across each rename (within 3x, the gap moves prices)
bad = con.execute("""
    SELECT e.symbol, e.swap_ratio, a.last_close / b.first_close AS implied
    FROM exit_labels e
    JOIN lifetimes a ON a.symbol = e.symbol
    JOIN lifetimes b ON b.symbol = e.successor
    WHERE e.exit_type = 'rename' AND abs(ln(a.last_close / b.first_close / e.swap_ratio)) > ln(3)
""").df()
assert bad.empty, f'swap ratios that do not match prices:\n{bad}'

# a redenomination's ratio should match the price jump across its ex_date (within 3x)
bad = con.execute("""
    SELECT r.symbol, r.ex_date, r.swap_ratio,
           (SELECT arg_max(close, ts) FROM prices WHERE symbol = r.symbol AND ts < CAST(r.ex_date AS DATE)) /
           (SELECT close FROM prices WHERE symbol = r.symbol AND ts = CAST(r.ex_date AS DATE)) AS implied
    FROM redenominations r
""").df()
bad = bad[(bad['implied'] / bad['swap_ratio']).map(lambda x: not (1 / 3 < x < 3))]
assert bad.empty, f'redenomination ratios that do not match prices:\n{bad}'

# no unexplained jump: after adjustment, no move of more than 3x across a trading halt (2 to 7 days).
# A one-day move that large can be real; one across a halt is almost always an unlabeled redenomination.
bad = con.execute("""
    SELECT symbol, ts, exp(log_ret) AS price_ratio
    FROM (SELECT *, date_diff('day', lag(ts) OVER (PARTITION BY asset_id ORDER BY ts), ts) AS gap FROM daily)
    WHERE gap >= 2 AND abs(log_ret) > ln(3)
""").df()
assert bad.empty, f'price jumps across a trading halt; add them to redenominations.csv:\n{bad}'

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
