from flask import Blueprint, jsonify, render_template


web = Blueprint("web", __name__)


@web.get("/")
def home():
    return render_template("index.html", page="home")


@web.get("/health")
def health():
    return jsonify(status="ok")


@web.app_errorhandler(404)
def page_not_found(_error):
    return render_template("404.html"), 404
