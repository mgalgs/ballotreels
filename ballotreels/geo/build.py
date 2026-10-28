"""Builds <data-dir>/geo/<state>/ from Census TIGER/Line shapefiles and
ZCTA-to-district relationship files (docs/ARCHITECTURE.md). Downloads go
through an injectable `fetch(url) -> bytes`, so this can run against a
fake in tests; the real CLI command uses urllib.

Safe to run on the host: it writes only under `<data-dir>/geo/`, skips a
file it already has, and builds into a temp directory that replaces the
real one only once everything has succeeded.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from .lookup import LOCAL_KINDS, PARTIAL, ocd_id
from .shapefile import iter_shapefile
from .shapes import (overlap_length, point_in_polygon, row_intervals,
                     simplify_ring)
from .states import legislative_kinds

# The district kinds whose zips come from a Census relationship file.
KINDS = ("cd", "sldu", "sldl", "county")

# The local kinds (ballotreels.geo.lookup.LOCAL_KINDS) have no ZCTA
# relationship file, so their zips are found from the shapes themselves:
# each is the union of these TIGER layers. A place is an incorporated
# city or town (a census-designated place has no government, and so no
# measures); a school district is unified, elementary or secondary.
LOCAL_LAYERS = {"place": ("place",),
                "school_district": ("unsd", "elsd", "scsd")}

# The spacing, in degrees of latitude, of the lines a zip's overlap with
# a local district is measured along (about 220 m).
SCAN_STEP = 0.002
# A local district covering less than this share of a zip is left off
# it: the zip and district outlines are drawn from different years'
# boundaries, so where they mean the same line they can differ by a
# sliver. One covering more than 1 - SLIVER of it covers all of it; any
# other is `partial`.
SLIVER = 0.01

# U.S. state and D.C. FIPS codes, abbreviation -> 2-digit code.
STATE_FIPS = {
    "al": "01", "ak": "02", "az": "04", "ar": "05", "ca": "06", "co": "08",
    "ct": "09", "de": "10", "dc": "11", "fl": "12", "ga": "13", "hi": "15",
    "id": "16", "il": "17", "in": "18", "ia": "19", "ks": "20", "ky": "21",
    "la": "22", "me": "23", "md": "24", "ma": "25", "mi": "26", "mn": "27",
    "ms": "28", "mo": "29", "mt": "30", "ne": "31", "nv": "32", "nh": "33",
    "nj": "34", "nm": "35", "ny": "36", "nc": "37", "nd": "38", "oh": "39",
    "ok": "40", "or": "41", "pa": "42", "ri": "44", "sc": "45", "sd": "46",
    "tn": "47", "tx": "48", "ut": "49", "vt": "50", "va": "51", "wa": "53",
    "wv": "54", "wi": "55", "wy": "56",
}

# TIGER/Line shapefiles are published only as .zip archives; the build
# downloads each one and extracts its .shp and .dbf. Override any URL
# with `--url <name>=<url>`.
TIGER_BASE = "https://www2.census.gov/geo/tiger/TIGER2024"
REL_BASE = "https://www2.census.gov/geo/docs/maps-data/data/rel2020"

SHAPE_ARCHIVES = ("cd", "sldu", "sldl", "county", "zcta", "place", "unsd",
                  "elsd", "scsd")

# The ZCTA-to-state-legislative-district relationship files (2024
# districts, 2020 ZCTAs, from the 2020 CD/SLD record layout) could not be
# checked from where this was written, so they are optional: if the
# default URL fails, the build warns and goes on, and zips carry no
# district of that kind. A URL given with --url must work.
OPTIONAL_DOWNLOADS = ("sldu_rel.txt", "sldl_rel.txt")

# A state whose every school district is unified (Hawaii's one, Nevada's
# counties) has no elementary or secondary layer to download: without
# one, the build warns and goes on.
OPTIONAL_SHAPES = ("elsd.zip", "scsd.zip")


def kinds_for(state_abbr: str) -> tuple[str, ...]:
    """The district kinds a state has: every KIND but the legislative
    ones for a state with no legislature (D.C.)."""
    sld = legislative_kinds(state_abbr)
    return tuple(k for k in KINDS if k not in ("sldu", "sldl") or k in sld)


def census_urls(state_abbr: str) -> dict[str, str]:
    """Every download for a state, by name. D.C. has no state legislative
    district files in TIGER, so it gets no sldu/sldl entries."""
    fips = STATE_FIPS[state_abbr]
    kinds = kinds_for(state_abbr)
    urls = {
        "cd.zip": f"{TIGER_BASE}/CD/tl_2024_{fips}_cd119.zip",
        "sldu.zip": f"{TIGER_BASE}/SLDU/tl_2024_{fips}_sldu.zip",
        "sldl.zip": f"{TIGER_BASE}/SLDL/tl_2024_{fips}_sldl.zip",
        "county.zip": f"{TIGER_BASE}/COUNTY/tl_2024_us_county.zip",
        "zcta.zip": f"{TIGER_BASE}/ZCTA520/tl_2024_us_zcta520.zip",
        "place.zip": f"{TIGER_BASE}/PLACE/tl_2024_{fips}_place.zip",
        "unsd.zip": f"{TIGER_BASE}/UNSD/tl_2024_{fips}_unsd.zip",
        "elsd.zip": f"{TIGER_BASE}/ELSD/tl_2024_{fips}_elsd.zip",
        "scsd.zip": f"{TIGER_BASE}/SCSD/tl_2024_{fips}_scsd.zip",
        "cd_rel.txt": f"{REL_BASE}/cd-sld/tab20_cd11820_zcta520_st{fips}.txt",
        "county_rel.txt":
            f"{REL_BASE}/zcta520/tab20_zcta520_county20_natl.txt",
        "sldu_rel.txt":
            f"{REL_BASE}/cd-sld/tab20_sldu202420_zcta520_st{fips}.txt",
        "sldl_rel.txt":
            f"{REL_BASE}/cd-sld/tab20_sldl202420_zcta520_st{fips}.txt",
    }
    # "sldu.zip" and "sldu_rel.txt" both belong to kind "sldu".
    layers = ("zcta",) + tuple(l for ls in LOCAL_LAYERS.values() for l in ls)
    return {name: url for name, url in urls.items()
            if name.split(".")[0].removesuffix("_rel") in kinds + layers}


class BuildError(Exception):
    """A download or build step that failed; the message names the file,
    the URL, and the --url flag to override it."""


def _download(name: str, url: str, dest: Path,
              fetch: Callable[[str], bytes]) -> None:
    if dest.exists():
        return
    try:
        data = fetch(url)
    except Exception as e:
        raise BuildError(
            f"{name}: could not fetch {url} ({e}); "
            f"override with --url {name}={{url}}") from None
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(data)
    part.replace(dest)


def _fetch_shapes(kind: str, url: str, raw_dir: Path,
                  fetch: Callable[[str], bytes]) -> None:
    """Leaves `<kind>.shp` and `<kind>.dbf` in raw_dir, downloading and
    extracting `<kind>.zip` unless both are already there. The archive is
    deleted once extracted (the national ZCTA one is several hundred MB)."""
    targets = [raw_dir / f"{kind}{ext}" for ext in (".shp", ".dbf")]
    if all(t.exists() for t in targets):
        return
    name = f"{kind}.zip"
    archive = raw_dir / name
    _download(name, url, archive, fetch)
    try:
        with zipfile.ZipFile(archive) as zf:
            for target in targets:
                members = [m for m in zf.namelist()
                           if m.lower().endswith(target.suffix)]
                if len(members) != 1:
                    raise BuildError(
                        f"{name}: expected one {target.suffix} file in "
                        f"{url}, found {len(members)}; override with "
                        f"--url {name}={{url}}")
                part = target.with_name(target.name + ".part")
                with zf.open(members[0]) as src, part.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                part.replace(target)
    except zipfile.BadZipFile:
        archive.unlink()
        raise BuildError(
            f"{name}: {url} is not a zip archive; "
            f"override with --url {name}={{url}}") from None
    except BuildError:
        archive.unlink()
        raise
    archive.unlink()


def _relationship_columns(header_line: str) -> tuple[str, int, int, int]:
    """(delimiter, zip column, district column, land-area column) of a
    relationship file's header; ValueError naming what is missing."""
    delim = "|" if "|" in header_line else ","
    header = [h.strip() for h in header_line.split(delim)]
    missing = [h for h in ("GEOID_ZCTA5_20", "AREALAND_PART")
               if h not in header]
    if missing:
        raise ValueError(f"header has no {', '.join(missing)} column")
    zip_col = header.index("GEOID_ZCTA5_20")
    district_cols = [i for i, h in enumerate(header)
                     if h.startswith("GEOID_") and i != zip_col]
    if not district_cols:
        raise ValueError("header has no GEOID_* district column")
    return delim, zip_col, district_cols[0], header.index("AREALAND_PART")


