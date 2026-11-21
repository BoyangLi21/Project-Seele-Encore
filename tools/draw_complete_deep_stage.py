"""Stage diagram bound to the installed native lift groups and migration receipt."""
from pathlib import Path
import json
import nbtlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Polygon

BASE=Path('D:/eva/artifacts/map_complete_20261013')
receipt=json.loads((BASE/'deep_components_384/APPLIED.json').read_text('utf8'))
assert receipt['world_written'] and receipt['complete_source_and_target_exact_readback']
groups=nbtlib.load(BASE/'WORLD/dimensions/projectseele/geofront/data/capabilities.dat')['data']['movingelevators:elevator_groups']
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':11,'axes.unicode_minus':False})
fig,axes=plt.subplots(1,2,figsize=(16,10),gridspec_kw={'width_ratios':[1,1.45]},facecolor='#f5f7fa')
ax=axes[0]
for x,key,title,col in ((0,'6;253','原主梯','#277fa7'),(1,'63;302','原东梯','#7852a7'),(2,'31;321','办公室小梯','#588165'),(3,'86;366','机库原内部梯','#ba7e31')):
    floors=list(map(int,groups[key]['group']['floors']))
    ax.plot([x,x],[min(floors),max(floors)],color=col,lw=4)
    for f in floors:ax.plot(x,f,'o',color=col,ms=6)
    ax.text(x,-382,title,color=col,ha='center',fontsize=11)
    shown=[min(floors),max(floors)]
    if key=='6;253':shown=[-1230,-987,-541,-502]
    for f in shown:ax.text(x+.07,f,str(f),va='center',fontsize=10,color=col)
ax.axhspan(-568,-410,color='#dee7ec',alpha=.5)
ax.axhline(-987,color='#397d78',ls='--',lw=1)
ax.text(1.5,-966,'两部主梯都到机库观察廊 −987',ha='center',color='#397d78',fontsize=10)
ax.set_ylim(-1344,-340);ax.set_xlim(-.4,3.65);ax.set_xticks([]);ax.set_ylabel('Y / m（真实原生停层高度）');ax.grid(axis='y',alpha=.2)
ax.set_title('A  原生电梯组：已安装并回读',loc='left',pad=20)
ax=axes[1]
ax.add_patch(Polygon([[0,-563],[120,-384],[240,-563]],facecolor='#687581',alpha=.5,edgecolor='#354554',lw=2))
ax.text(120,-498,'金字塔／总部／办公室\n保留已确认的沉降高度',ha='center',va='center',color='#243845')
ax.axhline(-473,color='#4789a0',lw=1);ax.text(268,-473,'人工湖水线 −473',va='center',fontsize=10,color='#4789a0')
ax.add_patch(Rectangle((0,-1133),240,203,facecolor='#c8dee1',edgecolor='#437981',lw=2))
ax.text(120,-961,'原机库 + 斜轨 + 三组发射区',ha='center',fontsize=11)
for f,label,label_y in ((-987,'观察廊',-980),(-1014,'登机层',-1010),(-1030,'发射脚位',-1040),(-1062,'机库脚位',-1070),(-1088,'整备维护层',-1100)):
    ax.hlines(f,0,240,color='#72999f',lw=.8)
    ax.plot([240,250],[f,label_y],color='#72999f',lw=.8)
    ax.text(252,label_y,f'{label} {f}',va='center',fontsize=10)
ax.add_patch(Rectangle((-15,-1311),270,131,facecolor='#dbd7e5',edgecolor='#74628c',lw=2))
ax.text(120,-1265,'完整莉莉丝／终极教条层\n原建筑、原实体整体下移',ha='center',va='center',color='#5d4a75')
ax.hlines(-1230,-15,255,color='#74628c',lw=1);ax.text(266,-1230,'原主梯停层 −1230',va='center',fontsize=10)
ax.axhline(-1344,color='#5a6068',lw=3);ax.text(268,-1334,'新维度底部 −1344',fontsize=10,color='#5a6068')
ax.plot([50,50],[-502,-1230],color='#277fa7',lw=3)
ax.plot([190,190],[-457,-987],color='#7852a7',lw=3)
ax.annotate('整件再下移 384 m\n内部相对布局保留',(90,-1120),(275,-768),arrowprops={'arrowstyle':'->','color':'#526774'},color='#526774',ha='center')
ax.set_ylim(-1344,-340);ax.set_xlim(-35,410);ax.set_xticks([]);ax.set_ylabel('Y / m');ax.grid(axis='y',alpha=.2)
ax.set_title('B  施工后实际高度关系（横向仅示意）',loc='left',pad=20)
fig.suptitle('阶段完成 · 地下设施整体下移 + 两部原主梯延长',fontsize=20,y=.98)
fig.text(.06,.052,'回读：678 个原实体身份保留，17 个原实体成员与 1 名保存玩家随设施平移；28 件设备完整 NBT 校验。',fontsize=11,color='#354554')
fig.text(.06,.021,'本图依据当前施工存档；几何／存档迁移已完成。实际乘梯、发射净空、照明及游戏画面验收仍待后续原生验证。',fontsize=10,color='#95602d')
fig.tight_layout(rect=[.02,.085,.98,.94]);fig.savefig(BASE/'design_reviews/deep-components-and-two-lifts-installed.png',dpi=140);plt.close(fig)
