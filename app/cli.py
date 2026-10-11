import click
from flask.cli import with_appcontext

from app.services.buddy_retention import purge_expired_conversations
from app.services.curriculum import CurriculumSeedError, seed_curriculum


@click.command("seed-curriculum")
@with_appcontext
def seed_curriculum_command():
    """Load missing starter lessons without overwriting existing content."""
    try:
        counts = seed_curriculum()
    except CurriculumSeedError as error:
        raise click.ClickException(str(error)) from error

    click.echo(
        "Curriculum ready. "
        f"Created {counts['languages']} languages, "
        f"{counts['topics']} topics, and {counts['lessons']} lessons."
    )


@click.command("purge-buddy-conversations")
@with_appcontext
def purge_buddy_conversations_command():
    """Delete saved Buddy conversations whose retention period has elapsed."""
    deleted_count = purge_expired_conversations()
    click.echo(f"Purged {deleted_count} expired Buddy conversations.")
