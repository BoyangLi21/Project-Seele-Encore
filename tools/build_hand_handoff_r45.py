"""Curated local hand/model handoff, excluding worlds, credentials and caches."""
from pathlib import Path
import json,hashlib,shutil,subprocess,datetime

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r45/hand_handoff_20261002'
ASSET=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele'

PROMPT='''你接手 Project SEELE 的 EVA 手部专项重做。请实际制作并交回可编辑模型和可接入游戏的资产，不只给建议或概念图。

用户已否决当前方块状手掌，也指出动态手指、关节、武器持握和握拳有明显错误。必须从包内原始 EVA 模型的手部重新开始。04_REJECTED 中的方块/体素候选仅用于识别失败，不得继续作为造型基础。

范围与优先级
1. 初号机优先做完整质量样板，然后以同一标准处理零号机、二号机。UN 两台机暂不处理。
2. 保留原模型的手甲轮廓、指长比例、掌厚、拇指根位置和机型配色，参考 EVA TV 原版的机械与生物结合造型。不能把掌心凸包当外壳，也不能把手掌换成盒子或一团胶状物。允许为屈伸重做局部拓扑，但必须保持原始外观。
3. 重建左右手的 MCP/PIP/DIP、拇指对掌与腕部关系。指轴、父子关系、bind pose、inverse bind 和蒙皮权重必须一致；UV 接缝两侧同位置顶点的权重一致，避免裂缝和尖刺。手背装甲应保持硬质轮廓，关节软区承担变形。
4. 完成自然放松、张掌、完整握拳、抓握、刀正握/反握、步枪右手握柄与食指扳机、左手承托。检查站立、走跑摆臂、下蹲、趴伏支撑、站/蹲/趴持枪和动作过渡中的手部。手指不得反折、相互穿透或穿过武器；枪托、握柄和前护木接触要成立。
5. 骨架改动以手部为界。保留 forearm_l/r、wrist_l/r、hand_l/r 的兼容名称、整体身高和腕部挂点。不得为了握枪拉长前臂或移动整个上半身。确需改变骨骼名、父级、pivot 或 bind 时，提供完整旧→新映射及同步迁移脚本，不能只给一个外观正确但游戏不能用的 GLB。

先读 READ_ME_FIRST_zh.txt 和 05_CONTRACT/runtime_contract.json。01_ORIGINAL 是原始未修改 OBJ/MTL/贴图；02_CURRENT_GAME 是当前实际游戏资产，包含过去的手指分割改造；03_RECOVERED_ORIGINAL_HANDS 是本轮重新从原 OBJ 提取的手部表面与 UV，尚未通过动态美术验收。06_EDITABLE 是便于编辑的骨架与模型场景；其说明会明确哪些是原生复现、哪些只是交换格式。

交付要求
- 可编辑 .blend，骨架、权重、材质、贴图打包完整；另给 GLB 或 FBX 作为交换文件。
- 如能直接接入现有管线，给 mesh.json、必要的 geo.json、贴图、手部姿态数据和导出器。否则给可复现的转换脚本以及明确剩余接入步骤。
- 提交一张左右手各姿态对照图，以及正面、掌面、手背、侧面的静态近景。当前用户已要求停止录制视频，不要以新视频代替模型交付。
- 给出原始文件与输出的 SHA-256、骨骼映射、尺度/坐标约定、bind/inverse-bind、材质清单，以及逐姿态的关节连续性、穿模/自交检查结果。美术未通过的地方直接列出。
- 不把三角面数量、编译、权重和为1或“可以导入”当作造型和动作通过。先自己逐姿态观察，尤其检查拳头侧面、拇指压在手指外侧的位置和握枪时掌根的方向。

注意：包中攻击片段还存在脚部支撑/第二段衔接问题，由主工程继续处理。你的手部专项不能擅自改变战斗伤害、冷却、世界、NPC或任务进度。包中的资料是用户已有的本地项目素材，保留来源及许可记录。
'''

