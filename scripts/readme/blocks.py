"""Generates the project cards and the arsenal block from config.json.

The card and arsenal markup copies the Loki Codex design exactly; only the content comes from config.
"""
import html, math

GREEN, GOLD = "#B6F36A", "#D5AE62"
MONO_ADV = 6.3 + 1.0          # JetBrains Mono 10.5px + 1px letter-spacing (tag + repo text)


def esc(s):
    return html.escape(s, quote=True)


def card_svg(n, p, handle):
    """One 436x168 project card. A private repo gets no arrow and no repo path."""
    private = p.get("private", False)
    tags, x = "", 24
    for t in p["tags"]:
        w = math.ceil(7.35 * len(t) + 18)
        tags += f'<rect x="{x}" y="132" width="{w}" height="22" rx="5" fill="none" stroke="#1E5B40"></rect><text x="{x + 11}" y="147">{esc(t)}</text>'
        x += w + 8
    arrow = "" if private else (
        f'<circle cx="396" cy="36" r="15" fill="#151D19" stroke="{GREEN}"></circle>'
        f'<path d="M390 42 L402 30 M395 30 H402 V37" fill="none" stroke="{GREEN}" stroke-width="1.6" stroke-linecap="round"></path>')
    path = ""
    if not private:
        full, short = f"{handle}/{p['repo']}", p["repo"]
        room = 412 - (x - 8) - 14
        pick = full if len(full) * MONO_ADV <= room else short if len(short) * MONO_ADV <= room else ""
        if pick:
            path = f'<text class="jb" x="412" y="147" font-size="10.5" fill="#858D88" text-anchor="end">{esc(pick)}</text>'
    lines = "".join(f'<text class="sg" x="24" y="{100 + 19 * i}" font-size="13.5" fill="#858D88">{esc(l)}</text>' for i, l in enumerate(p["lines"]))
    label = f'{p["title"]}. {" ".join(p["lines"])} {", ".join(p["tags"]).title()}.'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="436" height="168" viewBox="0 0 436 168" role="img" aria-label="{esc(label)}">'
            f'<rect x=".5" y=".5" width="435" height="167" rx="14" fill="#101715" stroke="#29332D"></rect>'
            f'<rect x="24" y="0" width="50" height="2" fill="{GREEN}"></rect>'
            f'<path d="M420 168 C 380 168 356 130 366 96" fill="none" stroke="{GOLD}" stroke-opacity=".25" stroke-width="2"></path>'
            f'<text class="jb" x="24" y="38" font-size="12" letter-spacing="2" fill="{GOLD}">{n:02d}</text>{arrow}'
            f'<text class="sg" x="24" y="76" font-size="24" font-weight="700" fill="#E8ECE7">{esc(p["title"])}</text>{lines}'
            f'<g class="jb" font-size="10.5" letter-spacing="1" fill="{GREEN}">{tags}</g>{path}</svg>')


def arsenal_svg(groups):
    """groups: [{label, accent: green|gold, items: [[abbr, name], ...]}]; 4 chips per line, 56px per line."""
    lines_per = [math.ceil(len(g["items"]) / 4) for g in groups]
    h = 56 * sum(lines_per) + 40
    labels, divs, chips, top = "", "", "", 26
    for gi, (g, nl) in enumerate(zip(groups, lines_per)):
        color = GOLD if g.get("accent") == "gold" else GREEN
        labels += f'<text x="28" y="{top + 24}">{esc(g["label"])}</text>'
        for i, (abbr, name) in enumerate(g["items"]):
            cx, cy = 240 + 150 * (i % 4), top + 56 * (i // 4)
            tx = 40 if len(abbr) <= 2 else 46
            chips += (f'<g transform="translate({cx},{cy})"><rect width="140" height="38" rx="8" fill="#151D19" stroke="#29332D"></rect>'
                      f'<text class="jb" x="12" y="24" font-size="12" font-weight="700" fill="{color}">{esc(abbr)}</text>'
                      f'<text x="{tx}" y="24">{esc(name)}</text></g>\n')
        top += 56 * nl
        if gi < len(groups) - 1:
            divs += f"M28 {top - 12} H852 "
    names = "; ".join(f'{g["label"].title()}: {", ".join(n for _, n in g["items"])}' for g in groups)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="{h}" viewBox="0 0 880 {h}" role="img" aria-label="{esc("Tech stack. " + names)}">\n'
            f'<rect x=".5" y=".5" width="879" height="{h - 1}" rx="14" fill="#101715" stroke="#29332D"></rect>\n'
            f'<g class="jb" font-size="11" letter-spacing="3" fill="{GREEN}">{labels}</g>\n'
            f'<g stroke="#29332D" stroke-opacity=".7"><path d="{divs.strip()}" fill="none"></path></g>\n'
            f'<g class="sg" font-size="13" fill="#E8ECE7">\n{chips}</g>\n</svg>')


