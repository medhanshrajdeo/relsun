"""
Deterministic create/update/delete request handling — the product's first
write path to governed master data. Per the Party Request Agent build
plan: gathering what a request needs is the Party Request Agent's (LLM)
job; everything in this module is plain code with no LLM involved,
because the two moments that actually change master_records — saving a
proposal, and applying an already-approved one — should never be
something an LLM decides on its own to do.

`proposed_attributes` uses the same shape as MasterRecord.attributes,
with two conventions: a "name" key maps to MasterRecord.name, and a
"lei" key maps to MasterRecord.external_id (the same column GLEIF
ingestion populates) — both live as their own columns rather than inside
attributes, and "lei" is what dedup checks below key off. A create needs
name + country always; LEI is optional but, when given, must not already
belong to another active record — an exact LEI match is decisive in a
way name similarity never is, so it's rejected outright rather than
merely flagged.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, MasterDataRequest, MasterRecord

REQUEST_TYPES = {"create", "update", "delete"}


class RequestValidationError(ValueError):
    """A submitted request is malformed or targets a record that doesn't
    exist — distinct from RequestStateError so callers (main.py) can map
    each to the right HTTP status."""


class RequestStateError(ValueError):
    """A decision (approve/reject) was attempted on a request that isn't
    pending — already decided, or doesn't exist."""


def _log(session: Session, entity_id: int, action: str, detail: str | None = None) -> None:
    session.add(AuditLog(entity_type="master_data_request", entity_id=entity_id, action=action, detail=detail))


def _lei_collision(session: Session, lei: str, *, exclude_record_id: int | None = None) -> MasterRecord | None:
    query = session.query(MasterRecord).filter(MasterRecord.external_id == lei, MasterRecord.deleted_at.is_(None))
    if exclude_record_id is not None:
        query = query.filter(MasterRecord.id != exclude_record_id)
    return query.first()


def submit_request(
    session: Session,
    domain: str,
    request_type: str,
    target_record_id: int | None = None,
    proposed_attributes: dict | None = None,
    submitted_by_id: int | None = None,
) -> MasterDataRequest:
    if request_type not in REQUEST_TYPES:
        raise RequestValidationError(f"request_type must be one of {sorted(REQUEST_TYPES)}, got {request_type!r}")

    if request_type == "create":
        if target_record_id is not None:
            raise RequestValidationError("create requests must not specify target_record_id")
        if not proposed_attributes or not proposed_attributes.get("name"):
            raise RequestValidationError("create requests need proposed_attributes with at least a 'name'")
        if not proposed_attributes.get("country"):
            raise RequestValidationError("create requests need proposed_attributes with at least 'name' and 'country'")
        lei = proposed_attributes.get("lei")
        if lei:
            existing = _lei_collision(session, lei)
            if existing is not None:
                raise RequestValidationError(
                    f"a record with LEI {lei} already exists (id {existing.id}, {existing.name}) — "
                    "this looks like the same entity, not a new one"
                )
    else:
        if target_record_id is None:
            raise RequestValidationError(f"{request_type} requests must specify target_record_id")
        target = session.get(MasterRecord, target_record_id)
        if target is None or target.deleted_at is not None:
            raise RequestValidationError(f"master record {target_record_id} not found")
        if request_type == "update" and not proposed_attributes:
            raise RequestValidationError("update requests need proposed_attributes")
        if request_type == "update" and proposed_attributes and proposed_attributes.get("lei"):
            existing = _lei_collision(session, proposed_attributes["lei"], exclude_record_id=target_record_id)
            if existing is not None:
                raise RequestValidationError(
                    f"a record with LEI {proposed_attributes['lei']} already exists "
                    f"(id {existing.id}, {existing.name})"
                )

    request = MasterDataRequest(
        domain=domain,
        request_type=request_type,
        target_record_id=target_record_id,
        proposed_attributes=proposed_attributes,
        status="pending",
        submitted_at=datetime.now(timezone.utc),
        submitted_by_id=submitted_by_id,
    )
    session.add(request)
    session.flush()  # populate request.id before it's referenced by the log entry
    _log(session, request.id, "submitted", detail=f"{request_type} request for domain {domain}")
    session.commit()
    session.refresh(request)
    return request


