from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.exceptions import BaseAppException
from core.tracing import bind_postgres_writer, setup_tracing, shutdown_tracing
from routes import build, graph, graphs, health, query
from services.app_state import state

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB access can't happen at import time, so the default graph is found/seeded
    # here rather than eagerly in the AppState singleton's constructor.
    setup_tracing()
    bind_postgres_writer()
    await state.bootstrap()
    yield
    await shutdown_tracing()


app = FastAPI(title="SKG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(health.router, prefix="/api")
app.include_router(graph.router, prefix="/api/graph")
app.include_router(graphs.router, prefix="/api/graphs")
app.include_router(query.router, prefix="/api")
app.include_router(build.router, prefix="/api/build")
