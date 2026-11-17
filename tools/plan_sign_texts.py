"""Plan text edits for street signs and NERV signs and boards by the rules in sign_rules.py.

Reads the current text straight from the world (so "before" is exact) and writes an edit list for
write_block_texts.py.

    plan_sign_texts.py --world W --at x,y,z [x,y,z ...] --out EDITS.json     (chosen signs)
    plan_sign_texts.py --world W --signs signs.json --kinds sign --areas core odawara --out EDITS.json

Street signs (vanilla): Japanese only. Generator lines ("入口 / 出口", "人员通行", block numbers) go; a house or office
entrance gets a house or building name picked from its position. Front and back get the same text.
NERV room plates (Japanese / CATEGORY / NERV): the Chinese name goes on the empty fourth line.
NERV wayfinding boards: title = Japanese floor or guide name, second line = Chinese and English, each destination row
= arrow + Japanese + Chinese + English, one name per place. The arrows themselves are kept as they are; they get
redone from the rebuilt floor graph in a later batch.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from write_deep_cells import REGION, read_chunk, block_at
from write_block_texts import current
import sign_rules as R

NUMBER = re.compile(r'^[0-9]{1,3}-[0-9]{1,3}$')
PYRAMID = (-90, 150, -1100, -294, 207, 447)        # x0 x1 y0 y1 z0 z1, with the levels under the pyramid


def pick(options, x, z):
    return options[int(hashlib.md5(f'{x},{z}'.encode()).hexdigest(), 16) % len(options)]


def in_nerv(x, y, z):
    return PYRAMID[0] <= x <= PYRAMID[1] and PYRAMID[2] <= y <= PYRAMID[3] and PYRAMID[4] <= z <= PYRAMID[5]


def street_sign(lines, x, z):
    out = _street_sign(lines, x, z)
    # a single name sits on the second line, near the middle of the board (owner's choice)
    if out[0] and not any(out[1:]):
        out = ['', out[0], '', '']
    return out


def _street_sign(lines, x, z):
    lines = [' / '.join(p for p in l.split(' / ') if not re.match(R.DROP_PATTERN, p)) for l in lines]
    kept = [l for l in lines if l and l not in R.DROP_LINES and not NUMBER.match(l)]
    head = lines[0] if lines else ''
    if head == '办公楼入口':
        return [pick(R.OFFICE_JA, x, z), '', '', '']
    if head == '住宅入口' or (not kept and head):
        return [pick(R.APARTMENT_JA, x, z), '', '', '']
    out = [R.to_ja(l) for l in kept]
    for i, l in enumerate(out):
        if l in ('住居', '民宿'):        # a bare use label: give the house a name like its neighbours
            out[i] = pick(R.APARTMENT_JA if l == '住居' else R.MINSHUKU_JA, x, z)
            continue
        m = re.match(R.GENERIC_USE, l)
        if m:
            out[i] = pick(R.APARTMENT_JA if m.group(1) == '住居' else R.USE_NAMES[m.group(1)], x, z)
    return (fit_lines(out) + [''] * 4)[:4]


def fit_lines(lines):
    """A line wider than a sign is split at ' / ' (else at its first space) when the sign has free lines for it."""
    out = []
    for i, l in enumerate(lines):
        if R.text_width(l) > R.SIGN_WIDTH:
            parts = l.split(' / ') if ' / ' in l else [] if any(c.isascii() and c.isalpha() for c in l) else l.split(' ', 1)
            if len(parts) > 1 and len(out) + len(parts) + len(lines) - i - 1 <= 4:
                out.extend(p.strip() for p in parts)
                continue
        out.append(l)
    return out[:4]


def multi(names):
    """'日本語|中文|English': the board renderer draws the Japanese part and the rest in small type under it."""
    return '|'.join(names)


def nerv_line(line, board=False):
    """'↑ 东侧主电梯' -> '↑ A号エレベーター|A号电梯|Lift A' on boards, '↑ A号エレベーター  A号电梯  Lift A' on signs;
    unknown names get Japanese characters only."""
    m = re.match(r'^([←→↑↓●│]\s*)?(.*)$', line)
    arrow, name = (m.group(1) or ''), m.group(2).strip()
    names = R.place(name)
    if names:
        return f'{arrow}{multi(names)}' if board else f'{arrow}{names[0]}  {names[1]}  {names[2]}'
    # a trailing arrow ("本层直梯 →") stays at the end
    tail = ''
    if name[-1:] in '←→' and name[:-1].strip() in R.BOARD_PHRASES:
        name, tail = name[:-1].strip(), ' ' + name[-1]
    if board and name in R.BOARD_PHRASES:
        ja, *rest = R.BOARD_PHRASES[name]
        return f'{arrow}{ja}{tail}|' + '|'.join(rest)
    return f'{arrow}{R.to_ja(name)}' if name else line


def nerv_plate(lines):
    """Room plate (Japanese / CATEGORY / NERV): the Chinese name goes on the free fourth line.
    Guide signs (arrows or Chinese phrases) are rewritten line by line from the phrase table."""
    lines = (list(lines) + [''] * 4)[:4]
    if tuple(lines) in R.NERV_GUIDE_SIGNS:
        return R.NERV_GUIDE_SIGNS[tuple(lines)]
    names = R.place(lines[0])
    if names:
        return [names[0], names[2].upper(), 'NERV', names[1]]
    if lines[2] == 'NERV' and not lines[3]:
        ja = R.to_ja(lines[0])
        zh = R.ja_to_zh(lines[0]) if ja == lines[0] else lines[0]
        return [ja, lines[1], 'NERV', zh]
    return [R.NERV_PHRASES.get(l, nerv_line(l) if l[:1] in '←→↑↓' else l) for l in lines]


def board(cur, compact):
    """compact: a hanging nerv_direction_panel, which shows Station as its only heading (Route is not drawn)."""
    station, route = cur['Station'], cur['Route']
    rows = [cur.get(k, '') for k in ('Row0', 'Row1', 'Row2')]
    if '全线站序' in route or any(r.startswith('│') or '本站' in r for r in rows):
        return {}                       # station line diagrams follow the station names (S-4), not the floor rules
    floor = R.FLOORS.get(station) or R.BOARD_HEADS.get(station)
    guide = R.GUIDE_TITLE.get(route) or (station in R.BOARD_HEADS)
    after = {}
    if floor and guide:
        if compact:
            after['Station'] = multi(floor)
        else:
            # large boards draw Route on top and Station under it: the heading's small line takes the Station slot
            after['Route'] = multi(floor)
            after['Station'] = ''
    for k in ('Row0', 'Row1', 'Row2'):
        if cur.get(k):
            after[k] = nerv_line(cur[k], board=True)
    return {k: v for k, v in after.items() if v != cur.get(k)}



# --- S-4: station boards, line diagrams and boarding signs --------------------------------------------------------
ROW = re.compile(r'^([←→↑↓●│]\s*)?(.*)$')
STATION_HEADS = {'R1 · 站内导向': 'R1 駅構内案内', 'S1 · 站内导向': 'S1 駅構内案内', '通行指引': '案内',
                 '到达／换乘指引': '到着・乗換案内', '本层通行指引': 'このフロアの案内'}


def station_row(row):
    m = ROW.match(row)
    arrow, text = (m.group(1) or ''), m.group(2).strip()
    if not text or '每分钟一班' in text:
        return row
    t = re.match(r'^换乘 (\S+)$', text)
    if t:
        return f'{arrow}乗換 {t.group(1)}|换乘 {t.group(1)}|Transfer {t.group(1)}'
    if text in R.STATION_PHRASES:
        ja, *rest = R.STATION_PHRASES[text]
        return f'{arrow}{ja}|' + '|'.join(rest)
    names = R.station(text) or R.place(text)
    if names:
        return f'{arrow}{multi(names)}'
    r = re.match(r'^(\w+) · (.+)$', text)
    if r and r.group(2) in R.ROUTES:
        ja, zh, en = R.ROUTES[r.group(2)]
        return f'{arrow}{r.group(1)} {ja}|{zh}|{en}'
    return row


def map_row(row):
    """A line-diagram entry: stops in Japanese (the diagram shows one language), footers as "日本語|中文"."""
    if row.startswith(('│', '●')):
        names = R.station(row[1:].replace('本站', '').strip())
        if not names:
            return row
        return f'{row[0]} {names[0]}' + ('  本站' if '本站' in row else '')
    if row in R.MAP_FOOTERS:
        return R.MAP_FOOTERS[row]
    m = re.match(r'^行车方向 (\S)\s+下一站 (.+)$', row)
    if m and R.station(m.group(2)):
        names = R.station(m.group(2))
        return f'進行方向 {m.group(1)}  次は {names[0]}|行车方向 {m.group(1)}  下一站 {names[1]}'
    m = re.match(r'^换乘 (\S+) · 按站内导向$', row)
    if m:
        return f'乗換 {m.group(1)} · 駅構内の案内で|换乘 {m.group(1)} · 按站内导向'
    return row


def is_station_board(cur, maps):
    return (maps is not None or any(t in cur['Route'] for t in ('站内导向', '全线站序', '站前导览', '到达'))
            or R.station(cur['Station']) is not None or R.station(cur['Route']) is not None
            or cur['Station'] in R.STATION_PHRASES)


def station_board(cur, compact, maps):
    after = {}
    st, rt = R.station(cur['Station']), R.station(cur['Route'])
    head = R.STATION_PHRASES.get(cur['Station'])
    if maps is not None:
        if st:
            after['Station'] = multi(st)
        new = [map_row(r) for r in maps]
        if new != maps:
            after['MapRows'] = new
        rows = {k: map_row(cur[k]) for k in ('Row0', 'Row1', 'Row2') if cur[k]}
    else:
        if compact:
            if st or head:
                after['Station'] = multi(st or head)
            # compact panels do not draw Route; it still follows the names
            if cur['Route'] in STATION_HEADS:
                after['Route'] = STATION_HEADS[cur['Route']]
            elif rt:
                after['Route'] = rt[0]
        elif rt:
            # the station's name heads the board; its Chinese and English take the second line
            after['Route'], after['Station'] = rt[0], f'{rt[1]} · {rt[2]}'
        else:
            if st or head:
                after['Station'] = multi(st or head)
            if cur['Route'] in STATION_HEADS:
                after['Route'] = STATION_HEADS[cur['Route']]
            elif cur['Route'] in R.STATION_PHRASES:
                after['Route'] = R.STATION_PHRASES[cur['Route']][0]     # Japanese only: Station holds the second line
        rows = {k: station_row(cur[k]) for k in ('Row0', 'Row1', 'Row2') if cur[k]}
    after.update(rows)
    return {k: v for k, v in after.items() if v != cur.get(k)}


def boarding_sign(lines):
    """GeoFront U-line boarding signs ("NERV 总部 / U1  每分钟一班 / 乘车 → / 北京时间"): no time zone line."""
    names = R.station(lines[0])
    if lines[2] == '乘车 →' and lines[3] == '北京时间' and names:
        ja, second = names[0], names[1] if names[1] != names[0] else names[2]
        if R.text_width(ja) > R.SIGN_WIDTH:          # 研究シミュレーション区: the last character moves down
            ja, second = ja[:-1], f'{ja[-1]} · {second}'
        return [ja, second, lines[1], 'のりば →']
    return None

def fix_arrow(text, old, new):
    """Swap the first `old` arrow in the Japanese part of a line (leading "↑ …" or trailing "… →")."""
    head, sep, rest = text.partition('|')
    i = head.find(old)
    return text if i < 0 else head[:i] + new + head[i + 1:] + sep + rest


def load_arrows(path):
    """plan_nerv_arrows.py output -> {(pos, side, row): (old, new)} for the rows whose arrow changes."""
    out = {}
    if path:
        for r in json.loads(Path(path).read_text('utf8')):
            if r['status'] == 'changed' and r['old_arrow'] and r['new_arrow']:
                out[tuple(r['pos']), r['side'], r['row']] = (r['old_arrow'], r['new_arrow'])
    return out


def plan(world, positions, nerv_extra=frozenset(), arrows=None):
    arrows = arrows or {}
    """nerv_extra: positions outside the pyramid box that still take the NERV rules (GeoFront)."""
    edits = []
    cache = {}
    for (x, y, z) in positions:
        rx, rz = x >> 9, z >> 9
        if (rx, rz) not in cache:
            cache[rx, rz] = (Path(world) / REGION / f'r.{rx}.{rz}.mca').read_bytes()
        root = read_chunk(cache[rx, rz], x >> 4, z >> 4)[3]
        ent = next((e for e in root.get('block_entities', []) if (int(e['x']), int(e['y']), int(e['z'])) == (x, y, z)), None)
        if ent is None:
            continue
        if str(ent['id']).endswith('sign'):
            cur = current(ent, 'sign')
            lines = cur['front']
            nerv = in_nerv(x, y, z) or (x, y, z) in nerv_extra
            boarding = boarding_sign(lines)
            new = boarding or (nerv_plate(lines) if nerv else street_sign(lines, x, z))
            # the back follows the front where it carried the same text, else it is converted on its own (table only,
            # so other sessions' prop texts outside the tables stay as they are); a blank back stays blank
            after = {}
            if new != lines:
                after['front'] = new
            if cur['back'] == lines:
                if new != lines:
                    after['back'] = new
            elif any(cur['back']):
                back = boarding_sign(cur['back']) or (nerv_plate(cur['back']) if nerv else street_sign(cur['back'], x, z))
                if not any(back):
                    back = new          # the back held only a generator label: it shows the plate's name instead
                if back != cur['back']:
                    after['back'] = back
            for side in ('front', 'back'):
                fixes = {row: v for (p, sd, row), v in arrows.items() if p == (x, y, z) and sd == side}
                if fixes:
                    text = list(after.get(side, cur[side]))
                    for row, (old, new_arrow) in fixes.items():
                        text[row] = fix_arrow(text[row], old, new_arrow)
                    if text != cur[side]:
                        after[side] = text
            if after:
                edits.append(dict(pos=[x, y, z], type='sign', before=cur, after=after,
                                  batch='S-4' if boarding else 'P' if nerv else 'S'))
        elif str(ent['id']) == 'projectseele:station_departure_board' and int(ent.get('Wayfinding', 0)):
            cur = current(ent, 'board')
            compact = 'nerv_direction_panel' in block_at(root, x, y, z)
            maps = cur.get('MapRows')
            station = is_station_board(cur, maps)
            if station:
                after = station_board(cur, compact, maps)
            else:
                after = board(cur, compact) if in_nerv(x, y, z) or (x, y, z) in nerv_extra else {}
            if not station and (in_nerv(x, y, z) or (x, y, z) in nerv_extra) and cur.get('RearRowsR47'):
                rear = [nerv_line(r, board=True) for r in cur['RearRowsR47']]
                if rear != cur['RearRowsR47']:
                    after['RearRowsR47'] = rear
            for (p, sd, row), (old, new_arrow) in arrows.items():
                if p != (x, y, z):
                    continue
                if sd == 'front' and row < 3:
                    k = f'Row{row}'
                    fixed = fix_arrow(after.get(k, cur[k]), old, new_arrow)
                    if fixed != cur[k]:
                        after[k] = fixed
                elif sd == 'rear' and cur.get('RearRowsR47') and row < len(cur['RearRowsR47']):
                    rear = list(after.get('RearRowsR47', cur['RearRowsR47']))
                    rear[row] = fix_arrow(rear[row], old, new_arrow)
                    if rear != cur['RearRowsR47']:
                        after['RearRowsR47'] = rear
            if after:
                edits.append(dict(pos=[x, y, z], type='board', before={k: cur[k] for k in after}, after=after,
                                  batch='S-4' if station else 'P'))
    return edits


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--at', action='append', default=[], help='x,y,z (repeat; write --at=-1,2,3 for negative x)')
    p.add_argument('--signs', type=Path)
    p.add_argument('--kinds', nargs='*', default=['sign', 'wayfinding'])
    p.add_argument('--areas', nargs='*')
    p.add_argument('--arrows', type=Path, help='plan_nerv_arrows.py output: rows whose arrow changes')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    positions = [tuple(map(int, s.split(','))) for s in a.at]
    nerv_extra = set()
    if a.signs:
        for s in json.loads(a.signs.read_text('utf8')):
            if s['kind'] in a.kinds and (not a.areas or s['area'] in a.areas) and not s['empty']:
                positions.append((s['x'], s['y'], s['z']))
                if s['area'] in ('pyramid', 'geofront'):
                    nerv_extra.add((s['x'], s['y'], s['z']))
    edits = plan(a.world, positions, nerv_extra, load_arrows(a.arrows))
    a.out.write_text(json.dumps(edits, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps(dict(positions=len(positions), edits=len(edits))))


if __name__ == '__main__':
    main()
