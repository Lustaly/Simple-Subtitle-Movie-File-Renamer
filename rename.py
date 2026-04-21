#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

VIDEO_EXT = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".ts",
    ".flv",
    ".webm",
    ".ogv",
    ".rmvb",
    ".divx",
    ".mpg",
    ".mpeg",
    ".vob",
    ".m2ts",
    ".mts",
    ".3gp",
    ".f4v",
    ".asf",
    ".rm",
    ".wtv",
    ".dvr-ms",
    ".iso",
    ".img",
    ".bdmv",
    ".ssif",
    ".strm",
}
SUBTITLE_EXT = {
    ".srt",
    ".sub",
    ".ass",
    ".ssa",
    ".vtt",
    ".idx",
    ".smi",
    ".sbv",
    ".dfxp",
    ".ttml",
}
SKIP_EXT = {".nfo", ".jpg", ".jpeg", ".png", ".txt", ".db", ".ini", ".json"}

_LANG2 = {
    "af",
    "ak",
    "sq",
    "am",
    "ar",
    "hy",
    "az",
    "eu",
    "be",
    "bn",
    "bs",
    "bg",
    "my",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "gl",
    "ka",
    "de",
    "el",
    "gu",
    "he",
    "hi",
    "hu",
    "is",
    "id",
    "ga",
    "it",
    "ja",
    "kn",
    "kk",
    "km",
    "ko",
    "lo",
    "lv",
    "lt",
    "mk",
    "ms",
    "ml",
    "mt",
    "mr",
    "mn",
    "ne",
    "no",
    "nb",
    "nn",
    "or",
    "ps",
    "fa",
    "pl",
    "pt",
    "pa",
    "ro",
    "ru",
    "sr",
    "sk",
    "sl",
    "so",
    "es",
    "sw",
    "sv",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "uz",
    "vi",
    "cy",
    "yo",
    "zu",
}
_LANG3 = {
    "afr",
    "sqi",
    "alb",
    "amh",
    "ara",
    "hye",
    "arm",
    "aze",
    "eus",
    "baq",
    "bel",
    "ben",
    "bos",
    "bul",
    "mya",
    "bur",
    "cat",
    "zho",
    "chi",
    "hrv",
    "ces",
    "cze",
    "dan",
    "nld",
    "dut",
    "eng",
    "est",
    "fin",
    "fra",
    "fre",
    "glg",
    "kat",
    "geo",
    "deu",
    "ger",
    "ell",
    "gre",
    "guj",
    "heb",
    "hin",
    "hun",
    "isl",
    "ice",
    "ind",
    "gle",
    "ita",
    "jpn",
    "kan",
    "kaz",
    "khm",
    "kor",
    "lao",
    "lav",
    "lit",
    "mkd",
    "mac",
    "msa",
    "may",
    "mal",
    "mlt",
    "mar",
    "mon",
    "nep",
    "nor",
    "ori",
    "pus",
    "fas",
    "per",
    "pol",
    "por",
    "pan",
    "ron",
    "rum",
    "rus",
    "srp",
    "slk",
    "slo",
    "slv",
    "som",
    "spa",
    "swa",
    "swe",
    "tam",
    "tel",
    "tha",
    "tur",
    "ukr",
    "urd",
    "uzb",
    "vie",
    "cym",
    "wel",
    "yor",
    "zul",
}
_LOCALES = set()
for _c in list(_LANG2):
    for _r in [
        "BR",
        "PT",
        "TW",
        "HK",
        "CN",
        "MX",
        "AR",
        "US",
        "GB",
        "AU",
        "CA",
        "ES",
        "IN",
    ]:
        _LOCALES.add(f"{_c}-{_r}")
        _LOCALES.add(f"{_c}_{_r}")
ALL_LANGS = _LANG3 | _LANG2 | _LOCALES

_LANG_TAIL_RE = re.compile(
    r"[._\- ]+(" + "|".join(sorted(ALL_LANGS, key=len, reverse=True)) + r")$",
    re.IGNORECASE,
)


def _norm_lang(code: str) -> str:
    for sep in ("-", "_"):
        if sep in code:
            a, b = code.split(sep, 1)
            return f"{a.lower()}-{b.upper()}"
    return code.lower()


