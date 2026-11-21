"""Root's measured exterior landmark sections, never a claim that images are ready."""
import json,math
import numpy as np
from pathlib import Path
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import read_box


def main():
    out=BASE/'runtime_directory/candidate/civil_landmarks';out.mkdir(parents=True,exist_ok=True)
    lo=(-95,-474,202);hi=(155,-386,452);a,palette=measure(lo,hi)
    shell=np.array(['nerv_pyramid_panel'in s for s in palette])[a]
    local=np.argwhere(shell);points=local[:,[2,0,1]]+np.array(lo)
    selections={}
    for name,pos,target,face in [
        ('pyramid_west_lake',[-170.,-393.,179.],[30.,-450.,327.],'west'),
        ('pyramid_east_original_interfaces',[180.,-424.,473.],[30.,-450.,327.],'east_south')]:
        keep=[]
        for y in np.unique(points[:,1]):
            row=points[points[:,1]==y]
            if face=='west':edge=row[row[:,0]==row[:,0].min()]
            else:edge=row[(row[:,0]==row[:,0].max())|(row[:,2]==row[:,2].max())]
            keep.extend(map(tuple,edge.tolist()))
        sections=sorted({(int(x)//16,int(y)//16,int(z)//16)for x,y,z in keep})
        selections[name]=dict(position=pos,target=target,required_sections=sections,measured_landmark_blocks=len(keep),
            scope='Actual camera-facing above-water pyramid shell facets; this does not certify buried interiors or the entire map')
    # The water surface and shaped rim both belong to the actual authored lake.
    lo2=(-1380,-481,414);hi2=(-900,-465,786);water,pal2=measure(lo2,hi2)
    wet=np.array([s.startswith('minecraft:water')for s in pal2])[water]
    y=-473;mask=wet[y-lo2[1]];zz,xx=np.nonzero(mask)
    lake_sections=sorted({((int(x)+lo2[0])//16,y//16,(int(z)+lo2[2])//16)for x,z in zip(xx,zz)})
    selections['far_natural_lake']=dict(position=[-1220.,-420.,435.],target=[-1140.,-473.,600.],required_sections=lake_sections,
        measured_landmark_blocks=len(xx),scope='Actual contiguous lake water surface sections; surrounding ecology/terrain still requires direct visual review')
    # Explicit sampled near and middle slopes, not a single summit point.
    ridge=[]
    for x in range(-1552,-1135,32):
        for z in range(-1744,-1263,32):
            column=read_box(BASE/'WORLD_R52','projectseele:geofront',(x,70,z),(x,223,z))
            ys=[Y for Y in range(70,224)if column[x,Y,z]in('minecraft:grass_block[snowy=false]','minecraft:stone','minecraft:dirt')]
            if ys:ridge.append((x,max(ys),z))
    selections['far_yashima_ridge']=dict(position=[-1460.,240.,-1510.],target=[-1240.,174.,-1400.],required_sections=sorted({(x//16,y//16,z//16)for x,y,z in ridge}),
        measured_landmark_blocks=len(ridge),scope='Actual sampled slope and shelf sections across the authored far ridge; not a full terrain acceptance')
    for name,row in selections.items():
        (out/(name+'.json')).write_text(json.dumps(row,indent=2),'utf8')
        print(name,len(row['required_sections']),'measured sections')
    (out/'INDEX.json').write_text(json.dumps(dict(world_written=False,native_ready=False,landmarks=selections),indent=2),'utf8')


if __name__=='__main__':main()
