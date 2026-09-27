"""Baked, reusable upholstered/formed seating inside the existing collision footprint."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'src/main/resources/assets/projectseele/models/block'


def model(station=False):
    elements=[]
    def box(lo,hi,material,rotation=None):
        faces={n:{'texture':'#'+material} for n in ('north','south','east','west','up','down')}
        part={'from':lo,'to':hi,'faces':faces}
        if rotation:part['rotation']=rotation
        elements.append(part)
    if station:
        # Anchored two-foot frame, rather than an office swivel base.
        for x in (4,12):
            box([x-1,0,3],[x+1,1.2,14],'metal')
            box([x-.65,1.2,7],[x+.65,8,9],'metal')
        box([3,6.5,7],[13,7.6,9],'metal')
    else:
        for lo,hi in [([2,1,7.1],[14,2.1,8.9]),([7.1,1,2],[8.9,2.1,14]),([4,1,4],[12,2,6])]:box(lo,hi,'metal')
        for x,z in ((2.4,8),(13.6,8),(8,2.4),(8,13.6),(4.5,4.5)):
            box([x-.8,0,z-.65],[x+.8,1.7,z+.65],'rubber')
            box([x-.4,1.3,z-.4],[x+.4,2.2,z+.4],'metal')
        box([6.9,2,6.9],[9.1,7.8,9.1],'metal')
        box([6.3,2,6.3],[9.7,4.5,9.7],'rubber')
    # Rounded cushion is built as recessed rings, with the seam under the lip.
    box([2.1,7.8,2.5],[13.9,8.6,13.2],'rubber')
    box([2.3,8.6,2.7],[13.7,9.65,13.0],'fabric')
    box([2.7,9.65,3.1],[13.3,10.25,12.6],'fabric')
    box([3.2,10.25,3.6],[12.8,10.45,12.1],'fabric')
    for x in (3.1,12.4):box([x,8.0,11.3],[x+.5,17.8,12.1],'metal')
    for y0,y1,z0,z1 in ((10.2,12.7,12.4,14.35),(12.7,15.3,12.7,14.65),(15.3,18.1,13.0,15.0)):
        box([2.6,y0,z0],[13.4,y1,z1],'rubber')
        box([2.95,y0+.12,z0-.12],[13.05,y1-.12,z0+.8],'fabric')
        box([3.3,y0+.3,z0-.19],[12.7,y1-.3,z0+.25],'fabric')
    if not station:
        for x in (1.8,13.2):
            box([x,8.5,7.7],[x+.9,13.0,9.0],'metal')
            box([x-.1,12.7,4.2],[x+1,13.4,11.2],'rubber')
            box([x+.05,13.4,4.5],[x+.85,13.65,10.9],'fabric')
    return {'parent':'minecraft:block/block','textures':{
        'particle':'minecraft:block/gray_concrete','fabric':'minecraft:block/cyan_terracotta' if station else 'minecraft:block/gray_concrete',
        'metal':'projectseele:block/nerv_machine_edge','rubber':'minecraft:block/black_concrete'},'elements':elements}


def main():
    for name,station in [('nerv_office_chair',False),('station_seat',True),('military_seat',False)]:
        data=model(station);path=OUT/(name+'.json');path.write_text(json.dumps(data,indent=2),'utf8');print(name,len(data['elements']),'baked elements; no new block entity or ticker')


if __name__=='__main__':main()
