"""Readable current design review: exact route data and explicitly unresolved exit."""
from pathlib import Path
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Polygon
from matplotlib.lines import Line2D
from build_continuous_upright_directory_r52 import sample

BASE=Path('D:/eva/artifacts/map_complete_20261013')
OUT=BASE/'design_reviews';OUT.mkdir(exist_ok=True)
SOURCE=BASE/'complete_routes/GROUND_CONTINUOUS_DESIGN.json'
doc=json.loads(SOURCE.read_text('utf8'))
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,'axes.titlesize':14})
colors={1:'#087f8c',2:'#ce711c',3:'#7951a1'}
nodes={r['id']:np.array(r['foot_frame']['translation']) for r in doc['nodes']}
legs={r['id']:r for r in doc['legs']}
def curve(leg):
    if 'centre_curve' in leg:return np.concatenate([sample(s['controls'],181) for s in leg['centre_curve']['segments']])
    a,b=nodes[leg['from']],nodes[leg['to']]
    p=np.linspace(a,b,181)
    if 'ramp_profile' in leg:
        r=leg['ramp_profile'];distance=np.linalg.norm((b-a)[[0,2]])*np.linspace(0,1,181)
        q=np.clip(distance-r['flat_before'],0,r['slope_run']);blend=r['blend'];run=r['slope_run']
        rounded=lambda v:v*.5-blend/(2*np.pi)*np.sin(np.pi*v/blend)
        h=np.where(q<blend,rounded(q),np.where(q>run-blend,run-blend-rounded(run-q),q-blend/2))/(run-blend)
        p[:,1]=a[1]+(b[1]-a[1])*h
    return p
def style(ax):
    ax.set_facecolor('#fbfcfc');ax.grid(color='#d9dfe2',lw=.6,alpha=.6);ax.set_axisbelow(True)
    for spine in ax.spines.values():spine.set_color('#aab5ba')
fig,axs=plt.subplots(1,2,figsize=(16,11),layout='constrained')
ax=axs[0];style(ax)
ax.add_patch(Rectangle((-285,11),275,275,facecolor='#dbeef0',edgecolor='#508a93',lw=1.8))
ax.text(-151,174,'同向正方形人工湖\n落位与出口正在联调',ha='center',color='#315660')
ax.add_patch(Rectangle((-90,207),240,240,facecolor='none',edgecolor='#777f82',ls='--',lw=1.4))
ax.text(-78,435,'金字塔底部投影',color='#60696d')
ax.add_patch(Rectangle((-31,266),122,122,facecolor='#eef0f0',edgecolor='#343c42',lw=2))
ax.text(30,365,'金字塔水线截面\n与方湖同轴',ha='center',color='#343c42')
ax.add_patch(Rectangle((-38,280),136,94,fill=False,edgecolor='#637b8c',lw=1.4,ls=':'))
for variant,x in enumerate((72.5,30.5,-11.5)):
    ax.scatter([x],[328.5],s=65,marker='s',color='#425b6b',zorder=6)
    ax.text(x,345,f'{variant:02d}号机',ha='center',fontsize=9,color='#334854')
    p=curve(legs[f'unit{variant}/original_incline']);ax.plot(p[:,0],p[:,2],color='#506f80',lw=2)
    for j in (1,2):
        p=curve(legs[f'unit{variant}/bank{j}_to_{j+1}']);ax.plot(p[:,0],p[:,2],color='#506f80',lw=2)
for bank,z in enumerate((124.5,76.5,28.5),1):
    ax.add_patch(Rectangle((-29,z-18.5),119,37,facecolor=colors[bank]+'18',edgecolor=colors[bank],lw=1.6))
    for x in (-11.5,30.5,72.5):ax.plot([x-17,x-17],[z-18.5,z+18.5],color=colors[bank],lw=.65)
    ax.text(103,z,f'第{bank}区\n'+{1:'→地下地表',2:'→原地表井',3:'→箱根'}[bank],va='center',color=colors[bank],fontsize=11)
    if bank<3:ax.text(6,z-24,'11 m',fontsize=8,color='#414b50',ha='center')
ax.text(110,229,'原斜向转移段\n保留形状\n脚位 −678 → −646',fontsize=10,color='#425b6b')
ax.annotate('机库 → 原斜轨 → 第一区 → 第二区 → 第三区',xy=(160,425),xytext=(160,425),ha='right',fontsize=10)
ax.add_patch(Rectangle((-34,100),130,49,fill=False,edgecolor='#b54742',ls='--',lw=1.3))
ax.add_patch(Rectangle((-34,100),24,49,facecolor='#d9534f33',edgecolor='#b54742',hatch='///',lw=.6))
ax.annotate('第一通道西口与方湖冲突\n最终出口待重排',xy=(-20,123),xytext=(-259,43),
    color='#9c332e',fontsize=10,arrowprops=dict(arrowstyle='->',color='#9c332e'),bbox=dict(facecolor='white',edgecolor='none',alpha=.9,pad=3))
