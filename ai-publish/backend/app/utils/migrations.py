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

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def run_sqlite_migrations() -> None:
    run_migrations()
