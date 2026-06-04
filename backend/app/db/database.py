# ============================================================
# app/db/database.py — SQLAlchemy Session + Engine
# ============================================================
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    # SQLite needs this; remove for PostgreSQL
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _sqlite_column_type(column) -> str:
    try:
        python_type = column.type.python_type
    except Exception:
        python_type = None

    if python_type is bool:
        return "BOOLEAN"
    if python_type is int:
        return "INTEGER"
    if python_type is float:
        return "FLOAT"
    return "TEXT"


def sync_sqlite_schema(base: DeclarativeBase) -> None:
    if "sqlite" not in settings.DATABASE_URL:
        return

    inspector = inspect(engine)

    with engine.begin() as conn:
        for table_name, model_table in base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue

            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for column in model_table.columns:
                if column.name in existing_cols:
                    continue

                col_type = _sqlite_column_type(column)
                nullable_sql = "" if column.nullable else " NOT NULL"
                default_sql = ""

                if column.default is not None and getattr(column.default, "is_scalar", False):
                    value = column.default.arg
                    if isinstance(value, str):
                        default_sql = f" DEFAULT '{value}'"
                    elif isinstance(value, bool):
                        default_sql = f" DEFAULT {1 if value else 0}"
                    elif value is not None:
                        default_sql = f" DEFAULT {value}"

                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{nullable_sql}{default_sql}"
                    )
                )


def get_db():
    """FastAPI dependency — yields a DB session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
