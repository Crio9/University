"""Re-evaluate unedited AI drafts after upgrading an existing demo database."""
import asyncio

from sqlalchemy import select

from app.db.database import AsyncSessionLocal, engine
from app.models import RawContent
from app.schemas.opportunity import OpportunityFields, ReviewedOpportunity
from app.services.publication import classify_publication


async def publish_ready():
    async with AsyncSessionLocal.begin() as db:
        rows = await db.scalars(select(RawContent).where(
            RawContent.opportunity_review.is_not(None)).order_by(RawContent.id).with_for_update())
        published = 0
        for raw in rows:
            proposal = (raw.ai_result or {}).get("opportunity")
            review = raw.opportunity_review
            if not proposal or review.get("status") != "draft":
                continue
            fields = OpportunityFields.model_validate(proposal)
            if ReviewedOpportunity.model_validate(review) != ReviewedOpportunity.model_validate(fields.model_dump()):
                continue
            card = classify_publication(raw, fields)
            if card.status == "published":
                raw.opportunity_review = card.model_dump(mode="json")
                published += 1
    print(f"Опубликовано карточек: {published}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(publish_ready())
