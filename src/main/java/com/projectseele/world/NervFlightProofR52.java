package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.TransportMembershipR52.Kind;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.NervRouteDirectoryR52.ResourceKind;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;
import org.joml.Vector3f;

/** Immutable native pickup/step/receiver evidence. Only actual surface checks
 * create checked inputs; no caller Boolean can authorize a movement. */
public final class NervFlightProofR52
{
    public interface Owner
    {
        default NervFlightGatePlanR52 previewFlightGates(ServerLevel level,Original original,Kind kind,Set<String> gates){return gates.isEmpty()?NervFlightGatePlanR52.inspect(level,Map.of(),gates,TransportMembershipR52.members(original,kind)):null;}
        default Set<String> flightReceiverGates(ServerLevel level,String port){return Set.of();}
        default boolean flightGateSampleCurrent(ServerLevel level,String id){return false;}
        default RigidTransform resolveFlightReceiverCargoRootR52(ServerLevel level,Original original,Kind kind,String port,CompoundTag data){return null;}
        default boolean prepareFlightGates(ServerLevel level,Original original,Kind kind,Set<String> gates,CompoundTag data){return gates.isEmpty();}
        default boolean holdFlightPickup(ServerLevel level,CheckedPickupHold proof,CompoundTag data){return false;}
        default boolean releaseWaitingPickup(ServerLevel level,CheckedPickupHold proof,CompoundTag data){return false;}
        default boolean acceptHullRecoveryStepR52(ServerLevel level,NervHullGroundRecoveryR52.AcceptedRecoveryStep proof,CompoundTag data){return false;}
        default boolean prepareEmptyCarrierGatesR52(ServerLevel level,Original original,UUID controller,Set<String> gates,CompoundTag data){return false;}
        default boolean prepareEmptyCarrierTurnR52(ServerLevel level,Original original,UUID controller,NervRouteDirectoryR52.Leg turn,CompoundTag data){return false;}
        default boolean applyEmptyCarrierTurnR52(ServerLevel level,Original original,UUID controller,DirectoryTrajectoryR52 curve,CompoundTag data){return false;}
        default boolean finishEmptyCarrierTurnR52(ServerLevel level,Original original,UUID controller,NervRouteDirectoryR52.Leg turn,CompoundTag data){return false;}
        default Set<String> pendingEmptyStationResourcesR52(ServerLevel level,Original original,CompoundTag data){return Set.of();}
        default boolean finishEmptyStationIdleR52(ServerLevel level,Original original,UUID controller,CompoundTag data){return false;}
        FlightPickupPreview previewFlight(ServerLevel level,Original original,Kind kind,CompoundTag data);
        boolean adoptFlight(ServerLevel level,CheckedPickup proof,CompoundTag data);
        boolean applyFlightStep(ServerLevel level,CheckedFlightStep proof,CompoundTag data);
        boolean receiverReady(ServerLevel level,String port,Original original,Kind kind,RigidTransform stopped,CompoundTag data);
        boolean acceptAirReceiver(ServerLevel level,CheckedAirReceiver proof,CompoundTag data);
        default boolean acceptAirDelivery(ServerLevel level,CheckedAirDelivery proof,CompoundTag data){return false;}
    }
    private static FullAssemblyGeometryR52.Provider capsules;
    public static synchronized void installCapsules()throws IOException
    {
        var receipt=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));capsules=FullAssemblyGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,hashes);
    }
    public static final class FlightPickupPreview
    {
        private final Original original;private final Kind kind;private final FootSupportFrameR52.Binding binding;private final RigidTransform root;
        private final EvaMechanicalFrameR52.HullCapture hull;private final EvaMechanicalFrameR52.OccupiedCapture occupied;private final NervHullPreviewR52 hullPreview;
        private final boolean carrierVisible,detachedCarrier;private final RigidTransform carrierFrame;private final float carrierRise,carrierRelease;private final boolean recoveryRack;private final double carrierDeckTravel;private final CompoundTag frozenBody,frozenHands;
        private final EvaOriginalMeshGeometryR52.Geometry geometry;private final List<Vec3> anchors;private final List<NervAirCradleContactsR52.Contact> contacts;private final List<NervRigidMeshSweepR52> surfaces;private final Vec3 pilotSeat,pilotHalf;
        private FlightPickupPreview(Original o,Kind k,FootSupportFrameR52.Binding b,RigidTransform r,EvaMechanicalFrameR52.HullCapture h,EvaMechanicalFrameR52.OccupiedCapture p,NervHullPreviewR52 hp,EvaOriginalMeshGeometryR52.Geometry g,List<Vec3> a,List<NervRigidMeshSweepR52> s,Vec3 seat,Vec3 half,boolean visible,float rise,float release,boolean rack,List<NervAirCradleContactsR52.Contact> contacts,CompoundTag body,CompoundTag hands,double deckTravel,boolean detached,RigidTransform carrier)
        {detachedCarrier=detached;carrierFrame=carrier;carrierDeckTravel=deckTravel;frozenBody=body.copy();frozenHands=hands.copy();carrierVisible=visible;carrierRise=rise;carrierRelease=release;recoveryRack=rack;this.contacts=List.copyOf(contacts);original=o;kind=k;binding=b;root=r;hull=h;occupied=p;hullPreview=hp;geometry=g;anchors=List.copyOf(a);surfaces=List.copyOf(s);pilotSeat=seat;pilotHalf=half;}
        public boolean payloadCarrierVisible(){return carrierVisible&&!detachedCarrier;}
        public CompoundTag bodySnapshotR52(){return frozenBody.copy();}
        public CompoundTag handSnapshotR52(){return frozenHands.copy();}
        public boolean carrierVisible(){return carrierVisible;}public float carrierRise(){return carrierRise;}public float carrierRelease(){return carrierRelease;}public boolean recoveryRack(){return recoveryRack;}public Original original(){return original;}public Kind kind(){return kind;}public FootSupportFrameR52.Binding binding(){return binding;}public RigidTransform root(){return root;}public EvaMechanicalFrameR52.HullCapture hullCapture(){return hull;}public EvaMechanicalFrameR52.OccupiedCapture occupiedCapture(){return occupied;}public EvaOriginalMeshGeometryR52.Geometry geometry(){return geometry;}public List<Vec3> jawAxes(){return contacts.stream().map(NervAirCradleContactsR52.Contact::axis).toList();}public List<Vec3> anchors(){return anchors;}public String sourceFingerprint(){return geometry.sourceFingerprint();}public Set<UUID> members(){return TransportMembershipR52.members(original,kind);}
        public boolean current(ServerLevel l)
        {
            if(!(l.getEntity(original.eva()) instanceof EvaUnit01Entity e))return false;
            if(EvaMechanicalFrameR52.active(e))return EvaMechanicalFrameR52.kind(e)==kind&&e.position().distanceToSqr(root.translation())<1e-10&&NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(e,1),root)&&shapeCurrent(l);
            return kind==Kind.HULL_ONLY_RECOVERY?hullPreview!=null&&hullPreview.matches(e,original):EvaMechanicalFrameR52.occupiedPreviewCurrent(e,original,occupied);
        }
        public boolean shapeCurrent(ServerLevel level)
        {
            if(!(level.getEntity(original.eva()) instanceof EvaUnit01Entity e)||!EvaMechanicalFrameR52.active(e))return current(level);
            boolean visible=NervMappedPlugMechanicsR52.actualCarrierVisibleR52(e);float release=e.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(e.getLaunchTicks()-1)/18F):0;
            return EvaMechanicalFrameR52.kind(e)==kind&&EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(sourceFingerprint())&&EvaShutdownR30.encode(EvaMechanicalFrameR52.frozenLocalPose(e)).equals(frozenBody)&&EvaFrozenHandsR52.capture(e,1).equals(frozenHands)&&visible==carrierVisible&&EvaMechanicalFrameR52.detachedCarrierR52(e)==detachedCarrier&&(!visible||e.carrierRiseProgress(1)==carrierRise&&release==carrierRelease&&e.recoveryRackR39()==recoveryRack&&EvaMechanicalFrameR52.carrierDeckTravelR52(e)==carrierDeckTravel&&(!detachedCarrier||NervAirTransportManifestR52.same(EvaMechanicalFrameR52.carrierFrameR52(e,1),carrierFrame)));
        }
        public FootSupportFrameR52.Sample sample(RigidTransform frame){return new FootSupportFrameR52.Sample(frame,frame.transformPoint(binding.leftFoot()),frame.transformPoint(binding.rightFoot()),frame.compose(binding.plugInEva()));}
        boolean cargoIntersects(RigidTransform from,RigidTransform to,AABB obstacle)
        {
            for(var s:surfaces)if(s.intersects(from,to,obstacle,.005))return true;
            if(pilotSeat!=null){double angle=NervRigidMeshSweepR52.angular(from,to),r=pilotSeat.length();int n=NervRigidMeshSweepR52.divisions(r,angle,.005);for(int i=0;i<n;i++){var a=from.interpolate(to,(double)i/n).transformPoint(pilotSeat);var b=from.interpolate(to,(double)(i+1)/n).transformPoint(pilotSeat);if(new AABB(a.subtract(pilotHalf),a.add(pilotHalf)).minmax(new AABB(b.subtract(pilotHalf),b.add(pilotHalf))).inflate(NervRigidMeshSweepR52.error(r,angle,n)).intersects(obstacle))return true;}}
            return false;
        }
        boolean cargoIntersects(RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 obstacle,RigidTransform frame)
        {return cargoIntersects(from,to,obstacle,frame,frame);}
        boolean cargoIntersects(RigidTransform from,RigidTransform to,NervRigidMeshSweepR52 obstacle,RigidTransform obstacleFrom,RigidTransform obstacleTo)
        {
            for(var s:surfaces)if(s.intersects(from,to,obstacle,obstacleFrom,obstacleTo,.005,Vec3.ZERO))return true;
            if(pilotSeat!=null){var a=from.transformPoint(pilotSeat);var b=to.transformPoint(pilotSeat);var pilot=new AABB(a.subtract(pilotHalf),a.add(pilotHalf)).minmax(new AABB(b.subtract(pilotHalf),b.add(pilotHalf))).inflate(NervRigidMeshSweepR52.error(pilotSeat.length(),NervRigidMeshSweepR52.angular(from,to),1));if(obstacle.intersects(obstacleFrom,obstacleTo,pilot,.005))return true;}return false;
        }
        List<AABB> cargoEnvelopes(RigidTransform from,RigidTransform to)
        {var out=new ArrayList<AABB>();for(var s:surfaces)out.add(s.envelope(from,to));if(pilotSeat!=null){var a=from.transformPoint(pilotSeat);var b=to.transformPoint(pilotSeat);out.add(new AABB(a.subtract(pilotHalf),a.add(pilotHalf)).minmax(new AABB(b.subtract(pilotHalf),b.add(pilotHalf))).inflate(NervRigidMeshSweepR52.error(pilotSeat.length(),NervRigidMeshSweepR52.angular(from,to),1)));}return List.copyOf(out);}
    }
    /** Read-only before leases/locking; no pose override or carrier rise. */
    public static FlightPickupPreview inspect(ServerLevel l,Original o,Kind kind)
    {
        if(!(l.getEntity(o.eva()) instanceof EvaUnit01Entity e)||!e.isAlive()||e.isExperimentalUnit()||e.getUnitVariant()!=o.variant()||!l.dimension().location().toString().equals(o.dimension()))return null;
        var fleet=EvaFleetSavedData.get(l.getServer()).entry(o.variant()).orElse(null);var deployed=NervRouteRuntimeR52.originalForFlight(l,o.variant(),o.owner());if(fleet==null||!fleet.canonicalId().equals(o.eva())||!fleet.entryPlugId().equals(o.plug())||!AutoSortieR32.missionToken(l).equals(o.mission())&&(deployed==null||!deployed.equals(o)))return null;
        NervHullPreviewR52 hp=null;EvaMechanicalFrameR52.OccupiedCapture occupied=null;EvaMechanicalFrameR52.HullCapture hull=null;FootSupportFrameR52.Binding binding;RigidTransform frame;
        if(EvaMechanicalFrameR52.active(e)){if(EvaMechanicalFrameR52.kind(e)!=kind)return null;binding=EvaMechanicalFrameR52.measuredBinding(e,o);frame=EvaMechanicalFrameR52.frame(e,1);}
        else if(kind==Kind.HULL_ONLY_RECOVERY){hp=NervHullPreviewR52.inspect(e,o);if(hp==null)return null;hull=hp.capture();binding=hp.binding();frame=hp.frame();}
        else{occupied=EvaMechanicalFrameR52.prepareOccupiedRecovery(e,o);if(occupied==null)return null;binding=EvaMechanicalFrameR52.occupiedPreviewBinding(occupied);frame=EvaMechanicalFrameR52.occupiedPreviewFrame(occupied);}
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var body=EvaMechanicalFrameR52.active(e)?EvaMechanicalFrameR52.frozenLocalPose(e):EvaBodyPose.sample(e,1);var hands=EvaFrozenHandsR52.capture(e,1);
        var geometry=provider.evaluate(e.getUnitVariant(),body,EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),hands));var surfaces=new ArrayList<NervRigidMeshSweepR52>();for(var part:geometry.parts())surfaces.add(new NervRigidMeshSweepR52(part.triangles()));
        var anchors=new ArrayList<Vec3>();for(String bone:new String[]{"arm_l","arm_r","leg_l","leg_r","shin_l","shin_r"}){var p=body.matrix(bone).transformPosition(new Vector3f(body.rig.get(bone).pivot()).add(0,0,2.5F/EvaScale.RENDER_SCALE)).mul(EvaScale.RENDER_SCALE);anchors.add(new Vec3(p.x,p.y,p.z));}
        boolean carrierVisible=NervMappedPlugMechanicsR52.actualCarrierVisibleR52(e);
        float rise=e.carrierRiseProgress(1),release=e.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(e.getLaunchTicks()-1)/18F):0;
        boolean detached=EvaMechanicalFrameR52.detachedCarrierR52(e);if(carrierVisible&&!detached){if(capsules==null)return null;for(var part:capsules.carrierParts(e.getUnitVariant(),rise,e.recoveryRackR39(),release,EvaMechanicalFrameR52.carrierDeckTravelR52(e)).values())surfaces.add(new NervRigidMeshSweepR52(part));}
        var contacts=NervAirCradleContactsR52.evaluate(geometry,anchors);anchors=new ArrayList<>(contacts.stream().map(NervAirCradleContactsR52.Contact::centre).toList());
        Vec3 seat=null,half=null;if(kind==Kind.OCCUPIED)
        {
            if(capsules==null||!(l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity plug)||!(l.getEntity(o.pilot()) instanceof LivingEntity pilot)||pilot.getVehicle()!=plug||plug.getVehicle()!=e||plug.getFirstPassenger()!=pilot||!plug.isHatchFullySealed()||!plug.isLockedToEva())return null;
            for(var p:capsules.closedPlugParts(o.variant()).values())surfaces.add(new NervRigidMeshSweepR52(transform(p,binding.plugInEva())));
            seat=binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var box=pilot.getBoundingBox();if(box.getCenter().distanceToSqr(frame.transformPoint(seat))>1e-8)return null;half=new Vec3(box.getXsize()/2,box.getYsize()/2,box.getZsize()/2);
        }
        return new FlightPickupPreview(o,kind,binding,frame,hull,occupied,hp,geometry,anchors,surfaces,seat,half,carrierVisible,rise,release,e.recoveryRackR39(),contacts,EvaShutdownR30.encode(body),hands,EvaMechanicalFrameR52.carrierDeckTravelR52(e),detached,EvaMechanicalFrameR52.carrierFrameR52(e,1));
    }
    /** One immutable actual-source preparation for this call and tick. It
     * grants no actor, SPACE or motion admission by itself. */
    public static final class PreparedSourceSweepR52 {
        private final ServerLevel level;private final long at;private final NervAirframeGeometryR52 geometry;private final FlightPickupPreview preview;private final Frame from,to;private final double rotorFrom,rotorTo;private final boolean movingCargo;private final NervAirframeGeometryR52.Sweep sweep;private final List<AABB> envelopes;
        private PreparedSourceSweepR52(ServerLevel level,NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo){this.level=level;this.at=level==null?Long.MIN_VALUE:level.getGameTime();this.geometry=geometry;this.preview=preview;this.from=from;this.to=to;this.rotorFrom=rotorFrom;this.rotorTo=rotorTo;this.movingCargo=movingCargo;sweep=geometry.sweep(from,to,preview==null?List.of():preview.anchors(),preview==null?List.of():preview.jawAxes(),rotorFrom,rotorTo,.005);var boxes=new ArrayList<AABB>(sweep.envelopes());if(movingCargo){if(preview==null)throw new IllegalArgumentException("Actual captured cargo source required");boxes.addAll(preview.cargoEnvelopes(root(preview,from),root(preview,to)));}envelopes=List.copyOf(boxes);}
        public List<AABB> envelopes(){return envelopes;}
        NervAirframeGeometryR52.Sweep sourceSweepR52(){return sweep;}
        boolean matchesR52(ServerLevel level,NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo){return level!=null&&this.level==level&&at==level.getGameTime()&&this.geometry==geometry&&this.preview==preview&&this.from.equals(from)&&this.to.equals(to)&&Double.compare(this.rotorFrom,rotorFrom)==0&&Double.compare(this.rotorTo,rotorTo)==0&&this.movingCargo==movingCargo;}
    }
    public static PreparedSourceSweepR52 prepareSourceSweepR52(ServerLevel level,NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo){return new PreparedSourceSweepR52(level,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo);}
    static final class ExactBlockObstaclesR52 {private final Set<AABB> tested=new HashSet<>();private int observations;boolean first(AABB box){observations++;return tested.add(box);}int observations(){return observations;}int narrowPhases(){return tested.size();}}
    public static final class CheckedFlightStep
    {
        private final Original original;private final Kind kind;private final FlightPickupPreview preview;private final UUID aircraft;private final Frame from,to;private final RigidTransform cargoFrom,cargoTo;private final NervAirframeGeometryR52.Sweep aircraftSweep;private final List<AABB> envelopes;private final Set<UUID> own;private final long at;private final String manifest;private final NervAirframeGeometryR52 geometry;private final Set<String> spaces;private final double rotorFrom,rotorTo;
        private CheckedFlightStep(ServerLevel l,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,String manifest,boolean movingCargo,Original original,Kind kind,Set<String> spaces,double rotorFrom,double rotorTo,NervAirframeGeometryR52 geometry,List<AABB> preparedEnvelopes)
        {this.geometry=geometry;this.rotorFrom=rotorFrom;this.rotorTo=rotorTo;this.spaces=Set.copyOf(spaces);this.original=original;this.kind=kind;this.preview=preview;this.aircraft=aircraft;this.from=from;this.to=to;cargoFrom=root(preview,from);cargoTo=root(preview,to);this.aircraftSweep=sweep;this.manifest=manifest;at=l.getGameTime();var ids=new HashSet<UUID>();ids.add(aircraft);if(movingCargo)ids.addAll(preview.members());own=Set.copyOf(ids);envelopes=List.copyOf(preparedEnvelopes);}
        public Original original(){return original;}public Kind kind(){return kind;}public FlightPickupPreview preview(){return preview;}public UUID aircraft(){return aircraft;}public Frame from(){return from;}public Frame to(){return to;}public FootSupportFrameR52.Sample fromSample(){return preview.sample(cargoFrom);}public FootSupportFrameR52.Sample toSample(){return preview.sample(cargoTo);}public String manifestFingerprint(){return manifest;}public long checkedAt(){return at;}public List<AABB> envelopes(){return envelopes;}public Set<UUID> members(){return own;}
        public boolean current(ServerLevel l){if(l.getGameTime()!=at||!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.active(p))return false;var actual=NervAircraftFrameR52.frame(p,1);return NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())&&actual.rig().equals(from.rig())&&(from.cargo()==null?actual.cargo()==null:NervAirTransportManifestR52.same(actual.cargo(),from.cargo()))&&NervAircraftFrameR52.rotorClock(p)==rotorFrom&&(from.rig().deployment()==0||preview!=null&&NervAircraftFrameR52.anchors(p).equals(preview.anchors())&&NervAircraftFrameR52.jawAxes(p).equals(preview.jawAxes()));}
        public double rotorFrom(){return rotorFrom;}public double rotorTo(){return rotorTo;}public Set<String> spaces(){return spaces;}
    }
    public static CheckedFlightStep checkStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,boolean movingCargo)
    {if(preview==null||!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||movingCargo&&!preview.shapeCurrent(l))return null;return checkStep(l,manifest,geometry,aircraft,preview,from,to,spaces,bindings,rotorFrom,rotorTo,movingCargo,prepareSourceSweepR52(l,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo));}
    public static CheckedFlightStep checkStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,boolean movingCargo,PreparedSourceSweepR52 prepared)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo))return null;
        if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||movingCargo&&(preview==null||!preview.shapeCurrent(l)))return null;
        var sweep=prepared.sweep;if(preview==null)return null;
        var proof=new CheckedFlightStep(l,aircraft,preview,from,to,sweep,manifest.fingerprint(),movingCargo,preview.original(),preview.kind(),spaces,rotorFrom,rotorTo,geometry,prepared.envelopes());var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null||manifest.directory().resource(id)==null||manifest.directory().resource(id).kind()!=ResourceKind.SPACE)return null;declared.addAll(b.spaces());}
        if(!authorizedDynamicSpacesR52(manifest,proof.envelopes(),spaces,bindings)||movingCargo&&sweep.airframeIntersectsCargo(preview.surfaces,root(preview,from),root(preview,to))||!clear(l,p,preview,from,to,sweep,proof.envelopes(),declared,proof.own,movingCargo))return null;
        return proof;
    }
    public static List<AABB> sourceEnvelopesR52(NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo){return prepareSourceSweepR52(null,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo).envelopes();}
    public static CheckedFlightStep checkAircraftStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,Original original,Kind kind,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo)
    {if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||p.carrying()||from.rig().deployment()!=0||to.rig().deployment()!=0||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||!NervAircraftFrameR52.frame(p,1).rig().equals(from.rig()))return null;return checkAircraftStep(l,manifest,geometry,aircraft,original,kind,from,to,spaces,bindings,rotorFrom,rotorTo,prepareSourceSweepR52(l,geometry,null,from,to,rotorFrom,rotorTo,false));}
    public static CheckedFlightStep checkAircraftStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,Original original,Kind kind,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,PreparedSourceSweepR52 prepared)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,null,from,to,rotorFrom,rotorTo,false))return null;
        if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||p.carrying()||from.rig().deployment()!=0||to.rig().deployment()!=0||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||!NervAircraftFrameR52.frame(p,1).rig().equals(from.rig()))return null;
        var sweep=prepared.sweep;var proof=new CheckedFlightStep(l,aircraft,null,from,to,sweep,manifest.fingerprint(),false,original,kind,spaces,rotorFrom,rotorTo,geometry,prepared.envelopes());var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null)return null;declared.addAll(b.spaces());}
        return authorizedDynamicSpacesR52(manifest,proof.envelopes(),spaces,bindings)&&clear(l,p,null,from,to,sweep,proof.envelopes(),declared,Set.of(aircraft),false)?proof:null;
    }
    public static boolean pathClear(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,boolean movingCargo,int ticks)
    {return pathClear(l,manifest,geometry,aircraft,preview,from,to,spaces,bindings,movingCargo,ticks,null);}
    public static boolean pathClear(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,boolean movingCargo,int ticks,NervFlightGatePlanR52 plan)
    {if(preview==null||!(l.getEntity(aircraft) instanceof UNTransportEntity))return false;try{return pathClear(l,manifest,geometry,aircraft,preview,from,to,spaces,bindings,movingCargo,ticks,plan,prepareSourceSweepR52(l,geometry,preview,from,to,0,ticks,movingCargo));}catch(IllegalArgumentException|IllegalStateException denied){return false;}}
    public static boolean pathClear(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,boolean movingCargo,int ticks,NervFlightGatePlanR52 plan,PreparedSourceSweepR52 prepared)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,preview,from,to,0,ticks,movingCargo))return false;
        if(preview==null||!(l.getEntity(aircraft) instanceof UNTransportEntity p))return false;
        try
        {
            var sweep=prepared.sweep;var boxes=prepared.envelopes();var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null)return false;declared.addAll(b.spaces());}
            if(!authorizedDynamicSpacesR52(manifest,boxes,spaces,bindings))return false;var own=new HashSet<UUID>();own.add(aircraft);if(movingCargo){own.addAll(preview.members());if(sweep.airframeIntersectsCargo(preview.surfaces,from.cargo(),to.cargo()))return false;}return clear(l,p,preview,from,to,sweep,boxes,declared,own,movingCargo,plan);
        }
        catch(IllegalArgumentException|IllegalStateException blocked){return false;}
    }
    private static boolean authorizedDynamicSpacesR52(NervAirTransportManifestR52 manifest,List<AABB> envelopes,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings){if(manifest.directory().dynamicSpacesR52().domains().isEmpty())return true;try{return spaces.containsAll(manifest.directory().dynamicSpacesR52().required(manifest.dimension(),envelopes,bindings));}catch(IllegalArgumentException denied){return false;}}
    private static boolean clear(ServerLevel l,Entity p,FlightPickupPreview preview,Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,List<AABB> envelopes,List<AABB> declared,Set<UUID> own,boolean movingCargo)
    {return clear(l,p,preview,from,to,sweep,envelopes,declared,own,movingCargo,null);}
    private static boolean clear(ServerLevel l,Entity p,FlightPickupPreview preview,Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,List<AABB> envelopes,List<AABB> declared,Set<UUID> own,boolean movingCargo,NervFlightGatePlanR52 plan)
    {
        if(plan!=null&&!plan.current(l))return false;
        var fixedCarriers=detachedCarrierObstacles(l);if(fixedCarriers==null)return false;for(var mesh:fixedCarriers)if(sweep.intersects(mesh.mesh(),mesh.frame())||movingCargo&&preview.cargoIntersects(root(preview,from),root(preview,to),mesh.mesh(),mesh.frame()))return false;
        for(var box:envelopes)if(!NervAirspaceCoverageR52.covered(box,declared)||!EntryPlugEjectionR48.loaded(l,box))return false;
        var seen=new HashSet<UUID>();var blockObstacles=new ExactBlockObstaclesR52();
        java.util.function.Predicate<AABB> sourceIntersects=obstacle->{if(!blockObstacles.first(obstacle)||plan!=null&&plan.isDeclaredSeal(l,obstacle))return false;return sweep.intersects(obstacle)||movingCargo&&preview.cargoIntersects(root(preview,from),root(preview,to),obstacle);};
        if(Boolean.getBoolean("projectseele.r52.flight.originalNativeCollisionQueries")){
            for(var box:envelopes)for(var shape:l.getBlockCollisions(p,box))for(var obstacle:shape.toAabbs())if(sourceIntersects.test(obstacle))return false;
        }else{
            var blocks=BoundedNativeCollisionGroupsR52.clear(envelopes,box->EntryPlugEjectionR48.loaded(l,box),box->{var actual=new ArrayList<AABB>();for(var shape:l.getBlockCollisions(p,box))actual.addAll(shape.toAabbs());return actual;},(piece,obstacle)->sourceIntersects.test(obstacle));
            if(!blocks.clear())return false;
        }
        for(var box:envelopes)
        {
            for(var e:l.getEntities((Entity)null,box.inflate(200),e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
            {
                if(!seen.add(e.getUUID()))continue;List<ObstacleMesh> actual;var planned=plan==null?null:plan.openMeshes(e.getUUID());if(planned!=null){var converted=new ArrayList<ObstacleMesh>();for(var mesh:planned)converted.add(new ObstacleMesh(mesh.geometry(),mesh.frame()));actual=List.copyOf(converted);}else actual=obstacleMeshes(e,sweep.source());if(actual==null){var bounds=e instanceof UNTransportEntity plane?plane.getBoundingBoxForCulling():e.getBoundingBox();if(envelopes.stream().anyMatch(b->b.intersects(bounds)))return false;continue;}
                if(actual.isEmpty()){if(sweep.intersects(e.getBoundingBox())||movingCargo&&preview.cargoIntersects(root(preview,from),root(preview,to),e.getBoundingBox()))return false;}
                else for(var mesh:actual)if(sweep.intersects(mesh.mesh(),mesh.frame(),mesh.endFrame())||movingCargo&&preview.cargoIntersects(root(preview,from),root(preview,to),mesh.mesh(),mesh.frame(),mesh.endFrame()))return false;
            }
        }
        return true;
    }
    public record ObstacleMesh(NervRigidMeshSweepR52 mesh,RigidTransform frame,RigidTransform endFrame){public ObstacleMesh(NervRigidMeshSweepR52 mesh,RigidTransform frame){this(mesh,frame,frame);}}
    private record CarrierMeshes(FullAssemblyGeometryR52.Provider source,float rise,boolean rack,float release,double travel,List<NervRigidMeshSweepR52> meshes){}
    private static final Map<UUID,CarrierMeshes> ACTUAL_CARRIER_MESHES=new HashMap<>();
    private static List<NervRigidMeshSweepR52> carrierMeshes(EvaUnit01Entity e)throws IOException
    {if(capsules==null)installCapsules();float rise=e.carrierRiseProgress(1),release=e.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(e.getLaunchTicks()-1)/18F):0;double travel=EvaMechanicalFrameR52.carrierDeckTravelR52(e);var old=ACTUAL_CARRIER_MESHES.get(e.getUUID());if(old!=null&&old.source()==capsules&&old.rise()==rise&&old.rack()==e.recoveryRackR39()&&old.release()==release&&old.travel()==travel)return old.meshes();var meshes=new ArrayList<NervRigidMeshSweepR52>();for(var part:capsules.carrierParts(e.getUnitVariant(),rise,e.recoveryRackR39(),release,travel).values())meshes.add(new NervRigidMeshSweepR52(part));var result=List.copyOf(meshes);ACTUAL_CARRIER_MESHES.put(e.getUUID(),new CarrierMeshes(capsules,rise,e.recoveryRackR39(),release,travel,result));return result;}
    /** Detached original steel remains at its recorded frame even though its
     * owning body UUID is in the moving membership or far outside the query. */
    public static List<ObstacleMesh> detachedCarrierObstacles(ServerLevel level)
    {
        var context=NervRouteRuntimeR52.flightContext(level);if(context==null)return null;var out=new ArrayList<ObstacleMesh>();for(int v=0;v<3;v++){var unit=context.directory().unit(v);if(unit==null)continue;var hardware=level.getEntity(NervOriginalCarrierR52.proposedIdentityR52(context.directory().epoch(),unit.eva()));if(hardware instanceof NervCarrierPlatformEntity n&&NervOriginalCarrierR52.declared(n)){if(!n.originalCarrierStateR52().getBoolean("Attached"))try{out.addAll(NervOriginalCarrierR52.actualMeshesR52(n));}catch(IOException missing){return null;}continue;}if(!(level.getEntity(unit.eva()) instanceof EvaUnit01Entity e))return null;if(!EvaMechanicalFrameR52.detachedCarrierR52(e)||!NervMappedPlugMechanicsR52.actualCarrierVisibleR52(e))continue;var frame=EvaMechanicalFrameR52.carrierFrameR52(e,1);try{for(var mesh:carrierMeshes(e))out.add(new ObstacleMesh(mesh,frame));}catch(IOException missing){return null;}}return List.copyOf(out);
    }
    private static NervAirframeGeometryR52 actualAircraftSource;
    public static String selectedCageSourceR52(){try{return JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/cage_collision_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject().get("sha256").getAsString();}catch(IOException missing){throw new IllegalStateException("Actual cage source receipt absent",missing);}}
    /** Same real source for closing-door group protection, including planes
     * whose small native entity box does not cover the wing/rotors. */
    public static synchronized List<ObstacleMesh> actualObstacleMeshes(Entity actor)
    {
        if(actor instanceof com.projectseele.entity.YashimaCannonEntityR52 gun)return YashimaCannonMeshR52.actualObstacleMeshesR52(gun);
        try{if(actualAircraftSource==null)actualAircraftSource=NervAirframeGeometryR52.loadClasspath(Map.of("mesh/tv_facilities_r16.json",NervSiloHatchGeometryR52.SOURCE_SHA,"mesh/air_cradle_r31.json","20ca048a0e0cb5a5a4caaed5d8984cd6bef16d769a7a70db5055fa727b6eaa1b"));return obstacleMeshes(actor,actualAircraftSource);}catch(IOException|IllegalArgumentException|IllegalStateException missing){return null;}
    }
    private static List<ObstacleMesh> obstacleMeshes(Entity actor,NervAirframeGeometryR52 source)
    {
        if(actor instanceof NervCarrierPlatformEntity gantry){try{if(NervFootGuideStationR52.declared(gantry))return NervFootGuideStationR52.actualMeshesR52(gantry);if(NervOriginalCarrierR52.declared(gantry))return NervOriginalCarrierR52.actualMeshesR52(gantry);if(gantry.isPlugCrane())return NervCraneGeometryR52.actualObstacleMeshesR52(gantry);if(!gantry.isRestraintGantry()||!gantry.hasDeclaredMachineFrameR52()||!gantry.declaredCollisionSourceR52().equals(selectedCageSourceR52()))return null;return NervPlantMotionR52.actualRenderedMeshesR52(gantry);}catch(IOException|IllegalStateException missing){return null;}}
        if(actor instanceof EvaUnit01Entity eva){var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var body=EvaMechanicalFrameR52.active(eva)?EvaMechanicalFrameR52.frozenLocalPose(eva):EvaBodyPose.sample(eva,1);var hands=EvaFrozenHandsR52.capture(eva,1);var geometry=provider.evaluate(eva.getUnitVariant(),body,EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),hands));var root=EvaMechanicalFrameR52.active(eva)?EvaMechanicalFrameR52.frame(eva,1):NervOwnerPlacementR52.actualRoot(eva);var out=new ArrayList<ObstacleMesh>();for(var part:geometry.parts())out.add(new ObstacleMesh(new NervRigidMeshSweepR52(part.triangles()),root));if(!EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(eva)&&NervMappedPlugMechanicsR52.actualCarrierVisibleR52(eva)){if(capsules==null)try{installCapsules();}catch(IOException missing){return null;}float release=eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(eva.getLaunchTicks()-1)/18F):0;try{for(var mesh:carrierMeshes(eva))out.add(new ObstacleMesh(mesh,EvaMechanicalFrameR52.carrierFrameR52(eva,1)));}catch(IOException missing){return null;}}return List.copyOf(out);}
        if(actor instanceof EntryPlugCarrierEntity plug){if(!plug.isHatchFullySealed())return null;if(capsules==null)try{installCapsules();}catch(IOException missing){return null;}var out=new ArrayList<ObstacleMesh>();for(var part:capsules.closedPlugParts(plug.getAssignedVariant()).values())out.add(new ObstacleMesh(new NervRigidMeshSweepR52(part),plug.getCanonicalTransform()));return List.copyOf(out);}
        if(actor instanceof NervSiloDoorEntity hatch){if(hatch.declaredSpecR52()==null)return null;var out=new ArrayList<ObstacleMesh>();for(var piece:hatch.declaredGeometryR52().pieces(hatch.actualOpenProgressR52()))out.add(new ObstacleMesh(new NervRigidMeshSweepR52(piece.part().xyz()),hatch.actualFrameR52().compose(piece.local())));return List.copyOf(out);}
        if(actor instanceof NervHangarDoorEntity gate){if(gate.declaredStackR52()==null)return null;var out=new ArrayList<ObstacleMesh>();for(var piece:gate.declaredGeometryR52().pieces(gate.actualOpenProgressR52()))out.add(new ObstacleMesh(new NervRigidMeshSweepR52(piece.part().xyz()),gate.actualFrameR52().compose(piece.local())));return List.copyOf(out);}
        if(!(actor instanceof UNTransportEntity plane))return List.of();if(!NervAircraftFrameR52.active(plane)&&(plane.carrying()||plane.rig(1)!=0))return null;
        var frame=NervAircraftFrameR52.active(plane)?NervAircraftFrameR52.frame(plane,1):new Frame(NervAircraftFrameR52.actual(plane),null,new Rig(plane.hoistDistance(),0,1));var out=new ArrayList<ObstacleMesh>();NervAircraftFrameR52.actual(plane);
        if(plane.groundCart()){var part=source.originalGroundCarrier();if(part==null)return null;return List.of(new ObstacleMesh(new NervRigidMeshSweepR52(part.xyz()),frame.plane()));}
        double clock=NervAircraftFrameR52.active(plane)?NervAircraftFrameR52.rotorClock(plane):plane.level().getGameTime()%3600;out.add(new ObstacleMesh(source.bodyMesh(),frame.plane()));for(int i=0;i<4;i++)out.add(new ObstacleMesh(source.rotorMesh(i),frame.plane().compose(source.rotorLocalFrame(i,clock)),frame.plane().compose(source.rotorLocalFrame(i,clock+1))));var parts=source.parts(frame,NervAircraftFrameR52.anchors(plane),NervAircraftFrameR52.jawAxes(plane),clock);for(int i=5;i<parts.size();i++)out.add(new ObstacleMesh(new NervRigidMeshSweepR52(parts.get(i).xyz()),frame.plane()));return List.copyOf(out);
    }
    public static final class CheckedPickup
    {
        private final CheckedFlightStep step;private CheckedPickup(CheckedFlightStep step){this.step=step;}public FlightPickupPreview preview(){return step.preview();}public Original original(){return step.original();}public Kind kind(){return step.kind();}public UUID aircraft(){return step.aircraft();}public Frame frame(){return step.to();}public boolean current(ServerLevel l){return step.current(l)&&preview().current(l);}
    }
    /** A stopped actor remains on its own real support while an empty plane
     * approaches. This is a pose hold, not aircraft carriage or a cargo frame
     * invented at the aircraft's stand. */
    public static final class CheckedPickupHold
    {
        private final CheckedFlightStep aircraft;private final FlightPickupPreview preview;private final UUID task;
        private CheckedPickupHold(CheckedFlightStep aircraft,FlightPickupPreview preview,UUID task){this.aircraft=aircraft;this.preview=preview;this.task=task;}
        public UUID task(){return task;}public UUID aircraft(){return aircraft.aircraft();}public Original original(){return preview.original();}public Kind kind(){return preview.kind();}public FlightPickupPreview preview(){return preview;}
        public boolean current(ServerLevel level){return aircraft.current(level)&&preview.current(level)&&positiveBearing(level,preview);}
    }
    public static CheckedPickupHold holdPickup(ServerLevel level,NervRouteReservationsR52 pool,UUID task,CheckedFlightStep aircraft,FlightPickupPreview preview,Set<String> cargoSpaces,Map<String,NervRouteNativeR52.Binding> bindings)
    {
        var context=NervRouteRuntimeR52.flightContext(level);var lease=pool.queryFlight(task);if(context==null||context.pool()!=pool||lease==null||preview==null||aircraft==null||!aircraft.current(level)||!preview.current(level)||!lease.original().equals(preview.original())||lease.kind()!=preview.kind()||!lease.aircraft().equals(aircraft.aircraft())||aircraft.from().cargo()!=null||aircraft.to().cargo()!=null||aircraft.from().rig().deployment()!=0||!lease.spaces().containsAll(cargoSpaces)||!positiveBearing(level,preview))return null;
        var boxes=preview.cargoEnvelopes(preview.root(),preview.root());var declared=new ArrayList<AABB>();for(String id:cargoSpaces){var b=bindings.get(id);if(b==null)return null;declared.addAll(b.spaces());}var own=new HashSet<>(preview.members());own.add(aircraft.aircraft());var eva=level.getEntity(preview.original().eva());
        for(var box:boxes){if(!NervAirspaceCoverageR52.covered(box,declared)||!EntryPlugEjectionR48.loaded(level,box))return null;for(var shape:level.getBlockCollisions(eva,box))for(var obstacle:shape.toAabbs())if(preview.cargoIntersects(preview.root(),preview.root(),obstacle))return null;for(var e:level.getEntities((Entity)null,box,e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith())))if(preview.cargoIntersects(preview.root(),preview.root(),e.getBoundingBox()))return null;}
        return new CheckedPickupHold(aircraft,preview,task);
    }
    private static boolean positiveBearing(ServerLevel level,FlightPickupPreview preview)
    {
        if(!(level.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva)||!eva.onGround()&&!EvaMechanicalFrameR52.active(eva))return false;
        if(preview.kind()==Kind.OCCUPIED){var sample=preview.sample(preview.root());return contact(level,eva,sample.leftContact())&&contact(level,eva,sample.rightContact());}
        double low=Double.POSITIVE_INFINITY;var points=new ArrayList<Vec3>();for(var part:preview.geometry().parts())for(var p:part.vertices()){var at=preview.root().transformPoint(p);low=Math.min(low,at.y);points.add(at);}for(var p:points)if(p.y<=low+.002&&contact(level,eva,p))return true;return false;
    }
    private static boolean contact(ServerLevel level,Entity entity,Vec3 p)
    {var pos=net.minecraft.core.BlockPos.containing(p.x,p.y-.002,p.z);if(!level.hasChunkAt(pos))return false;for(var box:level.getBlockState(pos).getCollisionShape(level,pos,net.minecraft.world.phys.shapes.CollisionContext.of(entity)).toAabbs()){var b=box.move(pos);if(p.x>=b.minX&&p.x<=b.maxX&&p.z>=b.minZ&&p.z<=b.maxZ&&Math.abs(p.y-b.maxY)<=.002)return true;}return false;}
    public static CheckedPickup pickup(ServerLevel l,CheckedFlightStep fullClamp)
    {
        if(fullClamp==null||!fullClamp.current(l)||!fullClamp.preview().current(l)||fullClamp.to().rig().deployment()!=1||fullClamp.to().rig().jaws()!=0||!NervAirTransportManifestR52.same(fullClamp.preview().root(),fullClamp.to().cargo()))return null;var parts=fullClamp.geometry.parts(fullClamp.to(),fullClamp.preview().anchors(),fullClamp.preview().jawAxes(),fullClamp.rotorFrom());int index=0;
        for(var contact:fullClamp.preview().contacts){String name="jaw/"+(index/2)+"/"+(index%2);var part=parts.stream().filter(x->x.name().equals(name)).findFirst().orElse(null);if(part==null)return null;var target=fullClamp.preview().root().transformPoint(contact.skin());double closest=Double.POSITIVE_INFINITY;var xyz=part.xyz();for(int n=0;n<xyz.length;n+=9){var a=fullClamp.to().plane().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));var b=fullClamp.to().plane().transformPoint(new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]));var c=fullClamp.to().plane().transformPoint(new Vec3(xyz[n+6],xyz[n+7],xyz[n+8]));closest=Math.min(closest,NervAirCradleContactsR52.closest(target,a,b,c).distanceToSqr(target));}if(closest>1e-6)return null;index++;}
        return new CheckedPickup(fullClamp);
    }
    public static final class CheckedAirReceiver
    {
        private final CheckedFlightStep step;private final Receiver receiver;private CheckedAirReceiver(CheckedFlightStep step,Receiver r){this.step=step;receiver=r;}public CheckedFlightStep step(){return step;}public Original original(){return step.original();}public Kind kind(){return step.kind();}public String port(){return receiver.port();}public RigidTransform stoppedFrame(){return receiver.stopped();}public boolean current(ServerLevel l){return step.current(l)&&NervAirTransportManifestR52.same(step.to().cargo(),stoppedFrame());}
    }
    public static CheckedAirReceiver receiver(ServerLevel l,CheckedFlightStep stopped,Receiver receiver,Owner owner,CompoundTag data)
    {if(stopped==null||!stopped.current(l)||receiver==null||receiver.delivery()||!NervAirTransportManifestR52.same(stopped.to().cargo(),receiver.stopped())||stopped.to().rig().jaws()!=1||!owner.receiverReady(l,receiver.port(),stopped.original(),stopped.kind(),receiver.stopped(),data))return null;return new CheckedAirReceiver(stopped,receiver);}
    public static final class CheckedAirDelivery
    {
        private final CheckedFlightStep step;private final Receiver destination;private CheckedAirDelivery(CheckedFlightStep step,Receiver destination){this.step=step;this.destination=destination;}
        public CheckedFlightStep step(){return step;}public Original original(){return step.original();}public Kind kind(){return step.kind();}public String destination(){return destination.port();}public RigidTransform stoppedFrame(){return destination.stopped();}
        public boolean current(ServerLevel l){return step.current(l)&&supportedDelivery(l,step,destination);}
    }
    /** Both measured sole centres must bear on the current collision surface
     * of Root's exact saved cells. A timer or heightmap cannot grant release. */
    public static boolean supportedDelivery(ServerLevel l,CheckedFlightStep stopped,Receiver receiver)
    {return stopped!=null&&stopped.current(l)&&stopped.to().rig().jaws()==1&&deliverySupportReady(l,stopped.preview(),stopped.to().cargo(),receiver);}
    public static boolean deliverySupportReady(ServerLevel l,FlightPickupPreview preview,RigidTransform stopped,Receiver receiver)
    {
        if(preview==null||preview.kind()!=Kind.OCCUPIED||receiver==null||!receiver.delivery()||!NervAirTransportManifestR52.same(stopped,receiver.stopped())||!(l.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva)||!NervAirTransportManifestR52.same(NervOwnerPlacementR52.actualRoot(eva),receiver.stopped()))return false;
        for(var c:receiver.supports())if(!l.hasChunkAt(c.position())||!net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(l.getBlockState(c.position())).equals(c.state()))return false;
        var sample=preview.sample(stopped);for(var foot:List.of(sample.leftContact(),sample.rightContact()))
        {
            boolean support=false;for(var c:receiver.supports())for(var b:l.getBlockState(c.position()).getCollisionShape(l,c.position(),net.minecraft.world.phys.shapes.CollisionContext.of(eva)).toAabbs())
            {var world=b.move(c.position());if(foot.x>world.minX&&foot.x<world.maxX&&foot.z>world.minZ&&foot.z<world.maxZ&&Math.abs(foot.y-world.maxY)<=.002)support=true;}
            if(!support)return false;
        }
        return true;
    }
    public static CheckedAirDelivery delivery(ServerLevel l,CheckedFlightStep stopped,Receiver destination)
    {return supportedDelivery(l,stopped,destination)?new CheckedAirDelivery(stopped,destination):null;}
    private static boolean contains(AABB a,AABB b){return a.minX<=b.minX&&a.minY<=b.minY&&a.minZ<=b.minZ&&a.maxX>=b.maxX&&a.maxY>=b.maxY&&a.maxZ>=b.maxZ;}
    private static double[] transform(double[] xyz,RigidTransform f){var out=xyz.clone();for(int i=0;i<out.length;i+=3){var p=f.transformPoint(new Vec3(out[i],out[i+1],out[i+2]));out[i]=p.x;out[i+1]=p.y;out[i+2]=p.z;}return out;}
    private static RigidTransform root(FlightPickupPreview preview,Frame frame){return frame.cargo()!=null?frame.cargo():preview==null?null:preview.root();}
    private NervFlightProofR52(){}
}
