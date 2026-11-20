CREATE TABLE IF NOT EXISTS personal_settings (
 owner_id TEXT PRIMARY KEY NOT NULL CHECK(length(owner_id)=36), nickname TEXT NOT NULL CHECK(length(trim(nickname)) BETWEEN 1 AND 24),
 avatar_path TEXT, avatar_version TEXT NOT NULL, created_at TEXT NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources))
);
CREATE TABLE IF NOT EXISTS point_entries (
 id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL CHECK(length(owner_id)=36), day TEXT NOT NULL,
 delta INTEGER NOT NULL CHECK(delta=10), reason TEXT NOT NULL CHECK(reason='daily_visit'), created_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources)), UNIQUE(owner_id,day,reason)
);
CREATE TABLE IF NOT EXISTS point_daily_claims (
 owner_hash TEXT NOT NULL CHECK(length(owner_hash)=64), day TEXT NOT NULL, expires_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources)), PRIMARY KEY(owner_hash,day)
);
CREATE TABLE IF NOT EXISTS personal_favorites (
 owner_id TEXT NOT NULL CHECK(length(owner_id)=36), post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources)), PRIMARY KEY(owner_id,post_id)
);
CREATE TABLE IF NOT EXISTS personal_ootds (
 id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL CHECK(length(owner_id)=36), client_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 worn_on TEXT NOT NULL, title TEXT NOT NULL CHECK(length(title)<=80), note TEXT NOT NULL CHECK(length(note)<=500),
 kind TEXT NOT NULL CHECK(kind IN ('photo','outfit')), photo_path TEXT, set_id TEXT REFERENCES outfit_sets(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources)), UNIQUE(owner_id,client_id),
 CHECK((kind='photo' AND photo_path IS NOT NULL AND set_id IS NULL) OR (kind='outfit' AND photo_path IS NULL))
);
CREATE TRIGGER IF NOT EXISTS personal_ootd_owner_insert BEFORE INSERT ON personal_ootds
WHEN NEW.set_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM outfit_sets WHERE id=NEW.set_id AND owner_id=NEW.owner_id)
BEGIN SELECT RAISE(ABORT,'FOREIGN KEY owner mismatch'); END;
CREATE TRIGGER IF NOT EXISTS personal_ootd_owner_update BEFORE UPDATE ON personal_ootds
WHEN NEW.set_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM outfit_sets WHERE id=NEW.set_id AND owner_id=NEW.owner_id)
BEGIN SELECT RAISE(ABORT,'FOREIGN KEY owner mismatch'); END;
CREATE TABLE IF NOT EXISTS personal_feedback (
 id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL CHECK(length(owner_id)=36), client_id TEXT NOT NULL, request_hash TEXT NOT NULL,
 category TEXT NOT NULL CHECK(category IN ('feedback','complaint')), text TEXT NOT NULL CHECK(length(trim(text)) BETWEEN 1 AND 1000),
 created_at TEXT NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources)), UNIQUE(owner_id,client_id)
);
CREATE TABLE IF NOT EXISTS personal_write_receipts (
 token_hash TEXT PRIMARY KEY NOT NULL, owner_hash TEXT NOT NULL, purpose TEXT NOT NULL CHECK(purpose IN ('ootd','feedback','avatar','settings','favorite','clear')),
 day TEXT NOT NULL, expires_at REAL NOT NULL, state TEXT NOT NULL CHECK(state IN ('issued','consumed','revoked')),
 payload_hash TEXT, sources TEXT NOT NULL CHECK(json_valid(sources))
);
CREATE INDEX IF NOT EXISTS personal_ootds_feed ON personal_ootds(owner_id,worn_on DESC,id DESC);
CREATE INDEX IF NOT EXISTS personal_receipts_owner ON personal_write_receipts(owner_hash);
CREATE INDEX IF NOT EXISTS point_entries_owner ON point_entries(owner_id,day DESC);
