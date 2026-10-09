import numpy as np
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
