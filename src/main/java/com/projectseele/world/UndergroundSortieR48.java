package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervHangarDoorEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Original lower launch-bed exit, bounded physical transfer, and same-bay return. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UndergroundSortieR48
{
    private static final int[] X={-12,30,72},DOOR_Z={-13,-10,-7};
    private static final Set<String> MODES=Set.of("IDLE","OPENING","OUTBOUND","DEPLOYED","RECOVER_OPENING","RETURNING");
    private static final Map<MinecraftServer,Boolean> ENABLED=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<Integer,UUID>> RECOVERY_CALLERS=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("r48_underground_sortie",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final class Row
    {
        UUID eva,owner,pilot;String mode="IDLE",fault="";boolean requested,collisionOpen,launchCancelled;
        Vec3 from=Vec3.ZERO;int age,duration;long lastTick=-1;CompoundTag extra=new CompoundTag();
    }
    private static final class State extends SavedData
    {
        final Map<Integer,Row> rows=new HashMap<>();CompoundTag extra=new CompoundTag();
        static State load(CompoundTag tag)
        {
            var data=new State();data.extra=tag.copy();
            for(var value:tag.getList("Rows",Tag.TAG_COMPOUND))
            {
                var raw=(CompoundTag)value;int v=raw.getInt("Variant");
                if(v<0||v>2||data.rows.containsKey(v))throw new IllegalStateException("Foreign underground sortie target");
                var row=new Row();row.extra=raw.copy();row.mode=raw.getString("Mode");
                if(!MODES.contains(row.mode))throw new IllegalStateException("Unknown underground carrier mode");
                if(raw.hasUUID("Eva"))row.eva=raw.getUUID("Eva");if(raw.hasUUID("Owner"))row.owner=raw.getUUID("Owner");if(raw.hasUUID("Pilot"))row.pilot=raw.getUUID("Pilot");
                row.requested=raw.getBoolean("Open");row.collisionOpen=raw.getBoolean("CollisionOpen");row.launchCancelled=raw.getBoolean("LaunchCancelled");row.age=raw.getInt("Age");row.duration=raw.getInt("Duration");row.fault=raw.getString("Fault");
                row.from=new Vec3(raw.getDouble("FromX"),raw.getDouble("FromY"),raw.getDouble("FromZ"));
                if(!Double.isFinite(row.from.x+row.from.y+row.from.z)||row.age<0||row.duration<0||row.age>row.duration)
                    throw new IllegalStateException("Invalid original underground carrier clock");
                data.rows.put(v,row);
            }
            return data;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            tag=extra.copy();tag.putInt("Version",48);var list=new ListTag();
            rows.forEach((v,row)->{
                var raw=row.extra.copy();raw.putInt("Variant",v);raw.putString("Mode",row.mode);raw.putString("Fault",row.fault);
                if(row.eva!=null)raw.putUUID("Eva",row.eva);if(row.owner!=null)raw.putUUID("Owner",row.owner);if(row.pilot!=null)raw.putUUID("Pilot",row.pilot);
                raw.putBoolean("Open",row.requested);raw.putBoolean("CollisionOpen",row.collisionOpen);raw.putBoolean("LaunchCancelled",row.launchCancelled);raw.putInt("Age",row.age);raw.putInt("Duration",row.duration);
                raw.putDouble("FromX",row.from.x);raw.putDouble("FromY",row.from.y);raw.putDouble("FromZ",row.from.z);list.add(raw);
            });tag.put("Rows",list);return tag;
        }
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_underground_sortie_r48");}
    private static Row row(ServerLevel level,int v){return state(level).rows.computeIfAbsent(v,key->new Row());}
    private static BlockPos bed(int v){return new BlockPos(X[v],-411,-36);}
    private static Vec3 bedFeet(int v){return new Vec3(X[v]+.5,-410,-35.5);}
    private static Vec3 padFeet(int v){return new Vec3(X[v]+.5,-410,6.5);}
    private static int[] planes(int v){return new int[]{-19,-18,-17,DOOR_Z[v]};}
    private static boolean enabled(ServerLevel level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return false;
        return ENABLED.computeIfAbsent(level.getServer(),server->{
            var file=server.getWorldPath(LevelResource.ROOT).resolve("r48_underground_sortie.json");if(!Files.isRegularFile(file))return false;
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(root.get("schema").getAsInt()!=48||!root.get("installed").getAsBoolean()||!root.get("dimension").getAsString().equals("projectseele:geofront"))return false;
                var found=new HashSet<Integer>();
                for(var raw:root.getAsJsonArray("plans"))
                {
                    var plan=raw.getAsJsonObject();int v=plan.get("variant").getAsInt();var b=plan.getAsJsonArray("bed");var p=plan.getAsJsonArray("pad");
                    if(v<0||v>2||!found.add(v)||b.size()!=3||p.size()!=3||b.get(0).getAsInt()!=X[v]||b.get(1).getAsInt()!=-411||b.get(2).getAsInt()!=-36
                            ||p.get(0).getAsInt()!=X[v]||p.get(1).getAsInt()!=-411||p.get(2).getAsInt()!=6||plan.get("clear_width").getAsInt()!=31)return false;
                }
                return found.size()==3;
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("R48 original underground frontage receipt rejected",failure);return false;}
        });
    }
    private static boolean canonical(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        return unit!=null&&unit.isAlive()&&!unit.isExperimentalUnit()&&unit.getUnitVariant()==v&&fleet!=null
                &&fleet.canonicalId().equals(unit.getUUID())&&EvaLogisticsDirector.isAssignedLowerLaunchBed(level,v,bed(v));
    }
    private static boolean authority(ServerPlayer caller,int v,EvaUnit01Entity unit)
    {
        if(caller==null||caller.serverLevel()!=unit.level()||caller.isSpectator()||!caller.isAlive()||!NervStaffDialogue.authorized(caller))return false;
        var pilot=unit.getPilotEntity();if(pilot==null||!pilot.isAlive())return false;
        if(pilot==caller&&EvaPilotResolver.controlTarget(caller)==unit)return true;
        var sortie=TvCampaignSavedData.get(caller.serverLevel()).sorties.get(v);
        return sortie!=null&&caller.getUUID().equals(sortie.commander)&&unit.getUUID().equals(sortie.eva)
                &&pilot.getUUID().equals(sortie.pilotR45)&&!AutoSortieR32.missionToken(caller.serverLevel()).isEmpty();
    }
    private static boolean bound(ServerLevel level,int v,EvaUnit01Entity unit,Row row)
    {return enabled(level)&&canonical(level,v,unit)&&row.eva!=null&&row.eva.equals(unit.getUUID())
            &&unit.getPilotEntity()!=null&&row.pilot!=null&&row.pilot.equals(unit.getPilotEntity().getUUID());}
    private static ServerPlayer owner(ServerLevel level,Row row)
    {return row.owner==null?null:level.getServer().getPlayerList().getPlayer(row.owner);}
    private static void retain(ServerLevel level,int v)
    {
        for(int x=(X[v]-35)>>4;x<=(X[v]+35)>>4;x++)for(int z=-52>>4;z<=17>>4;z++)
        {var p=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,p,2,p);level.getChunk(x,z);}
    }
    private static String dryPlant(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!level.getBlockState(bed(v)).is(Blocks.LODESTONE))return "原下层整备床未就绪。";
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
        if(fleet==null||fleet.lclLayers()!=0||EvaHangarBuilder.countLclEnvelope(level,RegionalFacilityLayout.evaOrigin(level),v)!=0)
            return "原湿舱仍有实际LCL，地下出口保持关闭。";
        if(NervAirLiftR30.ownsMotion(unit)||NervAirLiftR30.waitingAtHead(unit)||com.projectseele.entity.EvaAirTransportR31.active(unit)
                ||com.projectseele.entity.EvaBayRepairR33.active(unit)||unit.refreshTvPersonnelClockHoldR44())return "原机体仍有运输、检修或人员平台动作。";
        if(!EntryPlugDirector.hasLaunchLock(level,v,unit))return "原插入栓、驾驶员或舱盖联锁未完整。";
        return "";
    }
    private static boolean inPortal(int v,BlockPos p)
    {return p.getX()>=X[v]-15&&p.getX()<=X[v]+15&&p.getY()>=-410&&p.getY()<=-346&&Arrays.stream(planes(v)).anyMatch(z->z==p.getZ());}
    private static boolean occupied(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var area=new AABB(X[v]-34,-410,-20,X[v]+35,-345,DOOR_Z[v]+2);
        return !level.getEntities((Entity)null,area,e->e.isAlive()&&!e.isSpectator()&&!(e instanceof NervHangarDoorEntity)
                &&(unit==null||e!=unit&&e.getRootVehicle()!=unit)).isEmpty();
    }
    private static String corridor(ServerLevel level,int v,EvaUnit01Entity unit,Vec3 from,Vec3 to,boolean closedAllowed)
    {
        var body=unit.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(from)
                .minmax(unit.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(to)).deflate(.001);
        for(var p:BlockPos.betweenClosed(BlockPos.containing(body.minX,body.minY,body.minZ),BlockPos.containing(body.maxX,body.maxY,body.maxZ)))
        {
            if(!level.hasChunkAt(p))return "实际承载通路未加载。";
            if(!level.getFluidState(p).isEmpty())return "实际地下通路仍有液体。";
            var block=level.getBlockState(p);
            if(closedAllowed&&inPortal(v,p)&&block.is(Blocks.BARRIER))continue;
            for(var shape:block.getCollisionShape(level,p).toAabbs())if(shape.move(p).intersects(body))return "实际地下承载通路被方块挡住："+p.toShortString();
        }
        if(!level.getEntities((Entity)null,body,e->e.isAlive()&&!e.isSpectator()&&e!=unit&&e.getRootVehicle()!=unit
                &&!(e instanceof NervHangarDoorEntity)).isEmpty())return "地下承载通路有人或其他机体，请先让开。";
        return "";
    }
    private static boolean padSupported(ServerLevel level,int v,EvaUnit01Entity unit)
    {return padSupportFault(level,v,unit).isEmpty();}
    private static String padSupportFault(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(unit.position().distanceToSqr(padFeet(v))>36||Math.abs(unit.getY()+410)>.1)return "请将原机体停回自己的地下接应平台脚位。";
        // Both real feet use one shared pose/world sample. The broad entity
        // box also contains suspended arms and is not a bearing footprint.
        var pose=com.projectseele.entity.EvaBodyPose.sample(unit,1);
        var world=com.projectseele.entity.EvaRifleKinematics.world(unit,1);
        var feet=com.projectseele.entity.EvaBodyPose.posedFootSupportHullsR48(unit,pose,world);
        if(feet.size()!=2)return "原机体共同姿态缺少完整左右足承托数据。";
        for(var foot:feet)
        {
            if(Math.abs(foot.minY+410)>.15)return "原机体足底尚未贴合实际地下平台。";
            if(!level.getEntities((Entity)null,foot.deflate(.001),e->e.isAlive()&&!e.isSpectator()
                    &&e!=unit&&e.getRootVehicle()!=unit
                    &&(e instanceof net.minecraft.world.entity.LivingEntity||e.canBeCollidedWith())).isEmpty())
                return "原机体完整足部承托域有人或实体设备，请先让开。";
            for(var p:BlockPos.betweenClosed(net.minecraft.util.Mth.floor(foot.minX+.001),-411,net.minecraft.util.Mth.floor(foot.minZ+.001),
                    net.minecraft.util.Mth.floor(foot.maxX-.001),-411,net.minecraft.util.Mth.floor(foot.maxZ-.001)))
            {
                // The installed apron is 35x29. Actual feet extend beyond
                // the old 18x18 coarse-box sample; check the real pad boundary.
                if(p.getX()<X[v]-17||p.getX()>X[v]+17||p.getZ()<-12||p.getZ()>16)return "原机体完整足底投影超出自己的平台："+p.toShortString();
                if(!level.hasChunkAt(p))return "实际足底承托格未加载："+p.toShortString();
                if(!level.getFluidState(p).isEmpty())return "实际足底承托格有液体："+p.toShortString();
                if(level.getBlockEntity(p)!=null||!level.getBlockState(p).is(com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get()))
                    return "原平台足底承托格已被未知设施改变："+p.toShortString();
                if(!level.getBlockState(p).isCollisionShapeFullBlock(level,p))return "实际完整足底缺少实体承托："+p.toShortString();
            }
        }
        return "";
    }
    private static boolean doorReady(ServerLevel level,int v)
    {return row(level,v).collisionOpen&&level.getEntitiesOfClass(NervHangarDoorEntity.class,
            new AABB(X[v]-1,-411,DOOR_Z[v]-1,X[v]+2,-409,DOOR_Z[v]+1),e->e.getVariant()==v&&e.getOpenProgress(1)>=.999F).size()==1
            &&completePortalState(level,v,true);}
    private static boolean completePortalState(ServerLevel level,int v,boolean open)
    {
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))
        {
            if(!level.hasChunkAt(p)||level.getBlockEntity(p)!=null||!level.getFluidState(p).isEmpty())return false;
            var block=level.getBlockState(p);if(open?!block.isAir():!block.is(Blocks.BARRIER))return false;
        }
        return true;
    }
    private static boolean neighbourReady(ServerLevel level,int v,boolean carrierTrip)
    {
        for(int other=0;other<3;other++)if(Math.abs(other-v)==1)
        {
            var gate=row(level,other);if(motion(gate))return false;
            if(!carrierTrip)continue;
            if(gate.requested||gate.collisionOpen)return false;
            final int selected=other;var centre=new Vec3(X[other]+.5,-410,DOOR_Z[other]);
            if(level.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(centre,centre).inflate(1),e->e.getVariant()==selected&&e.getOpenProgress(1)>.001F).size()>0)return false;
        }
        return true;
    }
    private static boolean motion(Row row){return Set.of("OPENING","OUTBOUND","RECOVER_OPENING","RETURNING").contains(row.mode);}
    private static EvaLogisticsDirector.ActionResult result(boolean accepted,String text){return new EvaLogisticsDirector.ActionResult(accepted,text);}
    public static EvaLogisticsDirector.ActionResult request(ServerPlayer caller,int v,boolean open)
    {
        var level=caller.serverLevel();if(v<0||v>2||!enabled(level))return result(false,"三座原地下出口尚未安装。");
        EvaLogisticsDirector.loadControlTarget(level,v);retain(level,v);var unit=EvaLogisticsDirector.canonicalUnit(level,v);
        if(!canonical(level,v,unit)||!authority(caller,v,unit))return result(false,"需要本次原机体的驾驶员或已绑定指挥员许可。");
        var row=row(level,v);var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElseThrow();
        if(!open)
        {
            if(Set.of("OUTBOUND","RECOVER_OPENING","RETURNING").contains(row.mode))return result(false,"承载板正在运送原机体，出口暂不关闭。");
            if(row.eva!=null&&!row.eva.equals(unit.getUUID()))return result(false,"门控原机体绑定已变化。");
            row.requested=false;
            if(row.mode.equals("OPENING"))
            {
                if(row.launchCancelled&&fleet.phase()==EvaFleetSavedData.Phase.SILO_READY
                        &&unit.position().distanceToSqr(bedFeet(v))<=.25&&EntryPlugDirector.hasLaunchLock(level,v,unit))unit.armPreparedLaunch(bed(v));
                row.mode="IDLE";row.launchCancelled=false;
            }
            state(level).setDirty();maintainDoor(level,v);
            return result(true,occupied(level,v,null)?"门域有人或机体，出口保持开启直到清空。":"地下出口已请求关闭。");
        }
        if(!Set.of(EvaFleetSavedData.Phase.SILO_READY,EvaFleetSavedData.Phase.DEPLOYED).contains(fleet.phase()))return result(false,"地下出击须先完成原机体整备到SILO_READY。");
        if(motion(row))return result(false,"本原机体的地下门/承载动作已在进行。");
        if(!neighbourReady(level,v,fleet.phase()==EvaFleetSavedData.Phase.SILO_READY))
            return result(false,"相邻出口仍在开门或运送；请先由其操作员关门，保留宽转移架净空。");
        String fault=dryPlant(level,v,unit);if(!fault.isEmpty())return result(false,fault);
        if(occupied(level,v,unit))return result(false,"出口和完整门叶扫掠域有人或设备，请先清空。");
        if(fleet.phase()==EvaFleetSavedData.Phase.SILO_READY)
        {
            if(unit.position().distanceToSqr(bedFeet(v))>.25||unit.hasActiveCarrierMotion()||unit.isLaunchCommandReleased())return result(false,"原下层床尚未停稳或弹射已释放。");
            fault=corridor(level,v,unit,bedFeet(v),padFeet(v),true);if(!fault.isEmpty())return result(false,fault);
            row.mode="OPENING";
        }
        else if(!bound(level,v,unit,row)||!row.mode.equals("DEPLOYED"))return result(false,"此原机体尚未由本地下出口出动。");
        row.eva=unit.getUUID();row.owner=caller.getUUID();row.pilot=unit.getPilotEntity().getUUID();row.requested=true;row.fault="";
        if(row.mode.equals("OPENING"))
        {
            var reserved=EvaLogisticsDirector.requestUndergroundDepartureR48(caller,v,row.eva);
            if(!reserved.accepted()){row.mode="IDLE";row.requested=false;state(level).setDirty();return reserved;}
            row.launchCancelled=true;
        }
        state(level).setDirty();maintainDoor(level,v);
        return result(true,"真正地下出口开始开启，原门全开后承载板连续移至外平台。");
    }
    public static boolean departureAuthorizedR48(ServerPlayer caller,int v,EvaUnit01Entity unit)
    {var level=caller.serverLevel();var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals("OPENING")
            &&caller.getUUID().equals(row.owner)&&authority(caller,v,unit)&&neighbourReady(level,v,true)&&dryPlant(level,v,unit).isEmpty();}
    public static boolean reservesLaunchR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {if(v<0||v>2||!enabled(level))return false;var row=row(level,v);return bound(level,v,unit,row)&&Set.of("OPENING","OUTBOUND").contains(row.mode);}
    public static boolean cancelledReservationR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return reservesLaunchR48(level,v,unit)&&row(level,v).launchCancelled;}
    public static boolean recoveryAuthorizedR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals("RECOVER_OPENING")&&authority(owner(level,row),v,unit)
            &&doorReady(level,v)&&neighbourReady(level,v,true)&&padSupported(level,v,unit)&&dryPlant(level,v,unit).isEmpty();}
    public static boolean finishAuthorizedR48(ServerLevel level,int v,EvaUnit01Entity unit,boolean returning)
    {
        var row=row(level,v);return bound(level,v,unit,row)&&row.mode.equals(returning?"RETURNING":"OUTBOUND")&&row.age>=row.duration
                &&doorReady(level,v)&&authority(owner(level,row),v,unit)&&unit.position().distanceToSqr(returning?bedFeet(v):padFeet(v))<.01
                &&(returning||padSupported(level,v,unit));
    }
    public static boolean deployedBindingR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!enabled(level)||v<0||v>2)return false;var row=row(level,v);
        if(!bound(level,v,unit,row))return false;
        // An original underground unit returned by the existing aircraft to its
        // own surface head keeps the normal surface-descent recovery path.
        if(row.mode.equals("DEPLOYED")&&unit.position().distanceTo(NervAirLiftR30.head(level,v))<10)return false;
        return Set.of("DEPLOYED","RECOVER_OPENING","RETURNING").contains(row.mode);
    }
    public static boolean recoveringR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return enabled(level)&&v>=0&&v<3&&bound(level,v,unit,row(level,v))&&Set.of("RECOVER_OPENING","RETURNING").contains(row(level,v).mode);}
    public static boolean atDeployedPadR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {return deployedBindingR48(level,v,unit)&&row(level,v).mode.equals("DEPLOYED")&&padSupported(level,v,unit);}
    /** A fresh explicit caller context, or an already accepted same-owner staff job, owns recovery. */
    public static EvaLogisticsDirector.ActionResult requestRecoveryR48(ServerPlayer caller,int v)
    {
        var level=caller.serverLevel();if(v<0||v>2||!enabled(level))return result(false,"原地下平台未安装。");
        EvaLogisticsDirector.loadControlTarget(level,v);var unit=EvaLogisticsDirector.canonicalUnit(level,v);var row=row(level,v);
        if(!canonical(level,v,unit)||!bound(level,v,unit,row)||!caller.getUUID().equals(row.owner)||!authority(caller,v,unit))
            return result(false,"需要本原机体地下出动时的操作员与当前驾驶员/编成许可。");
        var contexts=RECOVERY_CALLERS.computeIfAbsent(level,key->new HashMap<>());contexts.put(v,caller.getUUID());
        try{return EvaLogisticsDirector.requestRecovery(level,v);}finally{contexts.remove(v);}
    }
    public static EvaLogisticsDirector.ActionResult recoverR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        var row=row(level,v);var caller=owner(level,row);
        if(!bound(level,v,unit,row)||!authority(caller,v,unit))return result(false,"地下回收的原指挥员/驾驶员绑定已变化。");
        boolean explicit=caller.getUUID().equals(RECOVERY_CALLERS.getOrDefault(level,Map.of()).get(v));
        if(!explicit&&!StaffRecoveryR47.queuedBy(caller,v))return result(false,"请由原操作者下达指挥回收，或使用 /nerv underground recover 指定原机。");
        if(!row.mode.equals("DEPLOYED"))return result(false,"原地下回收已经进行。");
        retain(level,v);
        if(!neighbourReady(level,v,true))return result(false,"相邻地下出口未关闭或承载板仍在运送，地下回收暂缓。");
        String supportFault=padSupportFault(level,v,unit);if(!supportFault.isEmpty())return result(false,supportFault);
        if(!EvaLogisticsDirector.recoveryMotionSettled(unit)||unit.hasActiveCarrierMotion()||unit.isLaunchSequenceActive())
            return result(false,"请将这台原机体开回自己的地下接应平台并停稳。");
        String fault=dryPlant(level,v,unit);if(fault.isEmpty())fault=corridor(level,v,unit,unit.position(),bedFeet(v),true);if(!fault.isEmpty())return result(false,fault);
        row.mode="RECOVER_OPENING";row.requested=true;row.fault="";unit.setNervLogisticsLocked(true);unit.setNoGravity(true);state(level).setDirty();maintainDoor(level,v);
        return result(true,"原地下回收已请求，等真实出口全开后沿同一承载线回库。");
    }
    public static boolean tickMotionR48(ServerLevel level,int v,EvaUnit01Entity unit)
    {
        if(!enabled(level))return false;var row=row(level,v);if(!motion(row))return false;
        if(!bound(level,v,unit,row))return true;retain(level,v);maintainDoor(level,v);unit.setNervLogisticsLocked(true);unit.setNoGravity(true);
        if(!authority(owner(level,row),v,unit)){hold(level,row,"原操作员/驾驶员许可暂时不可用，承载板保持当前位置。");return true;}
        if(!doorReady(level,v)){hold(level,row,"实际地下门尚未全开，或完整门域已变化，承载板保持当前位置。");return true;}
        if(!neighbourReady(level,v,true)){hold(level,row,"相邻原出口/承载板尚未停稳，未改变其他机体或门控。");return true;}
        if(row.mode.equals("OPENING")||row.mode.equals("RECOVER_OPENING"))
        {
            boolean returning=row.mode.equals("RECOVER_OPENING");var caller=owner(level,row);
            var result=returning?EvaLogisticsDirector.requestUndergroundRecoveryR48(level,v,row.eva):EvaLogisticsDirector.requestUndergroundDepartureR48(caller,v,row.eva);
            if(!result.accepted()){hold(level,row,result.message());return true;}
            row.from=unit.position();row.age=0;row.duration=Math.max(80,(int)Math.ceil(row.from.distanceTo(returning?bedFeet(v):padFeet(v))/.25));
            row.mode=returning?"RETURNING":"OUTBOUND";row.fault="";unit.publishAirCarrierFrameR39(row.from,row.from);state(level).setDirty();
        }
        if(row.lastTick==level.getGameTime())return true;row.lastTick=level.getGameTime();
        boolean returning=row.mode.equals("RETURNING");Vec3 destination=returning?bedFeet(v):padFeet(v);
        double previous=row.age/(double)row.duration;previous=previous*previous*(3-2*previous);
        if(unit.position().distanceToSqr(row.from.lerp(destination,previous))>.25)
        {hold(level,row,"原机体位置与持久动作时钟不一致，未执行纠正瞬移。");return true;}
        int age=Math.min(row.duration,row.age+1);
        double t=age/(double)row.duration;t=t*t*(3-2*t);Vec3 next=row.from.lerp(destination,t);
        String fault=corridor(level,v,unit,unit.position(),next,false);if(!fault.isEmpty()){hold(level,row,fault);return true;}
        // Republish an actual one-tick interval: a paused/reloaded persistent clock
        // must not let the client independently run an old full-length trajectory.
        unit.publishAirCarrierFrameR39(unit.position(),next);unit.moveOnNervCarrier(next.x,next.y,next.z,EvaUnit01Entity.SILO_BAY_YAW);row.age=age;row.fault="";state(level).setDirty();
        if(row.age>=row.duration)
        {
            if(!returning)
            {
                String supportFault=padSupportFault(level,v,unit);if(!supportFault.isEmpty()){hold(level,row,supportFault);return true;}
            }
            var result=returning?EvaLogisticsDirector.completeUndergroundRecoveryR48(level,v,row.eva):EvaLogisticsDirector.completeUndergroundDepartureR48(level,v,row.eva);
            if(!result.accepted()){hold(level,row,result.message());return true;}
            row.mode=returning?"IDLE":"DEPLOYED";row.launchCancelled=false;if(returning)row.requested=false;state(level).setDirty();
        }
        return true;
    }
    private static void hold(ServerLevel level,Row row,String reason)
    {
        if(!reason.equals(row.fault)){row.fault=reason;state(level).setDirty();ProjectSeele.LOGGER.warn("R48 original underground carrier held {}: {}",row.eva,reason);}
    }
    private static void maintainDoor(ServerLevel level,int v)
    {
        var row=row(level,v);var centre=new Vec3(X[v]+.5,-410,DOOR_Z[v]);
        if(!level.hasChunkAt(BlockPos.containing(centre)))return;
        var unit=row.eva==null?null:level.getEntity(row.eva) instanceof EvaUnit01Entity eva?eva:null;
        boolean open=row.requested||motion(row)||row.collisionOpen&&occupied(level,v,null);
        NervHangarDoorEntity.reconcile(level,v,centre,open);
        var doors=level.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(centre,centre).inflate(1),e->e.getVariant()==v);
        if(doors.size()!=1)return;float progress=doors.get(0).getOpenProgress(1);
        boolean clear=open&&progress>=.999F,closed=!open&&progress<=.001F;
        if(!clear&&!closed||row.collisionOpen==clear)return;
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))
        {
            if(!level.hasChunkAt(p)||level.getBlockEntity(p)!=null)return;var block=level.getBlockState(p);
            if(row.collisionOpen?!block.isAir():!block.is(Blocks.BARRIER))
            {hold(level,row,"地下门域偏离已记录的完整状态，保持人工/未知修改。");return;}
            if(!level.getFluidState(p).isEmpty()){hold(level,row,"地下门域出现液体，保持原状态。");return;}
        }
        if(closed&&occupied(level,v,null))return;
        if(row.collisionOpen==clear)return;
        var wanted=(clear?Blocks.AIR:Blocks.BARRIER).defaultBlockState();
        for(int z:planes(v))for(var p:BlockPos.betweenClosed(X[v]-15,-410,z,X[v]+15,-346,z))if(!level.getBlockState(p).equals(wanted))level.setBlock(p,wanted,2);
        row.collisionOpen=clear;state(level).setDirty();
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null||!enabled(level))return;
        for(int v=0;v<3;v++)
        {
            var row=row(level,v);var fleet=EvaFleetSavedData.get(level.getServer()).entry(v).orElse(null);
            if(row.mode.equals("DEPLOYED")&&fleet!=null&&fleet.canonicalId().equals(row.eva)
                    &&Set.of(EvaFleetSavedData.Phase.DESCENDING,EvaFleetSavedData.Phase.TO_HANGAR,EvaFleetSavedData.Phase.FILLING,EvaFleetSavedData.Phase.PARKED).contains(fleet.phase()))
            {row.mode="IDLE";row.requested=false;state(level).setDirty();}
            maintainDoor(level,v);
        }
    }
    @SubscribeEvent public static void commands(net.minecraftforge.event.RegisterCommandsEvent event)
    {
        event.getDispatcher().register(net.minecraft.commands.Commands.literal("nerv")
                .then(net.minecraft.commands.Commands.literal("underground")
                .then(net.minecraft.commands.Commands.literal("recover")
                .then(net.minecraft.commands.Commands.argument("unit",com.mojang.brigadier.arguments.IntegerArgumentType.integer(0,2)).executes(context->{
                    var caller=context.getSource().getPlayerOrException();var action=requestRecoveryR48(caller,com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(context,"unit"));
                    caller.sendSystemMessage(net.minecraft.network.chat.Component.literal(action.message()));return action.accepted()?1:0;
                })))));
    }
    private UndergroundSortieR48() { }
}
