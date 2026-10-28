"""The one-page app's HTML, with each shareable page's own title,
description and link-preview tags (Open Graph and Twitter card) in its
head, so a link pasted into a post shows a card for that page.

Every value put into the HTML is escaped: contest titles come from the
data files and may hold quotes, ampersands or angle brackets.
"""

from __future__ import annotations

import datetime
import html
import json
import re
from dataclasses import dataclass

SITE_NAME = "ballotreels"
# The site-wide preview image (1200x630), for pages without a poster.
DEFAULT_IMAGE = "/static/og-card.png"
DEFAULT_IMAGE_SIZE = (1200, 630)

HOME_TITLE = "ballotreels: your ballot, explained"
HOME_DESCRIPTION = ("Short, even-handed videos on everything on your "
                    "ballot. Every claim is sourced.")
NOT_FOUND_TITLE = "Page not found · ballotreels"

# index.html's default title and description sit between these markers;
# each page's tags replace them.
_META_BLOCK = re.compile(r"<!-- page-meta -->.*?<!-- /page-meta -->",
                         re.DOTALL)


@dataclass(frozen=True)
class PageMeta:
    title: str
    description: str
    # Site-relative ("/ut") or absolute; made absolute against the site
    # URL when rendered.
    path: str
    image: str = DEFAULT_IMAGE
    noindex: bool = False
    # A measure page's video, for its VideoObject structured data: the
    # video's URL and when it was made (epoch seconds).
    video: str | None = None
    video_made: float | None = None


def absolute(site_url: str, url: str) -> str:
    """`url` as an absolute URL: as it is if it already is one, else
    joined to the configured site URL (never the request's Host)."""
    if re.match(r"^https?://", url):
        return url
    return site_url.rstrip("/") + "/" + url.lstrip("/")


_ELECTION_YEAR_RE = re.compile(r"-(\d{4})-\d{2}-\d{2}$")


def election_year(election_id: str) -> str | None:
    """"ut-2026-11-03" -> "2026"; None for an id without a date."""
    m = _ELECTION_YEAR_RE.search(election_id)
    return m.group(1) if m else None


def contest_path(abbr: str, election_id: str, contest_id: str) -> str:
    """A contest's short path: /<st>/<year>/<id without its election
    prefix>, e.g. "/ut/2026/amendment-a". The site serves the contest's
    page there, and the film prints it on every frame."""
    slug = contest_id[len(election_id) + 1:]
    return f"/{abbr}/{election_year(election_id)}/{slug.lower()}"


def display_url(site_url: str, path: str) -> str:
    """`path` on the site as a person would type it: no scheme, no
    trailing slash ("ballotreels.org/ut/2026/amendment-a")."""
    url = absolute(site_url, path)
    return re.sub(r"^https?://", "", url).rstrip("/")


def capitalize(text: str) -> str:
    """The first letter upper-cased ("the District of Columbia" leading a
    title), the rest as written."""
    return text[:1].upper() + text[1:]


def measure_meta(state_name: str, title: str, path: str,
                 poster: str | None, choice: bool = False,
                 video: str | None = None,
                 video_made: float | None = None) -> PageMeta:
    """A measure's page: its state and ballot title, read neutrally. A
    choice question has no sides: its page says it lists the choices."""
    title = title.strip().rstrip(".").strip()
    what = ("What it asks and the choices on the ballot" if choice else
            "What it would do and what each side says")
    return PageMeta(
        title=f"{capitalize(state_name)} {title}, explained in 60 seconds",
        description=(f"A short, even-handed explainer of {state_name} "
                     f"{title}. {what}, every claim sourced."),
        path=path, image=poster or DEFAULT_IMAGE,
        video=video if poster else None,
        video_made=video_made if poster else None)


