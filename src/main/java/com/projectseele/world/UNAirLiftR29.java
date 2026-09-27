package com.projectseele.world;

import com.projectseele.ProjectSeele;
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
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/** Persistent physical transport of the original UN EVA and its original capsule. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UNAirLiftR29
{
    private enum Phase { PREPARE, GROUND_LIFT, ROLL_OUT, FERRY, APPROACH, CLAMP, ASCEND, CRUISE, DESCEND, RELEASE, GROUND_APPROACH, ROLL_IN, GROUND_LOWER, RETREAT, RETURN_FLIGHT, HOLD }
    private static final double OFFSET=TransportClearanceR30.HOIST_OFFSET,DECK=1.6;
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_un_airlift",Comparator.comparingLong(ChunkPos::toLong),120);
    public static final class State extends SavedData
    {
        final Map<Integer,Job> jobs=new HashMap<>();final Map<Integer,UUID> carts=new HashMap<>();final Map<Integer,BlockPos> cartPositions=new HashMap<>();final Map<Integer,String> last=new HashMap<>();
        static State load(CompoundTag tag)
        {
            State s=new State();
            for(var raw:tag.getList("Jobs",Tag.TAG_COMPOUND))
            {
                var t=(CompoundTag)raw;Job j=new Job();j.serial=t.getInt("Serial");j.owner=t.getUUID("Owner");j.unit=t.getUUID("Unit");j.plug=t.hasUUID("Plug")?t.getUUID("Plug"):null;j.plane=t.hasUUID("Plane")?t.getUUID("Plane"):null;
                j.phase=Phase.valueOf(t.getString("Phase"));j.from=read(t,"From");j.to=read(t,"To");j.destination=read(t,"Destination");j.pickup=read(t,"Pickup");j.planePosition=read(t,"PlanePosition");j.groundOffset=read(t,"GroundOffsetR40");j.age=t.getInt("Age");j.duration=t.getInt("Duration");j.total=t.getInt("Total");j.homebound=t.getBoolean("Homebound");j.groundOnly=t.getBoolean("GroundOnly");j.crew=t.getBoolean("Crew");j.cancel=t.getBoolean("Cancel");j.carrying=t.getBoolean("Carrying");j.note=t.getString("Note");j.nextReport=t.getLong("NextReportR39");j.touchdown=t.getBoolean("TouchdownR40");j.landingYaw=t.contains("LandingYawR40")?t.getFloat("LandingYawR40"):Float.NaN;j.rebase=true;s.jobs.put(j.serial,j);
            }
            for(int i=0;i<2;i++){if(tag.hasUUID("Cart"+i))s.carts.put(i,tag.getUUID("Cart"+i));if(tag.contains("CartPos"+i))s.cartPositions.put(i,BlockPos.of(tag.getLong("CartPos"+i)));s.last.put(i,tag.getString("Last"+i));}return s;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            ListTag list=new ListTag();for(var j:jobs.values())
            {
                CompoundTag t=new CompoundTag();t.putInt("Serial",j.serial);t.putUUID("Owner",j.owner);t.putUUID("Unit",j.unit);if(j.plug!=null)t.putUUID("Plug",j.plug);if(j.plane!=null)t.putUUID("Plane",j.plane);t.putString("Phase",j.phase.name());put(t,"From",j.from);put(t,"To",j.to);put(t,"Destination",j.destination);put(t,"Pickup",j.pickup);put(t,"PlanePosition",j.planePosition);put(t,"GroundOffsetR40",j.groundOffset);t.putInt("Age",j.age);t.putInt("Duration",j.duration);t.putInt("Total",j.total);t.putBoolean("Homebound",j.homebound);t.putBoolean("GroundOnly",j.groundOnly);t.putBoolean("Crew",j.crew);t.putBoolean("Cancel",j.cancel);t.putBoolean("Carrying",j.carrying);t.putString("Note",j.note);t.putLong("NextReportR39",j.nextReport);t.putBoolean("TouchdownR40",j.touchdown);if(Float.isFinite(j.landingYaw))t.putFloat("LandingYawR40",j.landingYaw);list.add(t);
            }
            tag.put("Jobs",list);for(int i=0;i<2;i++){if(carts.containsKey(i))tag.putUUID("Cart"+i,carts.get(i));if(cartPositions.containsKey(i))tag.putLong("CartPos"+i,cartPositions.get(i).asLong());tag.putString("Last"+i,last.getOrDefault(i,"待命"));}return tag;
        }
    }
    private static final class Job
    {
        long nextReport;int serial,age,duration,total,loadCursor,missing,planeMissing,contactTicks;boolean touchdown;float landingYaw=Float.NaN;UUID owner,unit,plug,plane;Phase phase=Phase.PREPARE;
        Vec3 from=Vec3.ZERO,to=Vec3.ZERO,destination=Vec3.ZERO,pickup=Vec3.ZERO,planePosition=Vec3.ZERO,groundOffset=Vec3.ZERO;
        boolean homebound,crew,cancel,carrying,rebase,paused,siteReady,groundOnly,tilting;String note="正在定位原机体";CompletableFuture<?> loading;Vec3 waitAt;
    }
    private static void put(CompoundTag tag,String key,Vec3 v){tag.putDouble(key+"X",v.x);tag.putDouble(key+"Y",v.y);tag.putDouble(key+"Z",v.z);}
    private static Vec3 read(CompoundTag tag,String key){return new Vec3(tag.getDouble(key+"X"),tag.getDouble(key+"Y"),tag.getDouble(key+"Z"));}
    public static State state(ServerLevel level){return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_un_airlift_r29");}
    public static boolean active(ServerLevel l,int serial){return state(l).jobs.containsKey(serial);}
    public static boolean ownsAircraft(ServerLevel l,UUID id){return state(l).jobs.values().stream().anyMatch(j->id.equals(j.plane));}
    public static void abortForMaintenance(ServerLevel l,int serial)
    {
        var s=state(l);UUID unit=UNRecoveryR22.identity(l,serial);
        if(unit!=null&&l.getEntity(unit) instanceof EvaPrototypeEntity held){held.getPersistentData().remove("R31GroundHold");held.getPersistentData().remove("R31GroundHoldAt");}
        var job=s.jobs.remove(serial);if(job==null)return;
        var aircraft=ServiceAircraftR32.find(l,job.plane);if(aircraft!=null)aircraft.discard();
        if(l.getEntity(job.unit) instanceof EvaPrototypeEntity eva){eva.endNervCarrierMotion();EvaAirTransportR31.clear(eva);eva.getPersistentData().putBoolean("UNTransportAutoload",false);}
        s.last.put(serial,"运输已由管理员维护复位接管");s.setDirty();
    }
    public static String phaseName(ServerLevel l,int serial){var j=state(l).jobs.get(serial);return j==null?"IDLE":j.phase.name();}
    public static void resumeReview(ServerLevel level,int serial,ServerPlayer owner)
    {
        if(!"r29-un".equals(System.getProperty("projectseele.regionalBuild","")))throw new IllegalStateException("Review only");
        var j=state(level).jobs.get(serial);if(j==null||j.phase!=Phase.HOLD||j.carrying||!j.owner.equals(owner.getUUID()))return;
        if(ServiceAircraftR32.payload(level,j.unit) instanceof EvaPrototypeEntity eva&&eva.position().distanceTo(UNRecoveryR22.home(serial))<8)
        {begin(level,j,Phase.ROLL_OUT,eva.position(),apron(serial),240,eva);state(level).setDirty();}
    }
    public static boolean ownsMotion(ServerLevel l,int serial)
    {
        UUID id=UNRecoveryR22.identity(l,serial);
        if(id!=null&&l.getEntity(id) instanceof EvaPrototypeEntity eva&&(waitingForDock(eva)||heldOnGround(eva)))return true;
        var j=state(l).jobs.get(serial);return j!=null&&j.phase!=Phase.PREPARE&&j.phase!=Phase.RETREAT&&j.phase!=Phase.RETURN_FLIGHT;
    }
    public static boolean waitingForDock(EvaPrototypeEntity eva)
    {return eva.getPersistentData().getBoolean("R30AwaitingIntake")&&(eva.position().distanceToSqr(apron(eva.getUNSerial()))<64||atReception(eva));}
    public static boolean heldOnGround(EvaPrototypeEntity eva)
    {return eva.getPersistentData().getBoolean("R31GroundHold")&&eva.position().distanceToSqr(Vec3.atCenterOf(BlockPos.of(eva.getPersistentData().getLong("R31GroundHoldAt"))))<16;}
    public static boolean emptyLoading(EvaPrototypeEntity eva)
    {return eva.level() instanceof ServerLevel l&&active(l,eva.getUNSerial())&&eva.getPersistentData().getBoolean("UNTransportAutoload")&&eva.getUUID().equals(UNRecoveryR22.identity(l,eva.getUNSerial()));}
    public static String status(ServerLevel l,int serial)
    {
        var j=state(l).jobs.get(serial);if(j==null)return state(l).last.getOrDefault(serial,"运输机待命");
        return j.note+" · "+(j.homebound?"返回联合国基地":"目的地 "+Math.round(j.destination.x)+" / "+Math.round(j.destination.z));
    }
    public static String request(ServerPlayer player,int serial,boolean homebound,int x,int z)
    {
        ServerLevel l=player.serverLevel();var s=state(l);if(s.jobs.containsKey(serial))return "这台机体已有运输任务，请先查看状态。";
        UUID unit=UNRecoveryR22.identity(l,serial);if(unit==null)return "没有这台 UN 机体的原始登记，未创建替代机。";
        if(x< -29999000||x>29999000||z< -29999000||z>29999000||!l.getWorldBorder().isWithinBounds(new BlockPos(x,80,z)))return "目标超出世界边界。";
        var j=new Job();j.serial=serial;j.owner=player.getUUID();j.unit=unit;j.homebound=homebound;j.destination=homebound?reception(l,serial):new Vec3(x+.5,0,z+.5);
        if(s.jobs.values().stream().anyMatch(other->other.destination.distanceToSqr(j.destination)<70*70))return "另一架运输机正在使用附近空域，请选择稍远的投放点。";
        var eva=l.getEntity(unit);if(eva instanceof EvaUnit01Entity repairing&&EvaBayRepairR33.active(repairing))return "机体正在检修，暂时不能起运。";j.crew=eva instanceof EvaPrototypeEntity e&&e.getPilotEntity()==player;
        if(eva instanceof EvaPrototypeEntity e&&e.getPilotEntity()!=null&&e.getPilotEntity()!=player)return "该机体由另一名驾驶员控制，请由驾驶员本人呼叫运输。";
        s.jobs.put(serial,j);s.setDirty();return "运输指令已接受。正在加载原机体与目的地，随后检查落点和机库联锁。";
    }
    public static boolean stageCruiseReviewR39(ServerLevel level,ServerPlayer owner)
    {
        if(!"r39-transport".equals(System.getProperty("projectseele.regionalBuild"))||!level.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_FIELD_R39_REVIEW"))throw new IllegalStateException("Isolated flight fixture only");
        var id=UNRecoveryR22.identity(level,0);if(id==null)throw new IllegalStateException("No original UN-00");
        var known=UNRecoveryR22.lastKnownPosition(level,id);retain(level,known==null?BlockPos.containing(UNRecoveryR22.home(0)):known,4);
        if(!(ServiceAircraftR32.payload(level,id) instanceof EvaPrototypeEntity eva))return false;
        if(active(level,0))throw new IllegalStateException("Existing UN flight in review copy");
        var j=new Job();j.serial=0;j.unit=id;j.owner=owner.getUUID();j.homebound=true;j.carrying=true;j.siteReady=true;j.destination=apron(0);
        var from=new Vec3(-1800.5,cruise(level)-OFFSET,1300.5);retain(level,BlockPos.containing(from),4);
        if(!readyAt(level,from))return false;
        var plane=ModEntities.UN_TRANSPORT.get().create(level);plane.configure(0,true);plane.addTag("seele_un_airlift");plane.setPos(from.add(0,OFFSET,0));plane.setHoistDistance((float)OFFSET);
        if(!level.addFreshEntity(plane))return false;
        eva.normalizeAfterTransportR30(false);EvaAirTransportR31.begin(eva);EvaAirTransportR31.transition(eva,90,1,1);lock(eva);eva.moveOnNervCarrier(from.x,from.y,from.z,0);
        j.plane=plane.getUUID();j.planePosition=plane.position();state(level).jobs.put(0,j);UNRecoveryR22.remember(eva);
        begin(level,j,Phase.CRUISE,from,new Vec3(j.destination.x,from.y,j.destination.z),duration(from,j.destination),eva);state(level).setDirty();return true;
    }

    public static String cancel(ServerPlayer player,int serial)
    {
        var s=state(player.serverLevel());var j=s.jobs.get(serial);if(j==null)return "没有正在执行的运输。";
        if(!j.owner.equals(player.getUUID())&&!player.hasPermissions(2))return "只有下达指令的人或管理员可以取消这次运输。";
        if(j.phase==Phase.PREPARE){if(player.serverLevel().getEntity(j.unit) instanceof EvaPrototypeEntity eva)eva.getPersistentData().putBoolean("UNTransportAutoload",false);s.jobs.remove(serial);s.last.put(serial,"已取消；已启动的机库机械按原流程完成");s.setDirty();return s.last.get(serial);}
        if(j.phase==Phase.RETREAT||j.phase==Phase.RETURN_FLIGHT)return "机体已安全卸载，运输机正在返航。";
        j.cancel=true;s.setDirty();return "已收到取消指令，将先安全返回基地，不会在空中释放机体。";
    }
    public static Vec3 apron(int serial){var home=UNRecoveryR22.home(serial);return new Vec3(home.x,home.y+DECK,-6101.5);}
    public static boolean resumeGroundReviewR40(ServerLevel level,int serial)
    {
        if(!"r40-airlift".equals(System.getProperty("projectseele.regionalBuild"))||!level.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_R32_AIR_REVIEW"))throw new IllegalStateException("Isolated recovery fixture only");
        var j=state(level).jobs.get(serial);
        if(j==null||!j.groundOnly||j.phase!=Phase.HOLD)throw new IllegalStateException("No held ground transfer to resume");
        if(!(ServiceAircraftR32.payload(level,j.unit) instanceof EvaPrototypeEntity eva))return false;
        Phase phase=j.to.distanceToSqr(apron(serial))<.01?Phase.GROUND_APPROACH:j.to.distanceToSqr(UNRecoveryR22.home(serial))<.01?Phase.GROUND_LOWER:Phase.ROLL_IN;
        j.total=0;j.rebase=false;var target=phase==Phase.GROUND_LOWER?AirCradleClearanceR31.landingRoot(eva,UNRecoveryR22.home(serial),eva.getYRot()):j.to;
        begin(level,j,phase,eva.position(),target,120,eva);state(level).setDirty();return true;
    }
    private static final Map<ServerLevel,Map<Integer,Vec3>> RECEIVING_PADS=new WeakHashMap<>();
    public static Vec3 reception(ServerLevel level,int serial)
    {
        var pads=RECEIVING_PADS.computeIfAbsent(level,l->{
            var path=l.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).resolve("un_air_reception_r40.json");
            if(!java.nio.file.Files.isRegularFile(path))return Map.of();
            try
            {
                var json=com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(path)).getAsJsonObject();
                if(!json.get("schema").getAsString().equals("projectseele.un-reception.r40.v1"))throw new IllegalArgumentException("UN reception schema");
                Map<Integer,Vec3> result=new HashMap<>();
                for(var item:json.getAsJsonArray("pads"))
                {
                    var row=item.getAsJsonObject();int key=row.get("serial").getAsInt();var p=row.getAsJsonArray("deck");
                    var value=new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());
                    if(key<0||key>1||!Double.isFinite(value.lengthSqr())||value.distanceTo(UNRecoveryR22.home(key))>512)throw new IllegalArgumentException("UN receiving pad location");
                    result.put(key,value);
                }
                return Map.copyOf(result);
            }
            catch(Exception error){throw new IllegalStateException("UN receiving apron could not load",error);}
        });
        return pads.getOrDefault(serial,apron(serial));
    }
    private static boolean atReception(EvaPrototypeEntity eva)
    {return eva.level() instanceof ServerLevel level&&eva.position().distanceToSqr(reception(level,eva.getUNSerial()))<64;}
    private static void receiveCart(ServerLevel level,State state,Job job,UNTransportEntity cart)
    {
        if(!job.homebound||job.groundOnly)return;
        Vec3 target=reception(level,job.serial);double distance=cart.position().distanceTo(target);
        if(distance>.001)cart.setPos(cart.position().lerp(target,Math.min(1,.45/distance)));
        cart.setYRot(Float.isFinite(job.landingYaw)?job.landingYaw:0);
        state.cartPositions.put(job.serial,cart.blockPosition());
    }
    private static float receivingHeading(ServerLevel level,Job job,EvaPrototypeEntity eva)
    {
        var pose=EvaAirTransportR31.origin(eva);var tried=new HashSet<Float>();
        float preferred=UNReceivingCradleR40.groundHeading(eva);if(!Float.isFinite(preferred))return Float.NaN;
        for(float requested:new float[]{preferred,preferred+90,preferred-90,preferred+180})
        {
            float yaw=AirCradleClearanceR31.landingYaw(eva,job.destination,requested);
            if(!Float.isFinite(yaw)||!tried.add(Mth.wrapDegrees(yaw)))continue;
            var fit=UNReceivingCradleR40.fit(eva,yaw);if(fit==null)continue;
            var at=AirCradleClearanceR31.landingRoot(eva,job.destination,yaw);
            Boolean clear=VerticalCarrierSweepR40.clearTranslationAt(level,eva,pose,0,yaw,at,apron(job.serial).add(fit.offset()).subtract(at));
            if(!Boolean.FALSE.equals(clear)){job.groundOffset=fit.offset();return yaw;}
        }
        return Float.NaN;
    }
    public static String requestDock(ServerPlayer player,int serial)
    {
        var l=player.serverLevel();var s=state(l);
        if(active(l,serial))return "请先等待当前运输结束。";
        UUID id=UNRecoveryR22.identity(l,serial);
        if(id==null)return "没有该机体的原始登记。";
        if(!(l.getEntity(id) instanceof EvaPrototypeEntity eva))return "正在定位原机体，请刷新状态后重试。";
        if(eva.getPilotEntity()!=null&&eva.getPilotEntity()!=player)return "请由当前驾驶员本人请求入库。";
        if(eva.position().distanceTo(apron(serial))>8&&!atReception(eva)&&!eva.isInsideTestHangar()&&!heldOnGround(eva))return "机体尚未抵达库外接应平台，请先呼叫运输机回收。";
        var j=new Job();j.serial=serial;j.owner=player.getUUID();j.unit=id;j.groundOnly=true;j.homebound=true;j.crew=eva.getPilotEntity()==player;
        s.jobs.put(serial,j);s.setDirty();return "库外接应已确认。等待机库排液、开门后，由地面载台送回库位。";
    }
    private static double cruise(ServerLevel l){return l.getMaxBuildHeight()+224;}
    private static void retain(ServerLevel l,BlockPos p,int radius)
    {var c=new ChunkPos(p);l.getChunkSource().addRegionTicket(TICKET,c,radius,c);}
    private static boolean readyAt(ServerLevel l,Vec3 point)
    {
        var c=new ChunkPos(BlockPos.containing(point));retain(l,BlockPos.containing(point),3);boolean ready=true;
        for(int x=c.x-1;x<=c.x+1;x++)for(int z=c.z-1;z<=c.z+1;z++)
            if(!l.getChunkSource().hasChunk(x,z)){ready=false;}
        return ready&&l.isPositionEntityTicking(BlockPos.containing(point));
    }
    private static boolean loadLanding(ServerLevel l,Job j)
    {
        var centre=new ChunkPos(BlockPos.containing(j.destination));retain(l,BlockPos.containing(j.destination),7);
        if(j.loadCursor>=169)return true;
        int x=centre.x+j.loadCursor%13-6,z=centre.z+j.loadCursor/13-6;
        // The region ticket schedules loading. getChunkFuture blocks when called
        // on the server thread, so readiness is polled across ticks instead.
        if(l.getChunkSource().hasChunk(x,z))j.loadCursor++;
        return false;
    }
    private static Vec3 landing(ServerLevel l,Vec3 requested,EvaPrototypeEntity eva)
    {
        return TransportClearanceR30.landing(l,requested,eva);
    }
    private static boolean openBase(ServerLevel l,int serial)
    {
        var phase=serial==0?MilitaryR07Director.state(l).phase:UNAnnexR20.state(l).phase;
        String action=phase==MilitaryR07Director.Phase.WET||phase==MilitaryR07Director.Phase.FILLING?"drain":phase==MilitaryR07Director.Phase.DRY?"door":"";
        if(!action.isEmpty()){if(serial==0)MilitaryR07Director.request(l,action,null);else UNAnnexR20.request(l,action,null);}
        return phase==MilitaryR07Director.Phase.OPEN;
    }
    private static UNTransportEntity cart(ServerLevel l,State s,Job j,EvaPrototypeEntity eva)
    {
        UUID id=s.carts.get(j.serial);
        if(id!=null){retain(l,s.cartPositions.getOrDefault(j.serial,BlockPos.containing(UNRecoveryR22.home(j.serial))),3);return l.getEntity(id) instanceof UNTransportEntity e?e:null;}
        var e=ModEntities.UN_TRANSPORT.get().create(l);if(e==null)return null;e.configure(j.serial,false);e.setGroundCart();Vec3 at=eva.position().distanceTo(UNRecoveryR22.home(j.serial))<5?eva.position():apron(j.serial);e.setPos(at);if(!l.addFreshEntity(e))return null;s.carts.put(j.serial,e.getUUID());s.cartPositions.put(j.serial,e.blockPosition());s.setDirty();return e;
    }
    private static void note(ServerLevel l,Job j,String text)
    {
        j.note=text;
    }
    private static void report(ServerLevel l,Job j)
    {
        long now=System.currentTimeMillis();
        if(j.nextReport==0||j.nextReport>now+10000){j.nextReport=now+10000;return;}
        if(now<j.nextReport)return;
        j.nextReport=now+10000;state(l).setDirty();
        var p=l.getServer().getPlayerList().getPlayer(j.owner);
        Vec3 at=j.planePosition;
        if(j.plane==null){var known=UNRecoveryR22.lastKnownPosition(l,j.unit);if(known!=null)at=Vec3.atCenterOf(known);}
        if(p!=null)p.sendSystemMessage(Component.literal("[UN 运输管制 · 0"+j.serial+"] "+BlockPos.containing(at).toShortString()+" · "+j.note));
    }
    private static boolean cruisePhase(Phase phase)
    {return phase==Phase.CRUISE||phase==Phase.FERRY||phase==Phase.RETURN_FLIGHT;}
    private static void begin(ServerLevel l,Job j,Phase phase,Vec3 from,Vec3 to,int duration,EvaPrototypeEntity eva)
    {
        j.phase=phase;j.from=from;j.to=to;j.age=0;j.duration=Math.max(1,duration);j.rebase=false;
        if(phase==Phase.APPROACH)EvaAirTransportR31.begin(eva);
        if(phase==Phase.ROLL_IN||phase==Phase.GROUND_LIFT)EvaAirTransportR31.transition(eva,0,1,Math.min(60,j.duration));
        if(phase==Phase.CLAMP)EvaAirTransportR31.transition(eva,0,1,j.duration);
        if(phase==Phase.ASCEND){j.tilting=false;EvaAirTransportR31.transition(eva,EvaAirTransportR31.pitch(eva,0),1,1);}
        if(phase==Phase.CRUISE)EvaAirTransportR31.transition(eva,90,1,1);
        if(phase==Phase.DESCEND){j.touchdown=false;j.contactTicks=0;EvaAirTransportR31.transition(eva,0,1,Math.max(40,j.duration*2/3));}
        if(phase==Phase.RELEASE&&EvaAirTransportR31.active(eva))EvaAirTransportR31.release(eva,j.duration);
        if(movesEva(phase)){eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.beginNervCarrierMotion(from,to,j.duration);}
        note(l,j,switch(phase){case GROUND_LIFT->"自行载台升起";case ROLL_OUT->"机体正在移至库外吊装点";case FERRY->"运输机前往接载点";case APPROACH->"运输机下降，展开吊装架";case CLAMP->"夹具接触，正在固定肩部、腰部和双腿";case ASCEND->"机体离地，运输鞍座收平";case CRUISE->"机体已横置固定，运输机巡航中";case DESCEND->"抵达目标，鞍座翻转后垂直下放";case RELEASE->"接地，解除夹具";case GROUND_APPROACH->"接应载台驶入机库转运通道";case ROLL_IN->"自行载台将机体送回库位";case GROUND_LOWER->"机体落座原机库";case RETREAT,RETURN_FLIGHT->"机体已交付，运输机返航";default->"运输准备中";});
    }
    private static boolean movesEva(Phase p){return switch(p){case GROUND_LIFT,ROLL_OUT,ASCEND,CRUISE,DESCEND,GROUND_APPROACH,ROLL_IN,GROUND_LOWER->true;default->false;};}
    private static int duration(Vec3 a,Vec3 b){return AirRouteR39.duration(a,b);}
    private static double smooth(double x){return x*x*x*(x*(x*6-15)+10);}
    private static void lock(EvaPrototypeEntity eva){eva.stopUNFlight();eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.setDeltaMovement(Vec3.ZERO);}
    private static void release(EvaPrototypeEntity eva)
    {
        eva.normalizeAfterTransportR30(false);eva.setOnGround(true);
        if(eva.level() instanceof ServerLevel level&&eva.getPilotEntity() instanceof ServerPlayer player)
        {
            var values=eva.getEntityData().packDirty();
            if(values!=null){var packet=new net.minecraft.network.protocol.game.ClientboundSetEntityDataPacket(eva.getId(),values);level.getChunkSource().broadcastAndSend(eva,packet);player.connection.send(packet);}
            level.getChunkSource().move(player);
            com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.PLAYER.with(()->player),new com.projectseele.network.ClientboundEvaArrivalSyncPacket(eva.getId(),eva.getX(),eva.getY(),eva.getZ(),eva.getYRot(),0));
        }
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var l=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return;var s=state(l);if(s.jobs.isEmpty())return;l.resetEmptyTime();
        for(var j:new ArrayList<>(s.jobs.values()))try{advance(l,s,j);report(l,j);}catch(Exception error){j.phase=Phase.HOLD;if(l.getEntity(j.unit) instanceof EvaUnit01Entity held){held.endNervCarrierMotion();EvaAirTransportR31.hold(held);}j.note="运输暂停："+error.getMessage();s.setDirty();ProjectSeele.LOGGER.error("UN airlift held serial={}",j.serial,error);}
    }
    private static void advance(ServerLevel l,State s,Job j)
    {
        BlockPos last=UNRecoveryR22.lastKnownPosition(l,j.unit);retain(l,last==null?BlockPos.containing(UNRecoveryR22.home(j.serial)):last,3);retain(l,BlockPos.containing(UNRecoveryR22.home(j.serial)),j.phase==Phase.PREPARE?6:3);
        if(!(ServiceAircraftR32.payload(l,j.unit) instanceof EvaPrototypeEntity eva))
        {if(++j.missing>600){j.phase=Phase.HOLD;note(l,j,"原机体未能加载，请由管理员检查登记或执行维护复位");s.setDirty();}return;}
        // Keep the persisted clamp/deployment state. CLAMP is attached before
        // Job.carrying becomes true, and ids are different after a reload.
        var bound=ServiceAircraftR32.find(l,j.plane);
        if(bound!=null)
        {bound.rebindCargo(eva.getId());bound.setHoistDistance((float)OFFSET);}
        if(j.plug==null&&eva.getPersistentData().hasUUID("UNPlug"))j.plug=eva.getPersistentData().getUUID("UNPlug");
        var plugPos=j.plug==null?null:UNRecoveryR22.lastKnownPosition(l,j.plug);if(plugPos!=null)retain(l,plugPos,3);
        EntryPlugCarrierEntity plug=ServiceAircraftR32.capsule(l,j.plug);
        j.missing=0;
        if(j.groundOnly){advanceGround(l,s,j,eva,plug);return;}
        var owner=l.getServer().getPlayerList().getPlayer(j.owner);
        if(j.phase==Phase.RETREAT||j.phase==Phase.RETURN_FLIGHT)j.crew=false;
        if(eva.getPilotEntity()!=null&&(owner==null||eva.getPilotEntity()!=owner)){if(!j.crew)throw new IllegalStateException("原机体已由其他驾驶员占用");}
        if(j.crew&&owner==null){eva.endNervCarrierMotion();eva.setDeltaMovement(Vec3.ZERO);if(!j.paused)EvaAirTransportR31.hold(eva);j.paused=true;note(l,j,"驾驶员离线，保持位置等待通信恢复");s.setDirty();return;}
        if(j.crew&&owner!=null&&eva.getPilotEntity()!=owner)
        {
            if(owner.level()!=l||owner.isPassenger()||owner.distanceToSqr(eva)>128*128)j.crew=false;
            else if(plug!=null&&plug.isLockedToEva()&&!plug.isVehicle()){owner.startRiding(plug,true);plug.syncPilotPositionNow();l.getChunkSource().move(owner);}
            else if(plug!=null&&!plug.isVehicle())plug.boardPassenger(owner);
        }
        if(j.paused){j.paused=false;j.rebase=true;}
        if(j.phase!=Phase.HOLD&&j.total++>24000)throw new IllegalStateException("运输超时，机体保持锁定等待处置");
        if(j.phase==Phase.PREPARE)
        {
            if(j.homebound&&eva.position().distanceTo(UNRecoveryR22.home(j.serial))<4)
            {s.jobs.remove(j.serial);s.last.put(j.serial,"机体已在原机库，无需运输回收");s.setDirty();return;}
            if(!loadLanding(l,j)){note(l,j,"正在逐批加载目标空域");return;}
            if(!j.siteReady)
            {
                Vec3 at=j.homebound?reception(l,j.serial):landing(l,j.destination,eva);
                if(at==null){s.jobs.remove(j.serial);s.last.put(j.serial,"落点及邻近地面没有足够净空，请选择开阔位置");note(l,j,s.last.get(j.serial));s.setDirty();return;}
                j.destination=at;j.siteReady=true;note(l,j,"落点确认："+BlockPos.containing(at).toShortString());
            }
            if(eva.isInsideTestHangar()&&!openBase(l,j.serial)){note(l,j,"等待机库排液与舱门开启");return;}
            if(eva.isUNFlying()){eva.landUNFlight();note(l,j,"等待 UN-01 降落后接载");return;}
            if(!j.homebound&&!EvaShutdownR30.wreck(eva)&&UNPlugDirector.atDock(eva))
            {
                if(plug==null){note(l,j,"等待原插入栓加载");return;}
                if(!plug.isLockedToEva()){UNPlugDirector.prepareEmptyForTransport(eva);note(l,j,"吊机正在接入原插入栓");return;}
                if(eva.getPersistentData().getInt("UNSequenceTicks")<60)return;
            }
            // Recovery carries the airframe even after ejection. The independent
            // original capsule stays at its actual dock/escape location; never create a replacement.
            if(j.crew&&(plug==null||!plug.isLockedToEva())){note(l,j,"等待驾驶员完成插入栓接入");return;}
            if(plug!=null&&(plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_INSERTING||plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_EJECTING||plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_FIELD_EJECTING))
            {note(l,j,"等待插入栓机械动作完成后接载");return;}
            if(!eva.isInsideTestHangar())
            {
                String problem=TransportClearanceR30.pickupProblem(l,eva);
                if(!problem.isEmpty()){note(l,j,problem);return;}
            }
            var cart=cart(l,s,j,eva);if(cart==null)return;
            if(j.plane==null)
            {
                var plane=ModEntities.UN_TRANSPORT.get().create(l);if(plane==null)return;
                Vec3 h=UNRecoveryR22.home(j.serial);plane.configure(j.serial,false);plane.addTag("seele_un_airlift");plane.setPos(h.x,cruise(l),h.z+500);if(!l.addFreshEntity(plane))return;j.plane=plane.getUUID();j.planePosition=plane.position();
            }
            j.pickup=eva.position();eva.getPersistentData().putBoolean("UNTransportAutoload",false);eva.getPersistentData().remove("R31GroundHold");eva.getPersistentData().remove("R31GroundHoldAt");eva.getPersistentData().remove("R30AwaitingIntake");EvaShutdownR30.waitingR31(eva,false);EvaAirTransportR31.begin(eva);EvaAirTransportR31.transition(eva,0,eva.isInsideTestHangar()?1:0,60);lock(eva);
            if(eva.isInsideTestHangar())
                begin(l,j,Phase.GROUND_LIFT,eva.position(),eva.position().add(0,DECK,0),30,eva);
            else begin(l,j,Phase.FERRY,j.planePosition,new Vec3(eva.getX(),cruise(l),eva.getZ()),duration(j.planePosition,new Vec3(eva.getX(),cruise(l),eva.getZ())),eva);
            s.setDirty();return;
        }
        retain(l,BlockPos.containing(j.planePosition),3);var plane=ServiceAircraftR32.find(l,j.plane);
        if(plane==null)
        {
            if(++j.planeMissing>600){j.phase=Phase.HOLD;eva.endNervCarrierMotion();lock(eva);note(l,j,"运输机信号丢失，保持机体位置；请管理员检查或维护复位");s.setDirty();}
            return;
        }
        j.planeMissing=0;
        plane.setHoistDistance((float)OFFSET);
        var cart=cart(l,s,j,eva);if(cart==null)return;
        receiveCart(l,s,j,cart);
        if(j.homebound)cart.cargo(eva.getId(),false,1);
        if(j.phase==Phase.HOLD)
        {
            lock(eva);if(!j.cancel)return;j.total=0;j.homebound=true;j.cancel=false;j.destination=reception(l,j.serial);
            if(!j.carrying&&eva.isInsideTestHangar())begin(l,j,Phase.ROLL_IN,eva.position(),UNRecoveryR22.home(j.serial).add(0,DECK,0),120,eva);
            else if(!j.carrying)begin(l,j,Phase.FERRY,plane.position(),new Vec3(eva.getX(),cruise(l),eva.getZ()),duration(plane.position(),new Vec3(eva.getX(),cruise(l),eva.getZ())),eva);
            else begin(l,j,Phase.ASCEND,eva.position(),new Vec3(eva.getX(),cruise(l)-OFFSET,eva.getZ()),120,eva);
        }
        if(j.rebase)
        {
            if(j.waitAt!=null&&!readyAt(l,j.waitAt))return;j.waitAt=null;
            Vec3 from=movesEva(j.phase)?eva.position():plane.position();int remaining=Math.max(30,j.duration-j.age);
            if(j.phase==Phase.CRUISE||j.phase==Phase.FERRY||j.phase==Phase.RETURN_FLIGHT)remaining=duration(from,j.to);
            begin(l,j,j.phase,from,j.to,remaining,eva);
        }
        if(j.cancel&&(j.phase==Phase.CRUISE||j.phase==Phase.ASCEND||j.phase==Phase.DESCEND))
        {j.homebound=true;j.cancel=false;j.destination=reception(l,j.serial);begin(l,j,Phase.ASCEND,eva.position(),new Vec3(eva.getX(),cruise(l)-OFFSET,eva.getZ()),120,eva);}
        else if(j.cancel&&j.phase==Phase.RELEASE)
        {
            j.cancel=false;
            if(!j.homebound){j.homebound=true;j.destination=reception(l,j.serial);begin(l,j,Phase.CLAMP,plane.position(),plane.position(),100,eva);}
        }
        else if(j.cancel&&(j.phase==Phase.GROUND_LIFT||j.phase==Phase.ROLL_OUT))
        {j.cancel=false;j.homebound=true;j.destination=reception(l,j.serial);begin(l,j,Phase.ROLL_IN,eva.position(),UNRecoveryR22.home(j.serial).add(0,DECK,0),120,eva);}
        if(cruisePhase(j.phase))AirRouteR39.prefetch(l,j.from,j.to,j.age,j.duration);
        j.age++;double t=smooth(Mth.clamp((double)j.age/Math.max(1,j.duration),0,1));Vec3 point=j.from.lerp(j.to,t);
        if(j.phase==Phase.CRUISE||j.phase==Phase.FERRY||j.phase==Phase.RETURN_FLIGHT)
            readyAt(l,j.from.lerp(j.to,smooth(Mth.clamp((j.age+8D)/Math.max(1,j.duration),0,1))));
        if(!readyAt(l,point))
        {j.age--;if(movesEva(j.phase)){eva.endNervCarrierMotion();}note(l,j,"前方区块正在加载，保持位置");s.setDirty();return;}
        if(movesEva(j.phase))
        {
            lock(eva);
            if(j.phase==Phase.ASCEND&&!j.tilting&&(eva.getY()-j.from.y>=24||j.age>=j.duration/2)){j.tilting=true;EvaAirTransportR31.transition(eva,90,1,Math.max(1,j.duration-j.age));}
            Vec3 wanted=point.subtract(eva.position());
            // Sweep the restrained model's measured parts, preserving the
            // dorsal walkway that lies outside the actual chest and shoulders.
            float yaw=eva.getYRot();if(j.phase==Phase.CRUISE){Vec3 d=j.to.subtract(j.from);float target=(float)Math.toDegrees(Math.atan2(-d.x,d.z));yaw=Mth.approachDegrees(yaw,target,2.5F);}else if(j.phase==Phase.DESCEND&&Float.isFinite(j.landingYaw))yaw=Mth.approachDegrees(yaw,j.landingYaw,2.5F);else if(j.phase==Phase.ROLL_IN||j.phase==Phase.ROLL_OUT)yaw=Mth.approachDegrees(yaw,0,2.5F);
            if(!(j.carrying?AirCradleClearanceR31.clear(eva,wanted,yaw):UNCarrierClearanceR30.clear(eva,wanted)))throw new IllegalStateException("运输路径受阻，停在 "+eva.blockPosition().toShortString());
            Vec3 previous=eva.position();eva.moveOnNervCarrier(point.x,point.y,point.z,yaw);
            eva.publishAirCarrierFrameR39(previous,point);
            if(j.carrying){plane.setPos(point.x,point.y+OFFSET,point.z);plane.setYRot(yaw);plane.cargo(eva.getId(),true,1);}
            else {cart.setPos(point);cart.setYRot(yaw);}
        }
        else if(j.phase==Phase.FERRY||j.phase==Phase.APPROACH||j.phase==Phase.RETREAT||j.phase==Phase.RETURN_FLIGHT)
        {
            plane.setPos(point);Vec3 d=j.to.subtract(j.from);if(d.horizontalDistanceSqr()>1)plane.setYRot(Mth.approachDegrees(plane.getYRot(),(float)Math.toDegrees(Math.atan2(-d.x,d.z)),2.5F));
            plane.cargo(eva.getId(),false,j.phase==Phase.APPROACH?(float)t:0);if(j.phase==Phase.APPROACH)plane.setYRot(Mth.approachDegrees(plane.getYRot(),eva.getYRot(),3.5F));
        }
        else if(j.phase==Phase.CLAMP){lock(eva);plane.cargo(eva.getId(),true,1);}
        else if(j.phase==Phase.RELEASE)
        {
            lock(eva);EvaAirTransportR31.refreshRelease(eva,Math.max(1,j.duration-j.age));plane.cargo(eva.getId(),false,1);
            if(!j.touchdown)
            {
                Vec3 contact=AirCradleClearanceR31.touchdownContact(eva,j.homebound?cart:null);
                j.contactTicks=contact==null?0:j.contactTicks+1;
                if(j.contactTicks>=2){com.projectseele.entity.CombatFoleyR36.airliftTouchdown(eva,contact);j.touchdown=true;s.setDirty();}
            }
        }
        j.planePosition=plane.position();s.cartPositions.put(j.serial,cart.blockPosition());UNRecoveryR22.remember(eva);if(plug!=null)UNRecoveryR22.remember(plug);s.setDirty();
        if(j.age<j.duration)return;
        switch(j.phase)
        {
            case GROUND_LIFT -> begin(l,j,Phase.ROLL_OUT,eva.position(),apron(j.serial),240,eva);
            case ROLL_OUT -> {eva.endNervCarrierMotion();j.pickup=eva.position();begin(l,j,Phase.FERRY,plane.position(),new Vec3(eva.getX(),cruise(l),eva.getZ()),duration(plane.position(),new Vec3(eva.getX(),cruise(l),eva.getZ())),eva);}
            case FERRY ->
            {
                String problem=TransportClearanceR30.pickupProblem(l,eva);
                if(!problem.isEmpty()){j.age=j.duration-1;note(l,j,problem);return;}
                begin(l,j,Phase.APPROACH,plane.position(),eva.position().add(0,OFFSET,0),120,eva);
            }
            case APPROACH -> {plane.setYRot(eva.getYRot());begin(l,j,Phase.CLAMP,plane.position(),plane.position(),100,eva);}
            case CLAMP -> {j.carrying=true;begin(l,j,Phase.ASCEND,eva.position(),new Vec3(eva.getX(),cruise(l)-OFFSET,eva.getZ()),120,eva);}
            case ASCEND -> {Vec3 dest=new Vec3(j.destination.x,cruise(l)-OFFSET,j.destination.z);begin(l,j,Phase.CRUISE,eva.position(),dest,duration(eva.position(),dest),eva);}
            case CRUISE -> {
                if(j.homebound&&cart.position().distanceTo(reception(l,j.serial))>.1){j.age--;note(l,j,"接应载台正在就位，保持空中等待");return;}
                j.landingYaw=j.homebound?receivingHeading(l,j,eva):eva.getYRot();
                if(!Float.isFinite(j.landingYaw))throw new IllegalStateException("接应平台没有容纳当前机体姿态的净空");
                if(j.homebound)cart.setYRot(j.landingYaw);
                j.destination=AirCradleClearanceR31.landingRoot(eva,j.destination,j.landingYaw);
                begin(l,j,Phase.DESCEND,eva.position(),j.destination,160,eva);
            }
            case DESCEND -> {eva.endNervCarrierMotion();begin(l,j,Phase.RELEASE,plane.position(),plane.position(),70,eva);}
            case RELEASE ->
            {
                if(!j.touchdown)throw new IllegalStateException("落点没有稳定承重面，保持运输夹具并等待重新调度");
                j.carrying=false;
                release(eva);
                if(j.homebound){eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.getPersistentData().putBoolean("R30AwaitingIntake",true);EvaShutdownR30.waitingR31(eva,true);}
                begin(l,j,Phase.RETREAT,plane.position(),new Vec3(plane.getX(),cruise(l),plane.getZ()),120,eva);
            }
            case ROLL_IN -> begin(l,j,Phase.GROUND_LOWER,eva.position(),UNRecoveryR22.home(j.serial),30,eva);
            case GROUND_LOWER ->
            {
                var occupant=eva.getPilotEntity();release(eva);
                if(occupant==null){if(plug!=null&&plug.isLockedToEva())plug.resetIndependentAtDock(eva);eva.enterHangarStandby();}
                else if(!EntryPlugDirector.ejectPilotToPlug(l,-1,eva,occupant))throw new IllegalStateException("退出原插入栓请求未被接受");
                begin(l,j,Phase.RETREAT,plane.position(),new Vec3(plane.getX(),cruise(l),plane.getZ()),120,eva);
            }
            case RETREAT -> {Vec3 home=UNRecoveryR22.home(j.serial);Vec3 end=new Vec3(home.x,cruise(l),home.z+500);begin(l,j,Phase.RETURN_FLIGHT,plane.position(),end,duration(plane.position(),end),eva);}
            case RETURN_FLIGHT ->
            {
                if(j.homebound&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_EJECTING){j.age=j.duration-1;note(l,j,"机体已固定，等待退出原插入栓");return;}
                plane.discard();s.jobs.remove(j.serial);s.last.put(j.serial,j.homebound?"机体已交付库外接应平台；请选择“平台送回机库”继续回收":"机体已安全投放，运输机待命");note(l,j,s.last.get(j.serial));s.setDirty();ProjectSeele.LOGGER.info("UN AIRLIFT COMPLETE unit={} plug={} serial={} homebound={}",j.unit,j.plug,j.serial,j.homebound);
            }
            default -> {}
        }
    }
    private static void advanceGround(ServerLevel l,State s,Job j,EvaPrototypeEntity eva,EntryPlugCarrierEntity plug)
    {
        if(j.phase==Phase.HOLD)
        {
            if(!j.cancel){note(l,j,"地面回收暂停，请清理通道后取消并重试，或使用管理员 reset。");return;}
            cancelGround(l,s,j,eva);return;
        }
        if(j.cancel){cancelGround(l,s,j,eva);return;}
        if(!openBase(l,j.serial)){note(l,j,"等待机库排液与舱门完全开启");return;}
        var cart=cart(l,s,j,eva);if(cart==null)return;
        if(j.phase==Phase.PREPARE)
        {
            EvaAirTransportR31.begin(eva);cart.cargo(eva.getId(),false,1);j.landingYaw=eva.getYRot();
            var fit=UNReceivingCradleR40.fit(eva,j.landingYaw);if(fit==null)throw new IllegalStateException("当前载台姿态不能进入机库，需要重新调度");j.groundOffset=fit.offset();
            eva.getPersistentData().remove("R30AwaitingIntake");eva.getPersistentData().remove("R31GroundHold");eva.getPersistentData().remove("R31GroundHoldAt");EvaShutdownR30.waitingR31(eva,false);
            if(eva.position().distanceTo(apron(j.serial).add(j.groundOffset))>8)
                begin(l,j,Phase.GROUND_APPROACH,eva.position(),apron(j.serial).add(j.groundOffset),Math.max(120,(int)Math.ceil(eva.position().distanceTo(apron(j.serial).add(j.groundOffset))/.43)),eva);
            else begin(l,j,Phase.ROLL_IN,eva.position(),UNRecoveryR22.home(j.serial).add(j.groundOffset).add(0,DECK,0),240,eva);
        }
        if(j.phase==Phase.GROUND_APPROACH||j.phase==Phase.ROLL_IN||j.phase==Phase.GROUND_LOWER)
        {
            if(j.rebase){j.from=eva.position();j.duration=Math.max(30,j.duration-j.age);j.age=0;j.rebase=false;eva.beginNervCarrierMotion(j.from,j.to,j.duration);}
            double t=smooth(Mth.clamp((double)(j.age+1)/j.duration,0,1));Vec3 at=j.from.lerp(j.to,t);
            if(!readyAt(l,at))return;
            lock(eva);Vec3 wanted=at.subtract(eva.position());
            float heading=Float.isFinite(j.landingYaw)?j.landingYaw:eva.getYRot();
            if(!AirCradleClearanceR31.clear(eva,wanted,heading))
            {eva.endNervCarrierMotion();throw new IllegalStateException("入库通道受阻："+eva.blockPosition().toShortString());}
            eva.moveOnNervCarrier(at.x,at.y,at.z,heading);cart.setPos(at);cart.setYRot(eva.getYRot());
            j.age++;s.cartPositions.put(j.serial,cart.blockPosition());UNRecoveryR22.remember(eva);s.setDirty();
            if(j.age<j.duration)return;
            if(j.phase==Phase.GROUND_APPROACH){begin(l,j,Phase.ROLL_IN,eva.position(),UNRecoveryR22.home(j.serial).add(j.groundOffset).add(0,DECK,0),240,eva);return;}
            if(j.phase==Phase.ROLL_IN){begin(l,j,Phase.GROUND_LOWER,eva.position(),AirCradleClearanceR31.landingRoot(eva,UNRecoveryR22.home(j.serial).add(j.groundOffset),eva.getYRot()),30,eva);return;}
            // Rebase the stored root after the measured surface is supported.
            // Preserve the world-space body; do not drive its collision margin
            // through the floor just to match the canonical entity coordinate.
            var home=UNRecoveryR22.home(j.serial);var offset=eva.position().subtract(home);
            if(EvaShutdownR30.disabled(eva)&&offset.lengthSqr()>1e-10)
            {
                var pose=EvaBodyPose.sample(eva,0);
                var local=offset.toVector3f().rotateY(-(180-eva.getYRot())*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
                pose.positions.get("root").add(local);pose.dirty();
                EvaShutdownR30.physicalRest(eva,pose,eva.getBoundingBox().move(offset));
            }
            cart.setPos(eva.position());s.cartPositions.put(j.serial,cart.blockPosition());eva.moveOnNervCarrier(home.x,home.y,home.z,eva.getYRot());
            eva.endNervCarrierMotion();var occupant=eva.getPilotEntity();eva.normalizeAfterTransportR30(true);
            if(occupant!=null)
            {
                if(!EntryPlugDirector.ejectPilotToPlug(l,-1,eva,occupant))throw new IllegalStateException("原插入栓退出请求失败");
                j.phase=Phase.RELEASE;note(l,j,"机体已固定，正在退出原插入栓");s.setDirty();return;
            }
            if(plug!=null&&plug.isLockedToEva())plug.resetIndependentAtDock(eva);
            eva.enterHangarStandby();finishGround(l,s,j,eva);return;
        }
        if(j.phase==Phase.RELEASE&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED)
        {eva.enterHangarStandby();finishGround(l,s,j,eva);}
    }
    private static void cancelGround(ServerLevel l,State s,Job j,EvaPrototypeEntity eva)
    {
        eva.endNervCarrierMotion();EvaAirTransportR31.hold(eva);eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.setDeltaMovement(Vec3.ZERO);
        eva.getPersistentData().putBoolean("R31GroundHold",true);eva.getPersistentData().putLong("R31GroundHoldAt",eva.blockPosition().asLong());
        eva.getPersistentData().putBoolean("R30AwaitingIntake",true);EvaShutdownR30.waitingR31(eva,true);
        s.jobs.remove(j.serial);s.last.put(j.serial,"地面回收已取消，载台保持原位。清理通道后可重新请求入库。");note(l,j,s.last.get(j.serial));s.setDirty();
    }
    private static void finishGround(ServerLevel l,State s,Job j,EvaPrototypeEntity eva)
    {
        var receiver=cart(l,s,j,eva);if(receiver!=null)receiver.cargo(-1,false,0);
        s.jobs.remove(j.serial);s.last.put(j.serial,EvaShutdownR30.wreck(eva)?"损毁机体已固定在原库位，等待维修。":"机体已回到原库位，回收完成。");note(l,j,s.last.get(j.serial));s.setDirty();
    }
    private UNAirLiftR29() {}
}
