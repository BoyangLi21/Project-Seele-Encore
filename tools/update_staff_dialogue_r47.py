"""Short, role-specific written conversations; never synthesizes character speech."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'src/main/resources/assets/projectseele'
path=ROOT/'src/main/resources/data/projectseele/nerv_dialogue/profiles.json'
data=json.loads(path.read_text('utf8')); p=data['profiles']
p['misato']['duty']=['先确认避难和迎击区。我会盯住出动与回收。','驾驶员的状态也要听他们自己说。检查完了再安排出击。','通信由日向接手，地面情报交给青叶。律子负责机体检查。']
p['misato']['campaign']=['司令，目标情报和迎击区已经在核对。请指定出击机体。']
p['fuyutsuki']['city']=['碇，城市收纳由我来操作。避难完成后再开始。','展开城市前，先确认地面机体和运输设备已经撤离。']
p['fuyutsuki']['duty']=['避难、城市升降和后方支援，我会让各班保持联络。','碇，孩子们的情况也听一听吧。']
p['maya']['duty']=['我负责同步波形、插入栓信号和生体数据。异常会立即报给赤木博士。','记录还要与驾驶员的反应对照，不能只看数值。']
p['hyuga']={'greeting':['司令，作战通信在线。'],'duty':['我负责出动通道、电源状态与回收联络。异常会报给葛城部长。'],'campaign':['目标与迎击区情报正在汇总，出击指令请交给葛城部长。'],'command_denied':['机体调度请联络葛城部长。我负责传达和核对通信。']}
p['aoba']={'greeting':['司令，地面监视在线。'],'duty':['我负责外部雷达、目标轨迹和地面观测。','监视班会持续确认避难区域与目标位置。'],'campaign':['目标轨迹还在更新。我会把最新观测送到战术屏。'],'command_denied':['出击由葛城部长指挥。我负责监视和情报。']}
p['scientist']={'greeting':['实验班在。请注意隔离线。'],'duty':['我负责连接检查和实验记录。参数变更须经赤木博士确认。','LCL循环与生体信号分别记录，异常时先暂停实验。'],'sync':['同步率只是连接状态的一部分，还要核对生体数据和驾驶员反应。'],'plug':['请先确认插入栓固定与通信，再开始实验。'],'power':['实验设备在断电检修前必须解除负载。'],'command_denied':['实验班负责检查与记录。机体出击请联系葛城部长。']}
p['civilian']={'greeting':['你好。','请走人行道。'],'duty':['警报响起时，我们按路牌去避难入口。','道路有施工时，我会绕开设备区。'],'city':['城市升降时请留意避难广播。'],'command_denied':['我不是NERV工作人员，请联系值班人员。']}
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
lines={
 'subtitles.projectseele.transport_engine':('运输机发动机运转','Transport aircraft engine'),
 'subtitles.projectseele.personnel_door_open':('金属门解锁开启','Metal door unlatches'),
 'subtitles.projectseele.personnel_door_close':('金属门关闭锁定','Metal door latches'),
 'subtitles.projectseele.eva_attack_roar':('EVA攻击吼叫','EVA attack roar'),
 'subtitles.projectseele.pressure_door_motion':('舱门滑轨运转','Pressure door track moves'),
 'msg.projectseele.weapon_vault_unit00_only':('仅零号机可领取这面盾牌。','Only Unit-00 can collect this shield.'),
 'msg.projectseele.weapon_vault_unit02_only':('仅二号机可领取这把长剑。','Only Unit-02 can collect this longsword.'),
 'msg.projectseele.shield_deployed':('零号机盾牌已就位。','Unit-00 shield is ready.'),
 'msg.projectseele.sword_deployed':('二号机长剑已就位。','Unit-02 longsword is ready.'),
 'msg.projectseele.synch_test_ready':('同步试验准备就绪，请确认插入栓与通信连接。','Synchronization test ready. Check entry-plug and communications links.'),
 'msg.projectseele.synch_test_run':('同步试验进行中。请保持连接。','Synchronization test in progress. Maintain the connection.'),
 'msg.projectseele.synch_test_result':('同步试验记录：%s','Synchronization test record: %s'),
}
for index,code in enumerate(('zh_cn','en_us')):
 path=ASSET/'lang'/f'{code}.json'; data=json.loads(path.read_text('utf8'))
 data.update({key:text[index] for key,text in lines.items()})
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
print('Written dialogue profiles:',len(p),'localized keys:',len(lines))