ax.set(xlim=(-325,178),ylim=(462,-67),xlabel='X / 方块',ylabel='Z / 方块（北 ↑）',title='① 基部平面：三个发射区串联，每区三道')
ax.set_aspect('equal')
ax=axs[1];style(ax)
ax.axhline(-467,color='#738676',lw=1);ax.text(380,-460,'地下地表约 Y=−467',ha='right',fontsize=10,color='#536959')
ax.axhline(80,color='#adb59f',lw=1);ax.text(380,89,'城市地表约 Y=80',ha='right',fontsize=10,color='#536959')
ax.add_patch(Polygon([[207,-563],[447,-563],[327,-384]],facecolor='#aab4b622',edgecolor='#899398',lw=1.1))
ax.text(327,-479,'金字塔',ha='center',fontsize=11,color='#5b656a')
ax.add_patch(Rectangle((280,-749),110,169,facecolor='#698fa015',edgecolor='#69808b',lw=1.1))
ax.text(388,-717,'机库',ha='right',color='#425b6b')
ax.add_patch(Rectangle((225,-927),188,131,facecolor='#9097ac16',edgecolor='#778195',lw=1.1))
ax.text(319,-877,'完整莉莉丝层',ha='center',color='#636e83')
for x,label,y0,y1 in ((253,'原主梯',-846,-502),(302,'原东梯',-603,-457)):
    ax.plot([x,x],[y0,y1],color='#515c66',lw=1.4,ls='--');ax.text(x+4,y0+16,label,rotation=90,fontsize=9,color='#515c66')
ax.plot([253,302,370],[-603,-603,-603],color='#515c66',lw=1.2,ls='--')
p=curve(legs['unit1/original_incline']);ax.plot(p[:,2],p[:,1],color='#506f80',lw=3)
for j in (1,2):
    p=curve(legs[f'unit1/bank{j}_to_{j+1}']);ax.plot(p[:,2],p[:,1],color='#506f80',lw=3)
for bank in (1,2,3):
    p=curve(legs[f'unit1/exit{bank}/upright_continuous']);inside=(p[:,2]>-80)&(p[:,2]<460)
    ax.plot(p[inside,2],p[inside,1],color=colors[bank],lw=2.6,ls='--' if bank==1 else '-')
    z=(124.5,76.5,28.5)[bank-1];ax.scatter(z,-646,color=colors[bank],s=50,zorder=8)
    ax.annotate(f'{bank}',xy=(z,-646),xytext=(z,-692),ha='center',color=colors[bank],fontweight='bold',arrowprops=dict(arrowstyle='-',color=colors[bank]))
ax.annotate('① 地下地表出口\n西侧一路需要调整',xy=(124.5,-466),xytext=(158,-405),color=colors[1],fontsize=10,arrowprops=dict(arrowstyle='->',color=colors[1]))
ax.annotate('② 接原有地表发射井\n保留原井位置 Z≈−35.5',xy=(-35.5,-190),xytext=(40,-140),color=colors[2],fontsize=10,arrowprops=dict(arrowstyle='->',color=colors[2]))
ax.annotate('③ 向北展开后斜升至箱根',xy=(-60,-644),xytext=(-42,-753),color=colors[3],fontsize=10,arrowprops=dict(arrowstyle='->',color=colors[3]))
ax.set(xlim=(-80,460),ylim=(-955,125),xlabel='Z / 方块（向左为北）',ylabel='Y / 高度',title='② 纵向剖面：地下地表与城市地表分开')
fig.suptitle('发射通道设计核对图 · 当前候选',fontsize=20)
fig.savefig(OUT/'launch-local-and-section.png',dpi=150);plt.close(fig)
fig=plt.figure(figsize=(16,10),layout='constrained');ax=fig.add_subplot(projection='3d')
for v in range(3):
    for key in [f'unit{v}/original_incline',f'unit{v}/bank1_to_2',f'unit{v}/bank2_to_3']:
        p=curve(legs[key]);ax.plot(p[:,0],p[:,2],p[:,1],color='#586f7e',lw=1.6)
    for bank in (1,2,3):
        p=curve(legs[f'unit{v}/exit{bank}/upright_continuous'])
        ax.plot(p[:,0],p[:,2],p[:,1],color=colors[bank],lw=2.2,ls=('--' if bank==1 else ('-', '--', ':')[v]))
        ax.scatter(*[p[-1,0],p[-1,2],p[-1,1]],color=colors[bank],s=28)
ax.text(85,330,-678,'原机库／原斜轨',color='#425b6b')
ax.text(100,135,-465,'① 地下地表\n西口待改',color=colors[1])
ax.text(95,-35,100,'② 原地表井',color=colors[2])
ax.text(-1390,-1580,198,'③ 箱根三出口\nY=175（地形候选）',color=colors[3])
for bank,z in enumerate((124.5,76.5,28.5),1):ax.text(-15,z,-704,f'第{bank}区',color=colors[bank],fontsize=9)
ax.set(xlabel='X / 方块',ylabel='Z / 方块',zlabel='Y / 高度',xlim=(-1450,150),ylim=(-1660,410),zlim=(-760,245))
ax.set_box_aspect((1600,2070,1005));ax.view_init(elev=23,azim=-54)
ax.legend(handles=[Line2D([0],[0],color=colors[b],lw=3,label={1:'第一通道：地下地表（出口待改）',2:'第二通道：原地表发射井',3:'第三通道：箱根'}[b]) for b in (1,2,3)],loc='upper left',frameon=False)
fig.suptitle('九条发射路线三维总览 · 每区三道，EVA 保持直立朝向',fontsize=19)
fig.savefig(OUT/'launch-nine-routes-3d.png',dpi=150);plt.close(fig)
(OUT/'LAUNCH_DIAGRAM_RECEIPT.json').write_text(json.dumps(dict(source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),status='review_candidate',bank1_exit_unresolved_due_to_corrected_cooriented_square_lake=True,lake_geometry='cooriented square; position not final',world_written=False),indent=2),'utf8')
print(OUT)
