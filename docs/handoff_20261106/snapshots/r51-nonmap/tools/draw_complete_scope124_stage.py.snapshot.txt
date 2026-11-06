"""Measured civil-stage diagram; deliberately not a gameplay screenshot."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.font_manager import FontProperties


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    base=a.base.resolve();pit=json.loads((base/'complete_carrier_pits/three_supported_dry_carrier_pits/PLAN.json').read_text('utf8'))
    buttons=json.loads((base/'hangar_operator_controls/APPLIED.json').read_text('utf8'))
    air=json.loads((base/'air_transport_shaft/actual_machine_bearings_and_cassettes/PLAN.json').read_text('utf8'))
    assert pit['world_written'] and buttons['world_written'] and air['world_written']
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':12})
    fig,axes=plt.subplots(1,2,figsize=(16,8),layout='constrained')
    fig.suptitle('阶段图｜已落图的三组维修坑、操作键与独立空运井',fontsize=21)
    ax=axes[0]
    for g in pit['gates']:
        x,y,z=g['frame']['position'];v=g['variant']
        ax.add_patch(Rectangle((x-16.5,z-17.5),33,35,facecolor='#daedf4',edgecolor='#24758c',lw=2))
        for support in g['supports']:
            q=support['position'];ax.scatter(q[0]+.5,q[2]+.5,s=16,c='#435662')
        ax.text(x,z,f'EVA-{v:02d}\n33 × 33 m 净口',ha='center',va='center')
    colors=['#169a88','#357cad','#cc7341']
    for row in buttons['buttons']:
        x,y,z=row['position'];ax.scatter(x+.5,z+.5,marker='s',s=23,c=colors[('PREPARE','STATUS','CANCEL').index(row['action'])])
    ax.set(xlim=(-39,100),ylim=(357,295),aspect='equal',xlabel='X / 方块',ylabel='Z / 方块',title='① 机库平面 · 三个原机位与维修坑')
    ax.text(30,299,'北侧 → 原坡道 → 三个紧邻发射区',ha='center',color='#435662')
    ax.text(30,354,'右侧三键：整备 / 状态 / 取消\n坑底保留实际机械行程；原湿区地板由联锁开启',ha='center',va='center',fontsize=11)
    ax.grid(alpha=.12)
    ax=axes[1]
    ax.add_patch(Rectangle((-802,-476),164,544,facecolor='#edf1f5',edgecolor='#536f82',lw=2))
    ax.plot([-802,-638],[68,68],lw=5,color='#d38738')
    ax.plot([-637,-637],[-475,-294],lw=5,color='#d38738')
    ax.plot([-826,-604],[-476,-476],color='#788c70',lw=2)
    ax.scatter([-720],[-330],c='#28667d',s=65)
    ax.annotate('载机参考高度 −330\n井内净宽 164 m',(-720,-330),(-815,-195),arrowprops={'arrowstyle':'->','color':'#28667d'},color='#28667d')
    ax.annotate('地表舱门 Y≈68',(-720,68),(-808,130),arrowprops={'arrowstyle':'->','color':'#c47b2e'},color='#a66624')
    ax.annotate('南侧进出门\nGeoFront 地面接机',(-637,-383),(-622,-315),arrowprops={'arrowstyle':'->','color':'#c47b2e'},color='#a66624')
    ax.text(-720,-535,'EVA 从一号通道到地下地表后接空运\n空运井中心 X=−1120，Z=−720',ha='center',va='center',fontsize=11)
    ax.set(xlim=(-841,-556),ylim=(-585,190),xlabel='Z / 方块（向右为南）',ylabel='Y / 高度',title='② 独立空运井剖面 · 真实土建标高')
    ax.grid(alpha=.13)
    fig.text(.5,.004,'施工图根据当前存档回读绘制；机电联锁、运行与游戏画面检查仍在进行。',ha='center',fontsize=11,color='#52616d')
    out=base/'design_reviews/installed-pits-controls-and-airshaft.png';out.parent.mkdir(exist_ok=True)
    fig.savefig(out,dpi=150);plt.close(fig);print(out)


if __name__=='__main__':main()
