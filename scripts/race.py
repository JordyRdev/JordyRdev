"""'Contribution Grand Prix': a pseudo-3D, behind-the-car arcade racer driven by
the GitHub contribution calendar. Pure SVG + SMIL, so it animates in a README.

World model: everything on the ground is drawn once at reference depth z=1 and
scaled about the vanishing point by s = 1/z (cheap, arcade-style perspective).
The car's track distance D(t) (with acceleration and braking) drives every
object's depth z = d_obj - D(t).

Each day with contributions becomes a green block in one of three lanes; the
car steers into it, the score climbs, month billboards pass by, and a
checkered gate marks the finish with the yearly total.
"""
import datetime as dt
import math
from html import escape

H = 310
HORIZON = 122
CAM_H = 150                      # ground y (below horizon) at depth z=1
ROAD_W = 270                     # half road width at z=1
LANES = (-160, 0, 160)
Z_NEAR, Z_FAR = 0.78, 26.0
BAND_L = 1.6                     # depth of one stripe period
DAY_Z = 3.0                      # track distance per active day (empty days are squeezed)
START_T, RACE_T, END_T = 3.0, 24.0, 4.5
ACC_T, BRAKE_T = 1.6, 1.6
Z_SAMPLES = [26, 20, 15, 11, 8, 6, 4.6, 3.6, 2.8, 2.2, 1.8, 1.5, 1.25, 1.08, 0.95, 0.85, 0.78]

PALETTES = {
    "dark": dict(
        sky=["#0b0f2a", "#2a1550", "#7a2a6e", "#ff6b6b"], sun=["#ffd36e", "#ff4fa3"],
        mount="#1c1240", mount_edge="#ff4fd8", grass=["#0e1a14", "#122319"],
        road=["#262633", "#2e2e3d"], kerb=["#ff4f6d", "#e8e8f0"], dash="#e8e8f0",
        hud="#ffffff", hud_dim="#c9bce8", accent="#ffa657", post="#4b3a7a", lamp="#ffd36e",
        lv=["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"], red="#f85149", green="#3fb950",
        board="#1b1036", board_text="#ffd36e"),
    "light": dict(
        sky=["#3d8bd9", "#6fb6f2", "#a9dcff", "#e6f6ff"], sun=["#fff7c2", "#ffd23f"],
        mount="#7d9cc0", mount_edge="#ffffff", grass=["#5fae4a", "#6dbd57"],
        road=["#7e7e86", "#88888f"], kerb=["#d7263d", "#ffffff"], dash="#ffffff",
        hud="#ffffff", hud_dim="#eef6ff", accent="#ffd23f", post="#5b4a3a", lamp="#fff3a0",
        lv=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"], red="#d7263d", green="#1a7f37",
        board="#ffffff", board_text="#953800"),
}


