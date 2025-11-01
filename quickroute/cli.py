#!/usr/bin/env python3
"""
QuickRoute Command Line Interface

Provides management commands for QuickRoute applications.
"""

import subprocess
import sys
from pathlib import Path
import typer
from typer import Typer

app = Typer(help="QuickRoute - async web framework built with FastAPI")


@app.command()
def runserver(host: str = None, port: int = None):
    """Run Uvicorn development server."""
    try:
        from app.settings import settings

        host = host or getattr(settings, "HOST", "127.0.0.1")
        port = port or getattr(settings, "PORT", 8000)
    except ImportError:
        host = host or "127.0.0.1"
        port = port or 8000

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--reload",
    ]
    subprocess.run(cmd)


@app.command()
def migrate(message: str = "migration"):
    """Create & run migrations using alembic."""
    subprocess.run([sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", message])
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])


@app.command()
def createsuperuser(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """Create a superuser record."""
    try:
        from app.database import AsyncSessionLocal
        from app.models import User
        from passlib.context import CryptContext
        import asyncio

        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

        async def _create():
            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=pwd_ctx.hash(password),
                    is_superuser=True,
                    is_active=True,
                )
                session.add(user)
                await session.commit()
                typer.echo(f"Superuser {email} created successfully!")

        asyncio.run(_create())
    except ImportError as e:
        typer.echo(f"Error: Could not import required modules. {e}")
        typer.echo("Make sure you're in a QuickRoute project directory.")
        sys.exit(1)


@app.command()
def shell():
    """interactive shell with app context"""
    try:
        import code
        import asyncio
        from app.models import User, BlacklistedToken
        from app.database import AsyncSessionLocal, engine
        from app.settings import settings
        from sqlalchemy import select
        from app.auth import hash_password, verify_password
    except ImportError as e:
        typer.echo(f"Error: Could not import required modules. {e}")
        typer.echo("Make sure you're in a QuickRoute project directory.")
        sys.exit(1)

    shell_globals = {
        "User": User,
        "BlacklistedToken": BlacklistedToken,
        "AsyncSessionLocal": AsyncSessionLocal,
        "engine": engine,
        "settings": settings,
        "select": select,
        "hash_password": hash_password,
        "verify_password": verify_password,
        "asyncio": asyncio,
        "session": None,  # Will be set in async context
    }

    async def get_session():
        """Get a database session"""
        return AsyncSessionLocal()

    async def get_user_by_email(email):
        """Get user by email"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            return result.scalar_one_or_none()

    async def create_user(email, password, **kwargs):
        """Create a new user"""
        async with AsyncSessionLocal() as session:
            user = User(email=email, hashed_password=hash_password(password), **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    shell_globals.update(
        {
            "get_session": get_session,
            "get_user_by_email": get_user_by_email,
            "create_user": create_user,
        }
    )

    banner = """
    🚀 QuickRoute Shell
    ══════════════════════════════════════════════════════════════════

    Available objects:
    • User, BlacklistedToken - Models
    • AsyncSessionLocal - Database session factory
    • settings - App settings
    • select - SQLAlchemy select
    • hash_password, verify_password - Auth utilities
    • get_user_by_email(email) - Helper function
    • create_user(email, password) - Helper function

    Example usage:
    >>> await get_user_by_email('user@example.com')
    >>> user = await create_user('test@example.com', 'password123')
    >>> users = await User.objects.all()
    >>> user = await User.objects.get(id=1)
    >>> active_users = await User.objects.filter(is_active=True)
    >>> new_user = await User.objects.create(email='test@example.com', is_superuser=True)
    >>> user_obj, created = await User.objects.get_or_create(email='test@example.com', defaults={'is_active': True})
    >>> count = await User.objects.count(is_active=True)
    >>> user.check_password('password123')  # method
    >>> user.set_password('newpassword')   # method
    >>> str(user)  # __str__ method

    Use 'exit()' or Ctrl+D to quit.
    """

    typer.echo(banner)
    code.interact(banner="", local=shell_globals)


@app.command()
def startproject(name: str):
    """Create a new QuickRoute project."""
    project_path = Path(name)

    if project_path.exists():
        typer.echo(f"Error: Directory '{name}' already exists.")
        sys.exit(1)

    project_path.mkdir()

    (project_path / "app").mkdir()

    main_content = """from quickroute import QuickRoute