README='''Project SEELE — EVA 手部专项交接包 / R45 / 2026-10-02

请先把 PROMPT_给另一个模型.txt 发给接手模型，再上传本 ZIP。

目录
01_ORIGINAL：三台 EVA 原始 OBJ、MTL、全部同目录贴图，未修改。最重要的造型依据。
02_CURRENT_GAME：当前游戏完整身体、骨架、贴图和武器。手部已经历早期程序化分割，不能视为原始模型。
03_RECOVERED_ORIGINAL_HANDS：从原始 OBJ 恢复的手部候选，保留原始表面/UV。仅增加平面内采样细分；尚未完成动态与美术认可。
04_REJECTED：用户已否决的方块手候选、预览与历史失败片段。仅供对照。
05_CONTRACT：坐标/格式/骨架矩阵、动作样本、武器挂点资料及相关运行代码。
06_EDITABLE：提供可编辑的 Blender 场景和 GLB；详细范围见其中说明。不得用交换格式的默认蒙皮效果替代 Minecraft 原生检查。
07_TOOLS：本次整理与原始恢复脚本，以及必要的原工程导出/绑定算法参考。

当前状态
方块手 v1-v6 已被拒绝，三个替换资源已从活动资源目录移走。原始身体文件未因此覆盖。
原始 OBJ 确实仍在，三机各恢复左右手249个源三角面。重新细分后的中点落在原三角面内，未以方块、凸包或体素重建外形。
当前原始手的重新绑定仍是候选。不要把其中某个动作、绑定或渲染预览当作已经被用户认可。
现有普通攻击仍需重做：此前“脚全程锁地”与“持续实体位移”冲突，第二段一次留下约(-2.70,0,-6.64)格位移；本包保留相关证据供了解，但手部接手者不负责修改整套战斗。

技术入口
Minecraft Java1.20.1 / Forge47.4.10 / Java17 / GeckoLib。
游戏内三机站高约60格。骨架/mesh原坐标以16单位为1模型格，再由RENDER_SCALE=5进入世界。
JSON模型的顶点stride为8：[相对part pivot的x,y,z,u,v,nx,ny,nz]。详细坐标变换和四元数顺序见runtime_contract.json及原代码。
最高价值参考不是失败造型，而是01_ORIGINAL中的真实艺术家表面、02_CURRENT_GAME的实际骨架/武器和05_CONTRACT中的变换规则。

原始MTL提醒
原OBJ附带MTL里有 d 0 / illum 9，部分软件会把模型导入为透明。原文件保持原样；可编辑场景已明确使用不透明材质，不要因为透明导入误以为模型缺面。

本包没有存档、玩家数据、API密钥、账户配置或完整构建缓存。所有条目SHA-256见MANIFEST.json。手部专项完成后将整个结果包回传给主工程，由主工程统一接入与验证。
'''

