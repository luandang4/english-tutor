"""Create an account from the command line (works while web sign-up is closed).

Usage (on the server: deploy/create-user.sh):
    uv run python scripts/create_user.py EMAIL "Display name" [--admin] [--plan CODE]
--plan puts the account on that plan right away (codes: trial, basic, plus, friends, or your own); without it
the account waits for an admin to choose a plan. The password is asked interactively and never echoed or logged.
"""

import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal  # noqa: E402
from app.services.auth import AuthError, create_user  # noqa: E402


async def main(email: str, name: str, admin: bool, plan: str | None) -> None:
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    async with SessionLocal() as session:
        try:
            user = await create_user(
                session, email=email, password=password, display_name=name, admin=admin, plan_code=plan
            )
        except AuthError as e:
            sys.exit(str(e))
    role = "admin" if user.is_admin else f"user on plan {plan}" if plan else "user (choose a plan in the admin panel)"
    print(f"Created account #{user.id} for {user.email} — {role}")


def parse_args(argv: list[str]) -> tuple[str, str, bool, str | None]:
    plan = None
    if "--plan" in argv:
        i = argv.index("--plan")
        if i + 1 >= len(argv):
            sys.exit(__doc__)
        plan = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]
    args = [a for a in argv if a != "--admin"]
    if len(args) != 2:
        sys.exit(__doc__)
    return args[0], args[1], "--admin" in argv, plan


if __name__ == "__main__":
    asyncio.run(main(*parse_args(sys.argv[1:])))
