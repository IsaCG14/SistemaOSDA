"""
Alembic migration runner script.
"""
import os
import sys
import subprocess

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from alembic.config import Config
from alembic import command


def run_migrations():
    """Run all pending migrations."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("✅ Migraciones aplicadas correctamente")


def create_migration(message: str):
    """Create a new migration."""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)
    print(f"✅ Migración creada: {message}")


def show_current():
    """Show current migration status."""
    alembic_cfg = Config("alembic.ini")
    command.current(alembic_cfg)


def show_history():
    """Show migration history."""
    alembic_cfg = Config("alembic.ini")
    command.history(alembic_cfg)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Alembic migration runner")
    parser.add_argument("action", choices=["upgrade", "create", "current", "history"])
    parser.add_argument("message", nargs="?", help="Migration message (for create)")
    
    args = parser.parse_args()
    
    if args.action == "upgrade":
        run_migrations()
    elif args.action == "create":
        if not args.message:
            print("Error: Se requiere mensaje para crear migración")
            sys.exit(1)
        create_migration(args.message)
    elif args.action == "current":
        show_current()
    elif args.action == "history":
        show_history()