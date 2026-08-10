"""
Single source of truth for Phase 1 seed data, shared by seed.py (Postgres)
and seed_graph.py (Neo4j) so both write about the same set of entities.

Real entities (name/LEI/address) were pulled from GLEIF's public API
(api.gleif.org) on 2026-08-10 — see memory: dataset-gleif-corporate-hierarchy.
Records marked "duplicate_of" are deliberately messy synthetic variants of a
real entity, used to exercise fuzzy/entity-resolution matching later.
Records marked "synthetic" don't exist in GLEIF at all — they model
Relsun's own commercial relationships (supplier/customer, site/location),
which GLEIF has no data for.
"""

ENTITIES = [
    # --- Alphabet Inc. corporate family (real, via GLEIF) ---
    {
        "name": "Alphabet Inc.",
        "domain": "Account",
        "attributes": {
            "lei": "5493006MHB84DD0ZWV18",
            "country": "US",
            "city": "Mountain View",
            "status": "customer",
            "source": "gleif",
        },
    },
    {
        "name": "Firebase, Inc.",
        "domain": "Account",
        "attributes": {
            "lei": "9845003D44CCA145CC76",
            "country": "US",
            "city": "Wilmington",
            "status": "customer",
            "source": "gleif",
        },
    },
    {
        "name": "Google UK Limited",
        "domain": "Party",
        "attributes": {
            "lei": "64886BIOSLNV78184624",
            "country": "GB",
            "city": "London",
            "status": "customer",
            "source": "gleif",
        },
    },
    {
        "name": "GOC International LLC",
        "domain": "Supplier",
        "attributes": {
            "lei": "984500DI9BZD41OF4781",
            "country": "US",
            "city": "Mountain View",
            "status": "active_supplier",
            "source": "gleif",
        },
    },
    {
        "name": "Google Payment Ireland Limited",
        "domain": "Supplier",
        "attributes": {
            "lei": "9845003AA4F14A013C44",
            "country": "IE",
            "city": "Dublin",
            "status": "active_supplier",
            "source": "gleif",
        },
    },
    {
        "name": "Google Switzerland GmbH",
        "domain": "Account",
        "attributes": {
            "lei": "984500B1C1A7S4898E77",
            "country": "CH",
            "city": "Zurich",
            "status": "customer",
            "source": "gleif",
        },
    },
    # --- Thoma Bravo / Cority Software (real, via GLEIF) — PE ownership example ---
    {
        "name": "Thoma Bravo, L.P.",
        "domain": "Party",
        "attributes": {
            "lei": "5493001G651ICQ33SN58",
            "country": "US",
            "city": "Chicago",
            "status": "n/a",
            "source": "gleif",
        },
    },
    {
        "name": "Cority Software Inc.",
        "domain": "Account",
        "attributes": {
            "lei": "549300CYIYJJX73J8I64",
            "country": "CA",
            "city": "Vancouver",
            "status": "prospect",
            "source": "gleif",
        },
    },
    # --- Standalone real entities, no reported GLEIF ownership edges ---
    {
        "name": "The Boeing Company",
        "domain": "Account",
        "attributes": {
            "lei": "RVHJWBXLJ1RFUBSY1F30",
            "country": "US",
            "city": "Wilmington",
            "status": "customer",
            "source": "gleif",
        },
    },
    {
        "name": "Nike, Inc.",
        "domain": "Party",
        "attributes": {
            "lei": "787RXPR0UX0O0XUXPZ81",
            "country": "US",
            "city": "Beaverton",
            "status": "n/a",
            "source": "gleif",
        },
    },
    # --- Deliberately messy near-duplicates (synthetic formatting drift) ---
    {
        "name": "Firebase Inc",
        "domain": "Account",
        "attributes": {
            "source": "synthetic_duplicate",
            "source_system": "Salesforce (import)",
            "duplicate_of": ("Firebase, Inc.", "Account"),
        },
    },
    {
        "name": "Firebase LLC",
        "domain": "Account",
        "attributes": {
            "source": "synthetic_duplicate",
            "source_system": "NetSuite (import)",
            "duplicate_of": ("Firebase, Inc.", "Account"),
        },
    },
    {
        "name": "Cority Software Incorporated",
        "domain": "Account",
        "attributes": {
            "source": "synthetic_duplicate",
            "source_system": "Manual entry",
            "duplicate_of": ("Cority Software Inc.", "Account"),
        },
    },
    {
        "name": "Google Payment Ireland Ltd",
        "domain": "Supplier",
        "attributes": {
            "source": "synthetic_duplicate",
            "source_system": "SAP (import)",
            "duplicate_of": ("Google Payment Ireland Limited", "Supplier"),
        },
    },
    # --- Synthetic locations (sites/facilities, not in GLEIF at all) ---
    {
        "name": "Firebase, Inc. — Mountain View Office",
        "domain": "Location",
        "attributes": {
            "source": "synthetic",
            "country": "US",
            "city": "Mountain View",
            "address": "1600 Amphitheatre Parkway, Mountain View, CA 94043",
            "belongs_to": ("Firebase, Inc.", "Account"),
        },
    },
    {
        "name": "Google UK Limited — London Office",
        "domain": "Location",
        "attributes": {
            "source": "synthetic",
            "country": "GB",
            "city": "London",
            "address": "1 St. Giles High Street, London WC2H 8AG",
            "belongs_to": ("Google UK Limited", "Party"),
        },
    },
    {
        "name": "GOC International LLC — Distribution Center",
        "domain": "Location",
        "attributes": {
            "source": "synthetic",
            "country": "US",
            "city": "Mountain View",
            "address": "1600 Amphitheatre Parkway, Mountain View, CA 94043",
            "belongs_to": ("GOC International LLC", "Supplier"),
        },
    },
]

# Real corporate ownership, as reported by GLEIF direct-parent/direct-children.
OWNERSHIP_EDGES = [
    ("Alphabet Inc.", "Account", "Firebase, Inc.", "Account"),
    ("Alphabet Inc.", "Account", "Google UK Limited", "Party"),
    ("Alphabet Inc.", "Account", "GOC International LLC", "Supplier"),
    ("Alphabet Inc.", "Account", "Google Payment Ireland Limited", "Supplier"),
    ("Alphabet Inc.", "Account", "Google Switzerland GmbH", "Account"),
    ("Thoma Bravo, L.P.", "Party", "Cority Software Inc.", "Account"),
]

# Synthetic commercial relationships within Relsun's own master data — GLEIF
# has no equivalent, this models what a real customer's MDM would capture.
COMMERCIAL_EDGES = [
    ("GOC International LLC", "Supplier", "Firebase, Inc.", "Account", "SUPPLIES_TO"),
    ("Google Payment Ireland Limited", "Supplier", "Google Switzerland GmbH", "Account", "SUPPLIES_TO"),
]
