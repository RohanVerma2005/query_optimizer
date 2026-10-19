"""
CREATE DATABASE IF NOT EXISTS qpa_metrics;
USE qpa_metrics;

-- 1. Query Catalog: Stores unique normalized query fingerprints
CREATE TABLE IF NOT EXISTS query_catalog (
    digest_hash VARCHAR(64) PRIMARY KEY,
    schema_name VARCHAR(64) NOT NULL,
    digest_text TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. Snapshots Header: Keeps track of each polling run timestamp
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    server_uptime_sec BIGINT NOT NULL
);

-- 3. Query Delta Metrics: Stores per-interval delta stats for each query
CREATE TABLE IF NOT EXISTS query_interval_stats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_id BIGINT NOT NULL,
    digest_hash VARCHAR(64) NOT NULL,
    interval_seconds INT NOT NULL,
    delta_exec_count BIGINT NOT NULL,
    delta_total_ms DOUBLE NOT NULL,
    avg_latency_ms DOUBLE NOT NULL,
    delta_rows_examined BIGINT NOT NULL,
    delta_rows_sent BIGINT NOT NULL,
    examined_to_sent_ratio DOUBLE NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES metric_snapshots(id) ON DELETE CASCADE,
    FOREIGN KEY (digest_hash) REFERENCES query_catalog(digest_hash) ON DELETE CASCADE,
    INDEX idx_digest_snapshot (digest_hash, snapshot_id)
);

"""