"""Builds California statewide-measure contest-index entries from the
Secretary of State's official voter information guide
(docs/ARCHITECTURE.md's "Statewide measures" source).

Each proposition's own overview page (`/propositions/<n>/index.htm`)
carries its own number and title, plus a sidebar nav listing every
proposition number on the ballot. `fetch_measures` walks that nav;
`append_entries` adds any proposition missing from a contests.toml,
leaving everything already there untouched.
"""

from __future__ import annotations

import html
import re
import tomllib
from pathlib import Path
from typing import Callable

_PROP_NUM_RE = re.compile(r'<span id="propNum">[^<]*?(\d+)\s*</span>')
_PROP_NAME_RE = re.compile(
    r'<div class="grid-90 propName">\s*<h2>(.*?)</h2>', re.DOTALL)
_NAV_RE = re.compile(r'/propositions/(\d+)/index\.htm')


def _clean_title(raw_html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return " ".join(text.split())


def parse_overview(page: str) -> tuple[str, str, tuple[str, ...]]:
    """(this page's proposition number, its title, every proposition
    number listed in its sidebar nav, in order) from one SoS
    `/propositions/<n>/index.htm` page."""
    num_match = _PROP_NUM_RE.search(page)
    name_match = _PROP_NAME_RE.search(page)
    if not num_match or not name_match:
        raise ValueError("not a recognized propositions overview page")
    number = num_match.group(1)
    title = _clean_title(name_match.group(1))
    nav = []
    seen: set[str] = set()
    for n in _NAV_RE.findall(page):
        if n not in seen:
            seen.add(n)
            nav.append(n)
    return number, title, tuple(nav)


def fetch_measures(fetch: Callable[[str], str], base_url: str,
                    start_number: str = "1") -> tuple[dict, ...]:
    """Every proposition on the ballot, in nav order: `{"number", "title"}`.

    `fetch(url)` returns the page text or raises on failure. Reads the
    sidebar nav of the `start_number` page to learn every proposition
    number on the ballot, then fetches each one's own overview page for
    its title (`start_number`'s own page is reused, not refetched).
    """
    def url_for(n: str) -> str:
        return f"{base_url}/propositions/{n}/index.htm"

    def fetch_page(url: str) -> str:
        try:
            return fetch(url)
        except Exception as e:
            raise RuntimeError(f"{url}: {e}") from e

    start_page = fetch_page(url_for(start_number))
    _, start_title, numbers = parse_overview(start_page)
    titles = {start_number: start_title}
    for n in numbers:
        if n not in titles:
            page = fetch_page(url_for(n))
            _, title, _ = parse_overview(page)
            titles[n] = title
    return tuple({"number": n, "title": titles[n]} for n in numbers)


def build_contest_entries(election_id: str, division: str,
                          measures: tuple[dict, ...]) -> list[dict]:
    """Full `[[contest]]` dicts for `append_entries`, from `fetch_measures`'
    `{"number", "title"}` records."""
    entries = []
    for m in measures:
        number = m["number"]
        entries.append({
            "id": f"{election_id}-prop-{number}",
            "kind": "measure",
            "division": division,
            "title": f"Proposition {number}: {m['title']}",
            "number": number,
        })
    return entries


def _existing_ids(path: Path) -> set[str]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {c["id"] for c in data.get("contest", []) if isinstance(c, dict)
            and "id" in c}


def _toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_entry(entry: dict) -> str:
    lines = ["[[contest]]"]
    for key in ("id", "kind", "division", "title", "number", "office"):
        if key in entry and entry[key] is not None:
            lines.append(f"{key} = {_toml_str(entry[key])}")
    return "\n".join(lines) + "\n"


def append_entries(path: str | Path, entries: list[dict]) -> int:
    """Append any of `entries` whose id is not already in `path`'s
    `[[contest]]` list, as TOML text (existing text and comments are
    left exactly as they were). Returns the number appended."""
    path = Path(path)
    existing = _existing_ids(path)
    missing = [e for e in entries if e["id"] not in existing]
    if not missing:
        return 0
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    for entry in missing:
        text += "\n" + _render_entry(entry)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return len(missing)
