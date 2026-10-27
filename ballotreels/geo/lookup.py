"""Zip and point lookup against the data `geo build` writes
(<data-dir>/geo/<state>/): zips.json plus one GeoJSON file per district
kind and one per zip outline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .shapes import point_in_polygon
from .states import chambers

KINDS = ("cd", "sldu", "sldl", "county")

# TIGER's congressional district codes that are not a numbered district.
_CD_LABELS = {
    "00": "At-large Congressional District",
    "98": "Delegate District (at large)",
}


def district_label(kind: str, district: str, state_abbr: str) -> str | None:
    """The neutral display name of district code `district` (the GEOID
    without its state digits), or None for a kind the state lacks."""
    if kind == "cd":
        return _CD_LABELS.get(district.zfill(2),
                              f"Congressional District {int(district)}")
    chamber = chambers(state_abbr).get(kind)
    if chamber is None:
        return None
    return f"{chamber} District {int(district)}"


def ocd_id(kind: str, geoid: str, state_abbr: str,
          name: str | None = None,
          display: str | None = None) -> tuple[str, str] | None:
    """(ocd-id, neutral display name) for one district feature's GEOID,
    or None for an undefined area (district part ZZ/ZZZ). A county's
    display name is `display` when given (TIGER's NAMELSAD: "Sacramento
    County", "District of Columbia"), else "<name> County"."""
    if kind == "county":
        if not name:
            return None
        slug = name.strip().lower().replace(" ", "_")
        return (f"ocd-division/country:us/state:{state_abbr}/county:{slug}",
                display or f"{name} County")
    district = geoid[2:]
    if district.upper() in ("ZZ", "ZZZ"):
        return None
    try:
        num = str(int(district))
    except ValueError:
        return None
    label = district_label(kind, district, state_abbr)
    if label is None:
        return None
    return (f"ocd-division/country:us/state:{state_abbr}/{kind}:{num}",
            label)


@dataclass
class GeoData:
    state: str
    zips: dict[str, dict[str, list[str]]]
    names: dict[str, str]
    district_shapes: dict[str, dict[str, Any]]
    zcta_dir: Path

    @classmethod
    def load(cls, geo_dir: str | Path) -> "GeoData":
        geo_dir = Path(geo_dir)
        zips = json.loads((geo_dir / "zips.json").read_text(encoding="utf-8"))
        names: dict[str, str] = {}
        district_shapes: dict[str, dict[str, Any]] = {}
        for kind in KINDS:
            path = geo_dir / f"{kind}.geojson"
            if not path.is_file():
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            for feat in doc["features"]:
                oid = feat["properties"]["ocd_id"]
                names[oid] = feat["properties"]["name"]
                district_shapes[oid] = feat["geometry"]
        return cls(state=geo_dir.name, zips=zips, names=names,
                   district_shapes=district_shapes,
                   zcta_dir=geo_dir / "zcta")

    def zip_districts(self, zip_code: str) -> dict[str, Any] | None:
        """`{zip, state, kinds:{kind:[{ocd_id,name}]}, ambiguous:[kind]}`,
        or None if this zip has no data."""
        entry = self.zips.get(zip_code)
        if entry is None:
            return None
        ambiguous = [k for k in KINDS if len(entry.get(k, [])) > 1]
        kinds = {}
        for k, ids in entry.items():
            kinds[k] = [{"ocd_id": oid, "name": self.names.get(oid, oid)}
                        for oid in ids]
        return {"zip": zip_code, "state": self.state, "kinds": kinds,
               "ambiguous": ambiguous, "chambers": chambers(self.state)}

    def zip_shapes(self, zip_code: str,
                   kinds: list[str] | None = None) -> dict[str, Any]:
        """GeoJSON FeatureCollection: the zip's own outline (`role: "zip"`)
        plus the candidate districts of `kinds` (default: every kind the
        zip has an entry for)."""
        features = []
        zip_path = self.zcta_dir / f"{zip_code}.geojson"
        if zip_path.is_file():
            feature = json.loads(zip_path.read_text(encoding="utf-8"))
            feature.setdefault("properties", {})["role"] = "zip"
            features.append(feature)
        entry = self.zips.get(zip_code, {})
        wanted = kinds if kinds is not None else list(entry.keys())
        for k in wanted:
            for oid in entry.get(k, []):
                geom = self.district_shapes.get(oid)
                if geom is None:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {"ocd_id": oid, "name": self.names.get(oid, oid),
                                   "kind": k, "role": "district"},
                    "geometry": geom,
                })
        return {"type": "FeatureCollection", "features": features}

    def point_in_district(self, point: tuple[float, float],
                          district_ocd_id: str) -> bool:
        geom = self.district_shapes.get(district_ocd_id)
        if geom is None:
            return False
        rings = [[tuple(p) for p in ring] for ring in geom["coordinates"]]
        return point_in_polygon(point, rings)
