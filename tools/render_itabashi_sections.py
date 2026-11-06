"""Measured bridge and boarding cross-sections from saved candidate blocks."""
import argparse, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.font_manager import FontProperties
from shapely.geometry import shape, LineString
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from author_itabashi_station import solid_boxes


def render(candidate, site, out):
    e=Editor(candidate);font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
    fig,axs=plt.subplots(3,1,figsize=(13,11),layout='constrained')
    def panel(ax,fixed,start,end,along,lo,hi):
        for pos in range(start,end+1):
            for y in range(lo,hi+1):
                x,z=(fixed,pos)if along=='z'else(pos,fixed)
                state=e.state(x,y,z)
                if 'grass_block'in state:c='#789166'
                elif 'dirt'in state:c='#b29d7f'
                elif 'glass'in state:c='#bdd6db'
                elif 'tactile'in state:c='#d4ad4f'
                else:c='#adb3ae'
                for b in solid_boxes(state):
                    lower=b[2]if along=='z'else b[0];upper=b[5]if along=='z'else b[3]
                    ax.add_patch(Rectangle((pos+lower,y+b[1]),upper-lower,b[4]-b[1],facecolor=c,edgecolor='#68746c',lw=.35))
        ax.set_xlim(start,end+1);ax.set_ylim(lo,hi+1);ax.set_aspect('equal',adjustable='box')
        ax.set_xlabel('Z'if along=='z'else'X');ax.set_ylabel('Y');ax.grid(alpha=.15)
    panel(axs[0],3138,730,765,'z',-80,-69)
    raw=json.loads(site.read_text('utf8'));water=unary_union([shape(q['geometry'])for q in raw['nearby_water_interfaces']])
    channel=water.intersection(LineString([(3138.5,730),(3138.5,765)]))
    buffer=water.buffer(3).intersection(LineString([(3138.5,730),(3138.5,765)]))
    for g in([buffer]if buffer.geom_type=='LineString'else buffer.geoms):
        lo,hi=g.bounds[1],g.bounds[3];axs[0].axvspan(lo,hi,color='#7ebde8',alpha=.12)
    for g in([channel]if channel.geom_type=='LineString'else channel.geoms):
        lo,hi=g.bounds[1],g.bounds[3];axs[0].plot([lo,hi],[-77,-77],c='#237ab5',lw=3,ls='--')
    axs[0].annotate('',xy=(739,-73),xytext=(739,-77),arrowprops=dict(arrowstyle='<->',color='#237ab5'))
    axs[0].text(740,-75,'预留净高 4 m',fontproperties=font,color='#165b89',fontsize=10)
    axs[0].set_title('A  桥横跨水道的纵剖：X = 3138.5；蓝色虚线是预留水面，水道尚未施工',fontproperties=font,fontsize=12)
    panel(axs[1],733,3135,3168,'x',-80,-69)
    axs[1].set_title('B  北侧缓坡与原街道：Z = 733.5；每级 0.5 格，完整实心承台连接现地',fontproperties=font,fontsize=12)
    panel(axs[2],3126,789,805,'z',-80,-71)
    # Cross-section of the full longitudinally swept visible vehicle envelope.
    proof=json.loads((candidate/'visible-model-sweep.json').read_text('utf8'))
    for band in proof['bands']:
        lo,hi=band['local_y'];w=band['visible_half_width'];W=band['swept_half_width']
        axs[2].add_patch(Rectangle((799.5-W,-77+lo),2*W,hi-lo,facecolor='none',edgecolor='#a84b3e',lw=1,ls='--'))
        axs[2].add_patch(Rectangle((799.5-w,-77+lo),2*w,hi-lo,facecolor='#d79869',edgecolor='#a84b3e',lw=.6,alpha=.42))
    axs[2].plot([798.25,800.75],[-76,-76],c='#923a35',lw=2)
    axs[2].text(790,-72.4,'可见外壳缝 0.1875 m；含 0.15 m 横向余量后净空 0.0375 m\n站台与原生 FLOOR 支承面同高，支承缝 0.25 m',fontproperties=font,fontsize=10)
    axs[2].set_title('C  站台与 e44 实际模型包络：X = 3126.5；虚线含安全余量，不是游戏渲染画面',fontproperties=font,fontsize=12)
    fig.savefig(out,dpi=160,facecolor='white');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('candidate','site','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();render(a.candidate,a.site,a.out)
