-- AI Publish MVP schema
CREATE DATABASE IF NOT EXISTS aipublish DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aipublish;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id BIGINT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(64) NOT NULL UNIQUE,
    permissions JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS account_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS platform_accounts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    account_name VARCHAR(128) NOT NULL,
    remark VARCHAR(255) NULL,
    group_id BIGINT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'inactive',
    created_by BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_platform_account (platform, account_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS account_cookies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id BIGINT NOT NULL,
    cookie_data TEXT NOT NULL,
    expire_time DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_account_id (account_id),
    CONSTRAINT fk_cookie_account FOREIGN KEY (account_id) REFERENCES platform_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS materials (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'upload',
    file_path VARCHAR(512) NOT NULL,
    thumbnail VARCHAR(512) NULL,
    url VARCHAR(512) NULL,
    name VARCHAR(128) NULL,
    category VARCHAR(64) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    moderation_status VARCHAR(20) NULL,
    moderation_detail TEXT NULL,
    ai_record_id BIGINT NULL,
    created_by BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ai_generation_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    prompt TEXT NOT NULL,
    result_summary TEXT NULL,
    cost DECIMAL(10, 4) NOT NULL DEFAULT 0,
    created_by BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS publish_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    content TEXT NULL,
    comment_guide TEXT NULL,
    topic VARCHAR(256) NULL,
    cover_text VARCHAR(128) NULL,
    wizard_step INT NULL,
    bilibili_tid INT NULL,
    tags JSON NULL,
    platform VARCHAR(32) NOT NULL,
    account_id BIGINT NOT NULL,
    content_type VARCHAR(20) NOT NULL DEFAULT 'note',
    material_ids JSON NULL,
    publish_time DATETIME NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    error_message TEXT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    next_retry_at DATETIME NULL,
    created_by BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_task_account FOREIGN KEY (account_id) REFERENCES platform_accounts(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS review_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    action VARCHAR(20) NOT NULL,
    comment TEXT NULL,
    reviewer_id BIGINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_review_task_id (task_id),
    CONSTRAINT fk_review_task FOREIGN KEY (task_id) REFERENCES publish_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS publish_task_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id BIGINT NOT NULL,
    step VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    CONSTRAINT fk_log_task FOREIGN KEY (task_id) REFERENCES publish_tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL UNIQUE,
    config_value TEXT NULL,
    remark VARCHAR(255) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS operation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64) NULL,
    target_id BIGINT NULL,
    ip VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sensitive_words (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(128) NOT NULL UNIQUE,
    enabled TINYINT(1) NOT NULL DEFAULT 1,
    remark VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS content_templates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    industry VARCHAR(64) NOT NULL,
    platform VARCHAR(32) NULL,
    content_type VARCHAR(20) NOT NULL DEFAULT 'note',
    template_kind VARCHAR(20) NOT NULL DEFAULT 'text',
    topic VARCHAR(256) NOT NULL,
    title_hint VARCHAR(256) NULL,
    content_body TEXT NULL,
    tags JSON NULL,
    image_style VARCHAR(32) NULL,
    image_ratio VARCHAR(16) NULL,
    brand_color VARCHAR(32) NULL,
    brand_hint VARCHAR(255) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO roles (role_name, permissions)
SELECT 'admin', JSON_ARRAY('*')
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name = 'admin');

INSERT INTO roles (role_name, permissions)
SELECT 'operator', JSON_ARRAY(
    'dashboard:read','accounts:read','accounts:write','materials:read','materials:write',
    'tasks:read','tasks:write','tasks:execute','publish:write','models:read','models:write','logs:read',
    'templates:read','templates:write'
)
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name = 'operator');

INSERT INTO roles (role_name, permissions)
SELECT 'viewer', JSON_ARRAY(
    'dashboard:read','accounts:read','materials:read','tasks:read','models:read','logs:read','templates:read'
)
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role_name = 'viewer');

-- Seed default users (bcrypt); passwords: admin123 / operator123 / viewer123
INSERT INTO users (username, password_hash, role_id, status)
SELECT 'admin', '$2b$12$sI7NNNo/ivmtH/cVuav7yeneRsXY7KHmv/iYB8IPGoJCRriShdRe6', r.id, 'active'
FROM roles r
WHERE r.role_name = 'admin'
  AND NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, password_hash, role_id, status)
SELECT 'operator', '$2b$12$MmJpD3IB/Y2ZteE51NKayOnc9F3jiKBlMsh/qmHqrlueCZPqZ0382', r.id, 'active'
FROM roles r
WHERE r.role_name = 'operator'
  AND NOT EXISTS (SELECT 1 FROM users WHERE username = 'operator');

INSERT INTO users (username, password_hash, role_id, status)
SELECT 'viewer', '$2b$12$1szlK/qd3qusygb/ovtkiONSReORkrg1mw0MSY77dHqMBnlz1ILSy', r.id, 'active'
FROM roles r
WHERE r.role_name = 'viewer'
  AND NOT EXISTS (SELECT 1 FROM users WHERE username = 'viewer');