def _check_relationship(name: str, url: str, path: Path) -> None:
    """Rejects a downloaded relationship file whose header is not one (an
    HTML error page served with 200, say), deleting it so the next run
    fetches it again."""
    with path.open(encoding="utf-8", errors="replace") as f:
        first = f.readline().lstrip("\ufeff")
    try:
        _relationship_columns(first)
    except ValueError as e:
        path.unlink()
        raise BuildError(
            f"{name}: {url} is not a relationship file ({e}); "
            f"override with --url {name}={{url}}") from None


def parse_relationship(text: str) -> list[dict]:
    """Rows of a Census ZCTA-to-district relationship file, columns found
    by header name (not position), so a renamed vintage keeps working."""
    lines = [l for l in text.lstrip("\ufeff").splitlines() if l.strip()]
    if not lines:
        return []
    delim, zip_col, district_col, arealand_col = \
        _relationship_columns(lines[0])
    rows = []
    for line in lines[1:]:
        parts = line.split(delim)
        zip_code = parts[zip_col].strip()
        district = parts[district_col].strip()
        # The national files also list the parts of a district that lie
        # in no ZCTA (blank zip), which no lookup needs.
        if not zip_code or not district:
            continue
        area = parts[arealand_col].strip()
        rows.append({
            "zip": zip_code,
            "district_geoid": district,
            "area_land_part": float(area) if area else 0.0,
        })
    return rows


