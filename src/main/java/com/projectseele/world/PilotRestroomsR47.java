package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCommandSeatEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import java.nio.file.Files;
import java.util.*;

/** World-owned original pilot posts; actual navigation and seats share this one fact source. */
@net.minecraftforge.fml.common.Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class PilotRestroomsR47
{
    public static final String EPOCH="r47-original-pilot-restrooms-v2";
    public static final String SEAT_TAG="seele_pilot_rest_seat_r47";
    private static final UUID[] ORIGINAL={UUID.fromString("142b7a38-691b-403d-8bee-183ac9f44862"),
            UUID.fromString("7618f1cf-a98d-415b-b3c9-8af3f2c1f148"),UUID.fromString("c489a07c-a287-45e1-af09-f9499e4513bb")};
    public record Plan(int variant,String id,UUID pilot,BlockPos chair,String chairState,double seatYOffset,
            Vec3 stand,Vec3 exitMidpoint,Vec3 insideDoor,Vec3 outsideDoor,BlockPos doorLower,String doorState,
            BlockPos goal,List<Vec3> route,BlockPos phone,BlockPos button,BlockPos beacon,String guardId) {}
    private static final Map<ServerLevel,List<Plan>> CACHE=new WeakHashMap<>();
    private static java.nio.file.Path file(ServerLevel level)
    {return level.getServer().getWorldPath(LevelResource.ROOT).resolve("r47_pilot_restrooms.json");}
    public static boolean configured(ServerLevel level){return Files.isRegularFile(file(level));}
    private static Vec3 point(JsonArray a)
    {
        if(a.size()!=3)throw new IllegalArgumentException("Room point must have three coordinates");
        Vec3 p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z))throw new IllegalArgumentException("Nonfinite room point");return p;
    }
    private static BlockPos cell(JsonArray a)
    {
        Vec3 p=point(a);
        if(p.x!=Math.rint(p.x)||p.y!=Math.rint(p.y)||p.z!=Math.rint(p.z))throw new IllegalArgumentException("Fractional room block owner");
        return BlockPos.containing(p);
    }
    public static List<Plan> plans(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION)||!configured(level))return List.of();
        return CACHE.computeIfAbsent(level,key->
        {
            try
            {
                if(Files.size(file(level))>256000)throw new IllegalArgumentException("Oversize room metadata");
                var root=JsonParser.parseString(Files.readString(file(level))).getAsJsonObject();
                if(root.get("schema").getAsInt()!=47||!EPOCH.equals(root.get("epoch").getAsString())
                        ||!"projectseele:geofront".equals(root.get("dimension").getAsString()))throw new IllegalArgumentException("Room epoch/dimension differs");
                var result=new ArrayList<Plan>();var seen=new HashSet<Integer>();var ids=new HashSet<String>();
                for(var item:root.getAsJsonArray("slots"))
                {
                    var row=item.getAsJsonObject();int v=row.get("variant").getAsInt();String id=row.get("id").getAsString();
                    UUID pilot=UUID.fromString(row.get("pilot_uuid").getAsString());
                    if(v<0||v>2||!ORIGINAL[v].equals(pilot)||!seen.add(v)||!ids.add(id)
                            ||!id.equals("r47/pilot_restroom/"+v)
                            ||!row.getAsJsonObject("guard").get("id").getAsString().equals("r47/restroom/security_"+v))throw new IllegalArgumentException("Foreign/duplicate original pilot post");
                    var chair=cell(row.getAsJsonArray("chair"));var stand=point(row.getAsJsonArray("stand"));
                    var exit=point(row.getAsJsonArray("exit_midpoint"));var goal=cell(row.getAsJsonArray("goal"));
                    double offset=row.get("seat_y_offset").getAsDouble();
                    if(!stand.equals(exit)||stand.y!=-394||chair.getY()!=-394||offset!=-.1
                            ||!chair.equals(new BlockPos(6+42*v,-394,-218))
                            ||!stand.equals(new Vec3(6.5+42*v,-394,-219.5))
                            ||!goal.equals(new BlockPos(-10+42*v,-394,-221)))throw new IllegalArgumentException("Room standing/seat/original goal contract differs");
                    if(!row.get("chair_state").getAsString().equals("projectseele:nerv_office_chair[facing=north]")
                            ||!row.get("door_state").getAsString().equals("projectseele:city_personnel_door[facing=east,half=lower,hinge=left,open=false,powered=false]")
                            ||!cell(row.getAsJsonArray("door_lower")).equals(new BlockPos(5+42*v,-394,-221))
                            ||!point(row.getAsJsonArray("inside_door")).equals(new Vec3(6.5+42*v,-394,-220.5))
                            ||!point(row.getAsJsonArray("outside_door")).equals(new Vec3(4.5+42*v,-394,-220.5))
                            ||!cell(row.getAsJsonArray("phone")).equals(new BlockPos(6+42*v,-394,-222))
                            ||!cell(row.getAsJsonArray("button")).equals(new BlockPos(4+42*v,-392,-219))
                            ||!cell(row.getAsJsonArray("beacon")).equals(new BlockPos(5+42*v,-391,-221)))throw new IllegalArgumentException("Room finite hardware anchor differs");
                    var route=new ArrayList<Vec3>();for(var p:row.getAsJsonArray("route"))route.add(point(p.getAsJsonArray()));
                    if(!route.equals(List.of(stand,new Vec3(6.5+42*v,-394,-220.5),new Vec3(5.5+42*v,-394,-220.5),
                            new Vec3(4.5+42*v,-394,-220.5),Vec3.atBottomCenterOf(goal))))throw new IllegalArgumentException("Incomplete actual short route");
                    for(Vec3 p:route)if(p.y!=-394||p.x< -35+42*v||p.x>10+42*v||p.z< -224||p.z> -216)throw new IllegalArgumentException("Room course outside finite dry approach");
                    result.add(new Plan(v,id,pilot,chair,row.get("chair_state").getAsString(),offset,stand,exit,
                            point(row.getAsJsonArray("inside_door")),point(row.getAsJsonArray("outside_door")),
                            cell(row.getAsJsonArray("door_lower")),row.get("door_state").getAsString(),goal,List.copyOf(route),
                            cell(row.getAsJsonArray("phone")),cell(row.getAsJsonArray("button")),cell(row.getAsJsonArray("beacon")),
                            row.getAsJsonObject("guard").get("id").getAsString()));
                }
                if(result.size()!=3)throw new IllegalArgumentException("Three original room posts required");
                result.sort(Comparator.comparingInt(Plan::variant));return List.copyOf(result);
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R47 original pilot room metadata rejected; no legacy respawn/position fallback",failure);return List.of();}
        });
    }
    public static Optional<Plan> plan(ServerLevel level,int variant)
    {return plans(level).stream().filter(p->p.variant==variant).findFirst();}

    /** Exact authorized fixed-room cells, outside the real central bridge lane. */
    public static boolean ownsRoomMaintenanceSpaceR47(ServerLevel level,BlockPos position)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        for(Plan p:plans(level))
        {
            int x=p.doorLower.getX();
            if(position.getX()>=x&&position.getX()<=x+2
                    &&position.getY()>=-395&&position.getY()<=-390
                    &&position.getZ()>=-223&&position.getZ()<=-217)return true;
            if(position.getX()==x-1&&position.getY()==-392
                    &&(position.getZ()==-219||position.getZ()==-222))return true;
        }
        return false;
    }
    public static boolean original(Plan p,TrainingPilotEntity pilot)
    {return p.pilot.equals(pilot.getUUID())&&p.variant==pilot.getAssignedVariant()&&pilot.isAlive();}
    public static boolean atStand(ServerLevel level,Plan p,TrainingPilotEntity pilot)
    {return original(p,pilot)&&TrainingPilotDirector.safeActualFeetR47(level,pilot.position())
            &&Math.abs(pilot.getY()-p.stand.y)<=.08&&pilot.position().multiply(1,0,1).distanceToSqr(p.stand.multiply(1,0,1))<=.65*.65;}
    public static boolean clearStand(ServerLevel level,Plan p,TrainingPilotEntity pilot)
    {return TrainingPilotDirector.safeActualFeetR47(level,p.stand)&&level.noCollision(pilot,new AABB(p.stand.x-.3,p.stand.y+.001,p.stand.z-.3,p.stand.x+.3,p.stand.y+1.8,p.stand.z+.3));}
    public static boolean chairValid(ServerLevel level,Plan p)
    {return level.hasChunkAt(p.chair)&&level.getBlockEntity(p.chair)==null
            &&TvPersonnelPlatformRecipeR44.stateKey(level.getBlockState(p.chair)).equals(p.chairState);}
    public static boolean ownsSeat(ServerLevel level,NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {
        var p=plan(level,pilot.getAssignedVariant());var data=seat.getPersistentData();
        return seat.getType()==ModEntities.PILOT_REST_SEAT_R47.get()&&p.isPresent()&&original(p.get(),pilot)
                &&data.hasUUID("RestroomPilotR47")&&data.getUUID("RestroomPilotR47").equals(pilot.getUUID())
                &&EPOCH.equals(data.getString("RestroomEpochR47"))&&data.getLong("RestroomChairR47")==p.get().chair.asLong()
                &&seat.position().distanceToSqr(new Vec3(p.get().chair.getX()+.5,p.get().chair.getY()+p.get().seatYOffset,p.get().chair.getZ()+.5))<1e-8
                &&chairValid(level,p.get());
    }
    public static boolean isSeated(ServerLevel level,TrainingPilotEntity pilot)
    {return pilot.getVehicle() instanceof NervCommandSeatEntity seat&&ownsSeat(level,seat,pilot)&&seat.getFirstPassenger()==pilot;}
    public static Optional<Vec3> safeDismount(ServerLevel level,NervCommandSeatEntity seat,TrainingPilotEntity pilot)
    {var p=plan(level,pilot.getAssignedVariant());return p.isPresent()&&ownsSeat(level,seat,pilot)&&clearStand(level,p.get(),pilot)?Optional.of(p.get().stand):Optional.empty();}
    public static boolean standUp(ServerLevel level,TrainingPilotEntity pilot)
    {
        if(!(pilot.getVehicle() instanceof NervCommandSeatEntity seat)||safeDismount(level,seat,pilot).isEmpty())return false;
        pilot.stopRiding();return pilot.getVehicle()==null&&plan(level,pilot.getAssignedVariant()).map(p->atStand(level,p,pilot)).orElse(false);
    }
    public static Optional<String> openDoor(ServerLevel level,TrainingPilotEntity pilot)
    {
        var optional=plan(level,pilot.getAssignedVariant());if(optional.isEmpty()||!original(optional.get(),pilot))return Optional.of("原待命室身份未接通。");
        var p=optional.get();var expected=TvPersonnelPlatformRecipeR44.parse(p.doorState);
        for(BlockPos q:List.of(p.doorLower,p.doorLower.above()))
        {
            var actual=level.getBlockState(q);
            if(level.getBlockEntity(q)!=null||!(actual.getBlock() instanceof CityPersonnelDoorR44)
                    ||actual.getValue(DoorBlock.HALF)!=(q.equals(p.doorLower)?net.minecraft.world.level.block.state.properties.DoubleBlockHalf.LOWER:net.minecraft.world.level.block.state.properties.DoubleBlockHalf.UPPER)
                    ||actual.getValue(DoorBlock.FACING)!=expected.getValue(DoorBlock.FACING)
                    ||actual.getValue(DoorBlock.HINGE)!=expected.getValue(DoorBlock.HINGE))return Optional.of("原待命室门框状态不完整。");
        }
        var state=level.getBlockState(p.doorLower);((DoorBlock)state.getBlock()).setOpen(pilot,level,state,p.doorLower,true);return Optional.empty();
    }
    public static void closeDoorWhenClear(ServerLevel level,TrainingPilotEntity pilot)
    {
        var optional=plan(level,pilot.getAssignedVariant());if(optional.isEmpty()||!original(optional.get(),pilot))return;
        var p=optional.get();
        var holds=MANUAL_DOOR_HOLDS_R48.get(level);
        if(holds!=null&&level.getGameTime()<holds.getOrDefault(p.variant,0L))return;
        if(holds!=null)holds.remove(p.variant);
        var state=level.getBlockState(p.doorLower);
        if(!(state.getBlock() instanceof CityPersonnelDoorR44))return;
        var expected=TvPersonnelPlatformRecipeR44.parse(p.doorState);
        for(BlockPos q:List.of(p.doorLower,p.doorLower.above()))
        {
            var actual=level.getBlockState(q);
            if(!(actual.getBlock() instanceof CityPersonnelDoorR44)||level.getBlockEntity(q)!=null
                    ||actual.getValue(DoorBlock.FACING)!=expected.getValue(DoorBlock.FACING)
                    ||actual.getValue(DoorBlock.HINGE)!=expected.getValue(DoorBlock.HINGE)
                    ||actual.getValue(DoorBlock.HALF)!=(q.equals(p.doorLower)?net.minecraft.world.level.block.state.properties.DoubleBlockHalf.LOWER:net.minecraft.world.level.block.state.properties.DoubleBlockHalf.UPPER))return;
        }
        if(!level.getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,
                new AABB(p.doorLower).expandTowards(0,1,0).inflate(.15),e->e.isAlive()&&!e.isSpectator()).isEmpty())return;
        ((DoorBlock)state.getBlock()).setOpen(pilot,level,state,p.doorLower,false);
    }
    private static final Map<ServerLevel,Map<Integer,Long>> MANUAL_DOOR_HOLDS_R48=new WeakHashMap<>();

    /** A manual latch keeps its five-second lease through the original seated AI tick. */
    public static boolean manualDoorR48(ServerLevel level,BlockPos clicked,net.minecraft.server.level.ServerPlayer player)
    {
        var room=plans(level).stream().filter(p->p.doorLower.equals(clicked)||p.doorLower.above().equals(clicked)).findFirst().orElse(null);
        if(room==null)return false;
        if(player.isSpectator()||!NervStaffDialogue.authorized(player)
                ||player.distanceToSqr(Vec3.atCenterOf(room.doorLower))>36)
        {player.displayClientMessage(net.minecraft.network.chat.Component.literal("驾驶员休息室需要NERV通行权限。"),true);return true;}
        var expected=TvPersonnelPlatformRecipeR44.parse(room.doorState);
        for(var q:List.of(room.doorLower,room.doorLower.above()))
        {
            var actual=level.getBlockState(q);
            if(level.getBlockEntity(q)!=null||!(actual.getBlock() instanceof CityPersonnelDoorR44)
                    ||actual.getValue(DoorBlock.FACING)!=expected.getValue(DoorBlock.FACING)
                    ||actual.getValue(DoorBlock.HINGE)!=expected.getValue(DoorBlock.HINGE)
                    ||actual.getValue(DoorBlock.HALF)!=(q.equals(room.doorLower)?net.minecraft.world.level.block.state.properties.DoubleBlockHalf.LOWER:net.minecraft.world.level.block.state.properties.DoubleBlockHalf.UPPER))
            {player.displayClientMessage(net.minecraft.network.chat.Component.literal("休息室完整门框未就绪。"),true);return true;}
        }
        var block=level.getBlockState(room.doorLower);boolean opening=!block.getValue(DoorBlock.OPEN);
        if(opening)
        {
            // The outside floor is a real bridge/pad. A retracted surface must
            // never be replaced by permission or a saved navigation waypoint.
            var fleet=EvaFleetSavedData.get(level.getServer()).entry(room.variant);
            if(fleet.isEmpty()||fleet.get().phase()!=EvaFleetSavedData.Phase.PARKED
                    ||!TrainingPilotDirector.safeActualFeetR47(level,room.outsideDoor)
                    ||!level.noCollision(player,player.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(room.outsideDoor)))
            {player.displayClientMessage(net.minecraft.network.chat.Component.literal("门外平台或登机桥尚未停稳，请等待。"),true);return true;}
            MANUAL_DOOR_HOLDS_R48.computeIfAbsent(level,key->new HashMap<>()).put(room.variant,level.getGameTime()+100);
        }
        else
        {
            if(!level.getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,
                    new AABB(room.doorLower).expandTowards(0,1,0).inflate(.15),e->e.isAlive()&&!e.isSpectator()).isEmpty())
            {player.displayClientMessage(net.minecraft.network.chat.Component.literal("门口有人，请先让出门扇。"),true);return true;}
            var holds=MANUAL_DOOR_HOLDS_R48.get(level);if(holds!=null)holds.remove(room.variant);
        }
        ((DoorBlock)block.getBlock()).setOpen(player,level,block,room.doorLower,opening);return true;
    }

    /** First reassignment is an actual navigation order, never an install teleport. */
    public static void holdOrArrangePost(ServerLevel level,TrainingPilotEntity pilot)
    {
        var optional=plan(level,pilot.getAssignedVariant());if(optional.isEmpty()||!original(optional.get(),pilot))return;
        var p=optional.get();if(isSeated(level,pilot)){closeDoorWhenClear(level,pilot);return;}
        if(pilot.getVehicle()!=null||pilot.getTrainingStage()!=TrainingPilotEntity.STAGE_STANDBY)return;
        if(atStand(level,p,pilot))
        {
            pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);
            pilot.getNavigation().stop();sitAtPost(level,pilot);closeDoorWhenClear(level,pilot);return;
        }
        if(pilot.getTrainingStage()!=TrainingPilotEntity.STAGE_STANDBY
                ||!pilot.getPersistentData().getString("SeelePilotRouteR30").equals("standby")
                ||EPOCH.equals(pilot.getPersistentData().getString("SeelePilotRestroomReassignmentRequestedR47")))return;
        if(TrainingPilotDirector.requestRestroomReturnR47(level,pilot))
            pilot.getPersistentData().putString("SeelePilotRestroomReassignmentRequestedR47",EPOCH);
    }
    @net.minecraftforge.eventbus.api.SubscribeEvent
    public static void retainOriginalPosts(net.minecraftforge.event.TickEvent.ServerTickEvent event)
    {
        if(event.phase!=net.minecraftforge.event.TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        for(var p:plans(level))TrainingPilotDirector.retainOriginalPilotR47(level,p.variant);
    }
    private static final class SeatState extends SavedData
    {
        final Map<Integer,UUID> ids=new HashMap<>();final Set<Integer> materialized=new HashSet<>();CompoundTag extra=new CompoundTag();
        static SeatState load(CompoundTag tag){var s=new SeatState();s.extra=tag.copy();for(var t:tag.getList("Seats",Tag.TAG_COMPOUND)){var r=(CompoundTag)t;int v=r.getInt("Variant");if(v>=0&&v<3&&r.hasUUID("UUID")){s.ids.put(v,r.getUUID("UUID"));if(r.getBoolean("Materialized"))s.materialized.add(v);}}return s;}
        @Override public CompoundTag save(CompoundTag tag){tag=extra.copy();var rows=new net.minecraft.nbt.ListTag();for(var e:ids.entrySet()){var r=new CompoundTag();r.putInt("Variant",e.getKey());r.putUUID("UUID",e.getValue());r.putBoolean("Materialized",materialized.contains(e.getKey()));rows.add(r);}tag.put("Seats",rows);return tag;}
    }
    public static boolean sitAtPost(ServerLevel level,TrainingPilotEntity pilot)
    {
        var optional=plan(level,pilot.getAssignedVariant());if(optional.isEmpty())return false;var p=optional.get();
        if(isSeated(level,pilot))return true;
        if(pilot.getVehicle()!=null||!atStand(level,p,pilot)||!chairValid(level,p)||!clearStand(level,p,pilot))return false;
        if(!level.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.asLong(p.chair)))return false;
        var state=level.getDataStorage().computeIfAbsent(SeatState::load,SeatState::new,"projectseele_pilot_rest_seats_r47");
        UUID id=state.ids.get(p.variant);NervCommandSeatEntity seat=null;
        if(id!=null){var entity=level.getEntity(id);if(entity instanceof NervCommandSeatEntity found)seat=found;else if(state.materialized.contains(p.variant))return false;}
        if(seat==null)
        {
            var other=level.getEntitiesOfClass(NervCommandSeatEntity.class,new AABB(p.chair).inflate(1),net.minecraft.world.entity.Entity::isVehicle);
            if(!other.isEmpty())return false;
            seat=ModEntities.PILOT_REST_SEAT_R47.get().create(level);if(seat==null)return false;
            if(id==null){id=UUID.randomUUID();state.ids.put(p.variant,id);state.setDirty();}seat.setUUID(id);
            seat.addTag(SEAT_TAG);seat.getPersistentData().putUUID("RestroomPilotR47",p.pilot);
            seat.getPersistentData().putString("RestroomEpochR47",EPOCH);seat.getPersistentData().putLong("RestroomChairR47",p.chair.asLong());
            var facing=level.getBlockState(p.chair).getValue(BlockStateProperties.HORIZONTAL_FACING);
            seat.moveTo(p.chair.getX()+.5,p.chair.getY()+p.seatYOffset,p.chair.getZ()+.5,facing.toYRot(),0);
            if(!level.addFreshEntity(seat))return false;state.materialized.add(p.variant);state.setDirty();
        }
        if(!ownsSeat(level,seat,pilot)||seat.getFirstPassenger()!=null)return false;
        if(!pilot.startRiding(seat,true))return false;
        pilot.setTrainingStage(TrainingPilotEntity.STAGE_STANDBY);pilot.setInvisible(false);
        pilot.getPersistentData().putString("SeelePilotRestroomEpochR47",EPOCH);
        pilot.getPersistentData().putString("SeelePilotRouteR30","standby");return true;
    }
    private PilotRestroomsR47() {}
}
