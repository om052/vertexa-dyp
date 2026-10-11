import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.curriculum_data import CURRICULUM
from app.extensions import db
from app.models import Language, Lesson, Topic


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIFFICULTIES = {"beginner", "intermediate", "advanced"}


class CurriculumSeedError(Exception):
    """A catalog is invalid or conflicts with existing curriculum data."""


def validate_catalog(catalog=CURRICULUM) -> None:
    languages = {}
    language_positions = set()
    lesson_keys = set()
    lesson_positions = {}
    prerequisite_map = {}

    for language in catalog:
        code = language["code"]
        if not SLUG_PATTERN.fullmatch(code):
            raise CurriculumSeedError(f"Invalid language slug: {code!r}.")
        if code in languages:
            raise CurriculumSeedError(f"Duplicate language slug: {code!r}.")
        if not language["name"].strip() or not language["description"].strip():
            raise CurriculumSeedError(
                f"Language {code!r} must have a name and description."
            )
        position = language["position"]
        if not isinstance(position, int) or position < 0:
            raise CurriculumSeedError(
                f"Language {code!r} has an invalid position."
            )
        if position in language_positions:
            raise CurriculumSeedError(
                f"Duplicate language ordering position: {position}."
            )
        language_positions.add(position)
        languages[code] = language

        topic_slugs = set()
        topic_positions = set()
        language_lesson_count = 0
        for topic_position, topic in enumerate(language["topics"]):
            slug, title, description, difficulty = (
                topic[0],
                topic[1],
                topic[2],
                topic[3],
            )
            lessons = (topic[4:8],)
            if not SLUG_PATTERN.fullmatch(slug):
                raise CurriculumSeedError(
                    f"Invalid topic slug in {code!r}: {slug!r}."
                )
            if slug in topic_slugs:
                raise CurriculumSeedError(
                    f"Duplicate topic slug in {code!r}: {slug!r}."
                )
            topic_slugs.add(slug)
            if not title.strip() or not description.strip():
                raise CurriculumSeedError(
                    f"Topic {code}/{slug} needs a title and description."
                )
            if difficulty not in DIFFICULTIES:
                raise CurriculumSeedError(
                    f"Topic {code}/{slug} has an unsupported difficulty."
                )
            if topic_position in topic_positions:
                raise CurriculumSeedError(
                    f"Duplicate topic ordering position in {code!r}."
                )
            topic_positions.add(topic_position)

            for lesson_position, lesson in enumerate(lessons):
                lesson_title, lesson_description, content, prerequisite = lesson
                lesson_slug = slug
                key = (code, slug, lesson_slug)
                if key in lesson_keys:
                    raise CurriculumSeedError(
                        f"Duplicate lesson key: {code}/{slug}/{lesson_slug}."
                    )
                if not lesson_title.strip() or not lesson_description.strip():
                    raise CurriculumSeedError(
                        f"Lesson {code}/{slug}/{lesson_slug} needs a title "
                        "and description."
                    )
                if not content.strip():
                    raise CurriculumSeedError(
                        f"Lesson {code}/{slug}/{lesson_slug} has no content."
                    )
                lesson_keys.add(key)
                lesson_positions[key] = (topic_position, lesson_position)
                language_lesson_count += 1
                prerequisite_map[key] = prerequisite

        if not 8 <= language_lesson_count <= 12:
            raise CurriculumSeedError(
                f"Language {code!r} must have 8 to 12 starter lessons; "
                f"found {language_lesson_count}."
            )

    if len(languages) != 4:
        raise CurriculumSeedError(
            f"The starter catalog must contain exactly four languages; "
            f"found {len(languages)}."
        )

    graph = {}
    for key, prerequisite in prerequisite_map.items():
        if prerequisite is None:
            graph[key] = ()
            continue
        if (
            not isinstance(prerequisite, tuple)
            or len(prerequisite) != 2
            or not all(SLUG_PATTERN.fullmatch(part) for part in prerequisite)
        ):
            raise CurriculumSeedError(
                f"Lesson {key[0]}/{key[1]}/{key[2]} has an invalid prerequisite."
            )
        prerequisite_key = (key[0], prerequisite[0], prerequisite[1])
        if prerequisite_key not in lesson_keys:
            raise CurriculumSeedError(
                f"Lesson {key[0]}/{key[1]}/{key[2]} references missing "
                f"prerequisite {prerequisite[0]}/{prerequisite[1]}."
            )
        graph[key] = (prerequisite_key,)

    visiting = set()
    visited = set()

    def visit(key):
        if key in visiting:
            raise CurriculumSeedError(
                f"Circular lesson prerequisite detected at "
                f"{key[0]}/{key[1]}/{key[2]}."
            )
        if key in visited:
            return
        visiting.add(key)
        for prerequisite_key in graph[key]:
            visit(prerequisite_key)
        visiting.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)

    for key, prerequisite_keys in graph.items():
        for prerequisite_key in prerequisite_keys:
            if lesson_positions[prerequisite_key] >= lesson_positions[key]:
                raise CurriculumSeedError(
                    f"Prerequisite {prerequisite_key[1]}/{prerequisite_key[2]} "
                    f"must appear before {key[1]}/{key[2]}."
                )


