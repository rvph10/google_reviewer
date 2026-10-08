import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.jobs import run_cycle
from app.web import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db(s.database_url)
    scheduler = BackgroundScheduler(timezone="UTC")
    if s.scheduler_enabled:
        first_run = datetime.now(UTC) + timedelta(seconds=30)
        scheduler.add_job(run_cycle, "interval", minutes=s.poll_minutes, next_run_time=first_run, coalesce=True)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Google Reviewer", lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(router)
