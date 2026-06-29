-- ============================================================
--  MarketPulse — ClickHouse Schema
--  Engine: MergeTree family for time-series optimisation
-- ============================================================

-- Raw tick data: one row per asset per ingestion cycle
CREATE TABLE IF NOT EXISTS market_ticks
(
    asset       LowCardinality(String),   -- BTC, ETH, SOL, BNB
    ts          DateTime64(3, 'UTC'),     -- millisecond precision
    open        Float64,
    high        Float64,
    low         Float64,
    close       Float64,
    volume_24h  Float64,
    market_cap  Float64,
    inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)          -- monthly partitions
ORDER BY (asset, ts)               -- primary sort: asset then time
TTL ts + INTERVAL 2 YEAR          -- auto-expire data older than 2 years
SETTINGS index_granularity = 8192;


-- Materialised view: pre-aggregate 1-minute candles
-- ClickHouse computes this at insert time — zero query-time cost
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1m
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(ts_bucket)
ORDER BY (asset, ts_bucket)
AS
SELECT
    asset,
    toStartOfMinute(ts)              AS ts_bucket,
    argMinState(open, ts)            AS open,
    maxState(high)                   AS high,
    minState(low)                    AS low,
    argMaxState(close, ts)           AS close,
    sumState(volume_24h)             AS volume
FROM market_ticks
GROUP BY asset, ts_bucket;


-- Query helper view: resolve AggregatingMergeTree states to final values
CREATE VIEW IF NOT EXISTS candles_1m_final AS
SELECT
    asset,
    ts_bucket,
    argMinMerge(open)   AS open,
    maxMerge(high)      AS high,
    minMerge(low)       AS low,
    argMaxMerge(close)  AS close,
    sumMerge(volume)    AS volume
FROM candles_1m
GROUP BY asset, ts_bucket
ORDER BY asset, ts_bucket;
