"""Bounded background processing; raw rows are committed before tasks start."""

import asyncio
import logging

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models import RawContent
from app.services import classification

logger = logging.getLogger(__name__)


def get_processing_session_factory():
    return AsyncSessionLocal


async def process_raw_ids(raw_ids: list[int], session_factory):
    if classification.get_classifier() is None:
        return
    semaphore = asyncio.Semaphore(settings.AI_PROCESSING_CONCURRENCY)

    async def process_one(raw_id):
        async with semaphore:
            try:
                async with session_factory() as db:
                    raw = await db.get(RawContent, raw_id)
                    if raw is not None and raw.status == "pending":
                        await classification.process_raw_content(
                            db, raw, skip_locked=True
                        )
                        await db.commit()
            except Exception:
                # A process/DB failure leaves the durable raw row available for retry.
                logger.exception(
                    "Background classification failed for raw_id=%s", raw_id
                )

    await asyncio.gather(*(process_one(raw_id) for raw_id in dict.fromkeys(raw_ids)))
