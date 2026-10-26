"""Pure transformation: retain only documented, useful analytical fields."""

from __future__ import annotations

import math

from .source import DataQualityError, canonical_url


def number(value: object) -> float | None:
    """Unknown values remain null; invalid or negative measures are rejected."""
    if value is None or str(value).strip().lower() in {"unknown", "n/a", "none", ""}:
        return None
    try:
        result = float(str(value).replace(",", ""))
    except ValueError as exc:
        raise DataQualityError("Invalid numeric measurement") from exc
    if not math.isfinite(result) or result < 0:
        raise DataQualityError("Measurement must be finite and non-negative")
    return result


def text(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DataQualityError(f"Missing or invalid {key}")
    return value.strip()


def prepare(people: list[dict], ships: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate the entire batch before any MongoDB writes occur.

    Source URLs, rather than names, link pilots. Two people may share a name.
    Raw descriptions and copyrighted film text are outside the stored projection.
    """
    clean_people, clean_ships, person_urls, ship_urls = [], [], set(), set()
    for row in people:
        url = canonical_url(text(row, "url"), "people")
        if url in person_urls:
            raise DataQualityError("Duplicate person source URL")
        person_urls.add(url)
        clean_people.append(
            {
                "source_url": url,
                "name": text(row, "name"),
                "height_cm": number(row.get("height")),
                "mass_kg": number(row.get("mass")),
            }
        )
    for row in ships:
        url = canonical_url(text(row, "url"), "starships")
        if url in ship_urls:
            raise DataQualityError("Duplicate starship source URL")
        ship_urls.add(url)
        raw_pilots = row.get("pilots")
        if not isinstance(raw_pilots, list):
            raise DataQualityError("Pilots must be a list")
        pilots = [canonical_url(p, "people") for p in raw_pilots]
        if len(set(pilots)) != len(pilots) or not set(pilots).issubset(person_urls):
            raise DataQualityError("Duplicate or unresolved pilot reference")
        clean_ships.append(
            {
                "source_url": url,
                "name": text(row, "name"),
                "model": text(row, "model"),
                "length_m": number(row.get("length")),
                "manufacturer": text(row, "manufacturer"),
                "pilot_urls": pilots,
            }
        )
    if not clean_people or not clean_ships:
        raise DataQualityError("People and starship datasets must both be nonempty")
    return clean_people, clean_ships
