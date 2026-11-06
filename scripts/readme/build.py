#!/usr/bin/env python3
"""
Builds the profile README from the "Loki Codex" design.

  python3 scripts/readme/build.py             # rebuild images + README.md (uses cached stats.json)
  python3 scripts/readme/build.py --refresh   # also re-fetch contribution stats via `gh`

How it works
  * src/*.svg        the design, one block per file (text is still live <text> here)
  * this script      stitches blocks into section images, then converts every glyph to a vector
                     path (positions come from Chrome's own text layout, outlines from the fonts in
                     fonts/), so the SVGs look identical anywhere - GitHub strips web fonts from images.
  * assets/readme/   the generated images the README points at
  * config.json      handle + every link

Needs: Python 3 with fontTools + brotli, Google Chrome (macOS path below), and `gh` for --refresh.
"""
import base64, hashlib, html, json, re, subprocess, sys, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SRC, FONTS, OUT = HERE / "src", HERE / "fonts", ROOT / "assets" / "readme"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)

W, GAP = 880, 14                      # design canvas width / vertical gap between sections
ROW_PAD, GRID_PAD = 8, 2          # transparent bottom pad per image (see build_images.add)
CFG = json.loads((HERE / "config.json").read_text())
FILE = {}                      # image name -> content-hashed file stem (filled in main); busts GitHub's image cache
sys.path.insert(0, str(HERE))
import blocks

# ---------------------------------------------------------------- measured HTML layout (nav + footer links)
# The design draws these two rows as HTML, so they were measured in Chrome (x relative to the 880px column).
NAV = [("identity", 120.188, 65.609), ("now", 233.625, 24.609), ("work", 306.063, 32.813),
       ("arsenal", 386.703, 57.406), ("codex", 491.938, 41.0), ("experiments", 580.766, 90.203),
       ("proof", 718.797, 41.0)]
NAV_SEPS = [203.797, 276.234, 356.875, 462.109, 550.938, 688.969]   # x of each rune separator
NAV_SEP_W, NAV_BASELINE, NAV_H = 11.828, 22, 36
FOOT = [("maximem", 283.984, 82.0), ("linkedin", 387.984, 65.609),
        ("medium", 475.594, 49.203), ("devto", 546.797, 49.203)]
FOOT_BASELINE, FOOT_H = 12, 22


# ================================================================ helpers
def read_src(name):
    return (SRC / f"{name}.svg").read_text(encoding="utf8").strip()


def head_attrs(svg):
    m = re.match(r"<svg([^>]*)>", svg)
    return dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1))), m.end()


def nested(name, x, y, text_fn=None):
    """A source block placed at (x, y) inside a bigger svg."""
    svg = read_src(name)
    if text_fn:
        svg = text_fn(svg)
    a, end = head_attrs(svg)
    inner = svg[end:-len("</svg>")]
    return f'<svg x="{x}" y="{y}" width="{a["width"]}" height="{a["height"]}" viewBox="{a["viewBox"]}">{inner}</svg>', \
           float(a["width"]), float(a["height"])


DEFS = (SRC / "defs.svg.part").read_text(encoding="utf8").strip()


def wrap(w, h, body, label):
    return (f'<svg xmlns="{NS}" width="{w:g}" height="{h:g}" viewBox="0 0 {w:g} {h:g}" role="img" '
            f'aria-label="{html.escape(label, quote=True)}">{DEFS}{body}</svg>')


def set_handle(svg):
    return svg.replace("[handle]", CFG["handle"])


# ================================================================ real-data proof section
def gh_graphql(query, **vars):
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in vars.items():
        cmd += ["-F", f"{k}={v}"]
    return json.loads(subprocess.check_output(cmd))


