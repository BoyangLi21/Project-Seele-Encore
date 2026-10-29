package com.projectseele.world;

import com.projectseele.entity.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** Additional moving rear hardware on the original upright carrier clock. */
@net.minecraftforge.fml.common.Mod.EventBusSubscriber(modid="projectseele")
public final class CarrierRearGuideMotionR53
{
    public record Result(List<AABB> envelopes,String rejection)
    {public boolean clear(){return rejection==null;}}
    record ContinuousBudget(int divisions,double rounding,double chord,double error){}
    private static final double CONTINUOUS_CHORD_BUDGET=.00003;
    private record Pair(NervLegacyCarrierRideR52.Piece from,NervLegacyCarrierRideR52.Piece to,AABB bounds){}
    private record Obstacle(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,AABB bounds)
    {
        Obstacle(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to)
        {this(mesh,from,to,mesh.envelope(from,to));}
    }
    private record FixedObstacle(String name,Obstacle obstacle){}
    /** One synchronous proposal owns this immutable-source index. World
     * blocks, supports and actors are still queried on every motion interval. */
    private static final class GeometryQuery
    {
        final NervRouteNativeR52.CheckedContinuousTraversalR52 coverage;
        boolean fixedCertified;
        GeometryQuery(){this(null);}
        GeometryQuery(NervRouteNativeR52.CheckedContinuousTraversalR52 coverage){this.coverage=coverage;}
        private NervStaticSpatialIndexR52<FixedObstacle> originalRails;
        final NervRigidMeshSweepR52.PairQuery narrow=new NervRigidMeshSweepR52.PairQuery();
        List<FixedObstacle> originalRails(AABB bounds)throws IOException
        {
            if(originalRails==null)
            {
                var rails=new ArrayList<FixedObstacle>();
                for(var f:NervLegacyCarrierRideR52.fixedPartsR52())
                    rails.add(new FixedObstacle(f.name(),new Obstacle(f.mesh(),f.frame(),f.frame())));
                originalRails=new NervStaticSpatialIndexR52<>(rails,f->f.obstacle().bounds());
            }
            return originalRails.query(bounds);
        }
    }
    private static final Map<String,NervRigidMeshSweepR52> BODY=new LinkedHashMap<>();
    private static final NervRigidPairMemoR53 SELF=new NervRigidPairMemoR53(8192);

    private record FixedMeshKey(String name,String leg,String mount,String component,
        NervRigidMeshSweepR52 mesh,RigidTransform frame){}
    record FixedPair(int interval,NervLegacyCarrierRideR52.Piece from,NervLegacyCarrierRideR52.Piece to,
        NervRigidMeshSweepR52 mesh,RigidTransform frame,double error,String rejection){}
    private record BridgeState(int entityId,String kind,RigidTransform frame,float progress,boolean alive){}
    private static Map<CarrierTransferRailsR53.Gate,BridgeState> bridgeState(ServerLevel level,CarrierTransferRailsR53.Source source)
    {
        if(source==null)return Map.of();
        var state=new HashMap<CarrierTransferRailsR53.Gate,BridgeState>();
        for(var gate:source.bridges().keySet())
        {
            var entity=level.getEntity(gate.visual());
            state.put(gate,entity instanceof NervHangarDoorEntity door
                ?new BridgeState(door.getId(),"door",door.actualFrameR52(),door.actualOpenProgressR52(),door.isAlive())
                :new BridgeState(entity==null?-1:entity.getId(),entity==null?"missing":"other",null,Float.NaN,entity!=null&&entity.isAlive()));
        }
        return Map.copyOf(state);
    }
    private static final class FixedWork
    {
        final CarrierRearGuideR53.Hardware hardware;
        final CarrierRearGuideR53.FixedGeometry rails;
        final CarrierTransferRailsR53.Source transfer;
        final CarrierMountProfileR53.State mounting;
        final double lift;
        final List<DirectoryTrajectoryR52> paths;
        final Set<FixedMeshKey> steel;
        final Map<CarrierTransferRailsR53.Gate,BridgeState> bridges;
        volatile boolean valid=true;
        java.util.concurrent.CompletableFuture<String> result;
        FixedWork(CarrierRearGuideR53.Hardware hardware,CarrierRearGuideR53.FixedGeometry rails,
            CarrierTransferRailsR53.Source transfer,CarrierMountProfileR53.State mounting,double lift,
            List<DirectoryTrajectoryR52> paths,Set<FixedMeshKey> steel,Map<CarrierTransferRailsR53.Gate,BridgeState> bridges)
        {this.hardware=hardware;this.rails=rails;this.transfer=transfer;this.mounting=mounting;this.lift=lift;
            this.paths=List.copyOf(paths);this.steel=Set.copyOf(steel);this.bridges=Map.copyOf(bridges);}
    }
    // Server-thread owned. Workers read only their immutable pair list and this
    // volatile cancellation flag; no SELF lock, Level, actor or selected lookup.
    private static final List<FixedWork> FIXED_WORK=new ArrayList<>();
    @net.minecraftforge.eventbus.api.SubscribeEvent
    public static void stopping(net.minecraftforge.event.server.ServerStoppingEvent event)
    {for(var work:FIXED_WORK)work.valid=false;FIXED_WORK.clear();}

