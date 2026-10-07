package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.server.level.*;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.*;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Same-cavern VTOL, original-pose cargo, and positive mechanical receiver handoff. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervUndergroundAirLiftR50
{
    private static final double EMPTY_CRUISE_SPEED=4, LOADED_CRUISE_SPEED=2.8;
    static final double PLANE_HALF_X=69, PLANE_MIN_Y=-11, PLANE_MAX_Y=19, PLANE_MIN_Z=-56, PLANE_MAX_Z=58;
    private static final Map<ServerLevel,Map<UUID,String>> LAST_CONNECTOR_REFUSAL_R50=new WeakHashMap<>();
    private static final int PICKUP_STILL_TICKS=12;
    private static final class PickupObservation
    {
        long tick=Long.MIN_VALUE;Vec3 previous=Vec3.ZERO,anchor=Vec3.ZERO;
        float previousYaw,anchorYaw;int still;
    }
    private static final Map<EvaUnit01Entity,PickupObservation> PICKUP_OBSERVATIONS=new WeakHashMap<>();
    private enum Phase { PREPARE,TAKEOFF,FERRY,APPROACH,CLAMP,ASCEND,STOW,CRUISE,UNSTOW,DESCEND,HANDOFF,RETREAT,RETURN,LAND }
    private static final TicketType<ChunkPos> TICKET=TicketType.create("nerv_underground_airlift_r50",Comparator.comparingLong(ChunkPos::toLong),120);
    private static final class Job
    {
        UUID eva,owner;int variant,age,duration,cursor,contactTicks;Phase phase=Phase.PREPARE;boolean carrying,paused,rebase,touchdownPlayed;
        Vec3 pickup=Vec3.ZERO,from=Vec3.ZERO,to=Vec3.ZERO;float yawFrom,yawTo;String pickupNode="",note="地下机场收到运输指令";
        List<Vec3> path=List.of();CompoundTag extra=new CompoundTag();
    }
    private static final class State extends SavedData
    {
        UUID aircraft;Vec3 planeAt=Vec3.ZERO;Job job;String last="地下运输机待命";CompoundTag extra=new CompoundTag();
        static State load(CompoundTag tag)
        {
            var s=new State();s.extra=tag.copy();if(tag.hasUUID("Aircraft"))s.aircraft=tag.getUUID("Aircraft");s.planeAt=vec(tag,"Plane");s.last=tag.getString("Last");
            if(tag.contains("Job"))
            {
                var n=tag.getCompound("Job");var j=new Job();j.extra=n.copy();j.eva=n.getUUID("Eva");j.owner=n.getUUID("Owner");j.variant=n.getInt("Variant");j.phase=Phase.valueOf(n.getString("Phase"));
                j.age=n.getInt("Age");j.duration=n.getInt("Duration");j.cursor=n.getInt("Cursor");j.carrying=n.getBoolean("Carrying");j.pickup=vec(n,"Pickup");j.from=vec(n,"From");j.to=vec(n,"To");
                j.contactTicks=n.getInt("ContactTicks");j.touchdownPlayed=n.getBoolean("TouchdownPlayed");
                j.yawFrom=n.getFloat("YawFrom");j.yawTo=n.getFloat("YawTo");j.pickupNode=n.getString("PickupNode");j.note=n.getString("Note");var path=new ArrayList<Vec3>();
                for(var raw:n.getList("Path",Tag.TAG_COMPOUND))path.add(vec((CompoundTag)raw,"At"));j.path=List.copyOf(path);
                if(j.variant<0||j.variant>2||j.age<0||j.duration<0||j.age>j.duration||j.cursor<0||j.cursor>j.path.size())throw new IllegalArgumentException("Invalid underground flight clock");j.rebase=true;s.job=j;
            }
            return s;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            tag=extra.copy();tag.putInt("Version",50);if(aircraft!=null)tag.putUUID("Aircraft",aircraft);put(tag,"Plane",planeAt);tag.putString("Last",last);
            if(job==null)tag.remove("Job");else
            {
                var j=job;var n=j.extra.copy();n.putUUID("Eva",j.eva);n.putUUID("Owner",j.owner);n.putInt("Variant",j.variant);n.putString("Phase",j.phase.name());n.putInt("Age",j.age);n.putInt("Duration",j.duration);n.putInt("Cursor",j.cursor);n.putBoolean("Carrying",j.carrying);
                put(n,"Pickup",j.pickup);put(n,"From",j.from);put(n,"To",j.to);n.putFloat("YawFrom",j.yawFrom);n.putFloat("YawTo",j.yawTo);n.putString("PickupNode",j.pickupNode);n.putString("Note",j.note);n.putInt("ContactTicks",j.contactTicks);n.putBoolean("TouchdownPlayed",j.touchdownPlayed);var list=new ListTag();for(var p:j.path){var row=new CompoundTag();put(row,"At",p);list.add(row);}n.put("Path",list);tag.put("Job",n);
            }
            return tag;
        }
    }
    private static State state(ServerLevel level){return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_nerv_underground_airlift_r50");}
    private static Vec3 vec(CompoundTag tag,String k){var v=new Vec3(tag.getDouble(k+"X"),tag.getDouble(k+"Y"),tag.getDouble(k+"Z"));if(!Double.isFinite(v.x+v.y+v.z))throw new IllegalArgumentException("Nonfinite flight coordinate");return v;}
    private static void put(CompoundTag tag,String k,Vec3 v){tag.putDouble(k+"X",v.x);tag.putDouble(k+"Y",v.y);tag.putDouble(k+"Z",v.z);}
    public static boolean registeredPickup(ServerLevel level,EvaUnit01Entity eva)
    {var site=NervUndergroundTransportSiteR50.get(level);return site!=null&&eva!=null&&eva.level()==level&&site.pickupContains(eva.position())
            &&site.airContains(planeBox(eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0),eva.getYRot()));}
    public static boolean pending(ServerLevel level,EvaUnit01Entity eva)
    {var j=state(level).job;return j!=null&&eva!=null&&j.eva.equals(eva.getUUID())&&!Set.of(Phase.RETREAT,Phase.RETURN,Phase.LAND).contains(j.phase);}
    public static boolean ownsMotion(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return false;var j=state(level).job;
        return j!=null&&j.eva.equals(eva.getUUID())&&(j.carrying||Set.of(Phase.APPROACH,Phase.CLAMP).contains(j.phase))
                &&!EvaGroundReceiverR50.active(eva);
    }
    public static boolean busy(ServerLevel level){return state(level).job!=null;}
    public static String status(ServerLevel level){var s=state(level);return s.job==null?s.last:NervStaffDialogue.unitName(s.job.variant)+"："+s.job.note;}
    public static boolean directReceiver(ServerLevel level,int variant,EvaUnit01Entity eva)
    {
        return eva!=null&&UndergroundSortieR48.undergroundRecoveryRouteR50(level,variant,eva)
                &&(eva.position().distanceToSqr(UndergroundSortieR48.padFeet(variant))<=36
                    ||eva.position().distanceToSqr(UndergroundSortieR48.airReceiverFeetR50(variant))<=.25);
    }
    public static int ownedCancelVariantR50(ServerPlayer caller)
    {
        var j=state(caller.serverLevel()).job;if(j==null||!j.owner.equals(caller.getUUID()))return -1;
        var fleet=EvaFleetSavedData.get(caller.server).entry(j.variant).orElse(null);
        return fleet!=null&&fleet.canonicalId().equals(j.eva)?j.variant:-1;
    }
    public static String cancel(ServerPlayer caller,int variant)
    {
        var s=state(caller.serverLevel());var j=s.job;if(j==null)return null;
        if(variant<0||variant>2||ownedCancelVariantR50(caller)!=variant)return "本机没有由您下达的地下运输任务，请核对机体编号。";
        if(j.phase==Phase.PREPARE){s.job=null;s.last="运输指令已取消，机体与运输机保持待命。";s.setDirty();return s.last;}
        if(!j.carrying&&Set.of(Phase.TAKEOFF,Phase.FERRY).contains(j.phase))
        {
            var site=NervUndergroundTransportSiteR50.get(caller.serverLevel());var plane=ServiceAircraftR32.find(caller.serverLevel(),s.aircraft);
            if(site==null||plane==null)return "尚未确认运输机当前位置，取消指令暂未执行。";
            if(j.phase==Phase.TAKEOFF)begin(s,j,plane,Phase.LAND,site.stand,site.standYaw,.7);
            else
            {
                var reverse=new ArrayList<Vec3>();reverse.add(j.from);
                for(int i=j.cursor-1;i>=0;i--)if(reverse.get(reverse.size()-1).distanceToSqr(j.path.get(i))>.0001)reverse.add(j.path.get(i));
                Vec3 first=j.path.get(0);
                if(reverse.get(reverse.size()-1).distanceToSqr(first)>.0001)reverse.add(first);
                String firstNode=site.nodes.entrySet().stream().filter(e->e.getValue().distanceToSqr(first)<.0001).map(Map.Entry::getKey).findFirst().orElse(null);
                if(firstNode==null)return "返场航线尚未确认，运输机暂时悬停。";
                for(var point:site.path(firstNode,site.airportNode))
                    if(reverse.get(reverse.size()-1).distanceToSqr(point)>.0001)reverse.add(point);
                path(s,j,plane,Phase.RETURN,reverse,EMPTY_CRUISE_SPEED);
            }
            note(caller.serverLevel(),s,j,"接载已取消，运输机正在返场。");return j.note;
        }
        return "吊装已经开始，将先把机体送到接应平台，再安排运输机返场。";
    }
    public static String request(ServerPlayer caller,int variant)
    {
        if(variant<0||variant>2||!NervStaffDialogue.authorized(caller)||!StaffConversationR24.radioAllowed(caller))return "请由机体操作者使用 NERV 指挥通信呼叫运输。";
        var level=caller.serverLevel();EvaLogisticsDirector.loadControlTarget(level,variant);var eva=EvaLogisticsDirector.canonicalUnit(level,variant);
        String ownership=EntryPlugEjectionR48.recoveryCallerBlocker(caller,eva);if(!ownership.isEmpty())return ownership;
        return schedule(level,eva,caller.getUUID());
    }
    public static boolean requestPilotReturn(ServerLevel level,EvaUnit01Entity eva,UUID commander)
    {
        if(eva==null||!(eva.getPilotEntity() instanceof TrainingPilotEntity pilot)||commander==null)return false;
        return PilotReturnR39.ownsRecoveryR50(level,eva,commander)
                &&schedule(level,eva,commander).startsWith("地下运输部门收到");
    }
    private static String schedule(ServerLevel level,EvaUnit01Entity eva,UUID commander)
    {
        var site=NervUndergroundTransportSiteR50.get(level);if(site==null)return "地下机场尚未就绪，请保持位置，等待运输管制通知。";
        if(eva==null||eva.isExperimentalUnit()||!registeredPickup(level,eva))return "此处不能安全接载，请驶入开阔接载区后再呼叫运输。";
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(eva.getUnitVariant()).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(eva.getUUID())||fleet.phase()!=EvaFleetSavedData.Phase.DEPLOYED)return "机体尚未完成出动，请到安全位置后再呼叫运输。";
        if(EvaGroundReceiverR50.active(eva))return "接应平台正在接收机体，运输机保持待命。";
        var s=state(level);if(s.job!=null)return "地下运输机已有任务："+s.job.note;
        if(EvaAirTransportR31.active(eva)||eva.hasActiveCarrierMotion()||eva.isLaunchSequenceActive())return "机体正在转运，请等当前作业结束后再安排运输。";
        String node=site.nearest(eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0));
        if(node==null)
        {
            connectorRefusedR50(level,eva,null,site.connectorRefusalR50(eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0)));
            return "接载点的转向净空不足，请移至更开阔处。";
        }
        if(site.path(site.airportNode,node)==null)
        {connectorRefusedR50(level,eva,node,"airport_graph_path_missing");return "接载点尚无安全航线通往地下机场，请核对位置。";}
        if(s.aircraft!=null&&!s.aircraft.equals(site.aircraft))return "运输机识别信号不符，机场正在核对，暂缓接载。";
        var j=new Job();j.eva=eva.getUUID();j.owner=commander;j.variant=eva.getUnitVariant();j.pickup=eva.position();j.pickupNode=node;s.job=j;if(s.aircraft==null)s.planeAt=site.stand;s.aircraft=site.aircraft;s.setDirty();
        var refusals=LAST_CONNECTOR_REFUSAL_R50.get(level);if(refusals!=null)refusals.remove(eva.getUUID());
        return "地下运输部门收到。正在核对航线，请保持位置，等待送往本机接应平台。";
    }
    private static void connectorRefusedR50(ServerLevel level,EvaUnit01Entity eva,String nearest,String reason)
    {
        var failures=LAST_CONNECTOR_REFUSAL_R50.computeIfAbsent(level,key->new HashMap<>());
        String cause=reason+":"+nearest;
        if(cause.equals(failures.put(eva.getUUID(),cause)))return;
        ProjectSeele.LOGGER.info("R50 underground pickup connector held: originalEva={} root={} yaw={} nearest={} reason={}",
                eva.getUUID(),eva.position(),eva.getYRot(),nearest==null?"none":nearest,reason);
    }
    private static void note(ServerLevel level,State s,Job j,String message)
    {
        if(message.equals(j.note))return;j.note=message;s.last=message;s.setDirty();var caller=level.getServer().getPlayerList().getPlayer(j.owner);
        if(caller!=null)caller.sendSystemMessage(net.minecraft.network.chat.Component.literal("[地下运输管制] "+message));
    }
    private static boolean loaded(ServerLevel level,AABB body)
    {
        if(body.minY<level.getMinBuildHeight()||body.maxY>=level.getMaxBuildHeight())return false;boolean ready=true;
        for(int x=Mth.floor(body.minX)>>4;x<=Mth.floor(body.maxX)>>4;x++)for(int z=Mth.floor(body.minZ)>>4;z<=Mth.floor(body.maxZ)>>4;z++)
        {var p=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,p,2,p);if(level.getChunkSource().getChunkNow(x,z)==null)ready=false;}
        return ready;
    }
    private static AABB planeBox(Vec3 at,float yaw)
    {
        double a=-yaw*Mth.DEG_TO_RAD;AABB result=null;
        // Selected un_transport_body exact bounds include actual gear minY=-11;
        // all four spinning rotors remain inside this horizontal envelope.
        for(double x:new double[]{-PLANE_HALF_X,PLANE_HALF_X})for(double y:new double[]{PLANE_MIN_Y,PLANE_MAX_Y})for(double z:new double[]{PLANE_MIN_Z,PLANE_MAX_Z})
        {var p=at.add(x*Math.cos(a)+z*Math.sin(a),y,-x*Math.sin(a)+z*Math.cos(a));var box=new AABB(p,p);result=result==null?box:result.minmax(box);}
        return result;
    }
    private static boolean transientObject(Entity entity)
    {return !entity.canBeCollidedWith()&&(entity instanceof ItemEntity||entity instanceof ExperienceOrb||entity instanceof Projectile||entity instanceof AreaEffectCloud);}
    private static String planeClear(ServerLevel level,NervUndergroundTransportSiteR50 site,UNTransportEntity plane,EvaUnit01Entity eva,Vec3 to,float yaw)
    {
        double turn=Math.abs(Mth.wrapDegrees(yaw-plane.getYRot()))*Mth.DEG_TO_RAD;
        var body=planeBox(plane.position(),plane.getYRot()).minmax(planeBox(to,yaw)).inflate(.002+92*turn*turn/8).deflate(.004);
        if(!site.airContains(body))return "航线净空不足，运输机已悬停。";
        if(!loaded(level,body))return "正在确认航线前方净空。";
        for(var shape:level.getBlockCollisions(plane,body))if(!shape.isEmpty())return "运输机前方有障碍，已悬停等待。";
        for(var other:level.getEntities(plane,body,e->e.isAlive()&&!e.isSpectator()&&e!=eva&&e.getRootVehicle()!=eva&&!transientObject(e)))
        {
            if(other instanceof UNTransportEntity aircraft&&!aircraft.groundCart())
            {if(planeBox(aircraft.position(),aircraft.getYRot()).intersects(body))return "前方有其他运输机，已悬停等待。";}
            else return "航线内有人或设备，运输机已悬停，请清空通路。";
        }
        return "";
    }
    private static void begin(State s,Job j,UNTransportEntity plane,Phase phase,Vec3 to,float yaw,double speed)
    {
        j.phase=phase;j.from=plane.position();j.to=to;j.yawFrom=plane.getYRot();j.yawTo=yaw;j.age=0;
        j.duration=Math.max(40,Math.max(Mth.ceil(j.from.distanceTo(to)*1.875/speed),Mth.ceil(Math.abs(Mth.wrapDegrees(yaw-j.yawFrom))*1.875/1.5)));
        j.rebase=false;s.setDirty();
    }
    private static float heading(Vec3 from,Vec3 to,float fallback)
    {var delta=to.subtract(from);return delta.horizontalDistanceSqr()<1e-6?fallback:(float)Math.toDegrees(Math.atan2(-delta.x,delta.z));}
    private static double phaseSpeed(Phase phase)
    {
        return switch(phase)
        {
            case FERRY,RETURN->EMPTY_CRUISE_SPEED;
            case CRUISE->LOADED_CRUISE_SPEED;
            case TAKEOFF->.7;
            case APPROACH,LAND->.25;
            case ASCEND->.35;
            case DESCEND->.2;
            case RETREAT->.5;
            default->throw new IllegalStateException("No translating speed for "+phase);
        };
    }
    private static void path(State s,Job j,UNTransportEntity plane,Phase phase,List<Vec3> points,double speed)
    {j.path=List.copyOf(points);j.cursor=0;begin(s,j,plane,phase,j.path.get(0),heading(plane.position(),j.path.get(0),plane.getYRot()),speed);}
    private static List<Vec3> pickupPath(NervUndergroundTransportSiteR50 site,Job j)
    {
        var points=new ArrayList<>(site.path(site.airportNode,j.pickupNode));
        var above=new Vec3(j.pickup.x,site.nodes.get(j.pickupNode).y,j.pickup.z);
        if(points.get(points.size()-1).distanceToSqr(above)>.0001)points.add(above);
        return points;
    }
    private static void lock(EvaUnit01Entity eva){eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.setDeltaMovement(Vec3.ZERO);}
    private static boolean actualPickupStillR50(EvaUnit01Entity eva)
    {
        var sample=PICKUP_OBSERVATIONS.computeIfAbsent(eva,key->new PickupObservation());
        long tick=eva.level().getGameTime();if(sample.tick==tick)return sample.still>=PICKUP_STILL_TICKS;
        var position=eva.position();float yaw=eva.getYRot();
        boolean consecutive=tick==sample.tick+1;
        // Native ridden travel retains the next gravity impulse in Motion.
        // Observe real roots, not that velocity, and reject accumulated slow
        // drift or a real body turn even when one individual step is small.
        boolean stable=consecutive&&position.distanceToSqr(sample.previous)<=.01*.01
                &&position.distanceToSqr(sample.anchor)<=.02*.02
                &&Math.abs(Mth.wrapDegrees(yaw-sample.previousYaw))<=.05F
                &&Math.abs(Mth.wrapDegrees(yaw-sample.anchorYaw))<=.15F;
        if(stable)sample.still=Math.min(PICKUP_STILL_TICKS,sample.still+1);
        else {sample.still=0;sample.anchor=position;sample.anchorYaw=yaw;}
        sample.tick=tick;sample.previous=position;sample.previousYaw=yaw;
        return sample.still>=PICKUP_STILL_TICKS;
    }
    private static String pickupClear(ServerLevel level,NervUndergroundTransportSiteR50 site,EvaUnit01Entity eva,String node)
    {
        if(!site.pickupContains(eva.position())||node==null)return "当前机体位置不在可通航的接载区内。";
        if(eva.hasLiveActionForRender(1)||EvaCombatR31.active(eva)||eva.isFirstBattleActive()
                ||eva.isLaunchSequenceActive()||eva.hasActiveCarrierMotion())
        {PICKUP_OBSERVATIONS.remove(eva);return "机体仍在动作中，请结束动作后等待接载。";}
        if(!actualPickupStillR50(eva))return "请保持机体停稳，运输机正在准备吊装。";
        var hover=eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0);
        if(!site.airContains(planeBox(hover,eva.getYRot())))return "机体上方没有足够的悬停空间，请移至开阔处。";
        if(!loaded(level,new AABB(eva.position(),hover.add(0,22,0)).inflate(76,0,76)))return "正在确认接载位置与吊装净空。";
        // Retain the whole footprint before testing its bearing surface; an
        // unloaded contact chunk must not become a permanent unsupported hold.
        // onGround and the next gravity impulse are not evidence of support.
        if(AirCradleClearanceR31.touchdownContact(eva)==null)
        {PICKUP_OBSERVATIONS.remove(eva);return "机体尚未稳妥落地，请停在承载面上等待接载。";}
        double rise=Math.max(1,site.nodes.get(node).y-NervUndergroundTransportSiteR50.HOIST-eva.getY());
        Boolean clear=VerticalCarrierSweepR40.clearAt(level,eva,EvaBodyPose.sample(eva,1),0,eva.getYRot(),eva.position(),rise);
        if(clear==null)return "机体状态尚未确认，吊架暂缓展开，请等待检查。";
        return clear?"":"机体上方有障碍，请移至开阔处等待接载。";
    }
    private static void rotateLoad(State s,Job j,EvaUnit01Entity eva,Phase phase,float pitch)
    {
        j.phase=phase;j.age=0;j.duration=100;j.rebase=false;
        EvaAirTransportR31.transition(eva,pitch,1,100);s.setDirty();
    }
    private static String cargoClear(ServerLevel level,NervUndergroundTransportSiteR50 site,UNTransportEntity plane,EvaUnit01Entity eva,Vec3 delta,float yaw)
    {
        var envelope=AirCradleClearanceR31.envelopeR50(eva,delta,yaw);
        if(!loaded(level,envelope))return "正在确认载荷前方净空。";
        if(!site.airContains(envelope))return "载荷前方净空不足，运输机已悬停。";
        if(!level.getEntities(eva,envelope,e->e.isAlive()&&!e.isSpectator()&&e!=plane&&e.getRootVehicle()!=eva&&!transientObject(e)).isEmpty())
            return "载荷前方有人或设备，运输机已悬停，请清空通路。";
        if(!AirCradleClearanceR31.clear(eva,delta,yaw))return "载荷前方有障碍，运输机已悬停。";
        return "";
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;var site=NervUndergroundTransportSiteR50.get(level);if(site==null)return;
        var s=state(level);if(s.job==null&&event.getServer().getTickCount()%20!=0)return;
        if(s.aircraft==null){s.aircraft=site.aircraft;s.planeAt=site.stand;s.setDirty();}if(!s.aircraft.equals(site.aircraft))return;
        var probe=new AABB(s.planeAt,s.planeAt).inflate(100);loaded(level,probe);var plane=ServiceAircraftR32.find(level,s.aircraft);
        if(plane==null){if(s.job!=null)note(level,s,s.job,"地下机场正在接通运输机信号。");return;}
        if(!plane.isNerv()||plane.groundCart()){if(s.job!=null)note(level,s,s.job,"运输机识别信号异常，暂停接载，等待机场确认。");return;}
        s.planeAt=plane.position();if(s.job==null)return;level.resetEmptyTime();
        try{advance(level,site,s,plane);}catch(Exception failure){if(s.job!=null){var eva=ServiceAircraftR32.payload(level,s.job.eva);if(eva!=null&&s.job.carrying){eva.endNervCarrierMotion();EvaAirTransportR31.hold(eva);}note(level,s,s.job,"运输安全暂停："+failure.getMessage());}ProjectSeele.LOGGER.error("R50 underground airlift held without actor reset",failure);}
    }
    private static void advance(ServerLevel level,NervUndergroundTransportSiteR50 site,State s,UNTransportEntity plane)
    {
        var j=s.job;boolean retreat=Set.of(Phase.RETREAT,Phase.RETURN,Phase.LAND).contains(j.phase);var eva=ServiceAircraftR32.payload(level,j.eva);
        if(eva==null&&!retreat)
        {loaded(level,new AABB(j.pickup,j.pickup).inflate(72));EvaLogisticsDirector.loadControlTarget(level,j.variant);note(level,s,j,"正在接通机体信号，请保持位置。");return;}
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(j.variant).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(j.eva)){note(level,s,j,"机体识别信号不符，运输暂停，请核对编号。");return;}
        if(j.carrying)plane.cargo(eva.getId(),true,1);
        var caller=level.getServer().getPlayerList().getPlayer(j.owner);
        if(!retreat&&(caller==null||caller.serverLevel()!=level||!caller.isAlive()||caller.isSpectator()||!NervStaffDialogue.authorized(caller)))
        {if(eva!=null&&EvaAirTransportR31.active(eva)){eva.endNervCarrierMotion();EvaAirTransportR31.hold(eva);}j.paused=true;note(level,s,j,"操作员通信中断，运输机已悬停，等待恢复联络。");return;}
        if(j.paused){j.paused=false;j.rebase=true;}
        if(j.phase==Phase.PREPARE)
        {
            if(!site.pickupContains(eva.position())||eva.hasLiveActionForRender(1)||EvaCombatR31.active(eva)){note(level,s,j,"请将机体停稳在接载区，等待吊装。");return;}
            j.pickup=eva.position();j.pickupNode=site.nearest(j.pickup.add(0,NervUndergroundTransportSiteR50.HOIST,0));
            if(j.pickupNode==null||site.path(site.airportNode,j.pickupNode)==null){note(level,s,j,"航线信息有变化，运输机保持待命，等待重新确认。");return;}
            String pickupFault=pickupClear(level,site,eva,j.pickupNode);
            if(!pickupFault.isEmpty()){note(level,s,j,pickupFault);return;}
            begin(s,j,plane,Phase.TAKEOFF,site.nodes.get(site.airportNode),site.standYaw,.7);note(level,s,j,"地下运输机已起飞，正在前往接载点。");return;
        }
        if(j.phase==Phase.HANDOFF)
        {
            if(!EvaGroundReceiverR50.active(eva)&&!j.touchdownPlayed)
            {
                Vec3 contact=AirCradleClearanceR31.touchdownContact(eva);
                j.contactTicks=contact==null?0:j.contactTicks+1;s.setDirty();
                if(j.contactTicks<2){note(level,s,j,"正在确认机体落稳，请等待接应平台接收。");return;}
                CombatFoleyR36.airliftTouchdown(eva,contact);j.touchdownPlayed=true;s.setDirty();
            }
            var reply=UndergroundSortieR48.acceptAirDeliveryR50(level,j.variant,eva,j.owner);
            if(!reply.accepted()){note(level,s,j,reply.message());return;}
            // The receiver now owns the shared AirFrame. Never clear or normalize it.
            j.carrying=false;plane.cargo(-1,false,0);begin(s,j,plane,Phase.RETREAT,site.nodes.get(site.receivers.get(j.variant).node()),plane.getYRot(),.5);note(level,s,j,"接应平台已接收机体，吊架解除，运输机开始返场。");return;
        }
        if(j.phase==Phase.CLAMP)
        {
            String aircraftFault=planeClear(level,site,plane,eva,plane.position(),plane.getYRot());if(!aircraftFault.isEmpty()){EvaAirTransportR31.hold(eva);note(level,s,j,aircraftFault);return;}
            lock(eva);
            if(EvaAirTransportR31.cradleStateR50(eva).getFloat("ToRestraint")<.999F)
                EvaAirTransportR31.transition(eva,0,1,Math.max(20,80-j.age));
            if(!AirCradleClearanceR31.clear(eva,Vec3.ZERO,eva.getYRot())){EvaAirTransportR31.hold(eva);note(level,s,j,"吊架周围有障碍，暂停吊装，请清空净空。");return;}
            plane.cargo(eva.getId(),false,1);j.age=Math.min(80,j.age+1);s.setDirty();if(j.age<80||EvaAirTransportR31.restraint(eva,0)<.999F)return;
            j.carrying=true;plane.cargo(eva.getId(),true,1);begin(s,j,plane,Phase.ASCEND,new Vec3(eva.getX(),site.nodes.get(j.pickupNode).y,eva.getZ()),eva.getYRot(),.35);note(level,s,j,"机体已固定，开始垂直起吊");return;
        }
        if(j.phase==Phase.STOW||j.phase==Phase.UNSTOW)
        {
            lock(eva);float goal=j.phase==Phase.STOW?90:0;
            String problem=planeClear(level,site,plane,eva,plane.position(),plane.getYRot());
            if(problem.isEmpty())
            {
                if(Math.abs(EvaAirTransportR31.cradleStateR50(eva).getFloat("ToPitch")-goal)>.01F)
                    EvaAirTransportR31.transition(eva,goal,1,Math.max(20,j.duration-j.age));
                problem=cargoClear(level,site,plane,eva,Vec3.ZERO,plane.getYRot());
            }
            if(!problem.isEmpty()){EvaAirTransportR31.hold(eva);note(level,s,j,problem);return;}
            j.age=Math.min(j.duration,j.age+1);s.setDirty();
            if(j.age<j.duration||Math.abs(EvaAirTransportR31.acceptedPitch(eva)-goal)>.01F)return;
            var receiver=site.receivers.get(j.variant);
            if(j.phase==Phase.STOW)
            {path(s,j,plane,Phase.CRUISE,site.path(j.pickupNode,receiver.node()),LOADED_CRUISE_SPEED);note(level,s,j,"机体已横放固定，正在前往接应平台。");}
            else
            {
                var touchdown=AirCradleClearanceR31.landingRoot(eva,receiver.feet(),receiver.yaw());
                begin(s,j,plane,Phase.DESCEND,touchdown.add(0,NervUndergroundTransportSiteR50.HOIST,0),receiver.yaw(),.2);
                note(level,s,j,"机体已恢复接载姿态，吊架开始缓慢下放。");
            }
            return;
        }
        if(j.rebase)begin(s,j,plane,j.phase,j.to,j.yawTo,phaseSpeed(j.phase));
        double t=Math.min(1,(j.age+1D)/j.duration);t=t*t*t*(t*(t*6-15)+10);var next=j.from.lerp(j.to,t);float yaw=j.yawFrom+Mth.wrapDegrees(j.yawTo-j.yawFrom)*(float)t;
        String obstacle=planeClear(level,site,plane,eva,next,yaw);if(!obstacle.isEmpty()){if(j.carrying)EvaAirTransportR31.hold(eva);note(level,s,j,obstacle);return;}
        if(j.carrying)
        {
            lock(eva);var target=next.add(0,-NervUndergroundTransportSiteR50.HOIST,0);var delta=target.subtract(eva.position());
            String cargoFault=cargoClear(level,site,plane,eva,delta,yaw);
            if(!cargoFault.isEmpty()){eva.endNervCarrierMotion();EvaAirTransportR31.hold(eva);note(level,s,j,cargoFault);return;}
            var previous=eva.position();eva.moveOnNervCarrier(target.x,target.y,target.z,yaw);eva.publishAirCarrierFrameR39(previous,target);plane.cargo(eva.getId(),true,1);
        }
        plane.setPos(next);plane.setYRot(yaw);plane.setHoistDistance((float)NervUndergroundTransportSiteR50.HOIST);s.planeAt=next;j.age=Math.min(j.duration,j.age+1);s.setDirty();if(j.age<j.duration)return;
        if(Set.of(Phase.FERRY,Phase.CRUISE,Phase.RETURN).contains(j.phase)&&j.cursor+1<j.path.size())
        {j.cursor++;begin(s,j,plane,j.phase,j.path.get(j.cursor),heading(plane.position(),j.path.get(j.cursor),plane.getYRot()),j.carrying?LOADED_CRUISE_SPEED:EMPTY_CRUISE_SPEED);return;}
        switch(j.phase)
        {
            case TAKEOFF->path(s,j,plane,Phase.FERRY,pickupPath(site,j),EMPTY_CRUISE_SPEED);
            case FERRY->{String pickupFault=pickupClear(level,site,eva,j.pickupNode);if(!pickupFault.isEmpty()){note(level,s,j,pickupFault);return;}
                if(eva.position().subtract(j.pickup).horizontalDistanceSqr()>1)
                {
                    String nextNode=site.nearest(eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0));
                    if(nextNode==null){note(level,s,j,"机体已离开接载区，请停回开阔位置等待。");return;}
                    var revised=new ArrayList<Vec3>();revised.add(site.nodes.get(j.pickupNode));
                    revised.addAll(site.path(j.pickupNode,nextNode));j.pickup=eva.position();j.pickupNode=nextNode;
                    revised.add(new Vec3(j.pickup.x,site.nodes.get(nextNode).y,j.pickup.z));
                    path(s,j,plane,Phase.FERRY,revised,EMPTY_CRUISE_SPEED);note(level,s,j,"机体位置已更新，运输机重新接近");return;
                }
                EvaAirTransportR31.begin(eva);lock(eva);begin(s,j,plane,Phase.APPROACH,eva.position().add(0,NervUndergroundTransportSiteR50.HOIST,0),eva.getYRot(),.25);note(level,s,j,"已到达机体上方，吊架开始下降");}
            case APPROACH->{EvaAirTransportR31.transition(eva,0,1,80);j.phase=Phase.CLAMP;j.age=0;j.duration=80;s.setDirty();}
            case ASCEND->{rotateLoad(s,j,eva,Phase.STOW,90);note(level,s,j,"机体已离地，吊架开始翻转，请保持通信。");}
            case CRUISE->{rotateLoad(s,j,eva,Phase.UNSTOW,0);note(level,s,j,"已抵达接应区，吊架正在调整机体姿态。");}
            case DESCEND->{eva.endNervCarrierMotion();eva.setDeltaMovement(Vec3.ZERO);j.phase=Phase.HANDOFF;s.setDirty();}
            case RETREAT->path(s,j,plane,Phase.RETURN,site.path(site.receivers.get(j.variant).node(),site.airportNode),EMPTY_CRUISE_SPEED);
            case RETURN->begin(s,j,plane,Phase.LAND,site.stand,site.standYaw,.25);
            case LAND->{plane.cargo(-1,false,0);s.last="地下运输机已返场，机体由接应平台送回机库。";s.job=null;s.setDirty();}
            default->{}
        }
    }
    private NervUndergroundAirLiftR50(){}
}