def fetch_stats(handle):
    q = """query($login:String!){user(login:$login){
      contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}
      repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){nodes{languages(first:8, orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""
    u = gh_graphql(q, login=handle)["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:3]
    return {"fetched": date.today().isoformat(), "total": cal["totalContributions"],
            "days": [d for w in cal["weeks"] for d in w["contributionDays"]],
            "languages": top}


LEVEL_COLOR = {"NONE": "#151D19", "FIRST_QUARTILE": "#1E5B40", "SECOND_QUARTILE": "#5C9A4C",
               "THIRD_QUARTILE": "#B6F36A", "FOURTH_QUARTILE": "#B6F36A"}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def streak(days):
    by = {d["date"]: d["contributionCount"] for d in days}
    cur = max(by)                                   # calendar's last day = today
    d = datetime.strptime(cur, "%Y-%m-%d").date()
    if by[cur] == 0:
        d -= timedelta(days=1)
    n = 0
    while by.get(d.isoformat(), 0) > 0:
        n += 1
        d -= timedelta(days=1)
    return n


def proof_block(stats):
    """The design's proof panel, with the placeholder pattern / [ N ] slots filled from real data."""
    svg = read_src("proof")
    days = sorted(stats["days"], key=lambda d: d["date"])
    # group into Sunday-first weeks, keep the last 53 (the design's 53 columns)
    weeks, cur, last_key = [], {}, None
    for d in days:
        dt = datetime.strptime(d["date"], "%Y-%m-%d").date()
        sunday = dt - timedelta(days=(dt.weekday() + 1) % 7)
        if sunday != last_key:
            if cur:
                weeks.append(cur)
            cur, last_key = {"sunday": sunday, "cells": {}}, sunday
        cur["cells"][(dt.weekday() + 1) % 7] = d
    weeks.append(cur)
    weeks = weeks[-53:]
    cells, labels, prev_label_col = [], [], -99
    for c, wk in enumerate(weeks):
        for r, d in wk["cells"].items():
            cells.append(f'<rect x="{24 + 15 * c}" y="{40 + 15 * r}" width="12" height="12" fill="{LEVEL_COLOR[d["contributionLevel"]]}"/>')
        first = wk["sunday"] + timedelta(days=min(wk["cells"]))
        if c == 0 or first.month != (weeks[c - 1]["sunday"] + timedelta(days=min(weeks[c - 1]["cells"]))).month:
            if c - prev_label_col >= 4 and c <= len(weeks) - 3:   # skip a label for a month that has barely started
                labels.append(f'<text x="{24 + 15 * c}" y="28">{MONTHS[first.month - 1]}</text>')
                prev_label_col = c
    svg = re.sub(r'(<g class="jb" font-size="10" fill="#858D88" letter-spacing="1">)<text x="24" y="28">NOV.*?</g>',
                 lambda m: m.group(1) + "".join(labels) + "</g>", svg, count=1, flags=re.S)
    svg = re.sub(r'<g fill="none" stroke-width="12">.*?</g>\s*</g>\s*(?=<g class="jb")',
                 "<g>" + "".join(cells) + "</g>\n", svg, count=1, flags=re.S)
    assert "stroke-dasharray" not in svg, "contribution grid replacement failed"
    # stat cards
    svg = svg.replace('>[ N ]</text><text class="jb" x="24" y="112" font-size="10" fill="#858D88">auto-generated · 12 months',
                      f'>{stats["total"]:,}</text><text class="jb" x="24" y="112" font-size="10" fill="#858D88">auto-generated · 12 months')
    svg = svg.replace('>[ N ]<tspan', f'>{streak(stats["days"])}<tspan')
    # language bars: same 220px track the design uses, split by share of the top three
    top = stats["languages"]
    tot = sum(s for _, s in top) or 1
    widths = [round(220 * s / tot) for _, s in top]
    widths[0] += 220 - sum(widths)
    xs = [24, 24 + widths[0] + 4, 24 + widths[0] + widths[1] + 8]
    bars = "".join(f'<rect x="{x}" y="56" width="{max(w - (4 if i < 2 else 0), 0)}" height="10" rx="2" fill="{c}"/>'
                   for i, (x, w, c) in enumerate(zip(xs, widths, ["#B6F36A", "#5C9A4C", "#1E5B40"])))
    svg = re.sub(r'<rect x="24" y="56" width="110".*?<rect x="256" y="56" width="0" height="10" fill="#D5AE62"></rect>',
                 bars, svg, count=1, flags=re.S)
    names = [n.upper() for n, _ in top] + ["", "", ""]
    svg = re.sub(r'● LANG 1   <tspan fill="#5C9A4C">● LANG 2</tspan>   <tspan fill="#1E5B40">● LANG 3</tspan>',
                 f'● {names[0]}   <tspan fill="#5C9A4C">● {names[1]}</tspan>   <tspan fill="#1E5B40">● {names[2]}</tspan>', svg)
    return svg


