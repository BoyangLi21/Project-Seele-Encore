"""Plan new wall signs (batch P-2) at the NERV lift landings and corridor junctions that have no wayfinding board.

Reads a stopped world copy only. Takes the candidates from plan_nerv_arrows.py (p-landings.json), rebuilds the same
walking graph, and for each candidate looks for an air cell at eye height (one above the walkway's feet cell) in front
of a full solid, non-glass block, facing the walkway and the candidate point. Arrows are computed exactly like the
boards: a reader stands in front of the sign face (plan_nerv_arrows.reader/first_leg/arrow).

Text: lift landings get the Japanese floor name, then up to three "arrow + destination" lines; junctions get up to four
lines, destinations whose arrows differ first. Every line fits 90 px by sign_rules.text_width.

    . E:/eva-terrain/env.sh; PYTHONIOENCODING=utf-8 $PY tools/plan_nerv_new_signs.py --world E:/eva-terrain/world14 \
        --landings E:/eva-signs/p-landings.json --pending "E:/eva-map-*" --out E:/eva-signs

Writes p2-rows.json ([x, y, z, before, after] for write_deep_cells --rows), p2-signs.json ({pos, front, back, color,
glow} for --signs), p2-skipped.json and p2-placed.json (texts, reader, arrows, camera for a shot).
"""
import argparse
import glob
import json
import math
import re
import time
from pathlib import Path

import numpy as np

import plan_nerv_arrows as A
import sign_rules as R

SIGN = 'minecraft:dark_oak_wall_sign[facing={},waterlogged=false]'
RESTRICTED_FLOORS = ('终极教条层', 'SEELE 会议室', '总指挥会客厅')
NEAR_WORDS = ('door', 'button', 'sign', 'lever', 'interlock', 'station_departure_board', 'nerv_direction_panel',
              'pressure_plate', 'apg_', 'psd_', 'access_reader')
NOT_A_WALL = ('glass', 'barrier', 'leaves', 'beacon', 'ice', 'lantern', 'froglight', 'light', 'shroomlight', 'glowstone')

# Japanese floor names: plan_nerv_arrows.floor_label() -> sign_rules.FLOORS / BOARD_HEADS key, or a proposal
FLOOR_KEY = {'B1 交通接驳层': 'B1 · 交通接驳层', '1F 总部门厅': '1F · 总部门厅', '2F 勤务联络层': '2F · 勤务联络层',
             '3F 科研联络层': '3F · 科研联络层', '4F 作战指挥层': '4F · 作战指挥层', '5F 指挥室上层': '5F · 指挥室上层',
             '6F 上部办公层': '6F · 上部办公层', '7F 上部观察层': '7F · 上部观察层', '机库登机层': '机库登机层',
             'LCL 同步实验层': 'NERV · LCL 同步实验层'}
PROPOSED = {'主指挥台': '発令所 主指揮台', '指挥后方勤务层': '発令所後方 勤務階', '指挥室观察廊': '発令所 観測回廊',
            '总指挥联络厅': '司令連絡ホール', '湖畔电梯接驳层': '湖畔EV連絡フロア', '发射区检修廊': '射出区 点検通路',
            '机库上层观察廊': 'ケイジ上層 観測回廊', '原机库站接驳层': '旧ケイジ駅連絡階', '总部车站层': '本部駅フロア'}

# lift landings whose height label would pick the wrong floor name (the lake lift's top sits at the LCL level's height)
LANDING_TITLE = {'GeoFront 地面 · 总部湖畔': 'ジオフロント 湖畔'}

DESTS = ['第一発令所', '本部駅', 'A号エレベーター', 'B号エレベーター', 'EVA ケイジ', 'エレベーター']
SHORT = {'A号エレベーター': 'A号EV', 'B号エレベーター': 'B号EV', 'EVA ケイジ': 'ケイジ', '第一発令所': '発令所'}


def floor_ja(label):
    key = FLOOR_KEY.get(label)
    if key:
        return (R.FLOORS.get(key) or R.BOARD_HEADS.get(key))[0], False
    if label in PROPOSED:
        return PROPOSED[label], True
    return None, False


