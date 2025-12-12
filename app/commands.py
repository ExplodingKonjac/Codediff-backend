import click
from datetime import datetime, timezone
from flask.cli import with_appcontext
from app.extensions import db
from app.models import VerificationCode

@click.command('clean-codes')
@with_appcontext
def clean_codes_command():
    """Remove used and expired verification codes."""
    now = datetime.now(timezone.utc)
    
    # Logic: Delete if used=True OR expires_at < now
    # We can do this in one SQL delete statement for efficiency
    
    deleted_count = VerificationCode.query.filter(
        (VerificationCode.used == True) | (VerificationCode.expires_at < now)
    ).delete()
    
    db.session.commit()
    
    click.echo(f"Cleaned up {deleted_count} verification codes.")

def register_commands(app):
    app.cli.add_command(clean_codes_command)
