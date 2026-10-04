package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Return orders outlive the battle record, disconnection and a server restart. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class PilotReturnR39
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_pilot_return_r39",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final class Order
    {
        int variant,stalled;UUID unit,commander,pilot;BlockPos position;String stage="WALK";
        double closest=Double.MAX_VALUE;boolean requested;long nextAttempt;
    }
    public static final class State extends SavedData
    {
        final Map<Integer,Order> orders=new LinkedHashMap<>();
        static State load(CompoundTag tag)
        {
            State state=new State();
            for(var raw:tag.getList("Orders",Tag.TAG_COMPOUND))
            {
                var n=(CompoundTag)raw;if(!n.hasUUID("Unit")||!n.hasUUID("Commander"))continue;
                var o=new Order();o.variant=n.getInt("Variant");o.unit=n.getUUID("Unit");o.commander=n.getUUID("Commander");
                if(n.hasUUID("ActualPilotR45"))o.pilot=n.getUUID("ActualPilotR45");
                o.position=BlockPos.of(n.getLong("Position"));o.stage=n.getString("Stage");o.requested=n.getBoolean("Requested");
                o.stalled=n.getInt("Stalled");o.closest=n.contains("Closest")?n.getDouble("Closest"):Double.MAX_VALUE;
                state.orders.put(o.variant,o);
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            var list=new ListTag();for(var o:orders.values())
            {
                var n=new CompoundTag();n.putInt("Variant",o.variant);n.putUUID("Unit",o.unit);n.putUUID("Commander",o.commander);
                n.putLong("Position",o.position.asLong());n.putString("Stage",o.stage);n.putBoolean("Requested",o.requested);
                n.putInt("Stalled",o.stalled);n.putDouble("Closest",o.closest);list.add(n);
                if(o.pilot!=null)n.putUUID("ActualPilotR45",o.pilot);
            }
            tag.put("Orders",list);return tag;
        }
    }
    public static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_pilot_return_r39");}
    public static boolean controls(EvaUnit01Entity unit)
    {
        if(!(unit.level() instanceof ServerLevel level)||unit.isExperimentalUnit())return false;
        var o=state(level).orders.get(unit.getUnitVariant());
        return o!=null&&o.unit.equals(unit.getUUID())&&o.pilot!=null
                &&unit.getPilotEntity() instanceof TrainingPilotEntity pilot&&o.pilot.equals(pilot.getUUID());
    }
    public static void enqueue(ServerLevel level,Collection<TvCampaignSavedData.Sortie> sorties)
    {
        var state=state(level);
        for(var sortie:sorties)
        {
            if(!sortie.npc||sortie.unit>2)continue;
            var entry=EvaFleetSavedData.get(level.getServer()).entry(sortie.unit).orElse(null);
            if(entry==null||sortie.eva==null||!entry.canonicalId().equals(sortie.eva)||sortie.pilotR45==null)continue;
            var o=new Order();o.variant=sortie.unit;o.unit=entry.canonicalId();o.commander=sortie.commander;o.pilot=sortie.pilotR45;
            var unit=ServiceAircraftR32.payload(level,o.unit);
            o.position=unit!=null?unit.blockPosition():sortie.position!=null?sortie.position:BlockPos.containing(NervAirLiftR30.head(level,o.variant));
            state.orders.put(o.variant,o);
            radio(level,o,"mission_return");
        }
        state.setDirty();
    }
    private static void radio(ServerLevel level,Order order,String topic)
    {
        var owner=level.getServer().getPlayerList().getPlayer(order.commander);
        if(owner!=null)NervStaffDialogue.say(owner,TrainingPilotEntity.pilotName(order.variant)+" · 驾驶员通信",StaffDialogueCatalogR24.next(owner,PilotRadioR28.profile(order.variant),"technician",topic));
    }
    private static void retain(ServerLevel level,BlockPos point)
    {var c=new ChunkPos(point);level.getChunkSource().addRegionTicket(TICKET,c,3,c);}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var state=state(level);if(state.orders.isEmpty())return;level.resetEmptyTime();
        for(var order:List.copyOf(state.orders.values()))tickOrder(level,state,order);
    }
    private static void tickOrder(ServerLevel level,State state,Order order)
    {
        var receipt=EvaFleetSavedData.get(level.getServer()).entry(order.variant).orElse(null);
        if(receipt==null||!receipt.canonicalId().equals(order.unit))
        {state.orders.remove(order.variant);state.setDirty();return;}
        retain(level,order.position);EvaLogisticsDirector.loadControlTarget(level,order.variant);
        var unit=ServiceAircraftR32.payload(level,order.unit);if(unit==null)return;
        var campaign=TvCampaignSavedData.get(level);
        if(!campaign.active.isEmpty()&&campaign.sorties.containsKey(order.variant)&&!campaign.phase.equals("combat_victory"))
        {unit.stopAutonomousR30();state.orders.remove(order.variant);state.setDirty();return;}
        order.position=unit.blockPosition();state.setDirty();
        if(receipt.phase()==EvaFleetSavedData.Phase.PARKED)
        {
            unit.stopAutonomousR30();
            if(level.getGameTime()<order.nextAttempt)return;
            order.nextAttempt=level.getGameTime()+20;
            if(TrainingPilotDirector.stop(level,order.variant)<=0)
            {
                if(!order.stage.equals("PILOT_EXIT_WAIT")){order.stage="PILOT_EXIT_WAIT";state.setDirty();}
                return;
            }
            radio(level,order,"back_in_bay");state.orders.remove(order.variant);state.setDirty();return;
        }
        if(receipt.phase()!=EvaFleetSavedData.Phase.DEPLOYED||unit.isFirstBattleActive()||unit.isLaunchSequenceActive()||unit.isBerserk())
        {unit.stopAutonomousR30();return;}
        if(!(unit.getPilotEntity() instanceof TrainingPilotEntity pilot))
        {unit.stopAutonomousR30();state.orders.remove(order.variant);return;}
        if(order.pilot==null||!order.pilot.equals(pilot.getUUID()))
        {unit.stopAutonomousR30();if(!order.stage.equals("IDENTITY_HOLD")){order.stage="IDENTITY_HOLD";state.setDirty();}return;}
        if(NervAirLiftR30.ownsMotion(unit)){unit.stopAutonomousR30();return;}
        Vec3 head=NervAirLiftR30.head(level,order.variant),delta=head.subtract(unit.position());
        double distance=delta.horizontalDistance();
        if((distance<1.5&&Math.abs(delta.y)<8)||NervAirLiftR30.waitingAtHead(unit))
        {
            unit.stopAutonomousR30();
            if(level.getGameTime()<order.nextAttempt)return;order.nextAttempt=level.getGameTime()+20;
            var result=EvaLogisticsDirector.requestRecovery(level,order.variant);
            if(result.accepted()){order.stage="DOCK";ProjectSeele.LOGGER.info("R39 NPC recovery accepted variant={} unit={}",order.variant,order.unit);}
            return;
        }
        if(distance<order.closest-1){order.closest=distance;order.stalled=0;}else order.stalled++;
        boolean air=order.stage.equals("AIR")||distance>640||Math.abs(delta.y)>16||EvaShutdownR30.disabled(unit)||order.stalled>240;
        if(air)
        {
            unit.stopAutonomousR30();order.stage="AIR";
            if(!order.requested)
            {
                radio(level,order,"pickup_request");
                order.requested=true;
            }
            if(level.getGameTime()>=order.nextAttempt)
            {order.nextAttempt=level.getGameTime()+100;NervAirLiftR30.requestPilotReturnR39(level,unit,order.commander);}
            return;
        }
        unit.settleAutonomousAttackR30(pilot);unit.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_FISTS);
        Vec3 desired=delta.multiply(1,0,1).normalize(),steer=Vec3.ZERO;
        for(int angle:new int[]{0,20,-20,45,-45,70,-70})
        {
            Vec3 candidate=desired.yRot((float)Math.toRadians(angle)),step=candidate.scale(Math.min(3,distance));
            retain(level,BlockPos.containing(unit.position().add(step.scale(8))));
            if(CombatSpacingR32.clip(unit,step).horizontalDistanceSqr()<step.horizontalDistanceSqr()*.9)continue;
            if(!level.noCollision(unit,unit.getBoundingBox().deflate(.12).move(step).move(0,.5,0)))continue;
            Vec3 next=unit.position().add(step);
            if(!level.getBlockCollisions(unit,new AABB(next.x-3,next.y-3,next.z-3,next.x+3,next.y+.05,next.z+3)).iterator().hasNext())continue;
            steer=candidate.scale(Math.min(1,distance/8));break;
        }
        unit.autonomousDriveR30(pilot,steer,unit.position().add(desired.scale(30)).add(0,45,0),distance>45);
    }
    private PilotReturnR39() {}
}
