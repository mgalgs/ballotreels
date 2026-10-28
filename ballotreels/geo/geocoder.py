"""Resolves a free-text address to exact districts with the Census
Geocoder (docs/ARCHITECTURE.md), falling back to point-in-polygon on the
built shapes when the geocoder's response is missing a layer: the
shapes are simplified for phones, so that fallback is not exact near a
border, which is why it is a fallback and not the primary path.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from typing import Any, Callable

from .build import STATE_FIPS
from .lookup import GeoData, ocd_id
from .shapes import point_in_polygon
from .states import legislative_kinds

# Layer names are matched by substring, not equality, since the exact
# name (e.g. "119th Congressional Districts") changes with the vintage.
# A school district may be in any of three layers ("Unified School
# Districts", "Elementary School Districts", "Secondary School
# Districts"), and an address in both an elementary and a secondary one
# is in both.
LAYER_SUBSTRINGS = {
    "cd": "Congressional Districts",
    "sldu": "Legislative Districts - Upper",
    "sldl": "Legislative Districts - Lower",
    "county": "Counties",
    "place": "Incorporated Places",
    "school_district": "School Districts",
}


GEOCODER_DOWN = "The address lookup isn't answering right now."


class AddressLookupError(Exception):
    """An address could not be resolved."""


class AddressNotFound(AddressLookupError):
    pass


class GeocoderError(AddressLookupError):
    pass


class AddressNotCovered(AddressNotFound):
    """The address was found, in a state none of the loaded ones;
    `state` is its abbreviation, or None if it is not a known one."""

    def __init__(self, state: str | None):
        super().__init__("We don't cover that address's state yet.")
        self.state = state


_ABBR_BY_FIPS = {fips: abbr for abbr, fips in STATE_FIPS.items()}


def _find_layer(geographies: dict[str, Any], substring: str) -> list | None:
    """The features of every layer whose name has `substring`, or None
    if no layer's does."""
    found = None
    for name, features in geographies.items():
        if substring in name:
            found = (found or []) + list(features)
    return found


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


def _state_by_point(geos: dict[str, GeoData | None],
                    point: tuple[float, float]) -> str | None:
    """The one loaded state whose district shapes hold `point`, if the
    geocoder named no state."""
    if point[0] is None or point[1] is None:
        return None
    found = [abbr for abbr, geo in geos.items() if geo is not None and any(
        point_in_polygon(point, [[tuple(p) for p in ring]
                                 for ring in geom["coordinates"]])
        for geom in geo.district_shapes.values())]
    return found[0] if len(found) == 1 else None


def lookup_address(address: str, fetch: Callable[[str], str], base_url: str,
                   geos: dict[str, GeoData | None]) -> dict[str, Any]:
    """`{"matched_address": str, "state": abbr, "kinds": {kind:
    [{"ocd_id", "name"}]}}` for an address in any state of `geos`
    (abbreviation -> its geo data, or None if it has none), or raises
    AddressNotFound (AddressNotCovered for another state) /
    GeocoderError."""
    query = urllib.parse.urlencode({
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "all",
        "format": "json",
    })
    url = f"{base_url}/geographies/onelineaddress?{query}"
    # The detail goes to the log, not the visitor: it can carry the
    # geocoder's URL and internal error text.
    try:
        text = fetch(url)
    except Exception as e:
        print(f"geocoder: could not be reached: {e}", file=sys.stderr)
        raise GeocoderError(GEOCODER_DOWN) from None
    try:
        doc = json.loads(text)
    except ValueError as e:
        print(f"geocoder: bad response: {e}", file=sys.stderr)
        raise GeocoderError(GEOCODER_DOWN) from None

    matches = doc.get("result", {}).get("addressMatches", [])
    if not matches:
        raise AddressNotFound("We couldn't find that address.")
    match = matches[0]
    geographies = match.get("geographies", {})
    coords = match.get("coordinates", {})
    point = (coords.get("x"), coords.get("y"))

    # ocd_id() drops the GEOID's state digits, so the state must come
    # from the address itself, never be assumed.
    found_fips = _address_state_fips(geographies)
    if found_fips is not None:
        state_abbr = _ABBR_BY_FIPS.get(found_fips)
        if state_abbr not in geos:
            raise AddressNotCovered(state_abbr)
    elif len(geos) == 1:
        state_abbr = next(iter(geos))
    else:
        state_abbr = _state_by_point(geos, point)
        if state_abbr is None:
            raise AddressNotFound("We couldn't find that address.")
    geo = geos[state_abbr]
    sld = legislative_kinds(state_abbr)

    kinds: dict[str, list[dict[str, str]]] = {
        "state": [{"ocd_id": f"ocd-division/country:us/state:{state_abbr}",
                  "name": "Statewide"}],
    }
    for kind, substring in LAYER_SUBSTRINGS.items():
        if kind in ("sldu", "sldl") and kind not in sld:
            continue
        features = _find_layer(geographies, substring)
        if features is not None:
            entries = []
            for feat in features:
                # Counties and places: NAME is "Sacramento County" or
                # "San Diego city", BASENAME is "Sacramento" or "San
                # Diego", which is what the TIGER shapefile's NAME (and so
                # the zip path's OCD-ID) uses; NAME is the shapefile's
                # NAMELSAD, the display name ("District of Columbia" has
                # no "County").
                based = kind in ("county", "place")
                name = (feat.get("BASENAME") or feat.get("NAME")
                        if based else feat.get("NAME"))
                display = feat.get("NAME") if based else None
                result = ocd_id(kind, feat.get("GEOID", ""), state_abbr, name,
                                display)
                if result:
                    entries.append({"ocd_id": result[0], "name": result[1]})
            if entries:
                kinds[kind] = entries
        elif geo is not None and point[0] is not None and point[1] is not None:
            entries = _fallback_point_in_polygon(geo, kind, point)
            if entries:
                kinds[kind] = entries
    return {"matched_address": match.get("matchedAddress", address),
           "state": state_abbr, "kinds": kinds}
