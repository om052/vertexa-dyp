from flask import Flask

from sqlalchemy import event

from app.config import configure_database, load_config, validate_config
from app.extensions import csrf, db, migrate


def _enable_sqlite_foreign_keys(connection, _connection_record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(load_config(app.instance_path))

    if test_config is not None:
        app.config.update(test_config)

    validate_config(app.config)
    configure_database(app)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.auth import account, auth, inject_current_user, load_current_user
    from app.catalog_routes import catalog_api
    from app.cli import seed_curriculum_command
    from app.pages import pages
    from app.routes import web

    app.register_blueprint(auth)
    app.register_blueprint(account)
    app.register_blueprint(web)
    app.register_blueprint(pages)
    app.register_blueprint(catalog_api)
    app.cli.add_command(seed_curriculum_command)
    app.before_request(load_current_user)
    app.context_processor(inject_current_user)
    with app.app_context():
        event.listen(db.engine, "connect", _enable_sqlite_foreign_keys)

    return app