_TECH = [
    r"(?<!\d)\d{3,4}[ip](?!\w)",
    r"4[Kk]\b",
    r"8[Kk]\b",
    r"UHD\b",
    r"FHD\b",
    r"QHD\b",
    r"\bHD\b",
    r"Dolby\.?Vision\b",
    r"\bDV\b",
    r"DoVi\b",
    r"HDR(?:10\+?)?\b",
    r"HLG\b",
    r"\bSDR\b",
    r"WCG\b",
    r"BT\.?2020\b",
    r"CAM(?:RIP)?\b",
    r"TELESYNC\b",
    r"\bTS\b",
    r"\bTC\b",
    r"DVDSCR\b",
    r"DVD(?:Rip|Remux|R[59]?)?\b",
    r"BD(?:Rip|Remux|MV)?\b",
    r"BRRip\b",
    r"BRip\b",
    r"Blu[\-\. ]?Ray\b",
    r"BluRay\b",
    r"WEB[\-\.]?DL\b",
    r"WEBRip\b",
    r"\bWEB\b",
    r"HDTV\b",
    r"PDTV\b",
    r"\bDSR\b",
    r"TVRip\b",
    r"VODRip\b",
    r"REMUX\b",
    r"HDDVD\b",
    r"RETAIL\b",
    r"SCREENER\b",
    r"AMZN\b",
    r"AMAZON(?:PRIME)?\b",
    r"\bNF\b",
    r"NETFLIX\b",
    r"DSNP\b",
    r"DISNEY(?:PLUS|\+)?\b",
    r"\bHULU\b",
    r"HBOMAX\b",
    r"\bHBO\b",
    r"\bMAX\b",
    r"ATVP\b",
    r"APPLETV\+?\b",
    r"PCOK\b",
    r"PEACOCK\b",
    r"PARAMOUNT\+?\b",
    r"PLUTO\b",
    r"TUBI\b",
    r"\bROKU\b",
    r"VUDU\b",
    r"CRACKLE\b",
    r"TVING\b",
    r"WAVVE\b",
    r"CRAV\b",
    r"ITVX\b",
    r"\bSTAN\b",
    r"BINGE\b",
    r"\bPRIME\b",
    r"SKYSHOWTIME\b",
    r"MUBI\b",
    r"SHUDDER\b",
    r"CRITERION\b",
    r"SUNDANCE\b",
    r"CBSAA\b",
    r"\bSTARZ\b",
    r"\bEPIX\b",
    r"SHOWTIME\b",
    r"CANAL\+?\b",
    r"GLOBOPLAY\b",
    r"HOTSTAR\b",
    r"VOOT\b",
    r"ZEE5\b",
    r"SONYLIV\b",
    r"ALT(?:BALAJI)?\b",
    r"[Xx]\.?26[45]\b",
    r"H\.?26[45]\b",
    r"HEVC\b",
    r"\bAVC\b",
    r"\bAV1\b",
    r"\bVP9\b",
    r"\bVP8\b",
    r"VC[\-\. ]?1\b",
    r"XviD\b",
    r"DivX\b",
    r"MPEG[\-\. ]?[24]\b",
    r"NVENC\b",
    r"\bQSV\b",
    r"\bVBR\b",
    r"\bCBR\b",
    r"AAC[\d\.]*\b",
    r"AC[\-\. ]?3\b",
    r"E[\-\. ]?AC[\-\. ]?3\b",
    r"EAC[\-\. ]?3\b",
    r"DD[\+\. ]?\d*\b",
    r"DDP[\d\.]*\b",
    r"DTS(?:[\-\. ](?:HD|MA|X|HRA|Express))?\b",
    r"TrueHD\b",
    r"Atmos\b",
    r"FLAC[\d\.]*\b",
    r"\bMP3\b",
    r"Opus\b",
    r"\bPCM\b",
    r"LPCM\b",
    r"\bAC4\b",
    r"(?:[257])\.(?:0|1)(?:ch)?\b",
    r"(?:8|10|12)[\-\. ]?[Bb]it\b",
    r"PROPER\b",
    r"REPACK\b",
    r"RERIP\b",
    r"EXTENDED\b",
    r"THEATRICAL\b",
    r"UNRATED\b",
    r"UNCENSORED\b",
    r"DIRECTORS?[\.\- ]?CUT\b",
    r"IMAX\b",
    r"HYBRID\b",
    r"COMPLETE\b",
    r"INTERNAL\b",
    r"LIMITED\b",
    r"READNFO\b",
    r"FESTIVAL\b",
    r"RESTORED\b",
    r"REMASTERED?\b",
    r"CRITERION\b",
    r"MULTI(?:SUB|DUB)?\b",
    r"DUAL[\.\- ]?AUDIO\b",
    r"DUBBED?\b",
    r"SUBBED?\b",
    r"HARDSUB\b",
    r"\bHI\b",
    r"\bSDH\b",
    r"\bCC\b",
    r"synced?\b",
    r"resync\b",
    r"corrected?\b",
    r"fixed\b",
    r"NORDiC\b",
    r"SWEDiSH\b",
    r"FiNNiSH\b",
    r"NORWEGiAN\b",
    r"FRENCH\b",
    r"GERMAN\b",
    r"ITALIAN\b",
    r"SPANISH\b",
    r"ENGLISH\b",
    r"ARABIC\b",
    r"HEBREW\b",
    r"TURKISH\b",
    r"PORTUGUESE\b",
    r"RUSSIAN\b",
    r"JAPANESE\b",
    r"KOREAN\b",
    r"CHINESE\b",
    r"HINDI\b",
    r"YIFY\b",
    r"\bYTS\b",
    r"RARBG\b",
    r"EZTV\b",
    r"TEPES\b",
    r"t3nzin\b",
    r"\bNTG\b",
    r"\bEVO\b",
    r"CMRG\b",
    r"ROVERS\b",
    r"\bFGT\b",
    r"ION10\b",
    r"\bFLUX\b",
    r"GGEZ\b",
    r"NOGRP\b",
    r"AMIABLE\b",
    r"SiGMA\b",
    r"DEFLATE\b",
    r"BLUDV\b",
    r"\bGAZ\b",
    r"\bFUM\b",
    r"\bCHD\b",
    r"SPARKS\b",
    r"GECKOS\b",
    r"DIMENSION\b",
    r"KILLERS\b",
    r"REWARD\b",
    r"VPPV\b",
]

TECH_BOUNDARY = re.compile(
    r"(?:^|[\s._\-\[(]+)\b(" + "|".join(_TECH) + r")\b.*",
    re.IGNORECASE | re.DOTALL,
)
_HASH_RE = re.compile(r"[\[\(][0-9A-Fa-f]{6,10}[\]\)]")
_GRPLEAD = re.compile(r"^\s*[\[\(][^\]\)]{1,50}[\]\)]\s*")
_GRPTAIL = re.compile(r"[\s._\-]+[A-Z][A-Z0-9]{1,15}$")
_TRAIL_SEP = re.compile(r"[\s\-_,\.(]+$")
_LEAD_SEP = re.compile(r"^[\s\-_,\.)]+")
_MULTI_SPC = re.compile(r"  +")
_PAREN_TECH = re.compile(
    r"\s*[\(\[]\s*[^\(\)\[\]]*?(?:" + "|".join(_TECH[:30]) + r")[^\(\)\[\]]*?[\)\]]\s*",
    re.IGNORECASE,
)

