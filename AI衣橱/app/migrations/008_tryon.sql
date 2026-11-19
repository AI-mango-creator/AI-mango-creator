CREATE TABLE IF NOT EXISTS experience_products (
 owner_id TEXT NOT NULL DEFAULT 'catalog' CHECK(owner_id='catalog'),
 id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL CHECK(category IN ('tops','bottoms','one-pieces')),
 image_path TEXT NOT NULL, source_label TEXT NOT NULL, rights_note TEXT NOT NULL,
 content_hash TEXT NOT NULL, created_at REAL NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources))
);
CREATE TABLE IF NOT EXISTS tryon_jobs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 product_id TEXT NOT NULL REFERENCES experience_products(id),
 status TEXT NOT NULL CHECK(status IN ('submitting','starting','in_queue','processing','completed','failed','unknown','timed_out')),
 provider_task_id TEXT, portrait_path TEXT, result_path TEXT, error_kind TEXT,
 created_at REAL NOT NULL, latency_ms INTEGER NOT NULL DEFAULT 0,
 polls INTEGER NOT NULL DEFAULT 0, last_poll REAL NOT NULL DEFAULT 0,
 sources TEXT NOT NULL CHECK(json_valid(sources)), UNIQUE(owner_id,request_id)
);
CREATE INDEX IF NOT EXISTS tryon_owner_created ON tryon_jobs(owner_id,created_at DESC);
CREATE TABLE IF NOT EXISTS tryon_daily_quotas (
 owner_hash TEXT NOT NULL, day TEXT NOT NULL, expires_at TEXT NOT NULL,
 tryon INTEGER NOT NULL DEFAULT 0 CHECK(tryon BETWEEN 0 AND 3),
 tryon_request_hashes TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(tryon_request_hashes)),
 PRIMARY KEY(owner_hash,day)
);
