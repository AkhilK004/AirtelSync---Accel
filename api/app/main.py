from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.loaders import get_data
from app import errors
from app import logging as pii_logging
from app.routers import admin, advisor, backoffice, checkout, consent, health, kyc, mocks, orders, quotes


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_data()  # load once at startup
    if settings.SEED_ON_START:
        from app.seed import seed_demo
        seed_demo(reset=False)
    yield


pii_logging.install()
app = FastAPI(title="Udyam Digital API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)
errors.install(app)
app.include_router(health.router)
app.include_router(mocks.router)
app.include_router(quotes.router)
app.include_router(advisor.router)
app.include_router(checkout.router)
app.include_router(consent.router)
app.include_router(kyc.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(backoffice.router)
