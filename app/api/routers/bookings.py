"""Bookings: /api/bookings (Part 2, Section 10). Requires x-user-id."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import HostId, SessionDep, get_host_id
from app.schemas.booking import BookingCreate, BookingCreateResponse, BookingListQuery, BookingListResponse
from app.schemas.common import ApiResponse
from app.services import booking_service

router = APIRouter(prefix="/api/bookings", tags=["bookings"], dependencies=[Depends(get_host_id)])


@router.get("", response_model=ApiResponse[BookingListResponse])
async def list_bookings(
    host_id: HostId, session: SessionDep, query: Annotated[BookingListQuery, Query()]
) -> ApiResponse[BookingListResponse]:
    data = await booking_service.list_bookings(session, host_id, query)
    return ApiResponse(data=data)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApiResponse[BookingCreateResponse])
async def create_booking(
    host_id: HostId, session: SessionDep, payload: BookingCreate
) -> ApiResponse[BookingCreateResponse]:
    # Pessimistic strategy is the routed one; create_booking_optimistic is
    # implemented and checked by scripts/check_booking_concurrency.py.
    data = await booking_service.create_booking(session, host_id, payload)
    return ApiResponse(data=data, message="Booking created successfully")
