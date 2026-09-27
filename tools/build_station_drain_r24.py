"""Original batched block-model drainage cover; no per-cell block entity or tick."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];A=ROOT/'src/main/resources/assets/projectseele'
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
def main():
    elements=[]
    def box(a,b,texture):elements.append({'from':a,'to':b,'faces':{d:{'texture':'#'+texture,'uv':[0,0,16,16]} for d in ('north','south','east','west','up','down')}})
    box([0,0,0],[16,15.4,16],'floor');box([.5,15.4,.5],[15.5,15.6,15.5],'dark')
    for a,b in [([.4,15.6,.4],[15.6,16,1.4]),([.4,15.6,14.6],[15.6,16,15.6]),([.4,15.6,1.4],[1.4,16,14.6]),([14.6,15.6,1.4],[15.6,16,14.6])]:box(a,b,'metal')
    for x in range(2,15,2):box([x,15.7,1.4],[x+.75,16,14.6],'metal')
    for x in (1,15):
        for z in (1,15):box([x-.25,16,z-.25],[x+.25,16.03,z+.25],'dark')
    save(A/'models/block/station_drain.json',{'textures':{'floor':'projectseele:block/period_station_concrete_r24','metal':'minecraft:block/gray_concrete','dark':'minecraft:block/black_concrete','particle':'projectseele:block/period_station_concrete_r24'},'elements':elements})
    save(A/'blockstates/station_drain.json',{'variants':{'':{'model':'projectseele:block/station_drain'}}});save(A/'models/item/station_drain.json',{'parent':'projectseele:block/station_drain'})
    save(ROOT/'src/main/resources/data/projectseele/loot_tables/blocks/station_drain.json',{'type':'minecraft:block','pools':[{'rolls':1,'entries':[{'type':'minecraft:item','name':'projectseele:station_drain'}],'conditions':[{'condition':'minecraft:survives_explosion'}]}]})
    print('Original drain model elements',len(elements))
if __name__=='__main__':main()
