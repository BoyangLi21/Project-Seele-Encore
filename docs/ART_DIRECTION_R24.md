# R24 环境细节与材质来源

采用的方向是九十年代日本公共设施中较克制的配色和尺度：浅灰矿物地面、奶油色搪瓷牌、灰绿设备外壳、茶色桌面、细金属框架与少量纸质信息。车站是有人停留和换乘的地方，设备应有明确的安装面；总部保留较冷的蓝灰、灰绿和警戒色分区。

## 实际参考与本项目改编

| 参考 | 实际看过的内容 | 本项目应用 |
|---|---|---|
| [1990 年新宿 JR 巴士站](https://commons.wikimedia.org/wiki/File:JR_Bus_Shinjiku_Sta_1990winter.jpg) | 原上传者 Cassiopeia sweet 的照片；公共领域声明 | 简洁浅色站务小屋、固定公告与设备安装方式；没有复制照片作贴图 |
| [1990 年新宿 Nitto POLE LIGHT 茶饮柜台](https://commons.wikimedia.org/wiki/File:Nitto_POLE_LIGHT_Shinjuku_Sta_1990.jpg) | 同一摄影者的现场照片 | 灰绿柜台、玻璃、日光灯、茶色地面等细节；平面按现有通行范围改编 |
| [TV 官方分集页面](https://www.ktv.jp/evangelion/) | 公开剧情介绍与所列剧照，包括第一话的绿色公用电话 | 原创建模的绿色电话和金属玻璃罩；官方图片仅留作研究参考，不进入游戏资源 |
| [JR 东日本九十年代沿革](https://www.jreast.co.jp/company/about/history/1990/) | 公开沿革文字 | 区分年代感与后来的设备；当前站台门作为虚构 2015 年设施的安全设计保留 |
| [UR 团地自行车棚档案](https://www.ur-net.go.jp/aboutus/action/archive/c/01725_suwa.html) | 下载并目视核对的实景照片 | 雾里六栋住宅入口旁的简洁混凝土车棚、薄屋面、带车篮自行车及草地／铺地边界；保持原入口和楼号身份 |
| [UR 高岛平当年设计记录](https://www.ur-net.go.jp/lab/kiho30/30-04.pdf) | 实际读图到 PDF 第 2、4 页的组团／场地规划图；没有声称读完全部十页 | 团地入口、步行空间与生活设施的尺度关系；现有住宅布局不按未测绘照片强行改成精确 1:1 |
| [1989 年涩谷 Center-gai](https://tokyu.shibuyaphotomuseum.jp/detail/1762/) | 东急档案中带原水印的公开照片 | 店招、橱窗与窄店面连续排列的层次；六处现有商业楼入口添加原创招牌、薄雨棚、书报与设备陈设 |
| [1989 年田园调布站](https://tokyu.shibuyaphotomuseum.jp/detail/1864/) | 实际查看站房、站台雨棚、小卖部及售货机的关系 | 低调的细节组合与足够的候车通道；不把这座旧站的整个历史立面复制到所有车站 |
| [1989 年东急文化会馆](https://tokyu.shibuyaphotomuseum.jp/detail/1944/) | 实际查看站前公交广场、建筑标识和上下不同尺度 | 区分远处可辨的建筑标识与走近后才看到的设备；原图不作游戏广告贴图 |

原画和设定资料的公开介绍列在 R24 开发记录。尚未完整阅读的书籍不作为“每一个房间已逐图复原”的证据。

## 原创模型

`tools/build_period_props_r24.py` 生成电话亭、公告栏、时钟、饮水台、设备箱、管线、街道路桩、消防栓、茶室家具、书报架、咖啡设备、店招、档案推车、模拟监测工作台和带车篮自行车。网格使用原创建模参数与颜色，无照片纹理。

电话、公告栏、咖啡设备和书报架的上部有独立的原生碰撞／拾取方块，指向同一底座。座椅可乘坐并按真实净空选择离座位置。店招是受墙面支撑的搪瓷板；车站时刻牌继续使用真实运行数据，二者不混用。

34 间已登记的金字塔侧室按用途增加监测台、推车、咖啡角和小桌。已认可的大指挥室布局保留。原有工具箱的灰绿色金属外观由 `art_sources/nerv_equipment_chest_r24.svg` 原创绘制，再以 Sharp 栅格化；仅在这些侧室采用专用图集，不替换箱子方块或改动库存。最新实机已经确认箱体盖板、锁扣、侧面及房间设备正常显示。

住宅车棚只在六个原有楼梯入口旁落位，每处原入口的五格宽区域受保护。楼号牌移到原墙面上、车棚顶以上。12 辆自行车包含辐条、挡泥板、车架、脚架、货架和线框前篮；它们是静态生活道具，不伪装为可驾驶载具。

东京北部与新箱根各三座现有商业楼增加地面门店细节。主要入口、原有楼梯和上层办公室保留，店外铺装与原有入口接齐；两根实际路灯保留。饮料机和邮筒也采用原创几何，没有复制厂商品牌，当前作为环境道具使用。它们与用户要求删除的售票机是不同设施；未恢复售票机。

## AI 辅助地面材质

最终游戏文件：`src/main/resources/assets/projectseele/textures/block/period_station_concrete_r24.png`。使用内置 `image_gen` 生成新图，未使用 CLI 或外部付费插件。原输出保留在本机 `artifacts/facility_r24/materials/generated_concrete_original.png`；以 FFmpeg Lanczos 进行 256×256 的技术缩放后接入方块材质。

完整生成提示词：

> Create ONE original production-ready seamless square albedo texture for a Minecraft block surface, intended for an early-1990s Japanese railway station concourse. Flat orthographic material scan filling the entire image, absolutely no scene, no objects, no typography, no border. Material: well maintained but gently worn fine-aggregate pale warm grey terrazzo-concrete, slightly warm grey base around sRGB #B7B6AE, very small subdued off-white and charcoal aggregate flecks (low contrast, not salt-and-pepper), soft fine mineral variation. Quiet, utilitarian, credible public transport material reminiscent of hand-painted background observation from 1990s Japanese animation but still plausible real material. All four edges must tile seamlessly. NO tile grout grid, NO dramatic cracks, NO directional light, NO cast shadows, NO vignette, NO perspective, NO gloss highlights, NO stains or focal features. Uniform overall value, fine-grained detail that reads as calm flooring at human eye height. Square image, ideally 1024 by 1024.

首次仅用于已检查的四个站点地面，保留盲道、扶梯和原有结构。实机视图、拼接效果与受影响通路的验证记录在 `artifacts/facility_r24`；离线道具图与实际游戏截图分别标记。
