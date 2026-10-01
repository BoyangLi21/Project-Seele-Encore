"""Offline 3D inspection of the complete measured semantic frame, not a photo.

Standalone canvas wire geometry with rotation/zoom and explicit evidence keys.
No game assets/reference bitmaps are included or modified. No world mutations.
"""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2"


def main():
    data=json.loads((OUT/"semantic_frame.json").read_text(encoding="utf8"))
    boxes=[];lines=[];labels=[]
    for b in data["bays"]:
        cx=b["bed"][0];name=f"EVA 0{b['variant']}"
        boxes += [{"lo":b["static_shell"][0],"hi":b["static_shell"][1],"colour":"#749aad","kind":"bay","label":name+" 湿舱（模板边界，非原作尺寸）"},
            {"lo":b["capsule_sweep_negative"][0],"hi":b["capsule_sweep_negative"][1],"colour":"#ffbf66","kind":"sweep","label":name+" 完整插栓/转姿负体积"},
            {"lo":[cx-15,-411,-51],"hi":[cx+15,81,-21],"colour":"#6fb4ba","kind":"shaft","label":name+" 原31×31发射净芯"},
            {"lo":[cx-20,-400,-267],"hi":[cx+20,-399,-213],"colour":"#d2777c","kind":"lcl","label":name+" LCL名义面，实际液位动态"}]
        foot=b["eva_feet"];labels += [{"p":foot,"text":name+" 原UUID脚点"},
            {"p":b["socket"]["origin"],"text":name+" 后颈S轴"},
            {"p":b["hatch_dock_world"],"text":name+" 停泊舱口"}]
        for rail_x in b["crane_rail_centres_x"]:
            boxes += [{"lo":[rail_x-.5,-376,-266],"hi":[rail_x+.5,-373,-215],"colour":"#84ba8b","kind":"crane","label":"双跑车轨 / 轮底 Y -373"}]
        for hanger_x in b["crane_fixed_support"]["outboard_hanger_x"]:
            for z in b["crane_fixed_support"]["support_z"]:
                boxes += [{"lo":[hanger_x-.5,-377,z-.5],"hi":[hanger_x+.5,-355,z+.5],"colour":"#719493","kind":"crane","label":"外置吊柱连接真实屋面 -355"}]
        lines += [{"points":[[cx+.5,-373,-266],[cx+.5,-373,-215]],"colour":"#84ba8b","kind":"crane","label":"跑车中轴 X=EVA轴 / Y -373"},
            {"points":[[cx-19,-395,-265],[cx-19,-395,-216]],"colour":"#acc2ab","kind":"crew","label":"承重侧廊 / feet -394"},
            {"points":[[cx+19,-395,-265],[cx+19,-395,-216]],"colour":"#acc2ab","kind":"crew","label":"承重侧廊 / feet -394"},
            {"points":[[cx,-443,-212],[cx,-411,-52],[cx,-411,-36],[cx,81,-36]],"colour":"#d5ca99","kind":"route","label":"现用户长坡/转移/发射线：SMALL WORLDS次级方向"},
            {"points":[q["crane_eye"] for q in b["capsule_route_samples"]],"colour":"#ffc48b","kind":"sweep","label":"canonical CRANE_ATTACHMENT_P 轨迹"}]
    boxes += [{"lo":[-35,-443,-212],"hi":[95,-357,-211],"colour":"#75a994","kind":"transfer","label":"共用三槽转移大厅低端剖面"},
              {"lo":[-35,-411,-55],"hi":[95,-325,-54],"colour":"#75a994","kind":"transfer","label":"共用三槽转移大厅高端剖面"}]
    payload=json.dumps({"boxes":boxes,"lines":lines,"labels":labels},ensure_ascii=False)
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>R44 整座机库三维语义校准</title>
<style>body{margin:0;background:#132127;color:#e0e8e8;font:15px system-ui}header{padding:18px 24px;background:#1d3038}h1{font-size:22px;margin:0 0 8px}p{margin:5px 0}main{display:flex;height:calc(100vh - 108px)}aside{width:315px;padding:18px;background:#1a2c34;overflow:auto}canvas{flex:1;min-width:0}label{display:block;margin:12px 0}button{margin:5px;padding:7px;border:1px solid #738e9a;background:#304c59;color:white;cursor:pointer}.note{font-size:13px;color:#b6c5c9;line-height:1.6}.key{padding:8px 0;border-top:1px solid #526a73}</style>
<header><h1>整座机库 · 单一世界坐标语义图</h1><p>原机体／湿舱／侧廊／插栓全转姿／吊机／载台／长坡／发射井。拖动旋转，滚轮缩放。</p></header>
<main><aside><button onclick="overview()">全设施</button><button onclick="cage()">三湿舱</button><button onclick="neck()">1号机后颈与吊机</button>
<div id="filters"></div><p class="note">本图是可检查的源码/测绘语义，未渲染Minecraft，不是原生验收照片。框仅表示明确边界或保护负体积，不能当作已经完成的新造型。</p>
<div class="key">TV原片：肩部座、后颈口、斜插轴、夹具、关盖顺序。缓存湿舱/拘束台图的集数未核实。</div>
<div class="key">SMALL WORLDS：现长坡和三线机械方向。仅作次级参考，不作为TV主体湿舱依据。</div>
<div class="key">显示阴影、材质与完整parts不在此图代验。骨架正常高度契约为60；真正模型parts bounds待本轮原生导出。</div>
<p class="note">参考来源、原UUID、全部29个设备NBT与121姿态样本见相邻semantic_frame.json/reference_ledger.json。</p><div id="hover" class="note"></div></aside><canvas id="scene"></canvas></main>
<script>const D=PAYLOAD;const C=document.querySelector('canvas'),ctx=C.getContext('2d');let az=.7,el=.42,zoom=1,target=[30,-180,-160],drag=false,old=[0,0];
const kinds={bay:'湿舱真实屋面 -355',sweep:'插栓/夹具保护体积',shaft:'31×31发射净芯',lcl:'动态LCL参考面',crane:'双轨与真实屋面吊挂',crew:'人员侧廊',transfer:'共用转移大厅剖面',route:'转移与发射同线'};const active=new Set(Object.keys(kinds));
for(const k in kinds){let l=document.createElement('label');l.innerHTML=`<input type="checkbox" checked data-key="${k}"> ${kinds[k]}`;document.querySelector('#filters').append(l)}
document.querySelector('#filters').onchange=e=>{if(e.target.checked)active.add(e.target.dataset.key);else active.delete(e.target.dataset.key);draw()};
function overview(){target=[30,-180,-160];zoom=1;az=.7;el=.42;draw()}function cage(){target=[30,-401,-240];zoom=3.3;az=.6;el=.30;draw()}function neck(){target=[30.5,-388,-230];zoom=8;az=-.70;el=.35;draw()}
function project(p){let x=p[0]-target[0],y=p[1]-target[1],z=p[2]-target[2],u=x*Math.cos(az)-z*Math.sin(az),v=x*Math.sin(az)+z*Math.cos(az),w=y*Math.cos(el)-v*Math.sin(el),depth=y*Math.sin(el)+v*Math.cos(el);let s=Math.min(C.width,C.height)/540*zoom;return[C.width*.5+u*s,C.height*.5-w*s,depth]}
function line(points,col,width=1){ctx.beginPath();points.forEach((p,i)=>{let a=project(p);if(!i)ctx.moveTo(a[0],a[1]);else ctx.lineTo(a[0],a[1])});ctx.strokeStyle=col;ctx.lineWidth=width;ctx.stroke()}
function box(b){let vs=[];for(let x of [b.lo[0],b.hi[0]])for(let y of [b.lo[1],b.hi[1]])for(let z of [b.lo[2],b.hi[2]])vs.push([x,y,z]);for(let i=0;i<8;i++)for(let mask of [1,2,4])if(i<(i^mask))line([vs[i],vs[i^mask]],b.colour,b.kind==='sweep'?1.4:.8)}
function draw(){C.width=C.clientWidth*devicePixelRatio;C.height=C.clientHeight*devicePixelRatio;ctx.fillStyle='#132127';ctx.fillRect(0,0,C.width,C.height);D.boxes.filter(b=>active.has(b.kind)).sort((a,b)=>project(a.lo)[2]-project(b.lo)[2]).forEach(box);D.lines.filter(l=>active.has(l.kind)).forEach(l=>line(l.points,l.colour,l.kind==='route'?2:1.3));ctx.font=`${12*devicePixelRatio}px system-ui`;for(const l of D.labels){let p=project(l.p);ctx.fillStyle='#e7f0e9';ctx.fillText(l.text,p[0]+5,p[1]-5)}line([[0,-467,-300],[70,-467,-300]],'#cfa1a1',2);line([[0,-467,-300],[0,-397,-300]],'#acd6a7',2);line([[0,-467,-300],[0,-467,-230]],'#a5bbd5',2);}
C.onpointerdown=e=>{drag=true;old=[e.clientX,e.clientY];C.setPointerCapture(e.pointerId)};C.onpointerup=()=>drag=false;C.onpointermove=e=>{if(drag){az+=(e.clientX-old[0])*.007;el=Math.max(-1.4,Math.min(1.4,el+(e.clientY-old[1])*.005));old=[e.clientX,e.clientY];draw()}};C.onwheel=e=>{e.preventDefault();zoom=Math.max(.25,Math.min(20,zoom*Math.exp(-e.deltaY*.001)));draw()};window.onresize=draw;draw();</script></html>'''.replace("PAYLOAD",payload)
    (OUT/"hangar_semantics_3d.html").write_text(html,encoding="utf8")
    print("Offline 3D semantic viewer, no world or reference bitmap edits")


if __name__=="__main__":main()
