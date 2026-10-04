"""Business rules for availability rules.

The notable one is in update: a partial change is combined with the stored
rule and the result is checked as a whole, so a PATCH can never leave a rule
whose end is before its start.
"""

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, not_found
from app.models.availability_rule import AvailabilityRule
from app.repositories import availability_rule_repository, user_repository
from app.schemas.availability import (
    AvailabilityRuleFields,
    AvailabilityRuleResponse,
    CreateAvailabilityRuleRequest,
    UpdateAvailabilityRuleRequest,
)


def _to_response(rule: AvailabilityRule) -> AvailabilityRuleResponse:
    return AvailabilityRuleResponse.model_validate(rule)


async def _load_or_404(
    session: AsyncSession, user_id: int, rule_id: int
) -> AvailabilityRule:
    rule = await availability_rule_repository.get_for_user(session, user_id, rule_id)
    if rule is None:
        raise not_found("Availability rule")
    return rule


async def list_rules(session: AsyncSession, user_id: int) -> list[AvailabilityRuleResponse]:
    rules = await availability_rule_repository.list_by_user(session, user_id)
    return [_to_response(r) for r in rules]


async def create_rule(
    session: AsyncSession, user_id: int, payload: CreateAvailabilityRuleRequest
) -> AvailabilityRuleResponse:
    if await user_repository.get_by_id(session, user_id) is None:
        raise not_found("User")

    rule = AvailabilityRule(user_id=user_id, **payload.model_dump())
    await availability_rule_repository.add(session, rule)
    await session.commit()
    return _to_response(rule)


async def update_rule(
    session: AsyncSession,
    user_id: int,
    rule_id: int,
    payload: UpdateAvailabilityRuleRequest,
) -> AvailabilityRuleResponse:
    rule = await _load_or_404(session, user_id, rule_id)
    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        return _to_response(rule)

    # Stored values first, then the changes on top.
    combined = {
        "weekday": rule.weekday,
        "start_time": rule.start_time,
        "end_time": rule.end_time,
        "is_active": rule.is_active,
        "timezone": rule.timezone,
        **changes,
    }
    try:
        AvailabilityRuleFields.model_validate(combined)
    except ValidationError as exc:
        message = exc.errors()[0]["msg"].removeprefix("Value error, ")
        raise BadRequestError(message)

    for field, value in changes.items():
        setattr(rule, field, value)

    await availability_rule_repository.save(session, rule)
    await session.commit()
    return _to_response(rule)


async def delete_rule(session: AsyncSession, user_id: int, rule_id: int) -> None:
    rule = await _load_or_404(session, user_id, rule_id)
    await availability_rule_repository.delete(session, rule)
    await session.commit()