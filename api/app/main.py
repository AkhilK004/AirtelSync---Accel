from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.loaders import get_data
from app.routers import health


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_data()  # load once at startup
    yield


app = FastAPI(title="Udyam Digital API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(health.router)