    static String evaluateFixedSourceR53(List<FixedPair> pairs)
    {
        var query=new NervRigidMeshSweepR52.PairQuery();int interval=-1;
        for(var pair:pairs)
        {
            NervGeometryWorkR53.check();
            if(interval!=pair.interval()){query.nextInterval();interval=pair.interval();}
            double error=pair.error();var a=pair.from();var b=pair.to();
            if(a.mesh().intersects(a.frame(),b.frame(),pair.mesh(),pair.frame(),pair.frame(),.003,
                    new Vec3(error,error,error),query))return pair.rejection();
        }
        return "";
    }

    /** null retains the original synchronous checks. A nonempty result is
     * HOLD, including pending/cancellation; only an empty result certifies steel. */
    private static String fixedSource(ServerLevel level,List<DirectoryTrajectoryR52> paths,
        CarrierRearGuideR53.Hardware hardware,CarrierRearGuideR53.FixedGeometry rails,
        CarrierMountProfileR53.State mounting,double lift,GeometryQuery geometry)throws IOException
    {
        boolean allowPending=geometry.coverage.allowsPendingSourceR53();
        var transfer=CarrierTransferRailsR53.selected();
        var context=NervRouteRuntimeR52.flightContext(level);
        if(context==null||!rails.directory().equals(context.directory().fingerprint())
            ||!rails.legacySource().equals(NervRouteRuntimeR52.uprightGuideSourceR52(level)))return "rear_actual_world_binding_changed";
        for(var path:paths)
            if(!path.pureTranslation()||!rails.directory().equals(path.directory().fingerprint())
                ||!NervUprightGuidewayR52.enabledForDirectoryR52(level,path.directory()))return "rear_route_source_or_root_changed";
        var bridges=bridgeState(level,transfer);
        // Legacy floor templates are installed once per class loader; their
        // fixed frames never mutate. Transfer/fixed source identity plus every
        // actual gate's presence, identity, frame and clock therefore covers
        // all source steel without rebuilding the interval candidate lists.
        for(var iterator=FIXED_WORK.iterator();iterator.hasNext();)
        {
            var work=iterator.next();
            if(!work.valid||!work.bridges.equals(bridges))
            {work.valid=false;iterator.remove();continue;}
            if(work.hardware!=hardware||work.rails!=rails||work.transfer!=transfer
                ||!work.mounting.equals(mounting)||work.lift!=lift
                ||!NervRailSourceCoverageR53.covers(work.paths,paths))continue;
            if(!work.result.isDone()){if(allowPending)return "rear_fixed_source_pending";continue;}
            String result=work.result.join();
            if(result.isEmpty())return result;
            if(NervRailSourceCoverageR53.covers(paths,work.paths))return result;
        }
        if(!allowPending)return null;
        if(FIXED_WORK.stream().filter(w->!w.result.isDone()).count()>=2)return "rear_fixed_source_pending";
        var keys=new HashSet<FixedMeshKey>();var pairs=new ArrayList<FixedPair>();int[] interval={0};
        var failure=visitContinuousIntervals(paths,hardware,lift,mounting,(path,from,to,rootFrom,rootTo,error)->{
            if(!path.pureTranslation()||!rails.directory().equals(path.directory().fingerprint())
                ||!NervUprightGuidewayR52.enabledForDirectoryR52(level,path.directory()))return rejected("rear_route_source_or_root_changed");
            int index=interval[0]++;double expanded=sweptError(from,to,error,false);
            String leg=CarrierRearGuideR53.canonicalPath(path);
            for(int i=0;i<from.size();i++)
            {
                var a=from.get(i);var b=to.get(i);
                if(!a.name().equals(b.name())||a.mesh()!=b.mesh())return rejected("rear_source_topology_changed");
                var bounds=pairBounds(a,b,expanded);
                for(var fixed:geometry.originalRails(bounds))
                {
                    var f=fixed.obstacle();
                    keys.add(new FixedMeshKey(fixed.name(),"","","original_floor",f.mesh(),f.from()));
                    pairs.add(new FixedPair(index,a,b,f.mesh(),f.from(),expanded,a.name()+" / original floor rail "+fixed.name()));
                }
                for(var fixed:CarrierTransferRailsR53.nearby(level,bounds))
                {
                    var f=fixed.steel();
                    keys.add(new FixedMeshKey(fixed.name(),fixed.leg(),fixed.mount(),fixed.component(),f.mesh(),f.frame()));
                    // Retain the exact original named finite bearing allowance
                    // on the server thread before freezing the source pair.
                    if(leg!=null&&CarrierRearGuideR53.namedContact(a,b,fixed,leg,expanded))continue;
                    pairs.add(new FixedPair(index,a,b,f.mesh(),f.frame(),expanded,a.name()+" / "+f.name()));
                }
            }
            return null;
        });
        if(failure!=null)return failure.rejection();
        if(pairs.isEmpty())return "";
        while(FIXED_WORK.size()>=8)
        {
            var iterator=FIXED_WORK.iterator();boolean removed=false;
            while(iterator.hasNext())
            {
                var old=iterator.next();if(!old.result.isDone())continue;
                old.valid=false;iterator.remove();removed=true;break;
            }
            if(!removed)return "rear_fixed_source_pending";
        }
        var work=new FixedWork(hardware,rails,transfer,mounting,lift,paths,keys,bridges);
        var captured=List.copyOf(pairs);
        try
        {
            work.result=NervGeometryWorkR53.submit(()->work.valid,()->evaluateFixedSourceR53(captured))
                .handle((value,error)->error==null?value:"rear_fixed_source_failed="+error.getClass().getSimpleName());
        }
        catch(java.util.concurrent.RejectedExecutionException busy){return "rear_fixed_source_pending";}
        FIXED_WORK.add(work);return "rear_fixed_source_pending";
    }

