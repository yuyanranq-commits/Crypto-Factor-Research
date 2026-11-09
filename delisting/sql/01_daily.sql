CREATE OR REPLACE TABLE daily AS
with base as (
    select
       symbol,
       ts,
       close,
       volume,
       close*volume as dollar_volume,
       ln(close / lag(close) over (partition by symbol order by ts)) as log_ret,
        close /max(close) OVER (partition by symbol order by ts
                                 rows between unbounded preceding and current row) - 1 as drawdown
    from prices
)
SELECT
    symbol,
    ts,
    close,
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
    w30  AS (PARTITION BY symbol ORDER BY ts RANGE BETWEEN INTERVAL 29 DAYS  PRECEDING AND CURRENT ROW),
    w90  AS (PARTITION BY symbol ORDER BY ts RANGE BETWEEN INTERVAL 89 DAYS  PRECEDING AND CURRENT ROW),
    w180 AS (PARTITION BY symbol ORDER BY ts RANGE BETWEEN INTERVAL 179 DAYS PRECEDING AND CURRENT ROW);
