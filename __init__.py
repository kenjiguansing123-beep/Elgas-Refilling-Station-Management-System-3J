"""EL-GAS REST API backend for the Tkinter desktop GUI."""
import os
from flask import Flask, jsonify, request
from . import db
from .api import api_bp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_app(db_path=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("ELGAS_SECRET", "change-this-secret-key")
    app.config["API_KEY"] = os.environ.get("ELGAS_API_KEY", "elgas-demo-key")
    app.config["DB_PATH"] = db_path or os.environ.get("ELGAS_DB", os.path.join(BASE_DIR, "elgas.db"))
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024
    db.init_db(app.config["DB_PATH"])
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="Route not found."), 404

    @app.errorhandler(405)
    def bad_method(_e):
        return jsonify(error="Method not allowed for this route."), 405

    @app.errorhandler(413)
    def too_big(_e):
        return jsonify(error="Request is too large."), 413

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify(error="Something went wrong on the server."), 500

    return app
