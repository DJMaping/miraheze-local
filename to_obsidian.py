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
from pathlib import Path

STATE_FILE = Path(".state.json")
VAULT = Path(r"C:\Users\danny\Documents\1 Ob Andah\Andah-Wiki")
ART_DIR = VAULT / "Articles"
CAT_DIR = VAULT / "Categories"

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
    rows = []
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
        key = k.replace("_", " ").strip()
        key = key[:1].upper() + key[1:]
        rows.append((key, v))
    if not rows:
        return ""
    md = ["", "|  |  |", "| --- | --- |"]
    for k, v in rows:
        md.append(f"| {k} | {v} |")
    md.append("")
    return "\n".join(md)


def convert_infoboxes(text: str) -> str:
    out, i = [], 0
    while True:
        m = re.search(r"\{\{\s*Infobox", text[i:], re.IGNORECASE)
        if not m:
            out.append(text[i:]); break
        start = i + m.start()
        out.append(text[i:start])
        tmpl, end = _find_template(text, start)
        if tmpl is None:
            out.append(text[start:]); break
        out.append(_render_infobox(tmpl))
        i = end
    return "".join(out)


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


def convert(title: str, raw: str) -> str:
    cats, body = extract_categories(raw)

    # redirect pages
    rm = re.match(r"^\s*#REDIRECT\s*\[\[([^\]\|]+)", body, re.IGNORECASE)
    redirect = rm.group(1).strip() if rm else None

    body = strip_refs(body)
    body = expand_data_templates(body)
    body = strip_file_links(body)
    body = convert_infoboxes(body)
    body = convert_tables(body)
    body = remove_templates(body)
    body = convert_external_links(body)
    body = convert_lists(body)
    body = convert_headings(body)
    body = convert_inline(body)
    body = collapse_blanks(body)

    fm = ["---"]
    fm.append(f'title: "{title}"')
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


def main():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    ART_DIR.mkdir(parents=True, exist_ok=True)
    CAT_DIR.mkdir(parents=True, exist_ok=True)

    n_main = n_cat = 0
    for title, info in state.items():
        path = Path(info["path"])
        parts = path.parts
        if "Main" in parts:
            base, kind = ART_DIR, "main"
        elif "Category" in parts:
            base, kind = CAT_DIR, "cat"
        else:
            continue
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")

        # category notes: title is "Category:Foo" -> use bare name for file + link
        disp_title = title.split(":", 1)[1] if kind == "cat" and ":" in title else title
        md = convert(disp_title, raw)
        out = safe_path(base, disp_title)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        if kind == "main":
            n_main += 1
        else:
            n_cat += 1

    print(f"Wrote {n_main} articles -> {ART_DIR}")
    print(f"Wrote {n_cat} categories -> {CAT_DIR}")


if __name__ == "__main__":
    main()