    private static Result rejected(String reason){return new Result(List.of(),reason);}
    private static List<NervLegacyCarrierRideR52.Piece> body(RigidTransform root)
    {
        if(BODY.isEmpty())CarrierAssemblyR53.selected().posed(1,0,0).forEach((n,v)->BODY.put(n,new NervRigidMeshSweepR52(v)));
        return BODY.entrySet().stream().map(e->new NervLegacyCarrierRideR52.Piece(
            "body/"+e.getKey(),e.getValue(),new double[0],root,"body")).toList();
    }

    /** Independent horizontal actuator: the controller, payload and lift stay fixed. */
    static Result transverse(ServerLevel level,NervCarrierPlatformEntity carrier,
                             CarrierMountProfileR53.State from,CarrierMountProfileR53.State to,
                             Set<UUID> own)throws IOException
    {
        if(from.aboveFloor()||to.aboveFloor()||from.elevation()!=0||to.elevation()!=0
            ||NervOriginalCarrierR52.progress(carrier,1)!=1
            ||CarrierRearGuideR53.actualLift(carrier,1)!=CarrierRearGuideR53.STOW_LIFT
            ||NervOriginalCarrierR52.headSlideR53(carrier,1)!=0)
            return rejected("rear_lateral_requires_original_raised_body_and_stowed_head");
        if(!NervTraversalPolicyR53.strict(level))
            return own.contains(carrier.getUUID())&&EntryPlugEjectionR48.loaded(level,carrier.getBoundingBox())
                    ?new Result(List.of(carrier.getBoundingBox()),null):rejected("rear_lateral_original_or_loaded_column_missing");
        var hardware=CarrierRearGuideR53.selected();
        if(hardware==null||!CarrierRearLateralR53.bearings(hardware,from.transverse(),to.transverse()))
            return rejected("rear_lateral_finite_source_bearings_missing");
        var root=NervOriginalCarrierR52.actualRoot(carrier,1);
        var direction=NervOriginalCarrierR52.uprightDirectionR52(carrier,1);
        var a=hardware.partsAt(root,1,direction,0,CarrierRearGuideR53.STOW_LIFT,from);
        var b=hardware.partsAt(root,1,direction,0,CarrierRearGuideR53.STOW_LIFT,to);
        var internal=NervTraversalPolicyR53.strict(level)?CarrierRearLateralR53.selfRejection(a,b):null;
        if(internal!=null)return rejected(internal);
        for(var id:own)if(level.getEntity(id) instanceof EvaUnit01Entity eva&&eva.isUmbilicalConnected())
        {
            if(!eva.isCarrierPowerConnected())return rejected("rear_lateral_power_not_bound_to_original_reel");
            var source=CarrierAssemblyR53.selected();if(source==null)return rejected("rear_lateral_actual_reel_missing");
            var reel=from.powerReelFrame(root,1,source.powerReel()).translation();
            // The rack lead's rounded control polygon stays inside its endpoint
            // hull plus the 2.2 m outlet; sag is clamped to .55 m and tube radius
            // is .22 m. This encloses its whole rendered path and connector.
            var cable=new AABB(eva.getUmbilicalMountPosition(),eva.getUmbilicalSocketPosition())
                .minmax(new AABB(reel,reel)).inflate(3);
            for(int i=0;i<a.size();i++)if(NervTraversalPolicyR53.strict(level)&&!a.get(i).frame().equals(b.get(i).frame())
                &&a.get(i).mesh().intersects(a.get(i).frame(),b.get(i).frame(),cable,.003))
                return rejected(a.get(i).name()+" / actual rack power lead envelope");
        }
        return check(level,carrier,a,b,root,root,0,null,own,!from.equals(to),new GeometryQuery());
    }