# ================================================================ compose the section images
def build_images(stats):
    """Returns {name: (svg_with_live_text, label)}"""
    imgs = {}

    def add(name, w, h, body, label, pad=None):
        # GitHub lays images out on text lines, which leaves ~6px below each one; a transparent pad
        # brings the gap to the design's 14px (8px between rows of the project grid).
        if pad is None:
            pad = 0 if name.startswith("foot-") else GRID_PAD if name in ("work-1", "work-2", "work-3", "work-4") else ROW_PAD
        imgs[name] = (wrap(w, h + pad, body, label), label)

    s, w, h = nested("hero", 0, 0)
    add("hero", w, h, s, "Anish Yadav. Designer by instinct. Engineer by curiosity. Founding Engineer at Maximem AI, designer, builder.")

    # nav: seven slices, one per link (each slice carries its trailing rune and its piece of the border lines)
    bounds = [0.0] + [sx + NAV_SEP_W + 9 for sx in NAV_SEPS] + [float(W)]
    for i, (name, x, tw) in enumerate(NAV):
        x0, x1 = bounds[i], bounds[i + 1]
        body = (f'<rect x="0" y="0" width="{x1 - x0:g}" height="1" fill="#29332D"/>'
                f'<rect x="0" y="{NAV_H - 1}" width="{x1 - x0:g}" height="1" fill="#29332D"/>'
                f'<text class="jb" x="{x - x0:g}" y="{NAV_BASELINE}" font-size="12" letter-spacing="1" fill="#B6F36A">{name}</text>')
        if i < len(NAV_SEPS):
            body += f'<text class="jb" x="{NAV_SEPS[i] - x0:g}" y="{NAV_BASELINE}" font-size="12" letter-spacing="1" fill="#D5AE62">ᛜ</text>'
        add(f"nav-{name}", x1 - x0, NAV_H, body, name)

    # 01 identity: banner + three aspect cards
    parts, y = [], 0
    s, w, h = nested("banner-identity", 0, 0); parts.append(s)
    for i, x in enumerate((0, 296, 592)):
        s, w, h = nested(f"aspect-{i + 1}", x, 48 + GAP); parts.append(s)
    add("identity", W, 48 + GAP + 200, "".join(parts), "01 Identity. Designer, Engineer, Experimenter.")

    s, w, h = nested("banner-now", 0, 0); add("now", W, h, s, "02 Currently building")
    s, w, h = nested("maximem", 0, 0)
    add("maximem", W, h, s, "Maximem AI. Founding Engineer. AI infrastructure and memory systems for AI agents. maximem.ai")

    s, w, h = nested("banner-work", 0, 0); add("work", W, h, s, "03 Selected work")
    for i in range(6):                                   # 2-column grid, 8px gutter baked into the canvases
        x = 0 if i % 2 == 0 else 4
        s, w, h = nested(f"card-{i + 1}", x, 0)
        add(f"work-{i + 1}", 440, h, s, CFG["links"]["projects"][i]["title"])

    s1, _, _ = nested("banner-arsenal", 0, 0); s2, _, h2 = nested("arsenal", 0, 48 + GAP)
    add("arsenal", W, 48 + GAP + h2, s1 + s2, "04 Engineering arsenal. Languages, front-end, backend and infra, AI and agents, design.")
    s1, _, _ = nested("banner-codex", 0, 0); s2, _, h2 = nested("codex", 0, 48 + GAP)
    add("codex", W, 48 + GAP + h2, s1 + s2, "05 The codex. Design the unknown. Memory is infrastructure. Fail gently, scale quietly. Build the impossible.")

    s, w, h = nested("banner-experiments", 0, 0); add("experiments", W, h, s, "06 Experiments")
    for i, (cw, x) in enumerate(((292, 0), (296, 4), (292, 4))):
        s, w, h = nested(f"exp-{i + 1}", x, 0)
        add(f"exp-{i + 1}", cw, h, s, f"Experiment 0{i + 1}")

    # 07 writing: banner + one full-width row per article (avatars embedded as data URIs)
    s, w, h = nested("banner-writing", 0, 0); add("writing", W, h, s, "07 Writing")
    for i, a in enumerate(CFG["articles"]):
        art = json.loads(json.dumps(a))
        for v in art["voices"]:
            f = HERE / "avatars" / f"{v['person'].get('avatar', '')}.jpg"
            v["person"]["avatar"] = base64.b64encode(f.read_bytes()).decode() if f.exists() else None
        (SRC / f"article-{i + 1}.svg").write_text(blocks.article_row(i + 1, art, measure)[0], encoding="utf8")
        s, w, h = nested(f"article-{i + 1}", 0, 0)
        add(f"article-{i + 1}", W, h, s, a["title"])

    # 08 proof + footer
    s1, _, _ = nested("banner-proof", 0, 0)
    p = proof_block(stats)
    a, end = head_attrs(p)
    s2 = f'<svg x="0" y="{48 + GAP}" width="{a["width"]}" height="{a["height"]}" viewBox="{a["viewBox"]}">{p[end:-6]}</svg>'
    s3, _, h3 = nested("footer", 0, 48 + GAP + 330 + GAP)
    add("proof", W, 48 + GAP + 330 + GAP + h3, s1 + s2 + s3, "08 Proof of work. Contribution graph, contributions, current streak, top languages. Chaos / creation. Anish Yadav, Bengaluru.")

    # footer links: four slices
    ends = [x + w for _, x, w in FOOT]
    fb = [FOOT[0][1] - 11] + [(ends[i] + FOOT[i + 1][1]) / 2 for i in range(3)] + [ends[-1] + 11]
    for i, (name, x, tw) in enumerate(FOOT):
        x0, x1 = fb[i], fb[i + 1]
        shown = {"maximem": "maximem.ai", "devto": "dev.to"}.get(name, name)
        body = (f'<text class="jb" x="{x - x0:g}" y="{FOOT_BASELINE}" font-size="12" letter-spacing="1" fill="#B6F36A">{shown}</text>')
        add(f"foot-{name}", x1 - x0, FOOT_H, body, name)
    return imgs


