package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.NervAirTransportStateR52.*;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;
import java.nio.file.*;
import java.util.*;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.nbt.*;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** One real task per Root aircraft, sharing the mechanical runtime's sole
 * actor/SPACE broker. No spawn, backup restoration, heightmap or teleport. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class NervAirTransportRuntimeR52
{
    private static final Map<ServerLevel,Controller> LIVE=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("nerv_air_transport_r52",Comparator.comparingLong(ChunkPos::toLong),100);
    public static NervAirTransportStateR52 state(ServerLevel l){return l.getDataStorage().computeIfAbsent(NervAirTransportStateR52::load,NervAirTransportStateR52::new,NervAirTransportStateR52.NAME);}
    public static boolean compatibleGroundInstall(ServerLevel level,NervRouteDirectoryR52 directory)
    {
        var saved=level.getDataStorage().get(NervAirTransportStateR52::load,NervAirTransportStateR52.NAME);if(saved==null)return true;if(!saved.fault().isEmpty())return false;
        boolean active=saved.jobs().stream().anyMatch(Job::active);return !active||!LIVE.containsKey(level)&&saved.epoch()==directory.epoch()&&saved.directoryFingerprint().equals(directory.fingerprint());
    }
    public static boolean quarantineSavedLeases(ServerLevel level,NervRouteDirectoryR52 directory,NervRouteReservationsR52 pool)
    {
        if(!compatibleGroundInstall(level,directory))return false;var saved=level.getDataStorage().get(NervAirTransportStateR52::load,NervAirTransportStateR52.NAME);if(saved==null)return true;
        for(var j:saved.jobs())if(j.active()&&!pool.quarantineFlight(new FlightLease(j.task(),j.original(),directory.fingerprint(),j.spaces(),j.aircraft(),j.kind(),j.payloadTransferred(),j.mechanisms())))return false;return true;
    }
    public static boolean loadAndInstall(ServerLevel l,Path explicitRootFile)throws java.io.IOException{return install(l,JsonParser.parseString(Files.readString(explicitRootFile)).getAsJsonObject());}
    public static boolean install(ServerLevel l,JsonObject root)throws java.io.IOException
    {
        if(LIVE.containsKey(l)&&state(l).jobs().stream().anyMatch(Job::active))return false;
        var ground=NervRouteRuntimeR52.flightContext(l);if(ground==null)return false;var manifest=NervAirTransportManifestR52.parse(root,ground.directory());if(!manifest.installed()||!l.dimension().location().toString().equals(manifest.dimension()))return false;
        var geometry=NervAirframeGeometryR52.loadClasspath(manifest.meshSources());NervFlightProofR52.installCapsules();var saved=state(l);saved.bind(manifest.directory().epoch(),manifest.directory().fingerprint(),manifest.fingerprint());
        LIVE.put(l,new Controller(l,manifest,geometry,saved));return true;
    }
    public static boolean ready(ServerLevel l){return LIVE.containsKey(l)&&NervRouteRuntimeR52.flightContext(l)!=null;}
    public static boolean pending(ServerLevel l,EvaUnit01Entity eva){return eva!=null&&state(l).payload(eva.getUUID())!=null;}
    public static boolean ownsMotion(EvaUnit01Entity e){if(!(e.level() instanceof ServerLevel l))return false;var job=state(l).payload(e.getUUID());return job!=null&&job.carrying();}
    public static boolean busy(ServerLevel l){var c=LIVE.get(l);return c==null||c.manifest.aircraft().values().stream().allMatch(a->state(l).aircraft(a.entity())!=null);}
    public static boolean registeredPickup(ServerLevel l,EvaUnit01Entity e){var c=LIVE.get(l);if(c==null||e==null)return false;var o=c.original(e.getUnitVariant(),e.getPersistentData().hasUUID("R49RecoveryOwner")?e.getPersistentData().getUUID("R49RecoveryOwner"):e.getPersistentData().hasUUID("R32SortieCommander")?e.getPersistentData().getUUID("R32SortieCommander"):e.getPilotEntity()==null?new UUID(0,0):e.getPilotEntity().getUUID());if(o==null)return false;var p=c.ground().owner().previewFlight(l,o,EntryPlugEjectionR48.originalFieldEjection(l,o.variant(),e,o.pilot())?Kind.HULL_ONLY_RECOVERY:Kind.OCCUPIED,new CompoundTag());return p!=null&&c.manifest.missions().values().stream().anyMatch(m->m.variants().contains(o.variant())&&m.pickupDomain().contains(p.root().transformPoint(p.binding().contactCentre())));}
    public static int ownedCancelVariant(ServerPlayer p){var jobs=state(p.serverLevel()).jobs().stream().filter(j->j.active()&&j.original().owner().equals(p.getUUID())).toList();return jobs.size()==1?jobs.get(0).original().variant():-1;}
    public static boolean deliveryPending(ServerLevel l,EvaUnit01Entity e,UUID owner){var j=e==null?null:state(l).payload(e.getUUID());return j!=null&&j.original().owner().equals(owner)&&!j.ownerData().getString("Intent").equals(Intent.RECOVER.name());}
    public static boolean atReceiver(ServerLevel l,EvaUnit01Entity e){return e!=null&&e.getPersistentData().getBoolean("R52AirGroundHandoff")&&NervRouteRuntimeR52.pending(l,e.getUnitVariant());}
    public static String status(ServerLevel l)
    {
        if(!ready(l))return "运输机尚未完成航路准备，请稍后再试。";
        var controller=LIVE.get(l);var jobs=state(l).jobs().stream().filter(Job::active).toList();return jobs.isEmpty()?"运输机在各泊位待命。":String.join(" ｜ ",jobs.stream().map(j->{var aircraft=controller.manifest.aircraft().values().stream().filter(a->a.entity().equals(j.aircraft())).findFirst().orElse(null);return "运输机"+(aircraft==null?"":aircraft.serial())+"："+NervStaffDialogue.unitName(j.original().variant())+" "+phaseLabelR52(j.phase())+" "+humanWaitingR52(j.waiting());}).toList());
    }
    private static String phaseLabelR52(Phase phase){return switch(phase){case PREPARE->"准备中";case TAKEOFF,FERRY->"前往接载点";case APPROACH,CLAMP->"接载中";case ASCEND,STOW,CRUISE->"运输中";case UNSTOW,DESCEND,HANDOFF,RELEASE->"交接中";case RETREAT->"退出接应点";case RETURN,LAND->"返场中";case HOLD->"等待";case COMPLETE->"已完成";case CANCELLED->"已取消";};}
    private static String humanWaitingR52(String reason){
        if(reason==null||reason.isBlank())return "";
        if(reason.contains("sweep"))return reason.contains("夹具")?"夹具附近受阻，等待净空。":"航路受阻，等待净空。";
        if(reason.contains("fraction"))return "正在确认运输机位置，原位等待。";
        if(reason.contains("UUID"))return "等待原运输机就绪。";
        if(reason.contains("Root"))return "返场航路尚未准备完成，原位等待。";
        if(reason.contains("旋翼实际停止样本验证失败"))return "正在确认旋翼安全间隔，原位等待。";
        if(reason.contains("来源")||reason.contains("几何"))return "正在确认机体姿势与承托，原位等待。";
        return reason;
    }
    public static String request(ServerPlayer caller,int variant,boolean returning,int x,int z)
    {
        if(variant<0||variant>2||!NervStaffDialogue.authorized(caller)||!StaffConversationR24.radioAllowed(caller))return "需要 NERV 指挥通信权限。";
        return request(caller.serverLevel(),variant,caller.getUUID(),returning?Intent.RECOVER:Intent.DELIVER,x,z);
    }
    public static boolean requestPilotReturn(ServerLevel l,EvaUnit01Entity e,UUID commander){if(e==null)return false;request(l,e.getUnitVariant(),commander,Intent.RECOVER,0,0);var c=LIVE.get(l);var job=state(l).payload(e.getUUID());return c!=null&&state(l).fault().isEmpty()&&job!=null&&job.active()&&job.manifestFingerprint().equals(c.manifest.fingerprint())&&job.original().owner().equals(commander)&&job.ownerData().getBoolean("Returning");}
    public static String request(ServerLevel l,int variant,UUID commander,Intent intent,int x,int z)
    {var c=LIVE.get(l);if(c==null)return status(l);try{return c.request(variant,commander,intent,x,z);}catch(IllegalArgumentException|IllegalStateException denied){com.projectseele.ProjectSeele.LOGGER.debug("R52 flight request rejected variant={} intent={}: {}",variant,intent,denied.toString());return "当前位置或接载路径尚未满足运输条件，机体保持原位。";}}
    /** Named actual far receiver; no shoe/body-root conversion or integer coordinate guess. */
    public static String requestReceiver(ServerLevel l,int variant,UUID commander,String receiverId)
    {var c=LIVE.get(l);if(c==null)return status(l);try{return c.request(variant,commander,Intent.FAR_MOUNTAIN,0,0,receiverId);}catch(IllegalArgumentException|IllegalStateException denied){com.projectseele.ProjectSeele.LOGGER.debug("R52 flight receiver request rejected variant={} receiver={}: {}",variant,receiverId,denied.toString());return "当前位置或接载路径尚未满足运输条件，机体保持原位。";}}
    public static String cancel(ServerPlayer p,int variant)
    {
        var s=state(p.serverLevel());var j=s.jobs().stream().filter(x->x.active()&&(variant<0||x.original().variant()==variant)&&x.original().owner().equals(p.getUUID())).findFirst().orElse(null);
        if(j==null)return "没有属于当前指挥者的原运输任务。";s.put(j.requestCancel());return j.carrying()?"原载荷和占域已保持；取消等待已验证接应链交付后返场。":"原飞机将沿已走过的实际航段逆向返场。";
    }
    public static boolean abortForMaintenance(ServerLevel l,int variant,UUID eva)
    {var j=eva==null?null:state(l).payload(eva);return j==null;}
    public static String forceRecover(ServerLevel l){return "R52 禁止传送或重建原飞机；"+status(l);}
    public static String phaseName(ServerLevel l){var jobs=state(l).jobs().stream().filter(Job::active).toList();return jobs.isEmpty()?"IDLE":String.join(",",jobs.stream().map(j->j.aircraft()+"/"+j.phase()).toList());}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {if(event.phase!=TickEvent.Phase.END)return;for(var level:event.getServer().getAllLevels()){var c=LIVE.get(level);if(c!=null)c.tick();}}
    private static final class Controller
    {
        final ServerLevel level;final NervAirTransportManifestR52 manifest;final NervAirframeGeometryR52 geometry;final NervAirTransportStateR52 saved;
        final Map<UUID,NervFlightProofR52.FlightPickupPreview> previews=new HashMap<>();
        final Map<UUID,NervHullGroundRecoveryR52.Plan> hullPlans=new HashMap<>();
        Controller(ServerLevel l,NervAirTransportManifestR52 m,NervAirframeGeometryR52 g,NervAirTransportStateR52 s){level=l;manifest=m;geometry=g;saved=s;}
        NervRouteRuntimeR52.FlightContext ground(){return NervRouteRuntimeR52.flightContext(level);}
        Original original(int variant,UUID commander)
        {
            var unit=manifest.directory().unit(variant);if(unit==null||!(level.getEntity(unit.eva()) instanceof EvaUnit01Entity eva))return null;UUID pilot=null;
            if(level.getEntity(unit.plug()) instanceof EntryPlugCarrierEntity plug&&plug.getFirstPassenger()!=null)pilot=plug.getFirstPassenger().getUUID();
            else if(eva.getPersistentData().hasUUID("R49EjectedPilot"))pilot=eva.getPersistentData().getUUID("R49EjectedPilot");if(pilot==null)return null;
            var deployed=NervRouteRuntimeR52.originalForFlight(level,variant,commander);if(deployed!=null&&!deployed.pilot().equals(pilot))return null;var o=deployed!=null?deployed:new Original(manifest.directory().epoch(),variant,unit.eva(),unit.plug(),pilot,commander,AutoSortieR32.missionToken(level),manifest.dimension());var tag=eva.getPersistentData();var assignment=TvCampaignSavedData.get(level).sorties.get(variant);
            boolean owns=pilot.equals(commander)&&level.getEntity(pilot) instanceof ServerPlayer player&&!player.isSpectator()&&NervStaffDialogue.authorized(player)||tag.hasUUID("R32SortieCommander")&&tag.getUUID("R32SortieCommander").equals(commander)||assignment!=null&&commander.equals(assignment.commander)||tag.hasUUID("R49RecoveryOwner")&&tag.getUUID("R49RecoveryOwner").equals(commander);return owns?o:null;
        }
        String request(int variant,UUID commander,Intent intent,int x,int z)
        {return request(variant,commander,intent,x,z,null);}
        String request(int variant,UUID commander,Intent intent,int x,int z,String receiverId)
        {
            if(receiverId!=null&&(manifest.receiver(receiverId)==null||!manifest.receiver(receiverId).delivery()))return "远山原运输接应口身份尚未登记。";
            var ground=ground();if(ground==null||!saved.fault().isEmpty())return status(level);var original=original(variant,commander);if(original==null)return "原 EVA、原插入栓、实际驾驶员或任务归属尚未就绪。";
            if(intent==Intent.RECOVER&&NervRouteRuntimeR52.originalForFlight(level,variant,commander)==null)return "原 EVA 的出击记录与回库承接尚未接通，原机体保持原位。";
            if(saved.payload(original.eva())!=null)return "同一原 EVA 已有运输任务。";var eva=(EvaUnit01Entity)level.getEntity(original.eva());Kind kind=EntryPlugEjectionR48.originalFieldEjection(level,variant,eva,original.pilot())?Kind.HULL_ONLY_RECOVERY:Kind.OCCUPIED;
            var data=new CompoundTag();data.putString("AssemblyKindR52",kind.name());data.putBoolean("Returning",intent==Intent.RECOVER);data.putString("Intent",intent.name());var preview=ground.owner().previewFlight(level,original,kind,data);if(preview==null)return "原机体须在真实支撑上停稳；空运不能替换原姿势、乘员或夹具。";
            Vec3 actualFoot=preview.root().transformPoint(preview.binding().contactCentre());var region=manifest.region(actualFoot);if(region==null)return "当前位置尚未开放空运接载。";
            var candidates=manifest.missions().values().stream().filter(m->(m.intent()==intent||intent==Intent.DELIVER&&m.intent()==Intent.FAR_MOUNTAIN)&&m.variants().contains(variant)&&m.region()==region&&m.pickupDomain().contains(actualFoot))
                    .filter(m->receiverId!=null?m.receiver().equals(receiverId):intent==Intent.RECOVER||nearDestination(m,x,z)).sorted(Comparator.comparingDouble(m->receiverDistance(m,preview,data,actualFoot))).toList();
            for(var m:candidates)
            {
                if(manifest.receiver(m.receiver()).delivery()&&kind!=Kind.OCCUPIED)continue;data.putString("Intent",m.intent().name());var aircraft=manifest.aircraft().get(m.aircraft());if(saved.aircraft(aircraft.entity())!=null||!(level.getEntity(aircraft.entity()) instanceof UNTransportEntity plane)||!aircraftSupported(aircraft)||plane.carrying()||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(plane),manifest.node(aircraft.stand()).frame().plane()))continue;
                // Read and prove actual full graph reachability before nearest
                // port selection; unknown chunks are not called traversable.
                data.put("PickupRoot",NervAircraftFrameR52.encodeRigid(preview.root()));for(var chain:List.of(m.outbound(),m.loaded(),m.retreat()))for(String id:chain)tickets(manifest.corridor(id));
                var pickupCells=pickupSpaces(m,preview);data.put("PickupHeldSpaces",writeList(pickupCells));var standFrame=frameAt(m,aircraft.stand(),preview,data,false);var initialClock=NervAircraftFrameR52.rotorClock(plane);var required=new HashSet<>(sourceSpaces(preview,standFrame,standFrame,false,initialClock,initialClock+1,manifest.node(aircraft.stand()).spaces()));required.addAll(pickupCells);if(!ground.pool().resourcesAvailable(null,required))continue;var doors=allDoors(m);var plan=ground.owner().previewFlightGates(level,original,kind,doors);if(plan==null||!pathPlanned(m,preview,data,plan)||!NervAircraftFrameR52.bind(plane,manifest,aircraft))continue;
                var stand=manifest.node(aircraft.stand());var heldSpaces=new HashSet<>(stand.spaces());heldSpaces.addAll(pickupCells);var frame=frameAt(m,aircraft.stand(),preview,data,false);var stationary=proof(aircraft.entity(),preview,frame,frame,heldSpaces,false);if(stationary==null)continue;
                UUID task=UUID.randomUUID();var access=access(original,kind,aircraft.entity(),stationary,false);
                if(!ground.pool().reserveFlight(task,original,aircraft.entity(),kind,heldSpaces,Set.of(),access))continue;
                data.putString("FlightStage","PREFLIGHT");NervAircraftFrameR52.putFrame(data,"Frame",frame);data.putInt("PassedOutbound",0);var j=new Job(task,aircraft.entity(),original,kind,manifest.fingerprint(),m.id(),m.receiver(),0,0,Phase.PREPARE,Phase.PREPARE,false,false,false,heldSpaces,Set.of(),data,"");save(j);previews.put(task,preview);return "已安排运输机，正在准备接载。";
            }
            return "暂时无法接载，等待运输机和航路可用。";
        }
        double receiverDistance(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,Vec3 foot){var r=resolvedReceiver(m,p,data);return r==null?Double.POSITIVE_INFINITY:r.stopped().transformPoint(p.binding().contactCentre()).distanceToSqr(foot);}
        boolean nearDestination(Mission m,int x,int z){var p=manifest.receiver(m.receiver()).stopped().translation();return Math.abs(p.x-x)<=.5&&Math.abs(p.z-z)<=.5;}
        boolean cells(List<Cell> cells){for(var c:cells)if(!level.hasChunkAt(c.position())||!BlockStateParser.serialize(level.getBlockState(c.position())).equals(c.state()))return false;return true;}
        boolean aircraftSupported(Aircraft aircraft)
        {
            if(!cells(aircraft.support()))return false;var plane=manifest.node(aircraft.stand()).frame().plane();for(var local:geometry.bearingPatches()){var patch=NervRigidMeshSweepR52.transformed(local,plane);var surface=new net.minecraft.world.phys.AABB(patch.minX,patch.minY-.001,patch.minZ,patch.maxX,patch.minY,patch.maxZ);var supports=new ArrayList<net.minecraft.world.phys.AABB>();for(var cell:aircraft.support())for(var shape:level.getBlockState(cell.position()).getCollisionShape(level,cell.position()).toAabbs()){var actual=shape.move(cell.position());if(Math.abs(actual.maxY-patch.minY)<=.002)supports.add(new net.minecraft.world.phys.AABB(actual.minX,patch.minY-.001,actual.minZ,actual.maxX,patch.minY,actual.maxZ));}if(!NervAirspaceCoverageR52.covered(surface,supports))return false;}return true;
        }
        boolean gates(Corridor c){for(String id:c.gates())if(!ground().nativeAccess().resourceReady(id,true))return false;return cells(manifest.node(c.to()).cells());}
        Set<String> allDoors(Mission m){var doors=new HashSet<String>();for(var chain:List.of(m.outbound(),m.loaded(),m.retreat()))for(String id:chain)doors.addAll(manifest.corridor(id).gates());var receiver=manifest.receiver(m.receiver());doors.addAll(receiver.gates());if(!receiver.delivery())doors.addAll(ground().owner().flightReceiverGates(level,receiver.port()));return Set.copyOf(doors);}
        Set<String> receiverDoors(Mission m){var receiver=manifest.receiver(m.receiver());var doors=new HashSet<>(receiver.gates());if(!receiver.delivery())doors.addAll(ground().owner().flightReceiverGates(level,receiver.port()));return Set.copyOf(doors);}
        private record GatePreparation(Job job,boolean ready){}
        GatePreparation prepareDoors(Job j,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data,Set<String> needed)
        {
            if(!j.mechanisms().containsAll(needed))
            {
                var union=new HashSet<>(j.mechanisms());union.addAll(needed);var stationary=proof(j.aircraft(),p,current,current,j.spaces(),j.carrying()||!j.payloadTransferred()&&(data.getBoolean("FlightWaitingR52")||data.getString("FlightStage").equals("TRANSFER")));
                if(stationary==null||!ground().pool().retargetFlightSpaces(j.task(),j.spaces(),union,access(j.original(),j.kind(),j.aircraft(),stationary,j.payloadTransferred()))){hold(j,"等待舱门可用");return new GatePreparation(j,false);}
                j=j.update(j.leg(),j.age(),j.phase(),j.carrying(),j.payloadTransferred(),j.spaces(),union,data,"");save(j);
            }
            boolean ready=ground().owner().prepareFlightGates(level,j.original(),j.kind(),needed,data)&&needed.stream().allMatch(id->ground().nativeAccess().resourceReady(id,true));
            if(!ready){save(j.update(j.leg(),j.age(),Phase.HOLD,j.carrying(),j.payloadTransferred(),j.spaces(),j.mechanisms(),data,"舱门正在开启"));}
            return new GatePreparation(j,ready);
        }
        Set<String> initialResources(Mission m,int variant)
        {var ids=new HashSet<String>();ids.addAll(manifest.node(m.pickupNode()).spaces());ids.addAll(manifest.node(manifest.aircraft().get(m.aircraft()).stand()).spaces());var receiver=manifest.receiver(m.receiver());if(!receiver.delivery()){var route=manifest.directory().route(receiver.reverseRoutes().get(variant));if(route!=null)for(String id:manifest.directory().resources(route))if(manifest.directory().resource(id).kind()==NervRouteDirectoryR52.ResourceKind.SPACE)ids.add(id);}return Set.copyOf(ids);}
        Set<String> pickupSpaces(Mission m,NervFlightProofR52.FlightPickupPreview p){return manifest.directory().dynamicSpacesR52().domains().isEmpty()?manifest.node(m.pickupNode()).spaces():manifest.directory().dynamicSpacesR52().required(manifest.dimension(),p.cargoEnvelopes(p.root(),p.root()),ground().bindings());}
        boolean pathPlanned(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,NervFlightGatePlanR52 plan){return checkPath(m,p,data,plan);}
        boolean pathReady(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data){return checkPath(m,p,data,null);}
        boolean checkPath(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,NervFlightGatePlanR52 plan){
            try{for(var chain:List.of(m.outbound(),m.loaded(),m.retreat()))for(String id:chain){var c=manifest.corridor(id);if(!cells(manifest.node(c.to()).cells())||plan==null&&!gates(c))return false;boolean loaded=chain==m.loaded();var from=startFrame(m,c,p,data,loaded);var to=endFrame(m,c,p,data,loaded);int count=Math.max(1,(int)Math.ceil(from.plane().translation().distanceTo(to.plane().translation())/16));boolean clear=true;for(int i=0;i<count;i++){var a=from.interpolate(to,i/(double)count);var b=from.interpolate(to,(i+1D)/count);int ticks=Math.max(1,(int)Math.ceil(c.ticks()/(double)count));var prepared=NervFlightProofR52.prepareSourceSweepR52(level,geometry,p,a,b,0,ticks,loaded);var spaces=sourceSpaces(prepared,c.spaces());tickets(spaces);if(!NervFlightProofR52.pathClear(level,manifest,geometry,manifest.aircraft().get(m.aircraft()).entity(),p,a,b,spaces,ground().bindings(),loaded,ticks,plan,prepared))clear=false;}if(!clear)return false;}return true;}catch(IllegalArgumentException|IllegalStateException invalid){com.projectseele.ProjectSeele.LOGGER.debug("R52 actual pickup path rejected mission={}: {}",m.id(),invalid.toString());return false;}}
        Frame startFrame(Mission m,Corridor c,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,boolean loaded)
        {return frameAt(m,c.from(),p,data,loaded);}
        Frame endFrame(Mission m,Corridor c,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,boolean loaded)
        {return frameAt(m,c.to(),p,data,loaded);}
        Frame frameAt(Mission m,String node,NervFlightProofR52.FlightPickupPreview p,CompoundTag data,boolean loaded)
        {
            var declared=manifest.node(node).frame();var pickup=NervAircraftFrameR52.decodeRigid(data.getCompound("PickupRoot"));var actual=NervActualPickupFramesR52.at(manifest,m,node,pickup,loaded);var cargo=actual.cargo();var plane=actual.plane();
            var receiver=manifest.receiver(m.receiver());if(loaded&&node.equals(receiver.node())&&!receiver.delivery()){if(p!=null&&p.kind()==Kind.HULL_ONLY_RECOVERY){var plan=recoveryPlan(m,p,data);if(plan==null)throw new IllegalStateException("Actual original hull source cannot plan this declared receiver");cargo=plan.waitingRoot();}else{var resolved=resolvedReceiver(m,p,data);if(resolved==null)throw new IllegalStateException("Actual original binding cannot resolve this typed receiver");cargo=resolved.stopped();}plane=RigidTransform.of(plane.translation().add(cargo.translation().subtract(receiver.stopped().translation())),plane.rotation());}
            return new Frame(plane,cargo,new Rig(declared.rig().hoist(),loaded?1:0,loaded?0:1));
        }
        Receiver resolvedReceiver(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data)
        {var r=manifest.receiver(m.receiver());if(r.delivery())return r;if(p==null)return null;RigidTransform root;if(p.kind()==Kind.HULL_ONLY_RECOVERY){var plan=recoveryPlan(m,p,data);root=plan==null?null:plan.stoppedRoot();}else root=ground().owner().resolveFlightReceiverCargoRootR52(level,p.original(),p.kind(),r.port(),data);return root==null?null:new Receiver(r.port(),r.region(),r.node(),root,r.reverseRoutes(),false,r.supports(),r.gates());}
        NervHullGroundRecoveryR52.Plan recoveryPlan(Mission m,NervFlightProofR52.FlightPickupPreview p,CompoundTag data)
        {
            if(p==null||p.kind()!=Kind.HULL_ONLY_RECOVERY)return null;var prior=hullPlans.get(p.original().eva());if(prior!=null&&prior.port().equals(m.receiver())&&!data.getCompound("HullGroundRecoveryR52").isEmpty())return prior;
            if(!data.getCompound("HullGroundRecoveryR52").isEmpty()&&!data.getCompound("HullGroundRecoveryR52").getString("Port").equals(m.receiver())){data.remove("HullGroundRecoveryR52");data.remove("HullRecoveryAgeR52");}
            try{var next=NervHullGroundRecoveryR52.plan(level,p,manifest.receiver(m.receiver()),data);if(next!=null)hullPlans.put(p.original().eva(),next);return next;}catch(java.io.IOException|IllegalArgumentException|IllegalStateException missing){return null;}
        }
        Set<String> sourceSpaces(NervFlightProofR52.FlightPickupPreview p,Frame from,Frame to,boolean movingCargo,double rotorFrom,double rotorTo,Set<String> fallback){if(manifest.directory().dynamicSpacesR52().domains().isEmpty())return fallback;return sourceSpaces(NervFlightProofR52.prepareSourceSweepR52(level,geometry,p,from,to,rotorFrom,rotorTo,movingCargo),fallback);}
        Set<String> sourceSpaces(NervFlightProofR52.PreparedSourceSweepR52 prepared,Set<String> fallback){if(manifest.directory().dynamicSpacesR52().domains().isEmpty())return fallback;return manifest.directory().dynamicSpacesR52().required(manifest.dimension(),prepared.envelopes(),ground().bindings());}
        NervFlightProofR52.CheckedFlightStep proof(UUID plane,NervFlightProofR52.FlightPickupPreview p,Frame from,Frame to,Set<String> spaces,boolean movingCargo)
        {
            double clock=level.getEntity(plane) instanceof UNTransportEntity entity?NervAircraftFrameR52.rotorClock(entity):0;
            try{var job=saved.aircraft(plane);var prepared=NervFlightProofR52.prepareSourceSweepR52(level,geometry,p,from,to,clock,clock+1,movingCargo);var actual=sourceSpaces(prepared,spaces);if(!manifest.directory().dynamicSpacesR52().domains().isEmpty()&&!movingCargo&&p!=null&&(job==null||!job.payloadTransferred()&&job.ownerData().getBoolean("FlightWaitingR52"))){var union=new HashSet<>(actual);union.addAll(manifest.directory().dynamicSpacesR52().required(manifest.dimension(),p.cargoEnvelopes(p.root(),p.root()),ground().bindings()));actual=Set.copyOf(union);}
                if(p==null&&job!=null&&job.payloadTransferred())return NervFlightProofR52.checkAircraftStep(level,manifest,geometry,plane,job.original(),job.kind(),from,to,actual,ground().bindings(),clock,clock+1,prepared);
                return NervFlightProofR52.checkStep(level,manifest,geometry,plane,p,from,to,actual,ground().bindings(),clock,clock+1,movingCargo,prepared);
            }catch(IllegalArgumentException|IllegalStateException invalid){com.projectseele.ProjectSeele.LOGGER.debug("R52 actual flight SPACE rejected plane={} from={} to={}: {}",plane,from,to,invalid.toString());return null;}
        }
        FlightAccess access(Original o,Kind kind,UUID plane,NervFlightProofR52.CheckedFlightStep proof,boolean transferred)
        {return access(o,kind,plane,proof,transferred,null,null);}
        FlightAccess access(Original o,Kind kind,UUID plane,NervFlightProofR52.CheckedFlightStep proof,boolean transferred,NervFlightProofR52.CheckedAirDelivery delivery,CompoundTag data)
        {
            return new FlightAccess()
            {
                public Set<String> checkedSourceSpacesR52(){return manifest.directory().dynamicSpacesR52().domains().isEmpty()?null:proof!=null&&proof.current(level)?proof.spaces():Set.of();}
                private boolean resourceProof(Set<NervRouteDirectoryR52.Resource> declared){var spaces=new HashSet<String>();for(var r:declared){if(r.kind()==NervRouteDirectoryR52.ResourceKind.SPACE)spaces.add(r.id());else if(r.kind()!=NervRouteDirectoryR52.ResourceKind.DOOR||!(ground().nativeAccess().resourceReady(r.id(),true)||canPrepareClosed(proof)&&(ground().nativeAccess().resourceReady(r.id(),false)||alreadyOwnsActualGate(r.id()))))return false;}return proof.spaces().equals(spaces);}
                private boolean alreadyOwnsActualGate(String id){var job=saved.aircraft(plane);var lease=job==null?null:ground().pool().queryFlight(job.task());return lease!=null&&lease.aircraft().equals(plane)&&lease.original().equals(o)&&lease.mechanisms().contains(id)&&ground().owner().flightGateSampleCurrent(level,id);}
                private boolean canPrepareClosed(NervFlightProofR52.CheckedFlightStep checked){return checked.from().rig().equals(checked.to().rig())&&NervAirTransportManifestR52.same(checked.from().plane(),checked.to().plane())&&(checked.from().cargo()==null?checked.to().cargo()==null:NervAirTransportManifestR52.same(checked.from().cargo(),checked.to().cargo()));}
                public boolean sameOriginalAssembly(Original x){return sameMovingAssembly(x,Kind.OCCUPIED);}
                public boolean sameMovingAssembly(Original x,Kind k){ground().nativeAccess().ownerData(new CompoundTag());return x.equals(o)&&k==kind&&ground().nativeAccess().sameAssembly(x,k);}
                public boolean checkedSupportedDelivery(Original x,Kind k){return delivery!=null&&delivery.current(level)&&x.equals(o)&&k==kind&&ground().owner().acceptAirDelivery(level,delivery,data);}
                public boolean originalAircraft(UUID id){return id.equals(plane)&&level.getEntity(id) instanceof UNTransportEntity p&&p.isNerv()&&!p.groundCart()&&manifest.aircraft().values().stream().anyMatch(a->a.entity().equals(id)&&a.serial()==p.serial());}
                public boolean checkedFlightGeometry(Original x,Set<NervRouteDirectoryR52.Resource> spaces,boolean restoring){return proof!=null&&proof.current(level)&&x.equals(o)&&!transferred&&resourceProof(spaces);}
                public boolean checkedAircraftOnlyGeometry(UUID id,Set<NervRouteDirectoryR52.Resource> spaces,boolean restoring){return proof!=null&&proof.current(level)&&id.equals(plane)&&resourceProof(spaces);}
            };
        }
        void save(Job j){var lease=ground()==null?null:ground().pool().queryFlight(j.task());if(lease!=null)j=j.update(j.leg(),j.age(),j.phase(),j.carrying(),j.payloadTransferred(),lease.spaces(),lease.mechanisms(),j.ownerData(),j.waiting());saved.put(j);}
        void hold(Job j,String reason){com.projectseele.ProjectSeele.LOGGER.debug("R52 flight hold task={} reason={}",j.task(),reason);save(j.hold(reason));}
        void tick()
        {
            if(ground()==null||!saved.fault().isEmpty())return;for(var j:saved.jobs())if(j.active())
            {try{tick(j);}catch(IllegalArgumentException|IllegalStateException invalid){com.projectseele.ProjectSeele.LOGGER.warn("R52 air job {} rejected",j.task(),invalid);hold(j,"当前状态正在核对，机体保持原位");}}
            for(var aircraft:manifest.aircraft().values())try{pulseStoppedRotors(aircraft);}catch(IllegalArgumentException|IllegalStateException invalid){var j=saved.aircraft(aircraft.entity());if(j!=null)hold(j,"原旋翼实际停止样本验证失败："+invalid.getMessage());}
        }
        /** Waiting or returned aircraft keep their real independently saved
         * rotor clock. A stop must not silently freeze the renderer forever. */
        void pulseStoppedRotors(Aircraft aircraft)
        {
            if(!(level.getEntity(aircraft.entity()) instanceof UNTransportEntity plane)||!NervAircraftFrameR52.contextMatches(plane,manifest)||NervAircraftFrameR52.sampledAt(plane)==level.getGameTime())return;
            var current=NervAircraftFrameR52.frame(plane,1);var j=saved.aircraft(aircraft.entity());NervFlightProofR52.CheckedFlightStep checked;
            if(j==null){var stand=manifest.node(aircraft.stand());if(plane.carrying()||current.cargo()!=null||current.rig().deployment()!=0||!aircraftSupported(aircraft)||!NervAirTransportManifestR52.same(current.plane(),stand.frame().plane()))return;double clock=NervAircraftFrameR52.rotorClock(plane);checked=NervFlightProofR52.checkAircraftStep(level,manifest,geometry,aircraft.entity(),null,Kind.OCCUPIED,current,current,stand.spaces(),ground().bindings(),clock,clock+1);}
            else{if(ground().pool().queryFlight(j.task())==null||ground().pool().flightQuarantined(j.task()))return;var data=j.ownerData();var preview=j.payloadTransferred()?null:ground().owner().previewFlight(level,j.original(),j.kind(),data);if(!j.payloadTransferred()&&preview==null)return;checked=proof(j.aircraft(),preview,current,current,j.spaces(),j.carrying()||!j.payloadTransferred()&&(data.getBoolean("FlightWaitingR52")||data.getString("FlightStage").equals("TRANSFER")));}
            if(checked!=null&&(j==null||ground().pool().retargetFlightSpaces(j.task(),j.spaces(),j.mechanisms(),access(j.original(),j.kind(),j.aircraft(),checked,j.payloadTransferred()))))NervAircraftFrameR52.apply(plane,checked);
        }
        void tick(Job job)
        {
            var m=manifest.missions().get(job.itinerary());if(m==null||!job.manifestFingerprint().equals(manifest.fingerprint())){hold(job,"保存目录/任务版本已改变");return;}
            var hint=job.ownerData();var savedFrame=NervAircraftFrameR52.decode(hint.getCompound("Frame"));ticketAt(savedFrame.plane().translation());if(savedFrame.cargo()!=null)ticketAt(savedFrame.cargo().translation());if(hint.contains("PickupRoot"))ticketAt(NervAircraftFrameR52.decodeRigid(hint.getCompound("PickupRoot")).translation());
            if(!(level.getEntity(job.aircraft()) instanceof UNTransportEntity plane)||!NervAircraftFrameR52.active(plane)){hold(job,"等待同 UUID 原飞机加载；不重造、不复制备份");return;}
            var data=job.ownerData();var p=previews.get(job.task());if(p==null&&!job.payloadTransferred()){p=ground().owner().previewFlight(level,job.original(),job.kind(),data);if(p==null){hold(job,"重载等待原载荷实际姿势/乘员图恢复");return;}previews.put(job.task(),p);}
            if(!job.payloadTransferred()&&Set.of("UNCLAMP","TRANSFER").contains(data.getString("FlightStage"))){var actual=ground().owner().previewFlight(level,job.original(),job.kind(),data);if(actual!=null){p=actual;previews.put(job.task(),p);}}
            var current=NervAircraftFrameR52.decode(data.getCompound("Frame"));if(!NervAirTransportManifestR52.same(current.plane(),NervAircraftFrameR52.actual(plane))||!current.rig().equals(NervAircraftFrameR52.frame(plane,1).rig())){hold(job,"原飞机保存 fraction 与实际同步帧不同");return;}
            var stationary=proof(job.aircraft(),p,current,current,job.spaces(),job.carrying()||!job.payloadTransferred()&&(data.getString("FlightStage").equals("TRANSFER")||data.getBoolean("FlightWaitingR52")));if(stationary==null){hold(job,"当前原机体、旋翼或夹具空间受阻/未加载");return;}
            // Preserve uncertain saved claims until the same original actor
            // and current complete source have passed. Then claim exactly
            // this stopped step; previous corridor cells are not carried on.
            if(ground().pool().queryFlight(job.task())==null&&!ground().pool().quarantineFlight(new FlightLease(job.task(),job.original(),manifest.directory().fingerprint(),job.spaces(),job.aircraft(),job.kind(),job.payloadTransferred(),job.mechanisms()))){hold(job,"同机/同 EVA/同航路重载租约被占用");return;}
            if(!ground().pool().retargetFlightSpaces(job.task(),job.spaces(),job.mechanisms(),access(job.original(),job.kind(),job.aircraft(),stationary,job.payloadTransferred()))){hold(job,"保存占域等待同机/同原载荷实际完整帧验证");return;}
            String stage=data.getString("FlightStage");if(job.cancelRequested()&&!job.carrying()&&!job.payloadTransferred()&&stage.equals("OUTBOUND")){cancelUnladen(job,m,p,current,data);return;}
            if(stage.equals("PREFLIGHT")){preflight(job,m,p,current,data);return;}
            if(stage.equals("CLAMP")&&job.cancelRequested()&&!job.carrying()){data.putString("FlightStage","RETRACT_PICKUP");save(job.update(0,job.age(),Phase.RELEASE,false,false,job.spaces(),job.mechanisms(),data,"原夹具连续收回后沿实际航段返场"));return;}
            if(stage.equals("RETRACT_PICKUP")){retractPickup(job,m,p,current,data);return;}
            if(stage.equals("CLAMP")){clamp(job,m,p,current,data);return;}if(stage.equals("UNCLAMP")){unclamp(job,m,p,current,data);return;}
            if(stage.equals("TRANSFER")){transfer(job,m,p,current,data);return;}
            List<String> chain=stage.equals("OUTBOUND")?m.outbound():stage.equals("LOADED")?m.loaded():stage.equals("CANCEL")?readList(data,"CancelChain"):m.retreat();
            if(job.leg()>=chain.size()){hold(job,"真实航段索引损坏");return;}var c=manifest.corridor(chain.get(job.leg()));tickets(c);
            var doorPreparation=prepareDoors(job,p,current,data,c.gates());job=doorPreparation.job();if(!doorPreparation.ready())return;
            if(!gates(c)){hold(job,"等待真实原门/支撑/已声明航段加载");return;}
            boolean loaded=stage.equals("LOADED");var from=startFrame(m,c,p,data,loaded);var to=endFrame(m,c,p,data,loaded);
            if(stage.equals("RETREAT")||stage.equals("CANCEL")){from=new Frame(from.plane(),current.cargo(),new Rig(from.rig().hoist(),0,1));to=new Frame(to.plane(),current.cargo(),new Rig(to.rig().hoist(),0,1));}
            int age=job.age();if(age>c.ticks()||loaded!=job.carrying()||plane.carrying()!=job.carrying()){hold(job,"保存时钟/真实携载状态不一致，原位保持");return;}var expected=from.interpolate(to,ease((double)age/c.ticks()));if(!NervAirTransportManifestR52.same(expected.plane(),current.plane())||!expected.rig().equals(current.rig())||loaded&&!NervAirTransportManifestR52.same(expected.cargo(),current.cargo())){hold(job,"航段同 fraction 与原实体不符；不重定位");return;}
            var next=from.interpolate(to,ease((double)Math.min(c.ticks(),age+1)/c.ticks()));var occupied=new HashSet<>(c.spaces());if(!loaded&&data.getBoolean("FlightWaitingR52"))occupied.addAll(readList(data,"PickupHeldSpaces"));var checked=proof(job.aircraft(),p,current,next,occupied,loaded||data.getBoolean("FlightWaitingR52"));if(checked==null||!ground().pool().retargetFlightSpaces(job.task(),occupied,c.gates(),access(job.original(),job.kind(),job.aircraft(),checked,job.payloadTransferred()))){hold(job,"上方航路受阻，等待净空");return;}
            if(loaded&&!ground().owner().applyFlightStep(level,checked,data)){hold(job,"原整组运动 Owner 拒绝当前实际样本");return;}if(!NervAircraftFrameR52.apply(plane,checked)){hold(job,"原飞机真实样本提交失败");return;}
            NervAircraftFrameR52.putFrame(data,"Frame",next);plane.rebindCargo(loaded?level.getEntity(job.original().eva()).getId():-1);plane.cargo(loaded?level.getEntity(job.original().eva()).getId():-1,loaded,next.rig().deployment());
            if(age+1<c.ticks()){save(job.update(job.leg(),age+1,phase(stage),loaded,job.payloadTransferred(),occupied,c.gates(),data,""));return;}
            if(stage.equals("OUTBOUND"))data.putInt("PassedOutbound",job.leg()+1);
            if(job.leg()+1<chain.size()){save(job.update(job.leg()+1,0,phase(stage),loaded,job.payloadTransferred(),occupied,c.gates(),data,""));return;}
            if(stage.equals("OUTBOUND")){data.putString("FlightStage","CLAMP");save(job.update(0,0,Phase.CLAMP,false,false,occupied,c.gates(),data,""));}
            else if(stage.equals("LOADED")){data.putString("FlightStage","UNCLAMP");save(job.update(0,0,Phase.RELEASE,true,false,c.spaces(),c.gates(),data,""));}
            else{var stand=manifest.aircraft().get(m.aircraft());if(!aircraftSupported(stand)||!NervAirTransportManifestR52.same(next.plane(),manifest.node(stand.stand()).frame().plane())){hold(job,"原飞机未在实际原泊位支撑上到位");return;}if(data.getBoolean("FlightWaitingR52")){var stationaryHold=proof(job.aircraft(),p,next,next,occupied,false);var wait=NervFlightProofR52.holdPickup(level,ground().pool(),job.task(),stationaryHold,p,Set.copyOf(readList(data,"PickupHeldSpaces")),ground().bindings());if(wait==null||!ground().owner().releaseWaitingPickup(level,wait,data)){NervAircraftFrameR52.putFrame(data,"Frame",next);save(job.update(job.leg(),c.ticks(),Phase.HOLD,false,false,occupied,c.gates(),data,"原机已返场；等待原载荷原位解锁"));return;}}if(!clearStandReference(job,next,data,occupied)){save(job.update(job.leg(),c.ticks(),Phase.HOLD,false,job.payloadTransferred(),occupied,c.gates(),data,"原泊位等待实际空机样本收尾"));return;}ground().pool().cancel(job.task(),job.original().owner());save(job.update(job.leg(),c.ticks(),job.cancelRequested()?Phase.CANCELLED:Phase.COMPLETE,false,job.payloadTransferred(),occupied,c.gates(),data,""));}
        }
        void preflight(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            var stand=manifest.aircraft().get(m.aircraft());if(!aircraftSupported(stand)||!NervAirTransportManifestR52.same(current.plane(),manifest.node(stand.stand()).frame().plane())){hold(j,"原泊位真实支持/机体帧已改变");return;}
            var refreshed=ground().owner().previewFlight(level,j.original(),j.kind(),data);if(refreshed==null){hold(j,"等待原机体在真实支撑上停稳，原飞机保持原泊位");return;}p=refreshed;previews.put(j.task(),p);data.put("PickupRoot",NervAircraftFrameR52.encodeRigid(p.root()));
            var aircraftProof=proof(j.aircraft(),p,current,current,j.spaces(),false);var actualPickup=pickupSpaces(m,p);data.put("PickupHeldSpaces",writeList(actualPickup));var wait=NervFlightProofR52.holdPickup(level,ground().pool(),j.task(),aircraftProof,p,actualPickup,ground().bindings());
            if(j.cancelRequested())
            {if(data.getBoolean("FlightWaitingR52")&&(wait==null||!ground().owner().releaseWaitingPickup(level,wait,data))){hold(j,"正在确认机体停稳");return;}ground().pool().cancel(j.task(),j.original().owner());save(j.update(0,0,Phase.CANCELLED,false,false,j.spaces(),j.mechanisms(),data,"取消于原泊位，未起飞"));return;}
            if(wait==null||!ground().owner().holdFlightPickup(level,wait,data)){save(j.update(0,0,Phase.PREPARE,false,false,j.spaces(),j.mechanisms(),data,"正在固定机体，等待起飞"));return;}
            p=ground().owner().previewFlight(level,j.original(),j.kind(),data);if(p==null){hold(j,"原机体姿势保持后完整来源不可读");return;}previews.put(j.task(),p);
            var doors=allDoors(m);if(!j.mechanisms().containsAll(doors)){var gateLease=proof(j.aircraft(),p,current,current,j.spaces(),true);if(gateLease==null||!ground().pool().retargetFlightSpaces(j.task(),j.spaces(),doors,access(j.original(),j.kind(),j.aircraft(),gateLease,false))){save(j.update(0,0,Phase.PREPARE,false,false,j.spaces(),j.mechanisms(),data,"等待舱门和航路可用"));return;}j=j.update(0,0,Phase.PREPARE,false,false,j.spaces(),doors,data,"");save(j);}
            if(!ground().owner().prepareFlightGates(level,j.original(),j.kind(),j.mechanisms(),data)||!pathReady(m,p,data)){save(j.update(0,0,Phase.PREPARE,false,false,j.spaces(),j.mechanisms(),data,"舱门正在开启，正在检查航路"));return;}
            var first=manifest.corridor(m.outbound().get(0));var spaces=new HashSet<>(first.spaces());spaces.addAll(readList(data,"PickupHeldSpaces"));var checked=proof(j.aircraft(),p,current,current,spaces,true);if(checked==null||!ground().pool().retargetFlightSpaces(j.task(),spaces,first.gates(),access(j.original(),j.kind(),j.aircraft(),checked,false))){hold(j,"起飞航路受阻，等待净空");return;}
            data.putString("FlightStage","OUTBOUND");save(j.update(0,0,Phase.FERRY,false,false,spaces,first.gates(),data,""));
        }
        void clamp(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            if(j.age()>20||j.carrying()||!clampRigMatches(j.age(),current)||!p.current(level)){hold(j,"实际停稳原姿势/原乘员/夹具保存时钟已改变");return;}float t=Math.min(1,(j.age()+1)/20F);var next=new Frame(current.plane(),p.root(),new Rig(current.rig().hoist(),t,1-t));var checked=proof(j.aircraft(),p,current,next,j.spaces(),true);if(checked==null){hold(j,"原夹具连续伸展完整 sweep 受阻");return;}
            var plane=(UNTransportEntity)level.getEntity(j.aircraft());if(!NervAircraftFrameR52.apply(plane,checked)){hold(j,"原夹具真实通道未提交");return;}NervAircraftFrameR52.putFrame(data,"Frame",next);
            if(t<1){save(j.update(0,j.age()+1,Phase.CLAMP,false,false,j.spaces(),j.mechanisms(),data,""));return;}
            j=j.update(0,20,Phase.CLAMP,false,false,j.spaces(),j.mechanisms(),data,"");save(j);var contact=proof(j.aircraft(),p,next,next,j.spaces(),true);var pickup=NervFlightProofR52.pickup(level,contact);if(pickup==null||!ground().owner().adoptFlight(level,pickup,data)){hold(j,"实际同帧原夹具接触/归属交接尚未完成");return;}
            plane.cargo(level.getEntity(j.original().eva()).getId(),true,1);data.putString("FlightStage","LOADED");save(j.update(0,0,Phase.CRUISE,true,false,j.spaces(),j.mechanisms(),data,""));
        }
        void retractPickup(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            if(j.age()>20||j.carrying()||!clampRigMatches(j.age(),current)||!p.current(level)){hold(j,"收回前原夹具/原位载荷时钟不一致");return;}
            int age=Math.max(0,j.age()-1);float t=age/20F;var next=new Frame(current.plane(),age==0?null:p.root(),new Rig(current.rig().hoist(),t,1-t));
            var checked=proof(j.aircraft(),p,current,next,j.spaces(),true);if(checked==null||!NervAircraftFrameR52.apply((UNTransportEntity)level.getEntity(j.aircraft()),checked)){hold(j,"原夹具连续收回的完整实际 sweep 受阻");return;}
            NervAircraftFrameR52.putFrame(data,"Frame",next);j=j.update(0,age,Phase.RELEASE,false,false,j.spaces(),j.mechanisms(),data,"原载荷原位保持；夹具收回中");save(j);if(age>0)return;
            var chain=new ArrayList<String>();int passed=data.getInt("PassedOutbound");if(passed!=m.outbound().size()){hold(j,"已走出站航段记录不完整；不猜测返场链");return;}
            for(int i=passed-1;i>=0;i--){var reverse=manifest.reverse(manifest.corridor(m.outbound().get(i)));if(reverse==null){hold(j,"已走实际出站航段缺 Root 明确逆向链");return;}chain.add(reverse.id());}
            data.put("CancelChain",writeList(chain));data.putString("FlightStage","CANCEL");save(j.update(0,0,Phase.RETURN,false,false,j.spaces(),j.mechanisms(),data,"原夹具已实际收回；沿已走航段返场"));
        }
        void unclamp(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            if(j.age()>20||!j.carrying()||current.rig().deployment()!=1||Math.abs(current.rig().jaws()-j.age()/20F)>1e-6){hold(j,"实际卸载夹具与保存时钟不同，原载荷保持承托");return;}
            var doorPreparation=prepareDoors(j,p,current,data,receiverDoors(m));j=doorPreparation.job();if(!doorPreparation.ready())return;
            if(!manifest.receiver(m.receiver()).delivery()&&!NervEmptyCarrierTransferR52.ensure(level,j.original(),m.receiver(),j.task(),data))
            {save(j.update(0,j.age(),Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,"等待回收架到位"));return;}
            if(j.kind()==Kind.HULL_ONLY_RECOVERY&&!data.getBoolean("HullRecoveryCompleteR52"))
            {
                var plan=recoveryPlan(m,p,data);int age=data.getInt("HullRecoveryAgeR52");if(plan==null||age<0||age>NervHullGroundRecoveryR52.TICKS){hold(j,"原倒姿来源或接应扶正进度损坏，飞机夹具保持承托");return;}
                if(!plan.done(age))
                {
                    var accepted=NervHullGroundRecoveryR52.check(level,j.task(),j.aircraft(),geometry,plan,age,current,j.spaces(),ground().bindings());
                    if(accepted==null||!ground().owner().acceptHullRecoveryStepR52(level,accepted,data)){save(j.update(0,0,Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,"原飞机夹具承重，等待全身/双手/背部栓座/钢架连续扶正净空"));return;}
                    if(!NervAircraftFrameR52.applyRecoveryStepR52((UNTransportEntity)level.getEntity(j.aircraft()),accepted))throw new IllegalStateException("Checked original hull source committed without its same-tick actual aircraft cradle");
                    NervAircraftFrameR52.putFrame(data,"Frame",accepted.to());data.putInt("HullRecoveryAgeR52",age+1);var refreshed=ground().owner().previewFlight(level,j.original(),j.kind(),data);if(refreshed==null)throw new IllegalStateException("Accepted hull pose cannot re-capture the current original source");previews.put(j.task(),refreshed);
                    save(j.update(0,0,Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,age<NervHullGroundRecoveryR52.POSE_TICKS?"原夹具随真实关节缓慢扶正":"原夹具承重，双鞋上方连续缓慢下降"));return;
                }
                data.putBoolean("HullRecoveryCompleteR52",true);p=ground().owner().previewFlight(level,j.original(),j.kind(),data);if(p==null){hold(j,"原扶正机体当前来源不可读");return;}previews.put(j.task(),p);
            }
            var receiver=resolvedReceiver(m,p,data);if(receiver==null||!(receiver.delivery()?NervFlightProofR52.deliverySupportReady(level,p,current.cargo(),receiver)&&receiver.gates().stream().allMatch(g->ground().nativeAccess().resourceReady(g,true)):ground().owner().receiverReady(level,receiver.port(),j.original(),j.kind(),receiver.stopped(),data))){save(j.update(0,j.age(),Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,"等待实际接应夹具/原转移架连续承托到位"));return;}
            p=ground().owner().previewFlight(level,j.original(),j.kind(),data);if(p==null){hold(j,"实际接应架到位后完整原组几何不可读");return;}previews.put(j.task(),p);float t=Math.min(1,(j.age()+1)/20F);var next=new Frame(current.plane(),receiver.stopped(),new Rig(current.rig().hoist(),1,t));var checked=proof(j.aircraft(),p,current,next,j.spaces(),true);if(checked==null||!ground().owner().applyFlightStep(level,checked,data)||!NervAircraftFrameR52.apply((UNTransportEntity)level.getEntity(j.aircraft()),checked)){hold(j,"承托后原夹具连续卸载 sweep 受阻");return;}NervAircraftFrameR52.putFrame(data,"Frame",next);
            if(t<1){save(j.update(0,j.age()+1,Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,""));return;}
            j=j.update(0,20,Phase.RELEASE,true,false,j.spaces(),j.mechanisms(),data,"");save(j);var stopped=proof(j.aircraft(),p,next,next,j.spaces(),true);var receipt=NervFlightProofR52.receiver(level,stopped,receiver,ground().owner(),data);if(!receiver.delivery()&&(receipt==null||!ground().owner().acceptAirReceiver(level,receipt,data))){hold(j,"原接应实际端点接管失败");return;}
            // Keep the payload lease while the plane physically clears the
            // receiver. Ground reservation occurs atomically afterwards.
            ((UNTransportEntity)level.getEntity(j.aircraft())).cargo(-1,false,1);data.put("ReceiverHeldSpaces",writeList(j.spaces()));data.putString("FlightStage","TRANSFER");data.putInt("TransferLeg",0);data.putInt("TransferAge",0);data.putUUID("GroundTask",UUID.randomUUID());save(j.update(0,0,Phase.RETREAT,false,false,j.spaces(),j.mechanisms(),data,""));
        }
        void transfer(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            int index=data.getInt("TransferLeg"),age=data.getInt("TransferAge");if(index>=m.retreat().size()){hold(j,"原飞机未能离开接应资源域");return;}var c=manifest.corridor(m.retreat().get(index));tickets(c);var doorPreparation=prepareDoors(j,p,current,data,c.gates());j=doorPreparation.job();if(!doorPreparation.ready())return;if(!gates(c)){hold(j,"等待实际接应退出门/空域");return;}
            var declaredTo=manifest.node(c.to()).frame();var start=age==0?current:NervAircraftFrameR52.decode(data.getCompound("TransferStart"));if(age==0)data.put("TransferStart",NervAircraftFrameR52.encode(current));var to=new Frame(declaredTo.plane(),current.cargo(),new Rig(declaredTo.rig().hoist(),0,1));var next=start.interpolate(to,ease((double)Math.min(c.ticks(),age+1)/c.ticks()));var held=new HashSet<>(c.spaces());held.addAll(readList(data,"ReceiverHeldSpaces"));var checked=proof(j.aircraft(),p,current,next,held,true);
            if(checked==null||!ground().pool().retargetFlightSpaces(j.task(),held,c.gates(),access(j.original(),j.kind(),j.aircraft(),checked,false))||!NervAircraftFrameR52.apply((UNTransportEntity)level.getEntity(j.aircraft()),checked)){hold(j,"原飞机连续退出 sweep/共享占域受阻");return;}NervAircraftFrameR52.putFrame(data,"Frame",next);data.putInt("TransferAge",Math.min(c.ticks(),age+1));var spaces=c.spaces();
            if(age+1>=c.ticks())
            {
                spaces=manifest.node(c.to()).spaces();var stationary=proof(j.aircraft(),p,next,next,spaces,false);String route=manifest.receiver(m.receiver()).reverseRoutes().get(j.original().variant());ground().nativeAccess().ownerData(data);
                if(stationary!=null&&manifest.receiver(m.receiver()).delivery())
                {
                    var receipt=NervFlightProofR52.delivery(level,stationary,manifest.receiver(m.receiver()));
                    if(receipt!=null&&ground().pool().handoffFlightToDelivery(j.task(),spaces,Set.of(),access(j.original(),j.kind(),j.aircraft(),stationary,true,receipt,data)))
                    {
                        data.putString("FlightStage","RETREAT");var plane=(UNTransportEntity)level.getEntity(j.aircraft());plane.cargo(-1,false,0);
                        if(index+1>=m.retreat().size()){var delivered=j.update(index,c.ticks(),Phase.RETURN,false,true,spaces,Set.of(),data,"");if(!aircraftSupported(manifest.aircraft().get(m.aircraft()))||!clearStandReference(delivered,next,data,spaces)){save(delivered.hold("原泊位实际空机样本/承托收尾未完成"));return;}ground().pool().cancel(j.task(),j.original().owner());save(delivered.update(index,c.ticks(),Phase.COMPLETE,false,true,spaces,Set.of(),data,""));return;}
                        save(j.update(index+1,0,Phase.RETURN,false,true,spaces,Set.of(),data,""));return;
                    }
                }
                if(stationary!=null&&!manifest.receiver(m.receiver()).delivery()&&NervRouteRuntimeR52.canAcceptFlightGround(level,j.original(),j.kind(),route))
                {
                    var result=ground().pool().handoffFlightToGround(j.task(),data.getUUID("GroundTask"),route,spaces,Set.of(),access(j.original(),j.kind(),j.aircraft(),stationary,true),ground().nativeAccess());
                    if(result.accepted())
                    {
                        if(!NervRouteRuntimeR52.acceptFlightGround(level,result.state(),data))throw new IllegalStateException("Atomic ground lease accepted but mechanical runtime receipt rejected");
                        var plane=(UNTransportEntity)level.getEntity(j.aircraft());plane.cargo(-1,false,0);level.getEntity(j.original().eva()).getPersistentData().putBoolean("R52AirGroundHandoff",true);data.putString("FlightStage","RETREAT");
                        if(index+1>=m.retreat().size()){var delivered=j.update(index,c.ticks(),Phase.RETURN,false,true,spaces,Set.of(),data,"");if(!aircraftSupported(manifest.aircraft().get(m.aircraft()))||!clearStandReference(delivered,next,data,spaces)){save(delivered.hold("原泊位实际空机样本/承托收尾未完成"));return;}ground().pool().cancel(j.task(),j.original().owner());save(delivered.update(index,c.ticks(),Phase.COMPLETE,false,true,spaces,Set.of(),data,""));return;}
                        save(j.update(index+1,0,Phase.RETURN,false,true,spaces,Set.of(),data,""));return;
                    }
                }
                data.putInt("TransferAge",c.ticks());
            }
            save(j.update(0,0,Phase.RETREAT,false,false,held,c.gates(),data,"原飞机退出中；原载荷保持承托和租约"));
        }
        void cancelUnladen(Job j,Mission m,NervFlightProofR52.FlightPickupPreview p,Frame current,CompoundTag data)
        {
            // Reverse exactly the travelled current fraction, then the actual
            // completed prefix. The original outbound chain is never guessed.
            var original=manifest.corridor(m.outbound().get(j.leg()));var reverse=manifest.reverse(original);if(reverse==null){hold(j,"当前已走航段没有 Root 明确逆向返场链");return;}
            var chain=new ArrayList<String>();chain.add(reverse.id());for(int i=j.leg()-1;i>=0;i--){var r=manifest.reverse(manifest.corridor(m.outbound().get(i)));if(r==null){hold(j,"已走原航段缺实际逆向链");return;}chain.add(r.id());}
            var tag=new ListTag();chain.forEach(id->tag.add(StringTag.valueOf(id)));data.put("CancelChain",tag);data.putString("FlightStage","CANCEL");
            // Quintic is symmetric; t'=1-t restores the exact same stopped
            // point in the authored reciprocal corridor, without rebasing.
            int reverseAge=reverse.ticks()-Math.round((float)j.age()/original.ticks()*reverse.ticks());if(reverse.ticks()!=original.ticks()){hold(j,"取消逆向时钟须与原物理段一致");return;}
            save(j.update(0,reverseAge,Phase.RETURN,false,false,j.spaces(),j.mechanisms(),data,"沿已走实际段逆向返场"));
        }
        boolean clearStandReference(Job j,Frame current,CompoundTag data,Set<String> spaces)
        {
            if(current.cargo()==null)return true;if(!j.payloadTransferred()||current.rig().deployment()!=0)return false;var plane=(UNTransportEntity)level.getEntity(j.aircraft());double clock=NervAircraftFrameR52.rotorClock(plane);var empty=new Frame(current.plane(),null,current.rig());var checked=NervFlightProofR52.checkAircraftStep(level,manifest,geometry,j.aircraft(),j.original(),j.kind(),current,empty,spaces,ground().bindings(),clock,clock);
            if(checked==null||!NervAircraftFrameR52.apply(plane,checked))return false;data.put("DetachedCargoReferenceR52",data.getCompound("Frame").getCompound("Cargo").copy());NervAircraftFrameR52.putFrame(data,"Frame",empty);return true;
        }
        void tickets(Set<String> ids){for(String id:ids){var binding=ground().bindings().get(id);if(binding==null)continue;for(var box:binding.spaces())for(int x=(int)Math.floor(box.minX)>>4;x<=(int)Math.floor(Math.nextDown(box.maxX))>>4;x++)for(int z=(int)Math.floor(box.minZ)>>4;z<=(int)Math.floor(Math.nextDown(box.maxZ))>>4;z++){var at=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,at,1,at);}}}
        void tickets(Corridor c)
        {
            // A finite Root corridor can span many chunks. Loading only its
            // endpoints would permanently fail the full preflight sweep.
            for(String id:c.spaces()){var binding=ground().bindings().get(id);if(binding==null)continue;for(var box:binding.spaces()){int x0=(int)Math.floor(box.minX)>>4,x1=(int)Math.floor(Math.nextDown(box.maxX))>>4,z0=(int)Math.floor(box.minZ)>>4,z1=(int)Math.floor(Math.nextDown(box.maxZ))>>4;for(int x=x0;x<=x1;x++)for(int z=z0;z<=z1;z++){var cp=new ChunkPos(x,z);level.getChunkSource().addRegionTicket(TICKET,cp,1,cp);}}}
            for(String node:List.of(c.from(),c.to()))ticketAt(manifest.node(node).frame().plane().translation());
        }
        void ticketAt(Vec3 p){var cp=new ChunkPos((int)Math.floor(p.x)>>4,(int)Math.floor(p.z)>>4);level.getChunkSource().addRegionTicket(TICKET,cp,6,cp);}
    }
    private static ListTag writeList(Set<String> ids){var list=new ListTag();ids.stream().sorted().forEach(id->list.add(StringTag.valueOf(id)));return list;}
    private static ListTag writeList(List<String> ids){var list=new ListTag();ids.forEach(id->list.add(StringTag.valueOf(id)));return list;}
    private static List<String> readList(CompoundTag data,String key){var r=new ArrayList<String>();for(var s:data.getList(key,Tag.TAG_STRING))r.add(s.getAsString());return List.copyOf(r);}
    private static Phase phase(String stage){return stage.equals("OUTBOUND")?Phase.FERRY:stage.equals("LOADED")?Phase.CRUISE:Phase.RETURN;}
    public static double ease(double t){t=Math.max(0,Math.min(1,t));return t*t*t*(t*(6*t-15)+10);}
    public static boolean clampRigMatches(int age,Frame frame){float t=Math.min(1,age/20F);return age>=0&&age<=20&&frame.rig().deployment()==t&&frame.rig().jaws()==1-t;}
    private NervAirTransportRuntimeR52(){}
}
