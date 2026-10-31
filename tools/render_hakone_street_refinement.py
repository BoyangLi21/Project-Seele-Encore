"""Small before/after plan views from installed block arrays, not design lines."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from author_hakone_lakefront import Editor
from render_hakone_installed_map import color


def render(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed'or not receipt['changed_section_readback']:raise ValueError('Actual installation must finish first')
    e=Editor(a.candidate);a.out.mkdir(exist_ok=True,parents=True)
    cases=[('主城北侧商住入口',(-255,-145,-170,-75)),('西部坡地街道',(-665,70,-565,155)),
           ('南部住宅与接街步道',(-530,775,-390,915)),('箱根汤本南侧街区',(2140,1135,2260,1255))]
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
    fig,axes=plt.subplots(len(cases),2,figsize=(13,20),layout='constrained',facecolor='#f6f5ef')
    invisible={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light','minecraft:barrier','minecraft:structure_void'}
    for row,(label,(x0,z0,X,Z))in enumerate(cases):
        for side,which in enumerate(('before','after')):
            rgb=np.full((Z-z0+1,X-x0+1,3),.9,np.float32);height=np.full(rgb.shape[:2],-129,np.int16)
            for cx in range(x0//16,X//16+1):
                for cz in range(z0//16,Z//16+1):
                    r=e.region(cx*16,cz*16)
                    if(cx,cz)not in r['index']:continue
                    b=r[which][r['index'][cx,cz]];visible=np.array([s.split('[')[0]not in invisible for s in r['names']])
                    top=447-np.argmax(visible[b[::-1]],axis=0);ids=np.take_along_axis(b,top[None],axis=0)[0]
                    colors=np.array([color(s)for s in r['names']])
                    for iz in range(16):
                        for ix in range(16):
                            xx,zz=cx*16+ix-x0,cz*16+iz-z0
                            if 0<=xx<rgb.shape[1]and 0<=zz<rgb.shape[0]:rgb[zz,xx]=colors[ids[iz,ix]];height[zz,xx]=top[iz,ix]-128
            shade=np.clip(1+.025*(height-np.roll(height,1,0))+.018*(height-np.roll(height,1,1)),.67,1.16)
            ax=axes[row,side];ax.imshow(np.clip(rgb*shade[:,:,None],0,1),extent=(x0,X+1,Z+1,z0),interpolation='nearest')
            ax.set_title(label+' · '+('细化前'if side==0 else'已安装细化后'),loc='left',fontsize=14);ax.set_xlabel('X');ax.set_ylabel('Z · 北朝上')
        e.regions.clear()
    fig.suptitle('R55 已装街区细化 · 方块平面图\n实际存档改动已回读；屋檐、门面和高差观感请在游戏内人工审查',fontsize=18)
    fig.savefig(a.out/'street-before-after.png',dpi=140);plt.close(fig)
    print(a.out/'street-before-after.png',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    render(p.parse_args())