# ================================================================ glyph outlining
FAMILY_FILES = {"Space Grotesk": ["space-grotesk.woff2"],
                "Cormorant Garamond": ["cormorant-garamond-italic.woff2"],
                "JetBrains Mono": ["jetbrains-mono.woff2"],
                "Noto Sans Runic": ["noto-sans-runic-runic.woff2", "noto-sans-runic-latin.woff2"]}
FALLBACK = json.loads((FONTS / "fallback-glyphs.json").read_text(encoding="utf8"))
_font_cache = {}


def font_instance(fname, weight):
    key = (fname, weight)
    if key not in _font_cache:
        f = TTFont(FONTS / fname)
        if "fvar" in f:
            axis = f["fvar"].axes[0]
            f = instancer.instantiateVariableFont(f, {"wght": max(axis.minValue, min(axis.maxValue, weight))}, inplace=False)
        _font_cache[key] = (f, f.getBestCmap(), f.getGlyphSet(), f["head"].unitsPerEm)
    return _font_cache[key]


def measure(kind, size, weight, text):
    fname = {"sg": "space-grotesk.woff2", "cg": "cormorant-garamond-italic.woff2"}[kind]
    f, cmap, _, upm = font_instance(fname, weight)
    return sum(f["hmtx"][cmap.get(ord(c), "space")][0] for c in text) / upm * size


