#!/usr/bin/env python3
from __future__ import annotations
import re, sys, json, argparse, difflib
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from typing import Optional

VIDEO_EXT    = {".mp4",".mkv",".avi",".mov",".wmv",".m4v",".ts",".flv",".webm",
                ".ogv",".rmvb",".divx",".mpg",".mpeg",".vob",".m2ts",".mts",
                ".3gp",".f4v",".asf",".rm",".wtv",".dvr-ms",".iso",".strm"}
SUBTITLE_EXT = {".srt",".sub",".ass",".ssa",".vtt",".idx",".smi",".sbv",".dfxp",".ttml"}

_LANG2 = {
    "af","ak","sq","am","ar","hy","az","eu","be","bn","bs","bg","my","ca","zh","hr",
    "cs","da","nl","en","et","fi","fr","gl","ka","de","el","gu","he","hi","hu","is",
    "id","ga","it","ja","kn","kk","km","ko","lo","lv","lt","mk","ms","ml","mt","mr",
    "mn","ne","no","nb","nn","or","ps","fa","pl","pt","pa","ro","ru","sr","sk","sl",
    "so","es","sw","sv","ta","te","th","tr","uk","ur","uz","vi","cy","yo","zu",
}
_LANG3 = {
    "afr","sqi","alb","amh","ara","hye","arm","aze","eus","baq","bel","ben","bos","bul",
    "mya","bur","cat","zho","chi","hrv","ces","cze","dan","nld","dut","eng","est","fin",
    "fra","fre","glg","kat","geo","deu","ger","ell","gre","guj","heb","hin","hun","isl",
    "ice","ind","gle","ita","jpn","kan","kaz","khm","kor","lao","lav","lit","mkd","mac",
    "msa","may","mal","mlt","mar","mon","nep","nor","ori","pus","fas","per","pol","por",
    "pan","ron","rum","rus","srp","slk","slo","slv","som","spa","swa","swe","tam","tel",
    "tha","tur","ukr","urd","uzb","vie","cym","wel","yor","zul",
}
_LOCALES: set[str] = set()
for _lc in list(_LANG2):
    for _rc in ["BR","PT","TW","HK","CN","MX","AR","US","GB","AU","CA","ES","IN"]:
        _LOCALES.add(f"{_lc}-{_rc}")
        _LOCALES.add(f"{_lc}_{_rc}")
ALL_LANGS = _LANG3 | _LANG2 | _LOCALES

_LANG_TAIL = re.compile(
    r"[._\- ]+(" + "|".join(sorted(ALL_LANGS, key=len, reverse=True)) + r")$",
    re.IGNORECASE,
)

def _norm_lang(code: str) -> str:
    for sep in ("-", "_"):
        if sep in code:
            a, b = code.split(sep, 1)
            return f"{a.lower()}-{b.upper()}"
    return code.lower()

_SEED_PATTERNS = [
    re.compile(r"^\d{3,4}[ip]$", re.I),
    re.compile(r"^[48][kK]$"),
    re.compile(r"^(?:UHD|FHD|QHD|SDR|WCG|HDR|HDR10|HLG|DV|DoVi)$", re.I),
    re.compile(r"^(?:BluRay|BDRip|BDRemux|WEBRip|WEBDL|WEB|HDTV|DVDRip|HDDVD|REMUX|SCREENER|DVDSCR|PDTV|VDRIP)$", re.I),
    re.compile(r"^(?:x264|x265|h264|h265|HEVC|AVC|AV1|VP9|XviD|DivX|NVENC|QSV|VC1|MPEG2|MPEG4)$", re.I),
    re.compile(r"^(?:AAC|AC3|EAC3|DTS|DTSHD|DTSMA|DTSX|TrueHD|Atmos|FLAC|MP3|Opus|PCM|LPCM|DD|DDP|DD5|DDP5|DD51|DDP51|EAC3)$", re.I),
    re.compile(r"^(?:PROPER|REPACK|RERIP|EXTENDED|THEATRICAL|UNRATED|IMAX|HYBRID|RETAIL|READNFO|FESTIVAL|RESTORED|REMASTERED|DIRECTORS|CRITERION)$", re.I),
    re.compile(r"^(?:MULTI|DUAL|DUBBED|SUBBED|HARDSUB|SYNC|SYNCED|RESYNC|FIXED|CORRECTED|SDH|NORDIC|INTERNAL|COMPLETE)$", re.I),
    re.compile(r"^(?:AMZN|AMAZON|NF|NETFLIX|DSNP|DISNEY|HULU|HBO|HBOMAX|ATVP|APPLETV|PCOK|PEACOCK|VUDU|MUBI|TUBI|PLUTO|PRIME|PARAMOUNT|CRACKLE|SHUDDER|STARZ|EPIX|SHOWTIME|STAN|BINGE|ITVX|CRAV|CBSAA|SKYSHOWTIME|CANAL|HOTSTAR|ZEE5|SONYLIV|GLOBOPLAY|TVING|WAVVE|MAX|HMAX)$", re.I),
    re.compile(r"^(?:YIFY|YTS|RARBG|EZTV|FGT|EVO|CMRG|NTG|FLUX|ION10|GGEZ|NOGRP|AMIABLE|SPARKS|GECKOS|DIMENSION|KILLERS|DEFLATE|BLUDV|VPPV|TEPES|ROVERS)$", re.I),
    re.compile(r"^\d+$"),
    re.compile(r"^[A-Z][A-Z0-9]{7,}$"),
]

