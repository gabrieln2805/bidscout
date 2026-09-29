"""The SQLite schema.

Ground rule 3: the raw JSON is a column, not a derived table. The reader has
been rewritten several times and each rewrite was replayed from these rows
instead of polling the portal again. ``notices.raw`` and
``sections.section3_raw`` must never be dropped or truncated.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS buyers (
    name        TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notices (
    c_notice_id         TEXT PRIMARY KEY,
    notice_no           TEXT NOT NULL,
    init_notice_id      TEXT,
    title               TEXT NOT NULL,
    buyer               TEXT,
    cpv                 TEXT,
    estimated_value_ron TEXT,
    published_at        TEXT,
    deadline_at         TEXT,
    notice_type_id      INTEGER,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    raw                 TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS notices_published ON notices (published_at);
CREATE INDEX IF NOT EXISTS notices_cpv ON notices (cpv);

-- One row per notice whose Section 3 we have fetched. A notice with no row
-- here has not been read in full, and must be skipped by the scorer rather
-- than scored as if it had no requirements.
CREATE TABLE IF NOT EXISTS sections (
    c_notice_id   TEXT PRIMARY KEY REFERENCES notices (c_notice_id),
    fetched_at    TEXT NOT NULL,
    section3_raw  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    c_notice_id   TEXT NOT NULL REFERENCES notices (c_notice_id),
    guid          TEXT NOT NULL,
    name          TEXT NOT NULL,
    code          TEXT,
    doc_group     TEXT,
    PRIMARY KEY (c_notice_id, guid)
);

CREATE TABLE IF NOT EXISTS scores (
    c_notice_id  TEXT NOT NULL REFERENCES notices (c_notice_id),
    company      TEXT NOT NULL,
    decision     TEXT NOT NULL,
    score        INTEGER NOT NULL,
    reasons      TEXT NOT NULL,
    unresolved   TEXT NOT NULL,
    scored_at    TEXT NOT NULL,
    PRIMARY KEY (c_notice_id, company)
);
"""