def _f(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") if x else "0"


# --------------------------------------------------------------------------- #
#  Motion: track distance D(t) with acceleration and braking                   #
# --------------------------------------------------------------------------- #
class Motion:
    def __init__(self, track_len):
        self.t0 = START_T
        self.vmax = track_len / (RACE_T - ACC_T / 2)
        self.tf = START_T + RACE_T               # crosses the finish line
        self.df = track_len
        self.cycle = START_T + RACE_T + END_T

    def D(self, t):
        if t <= self.t0:
            return 0.0
        a = self.vmax / ACC_T
        if t <= self.t0 + ACC_T:
            return 0.5 * a * (t - self.t0) ** 2
        if t <= self.tf:
            return 0.5 * self.vmax * ACC_T + self.vmax * (t - self.t0 - ACC_T)
        u = min(t - self.tf, BRAKE_T)
        return self.df + self.vmax * u - 0.5 * (self.vmax / BRAKE_T) * u * u

    @property
    def dmax(self):
        return self.D(self.cycle)

    def inv(self, d):
        """Earliest t with D(t) >= d, or None if never reached in this cycle."""
        if d <= 0:
            return 0.0
        if d > self.dmax + 1e-9:
            return None
        lo, hi = self.t0, self.tf + BRAKE_T
        for _ in range(60):
            mid = (lo + hi) / 2
            if self.D(mid) < d:
                lo = mid
            else:
                hi = mid
        return hi


def _object_keyframes(m, d_obj):
    """(t, scale) keyframes for a static world object at track distance d_obj."""
    kf = [(0.0, 1 / max(min(d_obj, Z_FAR), 0.05))]
    for zs in Z_SAMPLES:
        if zs >= d_obj:
            continue
        t = m.inv(d_obj - zs)
        if t is None:
            break
        kf.append((t, 1 / zs))
    if m.dmax < d_obj - Z_NEAR:                  # still ahead at cycle end
        kf.append((m.cycle, 1 / min(d_obj - m.dmax, Z_FAR)))
    return kf


def _anim_scale(kf, cyc):
    kt, vals, last = [], [], -1.0
    for t, s in kf:
        k = 0.0 if not kt else max(t / cyc, last + 1e-4)
        if k > 1:
            break
        kt.append(k)
        vals.append(s)
        last = k
    if kt[-1] < 1:
        kt.append(1.0)
        vals.append(vals[-1])
    return (f'<animateTransform attributeName="transform" type="scale" dur="{cyc:.2f}s" '
            f'repeatCount="indefinite" keyTimes="{";".join(_f(k) for k in kt)}" '
            f'values="{";".join(f"{v:.4f}" for v in vals)}"/>')


def _visibility_anim(changes, cyc):
    kt, vals = ["0"], ["0"]
    for t, v in changes:
        if t <= 0:
            vals[0] = str(int(v))
            continue
        if t >= cyc:
            break
        kt.append(_f(t / cyc))
        vals.append(str(int(v)))
    return (f'<animate attributeName="opacity" dur="{cyc:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{";".join(kt)}" values="{";".join(vals)}"/>')


# --------------------------------------------------------------------------- #
#  Drawing helpers (reference depth z=1, origin at the vanishing point)        #
# --------------------------------------------------------------------------- #
def _band(c, k, width):
    y0, hgt = CAM_H, CAM_H * 0.09
    g = [f'<rect x="{-width * 4}" y="{y0}" width="{width * 8}" height="{hgt:.1f}" fill="{c["grass"][1]}"/>',
         f'<rect x="{-ROAD_W}" y="{y0}" width="{2 * ROAD_W}" height="{hgt:.1f}" fill="{c["road"][1]}"/>',
         f'<rect x="{-ROAD_W - 34}" y="{y0}" width="34" height="{hgt:.1f}" fill="{c["kerb"][0]}"/>',
         f'<rect x="{ROAD_W}" y="{y0}" width="34" height="{hgt:.1f}" fill="{c["kerb"][0]}"/>']
    for lx in (-80, 80):
        g.append(f'<rect x="{lx - 4}" y="{y0}" width="8" height="{hgt:.1f}" fill="{c["dash"]}"/>')
    if k % 2 == 0:                                # street lamps on every other band
        for sgn in (-1, 1):
            px = sgn * (ROAD_W + 90)
            arm_x = px - 45 if sgn > 0 else px
            lamp_x = px - 45 if sgn > 0 else px + 33
            g.append(f'<rect x="{px - 5}" y="{y0 - 170}" width="10" height="170" fill="{c["post"]}"/>')
            g.append(f'<rect x="{arm_x}" y="{y0 - 178}" width="45" height="8" fill="{c["post"]}"/>')
            g.append(f'<rect x="{lamp_x}" y="{y0 - 170}" width="12" height="7" fill="{c["lamp"]}"/>')
    return "".join(g)


def _block(color):
    w, h = 64, 56
    y = CAM_H - h
    return (f'<rect x="{-w / 2}" y="{y}" width="{w}" height="{h}" rx="6" fill="{color}"/>'
            f'<rect x="{-w / 2 + 6}" y="{y + 6}" width="{w - 12}" height="10" rx="3" fill="#ffffff" opacity="0.5"/>'
            f'<rect x="{-w / 2}" y="{CAM_H - 6}" width="{w}" height="6" fill="#000" opacity="0.25"/>')


def _billboard(c, text, side):
    x = side * (ROAD_W + 230)
    return (f'<rect x="{x - 6}" y="{CAM_H - 150}" width="12" height="150" fill="{c["post"]}"/>'
            f'<rect x="{x - 95}" y="{CAM_H - 250}" width="190" height="110" rx="6" fill="{c["board"]}" '
            f'stroke="{c["board_text"]}" stroke-width="6"/>'
            f'<text x="{x}" y="{CAM_H - 168}" font-size="64" font-weight="bold" text-anchor="middle" '
            f'fill="{c["board_text"]}">{escape(text)}</text>')


def _gate(c):
    g = [f'<rect x="{-ROAD_W - 60}" y="{CAM_H - 300}" width="24" height="300" fill="{c["post"]}"/>',
         f'<rect x="{ROAD_W + 36}" y="{CAM_H - 300}" width="24" height="300" fill="{c["post"]}"/>']
    sq = 30
    n = int((2 * ROAD_W + 120) / sq)
    for i in range(n):
        for j in range(2):
            col = "#ffffff" if (i + j) % 2 == 0 else "#111111"
            g.append(f'<rect x="{-ROAD_W - 60 + i * sq}" y="{CAM_H - 300 + j * sq}" width="{sq}" height="{sq}" fill="{col}"/>')
    return "".join(g)


def _car():
    """Rear view of a generic pixel sports car, centred on x=0, tyres on y=0."""
    r = [
        ("#111", -62, -16, 26, 16), ("#111", 36, -16, 26, 16),                 # tyres
        ("#b3121f", -66, -50, 132, 36), ("#d81b2c", -60, -64, 120, 18),        # body
        ("#7d0d17", -66, -18, 132, 6),                                          # diffuser
        ("#1d2433", -40, -82, 80, 20), ("#3a4a66", -34, -78, 68, 6),            # rear window
        ("#d81b2c", -46, -86, 92, 6),                                           # roof
        ("#ffcf3f", -62, -46, 28, 9), ("#ffcf3f", 34, -46, 28, 9),              # tail lights
        ("#ff5a3c", -62, -37, 28, 4), ("#ff5a3c", 34, -37, 28, 4),
        ("#f2f2f2", -20, -36, 40, 12),                                          # plate
        ("#555", -50, -14, 10, 5), ("#555", 40, -14, 10, 5),                   # exhausts
        ("#111", -72, -64, 144, 6),                                             # spoiler
        ("#111", -60, -70, 6, 8), ("#111", 54, -70, 6, 8),
    ]
    g = ['<g shape-rendering="crispEdges">',
         '<ellipse cx="0" cy="2" rx="78" ry="7" fill="#000" opacity="0.35"/>']
    g += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col}"/>' for col, x, y, w, h in r]
    g.append('<text x="0" y="-27" font-size="9" font-weight="bold" text-anchor="middle" fill="#111">JRDEV</text>')
    g.append("</g>")
    return "".join(g)