_EP_PATS = [
    re.compile(r"[Ss](\d{1,2})\s?[Ee](\d{1,3})(?:\s?[\-Ee](\d{1,3}))+"),
    re.compile(r"[Ss](\d{1,2})\s?[Ee](\d{1,3})"),
    re.compile(r"[Ss](\d{1,2})[._][Ee](\d{1,3})"),
    re.compile(r"(?<!\d)(\d{1,2})[xX](\d{2,3})(?!\d)"),
    re.compile(r"Season\s*(\d+)\s+(?:Episode|Ep\.?)\s*(\d+)", re.IGNORECASE),
    re.compile(r"[Ss](\d)[Ee](\d{1,3})(?!\d)"),
    re.compile(r"[Ss](?:eason)?\s*(\d+)\s+[Ee](?:p(?:isode)?)?\s*(\d+)", re.IGNORECASE),
    re.compile(r"(\d{1,2})of\d{1,3}\b", re.IGNORECASE),
]

_DATEEP_RE = re.compile(
    r"(20\d\d)[.\-_ ]((?:0[1-9]|1[0-2]))[.\-_ ]((?:0[1-9]|[12]\d|3[01]))(?=[.\-_ ]|$)"
)
_ANIME_EP_RE = re.compile(r"(?:[\[\s\-._]+|^)(\d{2,4})(?:v\d)?(?:[\]\s\-._]+|$)")
_YEAR_RE = re.compile(r"[\(\[\s._\-]*((?:19[2-9]\d|20[0-2]\d))[\)\]\s._\-]*")
_PART_RE = re.compile(r"\b[Pp]art\.?\s*([IVXivx\d]+)\b")
_1OF6_RE = re.compile(r"(?<!\d)(\d{1,2})\s*of\s*\d{1,2}(?!\d)", re.IGNORECASE)
_EPONLY_RE = re.compile(r"(?:^|[\s._\-])[Ee](?:p(?:isode)?\.?)?\s*(\d{1,3})(?![\d\-])")
_ANIME_SEASON = re.compile(
    r"\b(\d+)(?:nd|rd|th|st)\s+[Ss]eason\b|\b[Ss]eason\s+(\d+)\b|\b[Ss](\d+)\b",
    re.IGNORECASE,
)

_SPECIAL_WORDS = {
    "pilot": ("S01", "E00", "Pilot"),
    "special": (None, "E00", "Special"),
    "ova": (None, "OVA", None),
    "ona": (None, "ONA", None),
    "oad": (None, "OAD", None),
    "movie": (None, None, None),
    "film": (None, None, None),
    "extras": (None, None, "Extras"),
    "featurette": (None, None, "Featurette"),
}

_CONTRACTIONS = {
    r"\bDont\b": "Don't",
    r"\bWont\b": "Won't",
    r"\bCant\b": "Can't",
    r"\bShouldnt\b": "Shouldn't",
    r"\bWouldnt\b": "Wouldn't",
    r"\bCouldnt\b": "Couldn't",
    r"\bDidnt\b": "Didn't",
    r"\bDoesnt\b": "Doesn't",
    r"\bHasnt\b": "Hasn't",
    r"\bHadnt\b": "Hadn't",
    r"\bIsnt\b": "Isn't",
    r"\bArent\b": "Aren't",
    r"\bWasnt\b": "Wasn't",
    r"\bWerent\b": "Weren't",
    r"\bHavent\b": "Haven't",
    r"\bMustnt\b": "Mustn't",
    r"\bNeednt\b": "Needn't",
    r"\bIve\b": "I've",
    r"\bIll\b": "I'll",
    r"\bIm\b": "I'm",
    r"\bId\b": "I'd",
    r"\bYouve\b": "You've",
    r"\bYoull\b": "You'll",
    r"\bYoure\b": "You're",
    r"\bYoud\b": "You'd",
    r"\bHes\b": "He's",
    r"\bHell\b": "He'll",
    r"\bHed\b": "He'd",
    r"\bShes\b": "She's",
    r"\bShell\b": "She'll",
    r"\bShed\b": "She'd",
    r"\bIts\b": "It's",
    r"\bWeve\b": "We've",
    r"\bWell\b": "We'll",
    r"\bWere\b": "We're",
    r"\bWed\b": "We'd",
    r"\bTheyve\b": "They've",
    r"\bTheyll\b": "They'll",
    r"\bTheyre\b": "They're",
    r"\bTheyd\b": "They'd",
    r"\bThats\b": "That's",
    r"\bTheres\b": "There's",
    r"\bWhos\b": "Who's",
    r"\bWhats\b": "What's",
    r"\bWheres\b": "Where's",
    r"\bLets\b": "Let's",
    r"\bHeres\b": "Here's",
    r"\bIts\b": "It's",
    r"\bShes\b": "She's",
    r"\bHows\b": "How's",
    r"\bWhenll\b": "When'll",
    r"\bWhereve\b": "Where've",
    r"\bWhoeve\b": "Who've",
}

_ROMAN_RE = re.compile(r"\b(X{0,3}(?:IX|IV|V?I{0,3}))\b")


def _smart_dots(text: str) -> str:
    def _sub(m):
        p = m.start()
        pre = re.search(r"(\w+)$", text[:p])
        post = re.search(r"^(\w+)", text[p + 1 :])
        if pre and post and len(pre.group(1)) == 1 and len(post.group(1)) == 1:
            return "."
        return " "

    return re.sub(r"\.", _sub, text)


def _normalize_stem(stem: str) -> str:
    stem = stem.replace("_", " ")
    stem = _smart_dots(stem)
    stem = _MULTI_SPC.sub(" ", stem)
    return stem.strip()


