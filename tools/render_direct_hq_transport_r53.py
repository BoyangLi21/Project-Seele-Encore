"""Draw current native rail centres and their actual descent profiles."""
from pathlib import Path
import argparse,json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.font_manager import FontProperties


def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument("--candidate-directory",type=Path,required=True);ap.add_argument("--old-directory",type=Path,required=True);ap.add_argument("--root-plan",type=Path,required=True);a=ap.parse_args();base=a.candidate_directory.resolve()
    read=lambda p:json.loads(p.read_text("utf8"));candidate=read(base/"CANDIDATE.json");curves={r["id"]:r for r in read(base/"NATIVE_GEOMETRY.json")};old=read(a.old_directory/"CANDIDATE.json");oldcurves={r["id"]:r for r in read(a.old_directory/"NATIVE_GEOMETRY.json")}
    font=FontProperties(fname="C:/Windows/Fonts/msyh.ttc");plt.rcParams["font.family"]=font.get_name();plt.rcParams["axes.unicode_minus"]=False
    fig,(plan,profile)=plt.subplots(1,2,figsize=(15,8),gridspec_kw={"width_ratios":[1.2,1]});lake=read(a.root_plan)["reservoir_candidate"]
    x0,x1=lake["x_bounds"];z0,z1=lake["z_bounds"];plan.add_patch(Rectangle((x0,z0),x1-x0,z1-z0,facecolor="#dceeff",edgecolor="#5994c6",lw=1.5));plan.text(x0+10,z0+35,"同向正方形湖",fontsize=10,color="#376891")
    plan.add_patch(Rectangle((213,453),75,94,facecolor="#f9e8de",edgecolor="#b46746",lw=1.2));plan.text(248,526,"Sigma\n完整保留",fontsize=9,ha="center",color="#924c30")
    colors={"original_6":"#276f9f","original_8":"#6ca2c4","original_2":"#cd7825","original_3":"#e2a250","original_4":"#6860a9","original_5":"#9b93c9"};rows=[]
    for group,chain in candidate["routes"].items():
        color=colors[group];parts=[np.asarray(curves[n]["points"]) for n in chain];p=np.concatenate(parts);oldp=np.concatenate([np.asarray(oldcurves[n]["points"]) for n in old["routes"][group]])
        plan.plot(oldp[:,0],oldp[:,2],color="#b7bcc2",lw=.8,alpha=.65);plan.plot(p[:,0],p[:,2],color=color,lw=2)
        distance=np.concatenate(([0],np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))));profile.plot(distance,p[:,1],color=color,lw=1.7,label=group.replace("original_","通道 "))
        rows.append(dict(original=group,old_metres=sum(oldcurves[n]["native_length"] for n in old["routes"][group]),metres=sum(curves[n]["native_length"] for n in chain)))
    for x,y,z,label in ((30,-560,505,"HQ 唯一地下站"),(-330,-467,785,"原西站 / 地表"),(310,-467,560,"原研究站 / 地表"),(300,-467,165,"原东站 / 地表")):
        plan.scatter([x],[z],s=40,c="#242a35",zorder=4);plan.annotate(label,(x,z),xytext=(8,-16),textcoords="offset points",fontsize=10)
    plan.annotate("北",xy=(-525,260),xytext=(-525,340),arrowprops=dict(arrowstyle="->",color="#263342"),ha="center");plan.set_aspect("equal");plan.invert_yaxis();plan.grid(alpha=.16);plan.set(xlabel="X / m（向东）",ylabel="Z / m（向南）",title="灰线整圈及旧通道全部退役；彩线为当前原生曲线")
    profile.axhline(-467,color="#677b4c",lw=1,ls="--",label="原地表铁路脚位 -467");profile.axhline(-560,color="#456d81",lw=1,ls=":");profile.set(xlabel="沿实际曲线距离 / m",ylabel="铁路脚位 Y / m",title="仅 HQ 下行 / 上行；原平台平喉保持");profile.grid(alpha=.2);profile.legend(fontsize=9,loc="lower right")
    fig.suptitle("当前交通设计：长段 160 km/h · 站台平喉 40 km/h · 三个独立原生闭塞",fontsize=15);fig.text(.52,.03,"40 原列车与原站台 / 原车库 / 原线路身份保留\n湖接口 6 面密封 + 实际车体 / 转向架 17 格有限清让\n静态设计证据；实际载人运行与画面由本轮 native 检查验证",fontsize=10,color="#3e4957")
    fig.tight_layout(rect=(0,.11,1,.94));fig.savefig(base/"CURRENT_DIRECT_HQ_DESIGN.png",dpi=150);plt.close(fig);(base/"ACTUAL_NATIVE_ROUTE_DISTANCES.json").write_text(json.dumps(rows,indent=2)+"\n","utf8");print(base/"CURRENT_DIRECT_HQ_DESIGN.png")


if __name__=="__main__":main()