def _filter_min_overlap(rows: list[dict], min_overlap: float) -> list[dict]:
    totals: dict[str, float] = {}
    for row in rows:
        totals[row["zip"]] = totals.get(row["zip"], 0.0) + row["area_land_part"]
    out = []
    for row in rows:
        total = totals.get(row["zip"], 0.0)
        frac = row["area_land_part"] / total if total else 0.0
        if frac >= min_overlap:
            out.append(row)
    return out


def _simplify_rings(rings, tolerance: float) -> list[list[tuple[float, float]]]:
    out = []
    for ring in rings:
        simplified = simplify_ring(ring, tolerance)
        if simplified is not None:
            out.append(simplified)
    return out


def build(data_dir: str | Path, state_abbr: str,
         fetch: Callable[[str], bytes], urls: dict[str, str] | None = None,
         min_overlap: float = 0.0, tolerance: float = 0.001) -> list[str]:
    """Builds `<data_dir>/geo/<state>/`; returns warnings for the caller
    to print (today: a district kind with no relationship file)."""
    data_dir = Path(data_dir)
    fips = STATE_FIPS[state_abbr]
    defaults = census_urls(state_abbr)
    unknown = sorted(set(urls or {}) - set(defaults))
    if unknown:
        raise BuildError(
            f"--url: unknown download name(s) {', '.join(unknown)}; known: "
            f"{', '.join(defaults)}")
    resolved_urls = {**defaults, **(urls or {})}

    raw_dir = data_dir / "geo" / ".raw" / state_abbr
    raw_dir.mkdir(parents=True, exist_ok=True)
    warnings = []
    for name, url in resolved_urls.items():
        kind = name[:-len(".zip")] if name.endswith(".zip") else None
        if kind in SHAPE_ARCHIVES:
            try:
                _fetch_shapes(kind, url, raw_dir, fetch)
            except BuildError as e:
                if name not in OPTIONAL_SHAPES or name in (urls or {}):
                    raise
                warnings.append(f"{e}; the state has no {kind} school "
                                f"districts in this build")
            continue
        try:
            _download(name, url, raw_dir / name, fetch)
            _check_relationship(name, url, raw_dir / name)
        except BuildError as e:
            if name not in OPTIONAL_DOWNLOADS or name in (urls or {}):
                raise
            kind = name[:-len("_rel.txt")]
            warnings.append(f"{e}; zips will carry no {kind} district")

    state_dir = data_dir / "geo" / state_abbr
    tmp_dir = data_dir / "geo" / f"{state_abbr}.tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    try:
        _build_into(tmp_dir, raw_dir, fips, state_abbr, min_overlap, tolerance)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    # Move the old output aside before the new one goes in, so that at
    # every moment one complete `<state>/` exists (or, for an instant
    # between the two renames, `<state>.old/`).
    old_dir = data_dir / "geo" / f"{state_abbr}.old"
    if old_dir.exists():
        if state_dir.exists():
            shutil.rmtree(old_dir)
        else:  # an earlier build stopped between the two renames
            old_dir.replace(state_dir)
    if state_dir.exists():
        state_dir.replace(old_dir)
    tmp_dir.replace(state_dir)
    shutil.rmtree(old_dir, ignore_errors=True)
    return warnings