def glyph(family, weight, ch):
    """-> (cache-key, path data, units-per-em)"""
    for fname in FAMILY_FILES[family]:
        f, cmap, gs, upm = font_instance(fname, weight)
        if ord(ch) in cmap:
            name = cmap[ord(ch)]
            pen = SVGPathPen(gs, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
            gs[name].draw(pen)
            return f"{fname}:{weight}:{name}", pen.getCommands(), upm
    if ch in FALLBACK:
        g = FALLBACK[ch]
        return f"fallback:{ch}", g["d"], g["upm"]
    raise SystemExit(f"no glyph for {ch!r} (U+{ord(ch):04X}) in {family}")


MEASURE_JS = r"""
(async()=>{
 await Promise.all([...document.fonts].map(f=>f.load().catch(()=>0)));
 await document.fonts.ready;
 const hex=c=>{const m=c.match(/[\d.]+/g).map(Number);return '#'+m.slice(0,3).map(v=>Math.round(v).toString(16).padStart(2,'0')).join('')};
 const out={};
 document.querySelectorAll('[data-img]').forEach(box=>{
  const res=[];
  box.querySelectorAll('text').forEach(t=>{
   const items=[];
   (function walk(n){for(const c of n.childNodes){
     if(c.nodeType===3){for(const ch of c.data)items.push({el:n,ch})}
     else if(c.nodeType===1&&(c.tagName==='tspan'||c.tagName==='textPath'))walk(c)}})(t);
   const proc=[];let prevSp=true;
   for(const it of items){let ch=it.ch;if(/\s/.test(ch)){ch=' ';if(prevSp)continue;prevSp=true}else prevSp=false;proc.push({el:it.el,ch})}
   while(proc.length&&proc[proc.length-1].ch===' ')proc.pop();
   const n=t.getNumberOfChars();
   if(n!==proc.length){res.push({error:'count mismatch '+n+' vs '+proc.length+' in '+t.textContent});return}
   const chars=[];
   proc.forEach((it,i)=>{ if(it.ch===' ')return;
     const p=t.getStartPositionOfChar(i),cs=getComputedStyle(it.el);
     chars.push({ch:it.ch,x:p.x,y:p.y,rot:t.getRotationOfChar(i),fs:parseFloat(cs.fontSize),
       fam:cs.fontFamily.split(',')[0].replace(/["']/g,'').trim(),w:parseInt(cs.fontWeight),
       fill:hex(cs.fill),fo:parseFloat(cs.fillOpacity)})});
   res.push({chars});
  });
  out[box.dataset.img]=res;
 });
 document.getElementById('__m').textContent=JSON.stringify(out);
})();
"""
PAGE_CSS = (""".sg{font-family:'Space Grotesk',system-ui,sans-serif}.cg{font-family:'Cormorant Garamond',Georgia,serif;font-style:italic}
.jb{font-family:'JetBrains Mono',ui-monospace,monospace}.rn{font-family:'Noto Sans Runic','Segoe UI Historic',sans-serif}
body{margin:0}""")


def font_faces():
    r = []
    for fam, fname, style, rng in [("Space Grotesk", "space-grotesk.woff2", "normal", "300 700"),
                                   ("Cormorant Garamond", "cormorant-garamond-italic.woff2", "italic", "300 700"),
                                   ("JetBrains Mono", "jetbrains-mono.woff2", "normal", "400 800"),
                                   ("Noto Sans Runic", "noto-sans-runic-runic.woff2", "normal", "400"),
                                   ("Noto Sans Runic", "noto-sans-runic-latin.woff2", "normal", "400")]:
        ur = "U+16A0-16F8" if "runic.woff2" in fname else "U+0000-00FF,U+2000-206F"
        r.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{rng};src:url(file://{FONTS / fname}) format('woff2');unicode-range:{ur}}}")
    return "".join(r)


def outline_all(imgs):
    """Replace every <text> in every image with glyph <path>/<use> elements."""
    boxes = "".join(f'<div data-img="{n}">{svg}</div>' for n, (svg, _) in imgs.items())
    page = (f"<!doctype html><meta charset=utf-8><style>{font_faces()}{PAGE_CSS}</style>"
            f'<pre id="__m"></pre>{boxes}<script>{MEASURE_JS}</script>')
    with tempfile.TemporaryDirectory() as td:
        pf = Path(td) / "measure.html"
        pf.write_text(page, encoding="utf8")
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--virtual-time-budget=20000",
                              "--dump-dom", f"file://{pf}"], capture_output=True, text=True).stdout
    m = re.search(r'<pre id="__m">(.*?)</pre>', dom, re.S)
    if not m or not m.group(1).strip():
        raise SystemExit("Chrome measurement produced no output")
    data = json.loads(html.unescape(m.group(1)))

    result = {}
    for name, (svg, label) in imgs.items():
        root = ET.fromstring(svg)
        parent = {c: p for p in root.iter() for c in p}
        texts = list(root.iter(f"{{{NS}}}text"))
        measured = data[name]
        assert len(texts) == len(measured), f"{name}: text count mismatch"
        defs, defmap = [], {}
        for t, mres in zip(texts, measured):
            if "error" in mres:
                raise SystemExit(f"{name}: {mres['error']}")
            g = ET.Element(f"{{{NS}}}g")
            for c in mres["chars"]:
                key, d, upm = glyph(c["fam"], c["w"], c["ch"])
                if key not in defmap:
                    defmap[key] = f"g{len(defmap)}"
                    p = ET.Element(f"{{{NS}}}path", {"id": defmap[key], "d": d})
                    defs.append(p)
                s = c["fs"] / upm
                tr = f'translate({c["x"]:.2f} {c["y"]:.2f})' + (f' rotate({c["rot"]:.2f})' if abs(c["rot"]) > 0.005 else "") + f" scale({s:.5f} {-s:.5f})"
                attrs = {"href": f"#{defmap[key]}", "transform": tr, "fill": c["fill"]}
                if c["fo"] < 1:
                    attrs["fill-opacity"] = f'{c["fo"]:g}'
                ET.SubElement(g, f"{{{NS}}}use", attrs)
            par = parent[t]
            par[list(par).index(t)] = g
        # drop leftover textPath carriers (the ring path stays harmless; remove if unused)
        gdefs = ET.Element(f"{{{NS}}}defs")
        gdefs.extend(defs)
        root.insert(0, gdefs)
        out = ET.tostring(root, encoding="unicode")
        out = re.sub(r"\sclass=\"[^\"]*\"", "", out)
        result[name] = out
    return result


