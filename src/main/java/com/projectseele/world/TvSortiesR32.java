package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.ChunkPos;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import java.util.*;

/** A single encounter, with independent original airframes and original riding chains. */
public final class TvSortiesR32
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("tv_sorties_r32",Comparator.comparingLong(ChunkPos::toLong),100);
    public static int slot(EvaUnit01Entity e){return e instanceof EvaPrototypeEntity un?3+un.getUNSerial():e.getUnitVariant();}
    public static String name(int slot){return slot<3?NervStaffDialogue.unitName(slot):"EVA-UN-0"+(slot-3);}
    public static EvaUnit01Entity unit(ServerLevel l,int slot)
    {
        if(slot<3)return EvaLogisticsDirector.canonicalUnit(l,slot);
        var id=UNRecoveryR22.identity(l,slot-3);return id!=null&&l.getEntity(id) instanceof EvaUnit01Entity e?e:null;
    }
    public static boolean ready(EvaUnit01Entity e)
    {return e!=null&&e.getPilotEntity()!=null&&e.isPoweredOn()&&!EvaShutdownR30.disabled(e)&&!e.isNervLogisticsLocked()&&!e.isLaunchSequenceActive()&&!EvaAirTransportR31.active(e);}
    /** Task readiness uses the same original pilot/role predicate as automatic dispatch. */
    public static boolean readyAssigned(ServerLevel level,TvCampaignSavedData.Sortie sortie)
    {
        if(sortie==null)return false;var eva=assignedUnit(level,sortie);
        if(!ready(eva))return false;
        if(sortie.unit<3&&StaffRecoveryR47.pending(level,sortie.unit))return false;
        // UN work is paused; retain its existing readiness behavior.
        return sortie.unit>=3||AutoSortieR32.assignedPilotR45(level,sortie.unit,eva.getPilotEntity());
    }
    /** A later fleet replacement never inherits the accepted original's sortie. */
    public static EvaUnit01Entity assignedUnit(ServerLevel l,TvCampaignSavedData.Sortie sortie)
    {
        var eva=unit(l,sortie.unit);
        return eva!=null&&sortie.eva!=null&&sortie.eva.equals(eva.getUUID())?eva:null;
    }
    public static EvaUnit01Entity assignedUnit(ServerLevel l,TvCampaignSavedData data,int unit)
    {var sortie=data.sorties.get(unit);return sortie==null?null:assignedUnit(l,sortie);}
    public static int reinforce(ServerPlayer caller,int unit,boolean npc,boolean rifle)
    {
        var l=TvCampaignDirector.level(caller);
        if(l==null||l!=caller.level()||!NervStaffDialogue.authorized(caller)||unit<0||unit>4||npc&&unit>2)return 0;
        if(unit<3&&(StaffRecoveryR47.pending(l,unit)||PilotReturnR39.pending(l,unit)))
        {caller.sendSystemMessage(Component.literal("这台机体仍在回收入库，驾驶员交接完成后再加入支援。"));return 0;}
        var d=TvCampaignSavedData.get(l);if(d.active.isEmpty()||Set.of("cancel","failure","combat_victory","episode_archived").contains(d.phase)||d.targetDeathConfirmedR45)return 0;
        String supportBlocker=TvEncounterRulesR45.formationSlotBlockerR47(l,d.active,unit);
        if(!supportBlocker.isEmpty()){caller.sendSystemMessage(Component.literal(supportBlocker));return 0;}
        var current=d.sorties.get(unit);
        if(current!=null)
        {
            boolean same=current.npc==npc&&(npc||caller.getUUID().equals(current.commander));
            caller.sendSystemMessage(Component.literal(name(unit)+(same?"已在出击编队中。"
                    :current.npc?"已编入 NPC 驾驶员；真人驾驶请在开始作战前于编队面板选择。":"已由其他驾驶员编入。")));
            return same?1:0;
        }
        var e=unit(l,unit);
        if(e!=null&&TvMissionEquipmentR45.awaitingPhysicalReturn(e))
        {caller.sendSystemMessage(Component.literal("炮、盾尚未归还，请完成装备回收后再出击。"));return 0;}
        if(e!=null&&e.getPilotEntity()!=null&&(npc?!(e.getPilotEntity() instanceof TrainingPilotEntity pilot&&pilot.getAssignedVariant()==unit):e.getPilotEntity()!=caller))
        {caller.sendSystemMessage(Component.literal("这台机体已有其他驾驶员，不能接管。"));return 0;}
        d.assign(unit,caller.getUUID(),npc,rifle&&npc);
        stampCommanderR55(l,d.sorties.get(unit));
        NervStaffDialogue.say(caller,"葛城美里 · 作战通信",name(unit)+"加入迎击。正在交战的机体继续牵制，支援机到达后从侧面接应。");
        return 1;
    }
    /** Each accepted operation re-stamps its parked originals, so an
     * earlier session's commander cannot veto this crew's launch. */
    public static void stampCommanderR55(ServerLevel l,TvCampaignSavedData.Sortie sortie)
    {
        if(sortie==null||sortie.unit>2)return;var eva=unit(l,sortie.unit);if(eva==null)return;
        var tag=eva.getPersistentData();tag.putUUID("R32SortieCommander",sortie.commander);tag.remove("R32AutoCancelled");
    }
    public static String roster(TvCampaignSavedData data)
    {return "出击编队："+String.join("、",data.sorties.values().stream().map(s->name(s.unit)+"（"+(s.npc?TrainingPilotEntity.pilotName(s.unit):"玩家驾驶")+"）").toList());}
    public static void updateTarget(ServerLevel l,TvCampaignSavedData d)
    {
        if(d.angel==null||!(l.getEntity(d.angel) instanceof Mob enemy))return;
        if(enemy instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(enemy))return;
        var choices=d.sorties.values().stream().filter(s->readyAssigned(l,s)).map(s->assignedUnit(l,s)).filter(e->!e.isFirstBattleActive()).toList();
        if(d.active.equals("ramiel"))
        {
            var shooter=assignedUnit(l,d,1);if(readyAssigned(l,d.sorties.get(1)))enemy.setTarget(shooter);
            return; // Unit00 physically intercepts the ray; proximity is not target priority.
        }
        var nearest=choices.stream().min(Comparator.comparingDouble(enemy::distanceToSqr)).orElse(null);
        var present=enemy.getTarget();
        // Retain an engaged target; switch only after it leaves combat or a much closer support intervenes.
        if(present==null||!choices.contains(present)||nearest!=null&&nearest.distanceToSqr(enemy)<present.distanceToSqr(enemy)*.45)
            enemy.setTarget(nearest);
    }
    public static void continuity(ServerLevel l,TvCampaignSavedData d)
    {
        if(d.active.isEmpty()||d.phase.equals("cancel"))return;
        boolean finishing=Set.of("failure","combat_victory","episode_archived").contains(d.phase)||d.targetDeathConfirmedR45;
        if(!finishing)
        for(var player:l.players())
        {
            var eva=EvaPilotResolver.controlTarget(player);if(eva==null||!NervStaffDialogue.authorized(player))continue;
            int unit=slot(eva);var assigned=d.sorties.get(unit);
            if(assigned!=null&&assigned.eva!=null&&!assigned.eva.equals(eva.getUUID()))continue;
            // Physical boarding alone does not join or overwrite an accepted
            // mission assignment. Use the explicit support/formation request.
            if(assigned==null||assigned.npc||!player.getUUID().equals(assigned.commander))continue;
        }
        for(var s:d.sorties.values())
        {
            var eva=unit(l,s.unit);
            // An explicit accepted assignment binds the loaded canonical airframe
            // once, including NPC sorties before boarding or cargo handoff.
            if(eva!=null&&s.eva==null&&!finishing){s.eva=eva.getUUID();d.setDirty();}
            if(eva!=null&&!eva.getUUID().equals(s.eva))continue;
            if(eva!=null&&!eva.blockPosition().equals(s.position)){s.position=eva.blockPosition();d.setDirty();}
            if(s.npc)
            {
                if(eva!=null&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot
                        &&pilot.getAssignedVariant()==s.unit&&pilot.getVehicle() instanceof EntryPlugCarrierEntity plug
                        &&plug.getLinkedEva()==eva&&plug.getVehicle()==eva)
                {
                    if(s.pilotR45==null&&!finishing){s.pilotR45=pilot.getUUID();d.setDirty();}
                    if(s.pilotR45==null||!s.pilotR45.equals(pilot.getUUID())){eva.stopAutonomousR30();continue;}
                    if(!plug.getUUID().equals(s.plug)){s.plug=plug.getUUID();d.setDirty();}
                }
                continue;
            }
            var player=l.getServer().getPlayerList().getPlayer(s.commander);if(player==null)continue;
            if(player.level()!=l){s.resumePending=s.wasRiding=false;d.setDirty();continue;}
            if(finishing){if(s.resumePending||s.wasRiding){s.resumePending=s.wasRiding=false;d.setDirty();}continue;}
            if(s.resumePending)
            {
                if(++s.resumeTicks>200){s.resumePending=s.wasRiding=false;d.setDirty();continue;}
                if(s.position!=null&&s.resumeTicks%10==1){var chunk=new ChunkPos(s.position);l.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);l.getChunk(s.position);}
                if(eva==null||s.eva==null||!eva.getUUID().equals(s.eva)||!(l.getEntity(s.plug) instanceof EntryPlugCarrierEntity plug))continue;
                if(player.isPassenger()){s.resumePending=false;s.wasRiding=EvaPilotResolver.controlTarget(player)==eva;d.setDirty();continue;}
                if(plug.getLinkedEva()!=eva||plug.getVehicle()!=eva||!plug.isLockedToEva()||!plug.isHatchFullySealed()||eva.getPilotEntity()!=null||plug.isVehicle()||player.distanceToSqr(eva)>128*128||!NervStaffDialogue.authorized(player))
                {s.resumePending=s.wasRiding=false;d.setDirty();continue;}
                if(player.startRiding(plug,true))
                {
                    player.fallDistance=0;plug.syncPilotPositionNow();l.getChunkSource().move(player);
                    var packet=new net.minecraft.network.protocol.game.ClientboundSetPassengersPacket(plug);l.getChunkSource().broadcastAndSend(plug,packet);player.connection.send(packet);
                    s.resumePending=false;s.wasRiding=true;d.setDirty();
                }
                continue;
            }
            boolean riding=eva!=null&&EvaPilotResolver.controlTarget(player)==eva&&player.getVehicle() instanceof EntryPlugCarrierEntity;
            if(riding){s.eva=eva.getUUID();s.plug=player.getVehicle().getUUID();}
            if(s.wasRiding!=riding){s.wasRiding=riding;d.setDirty();}
        }
    }
    /** /seele sortie support: slots 0-2 are the NERV units, 3-4 the UN units. */
    public static LiteralArgumentBuilder<CommandSourceStack> supportCommand()
    {
        return Commands.literal("support").then(Commands.argument("unit",IntegerArgumentType.integer(0,4))
                .then(Commands.literal("player").executes(c->TvCampaignDirector.beginAssigned(c.getSource().getPlayerOrException(),IntegerArgumentType.getInteger(c,"unit"),false,false)))
                .then(Commands.literal("npc").executes(c->TvCampaignDirector.beginAssigned(c.getSource().getPlayerOrException(),IntegerArgumentType.getInteger(c,"unit"),true,true))));
    }
    private TvSortiesR32(){}
}
