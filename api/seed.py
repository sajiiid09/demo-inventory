"""Seed the demo database by hand.

The API seeds itself on startup (app/bootstrap.py), so this script exists for
the times you want to do it explicitly — after a `docker compose down -v`, or
while working against a database the API is not attached to.

    python seed.py

It is idempotent: the staff logins are repaired if they drifted, and the demo
portfolio is loaded only when there are no members yet. The ledger is
append-only, so re-loading the portfolio means starting from a clean schema:

    alembic downgrade base && alembic upgrade head && python seed.py

The data itself lives in app/seeds.py.
"""

from app.seeds import ensure_seeded

if __name__ == "__main__":
    print("Seeded:", ensure_seeded())