def _zcta_of(attrs: dict) -> str:
    # The 2020-vintage ZCTA shapefile names the field GEOID20 (and
    # ZCTA5CE20); plain GEOID is accepted for older vintages.
    return str(attrs.get("GEOID20") or attrs.get("ZCTA5CE20")
               or attrs.get("GEOID") or "")


def _shp_base(raw_dir: Path, name: str) -> Path:
    return raw_dir / name


def _incorporated(attrs: dict) -> bool:
    """A TIGER place that is an incorporated city or town (class code
    C*), not a census-designated place (U*)."""
    return str(attrs.get("CLASSFP", "")).startswith("C")


class _ZipScan:
    """The zips' outlines as row intervals (ballotreels.geo.shapes.
    row_intervals), so a local district's share of each zip can be
    measured without keeping every zip's full outline in memory."""

    def __init__(self, step: float = SCAN_STEP):
        self.step = step
        # row -> [(x0, x1, zip)], sorted once all zips are in
        self.rows: dict[int, list[tuple[float, float, str]]] = {}
        self.area: dict[str, float] = {}
        # zips too small for any line to cross: a point inside each
        self.points: dict[str, tuple[float, float]] = {}
        self._sorted = False

    def add(self, zip_code: str, rings, simplified) -> None:
        rows = row_intervals(rings, self.step)
        area = sum(b - a for ivs in rows.values() for a, b in ivs)
        if area > 0:
            self.area[zip_code] = area
            for k, ivs in rows.items():
                self.rows.setdefault(k, []).extend(
                    (a, b, zip_code) for a, b in ivs)
        elif simplified or rings:
            ring = (simplified or rings)[0]
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            self.points[zip_code] = ((min(xs) + max(xs)) / 2,
                                     (min(ys) + max(ys)) / 2)
        self._sorted = False

    def overlaps(self, rings, simplified) -> dict[str, float]:
        """zip -> the share of its area inside the shape `rings`
        (`simplified`: the same shape, for the zips too small to
        measure, which count as wholly in it when their point is)."""
        if not self._sorted:
            for ivs in self.rows.values():
                ivs.sort()
            self._sorted = True
        shared: dict[str, float] = {}
        for k, mine in row_intervals(rings, self.step).items():
            theirs = self.rows.get(k)
            if not theirs:
                continue
            by_zip: dict[str, list[tuple[float, float]]] = {}
            lo, hi = mine[0][0], mine[-1][1]
            for a, b, z in theirs:
                if b > lo and a < hi:
                    by_zip.setdefault(z, []).append((a, b))
            for z, ivs in by_zip.items():
                length = overlap_length(mine, ivs)
                if length > 0:
                    shared[z] = shared.get(z, 0.0) + length
        out = {z: length / self.area[z] for z, length in shared.items()}
        for z, point in self.points.items():
            if point_in_polygon(point, simplified or rings):
                out[z] = 1.0
        return out


