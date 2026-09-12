from flask_migrate import upgrade
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db


def test_empty_database_upgrades_to_head_and_matches_models():
    application = create_app("testing")
    with application.app_context():
        upgrade(directory="migrations")
        with db.engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "d4b7e1c9a802"
            assert set(inspect(connection).get_table_names()) == set(db.metadata.tables) | {"alembic_version"}
            assert compare_metadata(MigrationContext.configure(connection), db.metadata) == []
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        db.session.remove()
        db.engine.dispose()
