"""Business rules for users.

Every function takes the session first, works in schemas on the outside and
models on the inside, raises domain errors rather than returning status codes,
and commits explicitly once all its steps have succeeded.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import already_exists, not_found
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from app.utils.slug import slugify, with_discriminator


def _to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


async def _load_or_404(session: AsyncSession, user_id: int) -> User:
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise not_found("User")
    return user


async def _free_slug_from_name(session: AsyncSession, name: str) -> str:
    """Derive a slug from the name; if taken, try -2, -3 ... until one is free."""
    base = slugify(name, fallback="user")
    candidate, number = base, 2
    while await user_repository.slug_exists(session, candidate):
        candidate = with_discriminator(base, number)
        number += 1
    return candidate


async def list_users(session: AsyncSession) -> list[UserResponse]:
    users = await user_repository.list_all(session)
    return [_to_response(u) for u in users]


async def get_user(session: AsyncSession, user_id: int) -> UserResponse:
    return _to_response(await _load_or_404(session, user_id))


async def create_user(session: AsyncSession, payload: CreateUserRequest) -> UserResponse:
    if await user_repository.get_by_email(session, payload.email) is not None:
        raise already_exists("Email")

    if payload.slug is not None:
        # The caller chose this exact slug, so a clash is reported, not renamed.
        if await user_repository.slug_exists(session, payload.slug):
            raise already_exists("Slug")
        slug = payload.slug
    else:
        slug = await _free_slug_from_name(session, payload.name)

    user = User(
        email=payload.email,
        name=payload.name,
        slug=slug,
        timezone=payload.timezone,
    )
    await user_repository.add(session, user)
    await session.commit()
    return _to_response(user)


async def update_user(
    session: AsyncSession, user_id: int, payload: UpdateUserRequest
) -> UserResponse:
    user = await _load_or_404(session, user_id)
    changes = payload.model_dump(exclude_unset=True)  # only fields the client sent

    new_email = changes.get("email")
    if new_email is not None and new_email != user.email:
        owner = await user_repository.get_by_email(session, new_email)
        if owner is not None and owner.id != user.id:
            raise already_exists("Email")

    for field, value in changes.items():
        setattr(user, field, value)

    await user_repository.save(session, user)
    await session.commit()
    return _to_response(user)


async def delete_user(session: AsyncSession, user_id: int) -> UserResponse:
    user = await _load_or_404(session, user_id)
    response = _to_response(user)  # captured before the row disappears
    await user_repository.delete(session, user)
    await session.commit()
    return response