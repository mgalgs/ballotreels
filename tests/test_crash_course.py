"""A state's crash course (ballotreels.crash_course): its identity in the
contest index, its cache key, and its layout from committed data alone.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ballotreels import crash_course as cc
from ballotreels.contest import load_contest
from ballotreels.index import (CRASH_COURSE, ContestIndexError, key_for,
                               key_string, load_index)
from ballotreels.narration import match_phrases
from ballotreels.standard import load_standard

REPO = Path(__file__).resolve().parent.parent
UT = REPO / "data" / "ut-2026-11-03"
CA = REPO / "data" / "ca-2026-11-03"
ID = REPO / "data" / "id-2026-11-03"
DC = REPO / "data" / "dc-2026-11-03"


def edit_vote_line(member_dir):
    """Change the text of `member_dir`'s first vote line, as an edit to the
    script would, leaving its committed narration as it was (now stale)."""
    path = Path(member_dir) / "script.toml"
    text = path.read_text(encoding="utf-8")
    line = load_contest(member_dir).script.sections[-1].lines[0].text
    assert text.count(f'text = "{line}"') == 1, line
    path.write_text(text.replace(f'text = "{line}"',
                                 f'text = "{line[:-1]}, edited."'),
                    encoding="utf-8")


class ElectionCopyTestCase(unittest.TestCase):
    """A scratch copy of an election directory, members and all."""
    source = UT

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / self.source.name
        shutil.copytree(self.source, self.dir)


class IdentityTest(unittest.TestCase):
    def test_an_election_level_contest_beside_the_entries(self):
        index = load_index(UT)
        entry = index.crash_course
        self.assertEqual(entry.id, "ut-2026-11-03-crash-course")
        self.assertEqual(entry.kind, CRASH_COURSE)
        self.assertEqual(entry.division, "ocd-division/country:us/state:ut")
        self.assertEqual(entry.members, ("ut-2026-11-03-amendment-a",
                                         "ut-2026-11-03-amendment-b"))
        # never one of the ballot's own entries, but found by its id
        self.assertNotIn(entry, index.entries)
        self.assertIs(index.get(entry.id), entry)

    def test_members_are_the_statewide_measures_in_contests_toml_order(self):
        index = load_index(CA)
        want = [e.id for e in index.entries
                if e.kind == "measure"
                and e.division == index.election.state]
        self.assertEqual(list(index.crash_course.members), want)
        self.assertEqual(len(want), 14)

    def test_none_with_a_single_statewide_measure(self):
        self.assertIsNone(load_index(DC).crash_course)

    def test_its_id_cannot_be_listed_by_hand(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contests.toml"
            path.write_text(
                '[election]\nid = "ut-2026-11-03"\n'
                'state = "ocd-division/country:us/state:ut"\ntitle = "x"\n'
                '[[contest]]\nid = "ut-2026-11-03-crash-course"\n'
                'kind = "measure"\n'
                'division = "ocd-division/country:us/state:ut"\n'
                'title = "x"\nnumber = "A"\n', encoding="utf-8")
            with self.assertRaisesRegex(ContestIndexError, "crash course"):
                load_index(tmp)

    def test_key_splits_back_to_its_id(self):
        index = load_index(UT)
        key = key_for(index.election.id, index.crash_course, load_standard())
        cid, digest = cc.split_key_contest(key[2])
        self.assertEqual(cid, "ut-2026-11-03-crash-course")
        self.assertRegex(digest, r"^[0-9a-f]{16}$")
        self.assertTrue(cc.is_crash_course(key[2]))
        self.assertEqual(key[4], cc.TEMPLATE_VERSION)
        # a measure's key is untouched
        measure = index.get("ut-2026-11-03-amendment-a")
        self.assertEqual(key_for(index.election.id, measure,
                                 load_standard())[2], measure.id)
        self.assertEqual(cc.split_key_contest(measure.id),
                         (measure.id, None))


class KeyTest(ElectionCopyTestCase):
    def key(self):
        index = load_index(self.dir)
        return key_string(key_for(index.election.id, index.crash_course,
                                  load_standard()))

    def test_stable_for_the_same_data(self):
        self.assertEqual(self.key(), self.key())

    def test_changes_when_a_member_script_changes(self):
        before = self.key()
        edit_vote_line(self.dir / "amendment-b")
        self.assertNotEqual(self.key(), before)

    def test_changes_when_a_member_narration_changes(self):
        before = self.key()
        path = self.dir / "amendment-a" / "narration.wav"
        data = bytearray(path.read_bytes())
        data[-1] ^= 0x01
        path.write_bytes(bytes(data))
        self.assertNotEqual(self.key(), before)
        middle = self.key()
        path = self.dir / "amendment-a" / "narration.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["phrases"][0]["end"] += 0.01
        path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertNotEqual(self.key(), middle)

    def test_changes_when_a_member_s_sources_change(self):
        before = self.key()
        with (self.dir / "amendment-a" / "sources.toml").open("a") as f:
            f.write("\n# a note\n")
        self.assertNotEqual(self.key(), before)


class LayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ut = cc.plan(UT)
        cls.ca = cc.plan(CA)

    def test_utah_and_california_from_committed_data(self):
        self.assertEqual(len(self.ut.members), 2)
        self.assertEqual(len(self.ca.members), 14)

    def test_each_slot_is_its_own_content_plus_the_gap(self):
        gap = round(cc.SLOT_GAP_SECONDS * self.ut.fps)
        for course in (self.ut, self.ca):
            self.assertEqual(list(course.slots),
                             [m.frames + gap for m in course.members])
            self.assertEqual(course.page_start(0), course.opening)
            for k, page in enumerate(course.pages):
                start = course.page_start(k) + course.lead
                for i in page:
                    self.assertEqual(course.slot_start(i), start)
                    start += course.slots[i]
                self.assertEqual(course.page_start(k + 1), start)
            self.assertEqual(course.slots_end, course.opening + sum(
                course.lead + sum(course.slots[i] for i in p)
                for p in course.pages))
            self.assertEqual(course.sources_start,
                             course.slots_end + course.closing)

    def test_no_slot_is_padded_to_the_longest(self):
        course = self.ca
        gap = round(cc.SLOT_GAP_SECONDS * course.fps)
        lengths = [m.frames for m in course.members]
        self.assertGreater(max(lengths) - min(lengths), 3 * course.fps)
        for i, m in enumerate(course.members):
            self.assertEqual(course.slots[i], m.frames + gap)
        # and its chapters start where its unequal slots do
        for i, ch in enumerate(cc.chapters(course)):
            self.assertAlmostEqual(ch["start"], course.slot_start(i)
                                   / course.fps, delta=0.001)

    def test_pages_split_evenly_over_the_fewest(self):
        self.assertEqual(cc.page_sizes(14), (5, 5, 4))
        self.assertEqual(cc.page_sizes(6), (6,))
        self.assertEqual(cc.page_sizes(7), (4, 3))
        self.assertEqual(cc.page_sizes(2), (2,))
        self.assertEqual(cc.page_sizes(13), (5, 4, 4))
        # in ballot order, every member once
        self.assertEqual([len(p) for p in self.ca.pages], [5, 5, 4])
        self.assertEqual([i for p in self.ca.pages for i in p],
                         list(range(14)))
        self.assertEqual(self.ut.pages, ((0, 1),))

    def test_each_one_liner_is_its_change_section_s_first_line(self):
        for course in (self.ut, self.ca):
            for m in course.members:
                change = next(s for s in m.contest.script.sections
                              if s.id == "change")
                self.assertIs(m.line, change.lines[0])
                self.assertFalse(m.fallback)

    def test_a_script_with_no_change_section_says_its_opening_line(self):
        course = cc.plan(ID)
        fell = [m for m in course.members if m.fallback]
        self.assertEqual([m.entry.id for m in fell],
                         ["id-2026-11-03-advisory-hb-932"])
        for m in fell:
            self.assertEqual(m.section, "what")
            self.assertIs(m.line, m.contest.script.sections[0].lines[0])

    def test_the_audio_is_cut_around_the_one_liner_only(self):
        # Every phrase of the committed narration either lies inside the
        # tile's cut (its one-liner's) or wholly outside it: nothing else
        # is said, not even a word of the next line.
        for course in (self.ut, self.ca, cc.plan(ID)):
            for m in course.members:
                a = m.audio_from
                b = a + m.audio_frames / course.fps
                said = False
                for span in match_phrases(m.contest):
                    if (span.section, span.index) == (m.section, 0):
                        self.assertLessEqual(a - 1e-6, span.start)
                        self.assertLessEqual(span.end, b + 1e-6)
                        said = True
                    else:
                        self.assertFalse(span.start < b and span.end > a,
                                         (m.entry.id, span))
                self.assertTrue(said, m.entry.id)

    def test_chapters_one_per_measure_in_ballot_order(self):
        index = load_index(CA)
        got = cc.chapters(self.ca)
        self.assertEqual([c["title"] for c in got],
                         [index.get(cid).title
                          for cid in index.crash_course.members])
        for i, c in enumerate(got):
            self.assertGreaterEqual(c["start"] * self.ca.fps,
                                    self.ca.slot_start(i))
            self.assertLess(c["start"] * self.ca.fps,
                            self.ca.slot_start(i) + 0.05)

    def test_the_opening_card_says_only_what_the_index_says(self):
        self.assertEqual(self.ut.state_name, "Utah")
        self.assertEqual(self.ut.headline, "2 statewide measures")
        self.assertEqual(self.ut.date, "November 3, 2026")
        self.assertEqual(self.ca.headline, "14 statewide measures")
        self.assertEqual(cc.plan(DC.parent / "id-2026-11-03").state_name,
                         "Idaho")

    def test_sources_are_what_the_reused_lines_cite(self):
        for m in self.ut.members:
            ids = set()
            for line in m.lines:
                ids.update(line.sources or ())
                if line.visual is not None and line.visual.source:
                    ids.add(line.visual.source)
            self.assertEqual({s.id for s in m.cited}, ids)
        flat = cc.sources(self.ut)
        self.assertEqual([s["contest"] for s in flat],
                         [m.entry.id for m in self.ut.members
                          for _ in m.cited])

    def test_its_script_record_quotes_the_reused_lines(self):
        import tomllib
        doc = tomllib.loads(cc.script_toml(self.ut))
        self.assertEqual(doc["contest"], "ut-2026-11-03-crash-course")
        for rec, m in zip(doc["member"], self.ut.members):
            self.assertEqual(rec["contest"], m.entry.id)
            self.assertEqual([ln for s in rec["section"] for ln in s["lines"]],
                             [m.line.text])
            self.assertEqual(rec["section"][0]["id"], "change")


class StaleMemberTest(ElectionCopyTestCase):
    def test_a_stale_member_fails_naming_it(self):
        edit_vote_line(self.dir / "amendment-b")
        with self.assertRaises(cc.CrashCourseError) as ctx:
            cc.plan(self.dir)
        msg = str(ctx.exception)
        self.assertIn("Constitutional Amendment B", msg)
        self.assertIn("ut-2026-11-03-amendment-b", msg)
        self.assertIn("no longer matches", msg)
        self.assertNotIn("amendment-a", msg)

    def test_a_member_with_no_narration_fails_naming_it(self):
        (self.dir / "amendment-a" / "narration.wav").unlink()
        with self.assertRaisesRegex(cc.CrashCourseError,
                                    r"Amendment A.*no committed narration"):
            cc.plan(self.dir)


class NeverAsksTheTtsTest(unittest.TestCase):
    def test_laid_out_with_every_speech_engine_refusing(self):
        from unittest import mock

        from videobuilder import speech

        def refuse(*a, **kw):
            raise AssertionError("the crash course asked the TTS")

        with mock.patch.object(speech, "say", refuse), \
                mock.patch.object(speech, "Gemini", refuse), \
                mock.patch.object(speech, "Kokoro", refuse), \
                mock.patch.object(speech, "Chatterbox", refuse):
            course = cc.plan(UT)
        self.assertEqual(len(course.members), 2)


if __name__ == "__main__":
    unittest.main()