# ---------------------------------------------------------------- 07 writing: article cards
def banner_svg(num, label, rune, accent_x):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="48" viewBox="0 0 880 48" role="img" aria-label="{num} {esc(label.title())}">'
            f'<text class="rn" x="0" y="32" font-size="24" fill="{GOLD}">{rune}</text>'
            f'<text class="jb" x="36" y="30" font-size="13" letter-spacing="4" fill="{GREEN}">{num} · {esc(label)}</text>'
            f'<rect x="{accent_x:g}" y="23" width="{850 - accent_x:g}" height="2" fill="url(#gBif)"></rect>'
            f'<path d="M868 24 l7 -8 l7 8 l-7 8 z" fill="none" stroke="{GOLD}" stroke-width="1.5"></path></svg>')


def wrap_text(text, width, measure, kind, size, weight=400):
    lines, cur = [], ""
    for word in text.split():
        t = f"{cur} {word}".strip()
        if cur and measure(kind, size, weight, t) > width:
            lines.append(cur); cur = word
        else:
            cur = t
    return lines + [cur] if cur else lines


def initials(name):
    p = name.split()
    return (p[0][0] + p[-1][0]).upper() if len(p) > 1 else p[0][:2].upper()


def article_row(n, a, measure, W=880):
    """One full-width row: title + claps on the left, then one column per voice (comment / clapped by).
    Only columns that exist are drawn, so nothing is padded with empty space. Content comes from config only."""
    voices = a["voices"]
    one = len(voices) == 1
    tcw = 330 if one else 250
    R = 26 if one else 22                      # avatar radius
    QS = 28 if one else 22                     # quote size
    lines = wrap_text(a["title"], tcw - 40, measure, "sg", 21, 700)
    left = f'<text class="jb" x="24" y="38" font-size="12" letter-spacing="2" fill="{GOLD}">W\u00b7{n:02d}</text>'
    left += "".join(f'<text class="sg" x="24" y="{84 + 26 * i}" font-size="21" font-weight="700" fill="#E8ECE7">{esc(l)}</text>' for i, l in enumerate(lines))
    ty = 84 + 26 * (len(lines) - 1) + 20
    if a.get("claps") is not None:
        label = f'{a["claps"]} CLAPS'
        pw = math.ceil(7.35 * len(label) + 18)
        left += (f'<g class="jb" font-size="10.5" letter-spacing="1" fill="{GREEN}"><rect x="24" y="{ty}" width="{pw}" height="22" rx="5" fill="none" stroke="#1E5B40"></rect>'
                 f'<text x="35" y="{ty + 15}">{label}</text></g>')
        ty += 22
    bottoms = [ty]
    x0 = 24 + tcw + 28
    weights = [1.45 if v["kind"] == "comment" else 1 for v in voices]
    total = W - 24 - x0 - 28 * (len(voices) - 1)
    widths = [total * w_ / sum(weights) for w_ in weights]
    body, defs = "", ""
    for j, v in enumerate(voices):
        vw = widths[j]
        vx = x0 + sum(widths[:j]) + 28 * j
        body += f'<path d="M{vx - 14:g} 24 V__H__" stroke="#29332D"></path>'
        p = v["person"]
        body += f'<text class="jb" x="{vx:g}" y="38" font-size="9" letter-spacing="2" fill="{GOLD}">{"COMMENT" if v["kind"] == "comment" else "CLAPPED BY"}</text>'
        y = 60
        if v["kind"] == "comment":
            ql = wrap_text("\u201c" + v["quote"] + "\u201d", vw, measure, "cg", QS, 500)
            for i, l in enumerate(ql):
                body += f'<text class="cg" x="{vx:g}" y="{y + QS + (QS + 4) * i}" font-size="{QS}" font-weight="500" fill="#E8ECE7">{esc(l)}</text>'
            y += QS + (QS + 4) * (len(ql) - 1) + 26
        else:
            y += 6
        ring = GOLD if v["kind"] == "clapped" else GREEN
        cx, cy = vx + R, y + R
        if p.get("avatar"):
            defs += f'<clipPath id="av{n}{j}"><circle cx="{cx:g}" cy="{cy:g}" r="{R}"></circle></clipPath>'
            body += (f'<image x="{cx - R:g}" y="{cy - R:g}" width="{2 * R}" height="{2 * R}" preserveAspectRatio="xMidYMid slice" clip-path="url(#av{n}{j})" href="data:image/jpeg;base64,{p["avatar"]}"></image>'
                     f'<circle cx="{cx:g}" cy="{cy:g}" r="{R}" fill="none" stroke="{ring}" stroke-width="1.5"></circle>')
        else:
            body += (f'<circle cx="{cx:g}" cy="{cy:g}" r="{R}" fill="#151D19" stroke="{ring}"></circle>'
                     f'<text class="jb" x="{cx:g}" y="{cy + 4:g}" font-size="12" font-weight="700" fill="{ring}" text-anchor="middle">{esc(initials(p["name"]))}</text>')
        body += f'<text class="sg" x="{vx + 2 * R + 14:g}" y="{y + R - 2}" font-size="{15 if one else 14.5}" font-weight="600" fill="#E8ECE7">{esc(p["name"])}</text>'
        ly = y + R + 17
        for st in p.get("stats", []):
            gold = st.startswith("*")
            for l in wrap_text(st.lstrip("*"), vw - 2 * R - 14, measure, "sg", 12):
                body += f'<text class="sg" x="{vx + 2 * R + 14:g}" y="{ly}" font-size="12" fill="{GOLD if gold else "#858D88"}">{esc(l)}</text>'
                ly += 16
        bottoms.append(max(y + 2 * R + 4, ly - 4))
    H = max(bottoms) + 26
    body = body.replace("V__H__", f"V{H - 24:g}")
    arrow = (f'<circle cx="{W - 40}" cy="36" r="15" fill="#151D19" stroke="{GREEN}"></circle>'
             f'<path d="M{W - 46} 42 L{W - 34} 30 M{W - 41} 30 H{W - 34} V37" fill="none" stroke="{GREEN}" stroke-width="1.6" stroke-linecap="round"></path>')
    spoken = " ".join((f'Comment from {v["person"]["name"]}: {v["quote"]}.' if v["kind"] == "comment" else f'Clapped by {v["person"]["name"]}.') +
                      " " + " ".join(t.lstrip("*") + "." for t in v["person"].get("stats", [])) for v in voices)
    label = f'{a["title"]}. ' + (f'{a["claps"]} claps. ' if a.get("claps") is not None else "") + spoken
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:g}" viewBox="0 0 {W} {H:g}" role="img" aria-label="{esc(label)}"><defs>{defs}</defs>'
            f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1:g}" rx="14" fill="#101715" stroke="#29332D"></rect>'
            f'<rect x="24" y="0" width="50" height="2" fill="{GREEN}"></rect>{left}{arrow}{body}</svg>'), H
