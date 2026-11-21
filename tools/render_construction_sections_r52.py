"""Read current saved blocks into labelled construction sections, no mutations."""
import argparse,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from query_blocks import chunk_statuses


def section(x,y0,z0,y1,z1):
    """Do not paint unfinished edge chunks as air in a read-only overview."""
    statuses=chunk_statuses(BASE/'WORLD_R52','projectseele:geofront',{(x//16,z)for z in range(z0//16,z1//16+1)})
    names=['UNMEASURED'];a=np.zeros((y1-y0+1,z1-z0+1,1),dtype=np.int32);unknown=[];runs=[]
    for z in range(z0//16,z1//16+1):
        if statuses.get((x//16,z))!='full':unknown.append([x//16,z,statuses.get((x//16,z),'missing')]);continue
        if runs and runs[-1][1]==z-1:runs[-1][1]=z
        else:runs.append([z,z])
    for first,last in runs:
        low=max(z0,first*16);high=min(z1,last*16+15);values,palette=measure((x,y0,low),(x,y1,high));mapping=[]
        for s in palette:
            if s not in names:names.append(s)
            mapping.append(names.index(s))
        a[:,low-z0:high-z0+1,:]=np.asarray(mapping)[values]
    return a,names,unknown


def colors(names):
    result=[]
    for s in names:
        if s=='UNMEASURED':c='#ca6ac7'
        elif s in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}:c='#eef2f5'
        elif 'water' in s or 'lcl' in s:c='#378faf'
        elif 'bedrock' in s:c='#777574'
        elif s.startswith(('minecraft:stone','minecraft:deepslate','minecraft:dirt','minecraft:grass_block')):c='#b7b1a5'
        elif 'glass' in s:c='#87bdbc'
        elif 'light' in s or 'lantern' in s:c='#edbc50'
        elif 'barrier' in s:c='#ce6458'
        else:c='#354f5a'
        result.append(matplotlib.colors.to_rgb(c))
    return np.asarray(result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',default='');args=parser.parse_args()
    out=BASE/'construction_review'
    if args.stage:
        assert args.stage.replace('_','').isalnum();out=out/args.stage
    out.mkdir(parents=True,exist_ok=True);measurements=[]
    fig,axes=plt.subplots(3,1,figsize=(17,18),constrained_layout=True)
    for ax,x in zip(axes,(30,89,108)):
        lo=(x,-944,-875);hi=(x,-375,555);a,p,unknown=section(x,lo[1],lo[2],hi[1],hi[2])
        measurements.append(dict(low=lo,high=hi,states_sha256=hashlib.sha256(a.tobytes()).hexdigest(),palette=p,unmeasured_chunks=unknown))
        ax.imshow(colors(p)[a[:,:,0]],origin='lower',extent=(-875,556,-944,-374),interpolation='nearest',aspect='equal')
        ax.set_title(f'ACTUAL SAVE / X={x} / N <- Z -> S / Construction incomplete / Purple: unfinished edge chunks')
        ax.set_ylabel('Absolute Y');ax.set_xlabel('Absolute Z');ax.grid(alpha=.12)
        for z,y,t in [(327,-380,'HQ pyramid'),(328,-570,'Original hangar'),(124,-535,'Bank 1'),(-328,-535,'Bank 2'),(-781,-535,'Bank 3'),(327,-790,'Full Terminal layer')]:
            ax.text(z,y,t,fontsize=8,ha='center')
    fig.savefig(out/'CURRENT_LONGITUDINAL_SECTIONS.png',dpi=125);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(16,11),constrained_layout=True)
    for ax,y in zip(axes.ravel(),(-554,-603,-630,-704,-846)):
        a,p=measure((-65,y,220),(165,y,450));ax.imshow(colors(p)[a[0]],origin='upper',extent=(-65,166,451,220),interpolation='nearest')
        ax.set_title(f'ACTUAL SAVE / foot elevation Y={y}');ax.set_xlabel('X');ax.set_ylabel('Z, north upward')
        ax.plot(108,407,'ro',ms=4);ax.text(110,408,'Shared lift',fontsize=7)
    axes.ravel()[-1].axis('off');axes.ravel()[-1].text(.05,.8,'Read-only block sections.\nNot a native walking/collision test.\n\nRed: closed gate collision\nDark: constructed material\nBeige: geological material\nBlue: water/LCL\nLight: air',va='top')
    fig.savefig(out/'CURRENT_FLOOR_SECTIONS.png',dpi=125);plt.close(fig)
    (out/'MEASURED_SECTIONS.json').write_text(json.dumps(dict(world=str(BASE/'WORLD_R52'),world_written=False,native_verified=False,measurements=measurements),indent=2),'utf8')
    print(out)


if __name__=='__main__':main()
