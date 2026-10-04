# 素材登记簿

> R24 依赖补全：载具手册使用 [Patchouli 1.20.1-85 Forge](https://modrinth.com/mod/patchouli/version/94dtOLgZ)，原作者 VazkiiMods，原项目标示 CC-BY-NC-SA-3.0。只从官方地址下载并校验固定 SHA-512，不把第三方 JAR 改标 MIT 或提交到源码。载具手册文字／图片仍属于 Superb Warfare 原资源；本项目补齐加载依赖和测试，没有宣称重写原手册。

> 合规基线：khara 二创指引（非商业、零官方素材）。本文件登记**所有**非代码资产的来源。
> 任何新素材入库前先在这里登记。

## 音效（原创合成与单列的语音生成）

R10 新增的 15 个 `eva_*.ogg` 由 `tools/build_eva_audio_r10.py` 固定种子合成，无录音采样。用途包括落足、落地、关节、挥击、实体命中、刀切、装甲、核心、AT 侵蚀/撕裂、咆哮和驾驶反馈。波形参数、响度与 SHA-256 记录在 `artifacts/first_battle_world_r10/audio/manifest.json`。

R10 机柜、档案柜、监护器、工作椅和战术屏由 `build_room_equipment_r10.py`、`build_briefing_furniture_r10.py` 原创绘制/建模；战术地图使用本机现有道路规划，未使用原片图像。首战动作由 `author_first_battle_r10.py` 编制，不是影视动作数据提取。

R10 负责人授权下载的九份 Battle Orchestra 模型与纹理仅放在 `external-assets/incoming/angels_r10` 和本机资源包中；不提交、不包含在公开构建中。模型获取与实机状态见 [R10 记录](WORLD_MOTION_R10.md) 和 [使徒来源清单](ANGEL_MODEL_ACQUISITION.md)。

| 文件 | 用途 | 来源 |
|---|---|---|
| `sounds/alarm.ogg` | 使徒来袭循环警报 | 原创：`tools/gen_sounds.ps1` 数学合成（正弦+奇次谐波双音） |
| `sounds/beam_charge.ogg` | 光束蓄力 | 同上（指数上扫+颤音） |
| `sounds/beam_fire.ogg` | 光束发射 | 同上（锯齿下坠+噪声） |
| `sounds/cross_explosion.ogg` | 十字爆炸 | 同上（低通噪声+低频轰鸣） |
| `sounds/crystal_hit.ogg` | 拉米尔受击 | 同上（高频正弦簇） |
| `sounds/crystal_break.ogg` | 拉米尔死亡 | 同上（下行玻璃音簇+噪声） |
| `sounds/drill.ogg` | 二阶段钻击 | 同上（锯齿嗡鸣+低通噪声） |
| `sounds/ramiel_hum.ogg` | 拉米尔环境音 | 同上（110/164.6Hz 拍频） |
| `sounds/rifle_fire.ogg` | EVA 帕雷特步枪 | 原创合成：机械枪机、爆音噪声与低频尾响，不含影视或现实枪械采样 |

全部由脚本以固定随机种子生成，可复现；无采样、无原作旋律。许可随仓库 MIT。

## 贴图（各项来源分别登记）

| 文件 | 规格 | 来源 |
|---|---|---|
| `textures/item/positron_rifle.png` | 32×32 | 原创：`tools/gen_textures.ps1` 程序绘制 |
| `textures/item/core_fragment.png` | 32×32 | 同上 |
| `textures/entity/ramiel.png` | 32×32 | 同上（渐变+棱面纹理） |

欢迎社区高清重绘（资源包可直接覆盖）。

## 本地测试资产（不在仓库内，永不提交）

| 资产 | 来源 | 状态 |
|---|---|---|
| NERV HQ 1:1 世界存档（`run/saves/NERV_HQ_1to1_Poodcie`） | PMC 项目 `nerv-hq`，作者 Poodcie，官方镜像下载 | 仅本地测试。**如需随 mod 公开发布，必须先取得作者授权**（ROADMAP §9 行动清单） |
| SmOd EVA/使徒本地参考包 | SmOd `EVANGELION: END ADDON V1.0`（Planet Minecraft / Bedrock addon），作者 SmOd774YT，未列开放许可证 | 旧版 EVA 转换结果已退出当前机体管线；仍作为使徒和造型参考保留。仅本地测试，**公开使用前必须取得作者许可** |
| 当前 EVA-00/01/02/量产机本机身体资源 | Tigerar1 的四个 Sketchfab 模型（逐项链接见下表），CC BY-SA | `make_tiger_unit01_pack.py` 与 `make_tiger_eva_variants_pack.py` 生成到忽略目录；这是当前测试身体来源，转换美术不属于 MIT 代码许可，正式发行前必须完成完整署名与 ShareAlike 审核 |
| 初号机/零号机通用高振动粒子刀 | [Udon-San `Progressive Knife`](https://sketchfab.com/3d-models/progressive-knife-e104dbec8c904f9b840c29c4a7d5d770)，CC Attribution | 用户下载的 FBX/贴图；3,766 三角面；由 `make_downloaded_eva_accessories_pack.py` 转换到本机包并以反握插槽使用。源文件与转换 mesh 均不入库 |
| 二号机专用粒子刀、双头刃剑与适配插入栓 | [Rainbow_Slakot `EVA-02 (rebuild version, not rigged)`](https://sketchfab.com/3d-models/eva-02-rebuild-version-not-rigged-4d715f56f7aa4f4cbed9703bc02a7171)，CC Attribution | **身体 mesh 明确排除**，只提取 1,032 三角刀、2,224 三角专武和插入栓模块；插入栓被缩放/换轴并补原创舱门以适配 Tiger 背部入口。仅本机评估，公开发行仍需署名及整体 EVA 二创合规复核 |
| Rei Chikita / EUD 本地参考文件 | 用户手动下载 | 已被 `.gitignore` 的 `/*.jar` 规则拦截，永不提交。Rei Chikita 只作为 SmOd 缺失时的本机 fallback/参考；EUD 1.1.0 清单标注 **CC BY-NC 4.0**，含驾驶服、LCL、三枪与 EVA 遗迹结构，但无可驾驶 EVA 模型；公开改用前仍联系作者确认署名方式 |
| 朗基努斯之枪本机附件（`tools/make_downloaded_eva_accessories_pack.py`） | EUD 1.1.0 的 Blockbench 方块模型与贴图 | 转换为 384 三角、独立 `longinus_lance` 附件，初号机/零号机使用双手前后握持；生成到本机资源包。公开发行前确认 EUD 作者署名，并遵守其清单所列 CC BY-NC 4.0 |
| 零号机本机头部模型（`tools/make_eud_eva00_pack.py`） | EUD 1.1.0 的 `eva00structure.nbt` 零号机头部雕塑 | 与 Project SEELE 原创可动画身体组合，仅本机测试；公开发行前确认 EUD 作者署名，并遵守 CC BY-NC 4.0 |
| EVA-X / GeoFront 球体世界（用户下载的 `EVA.rar`） | Bilibili 分享存档；当前缺少可核验作者与再发布许可 | `prepare_local_map_assets.py` 只把该存档作为测量参考；新的 `SEELE_TOKYO3_REBUILT` 使用普通噪声地表与原创深埋球体。源文件、转换结构和存档全部 gitignored，作者身份与许可确认前绝不发布 |
| `Nerv Comand Module` 世界 | Planet Minecraft `nerv-comand-module`，用户手动下载；作者/许可信息待登记 | 本机转换为 NERV 指挥区并叠加原创四屏实时遥测；不进入 jar。发布前必须补齐项目链接、作者署名与明确授权 |
| `tokyo-3-type-skyscrapper1-converted.schem` | 用户手动下载的 Tokyo-3 高楼 schematic；作者/许可信息待登记 | 本机在东京-3 战区放置三座实例；结构和拼接存档均不提交。未获得授权时发布版使用原创回退楼群 |

`run/` 已 gitignore，上表资产不会进入版本库与发行物。

## EVA 模型升级候选（2026-07-07 调研，尚未采用）

| 候选 | 技术情况 | 授权/下一步 |
|---|---|---|
| SmOd `EVANGELION: END ADDON V1.0` | Bedrock 1.21 addon，含 Unit-01/02 与动画；Bedrock geometry 可转换为 GeckoLib；目前仅保留为参考，不再覆盖 Tiger 身体 | Planet Minecraft 未列开放许可证；必须先联系 SmOd 获得移植与再发布许可 |
| BROWNCOAT `EVANGELION UNIT ONE` | Sketchfab 25.7k 三角面、未绑定骨骼；细节高但不能直接用作 GeckoLib 方块模型 | 页面标注 CC BY；仍需重新拓扑、绑定和制作 Minecraft 贴图，并登记署名 |
| PurpleGreenCream `EVA 01 (2022)` | 原生 Blockbench 长方体模型，最接近本项目技术路线 | 页面标注 CC BY-NC-SA；需联系作者索取源文件并确认 mod 再发布方式 |
| EUD 1.1.0 Forge 1.20.1 | 已下载官方文件并逐项审计；实际 jar 只有驾驶服、长枪、NPC 与 EVA 遗迹结构，没有页面所称的 EVA 实体模型/动画 | 不作为 EVA 模型来源；文件仅留在 `run/third_party/` |
| Tigerar1 [`Evangelion Unit-00`](https://sketchfab.com/3d-models/evangelion-unit-00-abe48f0c88914d66b7a5c916704767b3) | Sketchfab，3.7k 三角面，适合作为低多边形零号机重拓扑参考 | 已由用户下载并进入本机评估管线；CC BY-SA 4.0，发布时必须完整署名并以兼容方式共享改编模型 |
| Tigerar1 [`Mass Production Evangelion`](https://sketchfab.com/3d-models/mass-production-evangelion-a483209197814af99fc536b396813698) | Sketchfab，约 5k 三角面，比方块回退模型更接近 EoE 轮廓 | 已由用户下载并进入本机评估管线；CC BY-SA 4.0，正式打包仍需完成署名/ShareAlike 审核 |
| solodovnykov [`Sachiel - Evangelion`](https://sketchfab.com/3d-models/sachiel-evangelion-3c212c7ce6ac4284a8b718078bc6fc0f) | Sketchfab，524.7k 三角面/UDIM，细节很高但必须大幅减面 | CC BY 4.0；下载要求登录，作为后续高模烘焙候选，不直接塞入 Minecraft |

SmOd addon 已由用户下载为仓库根目录 `evaaddon1-0.zip`（被 `/*.zip` 忽略）。`tools/make_smod_model_pack.py` 可生成仅限本机测试的 Unit-01/02 GeckoLib 覆盖包；生成物和源素材均不得提交或发布。

## Local Tigerar1 Unit-01 evaluation (2026-07-12)

- Source: [Tigerar1 Evangelion Unit-01](https://sketchfab.com/3d-models/evangelion-unit-01-9fddeb0a7143436598c805dab2f147bf), user-downloaded OBJ and texture.
- Page licence: CC BY-SA; the converted art remains CC BY-SA and is not part of the MIT code licence.
- Local archive: `external-assets/incoming/evangelion-unit-01.zip` (Git-ignored).
- Converter: `tools/make_tiger_unit01_pack.py`; output is written only under the ignored `run/resourcepacks/eva_real_model/` tree.
- Current result: 3,789 source vertices / 4,226 triangles, mapped to 27 runtime mesh parts after the real finger and ankle splits. The `foot_l` / `foot_r` split preserves the source triangle count; non-mesh attachment bones are additional to the body contract. This is a rigid visual prototype, not release-approved art, and the poses still require in-game human review.

## Local Tigerar1 EVA variant evaluation (2026-07-12)

All archives and generated geometry below are Git-ignored. The converter code
may be distributed with Project SEELE, but the converted art remains under its
source licence and is outside the repository's MIT code licence.

| Target | Source and page licence | Local conversion state |
|---|---|---|
| EVA Unit-00 | [Tigerar1 Evangelion Unit-00](https://sketchfab.com/3d-models/evangelion-unit-00-abe48f0c88914d66b7a5c916704767b3), CC BY-SA | Downloaded OBJ; 3,120 vertices / 3,692 triangles; 27-part local pack generated. The finger/ankle splits preserve all triangles and pass offline contract validation; seams and animation feel remain blocked on an in-game visual pass. |
| EVA Unit-02 | [Tigerar1 Evangelion Unit-02](https://sketchfab.com/3d-models/evangelion-unit-02-a8731145a84f4e63b0fbc51f4f5948da), CC BY-SA | Downloaded OBJ; 3,384 vertices / 3,952 triangles; 27-part local pack generated. The finger/ankle splits preserve all triangles and pass offline contract validation; seams and animation feel remain blocked on an in-game visual pass. |
| Mass Production EVA | [Tigerar1 Mass Production Evangelion](https://sketchfab.com/3d-models/mass-production-evangelion-a483209197814af99fc536b396813698), CC BY-SA | Downloaded OBJ; 3,392 body + 1,509 wing triangles imported. The 440-triangle weapon lying at world origin is excluded. A 16-bone local rig carries gameplay `idle_1` / `move` / `attack`, explicit ritual, held Visual-Lab attack and folded revive animations. EUD's local replica lance is now rendered by the offline matrix; the ready pose removed a detected 26-pixel idle penetration. The five-state runtime matrix remains pending. |
| Positron rifle | [Kantrophe Positron Rifle](https://sketchfab.com/3d-models/positron-rifle-neon-genesis-evangelion-523e4d5b344543aa97b21e885f9dc064), CC Attribution | Download contains Blender 3.04 source and 4K PBR textures only. Portable Blender 3.6 exported and decimated 56,614 source triangles to 20,381; the 5,990-triangle ground cradles are excluded, leaving a 14,391-triangle local cannon. The axis/pivot correction passed an in-game Tigerar1 attachment capture; the two-hand support pose remains under Visual Lab review. |
| Pallet Rifle | [Oni Anniversary Edition community conversion](https://wiki.oni2.net/AE_talk%3ANew_weapons), provenance/redistribution permission not yet confirmed | Exact TV-style 167-vertex / 292-triangle OBJ and 1024x512 BMP are installed only under ignored external-assets/. tools/make_downloaded_pallet_rifle_pack.py is fingerprint-locked to that pair and emits a local-only runtime derivative. It must not ship until explicit author/licensor approval is recorded; the original 240-triangle MIT procedural rifle remains the distributable fallback. |
| Ultraman private avatar | User-supplied `ultraman-rig-updated.zip`; no licence or author metadata included | Local/private testing only. FBX contains a 54-bone Character Creator rig and 20,565 exported triangles. `tools/make_ultraman_avatar_pack.py` emits an ignored rigid-bone runtime derivative. Never publish or redistribute the source or derivative without provenance and permission. |


## Local Kiki260100 Lilith evaluation (2026-07-19)

- Source: [Kiki260100 `Lilith - Evangelion`](https://sketchfab.com/3d-models/lilith-evangelion-8203459ac3dc48e18bad7b2a6b46995f), downloaded manually by the user.
- Local archive: `external-assets/incoming/lilith-kiki260100.zip.zip`; GLB SHA-256 `6693b5ca325d6fa5c355152962e75cf50162266320a4519aab3130c2ecfef06c`.
- The downloaded archive contains only the GLB and two textures. No licence
  document is bundled, so this project treats the model as local evaluation
  material and will obtain explicit author approval before any release.
- `tools/make_lilith_model_pack.py` converts the GLB into six material layers
  inside the Git-ignored `run/resourcepacks/eva_real_model/` pack: body 11,814,
  eyes 1,540, face 322, mask 1,082, nails 448 and sealing spear 4,524
  triangles. The source cross material is deliberately excluded; Project
  SEELE retains its own pure-red block crucifix.
- Runtime height is 32 blocks and wrist span is approximately 42 blocks. The
  source body's front/side visual audit confirms the cross remains behind the
  body and the sealing spear extends toward the observation gallery.
- Converter, entity integration and clean-room fallback geometry may ship as
  code. The generated Kiki mesh/textures and source archive must never be
  committed or redistributed without permission.
`tools/make_tiger_eva_variants_pack.py` writes each EVA target incrementally
and never clears the active resource pack. During development its `--output`
must point at an ignored staging pack until the matching renderer and Visual
Lab batch have passed. `tools/render_tiger_variant_rig_preview.py` provides
deterministic four-view identity/stress checks without starting Minecraft.

## Local Entry Plug evaluation (2026-07-26)

- Exterior: [Crymsin `Entry Plug (Evangelion)`](https://www.thingiverse.com/thing:2501188),
  Thingiverse item 2501188, CC BY. The user-downloaded OBJ has 250,554 source
  triangles and five material groups.
- Cockpit reference: [DONW999 `Neo Genesis Evangelion Entry Plug Pilot Seat -
  The Soul Throne`](https://www.thingiverse.com/thing:4961673), Thingiverse
  item 4961673, CC BY. Its downloaded ZIP contains only `Stand.stl`, decals and
  render images; it does not contain the displayed chair/control meshes.
- `tools/make_entry_plug_model.py` cuts a physical hatch into the Crymsin
  pressure shell, decimates each material independently, then adds an original
  Project SEELE Soul-Throne-style seat, restraints, foot rests and two
  induction levers guided by the bundled DONW999 renders.
- The generated local contract is 14 x 58 x 14 model pixels, 11,670 triangles
  and three animated parts. It is written only to the ignored
  `run/resourcepacks/eva_real_model/` pack. Both source ZIPs and the derivative
  mesh remain local-only until release attribution and the wider EVA
  fan-work compliance review are complete.

## Open humanoid motion sources and animation references (2026-08-24)

| Asset | Licence and source | Project SEELE use |
|---|---|---|
| Quaternius Universal Animation Library Standard | [Official page](https://quaternius.com/packs/universalanimationlibrary.html), bundled `License.txt`: CC0 1.0; downloaded ZIP SHA-256 `CC73FC4E495B82958207316596317A3F40B9FA38065BDE1027937452DA537724` | 43 source actions were inventoried. Idle, walk, formal walk, jog, sprint, crouch, jump, punch, sword and firearm poses are clean-room retarget inputs. The raw ZIP/GLB remains under ignored `external-assets/`; the derived quaternion motion database may ship under the repository licence because the source is dedicated to the public domain. |
| Quaternius Universal Animation Library 2 Standard | [Official itch.io page](https://quaternius.itch.io/universal-animation-library-2), bundled `License.txt`: CC0 1.0; downloaded ZIP SHA-256 `4008EA208A604773A2B2177D965F0F5D3195498B5BF838C3F5785D68E95F2A68` | Adds hook punches, multi-stage sword attacks, dash, slide and ninja-jump references. Raw files remain ignored; selected derived clips are merged into `assets/projectseele/motion/eva_humanoid_v2.json`. |
| CMU Graphics Lab Motion Capture Database, subjects 02, 16, 22, 23, 54, 79, 80, 111, 120, 136 and 144 | [Official database](https://mocap.cs.cmu.edu/). The official FAQ explicitly permits copying, modification and redistribution without permission. ASF SHA-256: subject 02 `C9F5FF45B4437B279F58B95DACF017AFD3135373096274DF69436A9354D796CF`, subject 16 `2323F876564610F84BFBEC9B90B8EBFFB57515673B7F4A45B0FB0849AF465BDB`, subject 111 `8FE67A2163F1F70ED985E34ABE0E3FF4AF7F5DA76F2F3C178D59759CB18BBA16`. Phase-G review BVH SHA-256: `02_08.bvh` `9EB38F57C2D4AEDF00DA5A1700F134423AD5F3EE407E3AE1BDB00060569943D8`, `144_13.bvh` `0CC6D4BD771970FA1A07D33B8BF5E42F12E72E4EE9BD61AFECD53AC09D07CBE3`, `144_20.bvh` `D8E4025891F8FFC94FF53839525B0E71CFACD2CBEC30A181BD738EC8220CBFCE`. Phase-Q paired BVH SHA-256: `22_05.bvh` `742AD9875BFE1E8F192D3841A5F08B01447177B3386777FED0A2263AB08BD58F`, `23_05.bvh` `4E11A31FEFB9FC388231EB5E87BC166AFA99EF48B53CB27F848080821D829674`. | Subject 02 supplies sword/knife and staff-thrust mechanics; Phase G uses trial 08 strike 01/05 only. Subject 22/23 trial 05 supplies the synchronized body-entry, shoulder-control and target-reaction review for Phase Q. Subject 144 trial 13/20 supplies the isolated left/right unarmed candidates. Subject 54 supplies the promoted creature-roar pantomime, subject 120 the gorilla-style berserk run, and subject 136 the crouch walk. Subject 16 supplies locomotion transitions, subject 111 floor-motion references, and subject 80 trial 03 the Pallet Rifle torso/shoulder stance. Subject 79 trial 96 was screened but rejected as a rifle source. Raw ASF/AMC/BVH files remain ignored. |
| Rokoko free superhero and fight mocap packs | [15 free superhero animations](https://www.rokoko.com/resources/rokoko-mocap-15-free-superhero-animations) and [13 free fight animations](https://www.rokoko.com/resources/rokoko-mocap-13-free-fight-animations). Rokoko states that the full-body/finger recordings were captured with its motion-capture tools and may be used from passion projects through commercial projects. ZIP SHA-256: Superhero `B911E7B200C66916D812C2E9C392DF458C5CAE2C093D7D3CE832749D24AAAD72`; Combat `380C9854B4AC21DE8A2EE436AE3D2BBEF9AFDDB6AF3BC97345EEB49B93DE7CF8`. Selected FBX SHA-256: `IronMan_Combat_mixamo.fbx` `B7E47877D89EDCE72EB70C3A71EEC896C4CAE3A5C097E3DE62BFE04F6BD340B7`; `MutantClaws_mixamo.fbx` `10D01206DE575F4005D8BA5411FD70852CF41B377402143C4A7108F6986A7A85`; `KnifeFight_mixamo.fbx` `46E126F8407E84CEA105B05E94AF55BE4CE26073E089FE7C012466AA8FE5C027`. | Phase J tested `IronMan_Combat` frames 177–196, which were human-rejected, and preserved `KnifeFight` frames 464–523 after correcting their label to forward grip. Phase K replaces the ordinary attack with `MutantClaws` frames 778–792 and adds a geometry-solved reverse-grip copy of the knife motion. Raw ZIP/FBX files remain ignored. The derived databases are isolated, not live and not visually approved; promotion also requires a final redistribution/licence check. |
| Rokoko free sports mocap pack | [12 free sports animations](https://www.rokoko.com/resources/rokoko-mocap-12-free-sports-animations), supplied as full-body Mixamo FBX captures for project use. ZIP SHA-256 `536D63D5B11B3A9B6324868FA24960743A1727FF3EC2375BF1738C541C9578B0`; selected `Baseball_Pitcher_mixamo.fbx` SHA-256 `442DECD763BA305CF71DB5086A1E72C0B7C691EC0187AE578802F860BC17F5E9`. | Phase R uses three independent early pitcher takes only for their planted rear-foot, pelvis, thorax and single-arm overhand kinetic chains. Ball/throw semantics are removed; the derivative remains review-only until human inspection confirms it does not read as pitching. Raw ZIP/FBX files remain ignored. |
| G1 Moves MOVIN TRACIN mocap dataset | [Official Hugging Face dataset](https://huggingface.co/datasets/exptech/g1-moves) and [processing repository](https://github.com/experientialtech/g1-moves), CC BY 4.0. The dataset documents 59 MOVIN TRACIN markerless captures plus one separate video-derived clip; Phases T/U use only MOVIN-captured Karate clips. Selected BVH SHA-256: `M_Move11` `583EB124C05C6098187B5A663EFB1CDE5806B42A4296A1CD71EEEEE0F1113079`; `M_Move17` `9844E4BFC2CE05CA37C66BB4F563643B660AFDED1DFB9F4F3E9C46A5417B2628`; `M_ShortMove16` `BDEA1DC9969C20B264B8EAEB26338973B55C6E77AD1FDB2212D64C4EBBD1A14E`; `B_AttackKarate` `B76D5F5B2BA581E28ABC8C6DF620E1BC2011C073280A762A99DA024FD8687A24`; `M_Move10` `FADB13A4A2DCDD1C327E519210EFEE52334D191FCE29A32384BF71799102178E`; `M_Move18` `D5498405E8CD8A81FAD2D3B25826F30D3B203E7A87FB2BAB9888D5C6F888EB3E`; `M_ShortMove13` `AF02568686439170B64D2D0D008423E6F96FE7F8F6FD04FA9B9EF85AEF6604C1`. | Phase T C group was human-selected and promoted to the standing-fists left-click runtime at `1.5×`; A/B/D remain unselected. Phase U K1 side kick was selected and promoted to the standing-fists B-key runtime at `1.5×`; K2/K3 remain review-only. Raw BVH files remain ignored, and both live actions still require in-game visual approval. |
| Rokoko free zombie and Motion Library weapon mocap | [12 free zombie animations](https://www.rokoko.com/resources/rokoko-mocap-12-free-zombie-animations) and [10 free fight/weapon animations](https://www.rokoko.com/resources/motion-library-10-free-fight-and-weapon-animations). Zombie ZIP SHA-256 `1927FED3086ACDA527C7D5D968B2DDC7B388FBD01AB2F60E8A05D277F8280D9B`; `ZombieAttack_Walking_mixamo.fbx` `BAFC35FE2471124DB4ADBD98DAC7C8D743E7BAE79F3410D74D9D79E1D937989D`; `stabTwist_Knife` take 01 `81B8AFF94388353A65A9E67C1294E8F81A17982C2D4D4D73888907C8147CEA6C`; take 02 `CF37B6EE6E2957261321D8D6096E690AD604206F62F6CF9EAE499860B4773C7C`. | Phase L uses only Zombie frames 208–251 for a torso-led two-arm maul and two independent stab-and-twist takes for forward/reverse knife candidates. These replace, rather than repackage, the human-rejected Phase-K motions. Raw files remain ignored; the derived database is review-only and not visually approved. |
| Rapa Motion FREE Mudra anime mocap samples | [Official itch.io download](https://rapamotion.itch.io/mudra-samples), stated free for personal/commercial work with no credit required. ZIP SHA-256 `93FF6A966590975D8FE3A225778A2DAD5BB39C8BC9C84BA78478821BC235D7E7`; selected `AS_Anime_Rasengan_Attack_Ybot.fbx` SHA-256 `3B5C1060D0BF42FCD537DD707494564D20763EB967D1851FEDB903ABCA7386E9`; selected `AS_Anime_Chidori_Attack_02_Ybot.fbx` SHA-256 `4F003CE84948F5B3414ADAF22314AB52902ECA80F05DE2A6724A693D64944B0F`. | Phase M Rasengan and Phase N Chidori ordinary-attack derivatives were both human-rejected. Raw files and isolated negative evidence remain ignored/non-live; neither motion may be repackaged as an accepted attack. |
| Haley Tuffles Premade Mocap Pack | [Creator motion-capture page](https://haleytuffles.com/motioncapture); bundled `ReadME.txt` states free personal/commercial use and no credit requirement. The author records with iPiSoft and cleans in Blender. Selected `ArmsLariat.bvh` SHA-256 `EAE6D32AA4C9FAD0EADA1905182E5B2308FFB46B4C7F9E844048EACE8FA25A77`; `ArmsSlap.bvh` SHA-256 `82CB7AE1C23B4A7783F71CAD79F7F757649D3D957FA08E5913E4C5E2AFFF65CE`; `HurtPunchedStomach.bvh` SHA-256 `4CF814892ADF733300FB57C6DD07512AC9359B502E02A2C00EA100859173699A`; `PushedBackwards.bvh` SHA-256 `122D0C49F0EE5A6C65C36FC1F85E8544A26E918BADA2BD5370FCC75E0706964B`; `ReadME.txt` SHA-256 `0890A5A4F1C1F91732CA960B89758077B6867581762DF9DBECEB728633BC3C51`. | Phase O/P Lariat and slap derivatives were not accepted as ordinary attacks. Phase R uses only the hurt/backward takes as red target hit reactions, triggered on confirmed hits; they do not define the attacker motion. Raw files remain ignored and derivatives are non-live pending human review. |
| ACCAD Open Motion Project, Male-2 General Movements | [Official page](https://accad.osu.edu/research/motion-lab/mocap-system-and-data), CC BY 3.0. | Crouch idle, stand-to-crouch, crouch-to-lie, lie-to-crouch and crawl takes provide the real-human low-posture mechanics. Project SEELE trims, retargets, loop-closes and target-constrains the derivatives; raw BVH files remain ignored. |
| Cologne Motion Capture Database (CMCD), `KingKong2` | [Official licence page](https://mocap.web.th-koeln.de/about.php), CC BY 4.0. | Selected right/left creature swipes and a forward pounce supply the Unit-01 berserk body mechanics. The source remains human performance capture; Project SEELE performs axis normalization, Tiger retargeting and runtime constraint repair. |
| `amc2bvh` 0.1.0 | [Tom Copeland repository](https://github.com/thcopeland/amc2bvh), MIT | Local-only deterministic ASF/AMC to BVH conversion for Blender. The binary/source archive remains ignored; no executable is shipped in the mod. |
| GenoView Inverse Kinematics / Foot Locking | [Daniel Holden source](https://github.com/orangeduck/GenoView-InverseKinematics), MIT; article [Inverse Kinematics and Foot Locking](https://theorangeduck.com/page/inverse-kinematics-foot-locking) | Algorithmic reference for velocity-based contact annotation, shared-pelvis two-leg IK and offline contact locking. Project SEELE's implementation operates on its own EVA skeleton and data. |
| Motion Matching example | [Daniel Holden source](https://github.com/orangeduck/Motion-Matching), MIT | Reference architecture for trajectory features, database search, pose inertialization and contact fix-up. The external checkout is ignored; only independently adapted Project SEELE code may ship. |
| ozz-animation | [Official repository](https://github.com/guillaumeblanc/ozz-animation), MIT | Data-oriented sampling/blending reference. No native ozz binary is currently linked into Forge; the Java renderer follows its phase-synchronised local-pose blending principles. |

`tools/inspect_humanoid_motion_library.py` inventories source skeletons and
actions through the same Blender importer used by production.  The reusable
`tools/build_eva_motion_database.py` collapses the source spine/clavicle chains
onto the EVA hierarchy, calibrates against a standing idle rather than a
T-pose, changes coordinate systems, records 30 Hz normalized quaternions and
annotates left/right foot contact. No Evangelion animation, footage or official
asset is present in this database.

CMU trials are segmented by `analyze_bvh_locomotion.py`,
`analyze_bvh_jump.py` and `segment_bvh_combat_motion.py`.  Retargeted candidates
are built by `build_eva_cmu_motion_candidates.py`, then rejected unless both
`audit_eva_motion_database.py` and the exact-matrix Blender mesh audit are
green.  `refine_eva_motion_database.py` performs velocity-aware contact
annotation, fitted stride extraction, shared-root correction and two-leg IK;
`promote_eva_motion_candidates.py` refuses promotion from a failed audit.


## R04 CRT 工作终端（2026-09-08）

`textures/block/nerv_workstation.png` 为内置 imagegen 生成的原创绿色单色屏幕 UI，搭配项目原创的 CRT 外壳、底座与键盘模型；它是装饰工作终端，不替代已实现的指挥室控制系统，也不显示实时遥测。提示围绕 1990 年代日本机房显示风格、MAGI 三子系统、波形与节点图；未复制官方标志或原画。SHA-256 与完整本机来源记录见 `artifacts/world_motion_r04/asset_manifest.json`。

本轮清理的 NERV 叶片标志及 MoCap Online 持枪动捕重定向结果保留在本机资源目录，不进入仓库或发行物。

2026-09-08 R05：空手站立右键重击使用 [ACCAD Open Motion Project](https://accad.osu.edu/research/motion-lab/mocap-system-and-data) 的 `Male2_E4_CrossRight`，版权归 ACCAD / The Ohio State University，按 [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) 署名。派生数据经过裁剪、EVA 比例重定向、脚底约束、肘部修正、握拳和时长映射，详见 `motion/eva_heavy_right_cross_r05.json` 的 provenance。MoCap Online Demo `MOB1_CrouchWalk_F` 与相关持枪动捕重定向仍仅用于本机私有资源，未纳入仓库。

## R06 建筑饰面与姿态（2026-09-08）

`tools/build_nerv_architectural_assets.py` 独立绘制七种 128×128 建筑贴图及匹配模型：灰蓝墙板、红线墙板、浅色地板、警戒门槛、嵌入式灯具、导向盲道和警示盲道。矢量源位于 `tools/art/nerv_architecture/`；本轮未把网上原画、照片或剧照变成贴图。原 TV 和现实设施的研究链接见 [R06 记录](WORLD_MOTION_R06.md)。

单膝、扶地与卧姿转换由 `tools/author_eva_rifle_stances_r06.py` 在已测量骨架上编制，使用接触约束和双四元数接缝计算；不称作新下载的真人卧射。组合文件仍包含此前本机 MoCap Online 派生动作，保留在 `run/projectseele-local-maps/eva_body_r06.json`，不随仓库发布。售票机与时钟直接使用已经安装的 MTR 4.0.5 模组方块，没有复制或重发其素材。

## R07 原创试验机与军事港区（2026-09-09）

`eva_prototype` 的 83,432 个三角形、46 个部件和 1024×512 材质由 `tools/build_original_eva_prototype_r07.py` 从放样、装甲面、接缝及关节几何创建，没有复制原有 EVA 网格。复用项目公开的 70 骨接口与公开动画；用户尚未提交的原三机资源保持原样。原创造型草图通过内置 imagegen 生成，提示/方式/本机路径记录在 `artifacts/world_expansion_r07/prototype_design.txt`，草图不是游戏截图。实际网格预览由 Blender 渲染。

港口两艘固定舰体、基地建筑及标线为本项目原创建造；未导入查找过的 Planet Minecraft 舰艇文件。SBW 的坦克、飞机、巡逻艇、舰炮、近防炮与激光塔通过原模组使用，未拆出其保留权利的模型、贴图或音频并入本项目。依赖版本、SHA-512 和官方分发 URL 位于 `tools/r07_vehicle_mods.json`，下载物仅保存在忽略目录。详细来源、能力边界与验收记录见 [R07](WORLD_EXPANSION_R07.md)。

## R08 黑金试验机与历史驱逐舰（2026-09-09）

R07 的两艘简化原创舰体已被本机私有导入替换。实际使用的是 Nekoseal 的 [IJN Destroyer Division 6 (Akatsuki Class Destroyers)](https://www.planetminecraft.com/project/ijn-destroyer-division-6-akatsuki-class-destroyer/) 公开下载世界，ZIP SHA-256 为 `6e3fafaffd9060fec1f962890c7d5102ca65c7d0c63c48a4438dfd03029b2472`。从四艘模型中选择两艘约 238×23 格的舰体，保留作者方块和细节，旋转后按海平面安放；移除了源模型的不可见 barrier，并为本地图另做泊位和登舰桥。作者署名位于登舰点，下载来源及测量记录在忽略的 `artifacts/world_refinement_r08/ships/`。源世界、导入后世界及含其几何的导出图仅供本机使用，不作为 MIT 模组素材再发布。此前未成功下载的 Yukikaze 文件未用于本轮。

试验机保留用户已认可的原创设计图作为造型参考，通过 `tools/build_original_eva_prototype_r08.py` 重新建立黑金装甲轮廓和关节细节。最终模型为 98,722 个三角形、46 个网格部件，沿用公开 70 骨接口；没有从既有 EVA 网格复制顶点。模型、材质与构建脚本是本项目原创资源。材质在同一套资源中更新，运行时模型合同随之更新；三张原机型待提交资源按用户基线保留。离线 Blender 图用于检查几何，原生游戏图用于确认实际加载结果，两者不能混称。

码头桁架、容器端门、基地分隔和维修设施、黑色井筒外罩、机库屋面与平台下部结构均为本项目方块建造。现实参考和 TV 空间关系见 [R08 原作布局核对](TV_LAYOUT_REFERENCE_R08.md)；没有把官方剧照、照片、音频加入发行包。

## R09 金字塔饰面（2026-09-09）

新增金字塔外墙和标识方块的模型由 `tools/build_r09_pyramid_materials.py` 构造，引用原版 black/red concrete 纹理，没有复制原版纹理文件。南面经典 NERV 叶片与字标使用本机已经存在的 `run/projectseele-local-maps/nerv_logo.png` 提取方块遮罩，受限于分辨率省略微小格言；原图、遮罩、含图案的存档及导出图保持本机私有，没有将 NERV 位图加入公开资源包。单向窗渲染与旧存档兼容处理为本项目代码。造型和布局研究见 [R09](WORLD_REFINEMENT_R09.md) 与 [TV 对照](TV_LAYOUT_REFERENCE_R08.md)。


## R11 EVA-UN、工业吊机与识别图样（2026-09-10）

EVA-UN 的分层黑金装甲、单目、真实背部机械及吊机由项目程序构造。原三机的局部背部切孔仅作用于本机私有网格；不把第三方网格加入公开资源。原创试验机的公开模型、70 骨动作接口和新增机械节点继续由项目维护。

UN 徽记的矢量绘图来源为 [Wikimedia Commons / Emblem of the United Nations](https://commons.wikimedia.org/wiki/File:Emblem_of_the_United_Nations.svg)，Joowwww 绘制、Colohisto 清理，来源页为 PD-self。参照 [UN 官方徽记说明](https://www.un.org/en/about-us/un-emblem-and-flag)。该图样用于试验机的几何徽记和本机军事场景标志，来源与派生记录见 `artifacts/world_motion_r11/references/un_asset.json`。

SBW 的七种载具模型覆写保留在 `run/resourcepacks/eva_real_model`。文字在实际装甲、机翼或舱框识别板上随骨架运动。白／黑色块只写入原图集中未被原有 UV 引用的位置，图集尺寸、原多边形和原 UV 引用不变；原模型、贴图及派生覆写不作为本项目 MIT 素材发布。两艘历史驱逐舰继续沿用 R08 私有导入及作者署名。

本轮低姿态爬行属于在既有测量支撑姿态上的原创约束动作，不标为真人动捕原片。受击与机械音效复用项目已有原创合成资源。实际 TV 插入画面和线稿仅用于本机研究，未进入发行包。详见 [R11 记录](WORLD_MOTION_R11.md)。

## R12 动捕改编与吊机细节（2026-09-10）

CMU 18_03、18_05／19_05，Bandai Namco Research dataset-1 的职业演员出拳，以及 Haley Tuffles 的正蹬、跳跃、倒地、落地、受推和跪姿经本地骨架适配与接触修正组成 R12 演出。BNR 数据为 CC BY-NC 4.0，混合派生成品保存在本机 `run/projectseele-local-maps/first_battle_r12.json`，公共资源保留 R10 回退。源文件、许可和哈希索引由 `tools/prepare_human_sources_r12.py` 生成；完整出处、使用范围和真人／人工编排区分见 [R12](WORLD_MOTION_R12.md)。

吊机的倒角铸件、端盖、走台、滑轮、液压支撑和夹爪为本项目原创几何。借助 Konecranes 的公开工业产品资料理解卷扬布局，没有导入其 CAD、图片或商标。电影音轨继续使用项目既有原创合成音效，验收视频的音频是按实机事件时刻混音的独立音轨。

## R13 背部插入口（2026-09-10）

负责人提供的四张 TV 插入栓截图仅作本机造型和动作参考。原三机沿用私有 Tiger 模型的双圆点盖板和贴图，经几何拆分、归属修正、切孔及侧翻铰链适配后仍保存在私有包。UN 的背部服务盖和内部管道来自本项目原创模型；新夹具的齿圈、叉爪、驱动杆及软管为原创程序几何。公开数值接口记录每台机体的测量位置，完整过程及素材边界见 [R13](EVA_DORSAL_TV_R13.md)。

## R15 工作人员与门（2026-09-11）

`staff_misato`、`staff_ritsuko`、`staff_maya` 及六套通用 NERV／UN 制服由 `tools/build_staff_skins_r15.py` 原创绘制。Planet Minecraft 的候选角色皮肤下载未成功，未进入本轮素材。门的分缝、边框、识别条和状态指示为项目原创建模，使用原版白色混凝土纹理进行着色，没有复制该纹理文件。

R15 战斗继续在 R12 私有动捕和角色几何基础上改编；混合派生动作仅保存在本机 `first_battle_r15.json`。录像是实际游戏画面，配原创合成音效离线混音。Distant Horizons、Embeddium、FerriteCore 来自各项目官方 Modrinth 分发，下载脚本固定版本并验证 SHA-512；第三方 JAR 不提交到仓库。详见 [R15](STAFF_WORLD_R15.md)。


## R19 世界修补与 UN-00（2026-09-17）

新的道路灯头、站台／住宅／UN 座椅、发射区管道与支架、NPC 发型附件为项目原创几何；道路半砖引用 Minecraft 自带混凝土材质，未复制原版纹理文件。车站时刻牌读取实际 MTR 预测数据。参考图片及用户 Bilibili 片段仅保存在本机研究目录，不进入公开资源或游戏纹理。

EVA-UN-00 的两次 Lux3D 输出作为原始候选存档，未作为最终公开网格；公开的 139,806 三角形版本由 `build_un00_body_r19.py` 与 `attach_un00_dorsal_r19.py` 构造，沿用本项目原创背部机械。私有动作仍留在 `eva_real_model`，原三台用户机体资源不覆盖。人物恢复本机既有包中的像素皮肤，新增发型为项目原创模型。

依赖新增 Xaero’s Minimap 26.5.0 和 Xaero’s World Map 1.46.0，官方文件及 SHA-512 在 `tools/client_navigation_r19.json`。Acedium 0.2.7-beta 仅供独立试验，不随默认包分发。详情与造型出处见 [R19](WORLD_REPAIR_R19.md)。

## R20 场景与交接（2026-09-17）

斜坡导轨、承重腹板、纵向检修管线为 `build_transfer_mesh_r20.py` 生成的原创工程几何，使用场景固定渲染器，未嵌入参考视频纹理。站台、灯带、操作台和导向标识沿用项目已有原创资源，按实际道路和 MTR 几何布置。参考来源见 [R20 记录](WORLD_REBUILD_R20.md)。

负责人要求暂停 UN 模型制作；本轮私有 `eva_real_model` 资源包与冷备份逐文件相同。Pro 参考包以明确文件清单收录概念图、用户参考、Lux3D 原始候选及 R19 兼容模型／骨架／机械接口，不含账户凭据或本轮未采用的实验候选。该包保留在本机，未纳入公开仓库。

R20 视频取自实际 Minecraft 帧缓冲，按原时间剪辑，无生成或补间的运动画面。视频不带音轨；当前运行时原创音效保持。

## R21 机械声、播报与导向牌（2026-09-18）

轨道、液压、锁闭、弹射及固定音高双鸣警报由本项目合成，没有截取 TV 音轨。初版连续滑音警报已按负责人反馈更换为短促的 660 Hz 双鸣，压低峰值和高次谐波。

中文播报为本项目原创文本，使用 Microsoft Xiaoxiao 神经语音生成，不模仿具体配音演员。生成工具为 [edge-tts](https://github.com/rany2/edge-tts)，声线资料见 [Microsoft Speech 语言支持](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)。语音预先导出为本地 OGG，游戏运行时不联网合成；文本、参数、文件校验值和时长见 `artifacts/world_repair_r21/audio_v2`。重新生成以 `refine_facility_audio_r21.py` 为准，旧的 Huihui 版本仅留作比较备份。

12 块设施导向板复用本项目的金属显示板几何与游戏字体，在实际固定墙面上安装，按真实岔路给出目的地和换层方式。它们使用独立的导向数据模式；车站原有时刻板仍读取真实 MTR 运行信息。

使徒来袭的全局警报也引用同一固定双鸣音频，避免旧带颤音的警号继续出现；警报触发、解除和原音量不变。

## R21 UN 双机私有模型

Lux3D 原始网格、本地涂装与蒙皮处理、Pro 原始交付和 Blender 源文件保存在本机 `artifacts/un_models_r21`。实际选用 Lux3D 两个已完成任务的几何，经本地装配、测量与原生驾驶测试后接入独立 UN-00／UN-01 资源；未提交生成网格或参考图到公开仓库。来源、预算、验证与文件边界见 [UN 双机记录](UN_MODELS_R21.md)。

## R23 增量

- `nerv_direction_panel` 为原创紧凑壁牌，复用自有时刻表绘制，避免指路牌占用通道。
- `tools/build_tv_machinery_r16.py` 的常驻运输架上部增加原创检修视口；`refine_carrier_viewport_r23.py` 只重建该部件，未改变其他机械部分或加入原片素材。
- R23 两台 UN 的手部／光学改造与三驾驶员皮肤仅安装在本机私有资源包。完整皮肤来自用户已下载文件，原像素未改；其来源哈希和安装凭据保留于 `artifacts/access_r22/asset_stage.json` 与 `artifacts/facility_r23/asset_install`，公开前仍需各自的再分发许可。

## R24 环境、对白与作战（2026-09-19）

- `mesh/period_details_r24.json` 是 `tools/build_period_props_r24.py` 的原创几何：公共电话、时钟、陈列与茶室设施、监测台、推车、自行车、饮料机和邮筒等。1990 年新宿、1989 年东急档案及 UR 团地照片仅用于观察，来源、改编和 AI 材质提示词见 [美术记录](ART_DIRECTION_R24.md)。
- 侧室工具箱的 `textures/entity/chest/nerv_equipment_r24.png` 由项目原创 SVG 图集栅格化生成，可编辑源为 `art_sources/nerv_equipment_chest_r24.svg`；没有复制原版箱子纹理，库存和方块身份不变。
- `textures/block/period_station_concrete_r24.png` 为内置 image_gen 辅助生成的新地面材质，经技术缩放接入；不是官方场景截图或下载照片。AI 生成来源与原始提示词随项目明确登记。
- `sounds/shamshel_whip_charge.ogg`、`shamshel_whip_crack.ogg`、`period_phone_busy.ogg`、`staff_radio_connect.ogg`、`staff_radio_ack.ogg` 为固定种子原创合成，无录音采样；生成器为 `tools/build_tv_audio_r24.py`，按仓库 MIT 许可。
- `data/projectseele/nerv_dialogue/profiles.json` 为本项目原创对白，不是原剧台词转录。TV 章节目录用于事件顺序，已实现作战和未来章节分别标识。
- 夏姆榭尔新的骨骼轨迹和接触代码为本项目编写；现有本机身体依旧是先前登记的私有研究模型，新增动作不会改变原身体素材的许可状态。
- 开源与视频计划见 [公开准备](OPEN_SOURCE_RELEASE_R24.md) 和 [B 站制作方案](BILIBILI_AND_COMMUNITY_R24.md)。上述文件没有把许可询问信当作已经获得许可。


## R25 通信、步枪与可选写实材质

- `tools/build_radio_audio_r25.py` 生成原创卫星电话物品几何及重型步枪声。枪声由冲击噪声、低频衰减和机械尾音合成，无原剧音频。
- `tools/refine_crouch_support_r25.py` 仅在既有私有动作上调整双腿支撑，私有动作 JSON 留在本地，不加入公开仓库。
- 机库控制架由项目程序模型修改；`tools/refine_plug_frame_r25.py` 与 `audit_plug_machinery_r25.py` 记录三机插入栓扫掠包络。
- 写实基础材质候选为 illystray 的 [rotrBLOCKS](https://modrinth.com/resourcepack/rotrblocks)，V87、128×、2D Foliage。固定版本、官方 CDN 和散列见 `tools/realistic_pack_r25.json`。[作者条款](https://illystray.com/terms/) 允许个人使用、禁止重新分发；其 ZIP 和像素不进入 Git 或共享客户端包，使用官方直连下载。保留作者原档，置于 EVA 专用包下方。

## R29 运输机与核爆声画

- `tools/build_un_transport_r29.py` 生成原创 UN 垂直起降运输机及自行载台，几何接入既有设施网格；没有下载或改编第三方飞机网格。
- `tools/build_finale_audio_r29.py` 以固定种子合成 `angel_nuclear_finale.ogg`，不含电影、动画或现实爆炸录音。烟云和十字架为实时程序几何。
- 可选 [Complementary Unbound r5.3](https://modrinth.com/shader/complementary-unbound) 保留作者原文件，使用 [Oculus](https://modrinth.com/mod/oculus) 加载。固定官方 CDN 与 SHA-512 见 `tools/city_shaders_r29.json`；不将光影 ZIP 放入本仓库或交付压缩包，客户端脚本从作者来源下载。


## R30 设施、广播与 UN 模型

- `nerv_sign_post`、室内灯具细部和机场候机区配置为本项目编写的原创几何与布局；固定灯具和可切换指挥室照明不依靠后期抬亮截图。
- `pa_signal_r30.ogg`、`pa_blue_r30.ogg`、`pa_alert_r30.ogg` 使用原创短句和 Microsoft 标准普通话神经语音，通过既有 edge-tts 环境生成；未使用原剧录音或模仿原配音演员。生成器 `tools/build_mission_audio_r30.py`，本机来源、时长和散列在 `artifacts/facility_r30/mission_audio/sources.json`。
- UN 原始网格分别来自本轮既有 Lux3D 任务 `3672326`、`3672329`。本地工具保留比例与原 UV，重新分区、制作独立骨架、关节、手指、光学部件、铭记和背部喷口，并在 Blender 中烘焙新涂装；不是将原始生成结果直接作为成品。原件、编辑模型与检查记录留在本机私有工件目录。
- 材质按 [shaderLABS LabPBR 1.3](https://shaderlabs.org/wiki/LabPBR_Material_Standard) 编码，配有 4K 基色、粗糙度/金属度、LabPBR 和受供电状态控制的发光资源。法线贴图采用平法线，曲面细节由实际几何及顶点法线提供，未把平图宣称为细节烘焙。
- R30 的五个 ZIP 是用户现有文件的私人部署备份。独立材质、光影包内保留已下载的作者原始 ZIP 和说明，不进入 Git，也不作为项目公开开源发布物。

## R31 对白与设施广播

`data/projectseele/nerv_dialogue/profiles.json` 的 253 句为重新编写的项目原创中文对白，人物写法参考 TV 系列官方剧情介绍；具体来源和取舍见 [R31 对白记录](DIALOGUE_AUDIO_R31.md)。没有复制原剧完整台词。人物发言只显示文字。

18 段设施广播由 `tools/build_facility_audio_r31.py` 使用标准 Microsoft Xiaoxiao 神经语音生成，原有事件名保持兼容，新增 `pa_combat_r31.ogg`。没有模仿具体演员、使用克隆音色或截取原剧录音。文本、参数、时长和 SHA-256 记录在本机 `artifacts/dialogue_audio_r31/sources.json`，样音为 `facility_pa_sample.mp3`。角色对白、设施广播和公共交通提示使用独立触发途径；R30 的角色报告语音已停止调用。


## R32 gameplay motion (2026-09-23)

- Haley Tuffles: https://haleytuffles.com/motioncapture — author permits any use; credit retained. Selected source actions: StanceBoxer, ArmsJabBoxer, ArmsSinglePunch, ArmsSimpleLariat, ArmsCloseRangePunch, ArmsGrappleKnockdown, LegsStomp, AerialSlapDownwards, LegsDivekickFightingGameInspired and SlapDownwards.
- Quaternius Universal Animation Library, Standard free release: https://quaternius.com/packs/universalanimationlibrary.html — CC0. Uses Jump_Start, Jump_Loop, Jump_Land; the UAL2 free rig reference is decoded for calibration. No paid Source kit was acquired.
- `tools/author_gameplay_motion_r32.py` retargets to five measured local EVA rigs and Sachiel. Generated private runtime profiles retain each selected source path and SHA-256. Source assets and the owner's model pack are not committed with this code update.
- Runtime uses the actual pose for hit sweeps and maintains joint centres through blending. These are adapted motion performances, not animation assets taken from God of War, GTA V or official Evangelion footage.


## R33 grounded combat and machinery (2026-09-24)

ACCAD Open Motion Project, Advanced Computing Center for the Arts and Design / The Ohio State University, [official source](https://accad.osu.edu/research/motion-lab/mocap-system-and-data), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). R33 uses Male2 E1 JabLeft, E4 CrossRight, E5 HookLeft, E14 BodyCrossRight, E3 Advance, E5 Retreat, E9 SideStepLeft, E10 SideStepRight, and A1 Stand for calibration. The derivatives are trimmed, retargeted to five EVA rigs and Sachiel, cycle-corrected and constrained at the support toes. Source hashes and exact frame ranges are recorded in the private runtime profiles. Raw recordings are not committed; this attribution must accompany distributed derivatives.

The black carrier truss and twelve-arm maintenance equipment are original procedural geometry by Project SEELE, generated by `tools/build_bay_machinery_r33.py`. No film frame, commercial game model or downloaded texture is embedded in these meshes. Other unchanged motion/asset licenses continue to apply.

## R34/R35 experimental combat foley and launch hydraulics (2026-09-24)

Recorded combat foley derivatives use the following CC0 1.0 recordings: [Punch by qubodup](https://freesound.org/people/qubodup/sounds/482134/), [Whoosh by qubodup](https://freesound.org/people/qubodup/sounds/60013/), [iron hitting concrete by rifualk](https://freesound.org/people/rifualk/sounds/613466/), and [Heavy Metal Impact 2 by magnuswaker](https://freesound.org/s/614063/). Edits comprise excerpting, pitch/speed changes, filtering and layering; no claim of original TV audio is made.

`facility_hydraulic_launch.ogg` is a 3.2-second edited excerpt of **Hydraulic Press** by **Luan-Van-Den-Berg**, [source](https://freesound.org/people/Luan-Van-Den-Berg/sounds/708004/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: start at 1.46 seconds, mono conversion, 45 Hz highpass, 5.5 kHz lowpass, short fade-in/out. This attribution must accompany distributions of the derivative.

The optional local `eva_roar_r34` audition pack is not part of this repository. Its EVA-labelled community upload has no independently verified master-recording provenance or redistribution license; it must not be described as CC0 or verified original TV Japanese audio.

## R36 recorded movement and contact foley (2026-09-24)

R36 revised ground motion (2026-09-25) reuses the permitted Haley Tuffles captures above and adds `ArmsSinglePunch2` for the opposite-side follow-up. `author_combat_performance_r36.py` records the source file and SHA-256 for each derived clip. The earlier R36 wrist-path experiment is retained as a rejected comparison and cannot overwrite the active profiles from its CLI.

The following recordings are licensed CC0 1.0 on their original Freesound pages:

- Philipp Grzemba / Sheyvan: [Metal Impact Container 1 5](https://freesound.org/people/Sheyvan/sounds/569413/).
- newagesoup: [long-metal-hit-01](https://freesound.org/people/newagesoup/sounds/337832/), originally edited from EpicWizard's shed-door recording, as credited on the source page.
- Nox_Sound: [Foley Object Metal Oven Creaks](https://freesound.org/people/Nox_Sound/sounds/585734/), [Strong Stone Impacts with Debris](https://freesound.org/people/Nox_Sound/sounds/554148/), and [Rocks/Stones Impacts](https://freesound.org/people/Nox_Sound/sounds/567701/).
- velcronator: [Whoosh 01](https://freesound.org/people/velcronator/sounds/733888/).
- TRP: [210415 Punching bag, foley, ms](https://freesound.org/people/TRP/sounds/616953/), separately selected body-impact takes.

`tools/build_combat_audio_r36.py` fetches the public HQ preview files and authors mono game cues through excerpt selection, pitch/speed changes, equalization, fades and layering. Generated names end in `r36_<take>`. They are edited recordings, not original Evangelion TV sound effects. Source pages, original hashes and per-output hashes are retained in the local build manifest. The generator does not generate a new roar or sample an anime soundtrack.

## R37 TV jaw and feral action (2026-09-25)

The Unit-01 jaw is a derivative of the existing credited Tigerar1 CC BY-SA model, split at its painted serrated armour seam. The inset red interlocks, continuous mouth lining and edge bevels are original procedural geometry; the TV episode-2 production cel and broadcast frame were visual references only and are not included in the assets. The rejected external white dental arch is not installed or distributed. `tools/build_tv_jaw_r37.py` preserves a local source snapshot and writes an exact mesh/skeleton hash manifest.

The R37 feral clips adapt the already permitted Haley Tuffles recordings `ArmsSlap`, `ArmsLariat`, `ArmsSlapUpwards`, `ArmsSinglePunch2`, and `SlapDownwards`, with retargeting, timing changes, continuous supports and new claw finger poses. SNK's Iori material informed the attack direction only; no SNK model or animation data was imported. Source SHA-256 values remain in each private profile. R37 LabPBR derivatives use the existing credited colour/normal/material maps and generated shallow normal and reflectance channels; no official frame is used as a texture. Existing source-model licenses remain applicable.

## R38 facility shader (2026-09-25)

`ComplementaryUnbound_r5.3_SEELE_R38.zip` derives from the pinned Complementary Unbound 5.3 file and the existing LCL compatibility derivative. It retains the author's archive and license files and adds a spatially blended indirect-light floor in the surveyed facility volumes. The pinned original archive remains unchanged. Source/output SHA-256 and the modified shader path are recorded by `tools/build_facility_shader_r38.py`; no new model, animation recording, or official EVA image/audio was downloaded for R38.

## R40 performed roar and doors (2026-09-26)

`eva_berserk_performed_r40.ogg` adapts [Monster roar by colorsCrimsonTears](https://freesound.org/people/colorsCrimsonTears/sounds/537883/), licensed CC0 1.0. The source is the author's performed inhaled breath, not an anime recording. Changes: 0.88 resample pitch, mono 48 kHz, a 48–7000 Hz passband, mild compression and fades. `tools/build_roar_r40.py` checks the saved source hash; the original page, source and output hashes remain in the local R40 manifest. The conflicting optional R34 audition pack is deselected in the R40 client. Subjective auditory likeness has not been certified by an audio-inspection tool.

[Macaw's Doors](https://modrinth.com/mod/macaws-doors) by Sketch Macaw and Sketch Peachy is pinned to Forge 1.20.1 version 1.1.5 (Modrinth version `n8BlIUm3`). Its distribution metadata declares MIT. `tools/fetch_facility_doors_r40.py` verifies the upstream SHA-512; client and server both need this dependency for the new storefront entrances. Development uses ForgeGradle remapping; the unmodified upstream JAR is the deployment dependency.

## R40 offline deformation workflow

[libigl 2.6.3](https://libigl.github.io/tutorial/#as-rigid-as-possible), distributed under MPL-2.0 for the core functions used here, is an offline authoring dependency. It is installed from the pinned official PyPI wheel into the ignored local geometry runtime. It is not added as a Minecraft runtime dependency. Installation metadata and the wheel hash are retained in the R40 artifact report.

The paired Sachiel surface retains the existing private mesh topology/UVs and their original model licenses. Its authored soft-tissue motion uses ARAP with rigid anatomical attachments, grounded EVA supports and shared optical/socket curves. Original TV episode 02 was viewed for the reach, enclosing silhouette and core contact; no broadcast frame or audio is embedded. The public authoring tools do not contain third-party geometry. The saved `.blend`, private movie JSON, binary surface and native review videos remain local artifacts.

## R42 hands, optics and furniture (2026-09-28)

R42 gameplay/body/paired profiles derive from the previously credited private rigs and motion sources. Changes include an anatomical palm frame, finger articulation, elbow continuity, explicitly authored punch phrases, a non-looping airborne pose and paired timing/support corrections. Existing licenses continue to apply. TV episode-2 footage was viewed as a motion reference only; no footage, frame or soundtrack is included in the release.

The red and dormant-black eye textures are runtime colour derivatives of the existing eye alpha mask. The soft smoke density sprite and three baked seating models are original procedural assets. Wall artwork uses the pre-existing local images through a normal depth-tested block renderer; no new official image is embedded. The [Tokyu 1990 Den-en-chofu station photograph](https://tokyu.shibuyaphotomuseum.jp/detail/1765/) was viewed for entrance and pavement references and is not redistributed.

## R44 residential plaster (2026-10-01)

`assets/projectseele/textures/material_sources/residential_plaster_original_r44.png` is a new original bitmap produced with the built-in image-generation tool, without input images. Its full prompt and SHA-256 are recorded in `artifacts/rebuild_r44/city_expansion/misato_material_root_cause_v1/original_plaster_provenance.json`. The untouched 1254-pixel source is imported as a 512-pixel central sprite with Minecraft's native atlas `unstitch` source. No global quartz texture or PBR map is replaced.

The domestic finish is an original interpretation of pale matte apartment walls. A reproduced TV kitchen frame was viewed only as a material/proportion reference; the exact episode cut remains unconfirmed. That frame is neither embedded nor redistributed. In-game material, tiling and whole-room visual acceptance remain pending until the R44 native review.

## R45 anatomical hand candidate (2026-10-02)

### R45 physical constraint correction (2026-10-04)

`physics/AngularConeConstraintR45.java` adapts the Zlib-licensed [JBullet ConeTwistConstraint](https://github.com/stephengold/jbullet/blob/master/src/com/bulletphysics/dynamics/constraintsolver/ConeTwistConstraint.java). The original licence and authors remain in the source. Changes are explicitly marked: ordinary Java temporaries replace instrumented stack allocations; angular correction is expressed as the radial angular error to the existing ellipse, instead of its dimensionless squared ratio. The distinction follows the angular-error formulation documented by the [current Bullet implementation](https://github.com/bulletphysics/bullet3/blob/master/src/BulletDynamics/ConstraintSolver/btConeTwistConstraint.cpp). This is a local adaptation, not an upstream library upgrade. Native input captures, diagnostic omissions and the before/after root-cause record are in `artifacts/rebuild_r45/motion/physics_replay_v158`; that record does not claim completed visual acceptance.

The isolated hand candidate uses the CC0 MakeHuman base mesh, default skeleton and vertex weights from commit `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` of [makehumancommunity/makehuman](https://github.com/makehumancommunity/makehuman/tree/a8bc2d54ff0ac92e78ff71431b1023eda42bf482). The project's [official asset licence](https://static.makehumancommunity.org/about/license.html) and `LICENSE.ASSETS.md` distinguish graphical assets from application code. No MakeHuman application code is incorporated. The source files, licence copies, immutable download URLs and SHA-256 values are recorded under `artifacts/rebuild_r45/models/hands/makehuman_reference`.

Root-authored processing fits a coherent hand surface to EVA proportions, rebuilds a neutral finger rig and rebinds the skin. TV hand/foot design drawings were viewed as shape references; no reference image is copied into this candidate. Existing private EVA texture licensing remains unchanged. This is a development candidate, not a statement that the hand appearance, weapon contact or release asset admission has passed.

The [official MakeHuman system poses pack](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_poses.html) was downloaded for isolated rig diagnostics. Its fight-pose metadata names MakeHuman and CC0. Download URL and ZIP hash are in `artifacts/rebuild_r45/models/hands/makehuman_pose_reference/source.json`; these pose experiments were not promoted. MCO crouch data retains the pre-existing private evaluation restriction. New ordinary-strike candidates use the already credited ACCAD Male2 E1 JabLeft and E6 HookRight captures, with their exact source hashes and selected frames in the candidate authoring receipts; this is not an official EVA animation asset.

R45 pressure-door leaves and hazard stripes are original vector/material work. The TV11 R07 still informed the broad blue-grey leaf, dark centre seal, restrained bevel and red-black fixed frame; no official image pixels are shipped. Door numbering uses the actual game DoorID. Cabinet and mechanical details not visible in the reference are game adaptations. TV22's passenger-cabin wall band and TV12's utility-cabin roof are separate references, not evidence that all NERV doors have the same mechanism.

The private `forward_strikes_v187` study uses the already credited Haley Tuffles `ArmsPunch1` and `ArmsCloseRangePunch`, plus Eyes, JAPAN's `karate-09-punch strong-yokoyama.bvh` (SHA-256 `e4137dc5931cf6f45bcaff9c71557e2a798f8a382e5b14758007e83ebc31c82c`, source frames 400–431). [mocapdata's original free-data terms](https://mocapdata.com/Terms_of_Use) name Eyes, JAPAN Co. Ltd. and contain both BY and BY-SA 2.1 Japan wording; retain the attribution and ShareAlike terms with any distributed derivative rather than treating this data as MIT. The study changes skeleton proportions, hinge frames, support contacts and clip boundaries; sparse source hand markers do not supply finger animation. TV19 cuts 263B/267/274 inform forward pressure as a choreography reference only. This remains an unaccepted development candidate.


## R45 Mesh2Motion 动作族与二号机独立长剑（候选）

- Mesh2Motion 官方站 https://mesh2motion.org/ 与资产仓库 https://github.com/Mesh2Motion/mesh2motion-assets/tree/main/rigs/human ：资产 CC0-1.0；应用 MIT。实际三个 GLB 共178条，完整条目/处置在 `docs/MESH2MOTION_ACTION_PLAN_R45.md`。源 Git blob、SHA-256 和文件长度保存在私有 `motion/mesh2motion_research_v190/download_receipt.json`。主要为手工关键帧，独立 mocap 包单列，不把全部动作称为真人动捕。
- 三包各用自身 REST_BIND 校准；v213/v215 候选保留源全身动作、原机体骨长、独立详细手部坐标系与源根位移。翻滚/倒地使用全身表面承托，来源不是调参生成的腕点轨迹。离线候选不等同正式装入、原生通过或用户认可。
- 新 `eva02_longsword.mesh.json` 从上表 Rainbow_Slakot CC Attribution 双头刃武器的一端改编，延长单刃，重新制作原创直柄、护手、柄帽；保留原模型与高精度粒子刀文件。原作者、原作链接与许可证不变；新增造型和动作是游戏原创推演，不声称 TV 原作二号机曾使用这把长剑。手柄v205、手姿v209独立，未覆盖旧握拳/刀握姿。
- 持盾动作制作依据：TV第六话 289/290/292/297 镜头的举盾、迎击与失衡（https://wiki.evageeks.org/FGC:Episode_06_Scene_08）；采用轮廓/受力关系，研究画面不复制进发行贴图。普通 Mesh2Motion 小盾姿势需要适配巨盾，不能直接当作已复原屋岛。
