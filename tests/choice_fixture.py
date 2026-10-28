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


def write_stand_in_sidecars(path):
    """Stand-in narration sidecars for the script in `path`, as
    tests.helpers.write_narration lays them out (0.4 s a word), with the
    captions file and a silent WAV the film template reads beside them.
    Never for a real contest's committed directory: its sidecars come
    from the TTS model on the host."""
    import json
    import wave

    from .helpers import write_narration

    path = Path(path)
    write_narration(path)
    doc = json.loads((path / "narration.json").read_text(encoding="utf-8"))

    def ts(t):
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"
    cues = "".join(f"{ts(p['start'])} --> {ts(p['end'])}\n{p['text']}\n\n"
                   for p in doc["phrases"])
    (path / "narration.vtt").write_text("WEBVTT\n\n" + cues, encoding="utf-8")
    rate = 8000
    with wave.open(str(path / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * doc["seconds"] + rate))


def load_film(contest_dir):
    """film/measure.py loaded afresh for the contest in `contest_dir` (it
    reads BALLOTREELS_CONTEST once, at import), as its own module."""
    import importlib.util
    import os

    repo = Path(__file__).resolve().parent.parent
    old = os.environ.get("BALLOTREELS_CONTEST")
    os.environ["BALLOTREELS_CONTEST"] = str(contest_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            f"film_measure_{abs(hash(str(contest_dir)))}",
            repo / "film" / "measure.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if old is None:
            del os.environ["BALLOTREELS_CONTEST"]
        else:
            os.environ["BALLOTREELS_CONTEST"] = old
    return mod
