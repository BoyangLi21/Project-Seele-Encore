package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** NERV's airport-based VTOL recovers the registered airframe to its own surface head. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervAirLiftR30
{
    private enum Phase { PREPARE, TAKEOFF, FERRY, APPROACH, CLAMP, ASCEND, CRUISE, DESCEND, RELEASE, RETREAT, RETURN, LAND, HOLD }
    public static final Vec3 STAND=new Vec3(1200.5,84,20.5);
    private static final double OFFSET=TransportClearanceR30.HOIST_OFFSET;
    private static final TicketType<ChunkPos> TICKET=TicketType.create("nerv_airlift_r30",Comparator.comparingLong(ChunkPos::toLong),120);
    private static final class Job
    {
        UUID unit,owner;int variant,age,duration,contactTicks;boolean touchdown;Phase phase=Phase.PREPARE;boolean returning,carrying,crew,rebase,paused,tilting;
        float landingYaw=EvaUnit01Entity.SILO_BAY_YAW;
        long nextReport;
        Vec3 from=Vec3.ZERO,to=Vec3.ZERO,destination=Vec3.ZERO;String note="接收运输指令";
    }
    public static final class State extends SavedData
    {
        UUID aircraft;Vec3 aircraftAt=STAND;Job job;String last="NERV 重型运输机在机场待命";
        CompoundTag aircraftBackup=new CompoundTag();int aircraftMissingTicks;boolean forceRecovery;
        final Map<Integer,BlockPos> locations=new HashMap<>();
        static State load(CompoundTag t)
        {
            var s=new State();if(t.hasUUID("Aircraft"))s.aircraft=t.getUUID("Aircraft");if(t.contains("AircraftX"))s.aircraftAt=vec(t,"Aircraft");s.last=t.getString("Last");s.aircraftBackup=t.getCompound("AircraftBackupR32").copy();
            s.forceRecovery=t.getBoolean("ForceRecoveryR38");
            for(int i=0;i<3;i++)if(t.contains("Location"+i))s.locations.put(i,BlockPos.of(t.getLong("Location"+i)));
            if(t.contains("Job"))
            {
                var n=t.getCompound("Job");var j=new Job();j.unit=n.getUUID("Unit");j.owner=n.getUUID("Owner");j.variant=n.getInt("Variant");j.phase=Phase.valueOf(n.getString("Phase"));j.age=n.getInt("Age");j.landingYaw=n.contains("LandingYawR32")?n.getFloat("LandingYawR32"):EvaUnit01Entity.SILO_BAY_YAW;j.duration=n.getInt("Duration");j.returning=n.getBoolean("Returning");j.carrying=n.getBoolean("Carrying");j.crew=n.getBoolean("Crew");j.from=vec(n,"From");j.to=vec(n,"To");j.destination=vec(n,"Destination");j.note=n.getString("Note");j.touchdown=n.getBoolean("TouchdownR40");j.rebase=true;s.job=j;
            }return s;
        }
        @Override public CompoundTag save(CompoundTag t)
        {
            if(aircraft!=null)t.putUUID("Aircraft",aircraft);put(t,"Aircraft",aircraftAt);t.putString("Last",last);t.put("AircraftBackupR32",aircraftBackup.copy());t.putBoolean("ForceRecoveryR38",forceRecovery);locations.forEach((i,p)->t.putLong("Location"+i,p.asLong()));
            if(job!=null)
            {
                var j=job;var n=new CompoundTag();n.putUUID("Unit",j.unit);n.putUUID("Owner",j.owner);n.putInt("Variant",j.variant);n.putString("Phase",j.phase.name());n.putInt("Age",j.age);n.putFloat("LandingYawR32",j.landingYaw);n.putInt("Duration",j.duration);n.putBoolean("Returning",j.returning);n.putBoolean("Carrying",j.carrying);n.putBoolean("Crew",j.crew);put(n,"From",j.from);put(n,"To",j.to);put(n,"Destination",j.destination);n.putString("Note",j.note);n.putBoolean("TouchdownR40",j.touchdown);t.put("Job",n);
            }return t;
        }
    }
    private static Vec3 vec(CompoundTag t,String k){return new Vec3(t.getDouble(k+"X"),t.getDouble(k+"Y"),t.getDouble(k+"Z"));}
    private static void put(CompoundTag t,String k,Vec3 v){t.putDouble(k+"X",v.x);t.putDouble(k+"Y",v.y);t.putDouble(k+"Z",v.z);}
    public static State state(ServerLevel l){return l.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_nerv_airlift_r30");}
    public static Vec3 head(ServerLevel l,int unit){var p=EvaLogisticsDirector.surfaceTransportBedR30(l,unit);return new Vec3(p.getX()+.5,p.getY()+2,p.getZ()+.5);}
    public static boolean waitingAtHead(EvaUnit01Entity e){return e.level() instanceof ServerLevel l&&!e.isExperimentalUnit()&&e.getPersistentData().getBoolean("R30AwaitingNervRecovery")&&e.position().distanceToSqr(head(l,e.getUnitVariant()).add(0,e.getPersistentData().getDouble("R39LandingLift"),0))<.25;}
    public static boolean ownsMotion(EvaUnit01Entity e)
    {
        if(!(e.level() instanceof ServerLevel l))return false;var j=state(l).job;
        return j!=null&&j.unit.equals(e.getUUID())&&Set.of(Phase.APPROACH,Phase.CLAMP,Phase.ASCEND,Phase.CRUISE,Phase.DESCEND,Phase.RELEASE,Phase.HOLD).contains(j.phase);
    }
    public static String status(ServerLevel l){var s=state(l);return s.forceRecovery?s.last:s.job==null?s.last:NervStaffDialogue.unitName(s.job.variant)+"："+s.job.note;}
    public static String forceRecover(ServerLevel level)
    {
        if(!Files.isRegularFile(level.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_transport_r30.json")))return "此存档尚未安装 NERV 重型运输设施。";
        var s=state(level);s.forceRecovery=true;s.last="强制回收已受理，正在加载原运输机和载荷。";s.setDirty();return s.last;
    }
    public static CompoundTag inspectionR38(ServerLevel level){return state(level).save(new CompoundTag());}
    public static boolean stageCarriedReviewR38(ServerLevel level,int variant,UUID owner)
    {
        if(!"r38-recovery".equals(System.getProperty("projectseele.regionalBuild"))||!level.getServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_FIELD_R38_REVIEW"))throw new IllegalStateException("Isolated cargo fixture only");
        var s=state(level);boolean airport=ready(level,STAND,4);var known=s.locations.get(variant);if(known!=null)ready(level,Vec3.atCenterOf(known),4);
        EvaLogisticsDirector.loadControlTarget(level,variant);var receipt=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        var unit=receipt==null?null:ServiceAircraftR32.payload(level,receipt.canonicalId());var plane=ServiceAircraftR32.find(level,s.aircraft);
        if(unit==null||plane==null||!airport)return false;
        var job=new Job();job.variant=variant;job.unit=unit.getUUID();job.owner=owner;job.phase=Phase.HOLD;job.carrying=true;job.returning=true;job.destination=head(level,variant);job.from=STAND.add(0,160,0);job.to=job.from;job.duration=100;
        EvaAirTransportR31.begin(unit);lock(unit);EvaAirTransportR31.transition(unit,90,1,1);unit.moveOnNervCarrier(job.from.x,job.from.y,job.from.z,0);
        plane.setPos(job.from.add(0,OFFSET,0));plane.cargo(unit.getId(),true,1);s.aircraftAt=plane.position();s.locations.put(variant,unit.blockPosition());s.job=job;s.setDirty();return true;
    }
    @SubscribeEvent public static void commands(net.minecraftforge.event.RegisterCommandsEvent event)
    {
        event.getDispatcher().register(net.minecraft.commands.Commands.literal("nerv")
            .then(net.minecraft.commands.Commands.literal("transport").requires(source->source.hasPermission(2))
                .then(net.minecraft.commands.Commands.literal("status").executes(c->{var l=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return 0;c.getSource().sendSuccess(()->Component.literal(status(l)),false);return 1;}))
                .then(net.minecraft.commands.Commands.literal("force_recover").executes(c->{var l=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return 0;String reply=forceRecover(l);c.getSource().sendSuccess(()->Component.literal(reply),true);return 1;}))));
    }
    private static void completeForcedRecovery(ServerLevel l,State s)
    {
        if(!ready(l,STAND,3)||!ready(l,s.aircraftAt,4))return;
        var plane=ServiceAircraftR32.find(l,s.aircraft);if(plane==null)plane=restoreAircraft(l,s);if(plane==null)return;
        var job=s.job;boolean returnedCargo=false;
        if(job!=null&&(job.carrying||ownsRegisteredCargo(s)))
        {
            ready(l,Vec3.atCenterOf(s.locations.getOrDefault(job.variant,BlockPos.containing(head(l,job.variant)))),3);
            EvaLogisticsDirector.loadControlTarget(l,job.variant);
            var unit=ServiceAircraftR32.payload(l,job.unit);Vec3 destination=head(l,job.variant);
            var registration=EvaFleetSavedData.get(l.getServer()).entry(job.variant).orElse(null);
            boolean stale=unit==null&&registration!=null&&!registration.canonicalId().equals(job.unit);
            if(!stale&&(unit==null||!ready(l,destination,4)))return;
            if(stale)com.projectseele.ProjectSeele.LOGGER.warn("R38 cleared stale airlift reference {}; current registered EVA {} retained",job.unit,registration.canonicalId());
            else
            {
            // The original EVA/plug/crew are retained; emergency maintenance
            // bypasses a stuck flight path without dropping or healing cargo.
            unit.disconnectForAirliftR32();unit.normalizeAfterTransportR30(false);
            unit.moveOnNervCarrier(destination.x,destination.y,destination.z,EvaUnit01Entity.SILO_BAY_YAW);
            unit.setNervLogisticsLocked(true);unit.setNoGravity(true);unit.setOnGround(true);unit.resetFallDistance();
            unit.getPersistentData().remove("R39LandingLift");unit.getPersistentData().putBoolean("R30AwaitingNervRecovery",true);EvaShutdownR30.waitingR31(unit,true);
            s.locations.put(job.variant,unit.blockPosition());
            returnedCargo=true;
            }
        }
        plane.cargo(-1,false,0);plane.teleportTo(STAND.x,STAND.y,STAND.z);plane.setYRot(0);plane.setDeltaMovement(Vec3.ZERO);
        s.aircraftAt=STAND;s.aircraftBackup=plane.saveWithoutId(new CompoundTag());s.job=null;s.forceRecovery=false;s.aircraftMissingTicks=0;
        s.last=returnedCargo?"NERV 运输机已强制返回机场；原机体交付原发射井顶部，等待常规回收。":"NERV 运输机已返回机场，旧任务已清理；当前登记机体的位置保持不变。";s.setDirty();
        com.projectseele.ProjectSeele.LOGGER.info("R38 NERV force recovery completed aircraft={} cargo={}",s.aircraft,job==null?null:job.unit);
    }
    private static boolean ownsRegisteredCargo(State state)
    {return state.job!=null&&Set.of(Phase.APPROACH,Phase.CLAMP,Phase.ASCEND,Phase.CRUISE,Phase.DESCEND,Phase.RELEASE,Phase.HOLD).contains(state.job.phase);}
    public static String phaseName(ServerLevel l){var j=state(l).job;return j==null?"IDLE":j.phase.name();}
    public static boolean busy(ServerLevel level){var s=state(level);return s.job!=null||s.forceRecovery;}
    /** Called before a maintenance reset of this same registered airframe. */
    public static boolean abortForMaintenanceR47(ServerLevel level,int variant,UUID original)
    {
        var s=state(level);var job=s.job;if(job==null)return true;
        if(job.variant!=variant||original==null||!job.unit.equals(original))return false;
        var unit=ServiceAircraftR32.payload(level,original);
        if(unit==null||!ready(level,STAND,3)||!ready(level,s.aircraftAt,4))return false;
        var plane=ServiceAircraftR32.find(level,s.aircraft);if(plane==null)return false;
        unit.endNervCarrierMotion();EvaAirTransportR31.hold(unit);
        plane.cargo(-1,false,0);plane.setPos(STAND);plane.setYRot(0);plane.setDeltaMovement(Vec3.ZERO);
        s.aircraftAt=STAND;s.aircraftBackup=plane.saveWithoutId(new CompoundTag());s.job=null;s.forceRecovery=false;
        s.last="运输后续已交由原机体维护复位，原运输机返回机场。";s.setDirty();return true;
    }
    private static void report(ServerLevel level,State s,Job job)
    {
        long now=System.currentTimeMillis();
        if(job.nextReport==0||job.nextReport>now+10000){job.nextReport=now+10000;return;}
        if(now<job.nextReport)return;job.nextReport=now+10000;
        var owner=level.getServer().getPlayerList().getPlayer(job.owner);
        if(owner!=null)owner.sendSystemMessage(Component.literal("[NERV 运输管制] "+BlockPos.containing(s.aircraftAt).toShortString()+" · "+job.note));
    }
    public static String request(ServerPlayer p,int variant,boolean returning,int x,int z)
    {
        if(variant<0||variant>2||!NervStaffDialogue.authorized(p)||!StaffConversationR24.radioAllowed(p))return "需要 NERV 指挥通信权限。";
        var l=p.serverLevel();if(!l.dimension().equals(FacilitySchemaV2.DIMENSION))return "请先进入第三新东京市。";
        if(!Files.isRegularFile(l.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_transport_r30.json")))return "机场重型运输区尚未交付。";
        var s=state(l);if(s.job!=null)return "运输机已有任务："+s.job.note;
        var receipt=EvaFleetSavedData.get(l.getServer()).entry(variant).orElse(null);
        if(receipt==null)return "未找到原机体登记。";
        if(receipt.phase()!=EvaFleetSavedData.Phase.DEPLOYED)return "地下机库与发射井禁止直接起吊。请先完成正常发射，让机体抵达地表。";
        if(Math.abs((long)x)>29999000||Math.abs((long)z)>29999000||!l.getWorldBorder().isWithinBounds(new BlockPos(x,80,z)))return "指定位置超出世界边界。";
        var e=EvaLogisticsDirector.canonicalUnit(l,variant);
        if(e!=null&&e.getPilotEntity() instanceof ServerPlayer pilot&&pilot!=p)return "请由当前驾驶员本人呼叫空运，或先让驾驶员离开插入栓。";
        var j=new Job();j.variant=variant;j.unit=receipt.canonicalId();j.owner=p.getUUID();j.returning=returning;j.crew=e!=null&&e.getPilotEntity()==p;j.destination=returning?head(l,variant):new Vec3(x+.5,0,z+.5);s.job=j;s.setDirty();return "运输部门收到。正在确认机体身份、地表净空与降落位置。";
    }
    /** Called only by a persisted, completed NPC sortie; it does not require the commander online. */
    public static boolean requestPilotReturnR39(ServerLevel level,EvaUnit01Entity unit,UUID commander)
    {
        var s=state(level);if(s.job!=null||s.forceRecovery)return false;
        if(unit.isExperimentalUnit()||!(unit.getPilotEntity() instanceof TrainingPilotEntity))return false;
        var receipt=EvaFleetSavedData.get(level.getServer()).entry(unit.getUnitVariant()).orElse(null);
        if(receipt==null||receipt.phase()!=EvaFleetSavedData.Phase.DEPLOYED||!receipt.canonicalId().equals(unit.getUUID()))return false;
        var j=new Job();j.variant=unit.getUnitVariant();j.unit=unit.getUUID();j.owner=commander;
        j.returning=true;j.destination=head(level,j.variant);s.locations.put(j.variant,unit.blockPosition());s.job=j;s.setDirty();return true;
    }

    public static String cancel(ServerPlayer p)
    {
        var s=state(p.serverLevel());var j=s.job;if(j==null)return "运输机待命中。";
        if(!j.owner.equals(p.getUUID())&&!p.hasPermissions(2))return "请由下达运输指令的人取消。";
        if(j.phase==Phase.PREPARE){s.job=null;s.last="运输指令已取消";s.setDirty();return s.last;}
        if(j.phase==Phase.HOLD&&!j.carrying){if(p.serverLevel().getEntity(j.unit) instanceof EvaUnit01Entity e)e.normalizeAfterTransportR30(false);j.phase=Phase.RETREAT;j.from=s.aircraftAt;j.to=new Vec3(s.aircraftAt.x,cruise(p.serverLevel()),s.aircraftAt.z);j.age=0;j.duration=100;j.rebase=true;}
        j.returning=true;j.destination=head(p.serverLevel(),j.variant);
        if(j.carrying&&p.serverLevel().getEntity(j.unit) instanceof EvaUnit01Entity e)begin(p.serverLevel(),j,Phase.ASCEND,e.position(),new Vec3(e.getX(),cruise(p.serverLevel())-OFFSET,e.getZ()),100,e);
        s.setDirty();return "运输机将安全返回原发射井顶部，机体接地后等待回收指令。";
    }
    private static boolean ready(ServerLevel l,Vec3 p,int radius)
    {
        var c=new ChunkPos(BlockPos.containing(p));l.getChunkSource().addRegionTicket(TICKET,c,radius+1,c);boolean loaded=true;
        for(int x=c.x-radius;x<=c.x+radius;x++)for(int z=c.z-radius;z<=c.z+radius;z++)if(!l.getChunkSource().hasChunk(x,z)){loaded=false;}
        return loaded&&l.isPositionEntityTicking(BlockPos.containing(p));
    }
    private static double cruise(ServerLevel l){return l.getMaxBuildHeight()+224;}
    private static int duration(Vec3 a,Vec3 b){return AirRouteR39.duration(a,b);}
    private static boolean movingCargo(Phase p){return Set.of(Phase.ASCEND,Phase.CRUISE,Phase.DESCEND).contains(p);}
    private static void note(ServerLevel l,Job j,String text)
    {if(j.note.equals(text))return;j.note=text;var p=l.getServer().getPlayerList().getPlayer(j.owner);if(p!=null)p.sendSystemMessage(Component.literal("[NERV 运输管制] "+text));}
    private static void lock(EvaUnit01Entity e){e.setNervLogisticsLocked(true);e.setNoGravity(true);e.setDeltaMovement(Vec3.ZERO);}
    private static void begin(ServerLevel l,Job j,Phase phase,Vec3 a,Vec3 b,int ticks,EvaUnit01Entity e)
    {
        j.phase=phase;j.from=a;j.to=b;j.age=0;j.duration=Math.max(1,ticks);j.rebase=false;
        if(phase==Phase.APPROACH)EvaAirTransportR31.begin(e);
        if(phase==Phase.CLAMP)EvaAirTransportR31.transition(e,0,1,j.duration);
        if(phase==Phase.ASCEND){j.tilting=false;EvaAirTransportR31.transition(e,EvaAirTransportR31.pitch(e,0),1,1);}
        if(phase==Phase.CRUISE)EvaAirTransportR31.transition(e,90,1,1);
        if(phase==Phase.DESCEND){j.touchdown=false;j.contactTicks=0;EvaAirTransportR31.transition(e,0,1,Math.max(40,j.duration*2/3));}
        if(phase==Phase.RELEASE)EvaAirTransportR31.release(e,j.duration);
        if(movingCargo(phase)){lock(e);e.beginNervCarrierMotion(a,b,j.duration);}
        note(l,j,switch(phase){case TAKEOFF->"重型运输机离开机场";case FERRY->"正在前往机体所在位置";case APPROACH->"下降接近，吊装架展开";case CLAMP->"夹具接触，固定肩部、腰部和双腿";case ASCEND->"机体离地，运输鞍座收平";case CRUISE->"机体已横置固定，前往交付位置";case DESCEND->"抵达目标，鞍座翻转后垂直下放";case RELEASE->"机体接地，解除运输夹具";case RETREAT,RETURN,LAND->"机体已交付，运输机返回机场";default->"等待运输条件满足";});
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var l=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return;
        if(!Files.isRegularFile(l.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_transport_r30.json")))return;
        var s=state(l);
        if(event.getServer().getTickCount()%20==0)for(int i=0;i<3;i++){var e=EvaLogisticsDirector.canonicalUnit(l,i);if(e!=null&&!e.blockPosition().equals(s.locations.get(i))){s.locations.put(i,e.blockPosition());s.setDirty();}}
        if(s.aircraft==null)
        {
            if(!ready(l,STAND,5))return;var plane=ModEntities.UN_TRANSPORT.get().create(l);if(plane==null)return;plane.configure(0,false);plane.setNerv();plane.setPos(STAND);if(!l.addFreshEntity(plane))return;s.aircraft=plane.getUUID();s.aircraftAt=STAND;s.setDirty();
        }
        if(s.forceRecovery){l.resetEmptyTime();completeForcedRecovery(l,s);return;}
        if(s.job==null)return;l.resetEmptyTime();report(l,s,s.job);
        try{advance(l,s);}catch(Exception error){s.job.phase=Phase.HOLD;if(l.getEntity(s.job.unit) instanceof EvaUnit01Entity held){held.endNervCarrierMotion();EvaAirTransportR31.hold(held);}note(l,s.job,"运输暂停："+error.getMessage());s.setDirty();com.projectseele.ProjectSeele.LOGGER.error("NERV airlift held",error);}
    }
    private static void advance(ServerLevel l,State s)
    {
        var j=s.job;Vec3 location=s.locations.containsKey(j.variant)?Vec3.atCenterOf(s.locations.get(j.variant)):head(l,j.variant);ready(l,location,2);ready(l,s.aircraftAt,2);
        if("r32-airlift".equals(System.getProperty("projectseele.regionalBuild"))&&l.getGameTime()%100==0)com.projectseele.ProjectSeele.LOGGER.info("R32 AIR PATH {} age={}/{} plane={} target={}",j.phase,j.age,j.duration,s.aircraftAt,j.to);
        var e=ServiceAircraftR32.payload(l,j.unit);
        if(e==null){EvaLogisticsDirector.loadControlTarget(l,j.variant);note(l,j,"正在加载原机体；不会生成替代机");return;}
        UNTransportEntity plane=ServiceAircraftR32.find(l,s.aircraft);
        if(plane==null)plane=restoreAircraft(l,s);
        if(plane==null){note(l,j,"正在加载原运输机");return;}
        s.aircraftMissingTicks=0;
        plane.rebindCargo(e.getId());plane.setHoistDistance((float)OFFSET);
        var owner=l.getServer().getPlayerList().getPlayer(j.owner);
        if(j.crew&&owner==null&&j.phase!=Phase.RETURN&&j.phase!=Phase.LAND){e.endNervCarrierMotion();e.setDeltaMovement(Vec3.ZERO);if(!j.paused)EvaAirTransportR31.hold(e);j.paused=true;note(l,j,"驾驶员离线，保持位置等待通信恢复");return;}
        if(j.paused){j.paused=false;j.rebase=true;}
        if(e.getPilotEntity() instanceof ServerPlayer pilot&&pilot!=owner&&j.phase==Phase.PREPARE){s.last="原机体已有其他驾驶员，运输未开始";s.job=null;s.setDirty();return;}
        if(j.phase==Phase.HOLD){if(j.carrying)lock(e);return;}
        if(j.phase==Phase.PREPARE)
        {
            if(e.getY()<64){note(l,j,"机体仍在地下，请先正常发射至地表");return;}
            String problem=TransportClearanceR30.pickupProblem(l,e);if(!problem.isEmpty()){note(l,j,problem);return;}
            if(!ready(l,j.destination,7)){note(l,j,"检查目的地空域");return;}
            if(!j.returning){Vec3 site=TransportClearanceR30.landing(l,j.destination,e);if(site==null){s.last="目标附近没有安全落点，请换一个开阔位置";s.job=null;s.setDirty();return;}j.destination=site;}
            begin(l,j,Phase.TAKEOFF,plane.position(),new Vec3(STAND.x,cruise(l),STAND.z),100,e);s.setDirty();return;
        }
        if(j.rebase){Vec3 from=movingCargo(j.phase)?e.position():plane.position();int remaining=Math.max(30,j.duration-j.age);if(j.phase==Phase.CRUISE||j.phase==Phase.FERRY||j.phase==Phase.RETURN)remaining=duration(from,j.to);begin(l,j,j.phase,from,j.to,remaining,e);}
        if(j.phase==Phase.FERRY&&j.age==0){j.to=new Vec3(e.getX(),cruise(l),e.getZ());j.duration=duration(j.from,j.to);}
        if(j.phase==Phase.CRUISE||j.phase==Phase.FERRY||j.phase==Phase.RETURN)AirRouteR39.prefetch(l,j.from,j.to,j.age,j.duration);
        double look=Mth.clamp((double)(j.age+6)/j.duration,0,1);look=look*look*look*(look*(look*6-15)+10);ready(l,j.from.lerp(j.to,look),3);
        double t=Mth.clamp((double)(j.age+1)/j.duration,0,1);t=t*t*t*(t*(t*6-15)+10);Vec3 at=j.from.lerp(j.to,t);
        if(!ready(l,at,2)){if(movingCargo(j.phase)){e.endNervCarrierMotion();}return;}
        if(movingCargo(j.phase))
        {
            lock(e);
            if(j.phase==Phase.ASCEND&&!j.tilting&&(e.getY()-j.from.y>=24||j.age>=j.duration/2)){j.tilting=true;EvaAirTransportR31.transition(e,90,1,Math.max(1,j.duration-j.age));}
            Vec3 delta=at.subtract(e.position());
            float yaw=e.getYRot();if(j.phase==Phase.CRUISE){Vec3 d=j.to.subtract(j.from);yaw=Mth.approachDegrees(yaw,(float)Math.toDegrees(Math.atan2(-d.x,d.z)),2.5F);}
            if(j.phase==Phase.DESCEND&&j.returning)yaw=Mth.approachDegrees(yaw,j.landingYaw,2.5F);
            if(!AirCradleClearanceR31.clear(e,delta,yaw)){e.endNervCarrierMotion();throw new IllegalStateException("机体运输路径受阻："+j.phase+" / "+e.blockPosition().toShortString());}
            Vec3 previous=e.position();e.moveOnNervCarrier(at.x,at.y,at.z,yaw);e.publishAirCarrierFrameR39(previous,at);plane.setPos(at.add(0,OFFSET,0));plane.setYRot(yaw);plane.cargo(e.getId(),true,1);
        }
        else if(j.phase==Phase.CLAMP){lock(e);plane.cargo(e.getId(),true,1);}
        else if(j.phase==Phase.RELEASE)
        {
            lock(e);EvaAirTransportR31.refreshRelease(e,Math.max(1,j.duration-j.age));plane.cargo(e.getId(),false,1);
            if(!j.touchdown)
            {
                Vec3 contact=AirCradleClearanceR31.touchdownContact(e);
                j.contactTicks=contact==null?0:j.contactTicks+1;
                if(j.contactTicks>=2){com.projectseele.entity.CombatFoleyR36.airliftTouchdown(e,contact);j.touchdown=true;s.setDirty();}
            }
        }
        else
        {
            plane.setPos(at);Vec3 d=j.to.subtract(j.from);if(d.horizontalDistanceSqr()>1)plane.setYRot(Mth.approachDegrees(plane.getYRot(),(float)Math.toDegrees(Math.atan2(-d.x,d.z)),2.5F));plane.cargo(e.getId(),false,j.phase==Phase.APPROACH?(float)t:0);if(j.phase==Phase.APPROACH)plane.setYRot(Mth.approachDegrees(plane.getYRot(),e.getYRot(),3.5F));
        }
        s.aircraftAt=plane.position();s.aircraftBackup=plane.saveWithoutId(new CompoundTag());s.locations.put(j.variant,e.blockPosition());j.age++;s.setDirty();if(j.age<j.duration)return;
        switch(j.phase)
        {
            case TAKEOFF -> begin(l,j,Phase.FERRY,plane.position(),new Vec3(e.getX(),cruise(l),e.getZ()),duration(plane.position(),e.position()),e);
            case FERRY ->
            {
                if(e.position().distanceTo(new Vec3(j.to.x,e.getY(),j.to.z))>12){begin(l,j,Phase.FERRY,plane.position(),new Vec3(e.getX(),cruise(l),e.getZ()),80,e);return;}
                String problem=TransportClearanceR30.pickupProblem(l,e);if(!problem.isEmpty()){j.age--;note(l,j,problem);return;}
                EvaAirTransportR31.begin(e);lock(e);begin(l,j,Phase.APPROACH,plane.position(),e.position().add(0,OFFSET,0),100,e);
            }
            case APPROACH -> {plane.setYRot(e.getYRot());begin(l,j,Phase.CLAMP,plane.position(),plane.position(),100,e);}
            case CLAMP -> {j.carrying=true;e.getPersistentData().remove("R30AwaitingNervRecovery");EvaShutdownR30.waitingR31(e,false);begin(l,j,Phase.ASCEND,e.position(),new Vec3(e.getX(),cruise(l)-OFFSET,e.getZ()),100,e);}
            case ASCEND -> {Vec3 dest=new Vec3(j.destination.x,cruise(l)-OFFSET,j.destination.z);begin(l,j,Phase.CRUISE,e.position(),dest,duration(e.position(),dest),e);}
            case CRUISE -> {
                if(j.returning){j.landingYaw=AirCradleClearanceR31.landingYaw(e,j.destination,EvaUnit01Entity.SILO_BAY_YAW);if(!Float.isFinite(j.landingYaw))throw new IllegalStateException("原发射口周围没有容纳当前机体姿态的净空");}
                Vec3 floor=j.returning?head(l,j.variant):j.destination;
                j.destination=AirCradleClearanceR31.landingRoot(e,floor,j.returning?j.landingYaw:e.getYRot());
                if(j.returning)e.getPersistentData().putDouble("R39LandingLift",j.destination.y-floor.y);
                begin(l,j,Phase.DESCEND,e.position(),j.destination,140,e);
            }
            case DESCEND -> {e.endNervCarrierMotion();begin(l,j,Phase.RELEASE,plane.position(),plane.position(),70,e);}
            case RELEASE ->
            {
                if(!j.touchdown)throw new IllegalStateException("落点没有稳定承重面，保持运输夹具并等待重新调度");
                j.carrying=false;j.crew=false;e.normalizeAfterTransportR30(false);e.setOnGround(true);
                if(j.returning){e.setNervLogisticsLocked(true);e.setNoGravity(true);e.getPersistentData().putBoolean("R30AwaitingNervRecovery",true);EvaShutdownR30.waitingR31(e,true);}
                begin(l,j,Phase.RETREAT,plane.position(),new Vec3(plane.getX(),cruise(l),plane.getZ()),100,e);
            }
            case RETREAT -> {if(j.returning&&waitingAtHead(e))EvaLogisticsDirector.requestRecovery(l,j.variant);Vec3 atStand=new Vec3(STAND.x,cruise(l),STAND.z);begin(l,j,Phase.RETURN,plane.position(),atStand,duration(plane.position(),atStand),e);}
            case RETURN -> begin(l,j,Phase.LAND,plane.position(),STAND,100,e);
            case LAND -> {plane.setPos(STAND);plane.setYRot(0);s.aircraftAt=STAND;s.last=j.returning?"机体已交付原发射井，支撑架与舱门按回收顺序工作；运输机已返回 NERV 机场。":"机体投放完成，运输机在 NERV 机场待命。";note(l,j,s.last);s.job=null;s.setDirty();}
            default -> {}
        }
    }
    /** Restore only the job-owned service aircraft, never the EVA or its capsule.
     * Loading all neighbouring entity sections and checking known UUIDs prevents
     * mistaking an unloaded original for a lost aircraft. */
    private static UNTransportEntity restoreAircraft(ServerLevel level,State state)
    {
        if(!ready(level,state.aircraftAt,4))return null;
        var centre=new ChunkPos(BlockPos.containing(state.aircraftAt));
        for(int x=centre.x-4;x<=centre.x+4;x++)for(int z=centre.z-4;z<=centre.z+4;z++)
            if(!level.areEntitiesLoaded(ChunkPos.asLong(x,z)))return null;
        var manager=((com.projectseele.mixin.ServiceAircraftWorldR32Accessor)level).seele$entityManagerR32();
        if(manager.isLoaded(state.aircraft)||++state.aircraftMissingTicks<100)return null;
        var plane=ModEntities.UN_TRANSPORT.get().create(level);if(plane==null)return null;
        if(!state.aircraftBackup.isEmpty())plane.load(state.aircraftBackup.copy());
        plane.setUUID(state.aircraft);plane.setNerv();plane.configure(0,state.job!=null&&state.job.carrying);plane.setPos(state.aircraftAt);
        if(!level.addFreshEntity(plane))return null;
        if(state.job!=null)state.job.rebase=true;
        state.aircraftBackup=plane.saveWithoutId(new CompoundTag());state.setDirty();
        com.projectseele.ProjectSeele.LOGGER.warn("Restored missing NERV service aircraft with registered UUID {} at {}; original EVA/capsule unchanged",state.aircraft,state.aircraftAt);
        return plane;
    }
    private NervAirLiftR30(){}
}
