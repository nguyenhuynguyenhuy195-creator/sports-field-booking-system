from __future__ import annotations

from typing import Any

from app.extensions import db


def with_update_lock(statement: Any, entity: Any):
    """Apply a real update lock on SQL Server and a row lock elsewhere."""
    bind = db.session.get_bind()
    if bind.dialect.name == "mssql":
        return statement.with_hint(
            entity,
            "WITH (UPDLOCK, HOLDLOCK)",
            dialect_name="mssql",
        )
    return statement.with_for_update()
