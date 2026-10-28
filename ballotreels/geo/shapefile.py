"""Minimal stdlib reader for Esri shapefiles: polygon `.shp` records
(shape type 5) and their `.dbf` attribute table.

Rings are returned exactly as the file lists them, outer rings and holes
mixed together: a point is "in" the shape when it is in an odd number of
its rings (ballotreels.geo.shapes.point_in_polygon), the usual way to
handle holes and multiple parts without having to tell them apart by
winding order.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

POLYGON = 5

Ring = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class ShapeRecord:
    rings: tuple[Ring, ...]
    attrs: dict[str, Any]


def iter_dbf(path: Path) -> Iterator[dict[str, Any] | None]:
    """One attribute dict per `.dbf` record, read one record at a time;
    None for a record marked deleted, so positions stay matched with
    the `.shp` records."""
    with path.open("rb") as f:
        head = f.read(32)
        num_records, header_size, record_size = struct.unpack_from(
            "<IHH", head, 4)
        rest = f.read(header_size - 32)
        fields = []
        offset = 0
        while rest[offset] != 0x0D:
            name = rest[offset:offset + 11].split(b"\x00")[0].decode("ascii")
            ftype = chr(rest[offset + 11])
            length = rest[offset + 16]
            fields.append((name, ftype, length))
            offset += 32
        for _ in range(num_records):
            rec = f.read(record_size)
            if len(rec) < record_size:
                return
            if rec[0:1] == b"*":
                yield None
                continue
            row: dict[str, Any] = {}
            o = 1
            for name, ftype, length in fields:
                raw = rec[o:o + length].decode(
                    "utf-8", errors="replace").strip()
                o += length
                row[name] = int(raw) if ftype == "N" and raw else raw
            yield row


def _parse_shape(content: bytes) -> tuple[Ring, ...]:
    shape_type = struct.unpack_from("<i", content, 0)[0]
    if shape_type == 0:
        return ()
    num_parts, num_points = struct.unpack_from("<ii", content, 36)
    parts = struct.unpack_from(f"<{num_parts}i", content, 44)
    points_off = 44 + num_parts * 4
    points = struct.unpack_from(f"<{num_points * 2}d", content, points_off)
    rings = []
    for i, start in enumerate(parts):
        end = parts[i + 1] if i + 1 < len(parts) else num_points
        rings.append(tuple((points[2 * j], points[2 * j + 1])
                           for j in range(start, end)))
    return tuple(rings)


def iter_shp(path: Path, wanted: Callable[[], bool] | None = None
             ) -> Iterator[tuple[Ring, ...] | None]:
    """One tuple of rings per `.shp` record, read one record at a time.
    `wanted()`, if given, is called once per record, in order; a record
    it returns False for is skipped unparsed and yields None, so a
    national file filtered down to one state never builds the rest in
    memory."""
    with path.open("rb") as f:
        header = f.read(100)
        file_length = struct.unpack_from(">i", header, 24)[0] * 2
        pos = 100
        while pos + 8 <= file_length:
            rec_head = f.read(8)
            if len(rec_head) < 8:
                return
            _, content_words = struct.unpack(">ii", rec_head)
            size = content_words * 2
            pos += 8 + size
            if wanted is not None and not wanted():
                f.seek(size, 1)
                yield None
                continue
            yield _parse_shape(f.read(size))


def iter_shapefile(base_path: str | Path,
                   keep: Callable[[dict[str, Any]], bool] | None = None
                   ) -> Iterator[ShapeRecord]:
    """Reads `<base_path>.shp` and `<base_path>.dbf` together, one
    ShapeRecord per record (they are written in matching order), with
    only the current record in memory. `keep(attrs)` filters records
    before their geometry is parsed."""
    base_path = Path(base_path)
    attrs_iter = iter_dbf(base_path.with_suffix(".dbf"))
    _end = object()
    current: list[Any] = [None]

    def wanted() -> bool:
        current[0] = next(attrs_iter, _end)
        attrs = current[0]
        if attrs is _end or attrs is None:
            return False
        return keep is None or keep(attrs)

    for rings in iter_shp(base_path.with_suffix(".shp"), wanted):
        if current[0] is _end:
            return  # more shapes than attribute rows: stop, as zip() would
        if rings is not None:
            yield ShapeRecord(rings=rings, attrs=current[0])


def read_shapefile(base_path: str | Path) -> list[ShapeRecord]:
    return list(iter_shapefile(base_path))
