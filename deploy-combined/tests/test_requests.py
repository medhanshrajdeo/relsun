"""
Deterministic requests.py coverage — no LLM, no API key needed. Uses the
real dev Postgres via db_session (conftest.py), rolled back after each
test so nothing persists.
"""

import pytest

from app.models import AuditLog, MasterRecord
from app.requests import (
    RequestStateError,
    RequestValidationError,
    approve_request,
    list_requests,
    reject_request,
    submit_request,
)


def _make_record(session, name="Existing Co", **attrs):
    record = MasterRecord(domain="Party", name=name, attributes=attrs)
    session.add(record)
    session.flush()
    return record


def test_submit_create_then_approve_inserts_new_record(db_session):
    request = submit_request(
        db_session,
        domain="Party",
        request_type="create",
        proposed_attributes={"name": "New Co", "country": "US"},
    )
    assert request.status == "pending"

    approved = approve_request(db_session, request.id, decision_note="looks fine")
    assert approved.status == "published"
    assert approved.decision_note == "looks fine"

    created = db_session.query(MasterRecord).filter(MasterRecord.name == "New Co").one()
    assert created.attributes == {"country": "US"}

    actions = [
        a.action
        for a in db_session.query(AuditLog).filter(AuditLog.entity_id == request.id).order_by(AuditLog.id)
    ]
    assert actions == ["submitted", "approved", "published"]


def test_submit_update_then_approve_merges_attributes(db_session):
    record = _make_record(db_session, name="Old Name", country="US")
    request = submit_request(
        db_session,
        domain="Party",
        request_type="update",
        target_record_id=record.id,
        proposed_attributes={"city": "Austin"},
    )
    approve_request(db_session, request.id)

    db_session.refresh(record)
    assert record.attributes == {"country": "US", "city": "Austin"}
    assert record.name == "Old Name"  # unchanged — "name" wasn't in proposed_attributes


def test_submit_delete_then_approve_soft_deletes(db_session):
    record = _make_record(db_session)
    request = submit_request(db_session, domain="Party", request_type="delete", target_record_id=record.id)
    approve_request(db_session, request.id)

    db_session.refresh(record)
    assert record.deleted_at is not None


def test_reject_leaves_master_records_untouched(db_session):
    record = _make_record(db_session, name="Untouched Co")
    request = submit_request(
        db_session,
        domain="Party",
        request_type="update",
        target_record_id=record.id,
        proposed_attributes={"city": "Somewhere"},
    )
    reject_request(db_session, request.id, decision_note="not needed")

    db_session.refresh(record)
    assert record.attributes == {}
    assert request.status == "rejected"


def test_cannot_decide_a_request_twice(db_session):
    record = _make_record(db_session)
    request = submit_request(db_session, domain="Party", request_type="delete", target_record_id=record.id)
    approve_request(db_session, request.id)

    with pytest.raises(RequestStateError):
        approve_request(db_session, request.id)


def test_create_requires_name(db_session):
    with pytest.raises(RequestValidationError):
        submit_request(db_session, domain="Party", request_type="create", proposed_attributes={"country": "US"})


def test_create_requires_country(db_session):
    with pytest.raises(RequestValidationError):
        submit_request(db_session, domain="Party", request_type="create", proposed_attributes={"name": "New Co"})


def test_create_sets_external_id_from_lei(db_session):
    request = submit_request(
        db_session,
        domain="Party",
        request_type="create",
        proposed_attributes={"name": "LEI Co", "country": "US", "lei": "UNIQUE-LEI-001"},
    )
    approve_request(db_session, request.id)

    created = db_session.query(MasterRecord).filter(MasterRecord.name == "LEI Co").one()
    assert created.external_id == "UNIQUE-LEI-001"
    assert "lei" not in created.attributes  # pulled out into external_id, not left in the JSON blob


def test_create_rejects_duplicate_lei_at_submit(db_session):
    _make_record(db_session, name="Has LEI Already")
    existing_with_lei = db_session.query(MasterRecord).filter(MasterRecord.name == "Has LEI Already").one()
    existing_with_lei.external_id = "DUP-LEI-001"
    db_session.flush()

    with pytest.raises(RequestValidationError):
        submit_request(
            db_session,
            domain="Party",
            request_type="create",
            proposed_attributes={"name": "Different Name", "country": "US", "lei": "DUP-LEI-001"},
        )


def test_update_rejects_duplicate_lei_introduced_after_submit(db_session):
    # Submit succeeds (no collision yet) — this tests approve_request's own
    # re-check, the backstop for the race where a different record claims
    # the same LEI between this request being submitted and approved.
    target = _make_record(db_session, name="Target Co")
    request = submit_request(
        db_session,
        domain="Party",
        request_type="update",
        target_record_id=target.id,
        proposed_attributes={"lei": "DUP-LEI-002"},
    )

    other = _make_record(db_session, name="Other Co")
    other.external_id = "DUP-LEI-002"
    db_session.flush()

    with pytest.raises(RequestValidationError):
        approve_request(db_session, request.id)


def test_update_requires_existing_target(db_session):
    with pytest.raises(RequestValidationError):
        submit_request(
            db_session,
            domain="Party",
            request_type="update",
            target_record_id=999999999,
            proposed_attributes={"city": "X"},
        )


def test_list_requests_filters_by_status(db_session):
    record = _make_record(db_session)
    pending_request = submit_request(db_session, domain="Party", request_type="delete", target_record_id=record.id)

    pending = list_requests(db_session, status="pending")
    assert any(r.id == pending_request.id for r in pending)

    reject_request(db_session, pending_request.id)
    still_pending = list_requests(db_session, status="pending")
    assert not any(r.id == pending_request.id for r in still_pending)
