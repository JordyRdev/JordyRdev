"""Retro arcade 'Grand Prix' animation of the GitHub contribution graph.

The calendar becomes a serpentine race track: start lights count down, a pixel
car races through every week collecting contributions (cells flash and empty),
an arcade score counter climbs, a rival chases, and a checkered finish shows
the yearly total. Pure SVG + SMIL, so it animates inside a README <img>.
"""
import datetime as dt
import math
from html import escape

CELL, GAP = 13, 3
P = CELL + GAP
START_T, RACE_T, END_T = 2.6, 17.0, 4.0           # seconds: lights, race, finish
RIVAL_LAG = 0.07                                   # rival finishes 7% later

PALETTES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", dim="#616e7f", accent="#ffa657",
                 lv=["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"],
                 road="#30363d", car="#f85149", rival="#58a6ff", wheel="#0d1117",
                 cockpit="#0d1117", flash="#ffffff", red="#f85149", green="#3fb950"),
    "light": dict(bg="#f6f8fa", text="#24292f", dim="#8c959f", accent="#953800",
                  lv=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
                  road="#d0d7de", car="#cf222e", rival="#0969da", wheel="#24292f",
                  cockpit="#24292f", flash="#ffd33d", red="#cf222e", green="#1a7f37"),
}


def _f(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") if x else "0"


def _car(color, wheel, cockpit):
    """Top-down pixel race car pointing along +x, centred on (0,0)."""
    return (f'<g shape-rendering="crispEdges">'
            f'<rect x="-8" y="-6" width="4" height="2" fill="{wheel}"/>'
            f'<rect x="3" y="-6" width="4" height="2" fill="{wheel}"/>'
            f'<rect x="-8" y="4" width="4" height="2" fill="{wheel}"/>'
            f'<rect x="3" y="4" width="4" height="2" fill="{wheel}"/>'
            f'<rect x="-10" y="-5" width="2" height="10" fill="{color}"/>'
            f'<rect x="-8" y="-4" width="16" height="8" fill="{color}"/>'
            f'<rect x="8" y="-2" width="3" height="4" fill="{color}"/>'
            f'<rect x="-1" y="-2" width="5" height="4" fill="{cockpit}"/>'
            f'<rect x="-8" y="-1" width="6" height="2" fill="#ffffff" opacity="0.85"/>'
            f'</g>')


def _visibility_anim(intervals, cycle, attr="opacity"):
    """Discrete on/off animation from a list of (t, visible) change points."""
    kt, vals = ["0"], ["0"]
    for t, v in intervals:
        if t <= 0:
            vals[0] = str(int(v))
            continue
        kt.append(_f(t / cycle))
        vals.append(str(int(v)))
    return (f'<animate attributeName="{attr}" dur="{cycle:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{";".join(kt)}" values="{";".join(vals)}"/>')


def render_race(theme, stats, width, user):
    c = PALETTES[theme]
    cal = stats.get("calendar") or {}
    weeks = cal.get("weeks") or []           # [[ [weekday, count, level], ... ], ...]
    total = cal.get("total", 0)
    start_date = cal.get("start")
    cols = max(1, len(weeks))

    grid_w = cols * P - GAP
    gx0 = (width - grid_w) / 2
    hud_h, month_h = 46, 16
    gy0 = hud_h + month_h + 6
    h = int(gy0 + 7 * P + 18)
    cycle = START_T + RACE_T + END_T

    # ---- serpentine track through cell centres --------------------------------
    cx = lambda col: gx0 + col * P + CELL / 2
    cy = lambda row: gy0 + row * P + CELL / 2
    left_turn, right_turn = gx0 - 12, gx0 + grid_w + 12
    start_x, finish_x = gx0 - 34, gx0 + grid_w + 30
    pts = [(start_x, cy(0))]
    row_start = {}                           # row -> (cum distance at x, x, direction)
    dist = 0.0

    def add(p):
        nonlocal dist
        x0, y0 = pts[-1]
        dist += math.hypot(p[0] - x0, p[1] - y0)
        pts.append(p)

    for r in range(7):
        going_right = r % 2 == 0
        row_start[r] = (dist, pts[-1][0], 1 if going_right else -1)
        end_x = (finish_x if r == 6 else right_turn) if going_right else left_turn
        add((end_x, cy(r)))
        if r < 6:                            # U-turn (semicircle) into the next row
            rad = P / 2
            ccx, ccy = end_x, cy(r) + rad
            for k in range(1, 13):
                a = -math.pi / 2 + k * math.pi / 12
                add((ccx + (rad * math.cos(a) if going_right else -rad * math.cos(a)), ccy + rad * math.sin(a)))
    total_len = dist
    path_d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    def t_at(d, lag=0.0):
        return START_T + RACE_T * (1 + lag) * d / total_len

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" viewBox="0 0 {width} {h}" '
           f'font-family="Consolas,\'DejaVu Sans Mono\',monospace">',
           f'<rect width="{width}" height="{h}" rx="15" fill="{c["bg"]}"/>']

    # ---- road markings: faint dashed centre line along the track ----------------
    out.append(f'<path d="{path_d}" fill="none" stroke="{c["road"]}" stroke-width="1.5" '
               f'stroke-dasharray="6 6" opacity="0.9"/>')
    # start (grid) line + checkered finish
    out.append(f'<rect x="{start_x + 14:.1f}" y="{cy(0) - 8:.1f}" width="3" height="16" fill="{c["dim"]}"/>')
    fx = finish_x - 16
    for i in range(6):
        for j in range(2):
            col = "#ffffff" if (i + j) % 2 == 0 else "#000000"
            out.append(f'<rect x="{fx + j * 4:.1f}" y="{cy(6) - 12 + i * 4:.1f}" width="4" height="4" '
                       f'fill="{col}" shape-rendering="crispEdges"/>')

    # ---- month labels -------------------------------------------------------------
    if start_date:
        d0 = dt.date.fromisoformat(start_date)
        last = None
        for w in range(cols):
            m = (d0 + dt.timedelta(days=7 * w)).month
            if m != last and w < cols - 2:
                out.append(f'<text x="{gx0 + w * P:.1f}" y="{gy0 - 7}" font-size="10" fill="{c["dim"]}">'
                           f'{(d0 + dt.timedelta(days=7 * w)).strftime("%b")}</text>')
                last = m

    # ---- cells + collection timeline ----------------------------------------------
    events = []                              # (t, count)
    pops = []
    for w, days in enumerate(weeks):
        for wd, count, level in days:
            x, y = gx0 + w * P, gy0 + wd * P
            fill = c["lv"][level]
            if count <= 0:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/>')
                continue
            d_row, x_row, sign = row_start[wd]
            d = d_row + abs(cx(w) - x_row)
            t = t_at(d)
            events.append((t, count))
            k1, k2 = t / cycle, (t + 0.12) / cycle
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}">'
                       f'<animate attributeName="fill" dur="{cycle:.2f}s" repeatCount="indefinite" '
                       f'calcMode="discrete" keyTimes="0;{_f(k1)};{_f(k2)}" '
                       f'values="{fill};{c["flash"]};{c["lv"][0]}"/></rect>')
            if level >= 3:
                pops.append((x + CELL / 2, y, t, count))

    # arcade "+N" popups for the big days
    for x, y, t, n in pops:
        k1, k2 = t / cycle, min(0.999, (t + 0.7) / cycle)
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="10" font-weight="bold" text-anchor="middle" '
                   f'fill="{c["accent"]}" opacity="0">+{n}'
                   f'<animate attributeName="opacity" dur="{cycle:.2f}s" repeatCount="indefinite" '
                   f'keyTimes="0;{_f(k1)};{_f(k1 + 0.0001)};{_f(k2)};1" values="0;0;1;0;0"/>'
                   f'<animate attributeName="y" dur="{cycle:.2f}s" repeatCount="indefinite" '
                   f'keyTimes="0;{_f(k1)};{_f(k2)};1" values="{y:.1f};{y:.1f};{y - 14:.1f};{y - 14:.1f}"/>'
                   f'</text>')

    # ---- cars -------------------------------------------------------------------------
    s, e = START_T / cycle, (START_T + RACE_T) / cycle
    er = min(0.995, (START_T + RACE_T * (1 + RIVAL_LAG)) / cycle)
    for color, end, dy in ((c["rival"], er, 0), (c["car"], e, 0)):
        out.append(f'<g>{_car(color, c["wheel"], c["cockpit"])}'
                   f'<animateMotion dur="{cycle:.2f}s" repeatCount="indefinite" rotate="auto" '
                   f'path="{path_d}" keyPoints="0;0;1;1" keyTimes="0;{_f(s)};{_f(end)};1" calcMode="linear"/>'
                   f'</g>')

    # ---- HUD --------------------------------------------------------------------------
    out.append(f'<text x="22" y="28" font-size="15" font-weight="bold" fill="{c["accent"]}" '
               f'letter-spacing="2">1UP {escape(user.upper())}</text>')
    out.append(f'<text x="22" y="42" font-size="10" fill="{c["dim"]}" letter-spacing="1">'
               f'CONTRIBUTION GRAND PRIX · LAST 12 MONTHS</text>')

    # score counter: 6 arcade digits, each a stack of 0-9 toggled discretely
    events.sort()
    timeline, acc = [(0.0, 0)], 0
    for t, n in events:
        acc += n
        timeline.append((t, acc))
    sx = width - 22 - 6 * 12
    out.append(f'<text x="{sx - 8}" y="28" font-size="15" font-weight="bold" fill="{c["dim"]}" '
               f'text-anchor="end" letter-spacing="2">SCORE</text>')
    for place in range(6):
        div = 10 ** (5 - place)
        x = sx + place * 12
        for digit in range(10):
            changes, prev = [], None
            for t, v in timeline:
                vis = (v // div) % 10 == digit
                if vis != prev:
                    changes.append((t, vis))
                    prev = vis
            if not any(v for _, v in changes):
                continue
            out.append(f'<text x="{x}" y="28" font-size="15" font-weight="bold" fill="{c["text"]}">{digit}'
                       f'{_visibility_anim(changes, cycle)}</text>')
    out.append(f'<text x="{width - 22}" y="42" font-size="10" fill="{c["dim"]}" text-anchor="end" '
               f'letter-spacing="1">CONTRIBUTIONS COLLECTED</text>')

    # start lights: red, red, red ... GREEN / GO!
    lx = width / 2 - 36
    for i in range(3):
        on = 0.3 + i * 0.6
        out.append(f'<circle cx="{lx + i * 22}" cy="22" r="7" fill="{c["road"]}">'
                   + _visibility_anim([(0, 1), (START_T + 1.2, 0)], cycle) + '</circle>')
        out.append(f'<circle cx="{lx + i * 22}" cy="22" r="7" fill="{c["red"]}" opacity="0">'
                   + _visibility_anim([(on, 1), (START_T - 0.4, 0)], cycle) + '</circle>')
        out.append(f'<circle cx="{lx + i * 22}" cy="22" r="7" fill="{c["green"]}" opacity="0">'
                   + _visibility_anim([(START_T - 0.4, 1), (START_T + 1.2, 0)], cycle) + '</circle>')
    out.append(f'<text x="{lx + 66}" y="27" font-size="14" font-weight="bold" fill="{c["green"]}" opacity="0">GO!'
               + _visibility_anim([(START_T - 0.4, 1), (START_T + 1.2, 0)], cycle) + '</text>')
    out.append(f'<text x="{width / 2}" y="27" font-size="14" font-weight="bold" fill="{c["dim"]}" '
               f'text-anchor="middle" letter-spacing="3" opacity="0">LAP 1/1'
               + _visibility_anim([(START_T + 1.2, 1), (START_T + RACE_T, 0)], cycle) + '</text>')

    # finish banner (blinking) with the yearly total
    blink = [(START_T + RACE_T + i * 0.5, i % 2 == 0) for i in range(int(END_T / 0.5))]
    out.append(f'<text x="{width / 2}" y="27" font-size="16" font-weight="bold" fill="{c["accent"]}" '
               f'text-anchor="middle" letter-spacing="3" opacity="0">FINISH!'
               + _visibility_anim(blink, cycle) + '</text>')
    out.append(f'<text x="{width / 2}" y="41" font-size="10" fill="{c["text"]}" text-anchor="middle" '
               f'letter-spacing="1" opacity="0">{total:,} CONTRIBUTIONS IN THE LAST YEAR'
               + _visibility_anim([(START_T + RACE_T, 1)], cycle) + '</text>')

    out.append("</svg>")
    return "\n".join(out)
