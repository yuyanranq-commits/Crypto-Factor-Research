CREATE OR REPLACE TABLE panel AS
WITH months AS (
       --For each coin, generate a row for every month from the month after its listing date to its exit month
       --(the announcement month for delistings, the last trading month otherwise).
    SELECT
        l.symbol,
        l.asset_id,
        l.exit_type,
        l.delist_scope,
        l.last_date,
        l.exit_date,
        l.asset_first_date,
        l.asset_left_truncated AS left_truncated,
        CAST(g.m AS DATE) AS month_start
    FROM lifetimes l,
         generate_series(date_trunc('month', l.first_date) + INTERVAL 1 MONTH,
                         date_trunc('month', l.exit_date),
                         INTERVAL 1 MONTH) AS g(m)
),
cutoffs AS (
       --Feature cutoffs (month start, and 30 days earlier) and the end of the interval.
    SELECT
        *,
        month_start                                   AS cut0,
        CAST(month_start - INTERVAL 30 DAY AS DATE)   AS cut30,
        CAST(LEAST(month_start + INTERVAL 1 MONTH,
                   exit_date   + INTERVAL 1 DAY) AS DATE) AS interval_end
    FROM months
),
f0 AS (
       --The asset's last trading day features strictly before cut0 (any of its tickers)
    SELECT c.symbol, c.month_start, d.dv30, d.dv180, d.vol30, d.ret90, d.drawdown, d.n_obs30
    FROM cutoffs c
    ASOF LEFT JOIN daily d
      ON c.asset_id = d.asset_id AND c.cut0 > d.ts
),
f30 AS (
       --The asset's last trading day features strictly before cut30 (any of its tickers)
    SELECT c.symbol, c.month_start, d.dv30, d.dv180, d.vol30, d.ret90, d.drawdown, d.n_obs30
    FROM cutoffs c
    ASOF LEFT JOIN daily d
      ON c.asset_id = d.asset_id AND c.cut30 > d.ts
)
       --gather together
SELECT
    c.symbol,
    c.asset_id,
    c.month_start,
    c.exit_type,
    c.left_truncated,
    date_diff('day', c.asset_first_date, c.month_start)  AS start_age,
    date_diff('day', c.asset_first_date, c.interval_end) AS stop_age,
    date_diff('day', w.sample_start, c.month_start)      AS start_cal,
    date_diff('day', w.sample_start, c.interval_end)     AS stop_cal,
    -- any_delisting: a delisting (token or USDT pair) was announced this month; used in robustness checks
    (c.exit_type = 'delisting' AND date_trunc('month', c.exit_date) = c.month_start) AS any_delisting,
    -- event: a token delisting was announced this month
    (c.exit_type = 'delisting' AND c.delist_scope = 'token'
        AND date_trunc('month', c.exit_date) = c.month_start) AS event,
    ln(f0.dv30  + 1)                     AS log_dv30_lag0,
    ln(f30.dv30 + 1)                     AS log_dv30_lag30,
    ln((f0.dv30  + 1) / (f0.dv180  + 1)) AS dv_trend_lag0,
    ln((f30.dv30 + 1) / (f30.dv180 + 1)) AS dv_trend_lag30,
    f0.vol30     AS vol30_lag0,     f30.vol30     AS vol30_lag30,
    f0.ret90     AS ret90_lag0,     f30.ret90     AS ret90_lag30,
    f0.drawdown  AS drawdown_lag0,  f30.drawdown  AS drawdown_lag30,
    f0.n_obs30   AS n_obs30_lag0,   f30.n_obs30   AS n_obs30_lag30
FROM cutoffs c
CROSS JOIN sample_window w
JOIN f0  ON f0.symbol  = c.symbol AND f0.month_start  = c.month_start
JOIN f30 ON f30.symbol = c.symbol AND f30.month_start = c.month_start;