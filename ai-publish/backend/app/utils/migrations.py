from sqlalchemy import inspect, text

from app.database import engine


def run_migrations() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("materials"):
        return

    columns = {col["name"] for col in inspector.get_columns("materials")}
    statements: list[str] = []

    if inspector.has_table("avatars"):
        avatar_columns = {col["name"] for col in inspector.get_columns("avatars")}
        if "subject_id" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN subject_id VARCHAR(128)")
    if "name" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN name VARCHAR(128)")
    if "category" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN category VARCHAR(64)")
    if "moderation_status" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN moderation_status VARCHAR(20)")
    if "moderation_detail" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN moderation_detail TEXT")

    if inspector.has_table("publish_tasks"):
        task_columns = {col["name"] for col in inspector.get_columns("publish_tasks")}
        if "comment_guide" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN comment_guide TEXT")
        if "topic" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN topic VARCHAR(256)")
        if "cover_text" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN cover_text VARCHAR(128)")
        if "wizard_step" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN wizard_step INTEGER")
        if "retry_count" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN retry_count INTEGER DEFAULT 0")
        if "next_retry_at" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN next_retry_at DATETIME")
        if "bilibili_tid" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN bilibili_tid INTEGER")
        if "worker_id" not in task_columns:
            statements.append("ALTER TABLE publish_tasks ADD COLUMN worker_id INTEGER")

    if not inspector.has_table("account_groups"):
        statements.append(
            "CREATE TABLE account_groups ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(64) NOT NULL UNIQUE, "
            "remark VARCHAR(255), "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if inspector.has_table("users"):
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "role_id" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN role_id INTEGER")

    if not inspector.has_table("publish_workers"):
        statements.append(
            "CREATE TABLE publish_workers ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(64) NOT NULL UNIQUE, "
            "worker_key VARCHAR(64) NOT NULL UNIQUE, "
            "token_hash VARCHAR(128) NOT NULL, "
            "hostname VARCHAR(128), "
            "last_heartbeat_at DATETIME, "
            "status VARCHAR(20) DEFAULT 'active', "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if inspector.has_table("platform_accounts"):
        account_columns = {col["name"] for col in inspector.get_columns("platform_accounts")}
        if "remark" not in account_columns:
            statements.append("ALTER TABLE platform_accounts ADD COLUMN remark VARCHAR(255)")
        if "worker_id" not in account_columns:
            statements.append("ALTER TABLE platform_accounts ADD COLUMN worker_id INTEGER")
        if "publish_proxy" not in account_columns:
            statements.append("ALTER TABLE platform_accounts ADD COLUMN publish_proxy VARCHAR(512)")

    if not inspector.has_table("review_logs"):
        statements.append(
            "CREATE TABLE review_logs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "task_id INTEGER NOT NULL, "
            "action VARCHAR(20) NOT NULL, "
            "comment TEXT, "
            "reviewer_id INTEGER, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if not inspector.has_table("sensitive_words"):
        statements.append(
            "CREATE TABLE sensitive_words ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "word VARCHAR(128) NOT NULL UNIQUE, "
            "enabled INTEGER DEFAULT 1, "
            "remark VARCHAR(255), "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if not inspector.has_table("content_templates"):
        statements.append(
            "CREATE TABLE content_templates ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(128) NOT NULL, "
            "industry VARCHAR(64) NOT NULL, "
            "platform VARCHAR(32), "
            "content_type VARCHAR(20) DEFAULT 'note', "
            "template_kind VARCHAR(20) DEFAULT 'text', "
            "topic VARCHAR(256) NOT NULL, "
            "title_hint VARCHAR(256), "
            "content_body TEXT, "
            "tags TEXT, "
            "image_style VARCHAR(32), "
            "image_ratio VARCHAR(16), "
            "brand_color VARCHAR(32), "
            "brand_hint VARCHAR(255), "
            "status VARCHAR(20) DEFAULT 'active', "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if not inspector.has_table("trending_fetch_runs"):
        statements.append(
            "CREATE TABLE trending_fetch_runs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "source VARCHAR(32) NOT NULL, "
            "mode VARCHAR(32) NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "item_count INTEGER DEFAULT 0, "
            "error_message TEXT, "
            "started_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "finished_at DATETIME)"
        )

    if not inspector.has_table("trending_items"):
        statements.append(
            "CREATE TABLE trending_items ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "platform VARCHAR(32) NOT NULL, "
            "snapshot_date VARCHAR(10) NOT NULL, "
            "rank INTEGER DEFAULT 0, "
            "title VARCHAR(512) NOT NULL, "
            "tags TEXT, "
            "heat_score NUMERIC(12, 4) DEFAULT 0, "
            "source_url VARCHAR(1024), "
            "cover_url VARCHAR(1024), "
            "video_url VARCHAR(1024), "
            "duration_seconds INTEGER, "
            "aspect_ratio VARCHAR(16), "
            "ref_material_id INTEGER, "
            "first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if not inspector.has_table("avatars"):
        statements.append(
            "CREATE TABLE avatars ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(128) NOT NULL, "
            "type VARCHAR(32) NOT NULL, "
            "gender VARCHAR(16), "
            "config TEXT, "
            "reference_images TEXT, "
            "reference_image_url VARCHAR(1024), "
            "thumbnail VARCHAR(512), "
            "background_prompt TEXT, "
            "background_image_url VARCHAR(1024), "
            "subject_id VARCHAR(128), "
            "status VARCHAR(20) DEFAULT 'active', "
            "created_by INTEGER, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    # 兼容已存在 avatars 表：新增参考视频/参考图字段
    if inspector.has_table("avatars"):
        avatar_columns = {col["name"] for col in inspector.get_columns("avatars")}
        if "reference_video_url" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN reference_video_url VARCHAR(1024)")
        if "reference_image_url" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN reference_image_url VARCHAR(1024)")
        if "background_prompt" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN background_prompt TEXT")
        if "background_image_url" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN background_image_url VARCHAR(1024)")
        if "subject_id" not in avatar_columns:
            statements.append("ALTER TABLE avatars ADD COLUMN subject_id VARCHAR(128)")

    if not inspector.has_table("creative_sessions"):
        statements.append(
            "CREATE TABLE creative_sessions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, "
            "content_type VARCHAR(20) NOT NULL, "
            "keywords TEXT NOT NULL, "
            "background TEXT, "
            "theme_style VARCHAR(100), "
            "scene_desc TEXT, "
            "platforms TEXT, "
            "status VARCHAR(20) DEFAULT 'drafting', "
            "final_copy TEXT, "
            "polish_history TEXT, "
            "output_material_ids TEXT, "
            "draft_data TEXT, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if inspector.has_table("creative_sessions"):
        session_columns = {col["name"] for col in inspector.get_columns("creative_sessions")}
        if "draft_data" not in session_columns:
            statements.append("ALTER TABLE creative_sessions ADD COLUMN draft_data TEXT")

    if not inspector.has_table("generation_tasks"):
        statements.append(
            "CREATE TABLE generation_tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "session_id INTEGER NOT NULL, "
            "gen_type VARCHAR(30) NOT NULL, "
            "provider VARCHAR(50) NOT NULL, "
            "input_params TEXT, "
            "status VARCHAR(20) DEFAULT 'pending', "
            "progress INTEGER DEFAULT 0, "
            "result TEXT, "
            "error_message TEXT, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "completed_at DATETIME)"
        )

    if not inspector.has_table("voice_clone_tasks"):
        statements.append(
            "CREATE TABLE voice_clone_tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR(128) NOT NULL, "
            "task_id VARCHAR(128), "
            "sample_url VARCHAR(1024), "
            "voice_type INTEGER, "
            "status VARCHAR(20) DEFAULT 'pending', "
            "error_message TEXT, "
            "created_by INTEGER, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def run_sqlite_migrations() -> None:
    run_migrations()


def run_universal_migrations() -> None:
    """跨数据库兼容的轻量迁移（仅用于基础列追加）。

    不依赖 run_migrations 内的 SQLite 专属语法（AUTOINCREMENT 等），
    适用于生产环境 MySQL。启动时由 main.py 调用。
    """
    inspector = inspect(engine)
    if not inspector.has_table("avatars"):
        return
    avatar_columns = {col["name"] for col in inspector.get_columns("avatars")}
    statements = []
    if "background_prompt" not in avatar_columns:
        statements.append("ALTER TABLE avatars ADD COLUMN background_prompt TEXT")
    if "background_image_url" not in avatar_columns:
        statements.append("ALTER TABLE avatars ADD COLUMN background_image_url VARCHAR(1024)")
    if not statements:
        return
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
