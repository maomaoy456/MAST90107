from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app.config import Settings
from app.db import build_engine, get_session, session_factory
from app.logging import configure_logging, safe_log
from app.dashboard.routes import router
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError


class HealthResponse(BaseModel):
    application: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or Settings()
    engine = build_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="MPE Backend", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory(engine)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "PUT", "POST"], allow_headers=["X-API-Key", "Content-Type"])
    app.include_router(router)

    @app.middleware("http")
    async def private_requests(request, call_next):
        try:
            response = await call_next(request)
        except SQLAlchemyError:
            safe_log("database_unavailable", status=503)
            response = JSONResponse(status_code=503, content={"detail": "database_unavailable"})
        except Exception:
            safe_log("unhandled_error", status=500)
            response = JSONResponse(status_code=500, content={"detail": "internal_error"})
        safe_log("request_complete", status=response.status_code)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"detail": "invalid_request"})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": "request_error"})

    @app.get("/api/v1/health", response_model=HealthResponse,
             responses={503: {"model": HealthResponse}})
    def health(session: Session = Depends(get_session)):
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            safe_log("database_unavailable", status=503)
            return JSONResponse(status_code=503, content={"application": "ok", "database": "unavailable"})
        return HealthResponse(database="ok")

    return app
