"""How long a line takes to say, estimated from its text before it is
narrated: numbers, money, percents and symbols expanded to the words the
narrator says for them ("$90,000" is "ninety thousand dollars"), then
syllables and pauses counted.

checks.check_spoken_parity uses it to catch two side sections balanced by
word count but not by spoken time (STANDARD.md rule 2.2) before a script
is sent to the TTS, where check_airtime would otherwise catch it only
after narration. The coefficients are fitted to the committed narrations'
per-phrase timings (see SECONDS_PER_SYLLABLE).
"""

from __future__ import annotations

import re

_ONES = ("zero one two three four five six seven eight nine ten eleven "
         "twelve thirteen fourteen fifteen sixteen seventeen eighteen "
         "nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety")
_SCALES = ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"),
           (1000, "thousand"))
_SCALE_WORDS = ("thousand", "million", "billion", "trillion")


def _under_100(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else "")


def _under_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    words = [f"{_ONES[hundreds]} hundred"] if hundreds else []
    if rest or not hundreds:
        words.append(_under_100(rest))
    return " ".join(words)


def number_words(n: int) -> str:
    """A whole number >= 0 as said aloud: 90000 "ninety thousand"."""
    if n == 0:
        return "zero"
    words = []
    for value, name in _SCALES:
        if n >= value:
            words.append(f"{number_words(n // value)} {name}")
            n %= value
    if n:
        words.append(_under_1000(n))
    return " ".join(words)


def year_words(year: int) -> str:
    """A year as said aloud: 1978 "nineteen seventy-eight", 2026 "twenty
    twenty-six", 2000 "two thousand", 2005 "two thousand five"."""
    hi, lo = divmod(year, 100)
    if year % 1000 < 10 and hi % 10 == 0:
        return number_words(year)
    if lo == 0:
        return f"{_under_100(hi)} hundred"
    return f"{_under_100(hi)} {_under_100(lo) if lo >= 10 else 'oh ' + _ONES[lo]}"


def _decimal_words(digits: str) -> str:
    whole, _, frac = digits.replace(",", "").partition(".")
    words = number_words(int(whole)) if whole else ""
    if frac:
        words += " point " + " ".join(_ONES[int(d)] for d in frac)
    return words.strip()


# Money and plain numbers: "$1.4 billion", "$90,000", "20%", "1,500", "2.5".
_NUMBER = re.compile(
    r"(?P<cur>\$)?(?P<num>\d[\d,]*(?:\.\d+)?|\.\d+)"
    r"(?:\s+(?P<scale>thousand|million|billion|trillion)\b)?"
    r"(?P<pct>\s*%)?(?P<ord>st|nd|rd|th)?")
_YEAR = re.compile(r"\b(1[1-9]\d\d|20\d\d)\b(?!,\d)")
_SYMBOLS = {"&": " and ", "%": " percent ", "§": " section ", "+": " plus ",
            "@": " at ", "=": " equals ", "/": " slash "}
_ACRONYM = re.compile(r"\b([A-Z]{2,})(s?)\b")


def _say_number(m: re.Match) -> str:
    num, scale = m.group("num"), m.group("scale")
    if m.group("ord"):
        words = number_words(int(num.replace(",", "")))
        return f" {words}th "  # the ordinal's syllables, near enough
    words = _decimal_words(num)
    if scale:
        words += f" {scale}"
    if m.group("pct"):
        words += " percent"
    if m.group("cur"):
        words += " dollars"
    return f" {words} "


def spoken_text(text: str) -> str:
    """`text` as the narrator says it: years, money, percents, numbers,
    acronyms (letter by letter) and symbols written out in words."""
    text = _YEAR.sub(lambda m: f" {year_words(int(m.group(1)))} ", text)
    text = _NUMBER.sub(_say_number, text)
    text = _ACRONYM.sub(lambda m: " ".join(m.group(1)) + m.group(2), text)
    for sym, words in _SYMBOLS.items():
        text = text.replace(sym, words)
    return " ".join(text.split())


_VOWELS = re.compile(r"[aeiouy]+")


def word_syllables(word: str) -> int:
    """A word's syllables, by a spelling rule of thumb: vowel groups, less a
    silent final "e" (but not "-le"), and "-ed"/"-es" only after the sounds
    that need them. A single letter is one, but "w" (double-u) is three."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) == 1:
        return 3 if w == "w" else 1
    n = len(_VOWELS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    elif w.endswith("ed") and not w.endswith(("ted", "ded")) and n > 1:
        n -= 1
    elif (w.endswith("es") and n > 1
          and not re.search(r"(?:[sxzcg]|ch|sh)es$", w)):
        n -= 1
    if re.search(r"[^aeiou]le$", w) and len(w) > 2:
        n = max(n, 2)
    return max(n, 1)


def syllables(text: str) -> int:
    """`text`'s spoken syllables, numbers and symbols expanded first."""
    return sum(word_syllables(w)
               for w in re.split(r"[\s\-–—]+", spoken_text(text)))


_PAUSE = re.compile(r"[,;:–—]|\s-\s|\.(?=\s)")

# Fitted by least squares to every committed narration's per-phrase
# timings (Gemini, voice Rasalgethi, the style in voices/, 0.6 s gaps):
# 395 phrases from 39 contests, October 2026. Per phrase the fit is off by
# 0.45 s RMS; on the difference between a contest's two sides, by 0.55 s
# RMS (1.5 s at worst), most of it the TTS's own take-to-take variation.
# Letters and syllables together fit better than either alone.
SECONDS_PER_PHRASE = 0.32
SECONDS_PER_LETTER = 0.045
SECONDS_PER_SYLLABLE = 0.08
SECONDS_PER_PAUSE = 0.27
# `say`'s silence between two phrases of one line, plus its margins.
SECONDS_BETWEEN_PHRASES = 0.6


def phrase_seconds(text: str) -> float:
    """Estimated seconds to say one phrase (a sentence)."""
    said = spoken_text(text)
    letters = len(re.sub(r"[^A-Za-z]", "", said))
    pauses = len(_PAUSE.findall(text.rstrip(" .!?")))
    return (SECONDS_PER_PHRASE + SECONDS_PER_LETTER * letters
            + SECONDS_PER_SYLLABLE * syllables(text)
            + SECONDS_PER_PAUSE * pauses)


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘(])")


def _phrases(text: str) -> list[str]:
    try:
        from videobuilder import speech
    except ImportError:
        return [p for p in _SENTENCE.split(" ".join(text.split())) if p]
    return speech.phrases(text)


def seconds(text: str) -> float:
    """Estimated seconds to say `text` (a line, or a side's lines joined),
    split into phrases the way `say` splits it."""
    ps = _phrases(text)
    return (sum(phrase_seconds(p) for p in ps)
            + SECONDS_BETWEEN_PHRASES * max(len(ps) - 1, 0))
