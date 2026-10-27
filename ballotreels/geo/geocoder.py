"""Resolves a free-text address to exact districts with the Census
Geocoder (docs/ARCHITECTURE.md), falling back to point-in-polygon on the
built shapes when the geocoder's response is missing a layer: the
shapes are simplified for phones, so that fallback is not exact near a
border, which is why it is a fallback and not the primary path.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Callable

from .build import STATE_FIPS
from .lookup import GeoData, ocd_id
from .shapes import point_in_polygon

# Layer names are matched by substring, not equality, since the exact
# name (e.g. "119th Congressional Districts") changes with the vintage.
LAYER_SUBSTRINGS = {
    "cd": "Congressional Districts",
    "sldu": "Legislative Districts - Upper",
    "sldl": "Legislative Districts - Lower",
    "county": "Counties",
}


class AddressLookupError(Exception):
    """An address could not be resolved."""


class AddressNotFound(AddressLookupError):
    pass


class GeocoderError(AddressLookupError):
    pass


def _find_layer(geographies: dict[str, Any], substring: str) -> list | None:
    for name, features in geographies.items():
        if substring in name:
            return features
    return None


def _address_state_fips(geographies: dict[str, Any]) -> str | None:
    """The matched address's 2-digit state FIPS, from the "States" layer
    or else the prefix of any district GEOID; None if there is neither."""
    states = geographies.get("States")
    if states:
        return str(states[0].get("GEOID", ""))[:2] or None
    for features in geographies.values():
        for feat in features:
            geoid = str(feat.get("GEOID", ""))
            if len(geoid) >= 2:
                return geoid[:2]
    return None


def _fallback_point_in_polygon(geo: GeoData, kind: str,
                               point: tuple[float, float]
                               ) -> list[dict[str, str]]:
    entries = []
    for oid, geom in geo.district_shapes.items():
        if f"/{kind}:" not in oid:
            continue
        rings = [[tuple(p) for p in ring] for ring in geom["coordinates"]]
        if point_in_polygon(point, rings):
            entries.append({"ocd_id": oid, "name": geo.names.get(oid, oid)})
    return entries


def lookup_address(address: str, fetch: Callable[[str], str], base_url: str,
                   geo: GeoData | None, state_abbr: str) -> dict[str, Any]:
    """`{"matched_address": str, "kinds": {kind: [{"ocd_id", "name"}]}}`,
    or raises AddressNotFound / GeocoderError."""
    query = urllib.parse.urlencode({
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "all",
        "format": "json",
    })
    url = f"{base_url}/geographies/onelineaddress?{query}"
    try:
        text = fetch(url)
    except Exception as e:
        raise GeocoderError(f"the geocoder could not be reached: {e}") from None
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise GeocoderError(f"bad geocoder response: {e}") from None

    matches = doc.get("result", {}).get("addressMatches", [])
    if not matches:
        raise AddressNotFound("We couldn't find that address.")
    match = matches[0]
    geographies = match.get("geographies", {})
    coords = match.get("coordinates", {})
    point = (coords.get("x"), coords.get("y"))

    # ocd_id() drops the GEOID's state digits, so an address in another
    # state would otherwise resolve to this state's district numbers.
    found_fips = _address_state_fips(geographies)
    if found_fips is not None and found_fips != STATE_FIPS.get(state_abbr):
        raise AddressNotFound("We couldn't find that address.")

    kinds: dict[str, list[dict[str, str]]] = {
        "state": [{"ocd_id": f"ocd-division/country:us/state:{state_abbr}",
                  "name": "Statewide"}],
    }
    for kind, substring in LAYER_SUBSTRINGS.items():
        features = _find_layer(geographies, substring)
        if features is not None:
            entries = []
            for feat in features:
                # Counties: NAME is "Sacramento County", BASENAME is
                # "Sacramento", which is what the TIGER shapefile's NAME
                # (and so the zip path's OCD-ID) uses.
                name = (feat.get("BASENAME") or feat.get("NAME")
                        if kind == "county" else feat.get("NAME"))
                result = ocd_id(kind, feat.get("GEOID", ""), state_abbr, name)
                if result:
                    entries.append({"ocd_id": result[0], "name": result[1]})
            if entries:
                kinds[kind] = entries
        elif geo is not None and point[0] is not None and point[1] is not None:
            entries = _fallback_point_in_polygon(geo, kind, point)
            if entries:
                kinds[kind] = entries
    return {"matched_address": match.get("matchedAddress", address),
           "kinds": kinds}
