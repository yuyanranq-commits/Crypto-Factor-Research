import numpy as np
import pandas as pd
def performance_stats(daily_ret, periods=365):
    daily_ret = daily_ret.dropna()
    nav = (1 + daily_ret).cumprod()
    total = nav.iloc[-1] - 1
    years=len(daily_ret)/365
    CAGR = nav.iloc[-1]**(1/years)-1 if nav.iloc[-1] > 0 else -1
    ann_vol = daily_ret.std() * np.sqrt(periods)
    sharpe = daily_ret.mean() / daily_ret.std()*np.sqrt(periods) if ann_vol > 0 else np.nan
    # mdd
    peak = nav.cummax()
    drawdown = (nav - peak) / peak
    mdd = drawdown.min()
    return {'sharpe': sharpe, 'mdd': mdd, 'CAGR': CAGR,
            'total return': total,'Annualized volatility':ann_vol}


def load_prices(data_dir='data'):
    """Asset-level daily prices written by delisting/load_db.py (one column per asset_id).

    Renames are chained into one column and prices are split-adjusted, so MATIC -> POL or SUN's 1:1000
    redenomination leaves no break. Returns (close, dollar_volume, traded):
    - close: forward-filled through trading halts inside each asset's life (hold through halts), so the
      halt's whole price move lands on the day trading resumes; NaN before listing and after the last trade
    - dollar_volume: daily USDT volume, NaN on days without trading
    - traded: True on days the asset actually traded
    """
    raw = pd.read_csv(f'{data_dir}/asset_close.csv', index_col=0, parse_dates=True)
    dollar_volume = pd.read_csv(f'{data_dir}/asset_dollar_volume.csv', index_col=0, parse_dates=True)
    traded = raw.notna()
    close = raw.ffill(limit_area='inside')
    return close, dollar_volume, traded


def hold_through_halts(w, traded):
    """Keep a position unchanged while its asset is halted.

    w on day t is held from the close of t-1 to the close of t, so it can only change if the asset traded
    on t-1. On halt days, and on the day trading resumes, the weight from the last tradable day is kept.
    """
    can_trade = traded.shift(1, fill_value=False).reindex(index=w.index, columns=w.columns, fill_value=False)
    alive = traded.cummax() & traded[::-1].cummax()[::-1]
    alive = alive.reindex(index=w.index, columns=w.columns, fill_value=False)
    frozen = alive & ~can_trade
    return w.mask(frozen).ffill().where(frozen, w).fillna(0)
