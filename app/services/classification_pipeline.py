
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ai_classification import AIClassificationResult
from app.services.ai_classifier import AIProvider
from app.services.post_classification import create_post_from_classification


async def classify_and_create_post(
    db: AsyncSession,
    provider: AIProvider,
    *,
    title: str,
    content: str,
    author_id: int,
):
    """Классифицирует текст с помощью AI и создаёт публикацию."""
    classification: AIClassificationResult = await provider.classify(
        title=title,
        content=content,
    )

    classification = AIClassificationResult.model_validate(classification)

    post = await create_post_from_classification(
        db,
        title=title,
        content=content,
        author_id=author_id,
        classification=classification,
    )

    return post