def _is_seed_junk(tok: str) -> bool:
    return any(p.match(tok) for p in _SEED_PATTERNS)

_COMPOUND_TECH = [
    (re.compile(r"\bBlu[\s\-]?[Rr]ay\b"),        "BluRay"),
    (re.compile(r"\bWEB[\s\-\.]?DL\b", re.I),    "WEBDL"),
    (re.compile(r"\bH[\s\.]?265\b",    re.I),    "H265"),
    (re.compile(r"\bH[\s\.]?264\b",    re.I),    "H264"),
    (re.compile(r"\bDD[P+][\s\.]?\d[\s\.]?\d\b", re.I), "DDP51"),
    (re.compile(r"\bDD[\s\.]?\d[\s\.]?\d\b",     re.I), "DD51"),
    (re.compile(r"\bAC[\s\-\.]?3\b",   re.I),    "AC3"),
    (re.compile(r"\bDTS[\s\-]?HD\b",   re.I),    "DTSHD"),
    (re.compile(r"\bDTS[\s\-]?MA\b",   re.I),    "DTSMA"),
    (re.compile(r"\bTrue[\s\-]?HD\b",  re.I),    "TrueHD"),
    (re.compile(r"\bHDR[\s\-]?10\+?\b",re.I),    "HDR10"),
    (re.compile(r"\bDolby[\s\.]Vision\b", re.I), "DV"),
]

def _preprocess(text: str) -> str:
    for pat, repl in _COMPOUND_TECH:
        text = pat.sub(repl, text)
    return text

_EP_PATS = [
    re.compile(r"[Ss](\d{1,2})\s?[Ee](\d{1,3})(?:\s?[\-Ee](\d{1,3}))+"),
    re.compile(r"[Ss](\d{1,2})\s?[Ee](\d{1,3})"),
    re.compile(r"[Ss](\d{1,2})[._][Ee](\d{1,3})"),
    re.compile(r"(?<!\d)(\d{1,2})[xX](\d{2,3})(?!\d)"),
    re.compile(r"Season\s*(\d+)\s+(?:Episode|Ep\.?)\s*(\d+)", re.IGNORECASE),
    re.compile(r"[Ss](\d)[Ee](\d{1,3})(?!\d)"),
    re.compile(r"[Ss](?:eason)?\s*(\d+)\s+[Ee](?:p(?:isode)?)?\s*(\d+)", re.IGNORECASE),
]
_DATE_EP   = re.compile(r"(20\d\d)[.\-_ ](0[1-9]|1[0-2])[.\-_ ](0[1-9]|[12]\d|3[01])(?=[.\-_ ]|$)")
_ANIME_EP  = re.compile(r"(?:[\[\s\-._]+|^)(\d{2,4})(?:v\d)?(?:[\]\s\-._]+|$)")
_YEAR_RE   = re.compile(r"[\(\[\s._\-]*((?:19[2-9]\d|20[0-2]\d))[\)\]\s._\-]*")
_HASH_RE   = re.compile(r"[\[\(][0-9A-Fa-f]{6,10}[\]\)]")
_GRPLEAD   = re.compile(r"^\s*[\[\(][^\]\)]{1,50}[\]\)]\s*")
_TRAIL_SEP = re.compile(r"[\s\-_,\.(]+$")
_LEAD_SEP  = re.compile(r"^[\s\-_,\.)]+")
_MULTI_SPC = re.compile(r"  +")

