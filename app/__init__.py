"""
Scanwave CyberIntel Platform — Application Factory
====================================================
"""


def create_app():
    """Create and configure the Flask application."""
    from flask import Flask
    from . import config

    app = Flask(__name__,
                static_folder="static",
                static_url_path="/static")

    # Store config on app for access in blueprints
    app.config["DATA_DIR"] = config.DATA_DIR
    app.config["DB_PATH"] = config.DB_PATH

    # Initialize database
    from .database import init_db
    init_db(config.DB_PATH)

    # Register blueprints (added incrementally in Phase 3)
    # from .routes.dashboard import bp as dashboard_bp
    # app.register_blueprint(dashboard_bp)

    return app