app = QuickRoute(
    title="{{ name }}",
    description="{{ name }} application"
)

@app.get("/")
async def root():
    return {"message": "Hello from {{ name }}!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
""".replace(
        "{{ name }}", name
    )

    with open(project_path / "app" / "main.py", "w") as f:
        f.write(main_content)

    requirements = """quickroute
fastapi
uvicorn
sqlalchemy
alembic
aiosqlite
python-jose[cryptography]
passlib[bcrypt]
python-multipart
typer
"""

    with open(project_path / "requirements.txt", "w") as f:
        f.write(requirements)

    env_example = """SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite+aiosqlite:///./db.sqlite
JWT_SECRET_KEY=your-jwt-secret-here
"""

    with open(project_path / ".env.example", "w") as f:
        f.write(env_example)

    typer.echo(f"✅ Created QuickRoute project '{name}'")
    typer.echo(f"📁 Project directory: {project_path.absolute()}")
    typer.echo("\nNext steps:")
    typer.echo(f"  cd {name}")
    typer.echo("  cp .env.example .env")
    typer.echo("  pip install -r requirements.txt")
    typer.echo("  quickroute runserver")


@app.command()
def test(
    test_path: str = typer.Argument(None, help="Path to test file or directory"),
    verbosity: int = typer.Option(1, "--verbose", "-v", count=True),
    keepdb: bool = typer.Option(False, "--keep-db", help="Preserve test database"),
    parallel: int = typer.Option(1, "--parallel", "-n", help="Number of parallel processes"),
    pattern: str = typer.Option("test*.py", "--pattern", help="Test file pattern"),
    tag: str = typer.Option(None, "--tag", help="Run tests with specific tag"),
):
    """Run tests using pytest with QuickRoute test configuration."""
    try:
        import pytest
        from pathlib import Path
        import os

        # Build pytest command
        cmd = [sys.executable, "-m", "pytest"]

        if verbosity > 1:
            cmd.append(f"-{'v' * (verbosity - 1)}")
        elif verbosity > 0:
            cmd.append("-v")

        if test_path:
            cmd.append(test_path)
        else:
            # Default to tests directory
            test_dir = Path("tests")
            if test_dir.exists():
                cmd.append("tests")
            else:
                # Look for test files in current directory
                cmd.append(".")

        cmd.extend(["--pattern", pattern])

        if parallel > 1:
            cmd.extend(["-n", str(parallel)])

        if tag:
            cmd.extend(["-m", tag])

        if keepdb:
            os.environ["QUICKROUTE_TEST_KEEP_DB"] = "1"

        os.environ["QUICKROUTE_TESTING"] = "1"

        if os.environ.get("COVERAGE"):
            cmd.extend(
                [
                    "--cov=app",
                    "--cov-report=html",
                    "--cov-report=term-missing",
                    "--cov-fail-under=80",
                ]
            )

        cmd.extend(
            [
                "--tb=short",  # Short traceback format
                "--strict-markers",  # Strict marker checking
                "--disable-warnings",  # Disable warnings during testing
            ]
        )

        typer.echo(f"Running tests with command: {' '.join(cmd)}")
        subprocess.run(cmd)

    except ImportError:
        typer.echo("Error: pytest not found. Install with: pip install pytest pytest-asyncio")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error running tests: {e}")
        sys.exit(1)


@app.command()
def version():
    """Show QuickRoute version."""
    from . import __version__

    typer.echo(f"QuickRoute {__version__}")


def main():
    """Entry point for quickroute CLI."""
    app()


if __name__ == "__main__":
    main()