_CONTRACTIONS = {
    r"\bDont\b":"Don't",    r"\bWont\b":"Won't",     r"\bCant\b":"Can't",
    r"\bShouldnt\b":"Shouldn't", r"\bWouldnt\b":"Wouldn't", r"\bCouldnt\b":"Couldn't",
    r"\bDidnt\b":"Didn't",  r"\bDoesnt\b":"Doesn't",  r"\bHasnt\b":"Hasn't",
    r"\bHadnt\b":"Hadn't",  r"\bIsnt\b":"Isn't",      r"\bArent\b":"Aren't",
    r"\bWasnt\b":"Wasn't",  r"\bWerent\b":"Weren't",  r"\bHavent\b":"Haven't",
    r"\bMustnt\b":"Mustn't", r"\bNeednt\b":"Needn't",
    r"\bIve\b":"I've",      r"\bIll\b":"I'll",        r"\bIm\b":"I'm",    r"\bId\b":"I'd",
    r"\bYouve\b":"You've",  r"\bYoull\b":"You'll",    r"\bYoure\b":"You're", r"\bYoud\b":"You'd",
    r"\bHes\b":"He's",      r"\bHell\b":"He'll",      r"\bHed\b":"He'd",
    r"\bShes\b":"She's",    r"\bShell\b":"She'll",    r"\bShed\b":"She'd",  r"\bIts\b":"It's",
    r"\bWeve\b":"We've",    r"\bWell\b":"We'll",      r"\bWere\b":"We're",  r"\bWed\b":"We'd",
    r"\bTheyve\b":"They've", r"\bTheyll\b":"They'll", r"\bTheyre\b":"They're", r"\bTheyd\b":"They'd",
    r"\bThats\b":"That's",  r"\bTheres\b":"There's",  r"\bWhos\b":"Who's",
    r"\bWhats\b":"What's",  r"\bWheres\b":"Where's",  r"\bLets\b":"Let's",   r"\bHeres\b":"Here's",
    r"\bHows\b":"How's",
}

def _restore_contractions(text: str) -> str:
    for pat, repl in _CONTRACTIONS.items():
        text = re.sub(pat, repl, text)
    return text

def _smart_dots(text: str) -> str:
    def _sub(m: re.Match) -> str:
        p = m.start()
        pre  = re.search(r"(\w+)$", text[:p])
        post = re.search(r"^(\w+)",  text[p + 1:])
        if pre and post and len(pre.group(1)) == 1 and len(post.group(1)) == 1:
            return "."
        return " "
    return re.sub(r"\.", _sub, text)

def _normalize(stem: str) -> str:
    stem = stem.replace("_", " ")
    stem = _smart_dots(stem)
    return _MULTI_SPC.sub(" ", stem).strip()

def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "", name)
    return name.rstrip(". ")

def _extract_year(text: str) -> tuple[str, str]:
    m = _YEAR_RE.search(text)
    if not m:
        return "", text
    yr = m.group(1)
    if not (1920 <= int(yr) <= 2030):
        return "", text
    left  = text[:m.start()].rstrip(" ._-([")
    right = text[m.end():].lstrip(" ._-)]")
    return yr, (left + (" " if left and right else "") + right).strip()

def _extract_lang(stem: str) -> tuple[str, str]:
    m = _LANG_TAIL.search(stem)
    return (_norm_lang(m.group(1)), stem[:m.start()]) if m else ("", stem)

def _infer_season(folder: Path) -> int:
    pats = [
        re.compile(r"(?:Season|Series|Saison|Stagione|Staffel|Temporada|Sezon)\s*(\d+)", re.I),
        re.compile(r"^[Ss](?:eason)?\s*\.?\-?\s*(\d{1,2})$"),
        re.compile(r"^[Ss](\d{1,2})$"),
    ]
    for p in pats:
        mm = p.search(folder.name)
        if mm:
            return int(mm.group(1))
    return 0


