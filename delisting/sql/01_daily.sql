CREATE OR REPLACE TABLE daily AS
-- Features are computed per asset, not per ticker, so a rename does not reset them.
-- adj_close is the price per root token (split-adjusted with swap_ratio); dollar volume needs no adjustment.
with px as (
    select
       p.symbol,
       a.asset_id,
       p.ts,
       p.close,
       p.volume,
       p.close * a.adj_factor as adj_close,
       p.close * p.volume as dollar_volume
    from prices p
    join assets a on p.symbol = a.symbol
),
base as (
    select
       *,
       -- daily log return; NULL across a gap of more than 7 days (the same max_gap as dataclean.py)
       case when date_diff('day', lag(ts) over (partition by asset_id order by ts), ts) <= 7
            then ln(adj_close / lag(adj_close) over (partition by asset_id order by ts))
       end as log_ret,
       adj_close / max(adj_close) over (partition by asset_id order by ts
                                        rows between unbounded preceding and current row) - 1 as drawdown
    from px
)
SELECT
    symbol,
    asset_id,
    ts,
    close,
    adj_close,
    volume,
    dollar_volume,
    log_ret,
    drawdown,
    avg(dollar_volume) over w30 as dv30,
    avg(dollar_volume) over w180 as dv180,
    stddev_samp(log_ret) over w30 as vol30,
    sum(log_ret) over w90 as ret90,
    count(*) over w30 as n_obs30
from base
window
    w30  AS (PARTITION BY asset_id ORDER BY ts RANGE BETWEEN INTERVAL 29 DAYS  PRECEDING AND CURRENT ROW),
    w90  AS (PARTITION BY asset_id ORDER BY ts RANGE BETWEEN INTERVAL 89 DAYS  PRECEDING AND CURRENT ROW),
    w180 AS (PARTITION BY asset_id ORDER BY ts RANGE BETWEEN INTERVAL 179 DAYS PRECEDING AND CURRENT ROW);
