
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS people (
  source_url TEXT PRIMARY KEY, name TEXT NOT NULL,
  height_cm REAL CHECK(height_cm >= 0), mass_kg REAL CHECK(mass_kg >= 0)
);
CREATE TABLE IF NOT EXISTS models (
  model_id TEXT PRIMARY KEY, model TEXT NOT NULL,
  manufacturer_attribution TEXT NOT NULL, length_m REAL CHECK(length_m >= 0)
);
CREATE TABLE IF NOT EXISTS starships (
  source_url TEXT PRIMARY KEY, name TEXT NOT NULL,
  model_id TEXT NOT NULL REFERENCES models(model_id)
);
CREATE TABLE IF NOT EXISTS starship_pilots (
  starship_url TEXT NOT NULL REFERENCES starships(source_url),
  person_url TEXT NOT NULL REFERENCES people(source_url),
  PRIMARY KEY (starship_url, person_url)
);