class JunkClassifier:
    def __init__(self, stems: list[str]):
        self._learned: set[str] = set()
        n = len(stems)
        if n < 2:
            return

        doc_freq: dict[str, int] = defaultdict(int)
        positions: dict[str, list[float]] = defaultdict(list)

        for stem in stems:
            tokens = re.findall(r"[A-Za-z0-9]+", stem)
            n_tok  = max(len(tokens), 1)
            seen: set[str] = set()
            for i, tok in enumerate(tokens):
                key = tok.lower()
                if key not in seen:
                    doc_freq[key] += 1
                    seen.add(key)
                positions[key].append(i / n_tok)

        for tok, freq in doc_freq.items():
            df    = freq / n
            pos   = sum(positions[tok]) / len(positions[tok])
            upper = tok.upper() == tok and len(tok) >= 2
            seed  = _is_seed_junk(tok)
            num   = bool(re.match(r"^\d+$", tok))

            score = df * 3.0 + pos * 1.5
            if upper: score += 0.4
            if seed:  score += 3.0
            if num:   score += 1.0

            if score >= 2.2:
                self._learned.add(tok)

    def is_junk(self, tok: str) -> bool:
        return tok.lower() in self._learned or _is_seed_junk(tok)

    def cut_title(self, raw: str) -> str:
        raw = re.sub(r"^[\s\-_]*[\[\(][^\]\)]{0,60}[\]\)]\s*", "", raw).strip()
        raw = _preprocess(raw)
        raw = re.sub(r"[\s._\-]+[A-Z][A-Z0-9]{1,15}$", "", raw).strip()
        cut = len(raw)
        for m in re.finditer(r"[A-Za-z0-9]+", raw):
            if self.is_junk(m.group()):
                cut = m.start()
                break
        result = raw[:cut]
        result = re.sub(r"\s*[\(\[][^\(\)\[\]]{0,80}[\)\]]\s*$", "", result)
        result = _TRAIL_SEP.sub("", result).strip()
        result = _LEAD_SEP.sub("", result).strip()
        result = re.sub(r"^[\[\(][^\]\)]*$", "", result).strip()
        return _restore_contractions(_MULTI_SPC.sub(" ", result).strip())

    def cut_show(self, raw: str) -> str:
        raw = _preprocess(raw)
        raw = re.sub(r"[\s._\-]+[A-Z][A-Z0-9]{1,15}$", "", raw).strip()
        tokens = list(re.finditer(r"[A-Za-z0-9]+", raw))
        tokens.reverse()
        cut = len(raw)
        for m in tokens:
            if self.is_junk(m.group()):
                cut = m.start()
            else:
                break
        result = raw[:cut]
        return _TRAIL_SEP.sub("", result).strip()

    def parse(self, stem: str, folder_season: int = 0) -> tuple[str, str, str]:
        lang, stem = _extract_lang(stem)
        stem = _HASH_RE.sub(" ", stem)
        is_anime = bool(_GRPLEAD.match(stem))
        stem = _GRPLEAD.sub("", stem).strip()
        stem = _normalize(stem)

        dm = _DATE_EP.search(stem)
        if dm:
            date_code = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
            before = stem[:dm.start()].strip(" -_.")
            after  = stem[dm.end():].strip(" -_.")
            yr, show_raw = _extract_year(before)
            show = self.cut_show(show_raw)
            title = self.cut_title(after)
            show_full = f"{show} ({yr})" if yr else show
            parts = [show_full, date_code] + ([title] if title else [])
            return _sanitize(" - ".join(parts)), lang, date_code

        ep_match = None
        for pat in _EP_PATS:
            ep_match = pat.search(stem)
            if ep_match:
                break

        if ep_match:
            g = ep_match.groups()
            try:
                s  = int(g[0]) if g[0] else 0
                e  = int(g[1]) if len(g) > 1 and g[1] else 0
                e2 = int(g[2]) if len(g) > 2 and g[2] else 0
            except (TypeError, ValueError):
                s = e = e2 = 0
            if folder_season and s == 0:
                s = folder_season
            code = f"S{s:02d}E{e:02d}-E{e2:02d}" if (e2 and e2 != e) else f"S{s:02d}E{e:02d}"

            before = stem[:ep_match.start()].strip()
            after  = stem[ep_match.end():].strip()

            yr, show_raw = _extract_year(before)
            show_raw = _TRAIL_SEP.sub("", show_raw).strip()
            show = self.cut_show(show_raw) or show_raw
            title = self.cut_title(_LEAD_SEP.sub("", after).strip())

            show_full = f"{show} ({yr})" if yr else show
            parts = [show_full, code] + ([title] if title else [])
            return _sanitize(" - ".join(parts)), lang, code

        if is_anime:
            am = _ANIME_EP.search(stem)
            if am:
                ep = int(am.group(1))
                if 1 <= ep <= 9999:
                    before = stem[:am.start()].strip(" -_")
                    after  = stem[am.end():].strip(" -_")
                    show   = self.cut_show(before) or before.strip()
                    title  = self.cut_title(after)
                    code   = f"E{ep:02d}"
                    parts  = [show, code] + ([title] if title else [])
                    return _sanitize(" - ".join(parts)), lang, code

        m_yr = _YEAR_RE.search(stem)
        if m_yr:
            yr   = m_yr.group(1)
            left = stem[:m_yr.start()].rstrip(" ._-([")
            show = self.cut_show(left) or left
            show_full = f"{show} ({yr})" if yr else show
        else:
            show = self.cut_show(stem) or stem
            show_full = show
        return _sanitize(show_full), lang, ""