def state_meta(state_name: str, path: str, measures: int) -> PageMeta:
    name = capitalize(state_name)
    if not measures:
        return PageMeta(
            title=f"{name} statewide measures · ballotreels",
            description=(f"There are no statewide measures on "
                         f"{state_name}'s ballot this election. ballotreels "
                         f"makes short, even-handed explainers of ballot "
                         f"measures, every claim sourced."),
            path=path)
    return PageMeta(
        title=f"{name} statewide measures, explained in 60 seconds",
        description=(f"Short, even-handed explainers of the statewide "
                     f"measures on {state_name}'s ballot, every claim "
                     f"sourced."),
        path=path)


def home_meta() -> PageMeta:
    return PageMeta(title=HOME_TITLE, description=HOME_DESCRIPTION, path="/")


def not_found_meta(path: str) -> PageMeta:
    return PageMeta(title=NOT_FOUND_TITLE, description=HOME_DESCRIPTION,
                    path=path, noindex=True)


def meta_tags(meta: PageMeta, site_url: str) -> str:
    """The head tags for `meta`, every value escaped."""
    url = absolute(site_url, meta.path)
    image = absolute(site_url, meta.image)
    tags = [("title", None, meta.title),
            ("meta", ("name", "description"), meta.description)]
    if meta.noindex:
        tags.append(("meta", ("name", "robots"), "noindex"))
    else:
        tags.append(("link", ("rel", "canonical"), url))
    for prop, value in (("og:site_name", SITE_NAME), ("og:type", "website"),
                        ("og:locale", "en_US"),
                        ("og:title", meta.title),
                        ("og:description", meta.description),
                        ("og:url", url), ("og:image", image)):
        tags.append(("meta", ("property", prop), value))
    if meta.image == DEFAULT_IMAGE:
        w, h = DEFAULT_IMAGE_SIZE
        tags.append(("meta", ("property", "og:image:width"), str(w)))
        tags.append(("meta", ("property", "og:image:height"), str(h)))
    for name, value in (("twitter:card", "summary_large_image"),
                        ("twitter:title", meta.title),
                        ("twitter:description", meta.description),
                        ("twitter:image", image)):
        tags.append(("meta", ("name", name), value))
    lines = []
    for tag, attr, value in tags:
        esc = html.escape(value, quote=True)
        if tag == "title":
            lines.append(f"<title>{esc}</title>")
        elif tag == "link":
            lines.append(f'<link {attr[0]}="{attr[1]}" href="{esc}">')
        else:
            lines.append(f'<meta {attr[0]}="{attr[1]}" content="{esc}">')
    if meta.video and meta.video_made is not None:
        lines.append(video_json_ld(meta, site_url))
    return "\n".join(lines)


def video_json_ld(meta: PageMeta, site_url: str) -> str:
    """A measure video's schema.org VideoObject, so search can list it as
    a video result."""
    made = datetime.datetime.fromtimestamp(meta.video_made,
                                           datetime.timezone.utc)
    doc = {"@context": "https://schema.org", "@type": "VideoObject",
           "name": meta.title, "description": meta.description,
           "thumbnailUrl": absolute(site_url, meta.image),
           "contentUrl": absolute(site_url, meta.video),
           "uploadDate": made.isoformat(timespec="seconds"),
           "url": absolute(site_url, meta.path)}
    # "</" never appears raw inside the script element: a title holding
    # "</script>" must not end it.
    body = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def robots_txt(site_url: str) -> str:
    return ("User-agent: *\n"
            "Disallow: /admin\n"
            "Disallow: /api/\n"
            "Disallow: /worker/\n"
            f"Sitemap: {absolute(site_url, '/sitemap.xml')}\n")


def sitemap_xml(site_url: str, paths: list[str]) -> str:
    """A sitemap of `paths` (site-relative), in the order given."""
    urls = "".join(
        f"<url><loc>{html.escape(absolute(site_url, p))}</loc></url>\n"
        for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}</urlset>\n")


def render_page(template: str, meta: PageMeta, site_url: str) -> str:
    """index.html with its default title and description replaced by
    `meta`'s tags."""
    tags = meta_tags(meta, site_url)
    return _META_BLOCK.sub(lambda _m: tags, template, count=1)
