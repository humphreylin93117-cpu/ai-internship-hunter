from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes.applications import router as applications_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.health import router as health_router
from backend.api.routes.discovery import router as discovery_router
from backend.api.routes.interviews import router as interviews_router
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.resumes import router as resumes_router
from backend.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Internship Hunter Agent API",
    description="AI 求职助手后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(discovery_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(resumes_router)
app.include_router(interviews_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": "AI Internship Hunter Agent API",
        "status": "running",
        "docs": "/docs",
    }