@dataclass
class FileEntry:
    path:        Path
    new_stem:    str
    old_stem:    str
    lang:        str   = ""
    code:        str   = ""
    is_video:    bool  = False
    fuzzy:       bool  = False
    fuzzy_score: float = 0.0
    matched_vid: Optional[Path] = None


def _fuzzy(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    al, bl = a.lower(), b.lower()
    seq = difflib.SequenceMatcher(None, al, bl).ratio()
    ta  = set(re.findall(r"[a-z0-9]+", al))
    tb  = set(re.findall(r"[a-z0-9]+", bl))
    tok = len(ta & tb) / max(len(ta), len(tb)) if ta and tb else 0.0
    return 0.55 * seq + 0.45 * tok

def _resolve(stem: str, ext: str, used: set[str]) -> str:
    if (stem + ext) not in used:
        return stem
    for i in range(2, 500):
        c = f"{stem}.{i}"
        if (c + ext) not in used:
            return c
    return stem

def _strip_lang_from_stem(stem: str) -> str:
    m = _LANG_TAIL.search(stem)
    return stem[:m.start()] if m else stem

def build_plan(videos: list[Path], subs: list[Path], folder: Path) -> tuple[list[FileEntry], list[Path]]:
    folder_season = _infer_season(folder)
    raw_stems = [_GRPLEAD.sub("", _HASH_RE.sub(" ", p.stem)).strip() for p in videos + subs]
    clf = JunkClassifier(raw_stems)

    vid_entries: list[FileEntry]       = []
    vid_by_code: dict[str, FileEntry]  = {}
    used:        set[str]              = set()
    entries:     list[FileEntry]       = []
    unmatched:   list[Path]            = []

    for vp in videos:
        clean, lang, code = clf.parse(vp.stem, folder_season)
        final = _resolve(clean, vp.suffix.lower(), used)
        used.add(final + vp.suffix.lower())
        e = FileEntry(path=vp, new_stem=final, old_stem=vp.stem, lang=lang,
                      code=code, is_video=True)
        vid_entries.append(e)
        entries.append(e)
        if code:
            vid_by_code[code] = e

    def _sub_stem(base: str, sub_lang: str) -> str:
        bare = _strip_lang_from_stem(base)
        return bare + ("." + sub_lang if sub_lang else "")

    def _title_of(e: FileEntry) -> str:
        m = re.search(r" - S\d+E\d+ - (.+)$", e.new_stem)
        return m.group(1).lower() if m else ""

    for sp in subs:
        _, sub_lang, sub_code = clf.parse(sp.stem, folder_season)
        ext = sp.suffix.lower()
        fe  = FileEntry(path=sp, new_stem=sp.stem, old_stem=sp.stem,
                        lang=sub_lang, code=sub_code)
        matched = False

        if sub_code and sub_code in vid_by_code:
            raw = _sub_stem(vid_by_code[sub_code].new_stem, sub_lang)
            fe.new_stem    = _resolve(raw, ext, used)
            fe.matched_vid = vid_by_code[sub_code].path
            matched = True

        if not matched and vid_entries:
            _, _, _ = clf.parse(sp.stem, folder_season)
            sub_clean, _, _ = clf.parse(sp.stem, folder_season)
            sub_title = re.sub(r"[^a-z0-9 ]", "", sub_clean.lower())

            best_score, best_ve = 0.0, None
            for ve in vid_entries:
                if sub_code and ve.code and sub_code != ve.code:
                    continue
                score = _fuzzy(sub_title, re.sub(r"[^a-z0-9 ]", "", ve.new_stem.lower()))
                if score > best_score:
                    best_score, best_ve = score, ve

            if best_ve and best_score >= 0.65:
                raw = _sub_stem(best_ve.new_stem, sub_lang)
                fe.new_stem    = _resolve(raw, ext, used)
                fe.fuzzy       = True
                fe.fuzzy_score = best_score
                fe.matched_vid = best_ve.path
                matched = True

        if not matched:
            clean_self, sl, _ = clf.parse(sp.stem, folder_season)
            if clean_self and clean_self != sp.stem:
                fe.new_stem = _resolve(clean_self + ("." + sl if sl else ""), ext, used)
            else:
                unmatched.append(sp)
                entries.append(fe)
                continue

        used.add(fe.new_stem + ext)
        entries.append(fe)

    return entries, unmatched


UNDO_FILE = ".subtitle_renamer_undo.json"

def _load_undo(folder: Path) -> list[dict]:
    p = folder / UNDO_FILE
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception:
        return []

def _save_undo(folder: Path, log: list[dict]) -> None:
    p = folder / UNDO_FILE
    try:
        existing = _load_undo(folder)
        p.write_text(json.dumps(existing + log, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _do_rename(path: Path, new_stem: str) -> tuple[bool, str]:
    dst = path.parent / (new_stem + path.suffix.lower())
    if path == dst:
        return False, ""
    if dst.exists():
        return False, f"Target exists: {dst.name}"
    try:
        path.rename(dst)
        return True, ""
    except Exception as ex:
        return False, str(ex)

def _scan(folder: Path, recursive: bool) -> tuple[list[Path], list[Path]]:
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

W = 74

def _preview(entries: list[FileEntry], unmatched: list[Path]) -> None:
    changes = [e for e in entries if e.old_stem != e.new_stem]
    clean   = len(entries) - len(changes)
    print(f"\n  " + "─" * 70)
    print(f"  📋  {len(changes)} changes  │  {clean} already clean  │  {len(unmatched)} unrecognized")
    print("  " + "─" * 70 + "\n")

    vid_subs: dict[Path, list[FileEntry]] = defaultdict(list)
    for e in changes:
        if not e.is_video and e.matched_vid:
            vid_subs[e.matched_vid].append(e)

    shown: set[Path] = set()
    for e in changes:
        if not e.is_video:
            continue
        shown.add(e.path)
        print(f"  🎬 {e.path.name}")
        print(f"     \033[92m{e.new_stem}{e.path.suffix.lower()}\033[0m")
        for se in vid_subs.get(e.path, []):
            shown.add(se.path)
            tag = f"  \033[90m(fuzzy {se.fuzzy_score*100:.0f}%)\033[0m" if se.fuzzy else ""
            print(f"     📄 {se.path.name}")
            print(f"        \033[96m{se.new_stem}{se.path.suffix.lower()}\033[0m{tag}")
        print()

    for e in changes:
        if e.path in shown:
            continue
        shown.add(e.path)
        tag  = f"  \033[90m(fuzzy {e.fuzzy_score*100:.0f}%)\033[0m" if e.fuzzy else ""
        icon = "🎬" if e.is_video else "📄"
        print(f"  {icon} {e.path.name}")
        print(f"     \033[96m{e.new_stem}{e.path.suffix.lower()}\033[0m{tag}")
        print()

    if unmatched:
        print("  " + "─" * 70)
        print("  ⚠️  Unrecognized — will not be renamed:\n")
        for p in unmatched:
            print(f"     - {p.name}")
        print()


def process(folder_path: str, recursive: bool = False, dry_run: bool = False,
            log_path: Optional[Path] = None) -> None:
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        print(f"\n  ❌  Folder not found: {folder_path}")
        sys.exit(1)

    mode = "  ─  DRY RUN" if dry_run else ""
    print(f"\n{'═' * W}")
    print(f"  🎬  Ultra Media File Cleaner{mode}")
    print(f"{'═' * W}")
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
        print(f"  ✅  All {len(entries)} files already clean!\n")
        return

    _preview(entries, unmatched)
    print("  " + "═" * 70)

    if dry_run:
        print("  ℹ️  Dry-run — no files changed.\n")
        return
    if not changes:
        print("  ✅  Nothing to change.\n")
        return

    try:
        ans = input(f"  ⚡  {len(changes)} file(s) will be renamed. Continue? (y/n): ").strip().lower()
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
                print(f"  ⚠️  {e.path.name}  →  {msg}")
            skip += 1

    if undo_log:
        _save_undo(folder, undo_log)
    if log_path and log_lines:
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("\n".join(log_lines) + "\n")
            print(f"\n  📝  Log: {log_path}")
        except Exception as ex:
            print(f"\n  ⚠️  Log write failed: {ex}")

    print(f"\n{'═' * W}")
    print(f"  ✅  {ok} succeeded  │  {skip} skipped")
    print(f"  💡  To undo: python subtitle_renamer.py \"{folder}\" --undo\n")


def do_undo(folder: Path) -> None:
    log = _load_undo(folder)
    if not log:
        print("  ℹ️  No operations to undo.")
        return
    print(f"\n  {len(log)} operations will be reverted:\n")
    for entry in reversed(log):
        src, dst = Path(entry["new"]), Path(entry["old"])
        if src.exists():
            try:
                src.rename(dst)
                print(f"  ✅ {src.name}  ↩  {dst.name}")
            except Exception as ex:
                print(f"  ❌ {src.name}: {ex}")
        else:
            print(f"  ⚠️  Not found: {src.name}")
    (folder / UNDO_FILE).unlink(missing_ok=True)
    print()


_TESTS: list[tuple[str, str]] = [
    ("From (2022) - S01E08 - Broken Windows, Open Doors (1080p AMZN WEB-DL x265 t3nzin)",
     "From (2022) - S01E08 - Broken Windows, Open Doors"),
    ("From_S01E08_Broken_Windows_Open_Doors_1080p_AMZN_WEB-DL_DDP5_1_H_264-TEPES_synced",
     "From - S01E08 - Broken Windows Open Doors"),
    ("From (2022) - S01E02",                                    "From (2022) - S01E02"),
    ("Breaking.Bad.S01E08.Cancer.Man.1080p.BluRay.x264-ROVERS", "Breaking Bad - S01E08 - Cancer Man"),
    ("The.Boys.S03E06.Herogasm.2160p.UHD.BluRay.HDR.DV.x265.Atmos-GROUP",
     "The Boys - S03E06 - Herogasm"),
    ("Succession.S04E09.Church.and.State.1080p.NF.WEB-DL.DD5.1.H.264",
     "Succession - S04E09 - Church and State"),
    ("The.Wire.2x08.Duck.And.Cover.720p.HDTV",                  "The Wire - S02E08 - Duck And Cover"),
    ("Game.of.Thrones.S06E09E10.The.Battle.of.the.Bastards.1080p.BluRay",
     "Game of Thrones - S06E09-E10 - The Battle of the Bastards"),
    ("The.Dark.Knight.2008.1080p.BluRay.x264.YIFY",             "The Dark Knight (2008)"),
    ("Oppenheimer.2023.2160p.UHD.BluRay.HDR.DV.x265.Atmos-GROUP",
     "Oppenheimer (2023)"),
    ("S.W.A.T.S02E14.720p.WEB-DL",                             "S.W.A.T - S02E14"),
    ("[Commie] Attack on Titan - 25 [BD 1080p AAC] [ABCD1234]", "Attack on Titan - E25"),
    ("Peaky_Blinders_S05E06_Mr_Jones_1080p_AMZN_WEB-DL_DDP5_1_H_264-NTG",
     "Peaky Blinders - S05E06 - Mr Jones"),
    ("Breaking.Bad.S01E08.Cancer.Man.1080p.BluRay.tr",
     "Breaking Bad - S01E08 - Cancer Man.tr"),
    ("Show.S02E03.Episode.Title.1080p.WEB-DL.pt-BR",
     "Show - S02E03 - Episode Title.pt-BR"),
    ("The.Late.Show.2024.03.15.Guest.Name.WEB.x264",
     "The Late Show - 2024-03-15 - Guest Name"),
    ("Friends_S02E14_The.One.Where.Weve.Heard.This.Before.DVDRip",
     "Friends - S02E14 - The One Where We've Heard This Before"),
    ("House.of.the.Dragon.S01E10.1080p.HBOMAX.WEB-DL.DDP5.1.x264",
     "House of the Dragon - S01E10"),
    ("The.Last.of.Us.S01E09.Look.for.the.Light.1080p.HBOMAX.WEB-DL",
     "The Last of Us - S01E09 - Look for the Light"),
    ("Stranger.Things.S04E09.The.Piggyback.1080p.NF.WEB-DL",
     "Stranger Things - S04E09 - The Piggyback"),
    ("The.Mandalorian.S03E08.4K.HDR.DV.DSNP.WEB-DL.x265.Atmos",
     "The Mandalorian - S03E08"),
    ("Breaking Bad - S01E08 - Cancer Man",                      "Breaking Bad - S01E08 - Cancer Man"),
    ("The Dark Knight (2008)",                                  "The Dark Knight (2008)"),
    ("Doctor.Who.Season.1.Episode.9.The.Empty.Child.DVDRip",
     "Doctor Who - S01E09 - The Empty Child"),
    ("Severance.S02E10.Bye.Bye.Now.2160p.ATVP.WEB-DL.DDP5.1.HDR.H.265",
     "Severance - S02E10 - Bye Bye Now"),
    ("Shogun.2024.S01E10.Crimson.Sky.1080p.HULU.WEB-DL.DDP5.1.H.264",
     "Shogun (2024) - S01E10 - Crimson Sky"),
    ("[Erai-raws] Frieren - Beyond Journeys End - 28 [1080p] [ENG SUB]",
     "Frieren - Beyond Journeys End - E28"),
    ("Fallout.S01E08.The.Beginning.2160p.AMZN.WEB-DL.DDP5.1.HDR.H.265-FLUX",
     "Fallout - S01E08 - The Beginning"),
    ("A.Real.Pain.2024.1080p.WEB-DL.DDP5.1.Atmos.H264-CMRG",   "A Real Pain (2024)"),
    ("Dune.Part.Two.2024.2160p.UHD.BluRay.HDR.DV.x265.Atmos",  "Dune Part Two (2024)"),
    ("The.Penguin.S01E06.All.Happy.Families.2160p.MAX.WEB-DL.DDP5.1.HDR.H.265",
     "The Penguin - S01E06 - All Happy Families"),
    ("Agatha.All.Along.S01E09.1080p.DSNP.WEB-DL.DDP5.1.H.264-NTG",
     "Agatha All Along - S01E09"),
    ("The.Substance.2024.2160p.MUBI.WEB-DL.DDP5.1.SDR.H.265",  "The Substance (2024)"),
    ("Breaking.Bad.S01E08.Cancer.Man.COMPLETELYFAKEGROUP.INVENTEDCODEC.RANDOMBYTES",
     "Breaking Bad - S01E08 - Cancer Man"),
    ("Show.S03E05.Episode.Name.XYZFAKESERVICE.FAKECODEC2024.NEWUNKNOWNTAG",
     "Show - S03E05 - Episode Name"),
    ("From (2022) - S01E08 - Broken Windows, Open Doors (1080p AMZN WEB-DL x265 t3nzin).UNKNOWNTAG.ANOTHERJUNK",
     "From (2022) - S01E08 - Broken Windows, Open Doors"),
]

def run_tests() -> None:
    print(f"\n{'═' * W}")
    print("  🧪  Test Mode")
    print(f"{'═' * W}\n")
    clf = JunkClassifier([])
    ok = fail = 0
    for stem, expected in _TESTS:
        clean, lang, _ = clf.parse(stem)
        result = (clean + ("." + lang if lang else "")).rstrip()
        if result == expected:
            ok += 1
            print(f"  ✅ {stem[:66]}")
            print(f"     → {result}\n")
        else:
            fail += 1
            print(f"  ❌ {stem[:66]}")
            print(f"     Expected : {expected}")
            print(f"     Got      : {result}\n")
    print("─" * W)
    print(f"  Result: {ok} passed / {fail} failed  ({ok}/{ok+fail})\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="subtitle_renamer",
        description="Ultra Media File Cleaner — corpus-learning junk detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python subtitle_renamer.py
  python subtitle_renamer.py "D:/Shows/Breaking Bad/Season 1"
  python subtitle_renamer.py /media/Movies --dry-run
  python subtitle_renamer.py /media/Shows --recursive
  python subtitle_renamer.py /media/Shows --undo
  python subtitle_renamer.py /media/Shows --log rename.log
  python subtitle_renamer.py --test
""",
    )
    ap.add_argument("folder",      nargs="?", default=None)
    ap.add_argument("--recursive", "-r", action="store_true")
    ap.add_argument("--dry-run",   "-n", action="store_true")
    ap.add_argument("--undo",      "-u", action="store_true")
    ap.add_argument("--log",             metavar="FILE")
    ap.add_argument("--test",      "-t", action="store_true")
    args = ap.parse_args()

    if args.test:
        run_tests()
        return

    folder_str = args.folder
    if not folder_str:
        print("\nEnter folder path (blank = current directory):")
        folder_str = input("  › ").strip().strip('"').strip("'") or "."

    folder = Path(folder_str).resolve()

    if args.undo:
        print(f"\n{'═' * W}\n  ↩️  Undo Mode\n{'═' * W}\n  📁  {folder}\n")
        do_undo(folder)
        return

    process(folder_str, recursive=args.recursive, dry_run=args.dry_run,
            log_path=Path(args.log) if args.log else None)


if __name__ == "__main__":
    main()
