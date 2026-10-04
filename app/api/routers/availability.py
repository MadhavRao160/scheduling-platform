"""HTTP endpoints for /api/availability. Every route requires x-user-id.
Rules are here now; exceptions will be added to this same router.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import HostId, SessionDep, get_host_id
from app.schemas.availability import (
    AvailabilityRuleResponse,
    CreateAvailabilityRuleRequest,
    UpdateAvailabilityRuleRequest,
)
from app.schemas.common import ApiResponse
from app.services import availability_rule_service

router = APIRouter(
    prefix="/api/availability",
    tags=["availability"],
    dependencies=[Depends(get_host_id)],
)

# ---------------------------------------------------------------- Rules

@router.get("/rules", response_model=ApiResponse[list[AvailabilityRuleResponse]])
async def list_rules(
    host_id: HostId, session: SessionDep
) -> ApiResponse[list[AvailabilityRuleResponse]]:
    rules = await availability_rule_service.list_rules(session, host_id)
    return ApiResponse[list[AvailabilityRuleResponse]](data=rules)


@router.post(
    "/rules",
    response_model=ApiResponse[AvailabilityRuleResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    payload: CreateAvailabilityRuleRequest, host_id: HostId, session: SessionDep
) -> ApiResponse[AvailabilityRuleResponse]:
    rule = await availability_rule_service.create_rule(session, host_id, payload)
    return ApiResponse[AvailabilityRuleResponse](
        data=rule, message="Availability rule created successfully"
    )


@router.patch("/rules/{rule_id}", response_model=ApiResponse[AvailabilityRuleResponse])
async def update_rule(
    rule_id: int,
    payload: UpdateAvailabilityRuleRequest,
    host_id: HostId,
    session: SessionDep,
) -> ApiResponse[AvailabilityRuleResponse]:
    rule = await availability_rule_service.update_rule(session, host_id, rule_id, payload)
    return ApiResponse[AvailabilityRuleResponse](
        data=rule, message="Availability rule updated successfully"
    )


@router.delete("/rules/{rule_id}", response_model=ApiResponse[None])
async def delete_rule(rule_id: int, host_id: HostId, session: SessionDep) -> ApiResponse[None]:
    await availability_rule_service.delete_rule(session, host_id, rule_id)
    return ApiResponse[None](data=None, message="Availability rule deleted successfully")