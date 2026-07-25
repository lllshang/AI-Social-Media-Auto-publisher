-- Trending inspiration tables (MySQL)
CREATE TABLE IF NOT EXISTS trending_fetch_runs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL,
    item_count INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS trending_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    snapshot_date VARCHAR(10) NOT NULL,
    rank INT NOT NULL DEFAULT 0,
    title VARCHAR(512) NOT NULL,
    tags JSON NULL,
    heat_score DECIMAL(12, 4) NOT NULL DEFAULT 0,
    source_url VARCHAR(1024) NULL,
    cover_url VARCHAR(1024) NULL,
    video_url VARCHAR(1024) NULL,
    duration_seconds INT NULL,
    aspect_ratio VARCHAR(16) NULL,
    ref_material_id BIGINT NULL,
    first_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trending_platform_date (platform, snapshot_date)
) ENGINE=InnoDB;
