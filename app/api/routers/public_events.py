"""Invitee-facing endpoints. No header — the person calling has no account."""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.common import ApiResponse
from app.schemas.event_type import PublicEventTypeResponse
from app.services import event_type_service
from typing import Annotated
from fastapi import Query
from app.schemas.slot import SlotListQuery, SlotListResponse
from app.services import slot_service

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

@router.get(
    "/users/{user_id}/event-types/{slug}/slots",
    response_model=ApiResponse[SlotListResponse],
)
async def list_event_type_slots(
    user_id: int,
    slug: str,
    query: Annotated[SlotListQuery, Query()],
    session: SessionDep,
) -> ApiResponse[SlotListResponse]:
    """Bookable slots grouped by local date. No header required."""
    data = await slot_service.list_public_slots(session, user_id, slug, query)
    return ApiResponse(data=data)