def fit(line, dest=None):
    if R.text_width(line) <= R.SIGN_WIDTH:
        return line
    if dest and dest in SHORT:
        short = line.replace(dest, SHORT[dest])
        if R.text_width(short) <= R.SIGN_WIDTH:
            return short
    return None


def pending_cells(patterns):
    """Every [x, y, z, ...] row below y -300 in the pending rows*.json lists (map writers' queues)."""
    cells = set()
    files = []
    row = re.compile(r'\[\s*(-?\d+)\s*,\s*(-\d+)\s*,\s*(-?\d+)\s*,\s*"')
    for pat in patterns:
        files += glob.glob(str(Path(pat) / '**' / 'rows*.json'), recursive=True)
    for f in files:
        text = Path(f).read_text('utf8', errors='replace')
        for m in row.finditer(text):
            y = int(m.group(2))
            if y < -300:
                cells.add((int(m.group(1)), y, int(m.group(3))))
    return cells, len(files)


def aisle(K, p):
    """Storage aisle: short partition walls alternating with 2-3 wide gaps along one axis through p."""
    for ax in ((1, 0), (0, 1)):
        line = [A.lookup(K, np.array([A.key_of(p[0] + ax[0] * s, p[1], p[2] + ax[1] * s)]))[0] >= 0
                for s in range(-10, 11)]
        walls, run, gaps = 0, 0, []
        for v in line:
            if v:
                run += 1
            else:
                if run:
                    gaps.append(run)
                run = 0
                walls += 1
        if run:
            gaps.append(run)
        inner = gaps[1:-1]
        if len(inner) >= 3 and all(g <= 3 for g in inner):
            return True
    return False


class Blocks:
    def __init__(self, world):
        self.w = world
        self.cache = {}

    def at(self, x, y, z):
        k = (x >> 4, z >> 4)
        if k not in self.cache:
            buf = self.w.region(x >> 9, z >> 9)
            root = A.read_chunk(buf, k[0], k[1])[3]
            self.cache[k] = {int(s['Y']): A.decode(s['block_states']) for s in root['sections'] if 'block_states' in s}
        sec = self.cache[k].get(y >> 4)
        if sec is None:
            return 'minecraft:air'
        ids, pal = sec
        return pal[ids[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]]


def full_wall(state, shapes):
    name = state.split('[')[0]
    if any(w in name for w in NOT_A_WALL):
        return False
    return shapes.get(A.norm_state(state)) in ([[0.0, 0.0, 0.0, 1.0, 1.0, 1.0]], [[0, 0, 0, 1, 1, 1]])


def spots(G, B, shapes, pending, cand, radius=6):
    """Valid sign cells near the candidate: (score, sign cell, facing, wall cell, reason-if-invalid counts)."""
    c, K = G['c'], G['K']
    px, py, pz = cand
    found, why = [], {}
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            for dy in (0, -1, 1):
                feet = (px + dx, py + dy, pz + dz)
                if A.lookup(K, np.array([A.key_of(*feet)]))[0] < 0:
                    continue
                s = (feet[0], feet[1] + 1, feet[2])
                for face, (nx, nz) in A.NORMAL.items():
                    wall = (s[0] - nx, s[1], s[2] - nz)
                    wstate = B.at(*wall)
                    if not full_wall(wstate, shapes):
                        continue
                    # face toward the candidate (or along the wall when it is the candidate's own cell)
                    if (px - s[0]) * nx + (pz - s[2]) * nz < 0:
                        why['faces away'] = why.get('faces away', 0) + 1
                        continue
                    if B.at(*s) != 'minecraft:air':
                        why['sign cell not air'] = why.get('sign cell not air', 0) + 1
                        continue
                    if s in pending:
                        why['in a pending list'] = why.get('in a pending list', 0) + 1
                        continue
                    near = [B.at(s[0] + a, s[1] + b, s[2] + d) for a in (-1, 0, 1) for b in (-1, 0, 1) for d in (-1, 0, 1)
                            if (a, b, d) != (0, 0, 0)]
                    if any(any(wd in n.split('[')[0] for wd in NEAR_WORDS) for n in near):
                        why['next to a door/button/sign'] = why.get('next to a door/button/sign', 0) + 1
                        continue
                    d = math.hypot(s[0] - px, s[2] - pz) + abs(dy) * 2
                    found.append((d, s, face, wall, wstate))
    found.sort()
    return found, why


