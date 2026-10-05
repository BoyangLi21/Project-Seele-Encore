package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.Holder;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundSoundPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.ButtonBlock;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

/** Finite actual rest-room hardware; no actor movement, inventory issue or world scan. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class PilotRestroomServicesR47
{
    private static final long PHONE_TICKS=1200, RING_TICKS=100, COOLDOWN_TICKS=600;
    private record PhoneCall(ServerLevel level,String room,BlockPos phone,long until) {}
    private static final Map<ServerPlayer,PhoneCall> CALLS=new WeakHashMap<>();
    private static final class Alarm
    {
        long until,next;
        String mission="";
    }
    private static final class State extends SavedData
    {
        final Map<Integer,Alarm> alarms=new HashMap<>();
        static State load(CompoundTag tag)
        {
            var state=new State();
            for(int variant=0;variant<3;variant++)if(tag.contains(Integer.toString(variant)))
            {
                var row=tag.getCompound(Integer.toString(variant));var alarm=new Alarm();
                alarm.until=row.getLong("Until");alarm.next=row.getLong("Next");alarm.mission=row.getString("Mission");
                state.alarms.put(variant,alarm);
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            alarms.forEach((variant,alarm)->{
                var row=new CompoundTag();row.putLong("Until",alarm.until);row.putLong("Next",alarm.next);
                row.putString("Mission",alarm.mission);tag.put(Integer.toString(variant),row);
            });return tag;
        }
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_pilot_restroom_services_r47");}

    private static boolean completePhone(ServerLevel level,BlockPos root)
    {
        if(!level.hasChunkAt(root))return false;
        var base=level.getBlockState(root);
        if(!(base.getBlock() instanceof PeriodFixtureBlock)
                ||base.getValue(PeriodFixtureBlock.KIND)!=PeriodFixtureBlock.Kind.PUBLIC_PHONE
                ||base.getValue(PeriodFixtureBlock.FACING)!=Direction.SOUTH
                ||!(level.getBlockEntity(root) instanceof PeriodFixtureBlockEntity))return false;
        for(int offset=1;offset<=2;offset++)
        {
            var upper=level.getBlockState(root.above(offset));
            if(!(upper.getBlock() instanceof PeriodFixturePartBlock)
                    ||upper.getValue(PeriodFixturePartBlock.OFFSET)!=offset)return false;
        }
        return true;
    }
    public static boolean handlePhoneR47(ServerPlayer player,BlockPos root)
    {
        var level=player.serverLevel();
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        var room=PilotRestroomsR47.plans(level).stream().filter(row->row.phone().equals(root)).findFirst().orElse(null);
        if(room==null)return false; // Other street/public phones keep their original behavior.
        if(player.isSpectator()||!NervStaffDialogue.authorized(player))
        {player.sendSystemMessage(Component.literal("房内指挥电话需要NERV通行权限。"));return true;}
        if(player.distanceToSqr(Vec3.atCenterOf(root))>36||!completePhone(level,root))
        {player.sendSystemMessage(Component.literal("本房电话线路或完整设备尚未接通。"));return true;}
        CALLS.put(player,new PhoneCall(level,room.id(),root,level.getGameTime()+PHONE_TICKS));
        StaffConversationR24.contact(player,"美里");return true;
    }
    public static boolean fixedPhoneAllowedR47(ServerPlayer player)
    {
        var call=CALLS.get(player);if(call==null)return false;
        var level=player.serverLevel();
        boolean valid=call.level==level&&level.getGameTime()<call.until&&!player.isSpectator()
                &&NervStaffDialogue.authorized(player)&&player.distanceToSqr(Vec3.atCenterOf(call.phone))<=36
                &&completePhone(level,call.phone)&&PilotRestroomsR47.plans(level).stream()
                    .anyMatch(room->room.id().equals(call.room)&&room.phone().equals(call.phone));
        if(!valid)CALLS.remove(player);
        return valid;
    }
    private static boolean beaconExists(ServerLevel level,PilotRestroomsR47.Plan room)
    {return level.hasChunkAt(room.beacon())&&level.getBlockState(room.beacon()).is(ModBlocks.NERV_WARNING_BEACON.get());}
    private static void light(ServerLevel level,PilotRestroomsR47.Plan room,boolean lit)
    {
        if(!beaconExists(level,room))return;
        var block=level.getBlockState(room.beacon());
        if(block.getValue(BlockStateProperties.LIT)!=lit)
            level.setBlock(room.beacon(),block.setValue(BlockStateProperties.LIT,lit),Block.UPDATE_CLIENTS);
    }
    private static boolean ring(ServerLevel level,PilotRestroomsR47.Plan room,State state,Alarm alarm,String reason)
    {
        long now=level.getGameTime();
        if(now<alarm.next||!beaconExists(level,room))return false;
        alarm.until=now+RING_TICKS;alarm.next=now+COOLDOWN_TICKS;state.setDirty();light(level,room,true);
        var point=Vec3.atCenterOf(room.beacon());
        // facility_siren has a wide fixed sound range. Send its genuine positional
        // packet only to local listeners instead of broadcasting over that range.
        String response=null;
        if(level.getEntity(room.pilot()) instanceof TrainingPilotEntity pilot&&pilot.isAlive()
                &&pilot.getAssignedVariant()==room.variant()&&pilot.position().distanceToSqr(Vec3.atCenterOf(room.phone()))<=12*12)
            response=TrainingPilotEntity.pilotName(room.variant())+"："+switch(room.variant())
            {case 0->"明白。我会等指挥部通知。";case 1->"听到了。我在这里待命。";default->"听到了。需要出动就通知我。";};
        UUIDGuard guard=guard(level,room);
        for(var listener:level.players())if(!listener.isRemoved()&&listener.position().distanceToSqr(point)<=16*16)
        {
            listener.connection.send(new ClientboundSoundPacket(Holder.direct(ModSounds.FACILITY.get("facility_siren").get()),
                    SoundSource.BLOCKS,point.x,point.y,point.z,.65F,1,level.getRandom().nextLong()));
            listener.sendSystemMessage(Component.literal("[驾驶员休息室 0"+room.variant()+"] "+reason+"。请保持门口通行，联系作战指挥。"));
            if(response!=null)listener.sendSystemMessage(Component.literal(response));
            if(guard.available)listener.sendSystemMessage(Component.literal("["+guard.name+"] 收到。我负责本房门口值守。"));
        }
        return true;
    }
    private record UUIDGuard(boolean available,String name) {}
    private static UUIDGuard guard(ServerLevel level,PilotRestroomsR47.Plan room)
    {
        var id=NervStaffSavedData.get(level).identity(room.guardId());
        if(id!=null&&level.getEntity(id) instanceof NervStaffEntity npc&&npc.isAlive()
                &&npc.memberId().equals(room.guardId())&&npc.staffRole().equals("guard")
                &&npc.position().distanceToSqr(Vec3.atCenterOf(room.button()))<=8*8)
            return new UUIDGuard(true,npc.getName().getString());
        return new UUIDGuard(false,"");
    }
    @SubscribeEvent(priority=EventPriority.LOWEST)
    public static void button(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND||!(event.getEntity() instanceof ServerPlayer player)
                ||!(event.getLevel() instanceof ServerLevel level)||!level.dimension().equals(FacilitySchemaV2.DIMENSION))return;
        var room=PilotRestroomsR47.plans(level).stream().filter(row->row.button().equals(event.getPos())).findFirst().orElse(null);
        if(room==null)return;
        if(player.isSpectator()||!NervStaffDialogue.authorized(player)||player.distanceToSqr(Vec3.atCenterOf(room.button()))>36)
        {event.setCanceled(true);event.setCancellationResult(InteractionResult.FAIL);player.sendSystemMessage(Component.literal("本房警铃需要NERV值班权限。"));return;}
        var hardware=level.getBlockState(room.button());
        if(!hardware.is(Blocks.POLISHED_BLACKSTONE_BUTTON)||hardware.getValue(ButtonBlock.FACE)!=AttachFace.WALL
                ||hardware.getValue(ButtonBlock.FACING)!=Direction.WEST||hardware.getValue(ButtonBlock.POWERED)
                ||!hardware.canSurvive(level,room.button()))return;
        var state=state(level);var alarm=state.alarms.computeIfAbsent(room.variant(),key->new Alarm());
        if(!ring(level,room,state,alarm,"本房警铃已按下"))
        {event.setCanceled(true);event.setCancellationResult(InteractionResult.FAIL);player.sendSystemMessage(Component.literal("本房警铃仍在冷却，或设备未接通。"));}
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null||level.getGameTime()%10!=0)return;
        var rooms=PilotRestroomsR47.plans(level);if(rooms.isEmpty())return;
        var state=state(level);
        var mission=level.getDataStorage().get(TvCampaignSavedData::load,"projectseele_tv_campaign_r24");
        String alert=mission!=null&&mission.owner!=null&&mission.generationR43>0&&!mission.active.isEmpty()
                &&!mission.targetDeathConfirmedR45&&Set.of("alert","approach","combat").contains(mission.phase)
                ?mission.active+"/"+mission.generationR43+"/"+mission.alertStarted:"";
        for(var room:rooms)
        {
            var alarm=state.alarms.computeIfAbsent(room.variant(),key->new Alarm());
            if(!alert.isEmpty()&&!alert.equals(alarm.mission)&&ring(level,room,state,alarm,"已收到本次使徒作战告警"))
            {alarm.mission=alert;state.setDirty();}
            light(level,room,level.getGameTime()<alarm.until);
        }
    }
    private PilotRestroomServicesR47() {}
}
