"""Business rules for event types.
Every operation is scoped to the host identified by the request. Another
host's event type is reported as not found, never as forbidden.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import not_found, slug_taken
from app.models.event_type import EventType
from app.repositories import event_type_repository, user_repository
from app.schemas.event_type import (
    CreateEventTypeRequest,
    EventTypeResponse,
    PublicEventTypeResponse,
    PublicEventTypeSummary,
    PublicHost,
    UpdateEventTypeRequest,
)
from app.utils.slug import slugify


def _to_response(event_type: EventType) -> EventTypeResponse:
    return EventTypeResponse.model_validate(event_type)


async def _load_or_404(
    session: AsyncSession, host_id: int, event_type_id: int
) -> EventType:
    event_type = await event_type_repository.get_for_host(session, host_id, event_type_id)
    if event_type is None:
        raise not_found("Event type")
    return event_type


async def list_event_types(session: AsyncSession, host_id: int) -> list[EventTypeResponse]:
    event_types = await event_type_repository.list_by_host(session, host_id)
    return [_to_response(e) for e in event_types]


async def get_event_type(
    session: AsyncSession, host_id: int, event_type_id: int
) -> EventTypeResponse:
    return _to_response(await _load_or_404(session, host_id, event_type_id))


async def create_event_type(
    session: AsyncSession, host_id: int, payload: CreateEventTypeRequest
) -> EventTypeResponse:
    # The header is only an assertion. Without this check, an unknown host id
    # would reach the foreign key and fail as a database error.
    if await user_repository.get_by_id(session, host_id) is None:
        raise not_found("User")

    # Unlike user slugs, a clash here is always reported — even when the slug
    # was derived from the title. The host is naming their own products.
    slug = payload.slug or slugify(payload.title, fallback="event")
    if await event_type_repository.slug_taken(session, host_id, slug):
        raise slug_taken()

    event_type = EventType(
        host_id=host_id,
        slug=slug,
        **payload.model_dump(mode="json", exclude={"slug"}),
    )
    await event_type_repository.add(session, event_type)
    await session.commit()
    return _to_response(event_type)


async def update_event_type(
    session: AsyncSession,
    host_id: int,
    event_type_id: int,
    payload: UpdateEventTypeRequest,
) -> EventTypeResponse:
    event_type = await _load_or_404(session, host_id, event_type_id)
    changes = payload.model_dump(mode="json", exclude_unset=True)

    if not changes:
        return _to_response(event_type)  # empty body: nothing to change

    if "slug" in changes and await event_type_repository.slug_taken(
        session, host_id, changes["slug"], exclude_id=event_type.id
    ):
        raise slug_taken()

    for field, value in changes.items():
        setattr(event_type, field, value)

    await event_type_repository.save(session, event_type)
    await session.commit()
    return _to_response(event_type)


async def delete_event_type(
    session: AsyncSession, host_id: int, event_type_id: int
) -> None:
    event_type = await _load_or_404(session, host_id, event_type_id)
    await event_type_repository.delete(session, event_type)
    await session.commit()

async def get_public_event_type(
    session: AsyncSession, host_id: int, slug: str
) -> PublicEventTypeResponse:
    """The invitee-facing view. One message for every kind of absence, so the
    endpoint cannot be used to find out which hosts or drafts exist."""
    event_type = await event_type_repository.get_active_with_host(session, host_id, slug)
    if event_type is None:
        raise not_found("Event type")

    return PublicEventTypeResponse(
        event_type=PublicEventTypeSummary.model_validate(event_type),
        host=PublicHost.model_validate(event_type.host),
    )