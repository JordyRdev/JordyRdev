#!/usr/bin/env python3
"""
Neofetch-style GitHub profile card generator for JordyRdev.

Renders assets/card-dark.svg and assets/card-light.svg (plus the link buttons)
from the CONFIG below, live "uptime", and GitHub stats.

  python scripts/profile.py            # render using cached stats (assets/stats.json)
  GH_TOKEN=xxx python scripts/profile.py --fetch   # fetch fresh stats, then render

The GitHub Action in .github/workflows/profile.yml runs this daily.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# --------------------------------------------------------------------------- #
#  CONFIG — edit freely                                                        #
# --------------------------------------------------------------------------- #
USER = "JordyRdev"
PROMPT = "jordy@rdev"
CAREER_START = dt.date(2011, 1, 1)  # used for "Uptime" — set to when you started in QA

INFO = [
    ("OS", "Windows, Linux, Docker"),
    ("Uptime", "{uptime}"),
    ("Host", "Freelance / Contract · Remote"),
    ("Kernel", "Senior QA & Data Quality Consultant"),
    ("IDE", "VS Code, Power BI Desktop"),
    None,
    ("Languages.Programming", "TypeScript, Python, SQL, JS"),
    ("Languages.Testing", "Playwright, CodeceptJS, Cypress"),
    ("Languages.Real", "Dutch, English"),
    None,
    ("Focus.QA", "LLM evals, API, performance, CI gates"),
    ("Focus.Data", "Power BI, Fabric, ADF, Synapse"),
    ("Certs", "PL-300, ISTQB Adv TA, CTFL, TMap"),
    None,
    "Contact",
    ("Email", "jordydev@proton.me"),
    ("GitHub", "JordyRdev"),
    ("Status", "Open to work · remote · relocation"),
    None,
    "GitHub Stats",
    "STATS",
]

BUTTONS = [
    ("projects", "PROJECTS", f"https://github.com/{USER}?tab=repositories"),
    ("email", "EMAIL", "mailto:jordydev@proton.me"),
]

WIDTH = 58          # characters in each info line
FONT_SIZE = 16
CHAR_W = 9.63       # approx. advance of a 16px monospace glyph
LINE_H = 20
ART_FONT = 11       # portrait uses a smaller font for more detail
ART_CHAR_W = 6.62
ART_LINE_H = 13.4

# density ramp used by the portrait (dark -> bright on a dark background).
# In light mode the ramp is reversed so the portrait isn't a photo-negative.
RAMP = " .'`^,:;-~=+*xjk%#&$@"

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657",
                 value="#a5d6ff", dots="#616e7f", add="#3fb950", dele="#f85149",
                 art="#c9d1d9", accent="#ffa657"),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800",
                  value="#0a3069", dots="#c2cfde", add="#1a7f37", dele="#cf222e",
                  art="#24292f", accent="#953800"),
}

# --------------------------------------------------------------------------- #
#  Stats                                                                       #
# --------------------------------------------------------------------------- #
STATS_FILE = ASSETS / "stats.json"
API = "https://api.github.com"


def _req(url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-card",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else None)


def gql(token, query, variables):
    _, res = _req(f"{API}/graphql", token, {"query": query, "variables": variables})
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    return res["data"]


def fetch_stats(token):
    d = gql(token, """query($login:String!){ user(login:$login){
        id followers{totalCount}
        repositoriesContributedTo(includeUserRepositories:false,
          contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY,PULL_REQUEST_REVIEW]){totalCount}
    }}""", {"login": USER})["user"]
    uid = d["id"]
    stats = {"followers": d["followers"]["totalCount"],
             "contributed": d["repositoriesContributedTo"]["totalCount"],
             "repos": 0, "stars": 0, "commits": 0, "additions": 0, "deletions": 0}

    repos, cursor = [], None
    while True:
        page = gql(token, """query($login:String!,$id:ID!,$after:String){ user(login:$login){
            repositories(ownerAffiliations:OWNER, first:50, after:$after){
              totalCount pageInfo{hasNextPage endCursor}
              nodes{ name isFork stargazerCount
                defaultBranchRef{ target{ ... on Commit { history(author:{id:$id}){totalCount} } } } }
        }}}""", {"login": USER, "id": uid, "after": cursor})["user"]["repositories"]
        stats["repos"] = page["totalCount"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    for r in repos:
        if not r["isFork"]:
            stats["stars"] += r["stargazerCount"]
        ref = r.get("defaultBranchRef")
        n = (ref or {}).get("target", {}).get("history", {}).get("totalCount", 0) if ref else 0
        stats["commits"] += n
        if n == 0:
            continue
        # lines of code: per-author weekly additions/deletions (202 = still computing)
        for _ in range(8):
            status, body = _req(f"{API}/repos/{USER}/{r['name']}/stats/contributors", token)
            if status == 200 and isinstance(body, list):
                for c in body:
                    if (c.get("author") or {}).get("login", "").lower() == USER.lower():
                        stats["additions"] += sum(w["a"] for w in c["weeks"])
                        stats["deletions"] += sum(w["d"] for w in c["weeks"])
                break
            time.sleep(4)
    stats["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return stats


def load_stats():
    if STATS_FILE.exists():
        return json.loads(STATS_FILE.read_text())
    return {"repos": 0, "contributed": 0, "stars": 0, "commits": 0,
            "followers": 0, "additions": 0, "deletions": 0}


# --------------------------------------------------------------------------- #
#  Rendering                                                                   #
# --------------------------------------------------------------------------- #
def uptime(start, today=None):
    today = today or dt.date.today()
    y, m, d = today.year - start.year, today.month - start.month, today.day - start.day
    if d < 0:
        m -= 1
        prev = (today.replace(day=1) - dt.timedelta(days=1))
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    pl = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{pl(y, 'year')}, {pl(m, 'month')}, {pl(d, 'day')}"


def seg(text, cls):
    return (text, cls)


def kv_line(key, value):
    """'. Key: ......... value' padded to WIDTH."""
    head = [seg(". ", "dots")]
    parts = key.split(".")
    for i, p in enumerate(parts):
        if i:
            head.append(seg(".", "text"))
        head.append(seg(p, "key"))
    head.append(seg(":", "text"))
    used = 2 + len(key) + 1
    fill = WIDTH - used - len(value) - 2
    return head + [seg(" " + "." * max(fill, 1) + " ", "dots"), seg(value, "value")]


def section_line(title):
    left = f"- {title} "
    return [seg(left, "text"), seg("—" * (WIDTH - len(left)), "text")]


def stat_pair(lk, lv, rk, rv, lwidth):
    """'. Repos: .... 12 {..} | Stars: ..... 5'"""
    out = [seg(". ", "dots"), seg(lk, "key"), seg(":", "text")]
    lfill = lwidth - (2 + len(lk) + 1) - len(lv) - 2
    out += [seg(" " + "." * max(lfill, 1) + " ", "dots")] + lv_segs(lv)
    out += [seg(" | ", "text"), seg(rk, "key"), seg(":", "text")]
    rfill = WIDTH - lwidth - 3 - len(rk) - 1 - len(rv) - 2
    out += [seg(" " + "." * max(rfill, 1) + " ", "dots"), seg(rv, "value")]
    return out


def lv_segs(lv):
    if "{" in lv:  # '12 {Contributed: 3}'
        num, rest = lv.split(" ", 1)
        inner = rest.strip("{}")
        k, v = inner.split(": ")
        return [seg(num, "value"), seg(" {", "text"), seg(k, "key"),
                seg(": ", "text"), seg(v, "value"), seg("}", "text")]
    return [seg(lv, "value")]


def stats_lines(s):
    f = lambda n: f"{n:,}"
    lw = 33
    lines = [
        stat_pair("Repos", f"{f(s['repos'])} {{Contributed: {f(s['contributed'])}}}",
                  "Stars", f(s["stars"]), lw),
        stat_pair("Commits", f(s["commits"]), "Followers", f(s["followers"]), lw),
    ]
    loc = s["additions"] - s["deletions"]
    add, dele = f"{f(s['additions'])}++", f"{f(s['deletions'])}--"
    key = "Lines of Code on GitHub"
    tail_len = len(f(loc)) + 3 + len(add) + 2 + len(dele) + 2
    fill = WIDTH - (2 + len(key) + 1) - tail_len - 2
    lines.append([seg(". ", "dots"), seg(key, "key"), seg(":", "text"),
                  seg(" " + "." * max(fill, 1) + " ", "dots"),
                  seg(f(loc), "value"), seg(" ( ", "text"), seg(add, "add"),
                  seg(", ", "text"), seg(dele, "dele"), seg(" )", "text")])
    return lines


def build_info(stats):
    up = uptime(CAREER_START)
    lines = [[seg(PROMPT, "accent"), seg(" " + "—" * (WIDTH - len(PROMPT) - 1), "text")]]
    for item in INFO:
        if item is None:
            lines.append([seg(".", "dots")])
        elif item == "STATS":
            lines += stats_lines(stats)
        elif isinstance(item, str):
            lines.append(section_line(item))
        else:
            k, v = item
            lines.append(kv_line(k, v.format(uptime=up)))
    return lines


def render_card(theme, stats):
    t = THEMES[theme]
    art = [a.rstrip() for a in (ASSETS / "ascii.txt").read_text().split("\n")]
    while art and not art[0]:
        art.pop(0)
    while art and not art[-1]:
        art.pop()
    if theme == "light":
        rev = {c: RAMP[len(RAMP) - i] for i, c in enumerate(RAMP) if i}
        art = ["".join(rev.get(c, c) for c in a) for a in art]
    info = build_info(stats)
    art_cols = max(len(a) for a in art)
    pad = 20
    info_x = pad + art_cols * ART_CHAR_W + 28
    info_h = (len(info) + 2) * LINE_H
    art_h = len(art) * ART_LINE_H
    w = int(info_x + WIDTH * CHAR_W + pad)
    h = int(pad * 2 + max(info_h, art_h))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" font-family="ConsolasFallback,Consolas,'
           f'\'DejaVu Sans Mono\',monospace" width="{w}px" height="{h}px" font-size="{FONT_SIZE}px">',
           "<style>",
           "@font-face{src:local('Consolas'),local('Consolas Bold');font-family:'ConsolasFallback';"
           "font-display:swap;-webkit-size-adjust:109%;size-adjust:109%;}",
           *[f".{c}{{fill:{t[c]};}}" for c in ("text", "key", "value", "dots", "add", "dele", "accent")],
           f".art{{fill:{t['art']};}}",
           ".cursor{animation:blink 1.1s steps(1) infinite;}",
           "@keyframes blink{50%{opacity:0;}}",
           "text,tspan{white-space:pre;}",
           "</style>",
           f'<rect width="{w}px" height="{h}px" fill="{t["bg"]}" rx="15"/>']
    art_top = pad + 10 + max(0, (h - 2 * pad - art_h) / 2)  # vertically centred
    out.append(f'<text x="{pad}" y="{art_top:.1f}" class="art" font-size="{ART_FONT}px">')
    for i, line in enumerate(art):
        out.append(f'<tspan x="{pad}" y="{art_top + i * ART_LINE_H:.1f}">{escape(line)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{info_x:.0f}" y="{pad + 10}" class="text">')
    for i, line in enumerate(info):
        spans = "".join(f'<tspan class="{c}">{escape(s)}</tspan>' for s, c in line)
        out.append(f'<tspan x="{info_x:.0f}" y="{pad + 10 + i * LINE_H}">{spans}</tspan>')
    y = pad + 10 + (len(info) + 1) * LINE_H
    out.append(f'<tspan x="{info_x:.0f}" y="{y}"><tspan class="accent">&gt;</tspan>'
               f' <tspan class="accent cursor">█</tspan></tspan>')
    out.append("</text></svg>")
    return "\n".join(out)


ICONS = {
    # 24x24 stroke icons
    "email": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 7l10 7 10-7"/>',
    "projects": '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
                '<path d="M9 13l2 2 4-4"/>',
}


def render_button(theme, icon, label):
    t = THEMES[theme]
    w, h = 470, 56
    text_w = len(label) * 10.8
    gx = (w - (28 + 14 + text_w)) / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'font-family="Consolas,\'DejaVu Sans Mono\',monospace">'
            f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="6" fill="{t["bg"]}" '
            f'stroke="{t["border"]}" stroke-width="2"/>'
            f'<rect x="1" y="{h - 4}" width="{w - 2}" height="3" fill="{t["accent"]}"/>'
            f'<g transform="translate({gx:.0f},{(h - 28) / 2 - 1:.0f}) scale(1.17)" fill="none" '
            f'stroke="{t["accent"]}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS[icon]}</g>'
            f'<text x="{gx + 42:.0f}" y="{h / 2 + 5:.0f}" font-size="18" letter-spacing="1" '
            f'fill="{t["text"]}">{label}</text></svg>')


def main():
    stats = load_stats()
    if "--fetch" in sys.argv:
        token = os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("GH_TOKEN not set")
        stats = fetch_stats(token)
        STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n")
        print("stats:", stats)
    for theme in THEMES:
        (ASSETS / f"card-{theme}.svg").write_text(render_card(theme, stats))
        for icon, label, _ in BUTTONS:
            (ASSETS / f"btn-{icon}-{theme}.svg").write_text(render_button(theme, icon, label))
    print("rendered", ", ".join(sorted(p.name for p in ASSETS.glob("*.svg"))))


if __name__ == "__main__":
    main()
