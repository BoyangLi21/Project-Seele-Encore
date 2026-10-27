package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.entity.Entity;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.NervRouteRuntimeStateR52.Job;
import com.projectseele.world.NervRouteRuntimeStateR52.Phase;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Explicit Root installation and the sole R52 logistics entry/lifecycle owner.
 * Unclaimed old worlds retain legacy. Claimed incomplete/reloaded worlds hold. */
public final class NervRouteRuntimeR52
{
    private record Door(UUID entity,float width,float height){}
    private static final Map<ServerLevel,Optional<NervRouteRuntimeStateR52>> SAVES=new WeakHashMap<>();
    private static final Map<ServerLevel,Controller> LIVE=new WeakHashMap<>();
    private static final Map<ServerLevel,String> CONTINUOUS_RECOVERY_DIAGNOSTICS_R53=new WeakHashMap<>();
    public static String continuousRecoveryDiagnosticR53(ServerLevel level){return CONTINUOUS_RECOVERY_DIAGNOSTICS_R53.getOrDefault(level,"");}
    private static final Set<ServerLevel> INSTALLING=Collections.newSetFromMap(new WeakHashMap<>());
    /** The migrated map requires an explicit installed Root assembly declaration. */
    public static boolean mapRebuildEnabledR52(){return true;}
    private static NervRouteRuntimeStateR52 state(ServerLevel level,boolean create)
    {
        if(!mapRebuildEnabledR52()){if(create)throw new IllegalStateException("This release uses the original R50 map; migrated routes are deferred");return null;}
        Optional<NervRouteRuntimeStateR52> known=SAVES.computeIfAbsent(level,l->Optional.ofNullable(l.getDataStorage().get(NervRouteRuntimeStateR52::load,NervRouteRuntimeStateR52.NAME)));
        if(known.isPresent())return known.get();if(!create)return null;
        var s=level.getDataStorage().computeIfAbsent(NervRouteRuntimeStateR52::load,NervRouteRuntimeStateR52::new,NervRouteRuntimeStateR52.NAME);SAVES.put(level,Optional.of(s));return s;
    }
    public static boolean claimed(ServerLevel level){var state=state(level,false);return LIVE.containsKey(level)||state!=null&&state.claimed();}
    public static boolean ready(ServerLevel level){var c=LIVE.get(level);return c!=null&&(c.saved.pendingInstallationR52()==null||INSTALLING.contains(level))&&c.saved.fault().isEmpty()&&c.saved.epoch()==c.directory.epoch()&&c.saved.fingerprint().equals(c.directory.fingerprint())&&c.owner.fullRigidFramesReady(level,c.directory);}
    /** Only the current ordinary phone boarding receipt may delegate an idle original NPC. */
    static boolean manualNpcReceiptR60(Original original,Unit unit,long epoch,String dimension,String directory,
            String pilotDirectory,String pilotOperation,UUID declaredPilot,UUID stampedCommander,boolean currentOwner)
    {
        return original!=null&&original.mission().isEmpty()&&unit!=null&&currentOwner
                &&original.epoch()==epoch&&original.dimension().equals(dimension)&&original.variant()==unit.variant()
                &&original.eva().equals(unit.eva())&&original.plug().equals(unit.plug())
                &&original.pilot().equals(declaredPilot)&&original.owner().equals(stampedCommander)
                &&directory!=null&&!directory.isEmpty()
                &&directory.equals(pilotDirectory)&&"board".equals(pilotOperation);
    }
    static boolean manualNpcCommanderR60(UUID owner,UUID online,boolean alive,boolean sameLevel,boolean spectator,boolean authorized)
    {return owner!=null&&owner.equals(online)&&alive&&sameLevel&&!spectator&&authorized;}
    static boolean manualOriginalNpcR60(ServerLevel level,NervRouteDirectoryR52 directory,
            NervRouteNativeR52.AssemblyOwner owner,Original original,EvaUnit01Entity eva,TrainingPilotEntity pilot)
    {
        var c=LIVE.get(level);if(c==null||!(owner instanceof NervOriginalActorsR52.Access access))return false;
        var tag=eva.getPersistentData();var receipt=pilot.getPersistentData();
        UUID stamped=tag.hasUUID("R32SortieCommander")?tag.getUUID("R32SortieCommander"):null;
        return manualNpcReceiptR60(original,directory.unit(original.variant()),directory.epoch(),level.dimension().location().toString(),directory.fingerprint(),
                receipt.getString("R52OriginalPilotDirectory"),receipt.getString("R52OriginalPilotOperation"),
                access.originalPilot(level,original.variant())==pilot?pilot.getUUID():null,stamped,
                c.directory==directory&&c.owner==owner&&c.saved.claimed()&&c.saved.epoch()==directory.epoch()
                        &&c.saved.fingerprint().equals(directory.fingerprint())&&pilot.getAssignedVariant()==original.variant());
    }
    static boolean controllerLoadedR52(ServerLevel level){return LIVE.containsKey(level);}
    static NervRouteRuntimeStateR52 installationStateR52(ServerLevel level){return state(level,false);}
    static NervRouteRuntimeStateR52 queueInstallationR52(ServerLevel level,NervRouteRuntimeStateR52.PendingInstallationR52 request){var saved=state(level,true);saved.queueInstallationR52(request);return saved;}
    static void installationHeldR52(ServerLevel level){LIVE.remove(level);}
    public static String uprightGuideSourceR52(ServerLevel level){var saved=state(level,false);return saved!=null&&saved.claimed()?saved.uprightGuideSourceR52():"";}
    public record FlightContext(NervRouteDirectoryR52 directory,NervRouteReservationsR52 pool,NervRouteNativeR52 nativeAccess,Map<String,NervRouteNativeR52.Binding> bindings,NervFlightProofR52.Owner owner)
    {public FlightContext{bindings=directory.dynamicSpacesR52().bindings(Map.copyOf(bindings));}}
    public static FlightContext flightContext(ServerLevel level)
    {var c=LIVE.get(level);return c!=null&&ready(level)?c.flightContext:null;}
    public static Original originalForFlight(ServerLevel level,int variant,UUID commander)
    {var c=LIVE.get(level);if(c==null||!ready(level))return null;var job=c.saved.job(variant);if(job==null||job.phase()!=Phase.DEPLOYED)return null;var original=job.snapshot().original();return original.owner().equals(commander)&&original.epoch()==c.directory.epoch()&&job.snapshot().directoryFingerprint().equals(c.directory.fingerprint())&&original.dimension().equals(level.dimension().location().toString())?original:null;}
    /** Read before the atomic broker transfer; no leases or saved job change. */
    public static boolean canAcceptFlightGround(ServerLevel level,Original original,Kind kind,String routeId)
    {var c=LIVE.get(level);if(c==null||!ready(level))return false;var route=c.directory.route(routeId);var old=c.saved.job(original.variant());return route!=null&&route.recovery()&&route.variant()==original.variant()&&original.epoch()==c.directory.epoch()&&old!=null&&old.phase()==Phase.DEPLOYED&&sameOriginalProvenance(old.snapshot().original(),original)&&old.snapshot().directoryFingerprint().equals(c.directory.fingerprint());}
    private static boolean sameOriginalProvenance(Original a,Original b)
    {return a.epoch()==b.epoch()&&a.variant()==b.variant()&&a.eva().equals(b.eva())&&a.plug().equals(b.plug())&&a.pilot().equals(b.pilot())&&a.owner().equals(b.owner())&&a.dimension().equals(b.dimension());}
    /** Records exactly the already transferred lease; never reserves again. */
    public static boolean acceptFlightGround(ServerLevel level,Snapshot snapshot,CompoundTag ownerData)
    {
        var c=LIVE.get(level);if(c==null||!canAcceptFlightGround(level,snapshot.original(),snapshot.kind(),snapshot.route())||snapshot.stage()!=Stage.RESERVED||snapshot.leg()!=0||snapshot.fraction()!=0||!snapshot.equals(c.pool.query(snapshot.task()))||!snapshot.directoryFingerprint().equals(c.directory.fingerprint()))return false;
        var route=c.directory.route(snapshot.route());if(!ownerData.getString("AirReceiverPortR52").equals(route.port())||!ownerData.getString("AirReceiverDirectoryR52").equals(c.directory.fingerprint()))return false;
        var data=ownerData.copy();data.putString("AssemblyKindR52",snapshot.kind().name());data.remove(NervLaunchPhasesR53.KEY);data.putBoolean("Returning",true);data.putString("RouteR52",snapshot.route());for(String field:List.of("Finish","FinishTicks","FinishRoot","FinishFeet","FinishPlugLocal","LastFinishTick","FlightAircraftR52","FlightEpochR52","FlightDirectoryR52","FlightSourceR52","ContinuousClockR52","ContinuousDistanceR52","ContinuousRotationR52","ContinuousAutoLaunchR52","ContinuousCheckedStartR52"))data.remove(field);
        c.nativeAccess.ownerData(data);if(!c.nativeAccess.sameAssembly(snapshot.original(),snapshot.kind())||!c.nativeAccess.canRestoreAssembly(snapshot.original(),snapshot.kind(),route,0,0))return false;
        if(level.getEntity(snapshot.original().eva()) instanceof EvaUnit01Entity eva)EvaMechanicalFrameR52.setFlightCustody(eva,false,true);c.saved.put(new Job(snapshot,Phase.RETURNING,data,""));c.mirror(c.saved.job(snapshot.original().variant()));return true;
    }
    public static String personnelLiftManifest(ServerLevel level){var s=state(level,false);return s==null?"":s.personnelLiftManifest();}
    static void personnelLiftManifest(ServerLevel level,String actualVerifiedFile)
    {var c=LIVE.get(level);if(c==null||!c.owner.fullRigidFramesReady(level,c.directory)||!c.saved.fingerprint().equals(c.directory.fingerprint()))throw new IllegalStateException("Installed Root directory required before personnel lift binding");c.saved.personnelLiftManifest(actualVerifiedFile);S20PhysicalElevatorDirector.invalidateLiftSpecs(level.getServer());}
    public static long commissioningEpoch(ServerLevel level){var s=state(level,false);return s==null?0:s.epoch();}
    public static String directoryFingerprint(ServerLevel level){var s=state(level,false);return s==null?"":s.fingerprint();}
    public static NervOriginalActorsR52.Access originalActorAccess(ServerLevel level)
    {
        var c=LIVE.get(level);var saved=state(level,false);
        return c!=null&&saved!=null&&saved.claimed()&&saved.epoch()==c.directory.epoch()&&saved.fingerprint().equals(c.directory.fingerprint())
                &&c.owner instanceof NervOriginalActorsR52.Access access?access:null;
    }
    /** Root may stamp its migrated world pending before any native tick; no
     * default filename/world/coordinates are selected by this method. */
    public static void claimPending(ServerLevel level,long epoch,String rootReceiptSha256){state(level,true).claim(epoch,rootReceiptSha256);}
    public static boolean loadAndInstall(ServerLevel level,Path explicitRootFile,NervRouteNativeR52.AssemblyOwner owner)throws java.io.IOException
    {return install(level,JsonParser.parseString(Files.readString(explicitRootFile)).getAsJsonObject(),owner);}
    public static boolean install(ServerLevel level,JsonObject root,NervRouteNativeR52.AssemblyOwner owner)
    {
        return installParsed(level,root,NervRouteDirectoryR52.parse(root),owner,null);
    }
    /** The signed directory is unchanged. Air is a separate verified manifest
     * referencing its hash and reuses this exact directory object/pool. */
    static boolean installParsed(ServerLevel level,JsonObject root,NervRouteDirectoryR52 directory,NervRouteNativeR52.AssemblyOwner owner,JsonObject airDocument)
    {
        if(root.has("air_transport")||root.has("directory_fingerprint")||root.has("fingerprint"))throw new IllegalArgumentException("Directory cannot embed a manifest that refers to its own hash or contain a self-fingerprint");
        var running=LIVE.get(level);if(running!=null&&running.saved.jobs().stream().anyMatch(j->!Set.of(Phase.PARKED,Phase.DEPLOYED,Phase.CANCELLED).contains(j.phase())))throw new IllegalStateException("Active original ground leases cannot be discarded by hot reinstallation");
        if(!NervAirTransportRuntimeR52.compatibleGroundInstall(level,directory))throw new IllegalStateException("Active or foreign original flight leases cannot be discarded by ground installation");
        if(!directory.installed()||owner==null||!owner.fullRigidFramesReady(level,directory))return false;
        var runtime=root.getAsJsonObject("runtime");if(runtime==null)throw new IllegalArgumentException("Explicit native runtime bindings required");
        var bindings=NervRouteNativeR52.parseBindings(runtime.getAsJsonArray("bindings"),directory);var defaults=new HashMap<String,String>();
        for(var raw:runtime.getAsJsonArray("departure_defaults"))
        {
            var row=raw.getAsJsonObject();int variant=row.get("variant").getAsInt();
            for(String intent:List.of("surface","geofront","hakone"))
            {String id=row.get(intent).getAsString();Route route=directory.route(id);if(route==null||route.recovery()||route.variant()!=variant||route.bank()!=directory.bankForIntentR52(intent)||defaults.putIfAbsent(variant+"/"+intent,id)!=null)throw new IllegalArgumentException("Root departure default differs from explicit bank role");}
        }
        if(defaults.size()!=9)throw new IllegalArgumentException("Explicit defaults for all original units required");
        var doors=new HashMap<Integer,Door>();for(var raw:runtime.getAsJsonArray("hangar_doors"))
        {
            var row=raw.getAsJsonObject();int variant=row.get("variant").getAsInt();float width=row.get("width").getAsFloat(),height=row.get("height").getAsFloat();
            if(variant<0||variant>2||!Float.isFinite(width)||!Float.isFinite(height)||width<=0||height<=0||doors.putIfAbsent(variant,new Door(UUID.fromString(row.get("entity_uuid").getAsString()),width,height))!=null)throw new IllegalArgumentException("Explicit original hangar door geometry required");
        }
        if(doors.size()!=3||doors.values().stream().map(Door::entity).distinct().count()!=3)throw new IllegalArgumentException("Root must bind three distinct original wet-cage gates");
        var saved=state(level,true);if(!saved.fault().isEmpty()&&saved.interruptedContinuousCommitR53()==null)throw new IllegalStateException(saved.fault());saved.claim(directory.epoch(),directory.fingerprint());
        var controller=new Controller(level,directory,bindings,Map.copyOf(defaults),Map.copyOf(doors),owner,saved);
        if(!NervAirTransportRuntimeR52.quarantineSavedLeases(level,directory,controller.pool))throw new IllegalStateException("Original saved flight space/actor quarantine conflicts with this Root directory");
        for(var job:saved.jobs())if(!Set.of(Phase.PARKED,Phase.DEPLOYED,Phase.CANCELLED).contains(job.phase())&&!controller.pool.quarantineGround(job.snapshot()))throw new IllegalStateException("Original saved ground space/actor quarantine conflicts with this Root directory");
        LIVE.put(level,controller);INSTALLING.add(level);
        try
        {
            if(!saved.fault().isEmpty()&&!controller.recoverContinuousCommitR53()){LIVE.remove(level);return false;}
            if(airDocument!=null&&!NervAirTransportRuntimeR52.install(level,airDocument))throw new IllegalStateException("Explicit Root air transport/receiver installation is incomplete");
        }
        catch(java.io.IOException|RuntimeException failure){LIVE.remove(level);throw new IllegalStateException("Claimed Root installation held: actual declared air transport did not commission",failure);}
        finally{INSTALLING.remove(level);}return true;
    }
    public static EvaLogisticsDirector.ActionResult resumeParkedServiceR53(ServerLevel level,int variant)
    {
        var controller=LIVE.get(level);var job=controller==null?null:controller.saved.job(variant);
        if(!ready(level)||job==null||job.phase()!=Phase.PARKED||job.snapshot().stage()!=Stage.COMPLETE
                ||!(controller.owner instanceof NervAssemblyOwnerR52 plant))return unavailable();
        var observed=plant.parkedServiceReadbackR53(level,job.snapshot().original(),job.ownerData());
        if(observed==null)return new EvaLogisticsDirector.ActionResult(false,"现场原机、原栓、封口或已知液体/桥状态不满足整备续接，未修改现场。");
        observed.putUUID("ServiceReadbackTaskR53",job.snapshot().task());observed.putLong("ServiceReadbackTickR53",level.getGameTime());
        controller.saved.resumeParkedServiceR53(job,observed);controller.mirror(controller.saved.job(variant));
        return new EvaLogisticsDirector.ActionResult(true,"原任务已按实际液体和桥状态续接注液/桥复位；机体、驾驶员及任务身份保留。");
    }
    public static boolean pending(ServerLevel level,int variant)
    {var saved=state(level,false);var job=saved==null?null:saved.job(variant);return job!=null&&!Set.of(Phase.PARKED,Phase.DEPLOYED,Phase.CANCELLED).contains(job.phase());}
    public static List<EvaUnit01Entity> loadedOriginals(ServerLevel level)
    {
        var list=new ArrayList<EvaUnit01Entity>();for(int variant=0;variant<3;variant++)
        {var entry=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);if(entry!=null&&level.getEntity(entry.canonicalId()) instanceof EvaUnit01Entity eva&&eva.getUnitVariant()==variant&&!eva.isExperimentalUnit())list.add(eva);}return List.copyOf(list);
    }
    private static EvaLogisticsDirector.ActionResult unavailable(){return new EvaLogisticsDirector.ActionResult(false,"R52 运行目录或整组机械接口尚未就绪；原机体保持当前位置。");}
    public static EvaLogisticsDirector.ActionResult prepare(ServerLevel level,int variant)
    {
        var c=LIVE.get(level);if(c==null||!ready(level))return unavailable();
        var order=StaffCommandBookR24.unitOrder(level,variant);String intent=order!=null?NervOutletControlsR53.intent(order.requested)
                :TvCampaignSavedData.get(level).active.equals("ramiel")?TvEncounterSitesR45.departureIntentR53(level):"surface";
        if(TvCampaignSavedData.get(level).active.equals("ramiel")&&order!=null
                &&Set.of("prepare","launch","deploy").contains(order.requested))intent=TvEncounterSitesR45.departureIntentR53(level);
        var result=c.prepare(variant,intent);if(result.accepted()&&order!=null&&order.requested.equals(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY))c.launch(variant,null);return result;
    }
    public static EvaLogisticsDirector.ActionResult prepare(ServerLevel level,int variant,String rootIntent)
    {var c=LIVE.get(level);return c==null||!ready(level)?unavailable():c.prepare(variant,rootIntent);}
    public static EvaLogisticsDirector.ActionResult launch(ServerLevel level,int variant)
    {var c=LIVE.get(level);return c==null||!ready(level)?unavailable():c.launch(variant,null);}
    public static EvaLogisticsDirector.ActionResult launchToR53(ServerLevel level,int variant,String intent)
    {var c=LIVE.get(level);return c==null||!ready(level)?unavailable():c.launch(variant,intent);}
    public static EvaLogisticsDirector.ActionResult underground(ServerPlayer caller,int variant,boolean open)
    {
        var c=LIVE.get(caller.serverLevel());if(c==null||!ready(caller.serverLevel()))return unavailable();
        var job=c.saved.job(variant);if(job==null||!job.snapshot().original().owner().equals(caller.getUUID()))return new EvaLogisticsDirector.ActionResult(false,"原编队与当前指挥许可不符。");
        if(!open)return c.cancel(variant,caller.getUUID());return c.launch(variant,"geofront");
    }
    public static EvaLogisticsDirector.ActionResult recover(ServerLevel level,int variant)
    {var c=LIVE.get(level);return c==null||!ready(level)?unavailable():c.recover(variant);}
    public static EvaLogisticsDirector.ActionResult recover(ServerPlayer caller,int variant)
    {var c=LIVE.get(caller.serverLevel());if(c==null||!ready(caller.serverLevel()))return unavailable();var job=c.saved.job(variant);return job==null||!job.snapshot().original().owner().equals(caller.getUUID())?new EvaLogisticsDirector.ActionResult(false,"本次原编队的回收指挥者不符。"):c.recover(variant);}
    public static EvaLogisticsDirector.ActionResult cancel(ServerLevel level,int variant)
    {var c=LIVE.get(level);var s=state(level,false);var job=s==null?null:s.job(variant);return c==null||job==null?unavailable():c.cancel(variant,job.snapshot().original().owner());}
    public static void cancelOwner(ServerLevel level,UUID owner,int variant)
    {var c=LIVE.get(level);if(c==null)return;for(int v=0;v<3;v++)if(variant<0||variant==v)c.cancel(v,owner);}
    public static EvaUnit01Entity resetOriginalMaintenanceR53(ServerLevel level,int variant){var c=LIVE.get(level);if(c==null||!(c.owner instanceof NervAssemblyOwnerR52 owner))throw new IllegalStateException("原编队正在加载，尚未执行复位");var eva=owner.resetOriginalMaintenanceR53(level,variant);c.pool.clearOriginalMaintenanceR53(eva.getUUID());c.saved.clearOriginalMaintenanceR53(variant);return eva;}
    public static EvaLogisticsDirector.Status status(ServerLevel level,int variant)
    {
        var entry=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);var s=state(level,false);var job=s==null?null:s.job(variant);
        return new EvaLogisticsDirector.Status(variant,job==null?(entry==null?"UNREGISTERED":entry.phase().name()):job.phase()==Phase.PARKED&&!job.waiting().isEmpty()?"SERVICE_HOLD":NervRouteRuntimeStateR52.legacyPhase(job),entry!=null&&level.getEntity(entry.canonicalId()) instanceof EvaUnit01Entity,
                entry==null?null:entry.canonicalId(),entry==null?0:entry.lclLayers(),job==null?0:job.snapshot().leg());
    }
    public static List<String> sortieStatusR53(ServerLevel level)
    {
        var result=new ArrayList<String>();var controller=LIVE.get(level);var saved=state(level,false);
        result.add(level.dimension().location()+" tick="+level.getGameTime()+" installed="+(controller!=null)
                +" fault="+(saved==null?"no_saved_routes":saved.fault()));
        if(saved==null)return result;
        for(var job:saved.jobs())
        {
            var original=job.snapshot().original();var data=job.ownerData();
            var carrier=controller==null?null:NervOriginalCarrierR52.controller(level,original);
            String hold=controller!=null&&controller.owner instanceof NervAssemblyOwnerR52 owner?owner.holdReason(original.eva()):"";
            result.add("EVA-0"+original.variant()+" "+job.phase()+" prepare="+data.getString("Prepare")+":"+data.getInt("PrepareTicks")
                    +" drained="+data.getInt("DrainedLayers")+" leg="+job.snapshot().leg()+" progress="+job.snapshot().fraction()
                    +" wait="+job.waiting()+" hold="+hold+" carrier="+(carrier==null?"unloaded":NervOriginalCarrierR52.lastRejectionR53(carrier)));
        }
        return List.copyOf(result);
    }
    public static void tick(ServerLevel level)
    {
        var c=LIVE.get(level);if(c==null)return;
        if(c.saved.interruptedContinuousCommitR53()!=null)c.recoverContinuousCommitR53();
        if(ready(level))c.tick();
    }
    /** Constructed only after current physical endpoint and old-clock checks. */
    static final class RecoveredContinuousStepR53
    {
        final Snapshot from,to;
        final List<DirectoryTrajectoryR52> paths;
        private final ServerLevel level;
        private final long tick;
        private RecoveredContinuousStepR53(ServerLevel level,Snapshot from,Snapshot to,List<DirectoryTrajectoryR52> paths)
        {this.level=level;this.tick=level.getGameTime();this.from=from;this.to=to;this.paths=List.copyOf(paths);}
        boolean current(){return level.getGameTime()==tick;}
    }
    public static List<net.minecraft.world.phys.shapes.VoxelShape> cageCollisions(ServerLevel level,Entity actor,net.minecraft.world.phys.AABB query,List<net.minecraft.world.phys.shapes.VoxelShape> original)
    {var c=LIVE.get(level);if(c==null||!ready(level)||!(c.owner instanceof NervAssemblyOwnerR52 owner))return original;var extra=owner.actualCageCollisions(level,actor,query);if(extra.isEmpty())return original;var result=new ArrayList<>(original);result.addAll(extra);return result;}
    public static boolean personnelBindingsReady(ServerLevel level){var c=LIVE.get(level);return c!=null&&c.owner.originalPersonnelBindingsReady(level);}
    public static TrainingPilotDirector.ActionResult requestPilot(ServerLevel level,int variant,String operation)
    {var c=LIVE.get(level);return c!=null&&personnelBindingsReady(level)?c.owner.requestOriginalPilot(level,variant,operation):new TrainingPilotDirector.ActionResult(false,"R52 原驾驶员待命/电话/座椅绑定尚未接通，保持原位。");}
    public static boolean pilotRouting(ServerLevel level,TrainingPilotEntity pilot,String operation)
    {var c=LIVE.get(level);if(c!=null&&personnelBindingsReady(level)&&c.owner.routeOriginalPilot(level,pilot,operation))return true;pilot.getNavigation().stop();return false;}
    public static boolean pilotStandby(ServerLevel level,int variant){var c=LIVE.get(level);return c!=null&&personnelBindingsReady(level)&&c.owner.atOriginalPilotStandby(level,variant);}
    public static void invalidateMission(ServerLevel level)
    {var c=LIVE.get(level);if(c!=null)for(var job:c.saved.jobs())if(!job.snapshot().original().mission().isEmpty()&&!Set.of(Phase.PARKED,Phase.DEPLOYED,Phase.CANCELLED,Phase.RETURNING,Phase.FINISHING).contains(job.phase()))c.cancel(job.snapshot().original().variant(),job.snapshot().original().owner());}
    public static void automatic(ServerLevel level,int variant)
    {
        if(!ready(level))return;var c=LIVE.get(level);var mission=AutoSortieR32.missionToken(level,variant);if(mission.isEmpty())return;
        var order=StaffCommandBookR24.unitOrder(level,variant);if(order!=null&&!order.automatic)return;
        var job=c.saved.job(variant);if(job==null||job.phase()==Phase.PARKED){var result=c.prepare(variant,TvCampaignSavedData.get(level).active.equals("ramiel")?TvEncounterSitesR45.departureIntentR53(level):"surface");var created=c.saved.job(variant);if(created!=null&&c.directory.route(created.snapshot().route()).continuousUpright())c.launch(variant,null);}
        else if(job.phase()==Phase.READY)c.launch(variant,null);
    }
    /** A moved original's declared dimensions replace the old absolute -370
     * calculation. No search, duplicate disposal, relocation or door spawn. */
    public static void hangarDoor(ServerLevel level,int variant,boolean open)
    {
        var c=LIVE.get(level);if(c==null||!ready(level))return;var shape=c.doors.get(variant);
        if(shape!=null&&level.getEntity(shape.entity()) instanceof NervHangarDoorEntity door)door.applyDeclaredR52(variant,shape.width(),shape.height(),open);
    }
    private static final class Controller
    {
        final ServerLevel level;final NervRouteDirectoryR52 directory;final NervRouteReservationsR52 pool;final NervRouteNativeR52 nativeAccess;
        final Map<String,String> defaults;final Map<Integer,Door> doors;final NervRouteNativeR52.AssemblyOwner owner;final NervRouteRuntimeStateR52 saved;
        final Map<String,NervRouteNativeR52.Binding> bindings;
        final FlightContext flightContext;
        final Set<UUID> parkedReadbacksR53=new HashSet<>();
        final Map<UUID,Long> parkedReadbackStartedR54=new HashMap<>();
        Controller(ServerLevel level,NervRouteDirectoryR52 directory,Map<String,NervRouteNativeR52.Binding> bindings,Map<String,String> defaults,Map<Integer,Door> doors,NervRouteNativeR52.AssemblyOwner owner,NervRouteRuntimeStateR52 saved)
        {this.level=level;this.directory=directory;this.pool=new NervRouteReservationsR52(directory);this.defaults=defaults;this.doors=doors;this.owner=owner;this.saved=saved;this.bindings=directory.dynamicSpacesR52().bindings(Map.copyOf(bindings));this.nativeAccess=new NervRouteNativeR52(level,directory,bindings,owner);this.flightContext=owner instanceof NervFlightProofR52.Owner flightOwner?new FlightContext(directory,pool,nativeAccess,this.bindings,flightOwner):null;}
        final Set<UUID> continuousPrimedR52=new HashSet<>();
        NervTraversalPolicyR53.Mode traversalModeR53=NervTraversalPolicyR53.Mode.NORMAL;
        private record StoppedPreflightRetryR53(UUID task,String route,double from,double to,long after){}
        private final Map<Integer,StoppedPreflightRetryR53> stoppedPreflightRetriesR53=new HashMap<>();
        private boolean deferStoppedPreflightR53(Job job,Route route,double from,double to)
        {
            int variant=job.snapshot().original().variant();var retry=stoppedPreflightRetriesR53.get(variant);
            if(retry==null)return false;
            if(!retry.task().equals(job.snapshot().task())||!retry.route().equals(route.id())||retry.from()!=from||retry.to()!=to)
            {stoppedPreflightRetriesR53.remove(variant);return false;}
            return level.getGameTime()<retry.after();
        }
        private void retryStoppedPreflightR53(Job job,Route route,double from,double to)
        {
            // A blocked, stationary machine must not rescan its entire route
            // every tick and stall unrelated traffic. No successful proof is cached.
            stoppedPreflightRetriesR53.put(job.snapshot().original().variant(),
                    new StoppedPreflightRetryR53(job.snapshot().task(),route.id(),from,to,level.getGameTime()+10));
        }
        Original original(int variant)
        {
            nativeAccess.ownerData(new CompoundTag());
            var unit=directory.unit(variant);if(unit==null)return null;Entity p=level.getEntity(unit.plug());if(!(p instanceof EntryPlugCarrierEntity plug)||plug.getFirstPassenger()==null)return null;
            Entity pilot=plug.getFirstPassenger();UUID commander=pilot instanceof ServerPlayer?pilot.getUUID():null;
            String mission=AutoSortieR32.missionToken(level,variant);
            if(commander==null&&mission.isEmpty())
            {var eva=level.getEntity(unit.eva());if(!(eva instanceof EvaUnit01Entity original)||!original.getPersistentData().hasUUID("R32SortieCommander"))return null;commander=original.getPersistentData().getUUID("R32SortieCommander");}
            else
            {var assignment=TvCampaignSavedData.get(level).sorties.get(variant);if(commander==null&&assignment!=null)commander=assignment.commander;}
            if(commander==null)return null;
            if(pilot instanceof TrainingPilotEntity&&mission.isEmpty())
            {var online=level.getServer().getPlayerList().getPlayer(commander);if(!manualNpcCommanderR60(commander,online==null?null:online.getUUID(),online!=null&&online.isAlive(),online!=null&&online.level()==level,online!=null&&online.isSpectator(),online!=null&&NervStaffDialogue.authorized(online)))return null;}
            var o=new Original(directory.epoch(),variant,unit.eva(),unit.plug(),pilot.getUUID(),commander,mission,level.dimension().location().toString());return nativeAccess.sameOriginalAssembly(o)?o:null;
        }
        EvaLogisticsDirector.ActionResult prepare(int variant,String intent)
        {
            var existing=saved.job(variant);if(existing!=null&&!Set.of(Phase.PARKED,Phase.CANCELLED).contains(existing.phase()))return new EvaLogisticsDirector.ActionResult(false,"原机体已有运行安排，请先确认当前状态。");
            if(existing!=null&&existing.phase()==Phase.PARKED&&owner instanceof NervAssemblyOwnerR52 plant)
            {
                plant.retainOriginalBayBlocksR54(level,existing.snapshot().original());
                String hold=plant.parkedServiceHoldR53(level,existing.snapshot().original());
                if(!hold.isEmpty()){saved.put(existing.update(existing.snapshot(),existing.phase(),existing.ownerData(),hold));return new EvaLogisticsDirector.ActionResult(false,hold);}
            }
            Original original=original(variant);String route=defaults.get(variant+"/"+intent);if(original==null||route==null)return new EvaLogisticsDirector.ActionResult(false,"等待原驾驶员、原插入栓与 Root 路线许可。");
            var preparation=new CompoundTag();
            if(existing!=null&&existing.phase()==Phase.CANCELLED&&existing.ownerData().contains("Prepare"))
            {
                var stopped=existing.snapshot();
                if(stopped.stage()!=Stage.CANCELLED||stopped.leg()!=0||stopped.fraction()!=0
                        ||!stopped.original().equals(original)||!stopped.route().equals(route)
                        ||!(owner instanceof NervAssemblyOwnerR52 plant)
                        ||!plant.canResumeDockPreparationR53(level,original,existing.ownerData()))
                    return new EvaLogisticsDirector.ActionResult(false,"取消后的原编队不在可续接的登乘位；请按实际停止位置回收，未重置整备。");
                preparation=existing.ownerData().copy();
                preparation.remove("ReleaseWhenReady");preparation.remove("ContinuousAutoLaunchR52");
                preparation.putUUID("ResumedPreparationTaskR53",stopped.task());
            }
            var result=pool.reserve(UUID.randomUUID(),original,route,nativeAccess);if(!result.accepted())return new EvaLogisticsDirector.ActionResult(false,result.reason());
            saved.put(new Job(result.state(),Phase.PREPARING,preparation,""));mirror(saved.job(variant));return new EvaLogisticsDirector.ActionResult(true,"原编队已登记；按真实机械反馈整备并转移到预备位。");
        }
        EvaLogisticsDirector.ActionResult launch(int variant,String intent)
        {
            var job=saved.job(variant);if(job==null)return new EvaLogisticsDirector.ActionResult(false,"请先登记原编队并完成实际整备。");
            var selected=directory.route(job.snapshot().route());if(job.ownerData().getString("ContinuousBrakeR52").equals("CANCEL"))return new EvaLogisticsDirector.ActionResult(false,"原编队正在实际减速取消，请先等待停稳。");
            if(selected!=null&&selected.continuousUpright()&&job.phase()==Phase.PREPARING)
            {
                String requested=intent==null?selected.id():defaults.get(variant+"/"+intent);if(!selected.id().equals(requested))return new EvaLogisticsDirector.ActionResult(false,"当前选定线路已预留；请在预备位选择已接通的支路。");
                var data=job.ownerData().copy();data.putBoolean("ContinuousAutoLaunchR52",true);if(!selected.phased())NervMechanicalTravelR52.extendContinuousR52(data,selected.id(),directory.fingerprint(),directory.routeLength(selected));saved.put(job.update(job.snapshot(),Phase.PREPARING,data,""));return new EvaLogisticsDirector.ActionResult(true,"发射已接续整备：备发先停稳，再完成真实换轨准备后发射。");
            }
            if(job.phase()!=Phase.READY)return new EvaLogisticsDirector.ActionResult(false,"原编队当前尚不能追加发射。");
            if(intent!=null&&!defaults.get(variant+"/"+intent).equals(job.snapshot().route()))
            {
                if(selected!=null&&selected.phased())
                {
                    var target=directory.route(defaults.get(variant+"/"+intent));if(target==null||target.bank()<=selected.bank()||job.snapshot().leg()>=target.legs().size())return new EvaLogisticsDirector.ActionResult(false,"该目标没有同向备发轨接续，请保留当前停稳位置。");for(int i=0;i<job.snapshot().leg();i++)if(!selected.legs().get(i).equals(target.legs().get(i)))return new EvaLogisticsDirector.ActionResult(false,"目标与已走过的实际轨道不一致。");
                    var data=job.ownerData().copy();data.putString("RetargetPreparedRouteR53",target.id());data.remove("ContinuousAutoLaunchR52");data.remove("ReleaseWhenReady");saved.put(job.update(job.snapshot(),Phase.PREPARING,data,"先将局部滑靴转回备发导向"));return new EvaLogisticsDirector.ActionResult(true,"换道已登记；原机停稳转回备发导向，再沿后门轨道到下一准备位。");
                }
                nativeAccess.ownerData(job.ownerData());var switched=pool.retargetPrepared(job.snapshot().task(),defaults.get(variant+"/"+intent),nativeAccess);
                if(!switched.accepted())return new EvaLogisticsDirector.ActionResult(false,"地下准备支路尚未实际接通或被占用，原机仍停在预备位。");
                var data=job.ownerData().copy();data.putBoolean("ReleaseWhenReady",true);if(directory.route(switched.state().route()).continuousUpright()){data.remove("ContinuousClockR52");data.remove("ContinuousDistanceR52");data.remove(NervLaunchPhasesR53.KEY);data.putBoolean("ContinuousCheckedStartR52",true);continuousPrimedR52.remove(job.snapshot().task());}saved.put(job.update(switched.state(),Phase.PREPARING,data,""));mirror(saved.job(variant));return new EvaLogisticsDirector.ActionResult(true,"原机沿真实后门轨道转至地下准备位，确认停稳后再部署。");
            }
            nativeAccess.ownerData(job.ownerData());if(!nativeAccess.sameOriginalAssembly(job.snapshot().original()))return new EvaLogisticsDirector.ActionResult(false,"原驾驶员或原栓连接已变化，未发射。");
            var launchData=job.ownerData().copy();if(selected!=null&&selected.continuousUpright()){launchData.putBoolean("ContinuousAutoLaunchR52",true);if(!selected.phased())NervMechanicalTravelR52.extendContinuousR52(launchData,selected.id(),directory.fingerprint(),directory.routeLength(selected));continuousPrimedR52.remove(job.snapshot().task());}
            saved.put(job.update(job.snapshot(),selected!=null&&selected.phased()?Phase.READY:Phase.DEPARTING,launchData,""));mirror(saved.job(variant));return new EvaLogisticsDirector.ActionResult(true,"发射已登记；全路实际预开验线通过后连续出动。");
        }
        EvaLogisticsDirector.ActionResult recover(int variant)
        {
            var job=saved.job(variant);
            if(job!=null&&job.phase()==Phase.PARKED&&!job.waiting().isEmpty())return resumeParkedServiceR53(level,variant);
            if(job!=null&&job.phase()==Phase.CANCELLED)return recoverCancelledContinuousR52(job);if(job==null||job.phase()!=Phase.DEPLOYED)return new EvaLogisticsDirector.ActionResult(false,"没有可接应的原出动编队记录。");
            var moving=level.getEntity(job.snapshot().original().eva());if(moving instanceof EvaUnit01Entity current&&NervAirTransportRuntimeR52.pending(level,current))return new EvaLogisticsDirector.ActionResult(false,"同一原机体仍由已保存的航空任务保持，不另抢地面路线。");
            var old=job.snapshot().original();var original=new Original(old.epoch(),old.variant(),old.eva(),old.plug(),old.pilot(),old.owner(),AutoSortieR32.missionToken(level,old.variant()),old.dimension());
            if(job.snapshot().stage()==Stage.COMPLETE)pool.releaseCompletion(job.snapshot().task(),old.owner());
            Entity actor=level.getEntity(original.eva());if(!(actor instanceof EvaUnit01Entity eva)||!((eva.getDeltaMovement().horizontalDistanceSqr()<.001)))return new EvaLogisticsDirector.ActionResult(false,"原机体尚未在实际支撑上停稳。");
            Kind kind=EntryPlugEjectionR48.originalFieldEjection(level,variant,eva,original.pilot())?Kind.HULL_ONLY_RECOVERY:Kind.OCCUPIED;
            var data=job.ownerData().copy();for(String oldPhase:List.of("Finish","FinishTicks","FinishRoot","FinishFeet","FinishPlugLocal","LastFinishTick","RouteR52","ContinuousClockR52","ContinuousDistanceR52","ContinuousRotationR52","ContinuousAutoLaunchR52","ContinuousCheckedStartR52"))data.remove(oldPhase);data.remove(NervLaunchPhasesR53.KEY);data.putBoolean("Returning",true);data.putString("AssemblyKindR52",kind.name());nativeAccess.ownerData(data);
            var binding=owner.originalBinding(level,original,data);if(binding==null)return unavailable();
            var region=owner.actualRecoveryRegion(level,original,data);var feet=owner.actualFootBearingCentre(level,original,data);if(region==null||feet==null)return unavailable();
            var route=pool.nearestRecovery(original,region,feet,(port,reverse)->owner.approachReachable(level,original,port,reverse,data),kind);
            if(route.isEmpty())return new EvaLogisticsDirector.ActionResult(false,"同一原机没有可达且空闲的对应回收口。");
            // The outlet lid is not a central receiving platform. Do not take
            // ground custody or open it beneath a body waiting for its rack.
            if(((!(owner instanceof NervAssemblyOwnerR52 actualOwner)
                    ||!actualOwner.groundReceiverBearingReadyR53(level,original,route.get().port(),kind,data))))
                return NervAirTransportRuntimeR52.requestRecoveryReceiver(level,variant,original.owner(),route.get().port());
            var result=pool.reserve(UUID.randomUUID(),original,route.get().id(),nativeAccess,kind);if(!result.accepted())return new EvaLogisticsDirector.ActionResult(false,result.reason());
            saved.put(new Job(result.state(),Phase.RETURNING,data,""));mirror(saved.job(variant));return new EvaLogisticsDirector.ActionResult(true,kind==Kind.HULL_ONLY_RECOVERY?"原无人机体沿真实逆向线路回库；已分离的原栓与驾驶员保持原位。":"原机体沿该入口绑定的真实逆向线路回库。");
        }
        private EvaLogisticsDirector.ActionResult recoverCancelledContinuousR52(Job job)
        {
            var snapshot=job.snapshot();var route=directory.route(snapshot.route());var stored=job.ownerData().getCompound("ContinuousClockR52");if(route==null||!route.continuousUpright()||stored.getDouble("SpeedMps")!=0)return new EvaLogisticsDirector.ActionResult(false,"等待已取消的原编队沿实轨减速停稳。");
            // Route-wide gate admission happens before the first distance
            // clock exists. Cancelling there must still run normal bay
            // service; a missing clock at a moved point remains invalid.
            boolean unstarted=stored.isEmpty()&&!route.recovery()&&snapshot.leg()==0&&snapshot.fraction()==0
                    &&job.ownerData().getString("Prepare").equals("READY")
                    &&job.ownerData().getDouble("ContinuousDistanceR52")==0;
            if(stored.isEmpty()&&(!unstarted||!owner.restoreOriginalPreparation(level,snapshot.original(),job.ownerData())))
                return new EvaLogisticsDirector.ActionResult(false,"原取消任务缺少行驶时钟，且未通过原登乘位整备实况检查。");
            NervMechanicalTravelR52.ContinuousClock originalStop=null;
            try{if(!unstarted){var resumeSpeed=route.phased()?NervLaunchPhasesR53.current(job.ownerData().copy(),snapshot.task(),directory,route,directory.routeDistance(route,snapshot.leg(),snapshot.fraction())).speed():route.motionProfile().launch();originalStop=NervMechanicalTravelR52.continuousClock(job.ownerData(),route.id(),directory.fingerprint(),directory.routeDistance(route,snapshot.leg(),snapshot.fraction()),directory.routeLength(route),stored.getDouble("ToMetres"),resumeSpeed.cruiseMps(),resumeSpeed.accelerationMps2(),resumeSpeed.decelerationMps2());if(originalStop.speed()!=0)return new EvaLogisticsDirector.ActionResult(false,"原取消任务尚未真正停稳。");}}
            catch(IllegalArgumentException|IllegalStateException mismatch){return new EvaLogisticsDirector.ActionResult(false,"原取消任务的实际位置与保存时钟不符，保持原UUID等待修复。");}
            var old=snapshot.original();var original=new Original(old.epoch(),old.variant(),old.eva(),old.plug(),old.pilot(),old.owner(),AutoSortieR32.missionToken(level,old.variant()),old.dimension());var data=job.ownerData().copy();data.putString("AssemblyKindR52",snapshot.kind().name());nativeAccess.ownerData(data);
            if(!owner.rebindStoppedContinuousR52(level,original,data))return new EvaLogisticsDirector.ActionResult(false,"原UUID编队的实际恒定姿态与停止承托尚未通过。");
            var result=pool.reclaimCancelledContinuousR52(snapshot,UUID.randomUUID(),original,nativeAccess);if(!result.accepted())return new EvaLogisticsDirector.ActionResult(false,result.reason());
            for(String field:List.of("Finish","FinishTicks","FinishRoot","FinishFeet","FinishPlugLocal","LastFinishTick","ContinuousClockR52","ContinuousBrakeR52","ContinuousResumeStopR52","ContinuousAutoLaunchR52","ReleaseWhenReady","RetargetPreparedRouteR53"))data.remove(field);data.remove(NervLaunchPhasesR53.KEY);data.putBoolean("Returning",true);data.putBoolean("ContinuousCheckedStartR52",true);data.putString("RouteR52",result.state().route());data.putDouble("ContinuousDistanceR52",directory.routeDistance(directory.route(result.state().route()),result.state().leg(),result.state().fraction()));
            data.putUUID("HeadReturnFromTaskR53",snapshot.task());data.putString("HeadReturnFromRouteR53",snapshot.route());
            data.remove("PreviousBankStopR53");var returnRoute=directory.route(result.state().route());double returnAt=data.getDouble("ContinuousDistanceR52");
            if(originalStop!=null&&returnRoute.phased()&&Math.abs(returnAt-directory.readyDistanceR53(returnRoute))<=1e-6&&Math.abs(originalStop.distance()-directory.readyDistanceR53(route))<=1e-6)
            {var receipt=new CompoundTag();receipt.putUUID("SourceTask",snapshot.task());receipt.putUUID("TargetTask",result.state().task());receipt.putString("SourceRoute",route.id());receipt.putString("TargetRoute",returnRoute.id());receipt.putString("Directory",directory.fingerprint());receipt.putDouble("TargetDistance",directory.readyDistanceR53(returnRoute));receipt.put("Clock",stored.copy());receipt.put("SourcePhase",job.ownerData().getCompound(NervLaunchPhasesR53.KEY).copy());data.put("PreviousBankStopR53",receipt);data.putDouble("ContinuousDistanceR52",directory.readyDistanceR53(returnRoute));}

            var returning=job.update(result.state(),Phase.RETURNING,data,"");saved.put(returning);
            if(result.state().stage()==Stage.COMPLETE)saved.put(returning.update(result.state(),Phase.FINISHING,data,""));
            mirror(saved.job(original.variant()));return new EvaLogisticsDirector.ActionResult(true,"同一原编队已重占原路；从实际停止点沿对应反向轨道回库。");
        }
        EvaLogisticsDirector.ActionResult cancel(int variant,UUID commander)
        {
            var job=saved.job(variant);if(job==null||!job.snapshot().original().owner().equals(commander))return new EvaLogisticsDirector.ActionResult(false,"原任务指挥者不符。");
            if(Set.of(Phase.DEPLOYED,Phase.PARKED,Phase.CANCELLED).contains(job.phase()))return new EvaLogisticsDirector.ActionResult(false,"原编队当前没有运行中的路线任务。");
            var selected=directory.route(job.snapshot().route());var clock=job.ownerData().getCompound("ContinuousClockR52");if(selected!=null&&selected.continuousUpright()&&clock.getDouble("SpeedMps")>0)
            {var data=job.ownerData().copy();NervMechanicalTravelR52.brakeContinuousR52(data,selected.id(),directory.fingerprint(),directory.routeLength(selected),"CANCEL");saved.put(job.update(job.snapshot(),job.phase(),data,"原路减速取消中"));return new EvaLogisticsDirector.ActionResult(true,"取消已接受：沿当前实轨减速，停稳后释放任务；原机、原栓和载架均保留。");}
            owner.brakeOriginalInPlace(level,job.snapshot().original(),job.ownerData());if(job.snapshot().stage()==Stage.COMPLETE)pool.releaseCompletion(job.snapshot().task(),commander);else pool.cancel(job.snapshot().task(),commander);
            var s=job.snapshot();var cancelled=new Snapshot(s.task(),s.original(),s.directoryFingerprint(),s.route(),s.leg(),s.fraction(),Stage.CANCELLED,"",s.kind());saved.put(job.update(cancelled,Phase.CANCELLED,job.ownerData(),"原位停止；未瞬移回库"));mirror(saved.job(variant));return new EvaLogisticsDirector.ActionResult(true,"已取消并原位停止，原机、原栓与驾驶员均保留。");
        }
        void mirror(Job job)
        {
            int v=job.snapshot().original().variant();var data=EvaFleetSavedData.get(level.getServer());var entry=data.entry(v).orElse(null);
            if(entry!=null&&entry.canonicalId().equals(job.snapshot().original().eva()))data.put(v,entry.withPhase(EvaFleetSavedData.Phase.valueOf(NervRouteRuntimeStateR52.legacyPhase(job)),job.snapshot().leg(),entry.carrier(),entry.lclLayers()));
        }
        void wait(Job job,String reason)
        {owner.brakeOriginalInPlace(level,job.snapshot().original(),job.ownerData());saved.put(job.update(job.snapshot(),job.phase(),job.ownerData(),reason));}
        private double readyDistanceR52(Route route)
        {double metres=0;for(String id:route.legs()){var leg=directory.leg(id);if(leg.from().equals(route.readyNode()))return metres;metres+=directory.legLength(leg);if(leg.to().equals(route.readyNode()))return metres;}throw new IllegalStateException("Declared ready node is not on actual route");}
        private List<DirectoryTrajectoryR52> boundedContinuousSpanR52(Route route,double from,double to,FootSupportFrameR52.Binding binding)
        {var paths=new ArrayList<DirectoryTrajectoryR52>();for(double at=from;at<to;){double end=Math.min(to,at+16);paths.addAll(directory.routeSlices(route,at,end,binding));if(paths.size()>2048)throw new IllegalArgumentException("Bounded actual braking/lookahead span required");at=end;}return List.copyOf(paths);}
        private NervRouteNativeR52.CheckedContinuousTraversalR52 clearContinuousSpanR52(Original o,Route route,double from,double to,FootSupportFrameR52.Binding binding,CompoundTag data)
        {var paths=boundedContinuousSpanR52(route,from,to,binding);return checkedContinuousCarrierProofR53(o,route,paths,data);}
        private boolean checkedContinuousCarrierR53(Original original,Route route,List<DirectoryTrajectoryR52> paths,CompoundTag data)
        {
            if(paths.isEmpty())return false;
            var proof=nativeAccess.checkContinuousR52(original,route,paths,true);
            return proof!=null&&owner.preflightCheckedContinuousCarrierR53(level,proof,data);
        }
        private NervRouteNativeR52.CheckedContinuousTraversalR52 checkedContinuousCarrierProofR53(Original original,Route route,List<DirectoryTrajectoryR52> paths,CompoundTag data)
        {
            if(paths.isEmpty())return null;
            var proof=nativeAccess.checkContinuousR52(original,route,paths);
            return proof!=null&&owner.preflightCheckedContinuousCarrierR53(level,proof,data)?proof:null;
        }
        private void finishContinuousCancelR52(Job job,Snapshot snapshot,CompoundTag data)
        {
            owner.brakeOriginalInPlace(level,snapshot.original(),data);if(snapshot.stage()==Stage.COMPLETE)pool.releaseCompletion(snapshot.task(),snapshot.original().owner());else pool.cancel(snapshot.task(),snapshot.original().owner());continuousPrimedR52.remove(snapshot.task());var cancelled=new Snapshot(snapshot.task(),snapshot.original(),snapshot.directoryFingerprint(),snapshot.route(),snapshot.leg(),snapshot.fraction(),Stage.CANCELLED,"",snapshot.kind());saved.put(job.update(cancelled,Phase.CANCELLED,data,"实际原路减速停止；可从该点反向回库"));mirror(saved.job(snapshot.original().variant()));
        }
        private void continuousWaitR52(Job job,CompoundTag data,String reason)
        {
            var row=data.getCompound("ContinuousClockR52");if(row.getDouble("SpeedMps")>0){var route=directory.route(job.snapshot().route());NervMechanicalTravelR52.brakeContinuousR52(data,route.id(),directory.fingerprint(),directory.routeLength(route),"BLOCKED");}
            else {continuousPrimedR52.remove(job.snapshot().task());owner.brakeOriginalInPlace(level,job.snapshot().original(),data);}
            saved.put(job.update(job.snapshot(),job.phase(),data,reason));
        }
        private void holdContinuousStepR53(Job job,Route route,CompoundTag data,double at,double intended,
                                           double cruise,double acceleration,double deceleration,String reason)
        {
            // The rejected step has not moved anything. Retain the accepted frame,
            // then restart its analytic clock instead of inventing a future stop.
            owner.brakeOriginalInPlace(level,job.snapshot().original(),data);
            if(at<intended)NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),directory.routeLength(route),
                    new NervMechanicalTravelR52.ContinuousClock(new NervMechanicalTravelR52.ContinuousProfile(at,intended,cruise,acceleration,deceleration),0));
            data.putDouble("ContinuousDistanceR52",at);
            if(data.getString("ContinuousBrakeR52").equals("CANCEL"))
            {finishContinuousCancelR52(job,job.snapshot(),data);return;}
            data.remove("ContinuousBrakeR52");data.remove("ContinuousResumeStopR52");
            continuousPrimedR52.remove(job.snapshot().task());
            saved.put(job.update(job.snapshot(),job.phase(),data,reason));
        }
        private void tickContinuousR52(Job job,Route route)
        {
            var selectedMode=NervTraversalPolicyR53.mode(level);
            if(selectedMode!=traversalModeR53)
            {
                continuousPrimedR52.clear();stoppedPreflightRetriesR53.clear();
                traversalModeR53=selectedMode;
            }
            var snapshot=job.snapshot();var data=job.ownerData().copy();double total=directory.routeLength(route),at=directory.routeDistance(route,snapshot.leg(),snapshot.fraction());var stored=data.getCompound("ContinuousClockR52");if(!stored.isEmpty()&&stored.getString("Route").equals(route.id())&&stored.getString("Directory").equals(directory.fingerprint())&&Math.abs(at-stored.getDouble("DistanceMetres"))<=1e-6)at=stored.getDouble("DistanceMetres");data.putDouble("ContinuousDistanceR52",at);nativeAccess.ownerData(data);
            boolean finalCommitStarted=false;
            try
            {
                NervLaunchPhasesR53.Run phased=route.phased()?NervLaunchPhasesR53.current(data,snapshot.task(),directory,route,at):null;
                if(phased!=null&&data.contains("RetargetPreparedRouteR53"))
                {
                    NervLaunchPhasesR53.verifyStoppedBank(data,snapshot.task(),directory,route,at);
                    if(!owner.prepareContinuousRouteR52(level,snapshot.original(),route,data)||!owner.prepareBankForRetargetR53(level,snapshot.original(),route,snapshot.task(),data)){saved.put(job.update(snapshot,Phase.PREPARING,data,"等待真实滑靴转回备发导向"));return;}
                    nativeAccess.ownerData(data);var switched=pool.retargetPrepared(snapshot.task(),data.getString("RetargetPreparedRouteR53"),nativeAccess);
                    if(!switched.accepted()){saved.put(job.update(snapshot,Phase.PREPARING,data,"原位停稳等待目标备发轨预留："+switched.reason()));return;}
                    for(String field:List.of("RetargetPreparedRouteR53","ContinuousClockR52","ContinuousDistanceR52",NervLaunchPhasesR53.KEY,"PreviousBankStopR53","HeadReturnFromTaskR53","HeadReturnFromRouteR53"))data.remove(field);data.putBoolean("ContinuousCheckedStartR52",true);data.putBoolean("ReleaseWhenReady",true);data.putString("RouteR52",switched.state().route());continuousPrimedR52.remove(snapshot.task());saved.put(job.update(switched.state(),Phase.PREPARING,data,""));mirror(saved.job(snapshot.original().variant()));return;
                }

                if(phased!=null&&phased.bankStop()&&at==phased.stop()&&!data.contains("ContinuousBrakeR52"))
                {
                    if(!owner.prepareContinuousRouteR52(level,snapshot.original(),route,data)||!owner.prepareBankHeadsR53(level,snapshot.original(),route,snapshot.task(),data))
                    {saved.put(job.update(snapshot,route.recovery()?Phase.RETURNING:Phase.PREPARING,data,"等待停稳后的真实滑靴换轨与承托锁定"));return;}
                    boolean requested=route.recovery()||data.getBoolean("ContinuousAutoLaunchR52")||data.getBoolean("ReleaseWhenReady");
                    if(!requested){saved.put(job.update(snapshot,Phase.READY,data,""));return;}
                    if(!route.recovery()&&!FacilityRouteAudioR53.countdown(level,job,data)){saved.put(job.update(snapshot,Phase.READY,data,"发射倒计时"));return;}
                    phased=NervLaunchPhasesR53.crossStoppedBank(data,snapshot.task(),directory,route,at);
                    continuousPrimedR52.remove(snapshot.task());stored=data.getCompound("ContinuousClockR52");
                    job=job.update(snapshot,route.recovery()?Phase.RETURNING:Phase.DEPARTING,data,"");saved.put(job);
                }
                boolean launch=phased!=null?phased.launch():route.recovery()||job.phase()==Phase.DEPARTING||data.getBoolean("ContinuousAutoLaunchR52")||data.getBoolean("ReleaseWhenReady");
                double intended=phased!=null?phased.stop():launch?total:readyDistanceR52(route),stop=data.contains("ContinuousBrakeR52")?stored.getDouble("ToMetres"):intended;
                var speed=phased!=null?phased.speed():route.motionProfile().launch();
                if(job.phase()==Phase.READY&&!launch&&phased==null)return;
                boolean ready=owner.prepareContinuousRouteR52(level,snapshot.original(),route,data);
                if(!ready&&!NervTraversalPolicyR53.strict(level)&&!stored.isEmpty())
                {holdContinuousStepR53(job,route,data,at,intended,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2(),"等待前方区段的舱门、支承与加载就绪");return;}
                if(!ready&&stored.getDouble("SpeedMps")<=0){continuousWaitR52(job,data,NervTraversalPolicyR53.strict(level)?"等待全路真实门、地基、导轨与加载就绪":"等待前方区段的舱门、支承与加载就绪");return;}
                if(!ready&&!data.contains("ContinuousBrakeR52")){NervMechanicalTravelR52.brakeContinuousR52(data,route.id(),directory.fingerprint(),total,"BLOCKED");stored=data.getCompound("ContinuousClockR52");stop=stored.getDouble("ToMetres");}
                if(at==stop)
                {
                    if(data.getString("ContinuousBrakeR52").equals("CANCEL")){finishContinuousCancelR52(job,snapshot,data);return;}
                    if(data.getString("ContinuousBrakeR52").equals("BLOCKED")&&at<intended)
                    {var binding=owner.originalBinding(level,snapshot.original(),data);var whole=ready&&NervTraversalPolicyR53.strict(level)?(phased!=null?boundedContinuousSpanR52(route,at,intended,binding):owner.continuousRoutePathsR52(level,snapshot.original(),route,data)):List.<DirectoryTrajectoryR52>of();if(!ready||binding==null||(NervTraversalPolicyR53.strict(level)&&!checkedContinuousCarrierR53(snapshot.original(),route,whole,data))){continuousWaitR52(job,data,NervTraversalPolicyR53.strict(level)?"已沿实轨制动停稳，等待全路重新验线":"已沿实轨制动停稳，等待前方区段恢复");return;}data.remove("ContinuousBrakeR52");data.remove("ContinuousResumeStopR52");NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,new NervMechanicalTravelR52.ContinuousClock(new NervMechanicalTravelR52.ContinuousProfile(at,intended,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2()),0));stored=data.getCompound("ContinuousClockR52");stop=intended;continuousPrimedR52.add(snapshot.task());}
                    else {data.remove("ContinuousBrakeR52");data.remove("ContinuousResumeStopR52");var phase=at==total?Phase.FINISHING:route.recovery()?Phase.RETURNING:Phase.READY;saved.put(job.update(snapshot,phase,data,""));mirror(saved.job(snapshot.original().variant()));return;}
                }
                if(at>stop)throw new IllegalStateException("Saved original passed its explicit prepared/braking stop");
                var binding=owner.originalBinding(level,snapshot.original(),data);if(binding==null){continuousWaitR52(job,data,"实际恒定双脚与栓绑定缺失");return;}
                if(NervTraversalPolicyR53.strict(level)&&!continuousPrimedR52.contains(snapshot.task()))
                {
                    boolean stopped=stored.getDouble("SpeedMps")<=0&&!data.contains("ContinuousBrakeR52");
                    if(stopped&&deferStoppedPreflightR53(job,route,at,intended))return;
                    var whole=data.contains("ContinuousBrakeR52")?boundedContinuousSpanR52(route,at,stop,binding):(phased!=null?boundedContinuousSpanR52(route,at,intended,binding):owner.continuousRoutePathsR52(level,snapshot.original(),route,data));
                    if(!checkedContinuousCarrierR53(snapshot.original(),route,whole,data))
                    {
                        if(!data.contains("ContinuousBrakeR52"))
                        {
                            if(stopped)retryStoppedPreflightR53(job,route,at,intended);
                            continuousWaitR52(job,data,"发车/重载前全路或实际制动范围检查未通过");return;
                        }
                    }
                    else
                    {
                        stoppedPreflightRetriesR53.remove(snapshot.original().variant());
                        continuousPrimedR52.add(snapshot.task());
                    }
                }
                if(phased==null&&launch&&!data.contains("ContinuousBrakeR52"))NervMechanicalTravelR52.extendContinuousR52(data,route.id(),directory.fingerprint(),total);
                var clock=NervMechanicalTravelR52.continuousClock(data,route.id(),directory.fingerprint(),at,total,stop,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2());var next=clock.next();NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,clock);
                NervRouteNativeR52.CheckedContinuousTraversalR52 horizonProof=null;
                if(NervTraversalPolicyR53.strict(level)&&!data.contains("ContinuousBrakeR52"))
                {double horizon=Math.min(intended,next.distance()+NervMechanicalTravelR52.brakingDistanceR52(next.speed(),speed.decelerationMps2()));horizonProof=clearContinuousSpanR52(snapshot.original(),route,at,horizon,binding,data);if(horizonProof==null){if(clock.speed()<=0){continuousWaitR52(job,data,"起步前实际制动安全范围被占用");return;}NervMechanicalTravelR52.brakeContinuousR52(data,route.id(),directory.fingerprint(),total,"BLOCKED");stop=data.getCompound("ContinuousClockR52").getDouble("ToMetres");clock=NervMechanicalTravelR52.continuousClock(data,route.id(),directory.fingerprint(),at,total,stop,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2());next=clock.next();}}
                var paths=directory.routeSlices(route,at,next.distance(),binding);
                var proof=horizonProof==null?null:horizonProof.checkedPrefixR53(paths);
                if(proof==null)proof=nativeAccess.checkContinuousR52(snapshot.original(),route,paths);
                if(proof==null||!pool.canCommitContinuousR52(snapshot.task(),proof))
                {if(!NervTraversalPolicyR53.strict(level)){holdContinuousStepR53(job,route,data,at,intended,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2(),"本步真实碰撞、支撑或预留受阻，原位等待后继续");}else if(clock.speed()>0){owner.brakeOriginalInPlace(level,snapshot.original(),data);saved.put(job.update(snapshot,job.phase(),data,"实际障碍已侵入本步可验证制动范围，物理碰撞保持"));saved.faultR52("Unexpected obstacle invalidated the actual braking step at task "+snapshot.task()+"; no unsafe movement or synthetic zero-speed receipt");}else continuousWaitR52(job,data,"连续子曲线真实碰撞、支撑或全路预留检查未通过");return;}
                var contacts=List.<NervLaunchFeedbackR53.Contact>of();
                if(phased!=null&&phased.launch())
                {
                    var last=paths.get(paths.size()-1);var tangent=NervOuterCarrierGuideR52.direction(last,1);
                    try{contacts=NervOuterCarrierGuideR52.actualContactPointsR53(last.sample(1).evaRoot(),tangent).stream().map(point->new NervLaunchFeedbackR53.Contact(point,tangent)).toList();}
                    catch(java.io.IOException missing){continuousWaitR52(job,data,"实际导轨接触源未加载");return;}
                }
                finalCommitStarted=true;if(!owner.applyCheckedContinuousR52(level,proof,data))
                {finalCommitStarted=false;if(!NervTraversalPolicyR53.strict(level))holdContinuousStepR53(job,route,data,at,intended,speed.cruiseMps(),speed.accelerationMps2(),speed.decelerationMps2(),"本步机架、背轨或承托受阻，原位等待后继续");else continuousWaitR52(job,data,"同 tick 整组唯一最终提交未通过");return;}
                var result=pool.advanceCommittedContinuousR52(snapshot.task(),proof);if(!result.accepted())throw new IllegalStateException("Moved checked assembly failed its retained metadata commit: "+result.reason());
                NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,next);data.putDouble("ContinuousDistanceR52",next.distance());data.remove("ContinuousCheckedStartR52");
                if(phased!=null&&phased.launch())
                {
                    boolean first=NervLaunchPhasesR53.firstLaunchCommit(data,phased,at,next.distance(),readyDistanceR52(route));
                    if(first&&level.getEntity(snapshot.original().eva()) instanceof EvaUnit01Entity launched)FacilityPaR31.announce(level,launched.position().add(0,52,0),"pa_launch");
                    NervLaunchFeedbackR53.afterCommittedMotion(level,data,snapshot.task(),true,first,(next.distance()-at)*20,contacts);
                }
                if(next.complete()&&data.getString("ContinuousBrakeR52").equals("CANCEL")){finishContinuousCancelR52(job,result.state(),data);return;}
                var phase=launch&&!route.recovery()?Phase.DEPARTING:job.phase();if(next.complete()&&data.getString("ContinuousBrakeR52").equals("BLOCKED")){continuousPrimedR52.remove(snapshot.task());owner.brakeOriginalInPlace(level,snapshot.original(),data);}
                else if(result.state().stage()==Stage.COMPLETE)phase=Phase.FINISHING;else if(next.complete()){phase=route.recovery()?Phase.RETURNING:phased!=null?Phase.PREPARING:Phase.READY;continuousPrimedR52.remove(snapshot.task());}
                saved.put(job.update(result.state(),phase,data,""));mirror(saved.job(snapshot.original().variant()));
            }
            catch(IllegalArgumentException|IllegalStateException invalid){if(finalCommitStarted){owner.brakeOriginalInPlace(level,snapshot.original(),data);saved.faultR52("Continuous final commit/readback fault at task "+snapshot.task()+": "+invalid.getMessage());}else continuousWaitR52(job,data,"连续路线保存/真实提交不一致："+invalid.getMessage());}
        }
        private boolean recoveryHeldR53(String reason)
        {
            if(!reason.equals(CONTINUOUS_RECOVERY_DIAGNOSTICS_R53.put(level,reason)))
                com.projectseele.ProjectSeele.LOGGER.warn("R53 continuous commit recovery held: {}",reason);
            return false;
        }
        private boolean recoverContinuousCommitR53()
        {
            var job=saved.interruptedContinuousCommitR53();if(job==null)return false;
            String fault=saved.fault();var snapshot=job.snapshot();var original=snapshot.original();
            String prefix="task="+snapshot.task()+" ";
            try
            {
                if(LIVE.get(level)!=this||saved.epoch()!=directory.epoch()||!saved.fingerprint().equals(directory.fingerprint())
                        ||original.epoch()!=directory.epoch()||!snapshot.directoryFingerprint().equals(directory.fingerprint())
                        ||!owner.fullRigidFramesReady(level,directory))return recoveryHeldR53(prefix+"owner/epoch/directory not restored");
                var route=directory.route(snapshot.route());
                if(route==null||!route.continuousUpright()||Set.of(Stage.COMPLETE,Stage.CANCELLED).contains(snapshot.stage()))
                    return recoveryHeldR53(prefix+"saved task is not an interrupted continuous step");
                var data=job.ownerData().copy();nativeAccess.ownerData(data);
                if(!(level.getEntity(original.eva()) instanceof EvaUnit01Entity eva)||!EvaMechanicalFrameR52.active(eva)
                        ||EvaMechanicalFrameR52.epoch(eva)!=original.epoch()||EvaMechanicalFrameR52.kind(eva)!=snapshot.kind())
                    return recoveryHeldR53(prefix+"original mechanical EVA/epoch/kind unavailable");
                if(!nativeAccess.sameAssembly(original,snapshot.kind()))return recoveryHeldR53(prefix+"original membership/boarding receipt not restored");
                var encoded=new CompoundTag();EvaMechanicalFrameR52.save(eva,encoded);
                var sample=encoded.getCompound("R52MechanicalSample");var window=sample.getCompound("ContinuousWindowR52");
                var stored=data.getCompound("ContinuousClockR52");
                if(window.isEmpty()||stored.isEmpty()||!window.getCompound("Clock").equals(stored)
                        ||window.getLong("Sequence")<=0||window.getLong("Sequence")!=sample.getLong("ContinuousSequenceR52"))
                    return recoveryHeldR53(prefix+"physical window sequence/old clock differs from saved job");
                if(!stored.getString("Route").equals(route.id())||!stored.getString("Directory").equals(directory.fingerprint())
                        ||stored.getDouble("TotalMetres")!=directory.routeLength(route))
                    return recoveryHeldR53(prefix+"old clock route/profile provenance differs");
                var clock=new NervMechanicalTravelR52.ContinuousClock(new NervMechanicalTravelR52.ContinuousProfile(
                        stored.getDouble("FromMetres"),stored.getDouble("ToMetres"),stored.getDouble("CruiseMps"),
                        stored.getDouble("AccelerationMps2"),stored.getDouble("DecelerationMps2"),stored.getDouble("InitialMps")),stored.getLong("Ticks"));
                double at=clock.distance(),total=directory.routeLength(route);var next=clock.next();
                if(clock.complete()||next.distance()<=at||Math.abs(at-directory.routeDistance(route,snapshot.leg(),snapshot.fraction()))>1e-6
                        ||Math.abs(at-stored.getDouble("DistanceMetres"))>1e-6||Math.abs(clock.speed()-stored.getDouble("SpeedMps"))>1e-9
                        ||!data.contains("ContinuousDistanceR52")||Math.abs(at-data.getDouble("ContinuousDistanceR52"))>1e-6)
                    return recoveryHeldR53(prefix+"old snapshot/distance/speed is not the window's unique prior tick");
                var binding=EvaMechanicalFrameR52.measuredBinding(eva,original);
                if(binding==null)return recoveryHeldR53(prefix+"original frozen bearing binding unavailable");
                var paths=directory.routeSlices(route,at,next.distance(),binding);
                if(paths.isEmpty()||!DirectoryTrajectoryR52.encodePortableR52(paths).equals(window.getCompound("Path")))
                    return recoveryHeldR53(prefix+"portable window differs from the unique next route slice");
                var portable=DirectoryTrajectoryR52.decodePortableR52(window.getCompound("Path"));
                var from=paths.get(0).sample(0);var last=paths.get(paths.size()-1);var to=last.sample(1);
                if(Math.abs(portable.lengthMetres()-(next.distance()-at))>1e-6
                        ||!NervAirTransportManifestR52.same(portable.sample(0),from.evaRoot())
                        ||!NervAirTransportManifestR52.same(portable.sample(portable.lengthMetres()),to.evaRoot())
                        ||!NervAirTransportManifestR52.same(NervAircraftFrameR52.decodeRigid(sample.getCompound("Current")),to.evaRoot())
                        ||!sample.getBoolean("ContinuousHeldR52")&&!NervAirTransportManifestR52.same(NervAircraftFrameR52.decodeRigid(sample.getCompound("Previous")),from.evaRoot())
                        ||!owner.actualFrameMatches(level,original,to,data)||eva.position().distanceToSqr(to.evaRoot().translation())>1e-10)
                    return recoveryHeldR53(prefix+"actual EVA/plug endpoint or portable from/to does not match");
                var carrier=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);
                if(carrier==null||carrier!=NervOriginalCarrierR52.controller(level,original)||!NervOriginalCarrierR52.attachedTo(carrier,eva)||carrier.getUnitVariant()!=original.variant())
                    return recoveryHeldR53(prefix+"original attached carrier unavailable");
                var steel=carrier.originalCarrierStateR52();var steelRoot=NervAircraftFrameR52.decodeRigid(steel.getCompound("Current"));
                if(steel.getLong("Epoch")!=original.epoch()||!steel.getString("Directory").equals(directory.fingerprint())
                        ||NervOriginalCarrierR52.progress(carrier,1)!=1||carrier.position().distanceToSqr(steelRoot.translation())>1e-10
                        ||!NervAirTransportManifestR52.same(CarrierMountProfileR53.read(carrier,1).payloadFrame(steelRoot),to.evaRoot()))
                    return recoveryHeldR53(prefix+"original carrier has not committed the same endpoint");
                if(snapshot.kind()==Kind.OCCUPIED)
                {
                    if(!(level.getEntity(original.plug()) instanceof EntryPlugCarrierEntity plug)
                            ||plug.getVehicle()!=eva||eva.getLockedEntryPlug()!=plug||!plug.isLockedToEva())
                        return recoveryHeldR53(prefix+"original locked capsule relation unavailable");
                    var pilot=level.getEntity(original.pilot());
                    if(pilot==null||pilot.getVehicle()!=plug||plug.getFirstPassenger()!=pilot)
                        return recoveryHeldR53(prefix+"original rider relation unavailable");
                    var seat=plug.transformPlugMarker(EntryPlugKinematics.PILOT_SEAT_P).add(0,-pilot.getBbHeight()*.5,0);
                    if(pilot.position().distanceToSqr(seat)>1e-10)return recoveryHeldR53(prefix+"original rider has not reached the committed capsule seat");
                }
                int index=route.legs().indexOf(last.leg().id());double fraction=last.toFraction();Stage stage=Stage.MOVING;
                if(fraction==1){if(index+1==route.legs().size())stage=Stage.COMPLETE;else{index++;fraction=0;}}
                var target=new Snapshot(snapshot.task(),original,snapshot.directoryFingerprint(),snapshot.route(),index,fraction,stage,"",snapshot.kind());
                var phased=route.phased()?NervLaunchPhasesR53.current(data,snapshot.task(),directory,route,at):null;
                boolean launch=phased!=null?phased.launch():route.recovery()||job.phase()==Phase.DEPARTING||data.getBoolean("ContinuousAutoLaunchR52")||data.getBoolean("ReleaseWhenReady");
                NervMechanicalTravelR52.rememberContinuous(data,route.id(),directory.fingerprint(),total,next);
                data.putDouble("ContinuousDistanceR52",next.distance());data.remove("ContinuousCheckedStartR52");
                if(phased!=null&&phased.launch())NervLaunchPhasesR53.firstLaunchCommit(data,phased,at,next.distance(),readyDistanceR52(route));
                var phase=launch&&!route.recovery()?Phase.DEPARTING:job.phase();
                if(!(next.complete()&&Set.of("CANCEL","BLOCKED").contains(data.getString("ContinuousBrakeR52"))))
                {if(stage==Stage.COMPLETE)phase=Phase.FINISHING;else if(next.complete())phase=route.recovery()?Phase.RETURNING:phased!=null?Phase.PREPARING:Phase.READY;}
                var proof=new RecoveredContinuousStepR53(level,snapshot,target,paths);
                var result=new Result[1];var recovered=job.update(target,phase,data,"");
                boolean accepted=saved.recoverContinuousCommitR53(fault,job,recovered,()->
                {result[0]=pool.recoverCommittedContinuousR53(proof);return result[0].accepted();});
                if(!accepted)return recoveryHeldR53(prefix+(result[0]==null?"saved fault/job changed before commit":result[0].reason()));
                continuousPrimedR52.remove(snapshot.task());
                CONTINUOUS_RECOVERY_DIAGNOSTICS_R53.put(level,prefix+"completed metadata for observed tick "+clock.ticks()+" -> "+next.ticks());
                com.projectseele.ProjectSeele.LOGGER.info("R53 continuous commit recovery: {}",continuousRecoveryDiagnosticR53(level));
                return true;
            }
            catch(RuntimeException invalid){return recoveryHeldR53(prefix+invalid.getClass().getSimpleName()+": "+invalid.getMessage());}
        }
        void tick()
        {
            if(!saved.fault().isEmpty())return;for(var job:saved.jobs())
            {
                FacilityRouteAudioR53.tick(level,job);
                if(job.phase()==Phase.PARKED)
                {
                    if(!parkedReadbacksR53.contains(job.snapshot().task())&&owner instanceof NervAssemblyOwnerR52 plant)
                    {
                        UUID task=job.snapshot().task();long now=level.getGameTime();
                        Long began=parkedReadbackStartedR54.putIfAbsent(task,now);
                        // One short cold-read ticket, never permanent residency for parked machines.
                        if(began==null)plant.retainOriginalBayBlocksR54(level,job.snapshot().original());
                        String hold=plant.parkedServiceHoldR53(level,job.snapshot().original());
                        if(!hold.equals(job.waiting()))saved.put(job.update(job.snapshot(),job.phase(),job.ownerData(),hold));
                        if(plant.parkedBayBlocksLoadedR54(level,job.snapshot().original())
                                ||began!=null&&now-began>=100)
                        {parkedReadbacksR53.add(task);parkedReadbackStartedR54.remove(task);}
                    }
                    continue;
                }
                parkedReadbacksR53.remove(job.snapshot().task());
                parkedReadbackStartedR54.remove(job.snapshot().task());
                if(Set.of(Phase.DEPLOYED,Phase.CANCELLED).contains(job.phase()))continue;var snapshot=job.snapshot();var route=directory.route(snapshot.route());nativeAccess.ownerData(job.ownerData());
                if(owner instanceof NervAssemblyOwnerR52 plant)plant.retainOriginalBayBlocksR54(level,snapshot.original());
                if(route==null){wait(job,"Root 路线或保存版本已变化");continue;}
                if(job.phase()==Phase.FINISHING)
                {
                    if(pool.query(snapshot.task())==null)
                    {
                        Kind finishingKind=snapshot.kind();NativeAccess finishing=new NativeAccess(){public boolean sameOriginalAssembly(Original o){return nativeAccess.originalIdentitySet(o);}public boolean canTraverse(Original o,Route r,Leg l,double a,double b){return false;}public boolean canRestore(Original o,Route r,int i,double f){return nativeAccess.finishingPlacementClear(o,r,i,f);}public boolean sameAssembly(Original o,Kind k){return k==finishingKind&&nativeAccess.originalIdentitySet(o);}public boolean canRestoreAssembly(Original o,Kind k,Route r,int i,double f){return k==finishingKind&&nativeAccess.finishingPlacementClear(o,r,i,f);}};
                        var restored=pool.restoreCompletion(snapshot,finishing);
                        if(!restored.accepted()){wait(job,"等待整组收尾状态/几何恢复验证");continue;}
                        snapshot=restored.state();job=job.update(snapshot,job.phase(),job.ownerData(),"");saved.put(job);
                    }
                    var completion=pool.query(snapshot.task());
                    if(completion==null||completion.stage()!=Stage.COMPLETE){wait(job,"等待已验证的路线终点完成凭据，保留原路线占用");continue;}
                    snapshot=completion;job=job.update(snapshot,job.phase(),job.ownerData(),"");saved.put(job);
                    if(owner.finishOriginal(level,snapshot.original(),route.recovery(),job.ownerData()))
                    {
                        if(!pool.releaseCompletion(snapshot.task(),snapshot.original().owner())){wait(job,"真实机械收尾完成，但原路线占用释放尚未确认");continue;}
                        saved.put(job.update(snapshot,route.recovery()?Phase.PARKED:Phase.DEPLOYED,job.ownerData(),""));
                        mirror(saved.job(snapshot.original().variant()));
                        // A direct radio sortie has no campaign return order.
                        // Hand its original NPC back to the existing walking
                        // route only after the capsule and bridge are restored.
                        if(route.recovery() && level.getEntity(snapshot.original().plug())
                                instanceof com.projectseele.entity.EntryPlugCarrierEntity capsule
                                && capsule.getFirstPassenger() instanceof com.projectseele.entity.TrainingPilotEntity pilot
                                && pilot.getUUID().equals(snapshot.original().pilot()))
                            TrainingPilotDirector.stop(level,snapshot.original().variant());
                    }
                    else wait(job,"等待原编队真实机械收尾");continue;
                }
                if(job.phase()==Phase.PREPARING&&snapshot.leg()==0&&snapshot.fraction()==0&&job.ownerData().getBoolean("Prepared")&&owner.requiresPreparationRecoveryR53(level,snapshot.original(),job.ownerData()))
                {
                    // Retain identity, leases and clocks; an invalid prepared
                    // certificate must use physical preparation restoration.
                    var data=job.ownerData().copy();data.remove("Prepared");
                    job=job.update(snapshot,Phase.PREPARING,data,"");saved.put(job);nativeAccess.ownerData(data);
                }
                if(pool.query(snapshot.task())==null)
                {
                    if(route.recovery()&&snapshot.leg()==0&&snapshot.fraction()==0&&job.ownerData().getBoolean("ReceiverAlignmentR53"))
                    {
                        if(!owner.prepareContinuousRouteR52(level,snapshot.original(),route,job.ownerData()))
                        {wait(job,"继续出口接应架姿态调整");continue;}
                    }
                    NativeAccess restoreAccess=nativeAccess;
                    if(job.phase()==Phase.PREPARING&&!job.ownerData().getBoolean("Prepared"))
                    {
                        CompoundTag preparationData=job.ownerData();
                        restoreAccess=new NativeAccess(){public boolean sameOriginalAssembly(Original o){return nativeAccess.sameOriginalAssembly(o);}public boolean canTraverse(Original o,Route r,Leg l,double a,double b){return nativeAccess.canTraverse(o,r,l,a,b);}public boolean canRestore(Original o,Route r,int i,double f){return i==0&&f==0&&owner.restoreOriginalPreparation(level,o,preparationData);}};
                    }
                    var restored=pool.restore(snapshot,restoreAccess);if(!restored.accepted()){wait(job,"等待原编队实际位置/几何恢复验证");continue;}snapshot=restored.state();job=job.update(snapshot,job.phase(),job.ownerData(),"");saved.put(job);
                }
                if(job.phase()==Phase.READY&&!route.continuousUpright())
                {if(job.ownerData().getBoolean("ReleaseWhenReady")){var data=job.ownerData().copy();data.remove("ReleaseWhenReady");saved.put(job.update(snapshot,Phase.DEPARTING,data,""));}continue;}
                if(job.phase()==Phase.PREPARING&&!job.ownerData().getBoolean("Prepared"))
                {
                    var data=job.ownerData().copy();var result=owner.prepareOriginal(level,snapshot.original(),data);
                    if(result!=NervRouteNativeR52.Preparation.READY){saved.put(job.update(snapshot,Phase.PREPARING,data,"等待原机械、原栓和驾驶员实际整备"));continue;}
                    if(!EntryPlugDirector.hasLaunchLock(level,snapshot.original().variant(),(EvaUnit01Entity)level.getEntity(snapshot.original().eva()))||owner.originalBinding(level,snapshot.original(),data)==null){wait(job,"原插入栓/双脚承托姿态尚未确认");continue;}
                    data.putBoolean("Prepared",true);job=job.update(snapshot,Phase.PREPARING,data,"");saved.put(job);nativeAccess.ownerData(data);
                }
                if(route.continuousUpright()){tickContinuousR52(job,route);continue;}
                if(job.phase()==Phase.PREPARING&&snapshot.leg()==route.bank()&&snapshot.fraction()==0)
                {saved.put(job.update(snapshot,Phase.READY,job.ownerData(),""));mirror(saved.job(snapshot.original().variant()));continue;}
                var leg=directory.leg(route.legs().get(snapshot.leg()));int clock=NervMechanicalTravelR52.restoredClock(job.ownerData(),route.id(),snapshot.leg(),leg.ticks(),snapshot.fraction());if(clock<0||clock>=leg.ticks()){wait(job,"真实路段时钟与已保存几何进度不一致，保持原位");continue;}double next=NervMechanicalTravelR52.fraction(clock+1,leg.ticks());
                if(!owner.prepareLeg(level,snapshot.original(),route,leg,job.ownerData())){wait(job,"等待对应真实门与承载机构就绪");continue;}
                if(!nativeAccess.canTraverse(snapshot.original(),route,leg,snapshot.fraction(),next)){wait(job,"真实轨道/门/支撑/整组碰撞检查未通过");continue;}
                var binding=owner.originalBinding(level,snapshot.original(),job.ownerData());var from=directory.sample(leg,snapshot.fraction(),binding);var to=directory.sample(leg,next,binding);
                if(!owner.applyVerifiedWholeAssembly(level,snapshot.original(),from,to,job.ownerData())||!nativeAccess.canRestore(snapshot.original(),route,snapshot.leg(),next)){wait(job,"整组刚体运动或真实到位确认未通过");continue;}
                Original acceptedOriginal=snapshot.original();Kind acceptedKind=snapshot.kind();double before=snapshot.fraction();int acceptedLeg=snapshot.leg();
                NativeAccess committed=new NativeAccess(){public boolean sameOriginalAssembly(Original o){return o.equals(acceptedOriginal)&&nativeAccess.sameOriginalAssembly(o);}public boolean canTraverse(Original o,Route r,Leg l,double a,double b){return r.equals(route)&&l.equals(leg)&&a==before&&b==next&&nativeAccess.canRestore(o,r,acceptedLeg,next);}public boolean canRestore(Original o,Route r,int i,double f){return nativeAccess.canRestore(o,r,i,f);}public boolean sameAssembly(Original o,Kind k){return k==acceptedKind&&sameOriginalAssembly(o);}public boolean canTraverseAssembly(Original o,Kind k,Route r,Leg l,double a,double b){return k==acceptedKind&&canTraverse(o,r,l,a,b);}public boolean canRestoreAssembly(Original o,Kind k,Route r,int i,double f){return k==acceptedKind&&canRestore(o,r,i,f);}};
                var result=pool.advanceRetainingCompletion(snapshot.task(),next,committed);if(!result.accepted()){wait(job,result.reason());continue;}
                NervMechanicalTravelR52.remember(job.ownerData(),route.id(),snapshot.leg(),leg.ticks(),clock+1);
                var phase=job.phase();if(result.state().stage()==Stage.COMPLETE)
                {phase=Phase.FINISHING;}
                saved.put(job.update(result.state(),phase,job.ownerData(),""));mirror(saved.job(snapshot.original().variant()));
            }
        }
    }
    private NervRouteRuntimeR52(){}
}
