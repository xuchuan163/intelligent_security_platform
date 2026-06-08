"""Check that the live MySQL schema matches SQLAlchemy ORM table/column names."""

import sys
from pathlib import Path

from sqlalchemy import inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database import models  # noqa: F401,E402
from app.infrastructure.database.session import Base, engine  # noqa: E402


def main() -> int:
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)
    problems: list[str] = []

    for table in sorted(expected_tables - db_tables):
        problems.append(f"missing table: {table}")

    for table in sorted(expected_tables & db_tables):
        expected_columns = {column.name for column in Base.metadata.tables[table].columns}
        db_columns = {column["name"] for column in inspector.get_columns(table)}
        for column in sorted(expected_columns - db_columns):
            problems.append(f"missing column: {table}.{column}")

    if problems:
        print("Schema check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"Schema check passed: {len(expected_tables)} ORM tables match the database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
