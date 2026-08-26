"""
Party Request Agent — the only new agent in the Party Request branch (see
the build plan). Gathers what's needed for a create/update/delete request
conversationally, then saves it as a pending proposal — nothing here can
ever write to master_records. That write only happens via
requests.approve_request(), called from POST /requests/{id}/approve when
a human clicks Approve in the Review Queue, never from agent code.

No Search/Compare tools in this pass — name-to-ID resolution for
update/delete is the Master Data Agent's job (it holds Search), the same
pattern already used for Compare.

Recommendation sub-agent wired in 2026-08-20: web-search-only enrichment
for now (see recommendation_agent.py's own docstring for exactly what
that does and doesn't cover yet — no internal graph, no D&B, no
ownership-chain reasoning). The full graph-aware, sales-acceleration
Recommendation Agent from AGENT_INVENTORY.md is still its own future
scoping task, not delivered by this pass.
"""

from sqlalchemy.orm import Session

from app.agents.framework import Agent, Tool
from app.agents.recommendation_agent import get_recommendation_tool
from app.requests import (
    RequestValidationError,
    get_request,
    list_requests,
    submit_request,
)

PARTY_REQUEST_INSTRUCTIONS = (
    "You are the Party Request Agent for an MDM (master data management) "
    "platform. Your job is to gather what's needed to propose a create, "
    "update, or delete of a Party record (customers, suppliers, third "
    "parties), then submit it — you never approve, reject, or write "
    "directly to master data yourself. Every request you submit lands as "
    "pending in the Review Queue, and only becomes real once a human "
    "reviews it there. "
    "\n\nFor a CREATE: name and country are both REQUIRED — do not submit "
    "without both, ask if either is missing. LEI is optional, but if the "
    "user gives one, include it: it's checked against every existing "
    "record, and submission will be rejected if it's already in use "
    "(that means this is the same legal entity, not a new one — tell the "
    "user that plainly rather than retrying). Ask for other relevant "
    "fields too (e.g. city) but don't demand an exhaustive form beyond "
    "name/country. When you need several fields at once, ask for them in "
    "one compact list (e.g. 'Name, Country, City, LEI (optional)?') "
    "rather than one at a time, to keep the exchange short. "
    "\n\nFor an UPDATE or DELETE: you need the target record's ID. If the "
    "user only gave a name, you cannot look it up yourself — say so and "
    "ask for the ID, or ask them to search for it first. Never guess an "
    "ID. An update that changes the LEI is checked the same way a create "
    "is — rejected if that LEI already belongs to a different record. "
    "\n\nOnce you have what you need, call submit_party_request. If it "
    "reports a validation problem (missing field, or a duplicate LEI), "
    "relay that reason to the user plainly — don't retry blindly. After "
    "a successful submit, tell the user plainly that it's pending review "
    "— not done, not applied. Use check_request_status to answer "
    "questions about a request's current state; you cannot change that "
    "state yourself, only report it. Beyond an exact LEI match, you have "
    "no way to check whether a proposed record might be a duplicate of "
    "something existing — don't claim to have checked beyond that. "
    "Whenever you mention a record that has a known id — a "
    "target_record_id for an update/delete, or a record a duplicate LEI "
    "check surfaced — format it as a markdown link in the exact form "
    "[Name](record:ID) if you know its name, or [Record ID](record:ID) if "
    "you only know the id, so the person reading your reply can click "
    "straight through to it."
    "\n\nFor a CREATE, if the user gives just a company name and you think "
    "a quick web lookup would help (e.g. they don't know the country, or "
    "you want to double check an address), you may call get_recommendation "
    "with that name. It returns a suggestion from a live web search, not a "
    "verified fact — offer it to the user as something to confirm or "
    "correct ('I found X, does that look right?'), never fill it in "
    "silently or submit it without them agreeing. Don't call it for every "
    "request — only when it would actually save the user a step, e.g. "
    "they haven't already given you the field it would find."
)


def _submit_handler(
    request_type: str,
    target_record_id: int | None = None,
    proposed_attributes: dict | None = None,
    *,
    session: Session,
    current_user_id: int | None = None,
    **_ignored,
) -> str:
    try:
        request = submit_request(
            session,
            domain="Party",
            request_type=request_type,
            target_record_id=target_record_id,
            proposed_attributes=proposed_attributes,
            submitted_by_id=current_user_id,
        )
    except RequestValidationError as exc:
        return f"Could not submit: {exc}"
    return f"Submitted as request #{request.id}, status=pending. It will only take effect once approved in the Review Queue."


def _format_request(request) -> str:
    parts = [f"Request #{request.id}: {request.request_type} ({request.domain}), status={request.status}"]
    if request.target_record_id:
        parts.append(f"target_record_id={request.target_record_id}")
    if request.proposed_attributes:
        parts.append(f"proposed={request.proposed_attributes}")
    if request.decision_note:
        parts.append(f"decision_note={request.decision_note!r}")
    return ", ".join(parts)


def _status_handler(request_id: int | None = None, *, session: Session, **_ignored) -> str:
    if request_id is not None:
        request = get_request(session, request_id)
        return _format_request(request) if request else f"No request found with id {request_id}."
    recent = list_requests(session)[:5]
    return "\n".join(_format_request(r) for r in recent) if recent else "No requests have been submitted yet."


submit_party_request_tool = Tool(
    name="submit_party_request",
    description="Save a proposed Party create/update/delete as a pending request in the Review Queue. Does not apply it.",
    input_schema={
        "type": "object",
        "properties": {
            "request_type": {"type": "string", "enum": ["create", "update", "delete"]},
            "target_record_id": {
                "type": "integer",
                "description": "The existing record's id. Required for update/delete, omit for create.",
            },
            "proposed_attributes": {
                "type": "object",
                "description": (
                    "For create: must include 'name' and 'country'; 'lei' is optional but checked for "
                    "duplicates against every existing record if given, plus any other fields (e.g. city). "
                    "For update: only the fields being changed (including 'lei', if changing it — same "
                    "duplicate check applies). Omit for delete."
                ),
            },
        },
        "required": ["request_type"],
    },
    handler=_submit_handler,
)

check_request_status_tool = Tool(
    name="check_request_status",
    description="Look up a specific request by id, or list the most recent requests if no id is given. Read-only.",
    input_schema={
        "type": "object",
        "properties": {
            "request_id": {"type": "integer", "description": "Specific request id. Omit to see recent requests."}
        },
    },
    handler=_status_handler,
)

party_request_agent = Agent(
    name="party-request",
    instructions=PARTY_REQUEST_INSTRUCTIONS,
    tools=[submit_party_request_tool, check_request_status_tool, get_recommendation_tool],
)
