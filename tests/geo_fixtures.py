"""Writes hand-made Esri shapefiles for the geo tests: real binary
format (struct), fake data. Nothing here is real geography."""

from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

Ring = list[tuple[float, float]]


def write_shp(path: Path, records: list[list[Ring]]) -> None:
    """`records`: one list of rings per shape record (polygon, type 5)."""
    content_blocks = []
    for rings in records:
        parts = []
        points: list[tuple[float, float]] = []
        for ring in rings:
            parts.append(len(points))
            points.extend(ring)
        num_parts = len(parts)
        num_points = len(points)
        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            box = (min(xs), min(ys), max(xs), max(ys))
        else:
            box = (0.0, 0.0, 0.0, 0.0)
        content = struct.pack("<i", 5)
        content += struct.pack("<4d", *box)
        content += struct.pack("<ii", num_parts, num_points)
        content += struct.pack(f"<{num_parts}i", *parts)
        for x, y in points:
            content += struct.pack("<2d", x, y)
        content_blocks.append(bytes(content))

    file_length_words = 50 + sum(4 + len(c) // 2 for c in content_blocks)
    header = bytearray()
    header += struct.pack(">i", 9994)
    header += b"\x00" * 20
    header += struct.pack(">i", file_length_words)
    header += struct.pack("<i", 1000)
    header += struct.pack("<i", 5)
    header += struct.pack("<8d", 0, 0, 0, 0, 0, 0, 0, 0)
    assert len(header) == 100

    out = bytearray(header)
    for i, content in enumerate(content_blocks, start=1):
        out += struct.pack(">ii", i, len(content) // 2)
        out += content
    path.write_bytes(bytes(out))


def write_dbf(path: Path, fields: list[tuple[str, str, int]],
             records: list[dict]) -> None:
    """`fields`: (name, 'C'|'N', length)."""
    num_records = len(records)
    header_size = 32 + 32 * len(fields) + 1
    record_size = 1 + sum(f[2] for f in fields)

    header = bytearray(32)
    header[0] = 0x03
    struct.pack_into("<I", header, 4, num_records)
    struct.pack_into("<H", header, 8, header_size)
    struct.pack_into("<H", header, 10, record_size)

    out = bytearray(header)
    for name, ftype, length in fields:
        field = bytearray(32)
        nameb = name.encode("ascii")[:10]
        field[0:len(nameb)] = nameb
        field[11] = ord(ftype)
        field[16] = length
        out += field
    out += b"\x0d"

    for rec in records:
        out += b" "
        for name, ftype, length in fields:
            value = str(rec.get(name, ""))
            if ftype == "N":
                out += value[:length].rjust(length).encode("ascii")
            else:
                out += value[:length].ljust(length).encode("ascii")
    path.write_bytes(bytes(out))


def write_shapefile(base_path: Path, fields: list[tuple[str, str, int]],
                    records: list[dict], rings: list[list[Ring]]) -> None:
    """`records[i]`'s attributes go with `rings[i]`'s geometry."""
    base_path.parent.mkdir(parents=True, exist_ok=True)
    write_shp(base_path.with_suffix(".shp"), rings)
    write_dbf(base_path.with_suffix(".dbf"), fields, records)


# A small fake California, shared by every test that needs built geo
# data: cd 1/2 split at x=10, sldu 1/2 split at y=5, one sldl and one
# county covering everything. Zips: 99901 wholly in cd:1; 99902 spans
# cd:1/cd:2; 99903 spans cd:1/cd:2 and sldu:1/sldu:2; 99904 spans cd:1/
# cd:2 with a 0.1% sliver in cd:1, for --min-overlap.
STATE = "ca"


def write_fixture_source(src_dir: Path) -> None:
    fields = [("GEOID", "C", 10), ("STATEFP", "C", 2), ("NAME", "C", 40)]

    cd1 = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    cd2 = [(10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
    write_shapefile(
        src_dir / "cd", fields,
        [{"GEOID": "0601", "STATEFP": "06", "NAME": ""},
         {"GEOID": "0602", "STATEFP": "06", "NAME": ""}],
        [[cd1], [cd2]])

    sldu1 = [(0.0, 0.0), (20.0, 0.0), (20.0, 5.0), (0.0, 5.0), (0.0, 0.0)]
    sldu2 = [(0.0, 5.0), (20.0, 5.0), (20.0, 10.0), (0.0, 10.0), (0.0, 5.0)]
    write_shapefile(
        src_dir / "sldu", fields,
        [{"GEOID": "06001", "STATEFP": "06", "NAME": ""},
         {"GEOID": "06002", "STATEFP": "06", "NAME": ""}],
        [[sldu1], [sldu2]])

    sldl1 = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    write_shapefile(
        src_dir / "sldl", fields,
        [{"GEOID": "06001", "STATEFP": "06", "NAME": ""}],
        [[sldl1]])

    county = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    write_shapefile(
        src_dir / "county", fields,
        [{"GEOID": "06999", "STATEFP": "06", "NAME": "Example"}],
        [[county]])

    # The real ZCTA shapefile names its zip field GEOID20.
    zip_fields = [("GEOID20", "C", 10)]
    zips = {
        "99901": [(1.0, 1.0), (4.0, 1.0), (4.0, 4.0), (1.0, 4.0), (1.0, 1.0)],
        "99902": [(8.0, 1.0), (12.0, 1.0), (12.0, 4.0), (8.0, 4.0), (8.0, 1.0)],
        "99903": [(8.0, 3.0), (12.0, 3.0), (12.0, 7.0), (8.0, 7.0), (8.0, 3.0)],
        "99904": [(14.0, 1.0), (17.0, 1.0), (17.0, 4.0), (14.0, 4.0), (14.0, 1.0)],
    }
    write_shapefile(
        src_dir / "zcta", zip_fields,
        [{"GEOID20": z} for z in zips],
        [[ring] for ring in zips.values()])

    (src_dir / "cd_rel.txt").write_text(
        "AREALAND_PART|GEOID_CD_20|GEOID_ZCTA5_20\n"
        "999000|0601|99901\n"
        "500000|0601|99902\n"
        "500000|0602|99902\n"
        "400000|0601|99903\n"
        "600000|0602|99903\n"
        "999000|0602|99904\n"
        "1000|0601|99904\n",
        encoding="utf-8")
    (src_dir / "sldu_rel.txt").write_text(
        "GEOID_ZCTA5_20|GEOID_SLDU_20|AREALAND_PART\n"
        "99901|06001|1000000\n"
        "99902|06001|1000000\n"
        "99903|06001|450000\n"
        "99903|06002|550000\n"
        "99904|06001|1000000\n",
        encoding="utf-8")
    (src_dir / "sldl_rel.txt").write_text(
        "GEOID_ZCTA5_20|GEOID_SLDL_20|AREALAND_PART\n"
        "99901|06001|1000000\n"
        "99902|06001|1000000\n"
        "99903|06001|1000000\n"
        "99904|06001|1000000\n",
        encoding="utf-8")
    (src_dir / "county_rel.txt").write_text(
        "GEOID_ZCTA5_20|GEOID_COUNTY_20|AREALAND_PART\n"
        "99901|06999|1000000\n"
        "99902|06999|1000000\n"
        "99903|06999|1000000\n"
        "99904|06999|1000000\n",
        encoding="utf-8")


# The Census publishes no ZCTA-to-SLD relationship file, so the build has
# no default URL for one; the fixtures supply both with --url-style
# overrides, as an operator with such a file would.
SLD_REL_URLS = {
    "sldu_rel.txt": "https://fixture.example.test/sldu_rel.txt",
    "sldl_rel.txt": "https://fixture.example.test/sldl_rel.txt",
}


def _zip_shapes(src_dir: Path, kind: str) -> bytes:
    """`<kind>.shp` and `.dbf` packed the way the Census ships them: a zip
    archive whose members are named after the TIGER file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for ext in (".shp", ".dbf"):
            zf.write(src_dir / f"{kind}{ext}", f"tl_2024_fake_{kind}{ext}")
    return buf.getvalue()


def fetch_from(src_dir: Path, raise_for: str | None = None, calls=None):
    """A `fetch(url) -> bytes` reading the raw files `write_fixture_source`
    wrote, keyed by `ballotreels.geo.build.census_urls`'s URLs plus
    SLD_REL_URLS."""
    from ballotreels.geo.build import census_urls

    urls = {**census_urls(STATE), **SLD_REL_URLS}
    url_to_name = {url: name for name, url in urls.items()}

    def fetch(url: str) -> bytes:
        if calls is not None:
            calls.append(url)
        name = url_to_name[url]
        if name == raise_for:
            raise OSError("connection refused")
        if name.endswith(".zip"):
            return _zip_shapes(src_dir, name[:-len(".zip")])
        return (src_dir / name).read_bytes()

    return fetch


def build_fixture_geo(data_dir: Path, **build_kwargs) -> None:
    """Writes the fake source files to a scratch directory and builds
    them into `<data_dir>/geo/ca/`."""
    import tempfile

    from ballotreels.geo.build import build

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = Path(tmp)
        write_fixture_source(src_dir)
        build_kwargs.setdefault("urls", SLD_REL_URLS)
        build(data_dir, STATE, fetch_from(src_dir), **build_kwargs)
