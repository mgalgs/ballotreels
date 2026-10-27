"""A made-up choice question (docs/SCRIPT-FORMAT.md's [choices]), written
fresh for each test: `n` options, an archived ballot page quoting them,
and a script that lists them over the grid pages ballotreels.grid gives.

The options are "Model A tree (No. 1)", "Model B tree (No. 2)" and so on,
narrated without the part in parentheses."""

from pathlib import Path

from ballotreels import grid

CONTEST_ID = "id-2026-11-03-advisory-test"
ILLUSTRATION = "state-capitol"  # any entry in the library whose file exists


def letter(k):
    return chr(ord("a") + k)


def label(k):
    return f"Model {letter(k).upper()} tree (No. {k + 1})"


def spoken(k):
    return f"Model {letter(k).upper()} tree"


def choice_table(n):
    out = '[choices]\nsource = "ballot"\n\n'
    for k in range(n):
        out += (f'[[choices.choice]]\nletter = "({letter(k)})"\n'
                f'label = "{label(k)}"\nspoken = "{spoken(k)}"\n'
                f'illustration = "{ILLUSTRATION}"\n\n')
    return out


def page_lines(n):
    """The `choices` section's lines: one a grid page, each naming that
    page's options in ballot order."""
    out = ""
    for page in grid.pages(n):
        names = ", ".join(spoken(k) for k in page)
        out += (f'[[section.line]]\ntext = "The ballot lists {names}."\n'
                f'sources = ["ballot"]\n\n[section.line.visual]\n'
                f'kind = "choices"\nsource = "ballot"\n\n')
    return out


def write_choice_contest(path, n=6):
    path = Path(path)
    (path / "sources").mkdir(parents=True)
    items = "".join(f"<li>({letter(k)}) {label(k)};</li>\n" for k in range(n))
    (path / "sources" / "ballot.html").write_text(
        "<html><body><h1>Advisory Question - Test 7</h1>\n"
        "<p>Which tree should be the state tree? Please choose only one "
        "answer.</p>\n<ul>\n" + items + "</ul>\n"
        "<p>This advisory question asks voters to pick a state tree.</p>\n"
        "</body></html>\n", encoding="utf-8")
    (path / "sources" / "note.html").write_text(
        "<p>The question has no cost beyond printing the ballot.</p>\n",
        encoding="utf-8")
    (path / "sources.toml").write_text(f'''[contest]
id = "{CONTEST_ID}"
election = "id-2026-11-03"
division = "ocd-division/country:us/state:id"
kind = "measure"
title = "Advisory Question Test 7: State Tree"

[[source]]
id = "ballot"
kind = "official-title-summary"
publisher = "Test ballot page"
url = "https://example.com/ballot"
file = "sources/ballot.html"
retrieved = "2026-10-27"

[[source]]
id = "note"
kind = "official-fiscal-analysis"
publisher = "Test fiscal note"
url = "https://example.com/note"
file = "sources/note.html"
retrieved = "2026-10-27"
''', encoding="utf-8")
    (path / "script.toml").write_text(f'''contest = "{CONTEST_ID}"
template = "measure"
template_version = 2
standard_version = 2

[card]
source = "ballot"
number = "7"
title = "Which tree should be the state tree? Please choose only one answer."
origin = "Advisory Question - Test 7"
summary = "This advisory question asks voters to pick a state tree."

{choice_table(n)}[[section]]
id = "what"
heading = "Test 7"

[[section.line]]
text = "Test 7 asks which tree should be the state tree."
sources = ["ballot"]

[section.line.visual]
kind = "page"
source = "ballot"
highlight = ["Which tree should be the state tree?"]

[[section]]
id = "choices"
heading = "The choices"

{page_lines(n)}[[section]]
id = "fiscal"
heading = "What it costs"

[[section.line]]
text = "The fiscal note says the question costs nothing beyond printing."
sources = ["note"]

[[section]]
id = "vote"
heading = "How to vote"

[[section.line]]
text = "Voters choose only one answer."
sources = ["ballot"]

[section.line.visual]
kind = "page"
source = "ballot"
highlight = ["Please choose only one answer."]
''', encoding="utf-8")
    return path