def _strip_tech(text: str) -> str:
    text = TECH_BOUNDARY.sub("", text)
    text = _HASH_RE.sub(" ", text)
    text = _PAREN_TECH.sub(" ", text)
    text = _TRAIL_SEP.sub("", text).strip()
    text = _LEAD_SEP.sub("", text).strip()
    return text


def _restore_apostrophes(text: str) -> str:
    for pat, repl in _CONTRACTIONS.items():
        text = re.sub(pat, repl, text)
    return text


_TITLE_YEAR_RE = re.compile(r"^((?:19[2-9]\d|20[0-2]\d))\b")


def _clean_title(raw: str) -> str:
    raw = _strip_tech(raw)
    raw = _PAREN_TECH.sub(" ", raw)
    raw = re.sub(r"\s*[\(\[][^\(\)\[\]]{0,80}[\)\]]\s*$", "", raw).strip()
    raw = _GRPTAIL.sub("", raw).strip()
    raw = _TRAIL_SEP.sub("", raw).strip()
    raw = _LEAD_SEP.sub("", raw).strip()
    raw = _TITLE_YEAR_RE.sub("", raw).strip()
    raw = _restore_apostrophes(raw)
    raw = _MULTI_SPC.sub(" ", raw).strip()
    return raw


def _sanitize(name: str) -> str:
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1f\x7f]", "", name)
    name = name.rstrip(". ")
    return name


def _extract_year(text: str) -> tuple[str, str]:
    m = _YEAR_RE.search(text)
    if not m:
        return "", text
    yr = m.group(1)
    if not (1920 <= int(yr) <= 2030):
        return "", text
    left = text[: m.start()].rstrip(" ._-([")
    right = text[m.end() :].lstrip(" ._-)]")
    cleaned = (left + (" " if left and right else "") + right).strip()
    return yr, cleaned


def _extract_lang(stem: str) -> tuple[str, str]:
    m = _LANG_TAIL_RE.search(stem)
    if m:
        return _norm_lang(m.group(1)), stem[: m.start()]
    return "", stem


def _infer_season(folder: Path) -> int:
    name = folder.name
    pats = [
        re.compile(
            r"(?:Season|Series|Saison|Stagione|Staffel|Temporada|Sezon)\s*(\d+)",
            re.IGNORECASE,
        ),
        re.compile(r"^[Ss]eason?\s*[\.\-_ ]?(\d{1,2})$"),
        re.compile(r"^[Ss](\d{1,2})$"),
    ]
    for pat in pats:
        mm = pat.search(name)
        if mm:
            return int(mm.group(1))
    return 0


def _token_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return len(inter) / max(len(ta), len(tb))


