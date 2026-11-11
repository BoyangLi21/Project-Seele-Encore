import sys, json
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, '.')
from mca import REGION, World
from blocks import short, is_open, is_natural
w = World(REGION)
F = np.load('fill_room.npy'); W = np.load('walls_room.npy')
for spec in sys.argv[1:]:
    x0,y0,z0,x1,y1,z1 = map(int, spec.split(','))
    m = (F[:,0]>=x0)&(F[:,0]<=x1)&(F[:,2]>=z0)&(F[:,2]<=z1)&(F[:,1]>=y0)&(F[:,1]<=y1)
    f = F[m]; mw = (W[:,0]>=x0)&(W[:,0]<=x1)&(W[:,2]>=z0)&(W[:,2]<=z1)&(W[:,1]>=y0)&(W[:,1]<=y1); ww=W[mw]
    fm = Counter(short(w.get(x,y,z)) for x,y,z,_ in f.tolist())
    roof = Counter()
    for x,y,z,_ in f.tolist()[:400]:
        k=1
        while is_natural(w.get(x,y+k,z)): k+=1
        roof[short(w.get(x,y+k,z))]+=1
    wm = Counter(short(w.get(x,y,z)) for x,y,z,*_ in ww.tolist()[:2000])
    ys = Counter(f[:,1].tolist()).most_common(4)
    print(spec, 'fill', len(f), dict(fm.most_common(4)), 'roof', dict(roof.most_common(4)), 'ys', ys, '| walls', len(ww), dict(wm.most_common(5)))
