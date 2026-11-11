#!/usr/bin/env python3
"""Thumbnails for the 'Featured work' grid in the README.

Dashboard repos get a crop of their real screenshot; test repos get a
terminal-style tile with the results their READMEs report.

  python scripts/featured.py path/to/screenshot.png name   # crop a screenshot
  python scripts/featured.py --tiles                        # (re)draw the SVG tiles
"""
import sys
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "featured"
W, H = 800, 450
C = dict(bg="#161b22", bar="#0d1117", text="#c9d1d9", dim="#616e7f", key="#ffa657",
         value="#a5d6ff", ok="#3fb950", line="#30363d")


def crop(src, name):
    from PIL import Image, ImageDraw
    im = Image.open(src).convert("RGB")
    w, h = im.size
    target = W / H
    if w / h > target:                       # too wide -> trim sides
        nw = int(h * target)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                                    # too tall -> keep the top
        im = im.crop((0, 0, w, int(w / target)))
    im = im.resize((W, H), Image.LANCZOS)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), 14, fill=255)
    im.putalpha(mask)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{name}.png", optimize=True)


def tile(name, title, lines):
    """lines: list of segment lists [(text, colour_key), ...]"""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="Consolas,\'DejaVu Sans Mono\',monospace" xml:space="preserve">',
           f'<rect width="{W}" height="{H}" rx="14" fill="{C["bg"]}"/>',
           f'<path d="M0,14 a14,14 0 0 1 14,-14 h{W - 28} a14,14 0 0 1 14,14 v24 h-{W} z" fill="{C["bar"]}"/>',
           '<circle cx="22" cy="19" r="6" fill="#ff5f56"/><circle cx="42" cy="19" r="6" fill="#ffbd2e"/>'
           '<circle cx="62" cy="19" r="6" fill="#27c93f"/>',
           f'<text x="{W / 2}" y="24" font-size="14" fill="{C["dim"]}" text-anchor="middle">{escape(title)}</text>']
    y = 80
    for segs in lines:
        if segs == "---":
            out.append(f'<rect x="28" y="{y - 12}" width="{W - 56}" height="1" fill="{C["line"]}"/>')
            y += 14
            continue
        spans = "".join(f'<tspan fill="{C[k]}">{escape(t)}</tspan>' for t, k in segs)
        out.append(f'<text x="28" y="{y}" font-size="21">{spans}</text>')
        y += 32
    out.append("</svg>")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text("\n".join(out))


def tiles():
    tile("llm-eval-security-tests", "llm-eval-security-tests · nightly eval on main", [
        [("$ ", "key"), ("eval --live", "text"), ("   # golden questions, reference SQL", "dim")],
        [("  accuracy ............ ", "dim"), ("40/40", "value"), ("   ✓", "ok")],
        [("  made-up content ..... ", "dim"), ("0%", "value"), ("      ✓", "ok")],
        [("  faithfulness ........ ", "dim"), ("1.00", "value"), ("    ✓", "ok"), ("  target 0.85", "dim")],
        "---",
        [("OWASP Top 10 for LLM Applications 2026", "key")],
        [("  ✓ ", "ok"), ("prompt injection, direct and indirect", "text")],
        [("  ✓ ", "ok"), ("data leakage between roles", "text")],
        [("  ✓ ", "ok"), ("system prompt leakage · excessive agency", "text")],
        [("  ✓ ", "ok"), ("unbounded consumption · output handling", "text")],
        [("replay suite: ", "dim"), ("19 files · 256 tests", "value"), (" on every PR", "dim")],
    ])
    tile("playwright-typescript-portfolio", "playwright-typescript-portfolio · CI", [
        [("$ ", "key"), ("npx playwright test", "text")],
        [("Running ", "dim"), ("45", "value"), (" tests across ", "dim"), ("4", "value"), (" browsers", "dim")],
        "---",
        [("  ✓ ", "ok"), ("UI   ", "key"), ("login · cart · checkout journeys", "text")],
        [("  ✓ ", "ok"), ("API  ", "key"), ("auth · booking CRUD", "text")],
        [("  ✓ ", "ok"), ("Zod  ", "key"), ("contract checks on every payload", "text")],
        [("  ✓ ", "ok"), ("Page Objects + fixtures (shopper, bookingClient)", "text")],
        [("  ✓ ", "ok"), ("Chromium · Firefox · WebKit · Pixel 5", "text")],
        "---",
        [("  45 passed", "ok"), ("   HTML report published to GitHub Pages", "dim")],
    ])
    tile("powerbi-dashboard-playwright", "powerbi-dashboard-playwright · test analytics", [
        [("Playwright", "value"), (" ─▶ ", "dim"), ("GitHub Actions", "value"), (" ─▶ ", "dim"),
         ("star schema", "value"), (" ─▶ ", "dim"), ("Power BI", "value")],
        [("7 projects · 4 shards     every run on main is stored", "dim")],
        "---",
        [("The report answers:", "key")],
        [("  ? ", "key"), ("Which tests are flaky?", "text")],
        [("  ? ", "key"), ("Is the suite getting slower?", "text")],
        [("  ? ", "key"), ("Is this release better than the last?", "text")],
        "---",
        [("  ✓ ", "ok"), ("5 report pages in Quality.pbip", "text")],
        [("  ✓ ", "ok"), ("live Allure report on GitHub Pages", "text")],
    ])


if __name__ == "__main__":
    if sys.argv[1:] == ["--tiles"]:
        tiles()
    else:
        crop(sys.argv[1], sys.argv[2])
