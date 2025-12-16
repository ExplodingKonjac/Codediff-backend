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
    
    deleted_count = VerificationCode.query.filter(
        (VerificationCode.used == True) | (VerificationCode.expires_at < now)
    ).delete()
    
    db.session.commit()
    
    click.echo(f"Cleaned up {deleted_count} verification codes.")

@click.command('init-db')
@click.option('--force', is_flag=True, help='Force initialization without confirmation')
@with_appcontext
def init_db_command(force):
    """Initialize the database and create a root user."""
    import secrets
    import string

    if not force:
        if not click.confirm('This will DROP ALL TABLES and recreate them. Are you sure?'):
            click.echo('Operation cancelled.')
            return

    click.echo('Dropping all tables...')
    db.drop_all()
    
    click.echo('Creating all tables...')
    db.create_all()
    
    click.echo('Creating root user...')
    
    # Prompt for credentials
    default_username = 'root'
    username = click.prompt('Root username', default=default_username)
    
    password_input = click.prompt(
        'Root password (leave empty to generate random)',
        default='',
        show_default=False
    )
    
    if not password_input:
        # Generate random strong password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for i in range(20))
    else:
        password = password_input
    
    from app.models import User
    
    root = User(
        username=username,
        email=f'{username}@example.com',
        role='root'
    )
    root.set_password(password)
    
    db.session.add(root)
    db.session.commit()
    
    click.echo(f"""Database initialized.
----------------------------------------
Root user created
Username: {root.username}
Password: {password}
----------------------------------------
Please save this password immediately!""")

def register_commands(app):
    app.cli.add_command(clean_codes_command)
    app.cli.add_command(init_db_command)
