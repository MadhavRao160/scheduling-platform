"""Invitee-facing endpoints. No header — the person calling has no account."""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.common import ApiResponse
from app.schemas.event_type import PublicEventTypeResponse
from app.services import event_type_service

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get(
    "/users/{user_id}/event-types/{slug}",
    response_model=ApiResponse[PublicEventTypeResponse],
)
async def get_public_event_type(
    user_id: int, slug: str, session: SessionDep
) -> ApiResponse[PublicEventTypeResponse]:
    item = await event_type_service.get_public_event_type(session, user_id, slug)
    return ApiResponse[PublicEventTypeResponse](data=item)