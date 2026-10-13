package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Server-thread reservation/progress bookkeeping only; actor motion belongs to a real adapter. */
public final class NervRouteReservationsR52
{
    public enum Stage { RESERVED,MOVING,HOLD,COMPLETE,CANCELLED }
    public record Original(long epoch,int variant,UUID eva,UUID plug,UUID pilot,UUID owner,String mission,String dimension)
    {
        public Original{Objects.requireNonNull(eva);Objects.requireNonNull(plug);Objects.requireNonNull(pilot);Objects.requireNonNull(owner);Objects.requireNonNull(mission);Objects.requireNonNull(dimension);NervRouteDirectoryR52.require(!eva.equals(plug)&&!eva.equals(pilot)&&!plug.equals(pilot),"Distinct original EVA/plug/pilot required");}
    }
    public record Snapshot(UUID task,Original original,String directoryFingerprint,String route,int leg,double fraction,Stage stage,String waiting,Kind kind)
    {public Snapshot(UUID task,Original original,String directoryFingerprint,String route,int leg,double fraction,Stage stage,String waiting){this(task,original,directoryFingerprint,route,leg,fraction,stage,waiting,Kind.OCCUPIED);}public Snapshot{Objects.requireNonNull(kind);}}
    public record Result(boolean accepted,Snapshot state,String reason){}
    public record FlightLease(UUID task,Original original,String directoryFingerprint,Set<String> spaces,
                              UUID aircraft,Kind kind,boolean payloadTransferred,Set<String> mechanisms)
    {
        public FlightLease(UUID task,Original original,String fingerprint,Set<String> spaces)
        {this(task,original,fingerprint,spaces,null,Kind.OCCUPIED,false,Set.of());}
        public FlightLease(UUID task,Original original,String fingerprint,Set<String> spaces,UUID aircraft,Kind kind,boolean transferred)
        {this(task,original,fingerprint,spaces,aircraft,kind,transferred,Set.of());}
        public FlightLease{Objects.requireNonNull(task);Objects.requireNonNull(original);Objects.requireNonNull(directoryFingerprint);Objects.requireNonNull(kind);spaces=Set.copyOf(spaces);mechanisms=Set.copyOf(mechanisms);}
    }
    /** Flight geometry/identity admission still belongs to the actual existing
     * aircraft/payload controller. This broker invents no trajectory or space. */
    public interface FlightAccess
    {
        boolean sameOriginalAssembly(Original original);
        boolean checkedFlightGeometry(Original original,Set<Resource> declaredSpaces,boolean restoring);
        default boolean sameMovingAssembly(Original original,Kind kind){return kind==Kind.OCCUPIED&&sameOriginalAssembly(original);}
        default boolean originalAircraft(UUID aircraft){return false;}
        default boolean checkedAircraftOnlyGeometry(UUID aircraft,Set<Resource> spaces,boolean restoring){return false;}
        default boolean checkedSupportedDelivery(Original original,Kind kind){return false;}
        /** Concrete private geometry proof may supply the exact actual grid
         * set; callers cannot substitute a reference corridor's space IDs. */
        default Set<String> checkedSourceSpacesR52(){return null;}
    }
    /** Implement from loaded canonical fleet/plug/pilot UUIDs, original
     * commander/mission/dimension and real full
     * assembly sweeps, rail continuity, doors and foot-bearing clearance. Never
     * authorize by timers, nearest-coordinate guesses, teleport or noPhysics. */
    public interface NativeAccess
    {
        boolean sameOriginalAssembly(Original original);
        boolean canTraverse(Original original,Route route,Leg leg,double fromFraction,double toFraction);
        boolean canRestore(Original original,Route route,int leg,double fraction);
        default boolean sameAssembly(Original original,Kind kind){return kind==Kind.OCCUPIED&&sameOriginalAssembly(original);}
        default boolean canTraverseAssembly(Original original,Kind kind,Route route,Leg leg,double from,double to){return kind==Kind.OCCUPIED&&canTraverse(original,route,leg,from,to);}
        default boolean canRestoreAssembly(Original original,Kind kind,Route route,int leg,double fraction){return kind==Kind.OCCUPIED&&canRestore(original,route,leg,fraction);}
    }
    private final NervRouteDirectoryR52 directory;
    private final Map<UUID,Snapshot> tasks=new LinkedHashMap<>();
    private final Map<UUID,FlightLease> flights=new LinkedHashMap<>();
    public record HardwareLease(UUID task,UUID controller,int variant,long epoch,String directoryFingerprint,Set<String> resources,UUID companionFlight)
    {public HardwareLease{Objects.requireNonNull(task);Objects.requireNonNull(controller);Objects.requireNonNull(directoryFingerprint);resources=Set.copyOf(resources);}}
    public interface HardwareAccess
    {boolean sameOriginalCarrier(UUID controller,int variant,long epoch);boolean checkedCarrierGeometry(UUID controller,Set<Resource> resources,boolean restoring);}
    private final Map<UUID,HardwareLease> hardware=new LinkedHashMap<>();
    private final Map<String,UUID> hardwareResources=new HashMap<>();
    private final Set<UUID> quarantinedFlights=new HashSet<>();
    private final Map<UUID,Snapshot> quarantinedGround=new LinkedHashMap<>();
    private final Map<String,UUID> resources=new HashMap<>();
    private final Map<UUID,UUID> actors=new HashMap<>();
    public NervRouteReservationsR52(NervRouteDirectoryR52 directory){this.directory=Objects.requireNonNull(directory);}
    public synchronized Snapshot query(UUID task){return tasks.get(task);}
    public synchronized FlightLease queryFlight(UUID task){return flights.get(task);}
    public synchronized HardwareLease queryHardware(UUID task){return hardware.get(task);}
    /** Read only the actually admitted EVA actor claim, never a provisional
     * save, available route or UUID found by proximity. */
    public synchronized Snapshot groundTaskR52(Original original){UUID task=actors.get(original.eva());if(task==null)return null;var state=tasks.get(task);return state!=null&&state.original().equals(original)&&state.stage()!=Stage.CANCELLED?state:null;}
    /** Every physical resource is already owned by this exact task. Its one
     * admitted hardware/flight companion may share only their existing legal
     * relation; mere availability never satisfies this receipt. */
    public synchronized boolean resourcesHeldR52(UUID task,Set<String> ids)
    {
        if(task==null||ids.isEmpty())return false;for(String id:ids){if(directory.resource(id)==null)return false;UUID ground=resources.get(id),steel=hardwareResources.get(id);if(!task.equals(ground)&&!task.equals(steel))return false;
            if(ground!=null&&!ground.equals(task)){var h=hardware.get(task);var f=flights.get(ground);if(h==null||f==null||!ground.equals(h.companionFlight())||f.payloadTransferred()||f.original().variant()!=h.variant()||h.epoch()!=directory.epoch()||!h.directoryFingerprint().equals(directory.fingerprint()))return false;}
            if(steel!=null&&!steel.equals(task)){var h=hardware.get(steel);var f=flights.get(task);if(h==null||f==null||!task.equals(h.companionFlight())||f.payloadTransferred()||f.original().variant()!=h.variant()||h.epoch()!=directory.epoch()||!h.directoryFingerprint().equals(directory.fingerprint()))return false;}
        }return true;
    }
    private boolean hardwareAvailable(UUID ownTask,String id)
    {UUID held=hardwareResources.get(id);if(held==null||held.equals(ownTask))return true;var h=hardware.get(held);return h!=null&&ownTask!=null&&ownTask.equals(h.companionFlight());}
    public synchronized boolean resourcesAvailable(UUID ownTask,Set<String> ids)
    {for(String id:ids){if(directory.resource(id)==null||!hardwareAvailable(ownTask,id))return false;var owner=resources.get(id);if(owner!=null&&!owner.equals(ownTask))return false;}return true;}
    public synchronized boolean flightQuarantined(UUID task){return quarantinedFlights.contains(task);}
    public synchronized boolean groundQuarantined(UUID task){return quarantinedGround.containsKey(task);}
    /** Provisional claims are intentionally absent from query(): the native
     * controller must still run its normal full restore proof before motion. */
    public synchronized boolean quarantineGround(Snapshot saved)
    {
        Objects.requireNonNull(saved);var route=directory.route(saved.route());var previous=quarantinedGround.get(saved.task());if(previous!=null)return previous.equals(saved);
        if(tasks.containsKey(saved.task())||flights.containsKey(saved.task())||hardware.containsKey(saved.task())||route==null||!context(saved.original(),route).isEmpty()||!saved.directoryFingerprint().equals(directory.fingerprint())||saved.stage()==Stage.CANCELLED||saved.leg()<0||saved.leg()>=route.legs().size()||!Double.isFinite(saved.fraction())||saved.fraction()<0||saved.fraction()>1||!free(saved.original(),route,saved.kind()))return false;
        for(String id:directory.resources(route))resources.put(id,saved.task());for(UUID id:TransportMembershipR52.members(saved.original(),saved.kind()))actors.put(id,saved.task());quarantinedGround.put(saved.task(),saved);return true;
    }
    public synchronized Set<UUID> leasedMembers(UUID task){var result=new HashSet<UUID>();actors.forEach((actor,owner)->{if(owner.equals(task))result.add(actor);});return Set.copyOf(result);}
    public synchronized boolean available(Route route){return directory.resources(route).stream().noneMatch(id->resources.containsKey(id)||hardwareResources.containsKey(id));}
    /** Empty steel has its own actor lease. It never acquires an EVA/pilot/plug
     * membership or changes the existing flight's control owner. Shared SPACE
     * with its one companion aircraft still requires both actual mesh proofs. */
    public synchronized boolean reserveHardware(HardwareLease lease,HardwareAccess actual,boolean restoring)
    {
        if(!directory.installed()||lease.epoch()!=directory.epoch()||!lease.directoryFingerprint().equals(directory.fingerprint())||lease.variant()<0||lease.variant()>2||lease.resources().isEmpty()||tasks.containsKey(lease.task())||flights.containsKey(lease.task())||quarantinedGround.containsKey(lease.task()))return false;
        for(int variant=0;variant<3;variant++){var unit=directory.unit(variant);if(unit!=null&&(lease.controller().equals(unit.eva())||lease.controller().equals(unit.plug())))return false;}
        var old=hardware.get(lease.task());if(old!=null&&!old.controller().equals(lease.controller()))return false;
        UUID actor=actors.get(lease.controller());if(actor!=null&&!actor.equals(lease.task()))return false;
        FlightLease companion=lease.companionFlight()==null?null:flights.get(lease.companionFlight());if(lease.companionFlight()!=null&&(companion==null||companion.payloadTransferred()||companion.original().variant()!=lease.variant()||companion.original().pilot().equals(lease.controller())))return false;
        var declared=new HashSet<Resource>();for(String id:lease.resources())
        {var resource=directory.resource(id);if(resource==null||!Set.of(ResourceKind.RAIL,ResourceKind.SPACE,ResourceKind.DOOR,ResourceKind.SUPPORT).contains(resource.kind()))return false;UUID moving=resources.get(id),steel=hardwareResources.get(id);if(steel!=null&&!steel.equals(lease.task())||moving!=null&&!moving.equals(lease.task())&&!moving.equals(lease.companionFlight()))return false;declared.add(resource);}
        if(!actual.sameOriginalCarrier(lease.controller(),lease.variant(),lease.epoch())||!actual.checkedCarrierGeometry(lease.controller(),Set.copyOf(declared),restoring))return false;
        hardwareResources.entrySet().removeIf(entry->entry.getValue().equals(lease.task())&&!lease.resources().contains(entry.getKey()));for(String id:lease.resources())hardwareResources.put(id,lease.task());actors.put(lease.controller(),lease.task());hardware.put(lease.task(),lease);return true;
    }
    public synchronized boolean releaseHardware(UUID task,UUID controller)
    {var lease=hardware.get(task);if(lease==null||!lease.controller().equals(controller))return false;hardwareResources.entrySet().removeIf(e->e.getValue().equals(task));actors.entrySet().removeIf(e->e.getValue().equals(task));hardware.remove(task);return true;}
    private String context(Original original,Route route)
    {
        if(!directory.installed())return "Root directory is design, not installed";
        Unit unit=directory.unit(original.variant());
        if(original.epoch()!=directory.epoch()||unit==null||!unit.eva().equals(original.eva())||!unit.plug().equals(original.plug())||route==null||route.variant()!=original.variant())return "Original fleet/plug/epoch/route mismatch";
        if(!directory.node(directory.leg(route.legs().get(0)).from()).dimension().equals(original.dimension()))return "Wrong actual actor dimension";
        return "";
    }
    public synchronized Result reserve(UUID task,Original original,String routeId,NativeAccess nativeAccess)
    {return reserve(task,original,routeId,nativeAccess,Kind.OCCUPIED);}
    public synchronized Result reserve(UUID task,Original original,String routeId,NativeAccess nativeAccess,Kind kind)
    {
        Objects.requireNonNull(task);Objects.requireNonNull(original);Objects.requireNonNull(nativeAccess);Route route=directory.route(routeId);
        String blocker=context(original,route);if(!blocker.isEmpty())return new Result(false,null,blocker);
        if(flights.containsKey(task)||quarantinedGround.containsKey(task)||hardware.containsKey(task))return new Result(false,null,"Task ID belongs to a flight/hardware/provisional physical lease");
        Snapshot previous=tasks.get(task);if(previous!=null)return new Result(previous.original().equals(original)&&previous.kind()==kind&&previous.route().equals(routeId)&&previous.stage()!=Stage.CANCELLED&&previous.stage()!=Stage.COMPLETE,previous,"Task ID already registered");
        if(kind==Kind.HULL_ONLY_RECOVERY&&!route.recovery())return new Result(false,null,"Hull-only membership is admitted only on an actual recovery route");
        if(!nativeAccess.sameAssembly(original,kind))return new Result(false,null,"Actual original moving membership unavailable or changed");
        if(!free(original,route,kind))return new Result(false,null,"Declared physical space/resource or original moving actor already reserved");
        Snapshot state=new Snapshot(task,original,directory.fingerprint(),routeId,0,0,Stage.RESERVED,"",kind);claim(state,route);return new Result(true,state,"");
    }
    /** Reclaims a stopped cancelled original at the exact mirrored source point, never at a port. */
    public synchronized Result reclaimCancelledContinuousR52(Snapshot cancelled,UUID task,Original original,NervRouteNativeR52 actual)
    {
        if(cancelled==null||cancelled.stage()!=Stage.CANCELLED||!cancelled.directoryFingerprint().equals(directory.fingerprint())||!sameOriginalActorsR52(cancelled.original(),original))return new Result(false,null,"Stopped cancelled original provenance mismatch");var old=directory.route(cancelled.route());if(old==null||!old.continuousUpright()||cancelled.leg()<0||cancelled.leg()>=old.legs().size())return new Result(false,null,"Cancelled task has no exact continuous reverse");
        var reverse=old.recovery()?old:directory.route(directory.ports().get(old.port()).reverseRoutes().get(original.variant()));if(reverse==null||!reverse.continuousUpright()||!reverse.recovery()||!old.recovery()&&!reverse.reverseOf().equals(old.id()))return new Result(false,null,"Actual selected route has no bound reverse");
        int index=old.recovery()?cancelled.leg():old.legs().size()-1-cancelled.leg();double fraction=old.recovery()?cancelled.fraction():1-cancelled.fraction();if(fraction==1&&index+1<reverse.legs().size()){index++;fraction=0;}
        String blocker=context(original,reverse);if(!blocker.isEmpty()||tasks.containsKey(task)||flights.containsKey(task)||hardware.containsKey(task)||quarantinedGround.containsKey(task))return new Result(false,null,"Cancelled reverse task identity/context unavailable: "+blocker);
        if(!free(original,reverse,cancelled.kind())||!actual.sameAssembly(original,cancelled.kind())||!actual.canRestoreAssembly(original,cancelled.kind(),reverse,index,fraction))return new Result(false,null,"Exact stopped reverse source point, assembly or full-route lease unavailable");var state=new Snapshot(task,original,directory.fingerprint(),reverse.id(),index,fraction,Stage.HOLD,"Reclaimed at the actual cancelled curve point",cancelled.kind());claim(state,reverse);return new Result(true,state,"");
    }
    private static boolean sameOriginalActorsR52(Original a,Original b)
    {return a.epoch()==b.epoch()&&a.variant()==b.variant()&&a.eva().equals(b.eva())&&a.plug().equals(b.plug())&&a.pilot().equals(b.pilot())&&a.owner().equals(b.owner())&&a.dimension().equals(b.dimension());}
    private boolean free(Original original,Route route)
    {return free(original,route,Kind.OCCUPIED);}
    private boolean free(Original original,Route route,Kind kind)
    {return available(route)&&TransportMembershipR52.members(original,kind).stream().noneMatch(actors::containsKey);}
    private void claim(Snapshot state,Route route)
    {
        for(String resource:directory.resources(route))resources.put(resource,state.task());
        for(UUID actor:TransportMembershipR52.members(state.original(),state.kind()))actors.put(actor,state.task());tasks.put(state.task(),state);
    }
    private void release(Snapshot state)
    {release(state.task());}
    private void release(UUID task)
    {resources.entrySet().removeIf(e->e.getValue().equals(task));actors.entrySet().removeIf(e->e.getValue().equals(task));}
    private Result hold(Snapshot state,String reason)
    {var held=new Snapshot(state.task(),state.original(),state.directoryFingerprint(),state.route(),state.leg(),state.fraction(),Stage.HOLD,reason,state.kind());tasks.put(held.task(),held);return new Result(false,held,reason);}
    /** A rejected sweep leaves progress and all leases unchanged. The caller
     * must apply only an accepted measured sample via its sole movement owner. */
    public synchronized Result advance(UUID task,double nextFraction,NativeAccess nativeAccess)
    {return advance(task,nextFraction,nativeAccess,true);}
    public synchronized Result advanceRetainingCompletion(UUID task,double nextFraction,NativeAccess nativeAccess)
    {return advance(task,nextFraction,nativeAccess,false);}
    private Result advance(UUID task,double nextFraction,NativeAccess nativeAccess,boolean releaseCompleted)
    {
        Objects.requireNonNull(nativeAccess);Snapshot state=tasks.get(task);
        if(state==null||state.stage()==Stage.CANCELLED||state.stage()==Stage.COMPLETE)return new Result(false,state,"Task is not active");
        NervRouteDirectoryR52.require(Double.isFinite(nextFraction)&&nextFraction>=state.fraction()&&nextFraction<=1,"Progress must be monotone inside the current leg");
        Route route=directory.route(state.route());Leg leg=directory.leg(route.legs().get(state.leg()));
        if(!nativeAccess.sameAssembly(state.original(),state.kind()))return hold(state,"Actual moving assembly/mission changed");
        if(!nativeAccess.canTraverseAssembly(state.original(),state.kind(),route,leg,state.fraction(),nextFraction))return hold(state,"Actual track/door/support/full-assembly sweep is blocked");
        int index=state.leg();Stage stage=Stage.MOVING;double fraction=nextFraction;
        if(nextFraction==1){if(index+1==route.legs().size())stage=Stage.COMPLETE;else{index++;fraction=0;}}
        Snapshot next=new Snapshot(task,state.original(),state.directoryFingerprint(),state.route(),index,fraction,stage,"",state.kind());tasks.put(task,next);
        if(stage==Stage.COMPLETE&&releaseCompleted)release(next);return new Result(true,next,"");
    }
    public synchronized boolean canCommitContinuousR52(UUID task,NervRouteNativeR52.CheckedContinuousTraversalR52 proof)
    {
        Snapshot state=tasks.get(task);if(state==null||proof==null||state.stage()==Stage.COMPLETE||state.stage()==Stage.CANCELLED||!state.original().equals(proof.original())||state.kind()!=proof.kind()||!state.route().equals(proof.route().id())||!state.directoryFingerprint().equals(directory.fingerprint())||!resourcesHeldR52(task,directory.resources(proof.route())))return false;
        var paths=proof.paths();int previous=state.leg();double fraction=state.fraction();
        for(var path:paths){int index=proof.route().legs().indexOf(path.leg().id());if(index==previous){if(Math.abs(path.fromFraction()-fraction)>1e-12)return false;}else if(index==previous+1&&fraction==1&&path.fromFraction()==0){}else return false;if(path.toFraction()<path.fromFraction())return false;previous=index;fraction=path.toFraction();}
        return true;
    }
    public synchronized Result advanceCommittedContinuousR52(UUID task,NervRouteNativeR52.CheckedContinuousTraversalR52 proof)
    {
        Snapshot state=tasks.get(task);if(proof==null||!proof.committed()||!canCommitContinuousR52(task,proof))return new Result(false,state,"Concrete checked composite/retained route lease changed");
        var last=proof.paths().get(proof.paths().size()-1);int index=proof.route().legs().indexOf(last.leg().id());double fraction=last.toFraction();Stage stage=Stage.MOVING;
        if(fraction==1){if(index+1==proof.route().legs().size())stage=Stage.COMPLETE;else{index++;fraction=0;}}
        var next=new Snapshot(task,state.original(),state.directoryFingerprint(),state.route(),index,fraction,stage,"",state.kind());tasks.put(task,next);return new Result(true,next,"");
    }
    public synchronized boolean releaseCompletion(UUID task,UUID owner)
    {var s=tasks.get(task);if(s==null||s.stage()!=Stage.COMPLETE||!s.original().owner().equals(owner))return false;release(s);return true;}
    public synchronized Result restoreCompletion(Snapshot saved,NativeAccess actual)
    {
        var route=directory.route(saved.route());
        if(saved.stage()!=Stage.COMPLETE||route==null||saved.leg()!=route.legs().size()-1||saved.fraction()!=1)return new Result(false,null,"Actual final endpoint completion receipt required");
        var active=new Snapshot(saved.task(),saved.original(),saved.directoryFingerprint(),saved.route(),saved.leg(),saved.fraction(),Stage.HOLD,saved.waiting(),saved.kind());
        var result=restore(active,actual);if(result.accepted())tasks.put(saved.task(),saved);return new Result(result.accepted(),result.accepted()?saved:null,result.reason());
    }
    /** Cancellation releases bookkeeping; the real controller stops/brakes in
     * place. It never relocates an original actor or removes physical collision. */
    public synchronized Result cancel(UUID task,UUID owner)
    {
        if(quarantinedGround.containsKey(task)||quarantinedFlights.contains(task))return new Result(false,null,"Saved physical placement is still unknown; provisional space/members remain held");
        Snapshot state=tasks.get(task);
        if(state==null&&flights.containsKey(task))
        {
            FlightLease flight=flights.get(task);if(!flight.original().owner().equals(owner))return new Result(false,null,"Original flight owner required");
            release(task);flights.remove(task);quarantinedFlights.remove(task);return new Result(true,null,"Flight space lease cancelled in place; actual controller must brake/stop");
        }
        if(state==null||!state.original().owner().equals(owner))return new Result(false,state,"Original task owner required");
        if(state.stage()==Stage.COMPLETE)return new Result(false,state,"Completed task cannot be cancelled");
        release(state);Snapshot cancelled=new Snapshot(task,state.original(),state.directoryFingerprint(),state.route(),state.leg(),state.fraction(),Stage.CANCELLED,"",state.kind());tasks.put(task,cancelled);return new Result(true,cancelled,"");
    }
    /** No leases/progress are recreated until native identity AND physical
     * placement/geometry have been checked after all original entity sections attach. */
    public synchronized Result restore(Snapshot saved,NativeAccess nativeAccess)
    {
        Objects.requireNonNull(saved);Objects.requireNonNull(nativeAccess);Objects.requireNonNull(saved.task());Objects.requireNonNull(saved.original());
        Route route=directory.route(saved.route());String blocker=context(saved.original(),route);
        if(!blocker.isEmpty())return new Result(false,null,blocker);
        if(!directory.fingerprint().equals(saved.directoryFingerprint())||saved.leg()<0||saved.leg()>=route.legs().size()
                ||!Double.isFinite(saved.fraction())||saved.fraction()<0||saved.fraction()>1||saved.stage()==null||saved.stage()==Stage.COMPLETE||saved.stage()==Stage.CANCELLED)
            return new Result(false,null,"Saved task/directory/progress is incompatible");
        if(saved.kind()==Kind.HULL_ONLY_RECOVERY&&!route.recovery())return new Result(false,null,"Hull-only save cannot restore a departure");
        var provisional=quarantinedGround.get(saved.task());
        if(provisional!=null&&(!provisional.original().equals(saved.original())||!provisional.route().equals(saved.route())||provisional.kind()!=saved.kind()||provisional.leg()!=saved.leg()||provisional.fraction()!=saved.fraction()||!provisional.directoryFingerprint().equals(saved.directoryFingerprint())))return new Result(false,null,"Saved provisional physical progress changed");
        boolean free=directory.resources(route).stream().allMatch(id->hardwareAvailable(saved.task(),id)&&(resources.get(id)==null||saved.task().equals(resources.get(id))))&&TransportMembershipR52.members(saved.original(),saved.kind()).stream().allMatch(id->actors.get(id)==null||saved.task().equals(actors.get(id)));
        if(tasks.containsKey(saved.task())||flights.containsKey(saved.task())||hardware.containsKey(saved.task())||!free)return new Result(false,null,"Restore would collide with an existing reservation");
        if(!nativeAccess.sameAssembly(saved.original(),saved.kind())||!nativeAccess.canRestoreAssembly(saved.original(),saved.kind(),route,saved.leg(),saved.fraction()))return new Result(false,null,"Native restore membership/geometry was not confirmed");
        Snapshot restored=new Snapshot(saved.task(),saved.original(),saved.directoryFingerprint(),saved.route(),saved.leg(),saved.fraction(),Stage.HOLD,"Restored in place; native sweep required before continuing",saved.kind());claim(restored,route);quarantinedGround.remove(saved.task());return new Result(true,restored,"");
    }
    /** Switch a stopped prepared job only across an identical completed prefix.
     * New leases and actual placement are checked before replacing any old lease. */
    public synchronized Result retargetPrepared(UUID task,String newRouteId,NativeAccess actual)
    {
        Objects.requireNonNull(actual);Snapshot state=tasks.get(task);Route next=directory.route(newRouteId);
        if(state==null||state.kind()!=Kind.OCCUPIED||next==null||next.recovery()||state.fraction()!=0||state.leg()<=0||state.leg()>=next.legs().size()
                ||state.stage()==Stage.COMPLETE||state.stage()==Stage.CANCELLED||!context(state.original(),next).isEmpty())return new Result(false,state,"Not a compatible stopped preparation");
        Route previous=directory.route(state.route());
        for(int i=0;i<state.leg();i++)if(!previous.legs().get(i).equals(next.legs().get(i)))return new Result(false,state,"Different completed physical prefix");
        for(String id:directory.resources(next)){UUID held=resources.get(id);if(!hardwareAvailable(task,id)||held!=null&&!held.equals(task))return new Result(false,state,"New route space is already reserved");}
        if(!actual.sameOriginalAssembly(state.original())||!actual.canRestore(state.original(),next,state.leg(),0))return new Result(false,state,"Actual stopped assembly/new route geometry not confirmed");
        release(state);var changed=new Snapshot(task,state.original(),state.directoryFingerprint(),newRouteId,state.leg(),0,Stage.HOLD,"Continue physical preparation from the same node");claim(changed,next);return new Result(true,changed,"");
    }
    public synchronized Optional<Route> nearestRecovery(Original original,Region region,Vec3 actualFoot,RecoveryAccess actualAccess)
    {return nearestRecovery(original,region,actualFoot,actualAccess,Kind.OCCUPIED);}
    public synchronized Optional<Route> nearestRecovery(Original original,Region region,Vec3 actualFoot,RecoveryAccess actualAccess,Kind kind)
    {
        return directory.nearestRecovery(original.variant(),region,original.dimension(),actualFoot,
                (port,route)->context(original,route).isEmpty()&&free(original,route,kind)&&actualAccess.reachable(port,route));
    }
    public synchronized boolean reserveFlight(UUID task,Original original,Set<String> explicitlyDeclaredSpaces,FlightAccess actual)
    {return claimFlight(new FlightLease(task,original,directory.fingerprint(),explicitlyDeclaredSpaces),actual,false);}
    public synchronized boolean reserveFlight(UUID task,Original original,UUID aircraft,Kind kind,Set<String> spaces,Set<String> mechanisms,FlightAccess actual)
    {return aircraft!=null&&claimFlight(new FlightLease(task,original,directory.fingerprint(),spaces,aircraft,kind,false,mechanisms),actual,false);}
    public synchronized boolean restoreFlight(FlightLease saved,FlightAccess actual)
    {return claimFlight(saved,actual,true);}
    /** Cold-load uncertainty blocks the same saved physical space/members,
     * but grants no motion or geometry admission. A real checked retarget is
     * still required before any controller applies an aircraft/body step. */
    public synchronized boolean quarantineFlight(FlightLease saved)
    {
        Objects.requireNonNull(saved);var original=saved.original();var unit=directory.unit(original.variant());var previous=flights.get(saved.task());if(previous!=null)return previous.equals(saved);
        if(!directory.installed()||original.epoch()!=directory.epoch()||unit==null||!unit.eva().equals(original.eva())||!unit.plug().equals(original.plug())||!directory.knowsDimension(original.dimension())||!saved.directoryFingerprint().equals(directory.fingerprint())||saved.aircraft()==null||List.of(original.eva(),original.plug(),original.pilot()).contains(saved.aircraft())||tasks.containsKey(saved.task())||hardware.containsKey(saved.task())||quarantinedGround.containsKey(saved.task())||flightMembers(saved).stream().anyMatch(actors::containsKey)||flightResources(saved,null)==null)return false;
        for(String id:flightResourceIds(saved))resources.put(id,saved.task());for(UUID actor:flightMembers(saved))actors.put(actor,saved.task());flights.put(saved.task(),saved);quarantinedFlights.add(saved.task());return true;
    }
    private boolean claimFlight(FlightLease lease,FlightAccess actual,boolean restoring)
    {
        Objects.requireNonNull(lease);Objects.requireNonNull(actual);if(!spaceArgumentsValidR52(lease.spaces()))return false;var proved=actual.checkedSourceSpacesR52();if(proved!=null){if(restoring&&!lease.spaces().equals(proved))return false;lease=new FlightLease(lease.task(),lease.original(),lease.directoryFingerprint(),proved,lease.aircraft(),lease.kind(),lease.payloadTransferred(),lease.mechanisms());}Original original=lease.original();Unit unit=directory.unit(original.variant());
        if(!directory.installed()||original.epoch()!=directory.epoch()||unit==null||!unit.eva().equals(original.eva())||!unit.plug().equals(original.plug())
                ||!directory.knowsDimension(original.dimension())||!lease.directoryFingerprint().equals(directory.fingerprint())||lease.spaces().isEmpty()||tasks.containsKey(lease.task())||quarantinedGround.containsKey(lease.task())||flights.containsKey(lease.task())||hardware.containsKey(lease.task())
                ||lease.aircraft()!=null&&List.of(original.eva(),original.plug(),original.pilot()).contains(lease.aircraft())
                ||flightMembers(lease).stream().anyMatch(actors::containsKey))return false;
        var declared=flightResources(lease,null);if(declared==null||!checkedFlight(lease,declared,actual,restoring))return false;
        for(String id:flightResourceIds(lease))resources.put(id,lease.task());for(UUID actor:flightMembers(lease))actors.put(actor,lease.task());flights.put(lease.task(),lease);return true;
    }
    private static Set<UUID> flightMembers(FlightLease lease)
    {var ids=new HashSet<UUID>();if(!lease.payloadTransferred())ids.addAll(TransportMembershipR52.members(lease.original(),lease.kind()));if(lease.aircraft()!=null)ids.add(lease.aircraft());return Set.copyOf(ids);}
    private static Set<String> flightResourceIds(FlightLease lease)
    {var ids=new HashSet<>(lease.spaces());ids.addAll(lease.mechanisms());return Set.copyOf(ids);}
    private boolean spaceArgumentsValidR52(Set<String> ids){return !ids.isEmpty()&&ids.stream().allMatch(id->{var r=directory.resource(id);return r!=null&&r.kind()==ResourceKind.SPACE;});}
    private Set<Resource> flightResources(FlightLease lease,UUID ownTask)
    {
        if(lease.spaces().isEmpty()||!Collections.disjoint(lease.spaces(),lease.mechanisms())||!directory.dynamicSpacesR52().domains().isEmpty()&&lease.spaces().size()>directory.dynamicSpacesR52().maximumStepCells())return null;
        var result=new HashSet<Resource>();
        for(String id:flightResourceIds(lease))
        {
            Resource r=directory.resource(id);UUID held=resources.get(id);
            if(r==null||!hardwareAvailable(ownTask,id)||lease.spaces().contains(id)&&r.kind()!=ResourceKind.SPACE||lease.mechanisms().contains(id)&&r.kind()!=ResourceKind.DOOR||held!=null&&!held.equals(ownTask))return null;
            result.add(r);
        }
        return Set.copyOf(result);
    }
    private static boolean checkedFlight(FlightLease lease,Set<Resource> declared,FlightAccess actual,boolean restoring)
    {
        if(lease.aircraft()!=null&&!actual.originalAircraft(lease.aircraft()))return false;
        return lease.payloadTransferred()?lease.aircraft()!=null&&actual.checkedAircraftOnlyGeometry(lease.aircraft(),declared,restoring)
                :actual.sameMovingAssembly(lease.original(),lease.kind())&&actual.checkedFlightGeometry(lease.original(),declared,restoring);
    }
    /** Acquire the next segment before releasing previous space. A failed
     * actual geometry/identity check leaves every existing lease intact. */
    public synchronized boolean retargetFlightSpaces(UUID task,Set<String> spaces,Set<String> mechanisms,FlightAccess actual)
    {
        FlightLease previous=flights.get(task);if(previous==null||!spaceArgumentsValidR52(spaces))return false;
        var proved=actual.checkedSourceSpacesR52();var next=new FlightLease(task,previous.original(),previous.directoryFingerprint(),proved==null?spaces:proved,previous.aircraft(),previous.kind(),previous.payloadTransferred(),mechanisms);
        var declared=flightResources(next,task);if(declared==null||!checkedFlight(next,declared,actual,false))return false;
        resources.entrySet().removeIf(e->e.getValue().equals(task)&&!flightResourceIds(next).contains(e.getKey()));
        for(String id:flightResourceIds(next))resources.put(id,task);flights.put(task,next);quarantinedFlights.remove(task);return true;
    }
    /** Only a supported, released original occupied assembly can leave a
     * flight lease without a mechanical reverse route. Aircraft return space
     * remains owned throughout; a failed receipt releases no actor/resource. */
    public synchronized boolean handoffFlightToDelivery(UUID task,Set<String> spaces,Set<String> mechanisms,FlightAccess actual)
    {
        var flight=flights.get(task);if(flight==null||quarantinedFlights.contains(task)||flight.aircraft()==null||flight.payloadTransferred()||flight.kind()!=Kind.OCCUPIED)return false;
        var proved=actual.checkedSourceSpacesR52();var plane=new FlightLease(task,flight.original(),flight.directoryFingerprint(),proved==null?spaces:proved,flight.aircraft(),flight.kind(),true,mechanisms);var declared=flightResources(plane,task);if(declared==null||!checkedFlight(plane,declared,actual,false))return false;
        if(!actual.checkedSupportedDelivery(flight.original(),flight.kind()))return false;
        release(task);for(String id:flightResourceIds(plane))resources.put(id,task);actors.put(plane.aircraft(),task);flights.put(task,plane);return true;
    }
    /** The real controller must already have verified positive receiver
     * support and retracted clamps. Remaining aircraft space must no longer
     * overlap the complete ground route. No actor/resource is released on a
     * failed handoff, and the aircraft keeps its own return-flight lease. */
    public synchronized Result handoffFlightToGround(UUID flightTask,UUID groundTask,String routeId,
                                                     Set<String> remainingSpaces,Set<String> remainingMechanisms,
                                                     FlightAccess aircraftActual,NativeAccess receiverActual)
    {
        FlightLease flight=flights.get(flightTask);Route route=directory.route(routeId);
        if(flight==null||quarantinedFlights.contains(flightTask)||flight.aircraft()==null||flight.payloadTransferred()||groundTask.equals(flightTask)
                ||tasks.containsKey(groundTask)||quarantinedGround.containsKey(groundTask)||flights.containsKey(groundTask)||hardware.containsKey(groundTask)||route==null||!route.recovery())return new Result(false,null,"Actual untransferred flight and unique recovery task required");
        String blocker=context(flight.original(),route);if(!blocker.isEmpty())return new Result(false,null,blocker);
        var proved=aircraftActual.checkedSourceSpacesR52();var aircraft=new FlightLease(flightTask,flight.original(),flight.directoryFingerprint(),proved==null?remainingSpaces:proved,flight.aircraft(),flight.kind(),true,remainingMechanisms);
        var declared=flightResources(aircraft,flightTask);
        if(declared==null||!Collections.disjoint(flightResourceIds(aircraft),directory.resources(route))
                ||!checkedFlight(aircraft,declared,aircraftActual,false))return new Result(false,null,"Aircraft has not physically cleared receiver ground space");
        for(String id:directory.resources(route)){UUID held=resources.get(id);if(!hardwareAvailable(flightTask,id)||held!=null&&!held.equals(flightTask))return new Result(false,null,"Receiver/ground route is reserved by another original task");}
        if(!receiverActual.sameAssembly(flight.original(),flight.kind())
                ||!receiverActual.canRestoreAssembly(flight.original(),flight.kind(),route,0,0))return new Result(false,null,"Actual original receiver placement/support was not confirmed");
        for(UUID actor:TransportMembershipR52.members(flight.original(),flight.kind()))if(!flightTask.equals(actors.get(actor)))return new Result(false,null,"Original payload lease changed");
        release(flightTask);for(String id:flightResourceIds(aircraft))resources.put(id,flightTask);actors.put(flight.aircraft(),flightTask);flights.put(flightTask,aircraft);
        var snapshot=new Snapshot(groundTask,flight.original(),directory.fingerprint(),routeId,0,0,Stage.RESERVED,"",flight.kind());claim(snapshot,route);
        return new Result(true,snapshot,"");
    }
}
