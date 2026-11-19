"""Install reference dictionaries and a finite, curated starter catalog."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import AsyncSessionLocal, engine
from app.schemas.opportunity import ReviewedOpportunity
from app.schemas.raw_content import RawContentCreate
from app.services.dictionaries import sync_reference_data
from app.services.ingestion import ingest_raw_content
from app.services.publication import active, publication_error
from app.services.university import sync_university_structure


async def prepare():
    entries = json.loads((Path(__file__).resolve().parents[1] / "examples" / "starter-catalog.json").read_text())
    async with AsyncSessionLocal.begin() as db:
        await sync_reference_data(db)
        await sync_university_structure(db)
        for item in entries:
            card = ReviewedOpportunity.model_validate(item["card"])
            if not active(card, datetime.now(timezone.utc)):
                continue
            error = publication_error(card, item["source_url"])
            if error:
                raise ValueError(error)
            raw = await ingest_raw_content(db, RawContentCreate(
                source_type="curated", source_url=item["source_url"],
                raw_text=card.title + "\n" + card.summary,
                ingest_metadata={"entry_method": "editorial_summary", "checked_on": "2026-11-19"},
            ))
            if raw.opportunity_review is None:
                raw.opportunity_review = card.model_dump(mode="json")
                raw.status = "processed"
                raw.processed_at = datetime.now(timezone.utc)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(prepare())
