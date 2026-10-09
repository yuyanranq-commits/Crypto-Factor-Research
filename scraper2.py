import ccxt,pandas as pd,time, os
ex=ccxt.binance({'enableRateLimit':True})
# Crypto scraping
def fetch_ohlcv(symbol, timeframe='1d', since=None, limit=1000):
    all_bars = []
    now=ex.milliseconds()
    while since<now:
        bars=ex.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        print(f"{symbol} this round get {len(bars)} bars, {len(all_bars)+len(bars)} in total")
        if not bars:break
        all_bars+=bars
        since=bars[-1][0]+1
        time.sleep(ex.rateLimit/1000)
    df=pd.DataFrame(all_bars,columns=['ts','open','high','low','close','volume'])
    df['ts']=pd.to_datetime(df['ts'],unit='ms',utc=True)
    return df.set_index('ts')

# Filtering
markets=ex.load_markets()
print(len(markets))
print(markets['BTC/USDT'])
exclude = {'USDC', 'FDUSD', 'TUSD', 'BUSD', 'DAI', 'USDP', 'PAX', 'USDD', 'UST', 'USTC',
           'PYUSD', 'USD1', 'USDE', 'EUR', 'GBP', 'AUD', 'TRY', 'BRL',
           'PAXG', 'XAUT', 'WBTC', 'WBETH', 'BETH'}
all_bases={m['base'] for m in markets.values()}
def is_leveraged(base):
    for suffix in ['UP','DOWN','BULL','BEAR']:
        if base.endswith(suffix) and base[:-len(suffix)] in all_bases:
            return True
    return False

symbols=[]
for sym, m in markets.items():
    if m['spot'] and m['quote']=='USDT' and m['base'] not in exclude and not is_leveraged(m['base']):
        symbols.append(sym)
print("Numbers of pairs:", len(symbols))
print('Delisting:',sum(not markets[sym]['active'] for sym in symbols))

# Storage
os.makedirs('data/raw',exist_ok=True)
failed=[]
for i, sym in enumerate(symbols,1):
    path='data/raw/'+sym.replace('/','_')+'.csv'
    if os.path.exists(path):
        continue
    try:
        since = ex.parse8601('2020-01-01T00:00:00Z')
        df=fetch_ohlcv(sym,since=since)
        df=df[~df.index.duplicated()].sort_index()
        df.to_csv(path)
        print(f'[{i}/{len(symbols)}]{sym}:{len(df)} bars')
    except Exception as e:
        failed.append((sym,str(e)[:50]))
        print('failed:', failed)

# Create wide table
close_dict, volume_dict = {}, {}
for sym in symbols:
    path = 'data/raw/' + sym.replace('/', '_') + '.csv'
    if not os.path.exists(path):
        continue
    df=pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        continue
    close_dict[sym]=df['close']
    volume_dict[sym]=df['volume']
close = pd.DataFrame(close_dict).sort_index()
volume = pd.DataFrame(volume_dict).sort_index()
close.index.name='ts'
volume.index.name='ts'
print('wide form shape:',close.shape)
close.to_csv('data/wide_close.csv')
volume.to_csv('data/wide_volume.csv')
