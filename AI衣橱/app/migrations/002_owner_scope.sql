ALTER TABLE wardrobe_items ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy' CHECK (owner_id='legacy' OR length(owner_id)=36);
ALTER TABLE sessions ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy' CHECK (owner_id='legacy' OR length(owner_id)=36);
ALTER TABLE outfit_sets ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy' CHECK (owner_id='legacy' OR length(owner_id)=36);
ALTER TABLE outfit_items ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy' CHECK (owner_id='legacy' OR length(owner_id)=36);

UPDATE wardrobe_items SET sources=json_set(sources, '$.owner_id', 'derived');
UPDATE sessions SET sources=json_set(sources, '$.owner_id', 'derived');
UPDATE outfit_sets SET sources=json_set(sources, '$.owner_id', 'derived');
UPDATE outfit_items SET sources=json_set(sources, '$.owner_id', 'derived');

CREATE INDEX wardrobe_items_owner ON wardrobe_items(owner_id);
CREATE INDEX sessions_owner ON sessions(owner_id);
CREATE INDEX outfit_sets_owner ON outfit_sets(owner_id);
CREATE INDEX outfit_items_owner ON outfit_items(owner_id);

CREATE TABLE daily_quotas (
    owner_hash TEXT NOT NULL CHECK (length(owner_hash)=64 AND owner_hash NOT GLOB '*[^0-9a-f]*'),
    day TEXT NOT NULL,
    recognition INTEGER NOT NULL DEFAULT 0 CHECK (recognition BETWEEN 0 AND 20),
    composition INTEGER NOT NULL DEFAULT 0 CHECK (composition BETWEEN 0 AND 30),
    expires_at TEXT NOT NULL,
    PRIMARY KEY (owner_hash, day)
);

CREATE TRIGGER outfit_sets_owner_insert BEFORE INSERT ON outfit_sets
WHEN NOT EXISTS (SELECT 1 FROM sessions WHERE id=NEW.session_id AND owner_id=NEW.owner_id)
BEGIN
    SELECT RAISE(ABORT, 'FOREIGN KEY owner mismatch');
END;

CREATE TRIGGER outfit_items_owner_insert BEFORE INSERT ON outfit_items
WHEN NOT EXISTS (SELECT 1 FROM outfit_sets WHERE id=NEW.set_id AND owner_id=NEW.owner_id) OR NOT EXISTS (SELECT 1 FROM wardrobe_items WHERE id=NEW.item_id AND owner_id=NEW.owner_id)
BEGIN
    SELECT RAISE(ABORT, 'FOREIGN KEY owner mismatch');
END;

CREATE TRIGGER outfit_sets_owner_update BEFORE UPDATE ON outfit_sets
WHEN NOT EXISTS (SELECT 1 FROM sessions WHERE id=NEW.session_id AND owner_id=NEW.owner_id)
BEGIN
    SELECT RAISE(ABORT, 'FOREIGN KEY owner mismatch');
END;

CREATE TRIGGER outfit_items_owner_update BEFORE UPDATE ON outfit_items
WHEN NOT EXISTS (SELECT 1 FROM outfit_sets WHERE id=NEW.set_id AND owner_id=NEW.owner_id) OR NOT EXISTS (SELECT 1 FROM wardrobe_items WHERE id=NEW.item_id AND owner_id=NEW.owner_id)
BEGIN
    SELECT RAISE(ABORT, 'FOREIGN KEY owner mismatch');
END;
