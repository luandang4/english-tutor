"""Create an account from the command line (works while web sign-up is closed).

Usage (on the server: deploy/create-user.sh): uv run python scripts/create_user.py EMAIL "Display name"
The password is asked interactively and never echoed or logged.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal  # noqa: E402
from app.services.auth import AuthError, create_user  # noqa: E402

MIN_PASSWORD = 8


async def main(email: str, name: str) -> None:
    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD:
        sys.exit(f"Password must be at least {MIN_PASSWORD} characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    async with SessionLocal() as session:
        try:
            user = await create_user(session, email=email, password=password, display_name=name)
        except AuthError as e:
            sys.exit(str(e))
    print(f"Created account #{user.id} for {user.email}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