def _fuzzy(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    tok = _token_score(a, b)
    return 0.55 * seq + 0.45 * tok


@dataclass
class MediaInfo:
    path: Path
    show: str = ""
    year: str = ""
    season: int = 0
    episode: int = 0
    ep_end: int = 0
    title: str = ""
    language: str = ""
    is_movie: bool = False
    is_anime: bool = False
    is_dated: bool = False
    date_str: str = ""
    special: str = ""
    parse_ok: bool = False
    confidence: float = 1.0

    @property
    def ep_code(self) -> str:
        if self.special and self.special in ("OVA", "ONA", "OAD"):
            return self.special
        if self.is_dated:
            return self.date_str
        if self.is_anime and not self.season:
            return f"E{self.episode:02d}"
        if self.ep_end and self.ep_end != self.episode:
            return f"S{self.season:02d}E{self.episode:02d}-E{self.ep_end:02d}"
        if self.season or self.episode:
            return f"S{self.season:02d}E{self.episode:02d}"
        return ""

    @property
    def match_key(self) -> str:
        if self.is_dated:
            return self.date_str
        if self.special in ("OVA", "ONA", "OAD"):
            return self.special
        if self.is_anime and not self.season:
            return f"E{self.episode:02d}"
        if self.season or self.episode:
            return f"S{self.season:02d}E{self.episode:02d}"
        return ""

    @property
    def show_full(self) -> str:
        return f"{self.show} ({self.year})" if self.year else self.show

    @property
    def title_key(self) -> str:
        t = self.title.lower()
        t = re.sub(r"[^a-z0-9 ]", "", t)
        t = re.sub(r" +", " ", t).strip()
        return t

    def clean_stem(self) -> str:
        base = self.show_full
        if not base:
            return self.path.stem
        code = self.ep_code
        if not code or self.is_movie:
            result = base
        else:
            parts = [base, code]
            if self.title:
                parts.append(self.title)
            result = " - ".join(parts)
        if self.language:
            result += "." + self.language
        return _sanitize(result)


def _parse(path: Path, folder_season: int = 0) -> MediaInfo:
    mi = MediaInfo(path=path)
    stem = path.stem

    lang, stem = _extract_lang(stem)
    mi.language = lang

    stem = _HASH_RE.sub(" ", stem)
    is_anime_hint = bool(_GRPLEAD.match(stem))
    stem = _GRPLEAD.sub("", stem)
    stem = _normalize_stem(stem)

    dm = _DATEEP_RE.search(stem)
    if dm:
        mi.is_dated = True
        mi.date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
        before = stem[: dm.start()].strip(" -_.")
        after = stem[dm.end() :].strip(" -_.")
        yr, show_raw = _extract_year(before)
        mi.year = yr
        mi.show = _sanitize(_strip_tech(show_raw).strip())
        mi.title = _clean_title(after)
        mi.parse_ok = bool(mi.show)
        return mi

    ep_match = None
    for pat in _EP_PATS:
        ep_match = pat.search(stem)
        if ep_match:
            break

    if ep_match:
        g = ep_match.groups()
        try:
            mi.season = int(g[0]) if g[0] else 0
            mi.episode = int(g[1]) if (len(g) > 1 and g[1]) else 0
            mi.ep_end = int(g[2]) if (len(g) > 2 and g[2]) else 0
        except (TypeError, ValueError):
            pass

        if folder_season and not mi.season:
            mi.season = folder_season

        before = stem[: ep_match.start()].strip()
        after = stem[ep_match.end() :].strip()

        show_raw = _TRAIL_SEP.sub("", before).strip()
        yr, show_raw = _extract_year(show_raw)
        show_raw = _PAREN_TECH.sub(" ", show_raw)
        mi.year = yr
        mi.show = _sanitize(show_raw.strip())
        mi.title = _clean_title(_LEAD_SEP.sub("", after).strip())
        mi.parse_ok = True
        return mi

    pm = _PART_RE.search(stem)
    if pm:
        part_token = pm.group(1)
        before = stem[: pm.start()].strip(" -_.")
        yr, show_raw = _extract_year(before)
        show_raw = _strip_tech(show_raw)
        mi.year = yr
        mi.show = _sanitize(show_raw.strip())
        mi.episode = 0
        mi.title = f"Part {part_token}"
        mi.is_movie = True
        mi.parse_ok = bool(mi.show)
        mi.confidence = 0.85
        return mi

    em = _1OF6_RE.search(stem)
    if em:
        ep_num = int(em.group(1))
        before = stem[: em.start()].strip(" -_.")
        yr, show_raw = _extract_year(before)
        show_raw = _strip_tech(show_raw)
        mi.year = yr
        mi.show = _sanitize(show_raw.strip())
        mi.season = folder_season if folder_season else 1
        mi.episode = ep_num
        mi.parse_ok = bool(mi.show)
        mi.confidence = 0.80
        return mi

    eom = _EPONLY_RE.search(stem)
    if eom:
        ep_num = int(eom.group(1))
        before = stem[: eom.start()].strip(" -_.")
        after = stem[eom.end() :].strip(" -_.")
        yr, show_raw = _extract_year(before)
        show_raw = _strip_tech(show_raw)
        mi.year = yr
        mi.show = _sanitize(show_raw.strip())
        mi.season = folder_season if folder_season else 1
        mi.episode = ep_num
        mi.title = _clean_title(after)
        mi.parse_ok = bool(mi.show)
        mi.confidence = 0.75
        return mi

    if is_anime_hint:
        am = _ANIME_EP_RE.search(stem)
        if am:
            ep_num = int(am.group(1))
            if 1 <= ep_num <= 9999:
                mi.is_anime = True
                mi.episode = ep_num
                if folder_season:
                    mi.season = folder_season
                before = stem[: am.start()].strip(" -_")
                after = stem[am.end() :].strip(" -_")
                mi.show = _sanitize(_strip_tech(before))
                mi.title = _clean_title(after)
                mi.parse_ok = bool(mi.show)
                mi.confidence = 0.85
                return mi

    yr, clean = _extract_year(stem)
    if yr:
        clean = _strip_tech(clean)
        clean = _GRPTAIL.sub("", clean).strip()
        clean = _TRAIL_SEP.sub("", clean).strip()
        mi.year = yr
        mi.show = _sanitize(clean)
        mi.is_movie = True
        mi.parse_ok = bool(clean)
        return mi

    clean = _strip_tech(stem)
    clean = _GRPTAIL.sub("", clean).strip()
    clean = _TRAIL_SEP.sub("", clean).strip()
    if clean and len(clean) > 2:
        mi.show = _sanitize(clean)
        mi.is_movie = True
        mi.parse_ok = True
        mi.confidence = 0.65
    return mi


def _best_fuzzy(
    sub_mi: MediaInfo, candidates: list[MediaInfo], threshold: float = 0.68
) -> tuple[MediaInfo | None, float]:
    if not sub_mi.title_key:
        return None, 0.0
    best_score, best_mi = 0.0, None
    for vm in candidates:
        if sub_mi.season and vm.season and sub_mi.season != vm.season:
            continue
        if sub_mi.episode and vm.episode and sub_mi.episode != vm.episode:
            continue
        score = _fuzzy(sub_mi.title_key, vm.title_key)
        if score > best_score:
            best_score, best_mi = score, vm
    if best_score >= threshold:
        return best_mi, best_score
    return None, 0.0


def _resolve_collision(base_stem: str, ext: str, existing: set[str]) -> str:
    target = base_stem + ext
    if target not in existing:
        return base_stem
    for i in range(2, 100):
        candidate = f"{base_stem}.{i}{ext}"
        if candidate not in existing:
            return f"{base_stem}.{i}"
    return base_stem


def _scan(folder: Path, recursive: bool = False) -> tuple[list[Path], list[Path]]:
    pattern = "**/*" if recursive else "*"
    videos, subs = [], []
    for f in sorted(folder.glob(pattern)):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in VIDEO_EXT:
            videos.append(f)
        elif ext in SUBTITLE_EXT:
            subs.append(f)
    return videos, subs


@dataclass
class PlanEntry:
    path: Path
    new_stem: str
    old_stem: str
    match_key: str = ""
    fuzzy: bool = False
    fuzzy_score: float = 0.0
    matched_video: Path | None = None
    collision: bool = False


def build_plan(
    videos: list[Path], subs: list[Path], folder: Path
) -> tuple[list[PlanEntry], list[Path]]:
    folder_season = _infer_season(folder)
    vid_mis: dict[str, MediaInfo] = {}
    vid_all: list[MediaInfo] = []
    entries: list[PlanEntry] = []
    unmatched: list[Path] = []
    used_names: set[str] = set()

    for vp in videos:
        mi = _parse(vp, folder_season)
        vid_all.append(mi)
        if mi.match_key:
            vid_mis[mi.match_key] = mi
        new_stem = mi.clean_stem() if mi.parse_ok else vp.stem
        new_stem = _resolve_collision(new_stem, vp.suffix.lower(), used_names)
        used_names.add(new_stem + vp.suffix.lower())
        entries.append(
            PlanEntry(
                path=vp, new_stem=new_stem, old_stem=vp.stem, match_key=mi.match_key
            )
        )

    for sp in subs:
        mi = _parse(sp, folder_season)
        if not mi.parse_ok:
            unmatched.append(sp)
            entries.append(PlanEntry(path=sp, new_stem=sp.stem, old_stem=sp.stem))
            continue
        key = mi.match_key
        lang = mi.language
        ext = sp.suffix.lower()
        entry = PlanEntry(path=sp, new_stem=sp.stem, old_stem=sp.stem, match_key=key)

        def _make_stem(vm: MediaInfo) -> str:
            title = vm.title or mi.title
            parts = [vm.show_full, vm.ep_code]
            if title:
                parts.append(title)
            result = " - ".join(parts) if vm.ep_code else vm.show_full
            if lang:
                result += "." + lang
            return _sanitize(result)

        if key and key in vid_mis:
            vm = vid_mis[key]
            raw_stem = _make_stem(vm)
            new_stem = _resolve_collision(raw_stem, ext, used_names)
            entry.new_stem = new_stem
            entry.matched_video = vm.path
        else:
            fuzzy_vm, score = _best_fuzzy(mi, vid_all)
            if fuzzy_vm:
                raw_stem = _make_stem(fuzzy_vm)
                new_stem = _resolve_collision(raw_stem, ext, used_names)
                entry.new_stem = new_stem
                entry.fuzzy = True
                entry.fuzzy_score = score
                entry.matched_video = fuzzy_vm.path
            else:
                raw_stem = mi.clean_stem()
                new_stem = _resolve_collision(raw_stem, ext, used_names)
                entry.new_stem = new_stem

        used_names.add(entry.new_stem + ext)
        entries.append(entry)

    return entries, unmatched


UNDO_FILENAME = ".subtitle_renamer_undo.json"


def _load_undo(folder: Path) -> list[dict]:
    p = folder / UNDO_FILENAME
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_undo(folder: Path, log: list[dict]) -> None:
    p = folder / UNDO_FILENAME
    try:
        existing = _load_undo(folder)
        existing.extend(log)
        p.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _do_rename(path: Path, new_stem: str) -> tuple[bool, str]:
    new_path = path.parent / (new_stem + path.suffix.lower())
    if path == new_path:
        return False, ""
    if new_path.exists():
        return False, f"Target exists: {new_path.name}"
    try:
        path.rename(new_path)
        return True, ""
    except Exception as e:
        return False, str(e)


def do_undo(folder: Path) -> None:
    log = _load_undo(folder)
    if not log:
        print("  ℹ️  No operations found to undo.")
        return
    print(f"\n  {len(log)} operations will be reverted:\n")
    for entry in reversed(log):
        src = Path(entry["new"])
        dst = Path(entry["old"])
        if src.exists():
            try:
                src.rename(dst)
                print(f"  ✅ {src.name}")
                print(f"     ↳ {dst.name}")
            except Exception as e:
                print(f"  ❌ {src.name}: {e}")
        else:
            print(f"  ⚠️  Not found: {src.name}")
    (folder / UNDO_FILENAME).unlink(missing_ok=True)
    print()


W = 74


def _print_banner(dry_run: bool) -> None:
    mode = "  ─  DRY RUN" if dry_run else ""
    print(f"\n{'═'*W}")
    print(f"  🎬  Ultra Media File Cleaner{mode}")
    print(f"{'═'*W}")


def _grouped_preview(entries: list[PlanEntry], unmatched: list[Path]) -> None:
    changes = [e for e in entries if e.old_stem != e.new_stem]
    clean = len(entries) - len(changes)
    W2 = 70
    print("\n  " + "─" * W2)
    print(
        f"  📋  {len(changes)} changes  │  {clean} already clean  │  {len(unmatched)} unrecognized"
    )
    print("  " + "─" * W2 + "\n")
    vid_to_subs: dict[Path, list[PlanEntry]] = defaultdict(list)
    for e in changes:
        if e.matched_video:
            vid_to_subs[e.matched_video].append(e)
    shown: set[Path] = set()
    for e in changes:
        if e.path.suffix.lower() not in VIDEO_EXT:
            continue
        shown.add(e.path)
        print(f"  🎬 {e.path.name}")
        print(f"     ↳ \033[92m{e.new_stem}{e.path.suffix.lower()}\033[0m")
        for se in vid_to_subs.get(e.path, []):
            tag = (
                f"  \033[90m~ fuzzy {se.fuzzy_score*100:.0f}%\033[0m"
                if se.fuzzy
                else ""
            )
            print(f"     📄 {se.path.name}")
            print(
                f"        ↳ \033[96m{se.new_stem}{se.path.suffix.lower()}\033[0m{tag}"
            )
            shown.add(se.path)
        print()
    for e in changes:
        if e.path in shown:
            continue
        shown.add(e.path)
        tag = f"  \033[90m~ fuzzy {e.fuzzy_score*100:.0f}%\033[0m" if e.fuzzy else ""
        icon = "🎬" if e.path.suffix.lower() in VIDEO_EXT else "📄"
        print(f"  {icon} {e.path.name}")
        print(f"     ↳ \033[96m{e.new_stem}{e.path.suffix.lower()}\033[0m{tag}")
        print()
    if unmatched:
        print("  " + "─" * 70)
        print("  ⚠️  Unrecognized (will not be renamed):\n")
        for p in unmatched:
            print(f"     - {p.name}")
        print()


def process(
    folder_path: str,
    recursive: bool = False,
    dry_run: bool = False,
    log_path: Path | None = None,
) -> None:
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        print(f"\n  ❌  Folder not found: {folder_path}")
        sys.exit(1)

    _print_banner(dry_run)
    print(f"  📁  {folder}")
    if recursive:
        print("  🔁  Recursive mode enabled")
    print()

    videos, subs = _scan(folder, recursive)
    print(f"  Found: {len(videos)} video  │  {len(subs)} subtitles\n")

    if not videos and not subs:
        print("  ❌  No media files found.\n")
        return

    entries, unmatched = build_plan(videos, subs, folder)
    changes = [e for e in entries if e.old_stem != e.new_stem]

    if not changes and not unmatched:
        print(f"  ✅  All {len(entries)} files are already clean!\n")
        return

    _grouped_preview(entries, unmatched)

    print(f"  {'═'*70}")
    if dry_run:
        print("  ℹ️  Dry-run — no files were changed.\n")
        return

    if not changes:
        print("  ✅  Nothing to change.\n")
        return

    try:
        ans = (
            input(f"  ⚡  {len(changes)} file(s) will be renamed. Continue? (y/n): ")
            .strip()
            .lower()
        )
    except KeyboardInterrupt:
        print("\n  ❌  Cancelled.")
        return

    if ans not in ("y", "yes", "e", "evet"):
        print("  ❌  Cancelled.\n")
        return

    print()
    ok = skip = 0
    undo_log: list[dict] = []
    log_lines: list[str] = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for e in sorted(changes, key=lambda x: (x.path.parent, x.path.name)):
        success, msg = _do_rename(e.path, e.new_stem)
        new_name = e.new_stem + e.path.suffix.lower()
        if success:
            print(f"  ✅ {e.path.name}")
            print(f"     ↳ {new_name}")
            ok += 1
            undo_log.append({"old": str(e.path), "new": str(e.path.parent / new_name)})
            log_lines.append(f"[{ts}] {e.path.name} → {new_name}")
        else:
            if msg:
                print(f"  ⚠️  {e.path.name}")
                print(f"     ↳ {msg}")
            skip += 1

    if undo_log:
        _save_undo(folder, undo_log)

    if log_path and log_lines:
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("\n".join(log_lines) + "\n")
            print(f"\n  📝  Log: {log_path}")
        except Exception as e:
            print(f"\n  ⚠️  Failed to write log: {e}")

    print(f"\n{'═'*W}")
    print(f"  ✅  {ok} succeeded  │  {skip} skipped")
    print(f'  💡  To undo: python subtitle_renamer.py "{folder}" --undo\n')


_TESTS: list[tuple[str, str]] = [
    (
        "From (2022) - S01E08 - Broken Windows, Open Doors (1080p AMZN WEB-DL x265 t3nzin)",
        "From (2022) - S01E08 - Broken Windows, Open Doors",
    ),
    (
        "From_S01E08_Broken_Windows_Open_Doors_1080p_AMZN_WEB-DL_DDP5_1_H_264-TEPES_synced",
        "From - S01E08 - Broken Windows Open Doors",
    ),
    ("From (2022) - S01E02", "From (2022) - S01E02"),
    (
        "Breaking.Bad.S01E08.Cancer.Man.1080p.BluRay.x264-ROVERS",
        "Breaking Bad - S01E08 - Cancer Man",
    ),
    (
        "The.Boys.S03E06.Herogasm.2160p.UHD.BluRay.HDR.DV.x265.Atmos-GROUP",
        "The Boys - S03E06 - Herogasm",
    ),
    (
        "Succession.S04E09.Church.and.State.1080p.NF.WEB-DL.DD5.1.H.264",
        "Succession - S04E09 - Church and State",
    ),
    ("The.Wire.2x08.Duck.And.Cover.720p.HDTV", "The Wire - S02E08 - Duck And Cover"),
    (
        "Game.of.Thrones.S06E09E10.The.Battle.of.the.Bastards.1080p.BluRay",
        "Game of Thrones - S06E09-E10 - The Battle of the Bastards",
    ),
    ("The.Dark.Knight.2008.1080p.BluRay.x264.YIFY", "The Dark Knight (2008)"),
    ("Oppenheimer.2023.2160p.UHD.BluRay.HDR.DV.x265.Atmos-GROUP", "Oppenheimer (2023)"),
    ("Oppenheimer (2023) 2160p UHD BluRay HDR DV x265 Atmos", "Oppenheimer (2023)"),
    ("S.W.A.T.S02E14.720p.WEB-DL", "S.W.A.T - S02E14"),
    (
        "[Commie] Attack on Titan - 25 [BD 1080p AAC] [ABCD1234]",
        "Attack on Titan - E25",
    ),
    ("[SubsPlease] Demon Slayer - 44 (1080p) [CAFE1234]", "Demon Slayer - E44"),
    (
        "Peaky_Blinders_S05E06_Mr_Jones_1080p_AMZN_WEB-DL_DDP5_1_H_264-NTG",
        "Peaky Blinders - S05E06 - Mr Jones",
    ),
    (
        "Breaking.Bad.S01E08.Cancer.Man.1080p.BluRay.tr",
        "Breaking Bad - S01E08 - Cancer Man.tr",
    ),
    (
        "Show.S02E03.Episode.Title.1080p.WEB-DL.pt-BR",
        "Show - S02E03 - Episode Title.pt-BR",
    ),
    (
        "The.Late.Show.2024.03.15.Guest.Name.WEB.x264",
        "The Late Show - 2024-03-15 - Guest Name",
    ),
    (
        "Friends_S02E14_The.One.Where.Weve.Heard.This.Before.DVDRip",
        "Friends - S02E14 - The One Where We've Heard This Before",
    ),
    (
        "House.of.the.Dragon.S01E10.1080p.HBOMAX.WEB-DL.DDP5.1.x264",
        "House of the Dragon - S01E10",
    ),
    (
        "The.Last.of.Us.S01E09.Look.for.the.Light.1080p.HBOMAX.WEB-DL",
        "The Last of Us - S01E09 - Look for the Light",
    ),
    (
        "Stranger.Things.S04E09.The.Piggyback.1080p.NF.WEB-DL",
        "Stranger Things - S04E09 - The Piggyback",
    ),
    (
        "The.Mandalorian.S03E08.4K.HDR.DV.DSNP.WEB-DL.x265.Atmos",
        "The Mandalorian - S03E08",
    ),
    ("Breaking Bad - S01E08 - Cancer Man", "Breaking Bad - S01E08 - Cancer Man"),
    ("The Dark Knight (2008)", "The Dark Knight (2008)"),
    (
        "Doctor.Who.Season.1.Episode.9.The.Empty.Child.DVDRip",
        "Doctor Who - S01E09 - The Empty Child",
    ),
    (
        "Severance.S02E10.Bye.Bye.Now.2160p.ATVP.WEB-DL.DDP5.1.HDR.H.265",
        "Severance - S02E10 - Bye Bye Now",
    ),
    (
        "Mr.Robot.S01E01.eps1.0_hellofriend.mov.1080p.HDTV",
        "Mr Robot - S01E01 - eps1 0 hellofriend mov",
    ),
    (
        "Its.Always.Sunny.in.Philadelphia.S15E01.2021.720p.WEB-DL",
        "Its Always Sunny in Philadelphia - S15E01",
    ),
    (
        "The.Office.US.S03E01.Gay.Witch.Hunt.DVDRip.XviD",
        "The Office US - S03E01 - Gay Witch Hunt",
    ),
    (
        "Shogun.2024.S01E10.Crimson.Sky.1080p.HULU.WEB-DL.DDP5.1.H.264",
        "Shogun (2024) - S01E10 - Crimson Sky",
    ),
    (
        "[Erai-raws] Frieren - Beyond Journeys End - 28 [1080p] [ENG SUB]",
        "Frieren - Beyond Journeys End - E28",
    ),
    (
        "Fallout.S01E08.The.Beginning.2160p.AMZN.WEB-DL.DDP5.1.HDR.H.265-FLUX",
        "Fallout - S01E08 - The Beginning",
    ),
    ("A.Real.Pain.2024.1080p.WEB-DL.DDP5.1.Atmos.H264-CMRG", "A Real Pain (2024)"),
    ("Dune.Part.Two.2024.2160p.UHD.BluRay.HDR.DV.x265.Atmos", "Dune Part Two (2024)"),
    (
        "The.Penguin.S01E06.All.Happy.Families.2160p.MAX.WEB-DL.DDP5.1.HDR.H.265",
        "The Penguin - S01E06 - All Happy Families",
    ),
    (
        "Only.Murders.in.the.Building.S04E10.1080p.DSNP.WEB-DL.DDP5.1.H.264",
        "Only Murders in the Building - S04E10",
    ),
    (
        "Agatha.All.Along.S01E09.1080p.DSNP.WEB-DL.DDP5.1.H.264-NTG",
        "Agatha All Along - S01E09",
    ),
    ("The.Substance.2024.2160p.MUBI.WEB-DL.DDP5.1.SDR.H.265", "The Substance (2024)"),
]


def run_tests() -> None:
    print(f"\n{'═'*W}")
    print("  🧪  Test Mode")
    print(f"{'═'*W}\n")
    ok = fail = 0
    for stem, expected in _TESTS:
        mi = _parse(Path(stem + ".mkv"))
        result = mi.clean_stem().rstrip()
        if result == expected:
            ok += 1
            short = stem[:64]
            print(f"  ✅ {short}")
            print(f"     → {result}\n")
        else:
            fail += 1
            print(f"  ❌ {stem[:64]}")
            print(f"     Expected : {expected}")
            print(f"     Got      : {result}\n")
    print(f"{'─'*W}")
    print(f"  Result: {ok} passed / {fail} failed  ({ok}/{ok+fail})\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="subtitle_renamer",
        description="Ultra Media File Cleaner — handles any media/subtitle naming convention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python subtitle_renamer.py
  python subtitle_renamer.py "D:\\Shows\\Breaking Bad\\Season 1"
  python subtitle_renamer.py /media/hdd/Movies --dry-run
  python subtitle_renamer.py /media/hdd/Shows  --recursive
  python subtitle_renamer.py /media/hdd/Shows  --undo
  python subtitle_renamer.py /media/hdd/Shows  --log rename.log
  python subtitle_renamer.py --test
""",
    )
    ap.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="Folder path (default: current directory)",
    )
    ap.add_argument(
        "--recursive", "-r", action="store_true", help="Also scan subdirectories"
    )
    ap.add_argument(
        "--dry-run", "-n", action="store_true", help="Preview without renaming"
    )
    ap.add_argument("--undo", "-u", action="store_true", help="Undo the last operation")
    ap.add_argument("--log", metavar="FILE", help="Append rename log to FILE")
    ap.add_argument("--test", "-t", action="store_true", help="Run built-in test suite")
    args = ap.parse_args()

    if args.test:
        run_tests()
        return

    if args.folder:
        folder_str = args.folder
    else:
        print("\nEnter folder path (leave blank for current directory):")
        folder_str = input("  › ").strip().strip('"').strip("'") or "."

    folder = Path(folder_str).resolve()

    if args.undo:
        print(f"\n{'═'*W}")
        print("  ↩️   Undo Mode")
        print(f"{'═'*W}\n  📁  {folder}\n")
        do_undo(folder)
        return

    log_path = Path(args.log) if args.log else None
    process(
        folder_str, recursive=args.recursive, dry_run=args.dry_run, log_path=log_path
    )


if __name__ == "__main__":
    main()