    public static Result bank(ServerLevel level,NervCarrierPlatformEntity carrier,
                              net.minecraft.nbt.CompoundTag state,int step,Set<UUID> own)throws IOException
    {
        var hardware=CarrierRearGuideR53.selected();var root=NervOriginalCarrierR52.actualRoot(carrier,1);
        var mounting=CarrierMountProfileR53.read(carrier,1);
        if(mounting.transverse()!=0)return rejected("rear_transverse_must_expand_before_bank_capture");
        var a=NervBankHeadTransferR53.pose(state,state.getInt("Clock"));
        var b=NervBankHeadTransferR53.pose(state,state.getInt("Clock")+step);
        if(!NervTraversalPolicyR53.strict(level))
            return own.contains(carrier.getUUID())&&EntryPlugEjectionR48.loaded(level,carrier.getBoundingBox())
                    ?new Result(List.of(carrier.getBoundingBox()),null):rejected("rear_bank_original_or_loaded_column_missing");
        var A=hardware.partsAt(root,1,a.direction(),a.slide(),CarrierRearGuideR53.bankLift(state,state.getInt("Clock")),mounting);
        var B=hardware.partsAt(root,1,b.direction(),b.slide(),CarrierRearGuideR53.bankLift(state,state.getInt("Clock")+step),mounting);
        double angle=Math.acos(Math.max(-1,Math.min(1,a.direction().dot(b.direction()))));
        // The bank is stopped. During turning, the monotone angle follows a
        // single circular path about each fixed ball; slide and turn do not
        // overlap. This encloses the curved frame origin as well as SLERP.
        double error=angle==0?0:(.35+Math.abs(a.slide()))*angle*angle/8+2e-6;
        return check(level,carrier,A,B,root,root,error,state.getString("RearLegR53"),own,true,new GeometryQuery());
    }

    public static Result continuous(ServerLevel level,NervCarrierPlatformEntity carrier,
                                    List<DirectoryTrajectoryR52> paths,Set<UUID> own)throws IOException
    {return continuous(level,carrier,paths,own,null);}

    public static Result continuous(ServerLevel level,NervCarrierPlatformEntity carrier,
                                    List<DirectoryTrajectoryR52> paths,Set<UUID> own,
                                    NervRouteNativeR52.CheckedContinuousTraversalR52 coverage)throws IOException
    {
        if(coverage!=null&&(!coverage.current(level)||NervTraversalPolicyR53.strict(level)&&!coverage.coversFixedCarrierRailsR53(level,carrier,paths,own)))
            return rejected("rear_checked_assembly_rail_coverage_stale");
        var hardware=CarrierRearGuideR53.selected();var fixed=CarrierRearGuideR53.fixed();
        var boxes=new ArrayList<AABB>();double lift=CarrierRearGuideR53.actualLift(carrier,1);
        var geometry=new GeometryQuery(coverage);
        var mounting=CarrierMountProfileR53.read(carrier,1);
        if(mounting.transverse()!=0&&lift!=CarrierRearGuideR53.STOW_LIFT)return rejected("rear_transverse_requires_stowed_head");
        if(CarrierRearLateralR53.supported()&&lift==CarrierRearGuideR53.STOW_LIFT&&mounting.transverse()!=1)
            return rejected("rear_transverse_original_actuator_not_stowed");
        if(!NervTraversalPolicyR53.strict(level))
        {
            if(!own.contains(carrier.getUUID()))return rejected("rear_original_not_owned");
            var actual=NervOriginalCarrierR52.actualRoot(carrier,1).translation();
            for(var path:paths)
            {
                if(!path.pureTranslation()||!fixed.directory().equals(path.directory().fingerprint())
                        ||!NervUprightGuidewayR52.enabledForDirectoryR52(level,path.directory()))
                    return rejected("rear_route_source_or_root_changed");
                var bounds=carrier.getBoundingBox().move(path.sample(0).evaRoot().translation().subtract(actual))
                        .minmax(carrier.getBoundingBox().move(path.sample(.5).evaRoot().translation().subtract(actual)))
                        .minmax(carrier.getBoundingBox().move(path.sample(1).evaRoot().translation().subtract(actual)));
                if(!EntryPlugEjectionR48.loaded(level,bounds))return rejected("rear_route_column_unloaded");
                boxes.add(bounds);
            }
            return new Result(List.copyOf(boxes),null);
        }
        if(coverage!=null&&NervTraversalPolicyR53.strict(level))
        {
            String source=fixedSource(level,paths,hardware,fixed,mounting,lift,geometry);
            if(source!=null&&!source.isEmpty())return rejected(source);
            geometry.fixedCertified=source!=null;
        }
        var failure=visitContinuousIntervals(paths,hardware,lift,mounting,(path,from,to,rootFrom,rootTo,error)->{
            if(!path.pureTranslation()||!fixed.directory().equals(path.directory().fingerprint())
                ||!NervUprightGuidewayR52.enabledForDirectoryR52(level,path.directory()))return rejected("rear_route_source_or_root_changed");
            var result=check(level,carrier,from,to,rootFrom,rootTo,error,CarrierRearGuideR53.canonicalPath(path),own,false,geometry);
            if(!result.clear())return result;boxes.addAll(result.envelopes());return null;
        });
        if(failure!=null)return failure;
        if(coverage!=null&&(!coverage.current(level)||NervTraversalPolicyR53.strict(level)&&!coverage.coversFixedCarrierRailsR53(level,carrier,paths,own)))
            return rejected("rear_checked_assembly_rail_coverage_changed");
        return new Result(List.copyOf(boxes),null);
    }