# ================================================================ README
def readme():
    L = CFG["links"]
    pct = lambda w: f"{w / W * 100 * 0.998:.3f}".rstrip("0").rstrip(".")   # tiny safety margin so rows never wrap

    def img(name, w=W, alt=""):
        return f'<img src="assets/readme/{FILE.get(name, name)}.svg" width="{pct(w) if w < W else "100"}%" alt="{html.escape(alt, quote=True)}">'

    def link(href, tag):
        return f'<a href="{href}">{tag}</a>'

    nav_w = {n: b - a for n, (a, b) in zip([n for n, *_ in NAV],
                                           zip([0.0] + [sx + NAV_SEP_W + 9 for sx in NAV_SEPS], [sx + NAV_SEP_W + 9 for sx in NAV_SEPS] + [float(W)]))}
    ends = [x + w for _, x, w in FOOT]
    fb = [FOOT[0][1] - 11] + [(ends[i] + FOOT[i + 1][1]) / 2 for i in range(3)] + [ends[-1] + 11]
    anchors = "identity now work arsenal codex experiments proof".split()   # nav keeps the original 7 entries
    ex = [i for i in range(3)]

    def project(i):
        p = L["projects"][i]
        tag = img(f"work-{i + 1}", 440, p["title"] + (" (private)" if p.get("private") else ""))
        return tag if p.get("private") else link(f"https://github.com/{CFG['handle']}/{p['repo']}", tag)

    work = [project(i) for i in range(6)]
    exp = "".join(link(L["experiments"][i]["url"], img(f"exp-{i + 1}", (292, 296, 292)[i], f"Experiment 0{i + 1}")) for i in ex)
    art = "<br>\n  ".join(link(CFG["articles"][i]["url"], img(f"article-{i + 1}", W, CFG["articles"][i]["title"])) for i in range(3))
    foot = "".join(link(L[n], img(f"foot-{n}", fb[i + 1] - fb[i], n)) for i, (n, *_) in enumerate(FOOT))
    lines = [
        img("hero", alt="Anish Yadav. Designer by instinct. Engineer by curiosity. Founding Engineer at Maximem AI."),
        "".join(link(f"#{n}", img(f"nav-{n}", nav_w[n], n)) for n in anchors),
        '<a name="identity"></a>' + img("identity", alt="01 Identity. Designer, Engineer, Experimenter."),
        '<a name="now"></a>' + img("now", alt="02 Currently building"),
        link(L["maximem"], img("maximem", alt="Maximem AI. Founding Engineer. maximem.ai")),
        '<a name="work"></a>' + img("work", alt="03 Selected work"),
        work[0] + work[1], work[2] + work[3], work[4] + work[5],
        '<a name="arsenal"></a>' + img("arsenal", alt="04 Engineering arsenal"),
        '<a name="codex"></a>' + img("codex", alt="05 The codex"),
        '<a name="experiments"></a>' + img("experiments", alt="06 Experiments"),
        exp,
        '<a name="writing"></a>' + img("writing", alt="07 Writing"),
        art,
        '<a name="proof"></a>' + img("proof", alt="08 Proof of work"),
        foot,
    ]
    return '<p align="center">\n  ' + "<br>\n  ".join(lines) + "\n</p>\n"