def copy(src,dst):
    src=ROOT/src if not isinstance(src,Path)else src
    assert src.is_file(),src
    dst=OUT/dst;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'PROMPT_给另一个模型.txt').write_text(PROMPT,'utf8');(OUT/'READ_ME_FIRST_zh.txt').write_text(README,'utf8')
    for k,folder in [(0,'external-assets/work/unit00_audit/source_extracted'),(1,'external-assets/work/unit01/source-expanded'),(2,'external-assets/work/unit02_audit/source_extracted')]:
        for f in (ROOT/folder).iterdir():
            if f.is_file():copy(f,Path('01_ORIGINAL')/f'unit0{k}'/f.name)
        for sub,pattern in [('geo',f'eva_unit0{k}.geo.json'),('mesh',f'eva_unit0{k}.mesh.json')]:copy(ASSET/sub/pattern,Path('02_CURRENT_GAME/assets/projectseele')/sub/pattern)
        for f in (ASSET/'textures/entity').glob(f'eva_unit0{k}*.png'):copy(f,Path('02_CURRENT_GAME/assets/projectseele/textures/entity')/f.name)
        for f in (ROOT/f'artifacts/rebuild_r45/models/hands/original_source_v1/unit0{k}').iterdir():copy(f,Path('03_RECOVERED_ORIGINAL_HANDS')/f'unit0{k}'/f.name)
        rejected=ROOT/f'artifacts/rebuild_r45/models/hands/unit0{k}_candidate_v6'
        for f in rejected.iterdir():
            if f.suffix in ['.json','.png']:copy(f,Path('04_REJECTED')/f'unit0{k}_v6'/f.name)
    weapons=['eva_pallet_smg','progressive_knife','positron_cannon','longinus_lance','eva02_knife']
    for n in weapons:
        copy(ASSET/'mesh'/(n+'.mesh.json'),Path('02_CURRENT_GAME/assets/projectseele/mesh')/(n+'.mesh.json'))
        for f in (ASSET/'textures/entity').glob(n+'*.png'):copy(f,Path('02_CURRENT_GAME/assets/projectseele/textures/entity')/f.name)
    base=ROOT/'artifacts/rebuild_r45/motion/pose_codec_after/native/normals_1_clear/20261002_090907/resources'
    copy(base/'eva_body_r43.json',Path('05_CONTRACT/production_pose_data/eva_body_r43.json'))
    for f in (base/'gameplay').glob('eva_gameplay_r43_*.json'):
        if int(f.stem.rsplit('_',1)[1])<3:copy(f,Path('05_CONTRACT/production_pose_data')/f.name)
    java=['entity/EvaHandsR41.java','entity/EvaOriginalHandsR45.java','entity/EvaBodyPose.java','entity/EvaGameplayMotionR32.java',
          'entity/EvaRifleKinematics.java','entity/EvaRifleClearance.java','entity/EvaScale.java','client/render/EvaHandPoseR28.java',
          'client/render/EvaRifleContactRig.java','client/render/EvaRifleProneBody.java','client/render/EvaRifleMocap.java',
          'client/render/EvaRigTransforms.java','client/render/LocalTriangleMeshLayer.java','client/render/EvaUnit01Renderer.java',
          'client/render/EvaPoseGraph.java','client/render/EvaPoseTransition.java','util/QuaternionChannelsR45.java']
    for n in java:copy('src/main/java/com/projectseele/'+n,Path('05_CONTRACT/runtime_code')/n)
    tools=['recover_original_eva_hands_r45.py','make_tiger_unit01_pack.py','make_tiger_eva_variants_pack.py','eva_finger_axis_repair.py','author_articulation_r42.py','build_hand_handoff_r45.py']
    for n in tools:copy('tools/'+n,Path('07_TOOLS')/n)
    for n in ['normal_contact.mp4','normal_empty.mp4']:
        copy('artifacts/rebuild_r45/quick_review/ordinary_v6/'+n,Path('04_REJECTED/existing_failure_recordings')/n)
    copy('artifacts/rebuild_r45/motion/root_authority_v1/first_native_readback.json',Path('05_CONTRACT/current_attack_limitations.json'))
    (OUT/'SOURCES_LICENSES.txt').write_text('Original EVA models: Tigerar1, Sketchfab, CC BY-SA; existing local project sources. Preserve original attribution/licence when sharing derivatives.\nUnit01: https://sketchfab.com/3d-models/evangelion-unit-01-9fddeb0a7143436598c805dab2f147bf\nUnit00: https://sketchfab.com/3d-models/evangelion-unit-00-abe48f0c88914d66b7a5c916704767b3\nUnit02: https://sketchfab.com/3d-models/evangelion-unit-02-a8731145a84f4e63b0fbc51f4f5948da\nGame code: Project SEELE, see source repository licence. Weapon/source notes are copied separately when available; no new redistribution permission is asserted.\n','utf8')
    for f in [ROOT/'LICENSE',ROOT/'docs/ASSETS.md',ASSET.parent.parent/'_SOURCE.txt']:
        if f.is_file():copy(f,Path('05_CONTRACT/source_credits')/f.name)
    contract=dict(schema='projectseele.hand-handoff.r45',runtime={'minecraft':'1.20.1','forge':'47.4.10','java':17,'render_scale':5,'authored_units_per_model_block':16},
        mesh={'stride':8,'channels':['x','y','z','u','v','nx','ny','nz'],'position':'part-relative authored units; add part.pivot, reflect X, divide16; then bone/model/world transforms','normals':'reflect X then the actual normal transforms','hand_candidate_skin':'dual-quaternion, per-part jointSkins.influences, explicit inverseBindColumnMajor'},
        rig={'pivot':'authored XYZ; native pivot=(-x,y,z)/16','geometry_rotation':'degrees; native Rz(z)*Ry(-y)*Rx(-x)','native_matrix':'parent * T(native_offset) * T(pivot) * R * T(-pivot)','body_snapshot_quaternion':'rotation_wxyz stores authored [w,x,y,z]; native quaternion xyzw=(-x,-y,z,w)','snapshot_root':'root_m *112 then reflectX/divide16','snapshot_other_positions':'bone_position_xyz then reflectX/divide16'},
        scope=['EVA00','EVA01','EVA02'],UN='paused',original_hand_recovery='candidate; source surface/UV preserved, dynamic/art approval pending',
        required_returns=['editable blend','GLB or FBX','meshes/materials/textures','rig mapping+bind/inverse-bind','grip and fist poses','exporter or game JSON','static multiview pose review','known limitations'],
        no_new_video_recording=True)
    (OUT/'05_CONTRACT/runtime_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
    print('Prepared handoff inputs',OUT)

if __name__=='__main__':main()