    @FunctionalInterface
    private interface ContinuousInterval
    {
        Result visit(DirectoryTrajectoryR52 path,List<NervLegacyCarrierRideR52.Piece> from,
            List<NervLegacyCarrierRideR52.Piece> to,RigidTransform rootFrom,RigidTransform rootTo,double error)throws IOException;
    }

    private static Result visitContinuousIntervals(List<DirectoryTrajectoryR52> paths,CarrierRearGuideR53.Hardware hardware,
        double lift,CarrierMountProfileR53.State mounting,ContinuousInterval visitor)throws IOException
    {
        for(var originalPath:paths)for(var path:rearMotionSlices(originalPath))
        {
            ContinuousBudget budget;
            try{budget=continuousBudget(path,hardware);}
            catch(IllegalArgumentException invalid){return rejected("rear_curve_bound_exceeds_budget="+invalid.getMessage());}
            int divisions=budget.divisions();
            for(int k=0;k<divisions;k++)
            {
                double a=k/(double)divisions,b=(k+1D)/divisions;
                var from=path.sample(a).evaRoot();var to=path.sample(b).evaRoot();
                var result=visitor.visit(path,hardware.partsAt(from,1,NervOuterCarrierGuideR52.direction(path,a),0,lift,mounting),
                    hardware.partsAt(to,1,NervOuterCarrierGuideR52.direction(path,b),0,lift,mounting),from,to,budget.error());
                if(result!=null)return result;
            }
        }
        return null;
    }

    /** The captured payload excludes these tangent-following rear parts.
     * Prepare exactly the support query used below, including adjacent rails. */
    static Set<net.minecraft.world.level.ChunkPos> continuousSupportChunks(List<DirectoryTrajectoryR52> paths,
        double lift,CarrierMountProfileR53.State mounting)throws IOException
    {
        var hardware=CarrierRearGuideR53.selected();if(hardware==null)return Set.of();
        var rails=CarrierRearGuideR53.fixed();var chunks=new HashSet<net.minecraft.world.level.ChunkPos>();
        var failure=visitContinuousIntervals(paths,hardware,lift,mounting,(path,from,to,rootFrom,rootTo,error)->{
            error=sweptError(from,to,error,false);AABB area=null;
            for(int i=0;i<from.size();i++)
            {
                var bounds=pairBounds(from.get(i),to.get(i),error);area=area==null?bounds:area.minmax(bounds);
            }
            if(area!=null)for(var anchor:supportAnchors(rails,area))chunks.add(new net.minecraft.world.level.ChunkPos(anchor.at()));
            return null;
        });
        if(failure!=null)throw new IOException(failure.rejection());
        return Set.copyOf(chunks);
    }

    private static List<CarrierRearGuideR53.Anchor> supportAnchors(CarrierRearGuideR53.FixedGeometry rails,AABB area)
    {return rails.anchorIndex().query(area.inflate(32));}

    private static AABB pairBounds(NervLegacyCarrierRideR52.Piece from,NervLegacyCarrierRideR52.Piece to,double error)
    {return from.mesh().envelope(from.frame(),to.frame()).inflate(error);}

    private static double sweptError(List<NervLegacyCarrierRideR52.Piece> from,List<NervLegacyCarrierRideR52.Piece> to,double error,boolean stopped)
    {
        if(stopped)return error;
        double surrogate=0;
        for(int i=0;i<from.size();i++)
        {
            var a=from.get(i);var b=to.get(i);var box=a.mesh().bounds();
            double radius=Math.sqrt(Math.pow(Math.max(Math.abs(box.minX),Math.abs(box.maxX)),2)
                +Math.pow(Math.max(Math.abs(box.minY),Math.abs(box.maxY)),2)
                +Math.pow(Math.max(Math.abs(box.minZ),Math.abs(box.maxZ)),2));
            double angle=Math.toRadians(a.frame().rotationErrorDegrees(b.frame()));
            surrogate=Math.max(surrogate,radius*angle*angle/8);
        }
        // The query interpolates its endpoints with SLERP. Enclose its
        // departure from the vertex chord as well as the actual curve's.
        return error+surrogate;
    }

