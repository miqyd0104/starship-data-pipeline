
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
    model TEXT PRIMARY KEY,
    cost_in_credits TEXT, length TEXT, max_atmosphering_speed TEXT,
    crew TEXT, passengers TEXT, cargo_capacity TEXT, consumables TEXT,
    hyperdrive_rating TEXT, MGLT TEXT, starship_class TEXT
);
CREATE TABLE IF NOT EXISTS manufacturers (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS model_manufacturers (
    model TEXT REFERENCES models(model),
    manufacturer TEXT REFERENCES manufacturers(name),
    PRIMARY KEY (model, manufacturer)
);
CREATE TABLE IF NOT EXISTS starships (
    starship_url TEXT PRIMARY KEY, name TEXT NOT NULL,
    model TEXT NOT NULL REFERENCES models(model), created TEXT, edited TEXT
);
CREATE TABLE IF NOT EXISTS starship_pilots (
    starship_url TEXT REFERENCES starships(starship_url),
    character_id TEXT REFERENCES characters(character_id),
    PRIMARY KEY (starship_url, character_id)
);
CREATE TABLE IF NOT EXISTS films (film_url TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS starship_films (
    starship_url TEXT REFERENCES starships(starship_url),
    film_url TEXT REFERENCES films(film_url),
    PRIMARY KEY (starship_url, film_url)
);
