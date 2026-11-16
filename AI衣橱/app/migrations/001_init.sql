BEGIN;

CREATE TABLE IF NOT EXISTS wardrobe_items (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT,
    image_path TEXT,
    category TEXT CHECK (category IN ('top', 'bottom', 'dress', 'outer', 'shoes', 'accessory')),
    sub TEXT,
    colors TEXT NOT NULL CHECK (json_valid(colors) AND json_type(colors) = 'array'),
    material TEXT,
    pattern TEXT,
    warmth INTEGER CHECK (warmth IS NULL OR (warmth BETWEEN 1 AND 5 AND typeof(warmth) = 'integer')),
    formality INTEGER CHECK (formality IS NULL OR (formality BETWEEN 1 AND 5 AND typeof(formality) = 'integer')),
    seasons TEXT NOT NULL CHECK (json_valid(seasons) AND json_type(seasons) = 'array'),
    confidence REAL CHECK (confidence BETWEEN 0 AND 1),
    needs_confirm INTEGER NOT NULL CHECK (needs_confirm IN (0, 1)),
    user_edited INTEGER NOT NULL CHECK (user_edited IN (0, 1)),
    created_at TEXT NOT NULL,
    sources TEXT NOT NULL CHECK (json_valid(sources) AND json_type(sources) = 'object')
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY NOT NULL,
    temp_c INTEGER NOT NULL CHECK (typeof(temp_c) = 'integer'),
    occasion TEXT NOT NULL CHECK (occasion IN ('commute', 'date', 'weekend', 'client_meeting')),
    formality_target TEXT NOT NULL CHECK (
        json_valid(formality_target) AND json_type(formality_target) = 'array'
        AND json_array_length(formality_target) = 2
        AND json_extract(formality_target, '$[0]') BETWEEN 1 AND 5
        AND json_extract(formality_target, '$[1]') BETWEEN 1 AND 5
        AND json_extract(formality_target, '$[0]') <= json_extract(formality_target, '$[1]')
    ),
    excluded_items TEXT NOT NULL CHECK (json_valid(excluded_items) AND json_type(excluded_items) = 'array'),
    status TEXT NOT NULL CHECK (status IN ('ok', 'degraded', 'failed')),
    fallback_type TEXT CHECK (fallback_type IN ('timeout', 'parse_fail', 'no_compliant_set')),
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0 AND typeof(latency_ms) = 'integer'),
    prompt_version TEXT NOT NULL,
    sources TEXT NOT NULL CHECK (json_valid(sources) AND json_type(sources) = 'object')
);

CREATE TABLE IF NOT EXISTS outfit_sets (
    id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 3 AND typeof(rank) = 'integer'),
    reason TEXT NOT NULL,
    shortage_hint TEXT,
    degraded INTEGER NOT NULL CHECK (degraded IN (0, 1)),
    sources TEXT NOT NULL CHECK (json_valid(sources) AND json_type(sources) = 'object'),
    UNIQUE (session_id, rank)
);

CREATE TABLE IF NOT EXISTS outfit_items (
    set_id TEXT NOT NULL REFERENCES outfit_sets(id),
    item_id TEXT NOT NULL REFERENCES wardrobe_items(id),
    slot TEXT NOT NULL CHECK (slot IN ('top', 'bottom', 'dress', 'outer', 'shoes', 'accessory')),
    sources TEXT NOT NULL CHECK (json_valid(sources) AND json_type(sources) = 'object'),
    PRIMARY KEY (set_id, item_id),
    UNIQUE (set_id, slot)
);

COMMIT;
