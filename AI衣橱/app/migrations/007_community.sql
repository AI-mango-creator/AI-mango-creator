CREATE TABLE IF NOT EXISTS community_authors (
 id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL UNIQUE CHECK(length(owner_id)=36),
 nickname TEXT NOT NULL, created_at TEXT NOT NULL, sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object')
);
CREATE TABLE IF NOT EXISTS community_posts (
 id TEXT PRIMARY KEY NOT NULL, author_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('photo','outfit','poll','buy')), title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 80),
 body TEXT NOT NULL CHECK(length(body)<=2000), created_at TEXT NOT NULL, draft_id TEXT NOT NULL,
 request_hash TEXT NOT NULL CHECK(length(request_hash)=64), sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'),
 UNIQUE(author_id,draft_id)
);
CREATE INDEX IF NOT EXISTS community_posts_feed ON community_posts(created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS community_posts_author ON community_posts(author_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS community_media (
 id TEXT PRIMARY KEY NOT NULL, post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL CHECK(position>=0), file_path TEXT NOT NULL,
 mime_type TEXT NOT NULL CHECK(mime_type IN ('image/jpeg','image/png','image/webp')), caption TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'),
 UNIQUE(post_id,position), UNIQUE(id,post_id)
);
CREATE TABLE IF NOT EXISTS community_likes (
 post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 author_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'), PRIMARY KEY(post_id,author_id)
);
CREATE TABLE IF NOT EXISTS community_follows (
 follower_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE,
 followee_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'),
 PRIMARY KEY(follower_id,followee_id), CHECK(follower_id<>followee_id)
);
CREATE TABLE IF NOT EXISTS community_comments (
 id TEXT PRIMARY KEY NOT NULL, post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 author_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE,
 text TEXT NOT NULL CHECK(length(trim(text)) BETWEEN 1 AND 500), client_id TEXT NOT NULL, created_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'), UNIQUE(author_id,client_id)
);
CREATE INDEX IF NOT EXISTS community_comments_feed ON community_comments(post_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS community_poll_options (
 id TEXT PRIMARY KEY NOT NULL, post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 3), label TEXT NOT NULL, media_id TEXT,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'), UNIQUE(post_id,position), UNIQUE(id,post_id),
 FOREIGN KEY(media_id,post_id) REFERENCES community_media(id,post_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS community_votes (
 post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
 author_id TEXT NOT NULL REFERENCES community_authors(id) ON DELETE CASCADE,
 option_id TEXT NOT NULL, created_at TEXT NOT NULL,
 sources TEXT NOT NULL CHECK(json_valid(sources) AND json_type(sources)='object'), PRIMARY KEY(post_id,author_id),
 FOREIGN KEY(option_id,post_id) REFERENCES community_poll_options(id,post_id) ON DELETE CASCADE
);
