"""Per-state facts the lookup needs beyond the TIGER data: display names,
what each state calls its legislative chambers, and which state a zip
code's first three digits belong to (for saying which state a zip we
have no data for is in, without a national zip table).
"""

from __future__ import annotations

STATE_NAMES = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas",
    "ca": "California", "co": "Colorado", "ct": "Connecticut",
    "de": "Delaware", "dc": "the District of Columbia", "fl": "Florida",
    "ga": "Georgia", "hi": "Hawaii", "id": "Idaho", "il": "Illinois",
    "in": "Indiana", "ia": "Iowa", "ks": "Kansas", "ky": "Kentucky",
    "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota",
    "ms": "Mississippi", "mo": "Missouri", "mt": "Montana",
    "ne": "Nebraska", "nv": "Nevada", "nh": "New Hampshire",
    "nj": "New Jersey", "nm": "New Mexico", "ny": "New York",
    "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio",
    "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania",
    "ri": "Rhode Island", "sc": "South Carolina", "sd": "South Dakota",
    "tn": "Tennessee", "tx": "Texas", "ut": "Utah", "vt": "Vermont",
    "va": "Virginia", "wa": "Washington", "wv": "West Virginia",
    "wi": "Wisconsin", "wy": "Wyoming",
}

# States with no state legislature, so no SLDU/SLDL districts at all.
NO_LEGISLATURE = frozenset({"dc"})

# The lower chamber's on-screen name where it is not "State House".
_LOWER_CHAMBER = {
    "ca": "State Assembly", "ny": "State Assembly", "nv": "State Assembly",
    "nj": "State Assembly", "wi": "State Assembly",
    "md": "House of Delegates", "va": "House of Delegates",
    "wv": "House of Delegates",
}

# Nebraska's one chamber is TIGER's SLDU; it has no SLDL at all.
_UPPER_CHAMBER = {"ne": "Legislative"}
UNICAMERAL = frozenset({"ne"})


def chambers(state: str) -> dict[str, str]:
    """`{"sldu": ..., "sldl": ...}`: the on-screen name of each chamber
    (as in "<name> District 4"); empty for a state with no legislature."""
    if state in NO_LEGISLATURE:
        return {}
    if state in UNICAMERAL:
        return {"sldu": _UPPER_CHAMBER[state]}
    return {"sldu": _UPPER_CHAMBER.get(state, "State Senate"),
            "sldl": _LOWER_CHAMBER.get(state, "State House")}


def legislative_kinds(state: str) -> tuple[str, ...]:
    if state in NO_LEGISLATURE:
        return ()
    return ("sldu",) if state in UNICAMERAL else ("sldu", "sldl")


# USPS 3-digit zip prefixes, as (first, last, state); a prefix in no
# range (military, territories, unassigned) names no state. Ranges are
# state-level only, so a zip near a state line can be named for the
# neighbouring state; it is used only to word a "not covered" message.
_ZIP3 = (
    (5, 5, "ny"), (10, 27, "ma"), (28, 29, "ri"), (30, 38, "nh"),
    (39, 49, "me"), (50, 54, "vt"), (55, 55, "ma"), (56, 59, "vt"),
    (60, 69, "ct"), (70, 89, "nj"), (100, 149, "ny"), (150, 196, "pa"),
    (197, 199, "de"), (200, 200, "dc"), (201, 201, "va"),
    (202, 205, "dc"), (206, 219, "md"), (220, 246, "va"),
    (247, 268, "wv"), (270, 289, "nc"), (290, 299, "sc"),
    (300, 319, "ga"), (320, 339, "fl"), (341, 349, "fl"),
    (350, 369, "al"), (370, 385, "tn"), (386, 397, "ms"),
    (398, 399, "ga"), (400, 427, "ky"), (430, 459, "oh"),
    (460, 479, "in"), (480, 499, "mi"), (500, 528, "ia"),
    (530, 549, "wi"), (550, 567, "mn"), (569, 569, "dc"),
    (570, 577, "sd"), (580, 588, "nd"), (590, 599, "mt"),
    (600, 629, "il"), (630, 658, "mo"), (660, 679, "ks"),
    (680, 693, "ne"), (700, 714, "la"), (716, 729, "ar"),
    (730, 732, "ok"), (733, 733, "tx"), (734, 749, "ok"),
    (750, 799, "tx"), (800, 816, "co"), (820, 831, "wy"),
    (832, 838, "id"), (840, 847, "ut"), (850, 865, "az"),
    (870, 884, "nm"), (885, 885, "tx"), (889, 898, "nv"),
    (900, 961, "ca"), (967, 968, "hi"), (970, 979, "or"),
    (980, 994, "wa"), (995, 999, "ak"),
)


def state_for_zip(zip_code: str) -> str | None:
    """The state abbreviation a 5-digit zip's prefix belongs to, or None."""
    if len(zip_code) != 5 or not zip_code.isdigit():
        return None
    prefix = int(zip_code[:3])
    for first, last, state in _ZIP3:
        if first <= prefix <= last:
            return state
    return None