    static ContinuousBudget continuousBudget(DirectoryTrajectoryR52 path,CarrierRearGuideR53.Hardware hardware)
    {
        if(affineOriginalRamp(path))return continuousBudget(0,path.samplingErrorBound(),CONTINUOUS_CHORD_BUDGET);
        double distance=path.directory().legDistance(path.leg(),path.toFraction())-path.directory().legDistance(path.leg(),path.fromFraction());
        var axis=path.sample(0).evaRoot().transformVector(new Vec3(1,0,0));var frameBound=frameBound(path,axis);
        double coefficient=0;
        for(var part:hardware.parts())if(!Set.of("ROOT","LIFT").contains(part.frame()))
        {
            var b=part.mesh().bounds();double x=Math.max(Math.abs(b.minX),Math.abs(b.maxX));
            double y=Math.max(Math.abs(b.minY-.35),Math.abs(b.maxY-.35));
            double z=Math.max(Math.abs(b.minZ),Math.abs(b.maxZ));
            coefficient=Math.max(coefficient,x*frameBound.x+y*frameBound.y+z*frameBound.z);
        }
        // The installed transfer's finite end cells must also enclose the
        // swept pad hull within the unchanged .2 mm contact allowance.
        double chordBudget=CarrierTransferRailsR53.canonicalPath(path)!=null?.00002:CONTINUOUS_CHORD_BUDGET;
        return continuousBudget(path.translationSecondDerivativeBound()+coefficient*distance*distance,path.samplingErrorBound(),chordBudget);
    }

    /** These are the source profile's analytic boundaries, not sampled
     * guesses that a curved head happened to have equal endpoint tangents. */
    static List<DirectoryTrajectoryR52> rearMotionSlices(DirectoryTrajectoryR52 path)
    {
        var ramp=path.leg().rampProfile();
        if(ramp==null||!path.pureTranslation())return List.of(path);
        double horizontal=path.directory().node(path.leg().from()).footFrame().translation()
                .subtract(path.directory().node(path.leg().to()).footFrame().translation()).horizontalDistance();
        var cuts=new TreeSet<Double>();cuts.add(path.fromFraction());cuts.add(path.toFraction());
        for(double distance:new double[]{ramp.flatBefore(),ramp.flatBefore()+ramp.blend(),
                ramp.flatBefore()+ramp.slopeRun()-ramp.blend(),ramp.flatBefore()+ramp.slopeRun()})
        {
            double fraction=distance/horizontal;
            if(fraction>path.fromFraction()&&fraction<path.toFraction())cuts.add(fraction);
        }
        if(cuts.size()<=2)return List.of(path);
        var result=new ArrayList<DirectoryTrajectoryR52>();Double previous=null;
        for(double fraction:cuts){if(previous!=null)result.add(new DirectoryTrajectoryR52(path.directory(),path.leg(),path.binding(),previous,fraction));previous=fraction;}
        return List.copyOf(result);
    }

    static boolean affineOriginalRamp(DirectoryTrajectoryR52 path)
    {
        var ramp=path.leg().rampProfile();if(ramp==null||!path.pureTranslation())return false;
        double horizontal=path.directory().node(path.leg().from()).footFrame().translation()
                .subtract(path.directory().node(path.leg().to()).footFrame().translation()).horizontalDistance();
        double from=path.fromFraction(),to=path.toFraction();
        return to<=ramp.flatBefore()/horizontal||from>=(ramp.flatBefore()+ramp.slopeRun())/horizontal
                ||from>=(ramp.flatBefore()+ramp.blend())/horizontal
                &&to<=(ramp.flatBefore()+ramp.slopeRun()-ramp.blend())/horizontal;
    }

    static ContinuousBudget continuousBudget(double curvature,double samplingError)
    {return continuousBudget(curvature,samplingError,CONTINUOUS_CHORD_BUDGET);}

    private static ContinuousBudget continuousBudget(double curvature,double samplingError,double chordBudget)
    {
        if(!Double.isFinite(curvature)||curvature<0||!Double.isFinite(samplingError)||samplingError<0)
            throw new IllegalArgumentException("Finite nonnegative actual curve bounds required");
        // Refinement reduces the chord term only. The source inverse/float
        // bound remains in every outward collision expansion, however large.
        double rounding=Math.nextUp(samplingError+.00002);
        double count=Math.max(1,Math.ceil(Math.sqrt(curvature/(8*chordBudget))));
        if(count>4096)throw new IllegalArgumentException("Actual curve needs more than 4096 subdivisions");
        int divisions=(int)count;double chord=curvature==0?0:Math.nextUp(curvature/(8D*divisions*divisions));
        if(chord>chordBudget)
        {
            if(++divisions>4096)throw new IllegalArgumentException("Outward chord bound needs more than 4096 subdivisions");
            chord=Math.nextUp(curvature/(8D*divisions*divisions));
        }
        double error=Math.nextUp(rounding+chord);
        if(!Double.isFinite(error))throw new IllegalArgumentException("Actual outward error bound is not finite");
        return new ContinuousBudget(divisions,rounding,chord,error);
    }