def _build_into(tmp_dir: Path, raw_dir: Path, fips: str, state_abbr: str,
                min_overlap: float, tolerance: float) -> None:
    tmp_dir.mkdir(parents=True)
    zcta_dir = tmp_dir / "zcta"
    zcta_dir.mkdir()

    zip_kinds: dict[str, dict[str, list[str]]] = {}
    relevant_zips: set[str] = set()

    for kind in kinds_for(state_abbr):
        records = iter_shapefile(_shp_base(raw_dir, kind),
                                 keep=lambda a: a.get("STATEFP") == fips)
        features = []
        geoid_to_ocd: dict[str, str] = {}
        for rec in records:
            geoid = rec.attrs.get("GEOID", "")
            name = rec.attrs.get("NAME")
            result = ocd_id(kind, geoid, state_abbr, name,
                            rec.attrs.get("NAMELSAD") or None)
            if result is None:
                continue
            division, display = result
            geoid_to_ocd[geoid] = division
            rings = _simplify_rings(rec.rings, tolerance)
            if not rings:
                continue
            features.append({
                "type": "Feature",
                "properties": {"ocd_id": division, "name": display,
                              "kind": kind},
                "geometry": {"type": "Polygon",
                            "coordinates": [[list(p) for p in r]
                                             for r in rings]},
            })
        (tmp_dir / f"{kind}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}),
            encoding="utf-8")

        rel_path = raw_dir / f"{kind}_rel.txt"
        if not rel_path.exists():
            continue  # an optional one (OPTIONAL_DOWNLOADS) not supplied
        rows = _filter_min_overlap(
            parse_relationship(rel_path.read_text(encoding="utf-8",
                                                  errors="replace")),
            min_overlap)
        for row in rows:
            division = geoid_to_ocd.get(row["district_geoid"])
            if division is None:
                continue
            z = row["zip"]
            relevant_zips.add(z)
            bucket = zip_kinds.setdefault(z, {}).setdefault(kind, [])
            if division not in bucket:
                bucket.append(division)

    zip_scan = _ZipScan()
    zcta_records = iter_shapefile(_shp_base(raw_dir, "zcta"),
                                  keep=lambda a: _zcta_of(a) in relevant_zips)
    for rec in zcta_records:
        z = _zcta_of(rec.attrs)
        rings = _simplify_rings(rec.rings, tolerance)
        zip_scan.add(z, rec.rings, rings)
        if not rings:
            continue
        feature = {
            "type": "Feature",
            "properties": {"zip": z},
            "geometry": {"type": "Polygon",
                        "coordinates": [[list(p) for p in r] for r in rings]},
        }
        (zcta_dir / f"{z}.geojson").write_text(
            json.dumps(feature), encoding="utf-8")

    for kind in LOCAL_KINDS:
        features = []
        for layer in LOCAL_LAYERS[kind]:
            if not (raw_dir / f"{layer}.shp").exists():
                continue  # an optional one (OPTIONAL_SHAPES) not supplied
            records = iter_shapefile(
                _shp_base(raw_dir, layer),
                keep=lambda a: a.get("STATEFP") == fips and (
                    kind != "place" or _incorporated(a)))
            for rec in records:
                result = ocd_id(kind, rec.attrs.get("GEOID", ""), state_abbr,
                                rec.attrs.get("NAME"),
                                rec.attrs.get("NAMELSAD") or None)
                if result is None:
                    continue
                division, display = result
                rings = _simplify_rings(rec.rings, tolerance)
                for z, share in zip_scan.overlaps(rec.rings, rings).items():
                    if share < max(min_overlap, SLIVER):
                        continue
                    entry = zip_kinds.setdefault(z, {})
                    bucket = entry.setdefault(kind, [])
                    if division not in bucket:
                        bucket.append(division)
                    if share <= 1 - SLIVER:
                        entry.setdefault(PARTIAL, []).append(division)
                if not rings:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {"ocd_id": division, "name": display,
                                   "kind": kind},
                    "geometry": {"type": "Polygon",
                                 "coordinates": [[list(p) for p in r]
                                                 for r in rings]},
                })
        (tmp_dir / f"{kind}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}),
            encoding="utf-8")

    state_division = f"ocd-division/country:us/state:{state_abbr}"
    zips_doc = {}
    for z in sorted(relevant_zips):
        kinds = {"state": [state_division]}
        kinds.update(zip_kinds.get(z, {}))
        zips_doc[z] = kinds
    (tmp_dir / "zips.json").write_text(
        json.dumps(zips_doc, indent=2, sort_keys=True), encoding="utf-8")
