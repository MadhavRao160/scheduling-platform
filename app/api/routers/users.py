"""HTTP endpoints for /api/users.

Thin by design: each handler receives already-validated input, calls one
service function, and wraps the result in the response envelope. No business
rules and no queries live here.

No x-user-id header on these routes — creating a user is how a host comes to
exist in the first place.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.common import ApiResponse
from app.schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[list[UserResponse]]:
    users = await user_service.list_users(session)
    return ApiResponse[list[UserResponse]](data=users)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserResponse]:
    user = await user_service.get_user(session, user_id)
    return ApiResponse[UserResponse](data=user)


@router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserResponse]:
    user = await user_service.create_user(session, payload)
    return ApiResponse[UserResponse](data=user, message="User created successfully")


@router.patch("/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserResponse]:
    user = await user_service.update_user(session, user_id, payload)
    return ApiResponse[UserResponse](data=user, message="User updated successfully")


@router.delete("/{user_id}", response_model=ApiResponse[UserResponse])
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[UserResponse]:
    user = await user_service.delete_user(session, user_id)
    return ApiResponse[UserResponse](data=user, message="User deleted successfully")