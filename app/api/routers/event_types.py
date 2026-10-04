"""HTTP endpoints for /api/event-types. Every route requires x-user-id."""

from fastapi import APIRouter, Depends, status

from app.api.deps import HostId, SessionDep, get_host_id
from app.schemas.common import ApiResponse
from app.schemas.event_type import (
    CreateEventTypeRequest,
    EventTypeResponse,
    UpdateEventTypeRequest,
)
from app.services import event_type_service

router = APIRouter(
    prefix="/api/event-types",
    tags=["event-types"],
    # Applied to every route here, so none can be added without the header check.
    dependencies=[Depends(get_host_id)],
)


@router.get("", response_model=ApiResponse[list[EventTypeResponse]])
async def list_event_types(
    host_id: HostId, session: SessionDep
) -> ApiResponse[list[EventTypeResponse]]:
    items = await event_type_service.list_event_types(session, host_id)
    return ApiResponse[list[EventTypeResponse]](data=items)


@router.get("/{event_type_id}", response_model=ApiResponse[EventTypeResponse])
async def get_event_type(
    event_type_id: int, host_id: HostId, session: SessionDep
) -> ApiResponse[EventTypeResponse]:
    item = await event_type_service.get_event_type(session, host_id, event_type_id)
    return ApiResponse[EventTypeResponse](data=item)


@router.post(
    "",
    response_model=ApiResponse[EventTypeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_event_type(
    payload: CreateEventTypeRequest, host_id: HostId, session: SessionDep
) -> ApiResponse[EventTypeResponse]:
    item = await event_type_service.create_event_type(session, host_id, payload)
    return ApiResponse[EventTypeResponse](data=item, message="Event type created successfully")


@router.patch("/{event_type_id}", response_model=ApiResponse[EventTypeResponse])
async def update_event_type(
    event_type_id: int,
    payload: UpdateEventTypeRequest,
    host_id: HostId,
    session: SessionDep,
) -> ApiResponse[EventTypeResponse]:
    item = await event_type_service.update_event_type(session, host_id, event_type_id, payload)
    return ApiResponse[EventTypeResponse](data=item, message="Event type updated successfully")


@router.delete("/{event_type_id}", response_model=ApiResponse[None])
async def delete_event_type(
    event_type_id: int, host_id: HostId, session: SessionDep
) -> ApiResponse[None]:
    await event_type_service.delete_event_type(session, host_id, event_type_id)
    return ApiResponse[None](data=None, message="Event type deleted successfully")