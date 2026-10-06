"""Tiny city lookup so "long distance" is a computed, explainable fact (not a guess)."""

from math import asin, cos, radians, sin, sqrt

# Candidate/client cities that appear in the mock data. Unknown cities => distance unknown.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "delhi": (28.6139, 77.2090),
    "gurugram": (28.4595, 77.0266),
    "bengaluru": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
}

# Anything beyond this is treated as "long distance" for repeated-rejection matching.
LONG_DISTANCE_KM = 200.0


def normalise_city(name: str | None) -> str | None:
    if not name:
        return None
    return name.split(",")[0].strip().lower() or None


def distance_km(a: str | None, b: str | None) -> float | None:
    """Great-circle distance in km, or None if either city is unknown."""
    ka, kb = normalise_city(a), normalise_city(b)
    if ka is None or kb is None:
        return None
    if ka == kb:
        return 0.0
    if ka not in CITY_COORDS or kb not in CITY_COORDS:
        return None
    lat1, lon1 = map(radians, CITY_COORDS[ka])
    lat2, lon2 = map(radians, CITY_COORDS[kb])
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def same_city(a: str | None, b: str | None) -> bool | None:
    ka, kb = normalise_city(a), normalise_city(b)
    if ka is None or kb is None:
        return None
    return ka == kb
