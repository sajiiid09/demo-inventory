"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import register_handlers
from app.routers import auth, dashboard, loans, members, repayments

app = FastAPI(
    title="MicroLoan Demo API",
    description="Register members, issue loans, collect repayments. "
    "The arithmetic rules are in DOMAIN.md; every money figure is reproducible by hand.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
