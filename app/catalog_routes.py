import re

from flask import Blueprint, abort, jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import Language, Lesson, Topic


catalog_api = Blueprint("catalog_api", __name__, url_prefix="/api")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_slug(value):
    if not SLUG_PATTERN.fullmatch(value):
        abort(404)


def _lesson_json(lesson):
    return {
        "slug": lesson.slug,
        "title": lesson.title,
        "description": lesson.description,
        "position": lesson.position,
        "content": lesson.content,
        "prerequisites": [
            {
                "topic_slug": prerequisite.topic.slug,
                "lesson_slug": prerequisite.slug,
            }
            for prerequisite in lesson.prerequisites
        ],
    }


@catalog_api.errorhandler(404)
def not_found(_error):
    return (
        jsonify(
            error={
                "code": "not_found",
                "message": "The requested curriculum item was not found.",
            }
        ),
        404,
    )


@catalog_api.get("/languages")
def list_languages():
    rows = db.session.execute(
        select(
            Language,
            func.count(func.distinct(Topic.id)).label("topic_count"),
            func.count(Lesson.id).label("lesson_count"),
        )
        .outerjoin(Topic, Topic.language_code == Language.code)
        .outerjoin(Lesson, Lesson.topic_id == Topic.id)
        .group_by(Language.code)
        .order_by(Language.position, Language.code)
    ).all()
    return jsonify(
        languages=[
            {
                "slug": language.code,
                "name": language.name,
                "description": language.description,
                "topic_count": topic_count,
                "lesson_count": lesson_count,
            }
            for language, topic_count, lesson_count in rows
        ]
    )


@catalog_api.get("/languages/<language_code>")
def get_language(language_code):
    _validate_slug(language_code)
    language = db.session.scalar(
        select(Language)
        .options(selectinload(Language.topics))
        .where(Language.code == language_code)
    )
    if language is None:
        abort(404)

    lesson_counts = dict(
        db.session.execute(
            select(Topic.id, func.count(Lesson.id))
            .outerjoin(Lesson, Lesson.topic_id == Topic.id)
            .where(Topic.language_code == language_code)
            .group_by(Topic.id)
        ).all()
    )
    return jsonify(
        language={
            "slug": language.code,
            "name": language.name,
            "description": language.description,
            "topic_count": len(language.topics),
            "lesson_count": sum(lesson_counts.values()),
            "topics": [
                {
                    "slug": topic.slug,
                    "title": topic.title,
                    "description": topic.description,
                    "position": topic.position,
                    "difficulty": topic.difficulty,
                    "lesson_count": lesson_counts.get(topic.id, 0),
                }
                for topic in language.topics
            ],
        }
    )


@catalog_api.get("/languages/<language_code>/topics/<topic_slug>")
def get_topic(language_code, topic_slug):
    _validate_slug(language_code)
    _validate_slug(topic_slug)
    topic = db.session.scalar(
        select(Topic)
        .options(
            joinedload(Topic.language),
            selectinload(Topic.lessons)
            .selectinload(Lesson.prerequisites)
            .joinedload(Lesson.topic),
        )
        .where(
            Topic.language_code == language_code,
            Topic.slug == topic_slug,
        )
    )
    if topic is None:
        abort(404)

    return jsonify(
        topic={
            "slug": topic.slug,
            "title": topic.title,
            "description": topic.description,
            "position": topic.position,
            "difficulty": topic.difficulty,
            "language": {
                "slug": topic.language.code,
                "name": topic.language.name,
            },
            "lessons": [_lesson_json(lesson) for lesson in topic.lessons],
        }
    )


@catalog_api.get(
    "/languages/<language_code>/topics/<topic_slug>/lessons/<lesson_slug>"
)
def get_lesson(language_code, topic_slug, lesson_slug):
    _validate_slug(language_code)
    _validate_slug(topic_slug)
    _validate_slug(lesson_slug)
    lesson = db.session.scalar(
        select(Lesson)
        .join(Lesson.topic)
        .options(
            joinedload(Lesson.topic).joinedload(Topic.language),
            selectinload(Lesson.prerequisites).joinedload(Lesson.topic),
        )
        .where(
            Topic.language_code == language_code,
            Topic.slug == topic_slug,
            Lesson.slug == lesson_slug,
        )
    )
    if lesson is None:
        abort(404)

    return jsonify(
        lesson={
            **_lesson_json(lesson),
            "topic_slug": lesson.topic.slug,
            "language_slug": lesson.topic.language.code,
        }
    )
