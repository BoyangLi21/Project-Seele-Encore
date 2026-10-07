package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Phone requests authorize explicit originals; native wells and machinery execute them. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class StaffOperationsR48
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("armed_sortie_operator_r48",Comparator.comparingLong(ChunkPos::toLong),80);
    private static EvaLogisticsDirector.ActionResult result(boolean accepted,String message)
    { return new EvaLogisticsDirector.ActionResult(accepted,message); }
    private static String callerBlocker(ServerPlayer caller,NervStaffEntity operator,String operation)
    {
        if(operator==null||!operator.isAlive()||operator.level()!=caller.level())return "操作岗位未接通。";
        if(!NervStaffDialogue.authorized(caller)||!StaffAuthorityR25.allows(operator,operation))return "本岗位或通行权限不允许这项操作。";
        if(operator.busy()||StaffCommandBookR24.order(operator)!=null)return "本岗位仍在执行上一项指令，请完成后再安排。";
        return "";
    }
    private static boolean ownAutomaticLaunch(ServerPlayer caller,NervStaffEntity operator,int variant)
    {
        var queued=operator==null?null:StaffCommandBookR24.order(operator);
        return queued!=null&&queued.automatic&&queued.unit==variant&&queued.operation.equals("launch")
                &&queued.owner.equals(caller.getUUID())&&operator.isAlive()&&operator.level()==caller.level()
                &&NervStaffDialogue.authorized(caller)&&StaffAuthorityR25.allows(operator,"deploy")
                &&EvaLogisticsDirector.status(caller.serverLevel(),variant).phase().equals("SILO_READY");
    }
    private static boolean ownAutomaticEquipmentOrder(ServerPlayer caller,NervStaffEntity operator,int variant)
    {
        var queued=operator==null?null:StaffCommandBookR24.order(operator);
        return queued!=null&&queued.automatic&&queued.unit==variant
                &&Set.of("prepare","launch").contains(queued.operation)&&queued.owner.equals(caller.getUUID())
                &&operator.isAlive()&&operator.level()==caller.level()&&NervStaffDialogue.authorized(caller)
                &&StaffAuthorityR25.allows(operator,"campaign");
    }
    private static boolean canonical(ServerLevel level,EvaUnit01Entity eva,int variant)
    {
        return eva!=null&&eva.isAlive()&&!eva.isExperimentalUnit()&&eva.level()==level&&eva.getUnitVariant()==variant
                &&EvaLogisticsDirector.canonicalUnit(level,variant)==eva
                &&EvaFleetSavedData.get(level.getServer()).canonicalId(variant).filter(eva.getUUID()::equals).isPresent();
    }
    private static String targetBlocker(ServerPlayer caller,EvaUnit01Entity eva,int variant,UUID expectedPilot,boolean npcPilot)
    {
        return targetBlocker(caller,eva,variant,expectedPilot,npcPilot,true,true);
    }
    private static String targetBlocker(ServerPlayer caller,EvaUnit01Entity eva,int variant,UUID expectedPilot,boolean npcPilot,boolean preparedLaunchChoice)
    {
        return targetBlocker(caller,eva,variant,expectedPilot,npcPilot,preparedLaunchChoice,false);
    }
    private static String targetBlocker(ServerPlayer caller,EvaUnit01Entity eva,int variant,UUID expectedPilot,boolean npcPilot,
                                        boolean preparedLaunchChoice,boolean equipmentChoice)
    {
        var level=caller.serverLevel();
        if(!canonical(level,eva,variant))return "原机体信号尚未接通，未替换或接管其他机体。";
        var assignment=TvCampaignSavedData.get(level).sorties.get(variant);
        if(assignment!=null&&(!caller.getUUID().equals(assignment.commander)||assignment.npc!=npcPilot
                ||assignment.eva!=null&&!eva.getUUID().equals(assignment.eva)
                ||assignment.pilotR45!=null&&!expectedPilot.equals(assignment.pilotR45)))return "这台机体已有其他驾驶员或指挥员的编成。";
        String phase=EvaLogisticsDirector.status(level,variant).phase();
        boolean gearPreparing=equipmentChoice&&assignment!=null&&eva.getUUID().equals(assignment.eva)
                &&Set.of("PARKED","BRIDGE_RETRACTING","PLUG_INSERTING","PLUG_LOCKING","DRAINING","TO_SILO","SILO_READY").contains(phase);
        var tag=eva.getPersistentData();
        if(equipmentChoice&&AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),
                tag.getString("R43AutoMission"),AutoSortieR32.missionToken(level)))
            return "本次原机体的后续出击已取消，请先重新确认原出击编成，再安排专用装备。";
        AutoSortieR32.acceptOriginalHumanBoardingR50(level,eva,caller);
        if(tag.hasUUID("R32SortieCommander")&&!caller.getUUID().equals(tag.getUUID("R32SortieCommander")))return "机体仍由另一位指挥员受托，请先联系原下令人。";
        var order=StaffCommandBookR24.unitOrder(level,variant);
        if(order!=null&&!(order.automatic&&order.owner.equals(caller.getUUID())
                &&(preparedLaunchChoice&&order.operation.equals("launch")&&phase.equals("SILO_READY")
                    ||gearPreparing&&Set.of("prepare","launch").contains(order.operation))))
            return "这台机体仍有待执行的整备指令，请完成后再安排。";
        if(StaffPilotOrdersR25.pending(level).stream().anyMatch(p->p.unit()==variant
                &&!(gearPreparing&&!p.standby()&&p.caller().equals(caller.getUUID()))))
            return "驾驶员已有待执行的登机或下机指令。";
        if(StaffRecoveryR47.pending(level,variant)||PilotReturnR39.controls(eva)||EvaAirTransportR31.active(eva))return "原机体正在回收或运输，暂时不能追加出击。";
        var actual=eva.getPilotEntity();var plug=EntryPlugDirector.canonical(level,variant);
        if(plug==null||plug.getAssignedVariant()!=variant||plug.getLinkedEva()!=eva)return "原插入栓与机体对应关系未确认。";
        var occupant=plug.getFirstPassenger();
        if(actual!=null&&!expectedPilot.equals(actual.getUUID())||occupant!=null&&!expectedPilot.equals(occupant.getUUID()))return "原插入栓或机体已有其他驾驶员，不能接管。";
        var controlled=EvaPilotResolver.controlTarget(caller);
        if(!npcPilot&&controlled!=null&&controlled!=eva)return "您正在控制另一台机体，请先确认目标。";
        if(!Set.of("PARKED","SILO_READY","DEPLOYED").contains(phase)&&!gearPreparing
                ||eva.isLaunchSequenceActive()&&!(preparedLaunchChoice&&phase.equals("SILO_READY")
                    &&eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_LOCKED&&!eva.isLaunchCommandReleased())
                ||eva.isFirstBattleActive()||EvaShutdownR30.wreck(eva)||EvaBayRepairR33.active(eva)
                ||!phase.equals("PARKED")&&EvaShutdownR30.disabled(eva)
                    &&!(gearPreparing&&EvaShutdownR30.mode(eva)==EvaShutdownR30.EMPTY))return "原机体当前仍在机械作业或停机阶段，未追加出击。";
        return "";
    }
    private static EquipmentVaultsR47.State vaultState(ServerLevel level)
    { return level.getDataStorage().get(EquipmentVaultsR47.State::load,"projectseele_equipment_vaults_r47"); }
    private static UUID loan(ServerLevel level,NervArmamentStationEntity station)
    {
        var state=vaultState(level);String id=station.getPersistentData().getString("R47Vault");
        return state!=null&&!id.isEmpty()&&station.getUUID().equals(state.ids.get(id))?state.loans.get(id):null;
    }
    private static boolean recorded(ServerLevel level,NervArmamentStationEntity station,int payload)
    {
        var state=vaultState(level);String id=station.getPersistentData().getString("R47Vault");
        return station.level()==level&&station.isAlive()&&station.payloadR47()==payload&&state!=null&&!id.isEmpty()
                &&station.getUUID().equals(state.ids.get(id));
    }
    public static EvaLogisticsDirector.ActionResult armedSortie(ServerPlayer caller,NervStaffEntity operator,int variant,boolean npcPilot)
    {
        if(variant!=0&&variant!=2)return result(false,"携盾对应零号机，携剑对应二号机。");
        String blocked=callerBlocker(caller,operator,"campaign");
        if(!blocked.isEmpty()&&!ownAutomaticEquipmentOrder(caller,operator,variant))
            return result(false,blocked);
        var level=caller.serverLevel();
        if(TvCampaignDirector.level(caller)!=level)return result(false,"请进入已配置的NERV作战区域。");
        EvaLogisticsDirector.loadControlTarget(level,variant);var eva=EvaLogisticsDirector.canonicalUnit(level,variant);
        if(!canonical(level,eva,variant))return result(false,"原机体信号尚未接通，请稍候再试。");
        UUID pilotId=caller.getUUID();
        if(npcPilot)
        {
            TrainingPilotDirector.retainOriginalPilotR47(level,variant);
            var pilot=TrainingPilotDirector.existingPilotR45(level,variant);
            if(pilot==null||!pilot.isAlive()||pilot.getAssignedVariant()!=variant)return result(false,"原驾驶员信号尚未接通，未创建替代驾驶员。");
            pilotId=pilot.getUUID();
        }
        blocked=targetBlocker(caller,eva,variant,pilotId,npcPilot);if(!blocked.isEmpty())return result(false,blocked);
        int payload=variant==0?EvaUnit01Entity.WEAPON_SHIELD_R45:EvaUnit01Entity.WEAPON_SWORD_R45;
        var well=EquipmentVaultsR47.recordedStationR47(level,payload);
        if(well==null||!recorded(level,well,payload))return result(false,"对应原武器井尚未接通，未生成替代装备。");
        UUID borrowed=loan(level,well);
        if(borrowed!=null&&!borrowed.equals(eva.getUUID()))return result(false,"这件装备仍由其他原机体借用，等待归还。");
        if(borrowed!=null&&(eva.getArmamentMask()&(1<<payload))==0)return result(false,"原装备借用记录与机体库存不一致，请先检查原交接。");
        if(borrowed==null&&(eva.getArmamentMask()&(1<<payload))!=0)
            return result(false,"机体已有专用装备，但原武器井没有对应借用记录，请核对原交接后再出击。");
        if(borrowed==null&&!well.isStocked())return result(false,"对应原武器井当前空载，请等待装备归还。");
        var saved=ArmedSortieSavedDataR48.get(level);var prior=saved.selection(variant);
        String before=AutoSortieR32.missionToken(level);
        if(prior!=null&&(!prior.owner().equals(caller.getUUID())||!prior.eva().equals(eva.getUUID())
                ||!prior.pilot().equals(pilotId)||prior.npc()!=npcPilot||!prior.mission().equals(before)
                ||prior.phase().equals("return_pending")))return result(false,"原携装安排仍在执行或等待回收，请先完成原交接。");
        if(TvCampaignDirector.beginAssigned(caller,variant,npcPilot,false)==0)return result(false,TvCampaignDirector.briefing(caller));
        String mission=AutoSortieR32.missionToken(level);var sortie=TvCampaignSavedData.get(level).sorties.get(variant);
        if(mission.isEmpty()||sortie==null||!caller.getUUID().equals(sortie.commander)||sortie.npc!=npcPilot)
            return result(false,"当前任务没有接受这台原机体，未安排装备领用。");
        sortie.eva=eva.getUUID();sortie.pilotR45=pilotId;sortie.rifle=false;TvCampaignSavedData.get(level).setDirty();
        var selection=new ArmedSortieSavedDataR48.Selection(variant,payload,caller.getUUID(),eva.getUUID(),pilotId,
                operator.getUUID(),well.getUUID(),mission,npcPilot,borrowed==null?"pending":"issued");
        saved.put(selection);
        if(borrowed==null&&!well.isReadyAndStocked())well.deploy();
        String equipment=variant==0?"盾":"长剑";
        return result(true,borrowed!=null?"原机体已持有借用的"+equipment+"，本次出击继续使用这件原装备。"
                :npcPilot?"携"+equipment+"出击已安排。驾驶员发射后会先到原武器井实际领取，再前往迎击区。"
                :"携"+equipment+"出击已登记。请亲自驾驶原机体，发射后到 "+well.blockPosition().toShortString()+" 的原武器井领取；尚未领取装备。");
    }
    public static String undergroundEquipmentBlockerR49(ServerLevel level,EvaUnit01Entity eva)
    {
        var saved=level.getDataStorage().get(ArmedSortieSavedDataR48::load,"projectseele_armed_sorties_r48");
        var selected=saved==null?null:saved.selection(eva.getUnitVariant());
        if(selected==null||!selected.phase().equals("pending")||!selected.eva().equals(eva.getUUID())
                ||!bindingCurrent(level,selected))return "";
        var well=selectedWell(level,selected);
        boolean sameFloor=well!=null&&EquipmentVaultsR47.physicalHandoffFloorR49(well,eva);
        var known=EquipmentVaultsR47.knownVaultPositionR47(level,selected.payload());
        if(!sameFloor&&(well!=null&&well.getY()>=64||known.isPresent()&&known.get().getY()>=64))
            return "本机已预选地表专用武器井领用，地下出口不能代替该实体交接。领用任务保留，请先走地表出击到原井领取。";
        return "";
    }
    /** Strict caller ownership is retained even when the account has administrator permission. */
    public static EvaLogisticsDirector.ActionResult undergroundExit(ServerPlayer caller,NervStaffEntity operator,int variant,boolean open)
    {
        if(variant<0||variant>2)return result(false,"请指定零号机、初号机或二号机。");
        String blocked=callerBlocker(caller,operator,"deploy");
        boolean replacingOwnAutomaticLaunch=open&&ownAutomaticLaunch(caller,operator,variant);
        if(!blocked.isEmpty()&&!replacingOwnAutomaticLaunch)return result(false,blocked);
        var level=caller.serverLevel();EvaLogisticsDirector.loadControlTarget(level,variant);
        var eva=EvaLogisticsDirector.canonicalUnit(level,variant);var sortie=TvCampaignSavedData.get(level).sorties.get(variant);
        boolean physical=canonical(level,eva,variant)&&eva.getPilotEntity()==caller&&EvaPilotResolver.controlTarget(caller)==eva;
        boolean assigned=sortie!=null&&caller.getUUID().equals(sortie.commander)&&sortie.eva!=null&&sortie.pilotR45!=null
                &&canonical(level,eva,variant)&&eva.getUUID().equals(sortie.eva)&&!AutoSortieR32.missionToken(level).isEmpty();
        if(!physical&&!assigned)return result(false,"您没有控制这台原机体，未改变其地下门。");
        UUID pilot=physical?caller.getUUID():sortie.pilotR45;
        blocked=targetBlocker(caller,eva,variant,pilot,assigned&&sortie.npc,true);if(!blocked.isEmpty())return result(false,blocked);
        var action=UndergroundSortieR48.request(caller,variant,open);
        if(action.accepted()&&open)StaffCommandBookR24.cancelAutomatic(level,variant);
        return action;
    }
    /** The NPC brain sees the bound request, never a nearest replacement well. */
    public static ArmedSortieSavedDataR48.Selection npcSelection(ServerLevel level,EvaUnit01Entity eva,TrainingPilotEntity pilot)
    {
        var selection=ArmedSortieSavedDataR48.get(level).selection(eva.getUnitVariant());
        if(selection==null||!selection.npc()||!selection.phase().equals("pending")||!selection.eva().equals(eva.getUUID())
                ||!selection.pilot().equals(pilot.getUUID())||!bindingCurrent(level,selection))return null;
        var tag=eva.getPersistentData();
        if(tag.hasUUID("R32SortieCommander")&&!selection.owner().equals(tag.getUUID("R32SortieCommander")))return null;
        return selection;
    }
    public static String acquisitionBlocker(ServerLevel level,ArmedSortieSavedDataR48.Selection selection,EvaUnit01Entity eva,TrainingPilotEntity pilot)
    {
        var caller=level.getServer().getPlayerList().getPlayer(selection.owner());
        var operator=originalOperator(level,selection.operator());
        if(caller==null||caller.level()!=level||operator==null||!operator.isAlive()
                ||!NervStaffDialogue.authorized(caller)||!StaffAuthorityR25.allows(operator,"campaign"))return "原指挥链暂未接通，领用等待。";
        if(operator.busy()||StaffCommandBookR24.order(operator)!=null)return "原操作岗位仍在执行指令，领用等待。";
        var sortie=TvCampaignSavedData.get(level).sorties.get(selection.variant());
        if(!canonical(level,eva,selection.variant())||!selection.eva().equals(eva.getUUID())
                ||eva.getPilotEntity()!=pilot||!selection.pilot().equals(pilot.getUUID())||sortie==null||!sortie.npc
                ||!selection.owner().equals(sortie.commander)||!selection.eva().equals(sortie.eva)||!selection.pilot().equals(sortie.pilotR45)
                ||!selection.mission().equals(AutoSortieR32.missionToken(level)))return "原机体、驾驶员或任务绑定已变化，未领用装备。";
        var tag=eva.getPersistentData();
        if(tag.hasUUID("R32SortieCommander")&&!selection.owner().equals(tag.getUUID("R32SortieCommander")))return "原机体指挥权已变化，未领用装备。";
        if(AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),selection.mission()))return "原后续出击安排已取消，未领用装备。";
        if(!EvaEquipmentResourcesR45.ready(eva,selection.payload()))
            return "原专用装备的共同握持或动作资源尚未就绪，原武器井库存保持，未领用替代装备。";
        if(StaffCommandBookR24.unitOrder(level,selection.variant())!=null||StaffRecoveryR47.pending(level,selection.variant())
                ||PilotReturnR39.controls(eva)||EvaAirTransportR31.active(eva)||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()
                ||eva.isFirstBattleActive()||!eva.isPoweredOn()||!EvaLogisticsDirector.status(level,selection.variant()).phase().equals("DEPLOYED"))return "原机体当前不能领用，等待机械作业完成。";
        return "";
    }
    private static NervStaffEntity originalOperator(ServerLevel level,UUID identity)
    {
        if(level.getEntity(identity) instanceof NervStaffEntity actual)return actual;
        var identities=NervStaffSavedData.get(level);
        for(var post:NervStaffDirector.roster(level))if(identity.equals(identities.identity(post.id())))
        {
            var chunk=new ChunkPos(post.feet());level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunkAt(post.feet());
            return level.getEntity(identity) instanceof NervStaffEntity actual?actual:null;
        }
        return null;
    }
    public static NervArmamentStationEntity selectedWell(ServerLevel level,ArmedSortieSavedDataR48.Selection selection)
    {
        var well=EquipmentVaultsR47.recordedStationR47(level,selection.payload());
        return well!=null&&selection.well().equals(well.getUUID())&&recorded(level,well,selection.payload())?well:null;
    }
    public static boolean acquired(ServerLevel level,ArmedSortieSavedDataR48.Selection selection,EvaUnit01Entity eva,NervArmamentStationEntity well)
    {
        if(!bindingCurrent(level,selection)||!canonical(level,eva,selection.variant())
                ||eva.getPilotEntity()==null||!selection.pilot().equals(eva.getPilotEntity().getUUID())
                ||!selection.eva().equals(eva.getUUID())||!selection.well().equals(well.getUUID())
                ||!recorded(level,well,selection.payload())
                ||!selection.eva().equals(loan(level,well))||(eva.getArmamentMask()&(1<<selection.payload()))==0)return false;
        ArmedSortieSavedDataR48.get(level).put(selection.phase("issued"));return true;
    }
    private static boolean bindingCurrent(ServerLevel level,ArmedSortieSavedDataR48.Selection selection)
    {
        var sortie=TvCampaignSavedData.get(level).sorties.get(selection.variant());
        return selection.mission().equals(AutoSortieR32.missionToken(level))&&sortie!=null
                &&selection.owner().equals(sortie.commander)&&selection.eva().equals(sortie.eva)
                &&selection.pilot().equals(sortie.pilotR45)&&selection.npc()==sortie.npc;
    }
    /** A carried weapon requires the original physical loan as well as an installed armament. */
    public static boolean carriesSelectedR48(ServerLevel level,EvaUnit01Entity eva,LivingEntity pilot)
    {
        var selection=ArmedSortieSavedDataR48.get(level).selection(eva.getUnitVariant());
        if(selection==null||pilot==null||!selection.phase().equals("issued")||!bindingCurrent(level,selection)
                ||!canonical(level,eva,selection.variant())||!selection.eva().equals(eva.getUUID())
                ||!selection.pilot().equals(pilot.getUUID())||eva.getPilotEntity()!=pilot)return false;
        var tag=eva.getPersistentData();if(tag.hasUUID("R32SortieCommander")&&!selection.owner().equals(tag.getUUID("R32SortieCommander")))return false;
        var well=selectedWell(level,selection);
        return well!=null&&selection.eva().equals(loan(level,well))&&(eva.getArmamentMask()&(1<<selection.payload()))!=0;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        for(var level:event.getServer().getAllLevels())
        {
            var saved=level.getDataStorage().get(ArmedSortieSavedDataR48::load,"projectseele_armed_sorties_r48");
            if(saved==null)continue;
            for(var selection:saved.selections())
            {
                var well=selectedWell(level,selection);if(well==null)continue;
                UUID borrowed=loan(level,well);
                boolean current=bindingCurrent(level,selection)
                        &&!StaffRecoveryR47.pending(level,selection.variant());
                var eva=EvaLogisticsDirector.canonicalUnit(level,selection.variant());
                if(eva!=null)
                {
                    var tag=eva.getPersistentData();var pilot=eva.getPilotEntity();
                    String phase=EvaLogisticsDirector.status(level,selection.variant()).phase();
                    current&=selection.eva().equals(eva.getUUID())
                            &&(pilot==null||selection.pilot().equals(pilot.getUUID()))
                            &&(!tag.hasUUID("R32SortieCommander")||selection.owner().equals(tag.getUUID("R32SortieCommander")))
                            &&!AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),selection.mission())
                            &&!Set.of("DESCENDING","TO_HANGAR","FILLING","PLUG_ABORT_RETURNING","PLUG_ABORT_DOCKED").contains(phase)
                            &&!PilotReturnR39.controls(eva);
                }
                if(!current||selection.phase().equals("return_pending"))
                {
                    if(borrowed==null)saved.remove(selection.variant());
                    else if(!selection.phase().equals("return_pending"))saved.put(selection.phase("return_pending"));
                    // The original enterHangarStandby -> returnStoredR47 path returns the actual loan.
                    continue;
                }
                if(canonical(level,eva,selection.variant())&&selection.eva().equals(eva.getUUID()))
                {
                    if(selection.phase().equals("pending")&&selection.eva().equals(borrowed))acquired(level,selection,eva,well);
                    else if(selection.phase().equals("issued")&&borrowed==null)saved.remove(selection.variant());
                }
            }
        }
    }
    private StaffOperationsR48() {}
}
