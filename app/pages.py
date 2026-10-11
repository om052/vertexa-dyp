from flask import Blueprint, abort, render_template
from sqlalchemy import select
from app.extensions import db
from app.models import Language, Lesson, Topic


pages = Blueprint("pages", __name__)


@pages.get("/learn")
def learn():
    return render_template("learn.html", page="learn")


@pages.get("/learn/<language_code>")
def roadmap(language_code):
    language = db.session.get(Language, language_code)
    if language is None:
        abort(404)
    return render_template(
        "roadmap.html",
        page="roadmap",
        language_code=language_code,
    )


@pages.get("/learn/<language_code>/topics/<topic_slug>")
def topic_page(language_code, topic_slug):
    topic = db.session.scalar(
        select(Topic.id).where(
            Topic.language_code == language_code,
            Topic.slug == topic_slug,
        )
    )
    if topic is None:
        abort(404)
    return render_template(
        "topic.html",
        page="topic",
        language_code=language_code,
        topic_slug=topic_slug,
    )


@pages.get(
    "/learn/<language_code>/topics/<topic_slug>/lessons/<lesson_slug>"
)
def lesson_page(language_code, topic_slug, lesson_slug):
    lesson = db.session.scalar(
        select(Lesson.id)
        .join(Lesson.topic)
        .where(
            Topic.language_code == language_code,
            Topic.slug == topic_slug,
            Lesson.slug == lesson_slug,
        )
    )
    if lesson is None:
        abort(404)
    return render_template(
        "lesson.html",
        page="lesson",
        language_code=language_code,
        topic_slug=topic_slug,
        lesson_slug=lesson_slug,
    )
