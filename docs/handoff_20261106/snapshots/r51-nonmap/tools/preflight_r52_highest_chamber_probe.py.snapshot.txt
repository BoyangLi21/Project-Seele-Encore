"""Check exact immutable C9 and local vanilla/native probe APIs without launching."""
from pathlib import Path
import ast,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
C9=ROOT/'artifacts/r52_unified_candidate9/projectseele-0.1.0-all.jar'
EXPECTED='43ae73510b139df1f36d1185a4b9b79965c8b8d141fdcd7916d7d4abacb07357'
CLIENT=Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/net/minecraft/client/1.20.1-20230612.114412/client-1.20.1-20230612.114412-srg.jar')
EVENTBUS=Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/net/minecraftforge/eventbus/6.0.5/eventbus-6.0.5.jar')
JAVAP=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javap.exe')
OUT=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate/HIGHEST_CHAMBER_PROBE_PREFLIGHT.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[]
    def check(name,valid):
        checks.append(dict(check=name,pass_=bool(valid)))
        if not valid:raise AssertionError(name)
    check('Actual immutable C9 bytes match Root SHA',sha(C9)==EXPECTED)
    from prepare_r52_highest_chamber_probe_plan import PINS
    with zipfile.ZipFile(C9)as archive:pins={n:hashlib.sha256(archive.read(n.replace('.','/')+'.class')).hexdigest()for n in PINS}
    checks_by_class={
        'net.minecraft.server.level.ServerPlayerGameMode':['m_7179_(','m_9290_()'],
        'net.minecraft.server.level.ServerPlayer':['f_8941_','m_8999_(','m_143403_(','m_284548_()'],
        'net.minecraft.world.entity.player.Inventory':['f_35977_','m_36026_(','m_36035_(','m_6596_()'],
        'net.minecraft.world.item.ItemStack':['ItemStack(net.minecraft.world.level.ItemLike)'],
        'net.minecraft.world.level.ClipContext':['ClipContext(net.minecraft.world.phys.Vec3, net.minecraft.world.phys.Vec3,'],
        'net.minecraft.world.level.block.state.BlockBehaviour$BlockStateBase':['m_60808_(','m_60795_()'],
        'net.minecraft.world.level.block.entity.BlockEntity':['m_187480_()'],
        'net.minecraft.nbt.CompoundTag':['m_128344_(','m_128425_(','m_128441_(','m_128445_('],
    }
    for cls,tokens in checks_by_class.items():
        text=subprocess.check_output([str(JAVAP),'-p','-cp',str(CLIENT),cls],text=True,encoding='utf8',errors='replace')
        for token in tokens:check('Actual SRG native API '+cls+': '+token,token in text)
    bus=subprocess.check_output([str(JAVAP),'-p','-cp',str(EVENTBUS),'net.minecraftforge.eventbus.api.IEventBus'],text=True,encoding='utf8',errors='replace')
    check('Tools listener can bind real ServerTickEvent with explicit event Class','boolean, java.lang.Class<T>, java.util.function.Consumer<T>'in bus)
    check('Tools native listener can be removed after probe','unregister(java.lang.Object)'in bus)
    source=(ROOT/'tools/java/R52HighestChamberNativeProbeAgent.java').read_text('utf8')
    for forbidden in ['getDeclaredMethod("grant"','new String[]{"grant"','setBlock(','removeBlockEntity(','setBlockEntity(','addRegionTicket(','loadStatic(','openUntil",']:
        check('No direct gate/image/permission mutation: '+forbidden,forbidden not in source)
    check('Native interaction calls vanilla useItemOn','"useItemOn","m_7179_"'in source)
    check('Real outline ray must hit actual reader','"OUTLINE"'in source and '"getBlockPos","m_82425_"'in source)
    check('Permission distance is checked before native use','<16,"Actual native feet are outside'in source)
    check('Expiry observes real native tick before and at deadline','now==until-1'in source and 'now==until&&beforeExpiry'in source)
    check('Complete inventory/mode cleanup exists','backupInventory'in source and '"game_mode_restored"'in source)
    ast.parse((ROOT/'tools/prepare_r52_highest_chamber_probe_plan.py').read_text('utf8'))
    plan=OUT.parent/'highest_chamber_candidate9/C9_PLAN.json'
    if not plan.exists():
        subprocess.check_call(['python',str(ROOT/'tools/prepare_r52_highest_chamber_probe_plan.py'),'--jar',str(C9),'--output',str(plan)])
    prepared=json.loads(plan.read_text('utf8'));check('Concrete C9 probe plan pins exactly current immutable class bytes',prepared['candidate_jar_sha256']==EXPECTED and prepared['loaded_class_sha256']==pins)
    report=dict(world_opened=False,game_started=False,native_executed=False,native_passed=False,candidate_jar_sha256=EXPECTED,
                class_pins=pins,checks=checks,concrete_plan=str(plan),probe_source_sha256=sha(ROOT/'tools/java/R52HighestChamberNativeProbeAgent.java'),
                agent_sha256=sha(ROOT/'.Codex/r52_owner_draft/r52_highest_chamber_native_probe_agent.jar'),
                scope='Static exact-C9/native-API preflight only. Root must execute the concrete probe in the actual used QA; visual review remains separate.')
    OUT.write_text(json.dumps(report,indent=2)+'\n','utf8');print(json.dumps(dict(checks=len(checks),plan=str(plan),native_executed=False)))
if __name__=='__main__':main()
