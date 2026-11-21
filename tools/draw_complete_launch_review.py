"""Coordinate-scaled engineering review from the one current spatial candidate."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from build_continuous_upright_directory_r52 import sample

BASE=Path('D:/eva/artifacts/map_complete_20261013')
doc=json.loads((BASE/'monotone_launch_candidate/MONOTONE_ASCENT_CANDIDATE.json').read_text('utf8'))
plan=json.loads((BASE/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':10,'axes.unicode_minus':False})
fig=plt.figure(figsize=(19,11),facecolor='#f5f7fa')
grid=fig.add_gridspec(2,3,width_ratios=[1,1.1,1.6],height_ratios=[1, .32],wspace=.25,hspace=.35)
ax=fig.add_subplot(grid[0,0]); ax.set_aspect('equal')
lake=plan['reservoir_candidate']; x0,x1=lake['x_bounds'];z0,z1=lake['z_bounds']
ax.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,facecolor='#b4dae5',edgecolor='#247793',lw=2))
ax.add_patch(Rectangle((-31,266),122,122,facecolor='#454d5c',edgecolor='#26303c',lw=2,alpha=.85))
ax.add_patch(Rectangle((-31,348),37,40,facecolor='#55b6bd',edgecolor='#126969',hatch='///',lw=1.2))
ax.text(-136,515,'同向正方形人工湖\n275 × 275 m',ha='center',va='center',color='#205264')
ax.text(30,315,'金字塔\n水线截面',color='white',ha='center')
ax.annotate('西南角相交加大\n约 37 × 40 m',(-12.5,368),(-200,287),arrowprops={'arrowstyle':'->','color':'#126969'},color='#126969',ha='center')
ax.plot([-11.5,30.5,72.5],[124.5]*3,'s',color='#15808b',ms=6)
ax.text(25,99,'① 三道原轴直升',ha='center',color='#15808b')
ax.annotate('北',(-235,105),(-235,175),arrowprops={'arrowstyle':'-|>','lw':1.5},ha='center')
ax.set_xlim(-310,115);ax.set_ylim(665,65);ax.grid(alpha=.17);ax.set_xlabel('X / m');ax.set_ylabel('Z / m（北向上）')
ax.set_title('A  湖与金字塔：同向、只接西南角',loc='left',pad=15,fontsize=12)

ax=fig.add_subplot(grid[0,1]); colors=['#178491','#cf782c','#7852a7']
for v,x in enumerate((72.5,30.5,-11.5)):
    ax.plot([x,x],[330,28.5],color='#87909c',lw=3,alpha=.65)
    ax.plot(x,330,'s',color='#3c485b',ms=10)
for bank,z in enumerate((124.5,76.5,28.5),1):
    ax.add_patch(Rectangle((-29,z-18.5),118,37,fc=colors[bank-1],alpha=.13,ec=colors[bank-1],lw=2))
    ax.plot([-11.5,30.5,72.5],[z]*3,'o',color=colors[bank-1],ms=7)
    ax.text(103,z,f'{bank}  '+['地下地表','原城市井','箱根'][bank-1],va='center',color=colors[bank-1])
for z in (52.5,100.5):
    ax.text(-64,z,'48 m',va='center',ha='center',fontsize=9)
ax.add_patch(Rectangle((-29,267),118,117,fc='#b9c2cf',alpha=.45,ec='#3c485b',lw=2))
ax.text(30,365,'原机库 · 脚位 −1062',ha='center',fontsize=9)
ax.text(30,217,'原斜轨 + 短距串联\n仅用于发射前慢速就位',ha='center',color='#46566a',bbox={'facecolor':'white','edgecolor':'none','alpha':.92})
ax.set_xlim(-88,192);ax.set_ylim(405,-5);ax.set_aspect('equal');ax.grid(alpha=.17)
ax.set_xlabel('X / m');ax.set_ylabel('Z / m（北向上）');ax.set_title('B  机库内仍为紧凑三组，每组 3 道',loc='left',pad=15,fontsize=12)

ax=fig.add_subplot(grid[0,2]); stats=[]
for bank in (1,2,3):
    case=next(c for c in doc['cases'] if c['bank']==bank and c['variant']==1)
    pts=np.concatenate([sample(s['controls'],150) for s in case['centre_curve']['segments']])
    horizontal=np.r_[0,np.cumsum(np.linalg.norm(np.diff(pts[:,[0,2]],axis=0),axis=1))]
    ax.plot(horizontal,pts[:,1],color=colors[bank-1],lw=3,label=f'{bank}  '+['地下地表直升','接原城市发射井','地下岩层斜升 → 箱根'][bank-1])
    ax.plot(horizontal[-1],pts[-1,1],'o',color=colors[bank-1],ms=6)
    if bank==1:ax.annotate('① 全程垂直',(0,-640),(95,-730),arrowprops={'arrowstyle':'->','color':colors[0]},color=colors[0])
    if bank==2:ax.annotate('② 先垂直 112 m\n再向上斜接原井',(5,-905),(280,-955),arrowprops={'arrowstyle':'->','color':colors[1]},color=colors[1])
    if bank==3:ax.annotate(f"③ 先垂直 {case['initial_exact_vertical_metres']:.0f} m\n承载架过上门后再斜升",(0,-962),(650,-1130),arrowprops={'arrowstyle':'->','color':colors[2]},color=colors[2])
    length=case['length_metres'];v=min(180,math.sqrt(length*120));seconds=2*v/120+max(0,length-v*v/120)/v
    stats.append(dict(bank=bank,length=round(length,1),profile_target_seconds=round(seconds,1),peak_mps=v))
ax.axhline(-467,color='#678878',lw=1,ls='--');ax.text(700,-447,'地下地表约 −467',color='#678878')
ax.axhline(80,color='#678878',lw=1,ls='--');ax.text(680,101,'城市地表约 80',color='#678878')
ax.axhspan(-500,40,xmin=.15,xmax=.63,color='#e4e9ed',alpha=.5)
ax.text(870,-270,'GeoFront 空腔范围示意\n③ 从岩层下方绕出',ha='center',color='#647282')
ax.set_ylim(-1190,235);ax.set_xlabel('各路线从各自井底累计的水平距离 / m');ax.set_ylabel('真实 Y / m')
ax.grid(alpha=.17);ax.legend(loc='upper left',fontsize=9);ax.set_title('C  各路线独立纵剖面：没有水平发射段\n横轴各自归零；曲线重叠不代表空间相交',loc='left',pad=15,fontsize=11)

bottom=fig.add_subplot(grid[1,:]);bottom.axis('off')
bottom.text(.01,.98,'正式发射的演出与速度',fontsize=15,fontweight='bold',va='top',color='#26303c')
bottom.text(.01,.64,'机库慢速就位 → 停稳／锁定 → 电流爆发 + 接触点短闪 → 高速上升 + 轨道摩擦火花 → 出口减速／释放',fontsize=12,color='#26303c')
bottom.text(.01,.31,'设计速度上限 180 m/s，起步加速度 120 m/s²。仅计算正式发射段：'+ '；'.join(f"{r['bank']}号约 {r['profile_target_seconds']:.1f} 秒" for r in stats)+'。',fontsize=11,color='#46566a')
bottom.text(.01,.03,'状态：九路洞体／内衬、27座水平门基础与完整闭口已落图；正在安装轨道支承并联调机库。以上时长是设计计算，运行和音画待实测。',fontsize=10,color='#8b592c')
fig.suptitle('本轮更新 · 西南角扩大相交 / 原轴直升 / 先竖后斜 / 发射声光',fontsize=20,x=.055,ha='left',y=.985,color='#26303c')
out=BASE/'design_reviews';out.mkdir(exist_ok=True)
fig.savefig(out/'launch-and-lake-updated.png',dpi=140,bbox_inches='tight');plt.close(fig)
fig=plt.figure(figsize=(16,9),facecolor='#f5f7fa');ax=fig.add_subplot(111,projection='3d')
for c in doc['cases']:
    p=np.concatenate([sample(s['controls'],200) for s in c['centre_curve']['segments']])
    ax.plot(p[:,0],p[:,2],p[:,1],color=colors[c['bank']-1],alpha=.8,lw=1.8)
    ax.scatter(*p[0,[0,2,1]],color=colors[c['bank']-1],s=18)
    if c['variant']==1:ax.text(*p[-1,[0,2,1]],['  ① 地下地表','  ② 原城市井','  ③ 箱根'][c['bank']-1],fontsize=11,color=colors[c['bank']-1])
ax.set_xlabel('X / m',labelpad=8);ax.set_ylabel('Z / m',labelpad=8);ax.set_zlabel('Y / m',labelpad=8)
ax.set_box_aspect((1.5,1.7,1.3));ax.view_init(elev=22,azim=-63)
fig.suptitle('9 道发射线路 · 使用共同世界坐标的三维核对图',fontsize=18,y=.96)
fig.text(.05,.04,'每组 3 道。① 保持原轴；② 与③ 均先垂直再持续斜升。扩大的载体包络初筛未发现相交，完整轨道／门体扫掠仍待施工验线。',fontsize=11,color='#46566a')
fig.savefig(out/'nine-ascent-routes-world-coordinates.png',dpi=140,bbox_inches='tight');plt.close(fig)
(out/'LATEST_LAUNCH_REVIEW.json').write_text(json.dumps(dict(source=doc['schema'],spatial_plan=str(BASE/'ROOT_SPATIAL_PLAN.json'),stats=stats,measured_game_time=False),indent=2),'utf8')
print(json.dumps(stats))
