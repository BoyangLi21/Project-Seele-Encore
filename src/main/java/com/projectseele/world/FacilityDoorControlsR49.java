package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.item.NervAccessCardR44;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.block.state.properties.DoorHingeSide;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Explicit installed doors. Neither occupancy, a button nor a lift lease grants a room swipe. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FacilityDoorControlsR49
{
    private static final List<BlockPos> GATE=List.of(new BlockPos(28,-364,315),new BlockPos(29,-364,315));
    private static final Set<BlockPos> READERS=Set.of(new BlockPos(27,-363,314),new BlockPos(27,-363,316));
    private static final List<BlockPos> PILOT=List.of(new BlockPos(7,-394,-223),new BlockPos(49,-394,-223),new BlockPos(91,-394,-223));
    private static final Map<MinecraftServer,Boolean> ENABLED=new WeakHashMap<>();
    private static final Map<ServerLevel,State> STATES=new WeakHashMap<>();
    private record Swipe(UUID player,BlockPos reader,InteractionHand hand,long at) { }
    private static final class State
    {
        final Map<BlockPos,Long> pilotUntil=new HashMap<>();
        final Map<BlockPos,Swipe> swipes=new HashMap<>();
        long gateUntil;
    }
    private static Set<BlockPos> positions(com.google.gson.JsonArray array)
    {
        var set=new HashSet<BlockPos>();
        for(var item:array)
        {
            var p=item.getAsJsonArray();if(p.size()!=3)throw new IllegalArgumentException("Door coordinate length");
            if(!set.add(new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt())))throw new IllegalArgumentException("Duplicate door coordinate");
        }
        return set;
    }
    public static boolean installed(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        return ENABLED.computeIfAbsent(level.getServer(),server->
        {
            var file=server.getWorldPath(LevelResource.ROOT).resolve("r49_facility_controls.json");
            if(!Files.isRegularFile(file))return false;
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(root.get("schema").getAsInt()!=49||!root.get("installed").getAsBoolean()
                        ||!root.get("dimension").getAsString().equals("projectseele:geofront")
                        ||root.get("gate_clearance").getAsInt()!=3
                        ||!positions(root.getAsJsonArray("gate_lower")).equals(new HashSet<>(GATE))
                        ||!positions(root.getAsJsonArray("gate_readers")).equals(READERS))return false;
                var seen=new HashSet<BlockPos>();var variants=new HashSet<Integer>();
                for(var item:root.getAsJsonArray("pilot_guard_doors"))
                {
                    var row=item.getAsJsonObject();int v=row.get("variant").getAsInt();
                    var a=new com.google.gson.JsonArray();a.add(row.getAsJsonArray("lower"));
                    var p=positions(a).iterator().next();
                    if(v<0||v>2||!variants.add(v)||!p.equals(PILOT.get(v))
                            ||!row.get("facing").getAsString().equals("south")||!row.get("hinge").getAsString().equals("right"))return false;
                    seen.add(p);
                }
                return seen.equals(new HashSet<>(PILOT));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R49 exact finite door marker rejected",failure);return false;}
        });
    }
    public static boolean ownsDoor(ServerLevel level,BlockPos pos)
    {return installed(level)&&java.util.stream.Stream.concat(GATE.stream(),PILOT.stream()).anyMatch(p->pos.equals(p)||pos.equals(p.above()));}
    public static boolean protectedReader(ServerLevel level,BlockPos pos)
    {return installed(level)&&READERS.contains(pos);}
    private static boolean validDoor(ServerLevel level,BlockPos lower,DoorHingeSide hinge)
    {
        if(!level.hasChunkAt(lower))return false;
        for(var p:List.of(lower,lower.above()))
        {
            var s=level.getBlockState(p);
            if(!(s.getBlock() instanceof CityPersonnelDoorR44)||level.getBlockEntity(p)!=null
                    ||s.getValue(DoorBlock.FACING)!=Direction.SOUTH||s.getValue(DoorBlock.HINGE)!=hinge
                    ||s.getValue(DoorBlock.HALF)!=(p.equals(lower)?DoubleBlockHalf.LOWER:DoubleBlockHalf.UPPER))return false;
        }
        return true;
    }
    private static boolean occupied(ServerLevel level,BlockPos p,int width)
    {return !level.getEntitiesOfClass(LivingEntity.class,new AABB(p.getX(),p.getY(),p.getZ(),p.getX()+width,p.getY()+2,p.getZ()+1).inflate(.15),e->e.isAlive()&&!e.isSpectator()).isEmpty();}
    private static void door(ServerLevel level,BlockPos p,boolean open)
    {var s=level.getBlockState(p);((DoorBlock)s.getBlock()).setOpen(null,level,s,p,open);}
    public static boolean pilotDoorUse(ServerLevel level,BlockPos clicked,ServerPlayer player)
    {
        if(!installed(level))return false;
        var p=PILOT.stream().filter(q->clicked.equals(q)||clicked.equals(q.above())).findFirst().orElse(null);
        if(p==null)return false;
        if(player.isSpectator()||!NervStaffDialogue.authorized(player)||player.distanceToSqr(Vec3.atCenterOf(p))>36)
        {player.displayClientMessage(Component.literal("驾驶员休息室需要NERV通行权限。"),true);return true;}
        if(!validDoor(level,p,DoorHingeSide.RIGHT))return true;
        boolean open=!level.getBlockState(p).getValue(DoorBlock.OPEN);
        var state=STATES.computeIfAbsent(level,key->new State());
        if(open)
        {
            for(var feet:List.of(new Vec3(p.getX()+.5,p.getY(),-221.5),new Vec3(p.getX()+.5,p.getY(),-223.5)))
                if(!TrainingPilotDirector.safeActualFeetR47(level,feet)||!level.noCollision(player,player.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(feet)))
                {player.displayClientMessage(Component.literal("卫兵侧通道净空不足，请先清理门外。"),true);return true;}
            state.pilotUntil.put(p,level.getGameTime()+100);
        }
        else
        {
            if(occupied(level,p,1))return true;
            state.pilotUntil.remove(p);
        }
        door(level,p,open);return true;
    }
    private static boolean highest(ServerPlayer player,InteractionHand hand)
    {return player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card&&card.clearance()>=3;}
    private static boolean readerValid(ServerLevel level,BlockPos p)
    {
        var s=level.getBlockState(p);
        if(!s.is(ModBlocks.NERV_ACCESS_READER.get())||s.getValue(NervAccessReaderR44.FACING)!=(p.getZ()==314?Direction.NORTH:Direction.SOUTH)
                ||!(level.getBlockEntity(p) instanceof NervAccessReaderEntityR44 reader))return false;
        var tag=reader.saveWithoutMetadata();
        return !tag.getBoolean("Linked")&&tag.getInt("Clearance")==3
                &&level.getBlockState(new BlockPos(27,-363,315)).is(net.minecraft.world.level.block.Blocks.BLACK_CONCRETE);
    }
    private static boolean completeGate(ServerLevel level)
    {return validDoor(level,GATE.get(0),DoorHingeSide.RIGHT)&&validDoor(level,GATE.get(1),DoorHingeSide.LEFT)&&READERS.stream().allMatch(p->readerValid(level,p));}
    private static void visual(ServerLevel level,BlockPos pos,long start,int status)
    {
        if(!(level.getBlockEntity(pos) instanceof NervAccessReaderEntityR44 reader))return;
        CompoundTag tag=reader.saveWithoutMetadata();tag.putBoolean("Linked",false);tag.putLong("SwipeAt",start);
        tag.putInt("Status",status);tag.putInt("Presented",status==1||status==2?3:0);tag.putLong("IndicateUntil",level.getGameTime()+32);
        reader.load(tag);reader.setChanged();level.sendBlockUpdated(pos,level.getBlockState(pos),level.getBlockState(pos),2);
    }
    @SubscribeEvent(priority=EventPriority.HIGHEST)
    public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player)||!installed(player.serverLevel()))return;
        var level=player.serverLevel();var p=event.getPos();
        if(GATE.stream().anyMatch(q->p.equals(q)||p.equals(q.above())))
        {event.setCanceled(true);event.setCancellationResult(InteractionResult.CONSUME);player.displayClientMessage(Component.literal("SEELE门内外均需在读卡器刷最高权限卡。"),true);return;}
        if(!READERS.contains(p))return;
        event.setCanceled(true);event.setCancellationResult(InteractionResult.CONSUME);
        if(player.isSpectator()||player.distanceToSqr(Vec3.atCenterOf(p))>=16||!completeGate(level))return;
        var hand=highest(player,event.getHand())?event.getHand():highest(player,InteractionHand.OFF_HAND)?InteractionHand.OFF_HAND:InteractionHand.MAIN_HAND;
        if(!highest(player,hand)){visual(level,p,-1,3);player.displayClientMessage(Component.literal("权限不足：进出SEELE均需最高权限NERV卡。"),true);return;}
        var state=STATES.computeIfAbsent(level,key->new State());
        if(state.swipes.containsKey(p))return;
        state.swipes.put(p,new Swipe(player.getUUID(),p,hand,level.getGameTime()));visual(level,p,level.getGameTime(),1);player.startUsingItem(hand);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null||!installed(level))return;
        var state=STATES.computeIfAbsent(level,key->new State());long now=level.getGameTime();
        var iterator=state.swipes.entrySet().iterator();
        while(iterator.hasNext())
        {
            var swipe=iterator.next().getValue();if(now-swipe.at()<6)continue;
            var player=event.getServer().getPlayerList().getPlayer(swipe.player());
            boolean permit=player!=null&&player.serverLevel()==level&&!player.isSpectator()&&highest(player,swipe.hand())
                    &&player.distanceToSqr(Vec3.atCenterOf(swipe.reader()))<16&&completeGate(level)
                    &&(swipe.reader().getZ()==314?player.getZ()<315:player.getZ()>316);
            if(permit){state.gateUntil=now+120;SeeleConferenceAccessR47.grantRoomSwipeR49(player,swipe.hand());}
            visual(level,swipe.reader(),swipe.at(),permit?2:3);
            level.playSound(null,swipe.reader(),permit?SoundEvents.NOTE_BLOCK_PLING.value():SoundEvents.NOTE_BLOCK_BASS.value(),SoundSource.BLOCKS,.35F,permit?1.3F:.75F);
            iterator.remove();
        }
        if(completeGate(level))
        {
            boolean wasOpen=GATE.stream().allMatch(p->level.getBlockState(p).getValue(DoorBlock.OPEN));
            if(wasOpen&&now>=state.gateUntil&&occupied(level,GATE.get(0),2))state.gateUntil=now+15;
            for(var p:GATE)door(level,p,now<state.gateUntil);
        }
        for(var p:PILOT)
        {
            if(!validDoor(level,p,DoorHingeSide.RIGHT)||!level.getBlockState(p).getValue(DoorBlock.OPEN))continue;
            if(now>=state.pilotUntil.getOrDefault(p,0L)&&!occupied(level,p,1)){door(level,p,false);state.pilotUntil.remove(p);}
        }
        for(var p:READERS)
            if(level.hasChunkAt(p)&&!state.swipes.containsKey(p)&&level.getBlockEntity(p) instanceof NervAccessReaderEntityR44 reader
                    &&reader.indicator()!=0&&now>reader.saveWithoutMetadata().getLong("IndicateUntil"))visual(level,p,-1,0);
    }
    @SubscribeEvent public static void stopped(ServerStoppedEvent event)
    {ENABLED.remove(event.getServer());STATES.keySet().removeIf(level->level.getServer()==event.getServer());}
    private FacilityDoorControlsR49() { }
}
