"""Merge E5 entries into buildings and write the E5/E6 lists (Markdown + JSON) for the hand-over."""
import json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = Path(sys.argv[1])
SHOT = 'E:/eva-map-buildings/client/screenshots/'
H = json.load(open(HERE / 'houses.json', encoding='utf8'))
foot = {}
for f in ('E:/eva-map-buildings/plans/e5-pilot/sites.json', 'E:/eva-map-buildings/plans/e5-rest/sites.json'):
    for s in json.load(open(f, encoding='utf8')):
        foot[s['id']] = s['bbox']
for h in H:
    h['foot'] = foot.get(h['id'], h['bbox'])

# union entries whose footprints overlap (same building)
parent = {h['id']: h['id'] for h in H}


def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


for i, a in enumerate(H):
    for b in H[i + 1:]:
        if a['cls'] != b['cls'] or a['cls'] in ('not-house',):
            continue
        A, B = a['foot'], b['foot']
        g = 1 if a['cls'] == 'half' else 3
        if A[0] <= B[2] + g and B[0] <= A[2] + g and A[1] <= B[3] + g and B[1] <= A[3] + g:
            parent[find(a['id'])] = find(b['id'])
groups = defaultdict(list)
for h in H:
    groups[find(h['id'])].append(h)
buildings = []
for n, (root, hs) in enumerate(sorted(groups.items(), key=lambda kv: (kv[1][0]['cls'], kv[1][0]['foot'][1], kv[1][0]['foot'][0]))):
    xs0 = min(h['foot'][0] for h in hs); zs0 = min(h['foot'][1] for h in hs)
    xs1 = max(h['foot'][2] for h in hs); zs1 = max(h['foot'][3] for h in hs)
    doors = [d for h in hs for d in h['doors']]
    shots = []
    for h in hs:
        for kind in ('door', 'air'):
            for pre in ('before-', 'after5-'):
                p = Path(SHOT + f"{pre}{h['id']}-{kind}.png")
                if p.exists():
                    shots.append(str(p).replace('\\', '/'))
    buildings.append(dict(entries=[h['id'] for h in hs], cls=hs[0]['cls'], area=hs[0]['area'], bbox=[xs0, zs0, xs1, zs1],
                          floor=min(h['floor'] for h in hs), roof=max((h['roof'] or 0) for h in hs), ground=max((h['ground'] or 0) for h in hs),
                          fill=sum(h['fill'] for h in hs), doors=doors, note=hs[0]['note'], pilot=any(h['pilot'] for h in hs),
                          mats=hs[0]['mats'], shots=shots[:6]))
for k, b in enumerate(buildings):
    b['id'] = f"B{k + 1:02d}"
json.dump(buildings, open(OUT / 'e5-buildings.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

FIX = {'half': '房内填土清空；房子四周挖出 2 格平台（露出原来的平石地坪），再按 1:1 坡度接回山坡，新坡面铺草；坡上的树整棵移走',
       'deep': '要挖 9 格以上深的坑，或者把整片山坡退回去；工作量和效果要先定（见下文"待定"）',
       'look': '先进游戏看一眼再定', 'not-house': '不修（误报，列出来备查）'}
CLS = {'half': '半埋', 'deep': '整栋埋进山体', 'look': '待目视', 'not-house': '不是房屋'}
lines = ['## E5 埋在地下的房子（建筑部分）', '']
cnt = defaultdict(int)
for b in buildings:
    cnt[b['cls']] += 1
lines.append('| 类别 | 栋数 | 处理 |')
lines.append('|---|---|---|')
for c in ('half', 'deep', 'look', 'not-house'):
    lines.append(f"| {CLS[c]} | {cnt[c]} | {FIX[c]} |")
lines.append('')
for c in ('half', 'deep', 'look', 'not-house'):
    part = [b for b in buildings if b['cls'] == c]
    by_area = defaultdict(list)
    for b in part:
        by_area[b['area']].append(b)
    lines.append(f"### {CLS[c]}（{len(part)} 栋）")
    lines.append('')
    for area, bs in by_area.items():
        lines.append(f"**{area}**（{len(bs)} 栋）")
        lines.append('')
        lines.append('| 编号 | 范围 x,z | 室内地面 y | 屋顶 y | 周围地面 y | 房内填土格 | 被埋门数 | 说明 | 副本 |')
        lines.append('|---|---|---|---|---|---|---|---|---|')
        for b in bs:
            x0, z0, x1, z1 = b['bbox']
            state = '已试修' if b['pilot'] else ''
            lines.append(f"| {b['id']} | {x0}..{x1}, {z0}..{z1} | {b['floor']} | {b['roof']} | {b['ground']:.0f} | {b['fill']} | {len(b['doors'])} | {b['note']} | {state} |")
        lines.append('')
(OUT / 'e5-list.md').write_text('\n'.join(lines), 'utf8')
print(dict(cnt))