def _language_matches(language, expected):
    return (
        language.name == expected["name"]
        and language.description == expected["description"]
        and language.position == expected["position"]
    )


def _topic_matches(topic, expected, position):
    return (
        topic.title == expected[1]
        and topic.description == expected[2]
        and topic.difficulty == expected[3]
        and topic.position == position
    )


def _lesson_matches(lesson, expected, position, prerequisite_keys):
    current_prerequisite_keys = {
        (
            prerequisite.topic.language_code,
            prerequisite.topic.slug,
            prerequisite.slug,
        )
        for prerequisite in lesson.prerequisites
    }
    return (
        lesson.title == expected[0]
        and lesson.description == expected[1]
        and lesson.content == expected[2]
        and lesson.position == position
        and current_prerequisite_keys == set(prerequisite_keys)
    )


def seed_curriculum(catalog=CURRICULUM) -> dict:
    """Create missing starter records; refuse to overwrite conflicting records."""
    validate_catalog(catalog)
    counts = {"languages": 0, "topics": 0, "lessons": 0}
    topic_records = {}
    lesson_records = {}
    session = db.session()

    try:
        transaction = (
            session.begin_nested()
            if session.in_transaction()
            else session.begin()
        )
        with transaction:
            for language_data in catalog:
                language = db.session.get(Language, language_data["code"])
                if language is None:
                    language = Language(
                        code=language_data["code"],
                        name=language_data["name"],
                        description=language_data["description"],
                        position=language_data["position"],
                    )
                    db.session.add(language)
                    counts["languages"] += 1
                elif not _language_matches(language, language_data):
                    raise CurriculumSeedError(
                        f"Existing language {language_data['code']!r} differs "
                        "from the starter catalog; no records were changed."
                    )

            for language_data in catalog:
                language_code = language_data["code"]
                for topic_position, topic_data in enumerate(language_data["topics"]):
                    slug = topic_data[0]
                    topic = db.session.scalar(
                        select(Topic).where(
                            Topic.language_code == language_code,
                            Topic.slug == slug,
                        )
                    )
                    if topic is None:
                        topic = Topic(
                            language_code=language_code,
                            slug=slug,
                            title=topic_data[1],
                            description=topic_data[2],
                            difficulty=topic_data[3],
                            position=topic_position,
                        )
                        db.session.add(topic)
                        counts["topics"] += 1
                    elif not _topic_matches(topic, topic_data, topic_position):
                        raise CurriculumSeedError(
                            f"Existing topic {language_code}/{slug} differs "
                            "from the starter catalog; no records were changed."
                        )
                    topic_records[(language_code, slug)] = topic

            db.session.flush()
            existing_lessons = db.session.scalars(
                select(Lesson)
                .options(
                    joinedload(Lesson.topic),
                    selectinload(Lesson.prerequisites).joinedload(Lesson.topic),
                )
                .where(
                    Lesson.topic_id.in_(
                        [topic.id for topic in topic_records.values()]
                    )
                )
            ).all()
            lesson_records.update(
                {
                    (
                        lesson.topic.language_code,
                        lesson.topic.slug,
                        lesson.slug,
                    ): lesson
                    for lesson in existing_lessons
                }
            )

            for language_data in catalog:
                language_code = language_data["code"]
                for topic_data in language_data["topics"]:
                    topic_slug = topic_data[0]
                    topic = topic_records[(language_code, topic_slug)]
                    for lesson_position, lesson_data in enumerate(
                        (topic_data[4:8],)
                    ):
                        lesson_slug = topic_slug
                        key = (language_code, topic_slug, lesson_slug)
                        prerequisite = lesson_data[3]
                        prerequisite_keys = (
                            ()
                            if prerequisite is None
                            else ((language_code, prerequisite[0], prerequisite[1]),)
                        )
                        prerequisite_records = [
                            lesson_records[prerequisite_key]
                            for prerequisite_key in prerequisite_keys
                        ]
                        lesson = lesson_records.get(key)
                        if lesson is None:
                            lesson = Lesson(
                                topic=topic,
                                slug=lesson_slug,
                                title=lesson_data[0],
                                description=lesson_data[1],
                                content=lesson_data[2],
                                position=lesson_position,
                                prerequisites=prerequisite_records,
                            )
                            db.session.add(lesson)
                            db.session.flush()
                            counts["lessons"] += 1
                        elif not _lesson_matches(
                            lesson,
                            lesson_data,
                            lesson_position,
                            prerequisite_keys,
                        ):
                            raise CurriculumSeedError(
                                f"Existing lesson {language_code}/{topic_slug}/"
                                f"{lesson_slug} differs from the starter catalog; "
                                "no records were changed."
                            )
                        lesson_records[key] = lesson
    except IntegrityError as error:
        raise CurriculumSeedError(
            "The database rejected the starter curriculum. Check existing "
            "content and constraints; the transaction was rolled back."
        ) from error

    return counts
