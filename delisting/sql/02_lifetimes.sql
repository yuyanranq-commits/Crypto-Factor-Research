CREATE OR REPLACE TABLE lifetimes AS
with stats as (
       select symbol,
              min(ts) as first_date,
              max(ts) as last_date,
              count(*) as n_days,
              arg_min(close, ts) as first_close,
              arg_max(close,ts) as last_close
       from prices
       group by symbol
),
base as (
       SELECT
       s.symbol,
       s.first_date,
       s.last_date,
       s.n_days,
       s.first_close,
       s.last_close,
       date_diff('day', s.last_date, w.sample_end) >= 30 AS stopped,
       s.first_date = w.sample_start AS left_truncated,
       CASE
           WHEN e.exit_type IS NOT NULL THEN e.exit_type
           WHEN date_diff('day', s.last_date, w.sample_end) >= 30 THEN 'unlabeled'
           ELSE 'active'
       END AS exit_type,
       e.delist_scope,
       e.successor,
       e.needs_review,
       e.announcement_date,
       -- exit_date: the day the asset leaves the risk set. Delistings end at the announcement,
       -- or at last_date if trading stopped first (or no notice was found); all else at last_date.
       CASE WHEN e.exit_type = 'delisting' THEN LEAST(COALESCE(e.announcement_date, s.last_date), s.last_date)
            ELSE s.last_date END AS exit_date
    FROM stats s
    CROSS JOIN sample_window w
    LEFT JOIN exit_labels e ON s.symbol = e.symbol
)
SELECT
    b.*,
    a.asset_id,
    r.first_date     AS asset_first_date,
    r.left_truncated AS asset_left_truncated
FROM base b
JOIN assets a ON b.symbol = a.symbol
JOIN base r   ON r.symbol = a.asset_id