    private static Vec3 frameBound(DirectoryTrajectoryR52 path,Vec3 axis)
    {
        var curve=path.leg().centreCurve();
        if(curve!=null)return curve.transportedFrameSecondDerivativeBound(path.fromFraction(),path.toFraction(),axis);
        var ramp=path.leg().rampProfile();if(ramp==null)return Vec3.ZERO;
        var delta=path.directory().node(path.leg().to()).footFrame().translation().subtract(path.directory().node(path.leg().from()).footFrame().translation());
        if(Math.abs(delta.dot(axis))>1e-7)throw new IllegalStateException("Rear ramp must retain its measured transverse axis");
        double a=Math.abs(delta.y)*Math.PI/(2*ramp.blend()*(ramp.slopeRun()-ramp.blend()));
        double j=Math.abs(delta.y)*Math.PI*Math.PI/(2*ramp.blend()*ramp.blend()*(ramp.slopeRun()-ramp.blend()));
        double second=j+6*a*a;return new Vec3(0,second,second);
    }

    private static Result check(ServerLevel level,NervCarrierPlatformEntity carrier,
        List<NervLegacyCarrierRideR52.Piece> from,List<NervLegacyCarrierRideR52.Piece> to,
        RigidTransform rootFrom,RigidTransform rootTo,double error,String leg,Set<UUID> own,boolean stopped,GeometryQuery geometry)throws IOException
    {
        geometry.narrow.nextInterval();
        boolean strict=NervTraversalPolicyR53.strict(level),bypass=NervTraversalPolicyR53.bypass(level);
        var rails=CarrierRearGuideR53.fixed();var context=NervRouteRuntimeR52.flightContext(level);
        if(context==null||!rails.directory().equals(context.directory().fingerprint())
            ||!rails.legacySource().equals(NervRouteRuntimeR52.uprightGuideSourceR52(level)))return rejected("rear_actual_world_binding_changed");
        if(!strict)
        {
            var actual=NervOriginalCarrierR52.actualRoot(carrier,1).translation();
            var bounds=carrier.getBoundingBox().move(rootFrom.translation().subtract(actual))
                    .minmax(carrier.getBoundingBox().move(rootTo.translation().subtract(actual)));
            return own.contains(carrier.getUUID())&&EntryPlugEjectionR48.loaded(level,bounds)
                    ?new Result(List.of(bounds),null):rejected("rear_original_or_loaded_column_missing");
        }
        error=sweptError(from,to,error,stopped);
        var pairs=new ArrayList<Pair>();var boxes=new ArrayList<AABB>();AABB area=null;
        for(int i=0;i<from.size();i++)
        {
            var a=from.get(i);var b=to.get(i);
            if(!a.name().equals(b.name())||a.mesh()!=b.mesh())return rejected("rear_source_topology_changed");
            if(stopped&&a.frame().equals(b.frame()))continue;
            var bounds=pairBounds(a,b,error);pairs.add(new Pair(a,b,bounds));boxes.add(bounds);
            area=area==null?bounds:area.minmax(bounds);
        }
        if(area==null)return rejected("rear_empty_motion");
        // Authored travel and independent service actuators share the normal
        // intersection policy; full mesh clearance remains a STRICT diagnostic.
        if(bypass||!strict)
        {
            for(var pair:pairs)if(!EntryPlugEjectionR48.loaded(level,pair.bounds()))
                return rejected(pair.from().name()+" / unloaded "+pair.bounds());
        }
        else
        {
        var A=new ArrayList<NervOriginalCarrierR52.Part>();var B=new ArrayList<NervOriginalCarrierR52.Part>();
        for(var pair:pairs)
        {
            var a=pair.from();var b=pair.to();
            A.add(new NervOriginalCarrierR52.Part(a.name(),NervOriginalCarrierR52.Role.GUIDE,a.mesh(),a.frame()));
            B.add(new NervOriginalCarrierR52.Part(b.name(),NervOriginalCarrierR52.Role.GUIDE,b.mesh(),b.frame()));
        }
        var nativeFailure=NervOriginalCarrierR52.nativeBlockRejectionR53(A,B,error,
            b->EntryPlugEjectionR48.loaded(level,b),b->NativeCollisionShapesR53.read(level,carrier,b));
        if(nativeFailure!=null)return rejected(nativeFailure);
        }
        for(var anchor:supportAnchors(rails,area))
        {
            if(!level.hasChunkAt(anchor.at()))return rejected("rear_native_support_unloaded="+anchor.at());
            if(!CarrierRearGuideR53.anchorBears(level,anchor))return rejected("rear_native_support_changed="+anchor.at());
        }
        if(bypass||!strict)return new Result(List.copyOf(boxes),null);
        var obstacles=new ArrayList<Obstacle>();var carried=new ArrayList<Obstacle>();var actual=NervOriginalCarrierR52.actualRoot(carrier,1);
        var shiftFrom=rootFrom.compose(actual.inverse());var shiftTo=rootTo.compose(actual.inverse());
        for(var actor:level.getEntities((Entity)null,area.inflate(100),e->e.isAlive()&&!e.getUUID().equals(carrier.getUUID())&&(strict||!own.contains(e.getUUID()))
            &&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof NervCarrierPlatformEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof EntryPlugCarrierEntity||e instanceof UNTransportEntity)))
        {
            var mesh=NervFlightProofR52.actualObstacleMeshes(actor);
            if(mesh==null)return rejected("rear_unknown_actor="+actor.getUUID());
            if(mesh.isEmpty())
            {
                var box=actor.getBoundingBox();
                if(own.contains(actor.getUUID()))box=box.move(shiftFrom.translation()).minmax(box.move(shiftTo.translation()));
                for(var pair:pairs)if(pair.from().mesh().intersects(pair.from().frame(),pair.to().frame(),box.inflate(error),.003))
                    return rejected("rear_actor="+actor.getUUID());
            }
            else for(var m:mesh)
            {
                boolean coupled=own.contains(actor.getUUID());
                var obstacle=new Obstacle(m.mesh(),coupled?shiftFrom.compose(m.frame()):m.frame(),coupled?shiftTo.compose(m.frame()):m.endFrame());
                obstacles.add(obstacle);if(coupled)carried.add(obstacle);
            }
        }
        var obstacleIndex=new NervStaticSpatialIndexR52<>(obstacles,Obstacle::bounds);
        List<NervLegacyCarrierRideR52.Piece> bodyFrom=strict?body(rootFrom):List.of(),bodyTo=strict?body(rootTo):List.of();
        var bodies=new ArrayList<Obstacle>();
        for(int i=0;i<bodyFrom.size();i++)
            bodies.add(new Obstacle(bodyFrom.get(i).mesh(),bodyFrom.get(i).frame(),bodyTo.get(i).frame()));
        for(var pair:pairs)
        {
            var a=pair.from();var b=pair.to();var bounds=pair.bounds();
            for(var o:obstacleIndex.query(bounds))if(hit(a,b,bounds,o,error,geometry.narrow))return rejected(a.name()+" / actor mesh");
            if(strict&&!a.role().equals("source_weld"))
                for(var body:bodies)if(bounds.intersects(body.bounds())&&SELF.intersects(
                    a.mesh(),a.frame(),b.frame(),body.mesh(),body.from(),body.to(),.003,new Vec3(error,error,error),geometry.narrow))
                    return rejected(a.name()+" / carrier body");
            if(strict&&!geometry.fixedCertified)
            {
            for(var f:geometry.originalRails(bounds))
                if(hit(a,b,bounds,f.obstacle(),error,geometry.narrow))return rejected(a.name()+" / original floor rail "+f.name());
            for(var fixed:CarrierTransferRailsR53.nearby(level,bounds))
            {
                if(leg!=null&&CarrierRearGuideR53.namedContact(a,b,fixed,leg,error))continue;
                var f=fixed.steel();if(hit(a,b,bounds,new Obstacle(f.mesh(),f.frame(),f.frame()),error,geometry.narrow))return rejected(a.name()+" / "+f.name());
            }
            }
        }
        // A typed same-tick traversal has checked these exact fixed/bridge
        // meshes with the complete captured body and payload. Other callers
        // retain the interval checks, including independent head actuation.
        if(strict&&geometry.coverage==null)
        {
        for(int i=0;i<bodyFrom.size();i++)
        {
            var a=bodyFrom.get(i);var b=bodyTo.get(i);
            var bounds=bodies.get(i).bounds().inflate(error);
            for(var fixed:CarrierTransferRailsR53.nearby(level,bounds))
            {var f=fixed.steel();if(hit(a,b,bounds,new Obstacle(f.mesh(),f.frame(),f.frame()),error,geometry.narrow))return rejected(a.name()+" / "+f.name());}
        }
        for(var member:carried)for(var fixed:CarrierTransferRailsR53.nearby(level,member.bounds().inflate(error)))
        {
            var steel=fixed.steel();
            if(member.mesh().intersects(member.from(),member.to(),steel.mesh(),steel.frame(),steel.frame(),.003,new Vec3(error,error,error),geometry.narrow))
                return rejected("original carried body or plug / "+fixed.name());
        }
        }
        return new Result(List.copyOf(boxes),null);
    }

    private static boolean hit(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b,AABB bounds,Obstacle other,double error,NervRigidMeshSweepR52.PairQuery query)
    {
        if(!bounds.intersects(other.bounds()))return false;
        return a.mesh().intersects(a.frame(),b.frame(),other.mesh(),other.from(),other.to(),.003,new Vec3(error,error,error),query);
    }
    private CarrierRearGuideMotionR53(){}
}