# --------------------------------------------------------------------------- #
#  Main renderer                                                               #
# --------------------------------------------------------------------------- #
def render_race(theme, stats, width, user):
    c = PALETTES[theme]
    cal = stats.get("calendar") or {}
    weeks = cal.get("weeks") or []
    total = cal.get("total", 0)
    start = dt.date.fromisoformat(cal["start"]) if cal.get("start") else None
    n_weeks = max(1, len(weeks))
    # one track position per day: active days get room, empty stretches fast-forward
    days_flat = []                       # (date_index, weekday, count, level)
    for w, wk in enumerate(weeks):
        for wd, cnt, lvl in wk:
            days_flat.append((w * 7 + wd, wd, cnt, lvl))
    n_active = sum(1 for d_ in days_flat if d_[2] > 0)
    n_empty = len(days_flat) - n_active
    empty_z = 1.0 if not n_active else max(0.12, min(1.0, 0.5 * DAY_Z * n_active / max(n_empty, 1)))
    pos, acc = {}, DAY_Z
    for idx, wd, cnt, lvl in days_flat:
        acc += DAY_Z if cnt > 0 else empty_z
        pos[idx] = acc
    track = acc + DAY_Z
    m = Motion(track)
    cyc = m.cycle
    vx = width / 2
    sh = 'stroke="#000" stroke-width="0.8" paint-order="stroke"'
    sh_sm = 'stroke="#000" stroke-width="0.35" stroke-opacity="0.6" paint-order="stroke"'

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" viewBox="0 0 {width} {H}" '
           f'font-family="Consolas,\'DejaVu Sans Mono\',monospace">',
           '<defs>',
           f'<linearGradient id="sky-{theme}" x1="0" y1="0" x2="0" y2="1">'
           + "".join(f'<stop offset="{i / 3:.2f}" stop-color="{col}"/>' for i, col in enumerate(c["sky"]))
           + '</linearGradient>',
           f'<linearGradient id="sun-{theme}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["sun"][0]}"/>'
           f'<stop offset="1" stop-color="{c["sun"][1]}"/></linearGradient>',
           f'<clipPath id="card-{theme}"><rect width="{width}" height="{H}" rx="15"/></clipPath>',
           f'<clipPath id="ground-{theme}"><rect y="{HORIZON}" width="{width}" height="{H - HORIZON}"/></clipPath>',
           '</defs>',
           f'<g clip-path="url(#card-{theme})">']

    # ---- sky, sun, mountains ------------------------------------------------------
    out.append(f'<rect width="{width}" height="{HORIZON + 1}" fill="url(#sky-{theme})"/>')
    sun_r = 62
    out.append(f'<circle cx="{vx}" cy="{HORIZON - 8}" r="{sun_r}" fill="url(#sun-{theme})"/>')
    if theme == "dark":
        for i in range(5):
            out.append(f'<rect x="{vx - sun_r}" y="{HORIZON - 34 + i * 7}" width="{2 * sun_r}" '
                       f'height="{2 + i * 0.8:.1f}" fill="{c["sky"][3]}"/>')
    ridge = [(0, HORIZON), (60, HORIZON - 22), (130, HORIZON - 10), (210, HORIZON - 38), (300, HORIZON - 14),
             (380, HORIZON - 28), (440, HORIZON - 8), (vx + 160, HORIZON - 12), (vx + 230, HORIZON - 34),
             (vx + 320, HORIZON - 16), (vx + 400, HORIZON - 30), (width - 40, HORIZON - 12), (width, HORIZON - 20),
             (width, HORIZON)]
    out.append(f'<polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in ridge)}" fill="{c["mount"]}"/>')
    out.append(f'<polyline points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in ridge[1:-1])}" fill="none" '
               f'stroke="{c["mount_edge"]}" stroke-width="1.5" opacity="0.6"/>')

    # ---- ground: static base + moving stripe bands -----------------------------------
    out.append(f'<g clip-path="url(#ground-{theme})">')
    out.append(f'<rect y="{HORIZON}" width="{width}" height="{H - HORIZON}" fill="{c["grass"][0]}"/>')
    k15 = 1.5
    out.append(f'<polygon points="{vx},{HORIZON} {vx - (ROAD_W + 34) * k15:.0f},{HORIZON + CAM_H * k15} '
               f'{vx + (ROAD_W + 34) * k15:.0f},{HORIZON + CAM_H * k15}" fill="{c["kerb"][1]}"/>')
    out.append(f'<polygon points="{vx},{HORIZON} {vx - ROAD_W * k15:.0f},{HORIZON + CAM_H * k15} '
               f'{vx + ROAD_W * k15:.0f},{HORIZON + CAM_H * k15}" fill="{c["road"][0]}"/>')

    K = int(math.ceil((Z_FAR - Z_NEAR) / BAND_L)) + 1
    loop = K * BAND_L
    zs_band = [z for z in Z_SAMPLES if z < Z_NEAR + loop]
    bands = []
    for k in range(K):
        z0 = Z_NEAR + k * BAND_L
        kf = [(0.0, 1 / z0)]
        p = 0
        while True:
            base = z0 + p * loop
            done = False
            for zs in zs_band:
                if p == 0 and zs >= z0:
                    continue
                t = m.inv(base - zs)
                if t is None:
                    done = True
                    break
                kf.append((t, 1 / zs))
            if done:
                break
            t_w = m.inv(base - Z_NEAR)
            kf.append((t_w + 1e-3, 1 / (Z_NEAR + loop)))   # wrap to the far end
            p += 1
        zend = Z_NEAR + ((z0 - Z_NEAR - m.dmax) % loop)
        kf.append((cyc, 1 / zend))
        bands.append((z0, _band(c, k, width), kf))
    for _, content, kf in reversed(bands):
        out.append(f'<g transform="translate({vx},{HORIZON})"><g>{content}{_anim_scale(kf, cyc)}</g></g>')
    out.append('</g>')

    # ---- world objects: month billboards, contribution blocks, finish gate ----------
    objs = []                       # (track distance, svg, hide-at-depth)
    if start:
        last = None
        for idx, *_ in days_flat:
            d = start + dt.timedelta(days=idx)
            if d.month != last:
                if last is not None:
                    side = 1 if len(objs) % 2 == 0 else -1
                    objs.append((pos[idx] + 0.4, _billboard(c, d.strftime("%b").upper(), side), 0.6))
                last = d.month

    collects = []                   # (t, count, lane_x)
    for idx, wd, cnt, lvl in days_flat:
        if cnt <= 0:
            continue
        lane = LANES[(idx * 5 + cnt) % 3]
        d_obj = pos[idx]
        t_hit = m.inv(d_obj - 1.0)
        if t_hit is None:
            continue
        collects.append((t_hit, cnt, lane))
        objs.append((d_obj, f'<g transform="translate({lane},0)">{_block(c["lv"][max(lvl, 1)])}</g>', 1.0))

    objs.append((track + 1.0, _gate(c), 0.6))

    for d_obj, content, hide_at in sorted(objs, key=lambda o: -o[0]):
        kf = _object_keyframes(m, d_obj)
        enter = m.inv(d_obj - Z_FAR) if d_obj > Z_FAR else 0.0
        leave = m.inv(d_obj - hide_at)
        changes = [(0, d_obj <= Z_FAR)]
        if enter:
            changes.append((enter, 1))
        if leave is not None:
            changes.append((leave, 0))
        out.append(f'<g transform="translate({vx},{HORIZON})"><g opacity="0">{_visibility_anim(changes, cyc)}'
                   f'<g>{content}{_anim_scale(kf, cyc)}</g></g></g>')

    # ---- player car: steers into each block's lane ----------------------------------
    steer = [(0.0, 0.0)]
    for t, _, lane in sorted(collects):
        t_start = max(steer[-1][0] + 0.05, t - 0.45)
        if t_start < t:
            steer.append((t_start, steer[-1][1]))
        steer.append((t, lane))
    steer += [(m.tf + 0.6, 0.0), (cyc, 0.0)]
    kt, vals, last = [], [], -1.0
    for t, x in steer:
        k = 0.0 if not kt else max(t / cyc, last + 1e-4)
        if k > 1:
            continue
        kt.append(k)
        vals.append(x)
        last = k
    if kt[-1] < 1:
        kt.append(1.0)
        vals.append(0.0)
    car_y = HORIZON + CAM_H + 22
    out.append(f'<g transform="translate({vx},{car_y})"><g>'
               f'<animateTransform attributeName="transform" type="translate" dur="{cyc:.2f}s" repeatCount="indefinite" '
               f'keyTimes="{";".join(_f(k) for k in kt)}" values="{";".join(f"{v:.0f} 0" for v in vals)}"/>'
               f'<g><animateTransform attributeName="transform" type="translate" dur="0.18s" repeatCount="indefinite" '
               f'calcMode="discrete" values="0 0;0 -1.5"/>{_car()}</g></g></g>')

    for t, n, lane in collects:   # "+N" popups
        k1, k2 = t / cyc, min(0.999, (t + 0.6) / cyc)
        x, y = vx + lane, car_y - 100
        out.append(f'<text x="{x:.0f}" y="{y}" font-size="20" font-weight="bold" text-anchor="middle" '
                   f'fill="{c["lv"][4]}" {sh} opacity="0">+{n}'
                   f'<animate attributeName="opacity" dur="{cyc:.2f}s" repeatCount="indefinite" '
                   f'keyTimes="0;{_f(k1)};{_f(k1 + 0.0001)};{_f(k2)};1" values="0;0;1;0;0"/>'
                   f'<animate attributeName="y" dur="{cyc:.2f}s" repeatCount="indefinite" '
                   f'keyTimes="0;{_f(k1)};{_f(k2)};1" values="{y};{y};{y - 30};{y - 30}"/></text>')

    # ---- HUD --------------------------------------------------------------------------
    out.append(f'<text x="22" y="30" font-size="16" font-weight="bold" fill="{c["accent"]}" {sh} '
               f'letter-spacing="2">1UP {escape(user.upper())}</text>')
    out.append(f'<text x="22" y="46" font-size="10" fill="{c["hud_dim"]}" {sh_sm} letter-spacing="1">'
               f'CONTRIBUTION GRAND PRIX · LAST 12 MONTHS</text>')

    timeline, acc = [(0.0, 0)], 0
    for t, n, _ in sorted(collects):
        acc += n
        timeline.append((t, acc))
    sx = width - 22 - 6 * 12
    out.append(f'<text x="{sx - 8}" y="30" font-size="16" font-weight="bold" fill="{c["hud_dim"]}" {sh} '
               f'text-anchor="end" letter-spacing="2">SCORE</text>')
    for place in range(6):
        div = 10 ** (5 - place)
        for digit in range(10):
            changes, prev = [], None
            for t, v in timeline:
                vis = (v // div) % 10 == digit
                if vis != prev:
                    changes.append((t, vis))
                    prev = vis
            if any(v for _, v in changes):
                out.append(f'<text x="{sx + place * 12}" y="30" font-size="16" font-weight="bold" fill="{c["hud"]}" '
                           f'{sh}>{digit}{_visibility_anim(changes, cyc)}</text>')
    out.append(f'<text x="{width - 22}" y="46" font-size="10" fill="{c["hud_dim"]}" {sh_sm} text-anchor="end" '
               f'letter-spacing="1">CONTRIBUTIONS COLLECTED</text>')

    # speedometer
    sp = [(0.0, "000")]
    sp += [(START_T + (i + 1) * ACC_T / 6, f"{v:03d}") for i, v in enumerate((62, 128, 187, 236, 271, 293))]
    sp += [(m.tf + (i + 1) * BRAKE_T / 5, f"{v:03d}") for i, v in enumerate((241, 168, 94, 31, 0))]
    for i, (t, val) in enumerate(sp):
        t_end = sp[i + 1][0] if i + 1 < len(sp) else cyc + 1
        out.append(f'<text x="{width - 66}" y="{H - 16}" font-size="24" font-weight="bold" font-style="italic" '
                   f'text-anchor="end" fill="{c["accent"]}" {sh} opacity="0">{val}'
                   f'{_visibility_anim([(t, 1), (t_end, 0)], cyc)}</text>')
    out.append(f'<text x="{width - 22}" y="{H - 16}" font-size="11" font-weight="bold" text-anchor="end" '
               f'fill="{c["hud"]}" {sh}>KM/H</text>')

    # course map with moving marker
    bx, bw, by = 22, 220, H - 22
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="4" fill="#000" opacity="0.45"/>')
    out.append(f'<text x="{bx}" y="{by - 8}" font-size="10" fill="{c["hud"]}" {sh_sm} letter-spacing="1">COURSE</text>')
    if start:
        end_d = start + dt.timedelta(days=max(len(days_flat) - 1, 0))
        out.append(f'<text x="{bx + bw}" y="{by - 8}" font-size="10" text-anchor="end" fill="{c["hud"]}" {sh_sm}>'
                   f'{start.strftime("%b %y").upper()} - {end_d.strftime("%b %y").upper()}</text>')
    # marker follows the calendar date the car is currently driving through
    n_days = max(len(days_flat) - 1, 1)
    mk = [(0.0, 0.0)]
    for idx, *_ in days_flat[::3] + days_flat[-1:]:
        t = m.inv(pos[idx])
        if t is not None and t > mk[-1][0] + 1e-3:
            mk.append((t, idx / n_days))
    mk.append((cyc, 1.0 if m.dmax >= max(pos.values() or [0]) else mk[-1][1]))
    kt, vals, last = [], [], -1.0
    for t, frac in mk:
        k = 0.0 if not kt else max(t / cyc, last + 1e-4)
        if k > 1:
            continue
        kt.append(k)
        vals.append(bx - 3 + bw * frac)
        last = k
    if kt[-1] < 1:
        kt.append(1.0)
        vals.append(vals[-1])
    out.append(f'<rect x="{bx - 3}" y="{by - 4}" width="6" height="12" fill="{c["accent"]}" stroke="#000">'
               f'<animate attributeName="x" dur="{cyc:.2f}s" repeatCount="indefinite" '
               f'keyTimes="{";".join(_f(k) for k in kt)}" values="{";".join(f"{v:.1f}" for v in vals)}"/></rect>')

    # start lights + GO!
    lx = vx - 33
    for i in range(3):
        on = 0.5 + i * 0.7
        out.append(f'<circle cx="{lx + i * 33}" cy="66" r="12" fill="#222" stroke="#000" stroke-width="2" opacity="0">'
                   + _visibility_anim([(0, 1), (START_T + 1.0, 0)], cyc) + '</circle>')
        out.append(f'<circle cx="{lx + i * 33}" cy="66" r="9" fill="{c["red"]}" opacity="0">'
                   + _visibility_anim([(on, 1), (START_T - 0.3, 0)], cyc) + '</circle>')
        out.append(f'<circle cx="{lx + i * 33}" cy="66" r="9" fill="{c["green"]}" opacity="0">'
                   + _visibility_anim([(START_T - 0.3, 1), (START_T + 1.0, 0)], cyc) + '</circle>')
    out.append(f'<text x="{vx}" y="106" font-size="28" font-weight="bold" font-style="italic" text-anchor="middle" '
               f'fill="{c["accent"]}" {sh} opacity="0">GO!'
               + _visibility_anim([(START_T - 0.3, 1), (START_T + 1.0, 0)], cyc) + '</text>')

    # finish banner + yearly total
    blink = [(m.tf + i * 0.45, i % 2 == 0) for i in range(int(END_T / 0.45))]
    out.append(f'<text x="{vx}" y="76" font-size="32" font-weight="bold" font-style="italic" text-anchor="middle" '
               f'fill="{c["accent"]}" {sh} letter-spacing="3" opacity="0">FINISH!{_visibility_anim(blink, cyc)}</text>')
    out.append(f'<text x="{vx}" y="98" font-size="13" font-weight="bold" text-anchor="middle" fill="{c["hud"]}" '
               f'{sh} letter-spacing="1" opacity="0">{total:,} CONTRIBUTIONS IN THE LAST YEAR'
               + _visibility_anim([(m.tf, 1)], cyc) + '</text>')

    out.append("</g></svg>")
    return "\n".join(out)
