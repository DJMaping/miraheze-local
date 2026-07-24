"""
to_obsidian.py — Convert pulled MediaWiki pages into an Obsidian vault.

Reads page titles + paths from .state.json, converts Main + Category namespace
pages from MediaWiki markup to clean Obsidian markdown, and writes them into
the target vault. Categories on each page become YAML frontmatter tags.

Read-only against the wiki/GitHub; only writes into the Obsidian vault.
"""

import os
import re
import json
import argparse
from pathlib import Path

from dotenv import load_dotenv

# Secrets live outside the repo (~/.miraheze-secrets/.env); local .env is a fallback.
load_dotenv(Path.home() / ".miraheze-secrets" / ".env")
load_dotenv()

STATE_FILE = Path(".state.json")


def resolve_vault(cli_vault=None):
    """Locate the Obsidian vault: --vault arg > OBSIDIAN_VAULT env > sibling default."""
    if cli_vault:
        return Path(cli_vault).expanduser().resolve()
    env = os.environ.get("OBSIDIAN_VAULT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent / "Andah-Wiki"

# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

NOISE_TEMPLATES = (
    "short description", "reflist", "clear", "both", "toc", "notelist",
    "authority control", "portal", "commons category", "use dmy dates",
    "use british english", "use mdy dates", "refbegin", "refend", "div col",
    "div col end", "hatnote", "main", "see also",
)
NOISE_RE = re.compile(
    r"\{\{\s*(?:" + "|".join(re.escape(t) for t in NOISE_TEMPLATES) + r")\b[^{}]*\}\}",
    re.IGNORECASE,
)


def strip_refs(text: str) -> str:
    text = re.sub(r"<ref[^>]*?/>", "", text)
    text = re.sub(r"<ref[^>]*?>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text


# maintenance / tracking categories that shouldn't become content tags
BLOCK_CAT = re.compile(
    r"(template|pages using|pages with|lua|wikipedia|microformat|hcard|"
    r"tracking|sidebars|needing conversion|jsonconfig|wikiminiatlas|"
    r"duplicate arguments|metatemplate|documentation|hatnote|"
    r"script error|template loop)",
    re.IGNORECASE,
)


def extract_categories(text: str):
    cats = re.findall(r"\[\[\s*Category\s*:\s*([^\]\|]+?)\s*(?:\|[^\]]*)?\]\]", text, re.IGNORECASE)
    text = re.sub(r"\[\[\s*Category\s*:[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    cats = [c.strip() for c in cats if c.strip() and not BLOCK_CAT.search(c)]
    # de-dupe, preserve order
    seen, out = set(), []
    for c in cats:
        if c.lower() not in seen:
            seen.add(c.lower()); out.append(c)
    return out, text


def remove_templates(text: str) -> str:
    # flag templates
    text = re.sub(r"\{\{\s*flagicon\s*\|[^{}]*\}\}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{\s*flag(?:country)?\s*\|\s*([^|{}]+?)\s*(?:\|[^{}]*)?\}\}", r"[[\1]]", text, flags=re.IGNORECASE)
    # named noise templates
    text = NOISE_RE.sub("", text)
    # magic words
    text = re.sub(r"__[A-Z]+__", "", text)
    # html comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text


_ARROWS = {
    "increase": "▲", "decrease": "▼", "steady": "▬", "nochange": "▬",
    "increaseneutral": "▲", "increase neutral": "▲",
    "decreaseneutral": "▼", "decrease neutral": "▼",
    "steadyneutral": "▬",
}
_DROP_T = {"white", "worldpop", "stub", "documentation", "noflag", "flagdeco",
           "clear", "both", "-", "spaces", "nbsp", "dot", "flagicon",
           "left", "right", "center", "table alignment", "tree list",
           "tree list/end", "col-begin", "col-end", "col-break"}
_LISTJOIN = {"flaglist", "flatlist", "plainlist", "hlist", "ubl",
             "unbulleted list", "collapsible list", "nowrap", "nowraplinks"}


def _expand_one(m):
    body = m.group(1).strip()
    if not body:
        return ""
    parts = [p.strip() for p in body.split("|")]
    name = parts[0].strip().lower()
    pos = [a for a in parts[1:] if not re.match(r"^[\w ]+\s*=", a)]
    if name in _ARROWS:
        return _ARROWS[name]
    if name in _DROP_T:
        return ""
    if name == "lahn":
        return (pos[0] + " lahn") if pos else "lahn"
    if name in ("convert", "cvt"):
        return " ".join(pos[:2]) if len(pos) >= 2 else (pos[0] if pos else "")
    if name == "km2 mi2":
        return (pos[0] + " km²") if pos else ""
    if name == "sort":
        return pos[-1] if pos else ""
    if name in ("nts", "ntsh", "number", "n+p", "val", "rnd"):
        return pos[0] if pos else ""
    if name == "percentagebar":
        return (pos[0] + "%") if pos else ""
    if name == "start date":
        return pos[0] if pos else ""
    if name in ("goal", "pengoal"):
        suff = " (pen.)" if name == "pengoal" else ""
        scorers = ", ".join(a + "'" for a in pos if a)
        return (scorers + suff) if scorers else ""
    if name in ("flag", "flagcountry"):
        return f"[[{pos[0]}]]" if pos else ""
    if name in _LISTJOIN:
        return ", ".join(a for a in pos if a)
    if name == "tl":
        return pos[0] if pos else ""
    if name == "aet":
        return "(a.e.t.)"
    if name == "penmiss":
        return "✗"
    if name in ("n/a", "n/a.", "nadash", "ndash"):
        return "N/A" if name.startswith("n/a") else "–"
    if name == "tooltip":
        return pos[0] if pos else ""
    return m.group(0)  # unknown: leave untouched


def expand_data_templates(text: str) -> str:
    inner = re.compile(r"\{\{([^{}]*)\}\}")
    for _ in range(8):
        new = inner.sub(_expand_one, text)
        if new == text:
            break
        text = new
    return text


def strip_file_links(text: str) -> str:
    # remove [[File:...]] / [[Image:...]] embeds (handles one nested [[...]] in caption)
    pattern = re.compile(r"\[\[\s*(?:File|Image)\s*:(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]", re.IGNORECASE)
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub("", text)
    return text


def convert_external_links(text: str) -> str:
    text = re.sub(r"\[(https?://\S+)\s+([^\]]+)\]", r"[\2](\1)", text)
    text = re.sub(r"\[(https?://\S+)\]", r"\1", text)
    return text


def clean_cell(c: str) -> str:
    c = c.strip()
    # strip leading cell attributes:  style="..." | content
    if "|" in c:
        head, _, tail = c.partition("|")
        if re.search(r"(style|colspan|rowspan|align|scope|width|class|bgcolor|valign|text-align)\s*=", head, re.IGNORECASE) \
           or "=" in head and len(head) < 60:
            c = tail.strip()
    c = remove_templates(c)
    c = re.sub(r"'''(.+?)'''", r"**\1**", c)
    c = re.sub(r"''(.+?)''", r"*\1*", c)
    c = c.replace("\n", " ").strip()
    return c


def _find_template(text: str, start: int):
    """Given start at '{{', return (template_text, end_index) with balanced braces."""
    depth, i = 0, start
    n = len(text)
    while i < n - 1:
        two = text[i:i + 2]
        if two == "{{":
            depth += 1; i += 2; continue
        if two == "}}":
            depth -= 1; i += 2
            if depth == 0:
                return text[start:i], i
            continue
        i += 1
    return None, None


def _split_params(inner: str):
    """Split template body on top-level '|' (ignoring nested {{ }} and [[ ]])."""
    parts, buf, d, b = [], "", 0, 0
    i, n = 0, len(inner)
    while i < n:
        two = inner[i:i + 2]
        if two == "{{":
            d += 1; buf += two; i += 2; continue
        if two == "}}":
            d -= 1; buf += two; i += 2; continue
        if two == "[[":
            b += 1; buf += two; i += 2; continue
        if two == "]]":
            b -= 1; buf += two; i += 2; continue
        ch = inner[i]
        if ch == "|" and d == 0 and b == 0:
            parts.append(buf); buf = ""; i += 1; continue
        buf += ch; i += 1
    parts.append(buf)
    return parts


def _skip_param(k: str) -> bool:
    kl = k.lower()
    if kl.startswith("image") or kl.startswith("map_"):
        return True
    if kl in ("symbol_type", "native_name", "map_caption", "blank_emblem_type"):
        return True
    return kl.endswith(("_size", "_ref", "caption", "_darkstyle", "_alt", "_emblem"))


def _render_infobox(tmpl: str):
    inner = tmpl[2:-2]
    parts = _split_params(inner)
    template = re.sub(r"^\s*infobox\b\s*", "", parts[0], flags=re.IGNORECASE).strip().lower()
    rows = []
    fields = {}
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k, v = k.strip(), v.strip()
        if not v or _skip_param(k):
            continue
        v = re.sub(r"<br\s*/?>", ", ", v, flags=re.IGNORECASE)
        v = strip_refs(v)
        v = remove_templates(v)
        v = convert_inline(v)
        v = re.sub(r"\s+", " ", v).strip().strip(",").strip()
        if not v:
            continue
        fields[k.lower()] = v
        key = k.replace("_", " ").strip()
        key = key[:1].upper() + key[1:]
        rows.append((key, v))
    meta = {"template": template, "fields": fields}
    if not rows:
        return "", meta
    md = ["", "|  |  |", "| --- | --- |"]
    for k, v in rows:
        md.append(f"| {k} | {v} |")
    md.append("")
    return "\n".join(md), meta


def convert_infoboxes(text: str):
    """Render infoboxes to markdown tables; also return the first infobox's
    parsed {template, fields} dict for typed-frontmatter extraction."""
    out, i = [], 0
    meta = None
    while True:
        m = re.search(r"\{\{\s*Infobox", text[i:], re.IGNORECASE)
        if not m:
            out.append(text[i:]); break
        start = i + m.start()
        out.append(text[i:start])
        tmpl, end = _find_template(text, start)
        if tmpl is None:
            out.append(text[start:]); break
        md, m_meta = _render_infobox(tmpl)
        out.append(md)
        if meta is None or (not meta.get("fields") and m_meta.get("fields")):
            meta = m_meta
        i = end
    return "".join(out), (meta or {"template": None, "fields": {}})


def convert_tables(text: str) -> str:
    out_lines = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("{|"):
            # collect block to matching |}
            depth = 0
            block = []
            while i < len(lines):
                s = lines[i].lstrip()
                if s.startswith("{|"):
                    depth += 1
                if s.startswith("|}"):
                    depth -= 1
                    block.append(lines[i])
                    i += 1
                    if depth == 0:
                        break
                    continue
                block.append(lines[i])
                i += 1
            out_lines.extend(render_table(block))
        else:
            out_lines.append(lines[i])
            i += 1
    return "\n".join(out_lines)


def render_table(block):
    caption = None
    rows, cur = [], None
    for ln in block:
        s = ln.strip()
        if s.startswith("{|") or s.startswith("|}"):
            continue
        if s.startswith("|+"):
            caption = clean_cell(s[2:]); continue
        if s.startswith("|-"):
            if cur is not None:
                rows.append(cur)
            cur = []
            continue
        if cur is None:
            cur = []
        if s.startswith("!"):
            for c in re.split(r"!!", s[1:]):
                cur.append(clean_cell(c))
        elif s.startswith("|"):
            for c in re.split(r"\|\|", s[1:]):
                cur.append(clean_cell(c))
        else:
            # continuation of previous cell
            if cur:
                cur[-1] = (cur[-1] + " " + clean_cell(s)).strip()
    if cur:
        rows.append(cur)
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return [f"**{caption}**", ""] if caption else []

    md = []
    if caption:
        cap = caption.strip().strip("*").strip()
        md.append(f"**{cap}**")
        md.append("")
    md.append("|  |  |")
    md.append("| --- | --- |")
    for r in rows:
        cells = [c for c in r]
        if len(cells) == 1:
            md.append(f"| **{cells[0]}** |  |")
        else:
            key = cells[0]
            val = " ".join(cells[1:]).strip()
            md.append(f"| {key} | {val} |")
    md.append("")
    return md


def convert_headings(text: str) -> str:
    def repl(m):
        eq = m.group(1)
        title = m.group(2).strip()
        return "#" * len(eq) + " " + title
    return re.sub(r"^(={2,6})\s*(.*?)\s*\1\s*$", repl, text, flags=re.MULTILINE)


def convert_lists(text: str) -> str:
    out = []
    for ln in text.split("\n"):
        m = re.match(r"^([#*]+)\s+(.*)$", ln)
        if m:
            marks, rest = m.group(1), m.group(2)
            indent = "    " * (len(marks) - 1)
            marker = "1." if marks[-1] == "#" else "-"
            out.append(f"{indent}{marker} {rest}")
        else:
            out.append(ln)
    return "\n".join(out)


def convert_inline(text: str) -> str:
    text = re.sub(r"'''(.+?)'''", r"**\1**", text)
    text = re.sub(r"''(.+?)''", r"*\1*", text)
    return text


def collapse_blanks(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def tag_slug(cat: str) -> str:
    s = re.sub(r"[^0-9A-Za-z _/-]", "", cat).strip()
    s = re.sub(r"\s+", "-", s)
    return s


# ---------------------------------------------------------------------------
# Typed frontmatter (second-brain enrichment)
# ---------------------------------------------------------------------------

_ARROW_CHARS = "▲▼▬"
_NUMERIC_KEYS = {"population", "population_year", "area_km2", "hdi", "year", "countries"}
EMIT_AS_LIST = {"official_languages", "denominations"}

# Per-type field maps: (frontmatter_key, lowercased infobox/source key)
_COUNTRY_FIELDS = [
    ("capital", "capital"),
    ("largest_city", "largest_city"),
    ("population", "population_estimate"),
    ("area_km2", "area_km2"),
    ("gdp_ppp", "gdp_ppp"),
    ("gdp_nominal", "gdp_nominal"),
    ("hdi", "hdi"),
    ("currency", "currency"),
    ("government", "government_type"),
    ("demonym", "demonym"),
    ("official_languages", "official_languages"),
]
_CONTINENT_FIELDS = [
    ("area", "area"),
    ("population", "population"),
    ("gdp_ppp", "gdp_ppp"),
    ("gdp_nominal", "gdp_nominal"),
    ("gdp_per_capita", "gdp_per_capita"),
    ("countries", "countries"),
    ("demonym", "demonym"),
]
_CITY_FIELDS = [
    ("settlement_type", "settlement_type"),
    ("population", "population_total"),
    ("population_year", "population_as_of"),
    ("demonym", "population_demonym"),
]
_WORLDCUP_FIELDS = [
    ("year", "year"),
    ("host", "host"),
    ("dates", "dates"),
    ("teams", "teams"),
    ("champion", "champion"),
    ("runner_up", "runner_up"),
    ("third_place", "third_place"),
    ("top_scorer", "top_scorer"),
    ("best_player", "best_player"),
]

_WC_TITLE_RE = re.compile(r"^\d{4}\s+FLLA\s+World\s+Cup$", re.IGNORECASE)
_WC_LABELS = {
    "host country": "host", "host": "host", "host countries": "host",
    "dates": "dates",
    "teams": "teams",
    "champion": "champion", "champions": "champion",
    "runner-up": "runner_up", "runners-up": "runner_up", "runner up": "runner_up",
    "third place": "third_place",
    "top scorer": "top_scorer", "top scorers": "top_scorer", "top scorer(s)": "top_scorer",
    "best player": "best_player",
}


def yaml_scalar(v) -> str:
    """Double-quote and escape a value for safe YAML frontmatter."""
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _clean_value(v: str) -> str:
    v = v.strip().lstrip(_ARROW_CHARS).strip()
    v = re.sub(r"(?i)\blahn(?=\d)", "lahn ", v)  # {{lahn}} expands glued to the figure
    return v


def _numish(v: str):
    """Return a bare numeric string if v is purely numeric (commas/units-free), else None."""
    core = re.sub(r"\s*\([^)]*\)\s*$", "", v).strip()   # drop a trailing "(1765)" etc.
    core = core.lstrip(_ARROW_CHARS).strip().replace(",", "")
    return core if re.fullmatch(r"\d+(?:\.\d+)?", core) else None


def _delink(x: str) -> str:
    return re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", x)


def _split_list(v: str):
    out, seen = [], set()
    for item in v.split(","):
        it = _delink(item.strip().lstrip("*").strip()).strip().strip(",").strip()
        if not it or it.endswith(":") or re.fullmatch(r"[\W_]+", it):
            continue
        if "[[" in it or "]]" in it:            # drop mangled wikilink fragments
            continue
        if it.lower() in seen:
            continue
        seen.add(it.lower())
        out.append(it)
    return out


def _detect_type(title: str, template, cats, is_category: bool) -> str:
    """First match wins: title pattern > infobox template > clean category > generic."""
    if is_category:
        return "category"
    if _WC_TITLE_RE.match(title.strip()):
        return "worldcup"
    t = (template or "").lower()
    if t in ("country", "former country", "nation"):
        return "country"
    if t == "continent":
        return "continent"
    if t in ("settlement", "city"):
        return "city"
    if t == "officeholder":
        return "person"
    catset = {c.lower() for c in cats}
    if "flla confederations" in catset or "confederations" in catset:
        return "confederation"
    if "religions" in catset or "religion" in catset:
        return "religion"
    return "article"


def _clean_wc_value(v: str) -> str:
    v = strip_refs(v)
    v = remove_templates(v)        # drops {{Flagicon|...}}, maps {{flag|X}} -> [[X]]
    v = convert_inline(v)          # ''' -> **, '' -> *
    v = v.replace("*", "")         # strip emphasis markers for a clean scalar
    v = re.sub(r"\s+", " ", v).strip().strip("|").strip()
    return v


def extract_worldcup(raw: str, title: str) -> dict:
    """Pull World Cup edition details from the page's hand-rolled infobox table."""
    fields = {}
    ym = re.match(r"(\d{4})", title.strip())
    if ym:
        fields["year"] = ym.group(1)
    m = re.search(r'\{\|\s*class="[^"]*infobox', raw, re.IGNORECASE)
    if not m:
        return fields
    block = raw[m.start():]
    end = block.find("|}")
    if end != -1:
        block = block[:end]
    for line in block.split("\n"):
        s = line.strip()
        if not s.startswith("|") or s.startswith(("|-", "|+", "|}")):
            continue
        if "||" not in s:
            continue
        label, _, value = s[1:].partition("||")
        key = _WC_LABELS.get(label.strip().lower())
        if not key or key in fields:
            continue
        cv = _clean_wc_value(value)
        if cv:
            fields[key] = cv
    return fields


def build_typed_frontmatter(title, cats, ibox, wc, is_category):
    """Return YAML lines for `type:` plus typed properties for the note."""
    ibox = ibox or {}
    template = ibox.get("template")
    fields = ibox.get("fields", {})
    ntype = _detect_type(title, template, cats, is_category)
    lines = [f"type: {ntype}"]

    if ntype == "worldcup":
        spec, src = _WORLDCUP_FIELDS, (wc or {})
    elif ntype == "country":
        spec, src = _COUNTRY_FIELDS, fields
    elif ntype == "continent":
        spec, src = _CONTINENT_FIELDS, fields
    elif ntype == "city":
        spec, src = _CITY_FIELDS, fields
    else:
        spec, src = [], {}

    for out_key, in_key in spec:
        raw_val = src.get(in_key)
        if raw_val is None or raw_val == "":
            continue
        val = _clean_value(str(raw_val))
        if not val:
            continue
        if out_key in EMIT_AS_LIST:
            items = _split_list(val)
            if not items:
                continue
            lines.append(f"{out_key}:")
            lines.extend(f"  - {yaml_scalar(it)}" for it in items)
        elif out_key in _NUMERIC_KEYS:
            num = _numish(val)
            lines.append(f"{out_key}: {num}" if num is not None else f"{out_key}: {yaml_scalar(val)}")
        else:
            lines.append(f"{out_key}: {yaml_scalar(val)}")
    return lines


def convert(title: str, raw: str, is_category: bool = False) -> str:
    cats, body = extract_categories(raw)

    # redirect pages
    rm = re.match(r"^\s*#REDIRECT\s*\[\[([^\]\|]+)", body, re.IGNORECASE)
    redirect = rm.group(1).strip() if rm else None

    body = strip_refs(body)
    body = expand_data_templates(body)
    body = strip_file_links(body)
    body, ibox = convert_infoboxes(body)
    body = convert_tables(body)
    body = remove_templates(body)
    body = convert_external_links(body)
    body = convert_lists(body)
    body = convert_headings(body)
    body = convert_inline(body)
    body = collapse_blanks(body)

    wc = extract_worldcup(raw, title) if _WC_TITLE_RE.match(title.strip()) else None

    fm = ["---"]
    fm.append(f"title: {yaml_scalar(title)}")
    fm.extend(build_typed_frontmatter(title, cats, ibox, wc, is_category))
    if cats:
        fm.append("tags:")
        for c in cats:
            fm.append(f"  - {tag_slug(c)}")
    fm.append(f"source: https://andah.miraheze.org/wiki/{title.replace(' ', '_')}")
    fm.append("---")
    front = "\n".join(fm)

    if redirect:
        return f"{front}\n\n> Redirect to [[{redirect}]]\n"
    return f"{front}\n\n{body}"


_BAD = '<>:"\\|?*'


def safe_path(base: Path, title: str) -> Path:
    # keep '/' as subfolders, replace other illegal chars
    parts = title.split("/")
    parts = ["".join("-" if ch in _BAD else ch for ch in p).strip() or "_" for p in parts]
    p = base.joinpath(*parts)
    return p.with_suffix(".md")


def main(vault: Path):
    art_dir = vault / "Articles"
    cat_dir = vault / "Categories"
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    art_dir.mkdir(parents=True, exist_ok=True)
    cat_dir.mkdir(parents=True, exist_ok=True)

    n_main = n_cat = 0
    for title, info in state.items():
        path = Path(info["path"])
        parts = path.parts
        if "Main" in parts:
            base, kind = art_dir, "main"
        elif "Category" in parts:
            base, kind = cat_dir, "cat"
        else:
            continue
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")

        # category notes: title is "Category:Foo" -> use bare name for file + link
        disp_title = title.split(":", 1)[1] if kind == "cat" and ":" in title else title
        md = convert(disp_title, raw, is_category=(kind == "cat"))
        out = safe_path(base, disp_title)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        if kind == "main":
            n_main += 1
        else:
            n_cat += 1

    print(f"Wrote {n_main} articles -> {art_dir}")
    print(f"Wrote {n_cat} categories -> {cat_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Export pulled MediaWiki pages into an Obsidian vault.")
    ap.add_argument("--vault", help="Target vault path (overrides OBSIDIAN_VAULT env and the default).")
    args = ap.parse_args()
    main(resolve_vault(args.vault))
