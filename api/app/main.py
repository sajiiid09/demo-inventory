"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import bootstrap
from app.config import settings
from app.errors import register_handlers
from app.routers import auth, dashboard, loans, members, repayments


def _configure_bootstrap_logging() -> None:
    """Make the startup steps visible in `docker compose logs api`.

    Borrow uvicorn's handler so the lines match its format and stream; fall
    back to our own when the app is started some other way (a test client, a
    script) and nothing has configured logging.
    """
    log = logging.getLogger("microloan.bootstrap")
    log.setLevel(logging.INFO)
    if log.handlers:
        return
    inherited = logging.getLogger("uvicorn.error").handlers or logging.getLogger().handlers
    if inherited:
        log.handlers = list(inherited)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("INFO:     %(message)s"))
        log.addHandler(handler)
    log.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starting the API is the only step: it creates the database if it is
    missing, migrates it to the current revision, and seeds the demo data.
    All idempotent — see app/bootstrap.py."""
    _configure_bootstrap_logging()
    bootstrap.prepare_database()
    yield


app = FastAPI(
    title="MicroLoan Demo API",
    description="Register members, issue loans, collect repayments. "
    "The arithmetic rules are in DOMAIN.md; every money figure is reproducible by hand.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_handlers(app)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(loans.router)
app.include_router(repayments.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