def plan_text(G, w, s, face, kind, floor_label, lift_id=None, landing=None):
    """Lines and per-destination arrows for a sign at s facing face (reader stands in front of it)."""
    c, K = G['c'], G['K']
    ri, clear = A.reader(w, c, K, G['size'], s, face, .5)
    if ri is None:
        return None, None, 'no reading cell in front of the sign'
    arrows = {}
    for dest in DESTS:
        p = G['preds'].get(dest)
        if p is None or not np.isfinite(G['dists'][dest][ri]):
            continue
        end, leg, special = A.first_leg(c, K, p, ri)
        if leg < 3 and not (special and end == ri):
            pts, _, _ = A.trace(c, p, ri, 6.0)
            end = pts[-1]
        ar = A.arrow(c[end] - c[ri], face)
        if ar == '●':
            continue
        arrows[dest] = dict(arrow=ar, path=A.path_length(c, p, ri), leg=[c[ri].tolist(), c[end].tolist()])
    lines, used = [], set()
    if kind == 'lift_landing':
        title, proposed = (LANDING_TITLE[landing], True) if landing in LANDING_TITLE else floor_ja(floor_label)
        if title is None or R.text_width(title) > R.SIGN_WIDTH:
            return None, arrows, f'no Japanese floor name for {floor_label}'
        lines.append(title)
        order = ['第一発令所', '本部駅', 'EVA ケイジ', 'A号エレベーター', 'B号エレベーター']
        if c[ri, 1] > -900:
            order.remove('EVA ケイジ')
        own = {A.LIFT_A: 'A号エレベーター', A.LIFT_B: 'B号エレベーター'}.get(lift_id)
        if own:                               # the lift you are standing at needs no arrow
            order.remove(own)
        room = 3
    else:
        order = ['第一発令所', '本部駅', 'A号エレベーター', 'B号エレベーター', 'エレベーター', 'EVA ケイジ']
        room = 4
    chosen = []
    for d in order:                       # first pass: one destination per distinct arrow
        if d in arrows and arrows[d]['arrow'] not in used and len(chosen) < room:
            chosen.append(d); used.add(arrows[d]['arrow'])
    for d in order:                       # then the rest by priority
        if d in arrows and d not in chosen and len(chosen) < room:
            if d == 'エレベーター' and any(x in chosen for x in ('A号エレベーター', 'B号エレベーター')):
                continue
            chosen.append(d)
    chosen.sort(key=order.index)
    for d in chosen:
        line = fit(f"{arrows[d]['arrow']} {d}", d)
        if line:
            lines.append(line)
    if len(lines) < (2 if kind == 'lift_landing' else 1):
        return None, arrows, 'no destination arrow from this spot'
    return (lines + [''] * 4)[:4], dict(arrows=arrows, reader=c[ri].tolist(), reader_clear=clear), None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--landings', type=Path, required=True)
    ap.add_argument('--pending', nargs='+', default=['E:/eva-map-buildings', 'E:/eva-map-edges', 'E:/eva-map-roads'])
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    t0 = time.time()
    pats = [p for pat in a.pending for p in glob.glob(pat)] or a.pending
    pending, nfiles = pending_cells(pats)
    print(f'pending deep cells {len(pending)} from {nfiles} row files, {time.time() - t0:.0f}s', flush=True)
    G = A.build(a.world, t0)
    w = G['w']
    B = Blocks(w)
    shapes = w.shapes
    cands = json.loads(a.landings.read_text('utf8'))
    import gzip
    g = json.loads(gzip.decompress((a.world / 'nerv_routes_r24.json.gz').read_bytes()))
    restricted = {tuple(r['actual']) for r in g['named_lift_landings'] if r['restricted']}
    rows, signs, placed, skipped = [], [], [], []
    taken = []
    for cd in cands:
        cell = tuple(cd['cell'])
        label = cd['floor']
        base = dict(type=cd['type'], cell=list(cell), floor=label, label=cd.get('label'))
        if label in RESTRICTED_FLOORS or cd.get('label') in RESTRICTED_FLOORS or cell[1] <= -1100 or \
                (cd['type'] == 'lift_landing' and tuple(cd['cell']) in restricted):
            skipped.append({**base, 'reason': 'restricted level (Terminal Dogma / SEELE / commander)'}); continue
        if cd['type'] == 'corridor_branch' and aisle(G['K'], cell):
            skipped.append({**base, 'reason': 'storage aisle'}); continue
        found, why = spots(G, B, shapes, pending, cell)
        found = [f for f in found if all(math.dist(f[1], t) > 4 for t in taken)]
        if not found:
            skipped.append({**base, 'reason': 'no solid non-glass wall with an air cell at eye height within 6 blocks',
                            'rejected': why}); continue
        done = False
        last = None
        for d, s, face, wall, wstate in found[:12]:
            lines, info, err = plan_text(G, w, s, face, cd['type'], label, cd.get('lift_id'), cd.get('label'))
            if err:
                last = err
                continue
            twin = next((q for q in placed if q['front'] == lines and math.dist(q['sign'], s) <= 10), None)
            if twin:
                last = f"same text as the sign at {twin['sign']} {round(math.dist(twin['sign'], s), 1)} blocks away"
                break
            before = B.at(*s)
            rows.append([s[0], s[1], s[2], before, SIGN.format(face)])
            signs.append(dict(pos=list(s), front=lines, back=['', '', '', ''], color='black', glow=False))
            rd = info['reader']
            # camera: player feet on the reading cell, looking at the sign's centre (Minecraft yaw: south 0, west 90)
            dx, dz = s[0] + .5 - (rd[0] + .5), s[2] + .5 - (rd[2] + .5)
            dy = s[1] + .5 - (rd[1] + 1.62)
            cam = dict(pos=[rd[0] + .5, rd[1], rd[2] + .5], yaw=round(-math.degrees(math.atan2(dx, dz)), 1),
                       pitch=round(-math.degrees(math.atan2(dy, math.hypot(dx, dz))), 1))
            placed.append({**base, 'sign': list(s), 'facing': face, 'wall': list(wall), 'wall_block': wstate, 'front': lines,
                           'reader': rd, 'reader_clear': info['reader_clear'],
                           'arrows': {k: v['arrow'] for k, v in info['arrows'].items()},
                           'title_proposed': cd['type'] == 'lift_landing' and (label in PROPOSED or cd.get('label') in LANDING_TITLE),
                           'distance_from_candidate': round(d, 1), 'camera': cam,
                           'one_direction': len({l.split(' ')[0] for l in lines if l[:1] in '←→↑↓'}) == 1})
            taken.append(s)
            done = True
            break
        if not done:
            skipped.append({**base, 'reason': last or 'no usable spot'})
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'p2-rows.json').write_text(json.dumps(rows, ensure_ascii=False), 'utf8')
    (a.out / 'p2-signs.json').write_text(json.dumps(signs, ensure_ascii=False, indent=1), 'utf8')
    (a.out / 'p2-placed.json').write_text(json.dumps(placed, ensure_ascii=False, indent=1), 'utf8')
    (a.out / 'p2-skipped.json').write_text(json.dumps(skipped, ensure_ascii=False, indent=1), 'utf8')
    from collections import Counter
    print(json.dumps(dict(candidates=len(cands), placed=len(placed), one_direction=sum(p['one_direction'] for p in placed),
                          skipped=Counter(s['reason'].split(' at [')[0] for s in skipped),
                          seconds=round(time.time() - t0)), ensure_ascii=False))


if __name__ == '__main__':
    main()
