"""
Streaming parsers for GLEIF's bulk concatenated files (LEI-CDF v3.1 for
entities, RR-CDF v2.1 for relationships). Both are large XML documents
(Level 1 is ~8.3GB uncompressed for ~3.4M records) so these use
ElementTree.iterparse and drop each record element (and remove it from its
parent) as soon as it's been yielded, keeping memory bounded regardless of
file size. Callers pass the already-open zip member stream.
"""

from collections.abc import Iterator
from xml.etree import ElementTree as ET

LEI_NS = "http://www.gleif.org/data/schema/leidata/2016"
RR_NS = "http://www.gleif.org/data/schema/rr/2016"

# Level 2 reports several relationship types (accounting consolidation,
# international branches, funds, etc). Per DATA_STRATEGY.md we only want the
# ownership-shaped ones: direct parent and ultimate parent.
OWNERSHIP_RELATIONSHIP_TYPES = {"IS_DIRECTLY_CONSOLIDATED_BY", "IS_ULTIMATELY_CONSOLIDATED_BY"}


def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _text(elem: ET.Element | None, path: str) -> str | None:
    if elem is None:
        return None
    found = elem.find(path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _stream_records(stream, records_tag: str, record_tag: str) -> Iterator[ET.Element]:
    context = ET.iterparse(stream, events=("start", "end"))
    container = None
    for event, elem in context:
        if event == "start":
            if elem.tag == records_tag:
                container = elem
            continue
        if elem.tag != record_tag:
            continue
        yield elem
        elem.clear()
        if container is not None:
            container.remove(elem)


def iter_entities(stream) -> Iterator[dict]:
    """Yield one dict per LEIRecord: lei, name, country, city, hq_country,
    hq_city, entity_category, legal_form, status. Records missing an LEI or
    legal name (shouldn't happen, but the format doesn't guarantee it) are
    skipped."""
    tag = lambda local: _tag(LEI_NS, local)  # noqa: E731
    entity_path = tag("Entity")
    legal_addr_path = f"{entity_path}/{tag('LegalAddress')}"
    hq_addr_path = f"{entity_path}/{tag('HeadquartersAddress')}"

    for elem in _stream_records(stream, tag("LEIRecords"), tag("LEIRecord")):
        lei = _text(elem, tag("LEI"))
        name = _text(elem, f"{entity_path}/{tag('LegalName')}")
        if not lei or not name:
            continue

        yield {
            "lei": lei,
            "name": name,
            "country": _text(elem, f"{legal_addr_path}/{tag('Country')}"),
            "city": _text(elem, f"{legal_addr_path}/{tag('City')}"),
            "hq_country": _text(elem, f"{hq_addr_path}/{tag('Country')}"),
            "hq_city": _text(elem, f"{hq_addr_path}/{tag('City')}"),
            "entity_category": _text(elem, f"{entity_path}/{tag('EntityCategory')}"),
            "legal_form": _text(elem, f"{entity_path}/{tag('LegalForm')}/{tag('EntityLegalFormCode')}"),
            "status": _text(elem, f"{entity_path}/{tag('EntityStatus')}"),
        }


def iter_ownership_edges(stream) -> Iterator[dict]:
    """Yield one dict per ACTIVE direct/ultimate-parent relationship: parent_lei,
    child_lei, basis ('direct' or 'ultimate'). GLEIF encodes the edge as
    StartNode IS_..._CONSOLIDATED_BY EndNode, i.e. StartNode is the child and
    EndNode is the parent."""
    tag = lambda local: _tag(RR_NS, local)  # noqa: E731
    rel_path = tag("Relationship")

    for elem in _stream_records(stream, tag("RelationshipRecords"), tag("RelationshipRecord")):
        status = _text(elem, f"{rel_path}/{tag('RelationshipStatus')}")
        rel_type = _text(elem, f"{rel_path}/{tag('RelationshipType')}")
        if status != "ACTIVE" or rel_type not in OWNERSHIP_RELATIONSHIP_TYPES:
            continue

        child_lei = _text(elem, f"{rel_path}/{tag('StartNode')}/{tag('NodeID')}")
        parent_lei = _text(elem, f"{rel_path}/{tag('EndNode')}/{tag('NodeID')}")
        if not child_lei or not parent_lei:
            continue

        yield {
            "parent_lei": parent_lei,
            "child_lei": child_lei,
            "basis": "direct" if rel_type == "IS_DIRECTLY_CONSOLIDATED_BY" else "ultimate",
        }
