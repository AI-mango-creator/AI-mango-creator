CREATE TABLE IF NOT EXISTS body_profiles (
    owner_id TEXT PRIMARY KEY NOT NULL,
    height_cm REAL CHECK (height_cm IS NULL OR height_cm > 0),
    weight_kg REAL CHECK (weight_kg IS NULL OR weight_kg > 0),
    body_shape TEXT CHECK (body_shape IS NULL OR body_shape IN ('X','A','TY','H','O')),
    sources TEXT NOT NULL CHECK (json_valid(sources))
);