def list_requests(session: Session, status: str | None = None) -> list[MasterDataRequest]:
    query = session.query(MasterDataRequest)
    if status:
        query = query.filter(MasterDataRequest.status == status)
    return query.order_by(MasterDataRequest.submitted_at.desc()).all()


def get_request(session: Session, request_id: int) -> MasterDataRequest | None:
    return session.get(MasterDataRequest, request_id)


def _require_pending(session: Session, request_id: int) -> MasterDataRequest:
    request = session.get(MasterDataRequest, request_id)
    if request is None:
        raise RequestStateError(f"request {request_id} not found")
    if request.status != "pending":
        raise RequestStateError(f"request {request_id} is already {request.status}, not pending")
    return request


def approve_request(
    session: Session, request_id: int, decision_note: str | None = None, decided_by_id: int | None = None
) -> MasterDataRequest:
    """Applies the request's diff to master_records, then marks it
    published. This is the only function in the codebase allowed to turn
    a MasterDataRequest into an actual MasterRecord change — it only
    runs when a human calls it (via POST /requests/{id}/approve), never
    from agent code."""
    request = _require_pending(session, request_id)
    attrs = dict(request.proposed_attributes or {})

    if request.request_type == "create":
        name = attrs.pop("name")
        lei = attrs.pop("lei", None)
        # Re-checked here, not just at submit time: two pending requests
        # proposing the same new LEI can both still be pending when the
        # first one gets approved — this is the actual write, so this is
        # the check that has to be airtight. The IntegrityError catch
        # below is the final backstop if even this race loses.
        if lei and _lei_collision(session, lei) is not None:
            raise RequestValidationError(f"cannot approve — a record with LEI {lei} already exists")
        record = MasterRecord(domain=request.domain, name=name, attributes=attrs, external_id=lei)
        session.add(record)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise RequestValidationError(f"cannot approve — LEI {lei} was just used by another record") from exc
        applied_detail = f"created master record {record.id} ({name})" + (f", LEI {lei}" if lei else "")
    else:
        record = session.get(MasterRecord, request.target_record_id)
        if record is None or record.deleted_at is not None:
            raise RequestStateError(f"master record {request.target_record_id} no longer exists")
        if request.request_type == "update":
            if "name" in attrs:
                record.name = attrs.pop("name")
            if "lei" in attrs:
                lei = attrs.pop("lei")
                if lei and _lei_collision(session, lei, exclude_record_id=record.id) is not None:
                    raise RequestValidationError(f"cannot approve — a record with LEI {lei} already exists")
                record.external_id = lei
            record.attributes = {**record.attributes, **attrs}
            applied_detail = f"updated master record {record.id}"
        else:  # delete
            record.deleted_at = datetime.now(timezone.utc)
            applied_detail = f"soft-deleted master record {record.id}"

    now = datetime.now(timezone.utc)
    request.status = "published"
    request.decision_note = decision_note
    request.decided_at = now
    request.decided_by_id = decided_by_id
    _log(session, request.id, "approved", detail=decision_note)
    _log(session, request.id, "published", detail=applied_detail)
    session.commit()
    session.refresh(request)
    return request


def reject_request(
    session: Session, request_id: int, decision_note: str | None = None, decided_by_id: int | None = None
) -> MasterDataRequest:
    request = _require_pending(session, request_id)
    request.status = "rejected"
    request.decision_note = decision_note
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by_id = decided_by_id
    _log(session, request.id, "rejected", detail=decision_note)
    session.commit()
    session.refresh(request)
    return request
