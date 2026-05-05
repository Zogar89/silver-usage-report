from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.usage_report import router as usage_report_api_router
from app.db.session import init_database
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="Silver Usage Report", lifespan=lifespan)

    @application.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Content-Security-Policy", _content_security_policy())
        return response

    application.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    application.include_router(usage_report_api_router)
    application.include_router(web_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "silver-usage-report",
        }

    return application


app = create_app()


def _content_security_policy() -> str:
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
