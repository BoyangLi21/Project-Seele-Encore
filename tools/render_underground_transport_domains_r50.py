"""Review map of measured domains; never reads/writes live world."""
from pathlib import Path
import json,heapq,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r50/underground_airlift'
def main():
    p=np.load(OUT/'cavern_grid/actual_cavern_air_band.npz');m=json.loads((OUT/'nerv_underground_transport_r50.json').read_text('utf8'))
    x0,z0=map(int,p['origin']);h,w=p['known_full'].shape;s=np.zeros((h,w),np.uint8)
    s[p['known_full']]=1;s[p['known_full']&p['blocked_any_y_minus410_to_minus237']]=2;s[p['airport_connected']]=3
    points={n['id']:n['pos']for n in m['nodes']};adj={k:[]for k in points}
    for a,b in m['edges']:d=math.dist(points[a],points[b]);adj[a].append((b,d));adj[b].append((a,d))
    dist={'airportLift':0};prev={};pending=[(0,'airportLift')]
    while pending:
        cost,node=heapq.heappop(pending)
        if cost!=dist[node]:continue
        for target,length in adj[node]:
            if cost+length<dist.get(target,math.inf):dist[target]=cost+length;prev[target]=node;heapq.heappush(pending,(cost+length,target))
    view=set()
    for node in points:
        if not(node.startswith('cruise_field_')or node.startswith('receiver_')):continue
        while node in prev:view.add(tuple(sorted((node,prev[node]))));node=prev[node]
    fig,ax=plt.subplots(figsize=(11,10));ax.imshow(s,origin='lower',extent=[x0,x0+w,z0,z0+h],cmap=ListedColormap(['#bfc5cc','#dfcba9','#8d6b72','#e1eff4']),interpolation='nearest')
    for zone in m['pickup_zones']:
        if not zone['id'].startswith('pickup_field_'):continue
        lo,hi=zone['bounds'];ax.add_patch(Rectangle((lo[0],lo[2]),hi[0]-lo[0],hi[2]-lo[2],facecolor='#93c7ad',edgecolor='none',alpha=.5))
    for a,b in view:
        u,v=points[a],points[b];ax.plot([u[0],v[0]],[u[2],v[2]],color='#2e537c',lw=.8)
    ax.scatter([-440],[-270],s=100,c='#d07533',marker='*',zorder=8,label='Commissioned underground airport candidate')
    ax.scatter([-11.5,30.5,72.5],[100.5]*3,s=35,c='#6c496a',marker='s',zorder=8,label='Receiving platforms for original units')
    ax.text(-440,-320,'Airport',ha='center',fontsize=9);ax.text(60,170,'3 receiver axes',ha='center',fontsize=9)
    ax.set(xlabel='World X (m)',ylabel='World Z (m)')
    ax.set_title('R50 main GeoFront transport domain: actual stored voxels\nGreen: registered pickup | Blue: routes | Rose: blocked | Grey: unknown/proto',fontsize=12)
    ax.legend(loc='upper left',fontsize=8);ax.set_aspect('equal');fig.tight_layout();target=OUT/'connected_cavern_pickup_map_r50.png';fig.savefig(target,dpi=140);plt.close(fig)
    report=OUT/'expanded_topology_readback.json';j=json.loads(report.read_text('utf8'));j['review_map']=str(target.resolve());report.write_text(json.dumps(j,ensure_ascii=False,indent=2),'utf8')
    print(target)
if __name__=='__main__':main()
