import click
from flask.cli import with_appcontext

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