# ================================================================ main
def write_blocks():
    for i, p in enumerate(CFG["links"]["projects"]):
        (SRC / f"card-{i + 1}.svg").write_text(blocks.card_svg(i + 1, p, CFG["handle"]), encoding="utf8")
    (SRC / "arsenal.svg").write_text(blocks.arsenal_svg(CFG["arsenal"]), encoding="utf8")
    (SRC / "banner-writing.svg").write_text(blocks.banner_svg("07", "WRITING", "ᚹ", 36 + 12 * 11.8 + 1.4), encoding="utf8")
    (SRC / "banner-proof.svg").write_text(blocks.banner_svg("08", "PROOF OF WORK", "ᛞ", 256), encoding="utf8")


def main():
    write_blocks()
    stats_path = HERE / "stats.json"
    if "--refresh" in sys.argv or not stats_path.exists():
        stats_path.write_text(json.dumps(fetch_stats(CFG["handle"]), indent=1))
        print("fetched contribution stats")
    stats = json.loads(stats_path.read_text())

    imgs = build_images(stats)
    done = outline_all(imgs)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for name, svg in done.items():
        FILE[name] = f"{name}.{hashlib.sha1(svg.encode('utf8')).hexdigest()[:8]}"
        (OUT / f"{FILE[name]}.svg").write_text(svg, encoding="utf8")
    (ROOT / "README.md").write_text(readme(), encoding="utf8")
    total = sum(len(s) for s in done.values())
    print(f"wrote {len(done)} images ({total / 1024:.0f} KB) to {OUT.relative_to(ROOT)} and README.md")


if __name__ == "__main__":
    main()
