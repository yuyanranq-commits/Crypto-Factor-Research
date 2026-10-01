import ccxt,pandas as pd,time
ex=ccxt.binance({'enableRateLimit':True})
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
symbols = ['BTC/USDT','ETH/USDT','BNB/USDT','XRP/USDT','SOL/USDT',
    'TRX/USDT','FIGR_HELOC/USDT','HYPE/USDT','ZEC/USDT','DOGE/USDT',
    'RAIN/USDT','XMR/USDT','LEO/USDT','WBT/USDT','LINK/USDT',
    'ADA/USDT','XLM/USDT','BCH/USDT','DAI/USDT','CC/USDT',
    'LTC/USDT','UNI/USDT','HBAR/USDT','AVAX/USDT','SUI/USDT',
    'SHIB/USDT','BUIDL/USDT','USYC/USDT','XAUT/USDT','CRO/USDT',
    'NEAR/USDT','M/USDT','OKB/USDT','TAO/USDT','ASTER/USDT',
    'AAVE/USDT','PAXG/USDT','MNT/USDT','WLFI/USDT','MORPHO/USDT',
    'ONDO/USDT','PUMP/USDT','SKY/USDT','DOT/USDT','ENA/USDT','HTX/USDT',
           'PEPE/USDT','BGB/USDT','ICP/USDT']
close_dict = {}
volume_dict = {}
failed = []
for sym in symbols:
    try:
        since = ex.parse8601('2020-01-01T00:00:00Z')   # 每个币都要重置 since！
        df = fetch_ohlcv(sym, since=since)
        if df.empty:
            failed.append((sym, 'empty data'))
            continue
        # Deduplication + Sorting
        df = df[~df.index.duplicated()].sort_index()
        close_dict[sym] = df['close']
        volume_dict[sym] = df['volume']
    except Exception as e:
        failed.append((sym, str(e)[:50]))
        print(f"⚠️ {sym} fail: {str(e)[:50]}")
        continue

# concat：index=date，columns=coins
close = pd.DataFrame(close_dict)
volume = pd.DataFrame(volume_dict)

print(f"success: {close.shape[1]}，fail: {len(failed)}")
print("failed series:", failed)
print("wide form shape:", close.shape)

# saved
close.to_csv('/root/wide-close.csv')
volume.to_csv('/root/wide-volume.csv')