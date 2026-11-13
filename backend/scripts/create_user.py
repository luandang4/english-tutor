"""Create an account from the command line (works while web sign-up is closed).

Usage (on the server: deploy/create-user.sh): uv run python scripts/create_user.py EMAIL "Display name" [--admin]
The password is asked interactively and never echoed or logged.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal  # noqa: E402
from app.services.auth import AuthError, create_user  # noqa: E402


async def main(email: str, name: str, admin: bool) -> None:
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    async with SessionLocal() as session:
        try:
            user = await create_user(session, email=email, password=password, display_name=name, admin=admin)
        except AuthError as e:
            sys.exit(str(e))
    role = "admin" if user.is_admin else "user (grant features in the admin panel)"
    print(f"Created account #{user.id} for {user.email} — {role}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--admin"]
    if len(args) != 2:
        sys.exit(__doc__)
    asyncio.run(main(args[0], args[1], "--admin" in sys.argv))
