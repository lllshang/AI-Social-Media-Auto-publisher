from sqlalchemy import inspect, text

from app.database import engine


def run_migrations() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("materials"):
        return

    columns = {col["name"] for col in inspector.get_columns("materials")}
    statements: list[str] = []
    if "name" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN name VARCHAR(128)")
    if "category" not in columns:
        statements.append("ALTER TABLE materials ADD COLUMN category VARCHAR(64)")

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

    if inspector.has_table("platform_accounts"):
        account_columns = {col["name"] for col in inspector.get_columns("platform_accounts")}
        if "remark" not in account_columns:
            statements.append("ALTER TABLE platform_accounts ADD COLUMN remark VARCHAR(255)")

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

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def run_sqlite_migrations() -> None:
    run_migrations()
