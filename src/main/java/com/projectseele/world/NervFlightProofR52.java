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
        default boolean closeIdleAirshaftGateR53(ServerLevel level,String id){return false;}
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
        var receipt=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));capsules=FullAssemblyGeometryR52.selectedClasspathProviderR52(hashes);
    }
    static EvaOriginalMeshGeometryR52.Geometry occupiedPoseGeometryR53(EvaUnit01Entity eva,
            EvaBodyPose.Sample body,EvaOriginalMeshGeometryR52.Geometry geometry,LivingEntity pilot)
    {
        if(capsules==null)throw new IllegalStateException("Original capsule geometry unavailable");
        var parts=new ArrayList<>(geometry.parts());
        var socket=EvaMechanicalFrameR52.emptySocketReferenceR52(body,EvaRifleKinematics.frameWorldR52(Vec3.ZERO,180),EvaDorsalProfile.of(eva));
        for(var entry:capsules.closedPlugParts(eva.getUnitVariant()).entrySet())
        {
            var xyz=transform(entry.getValue(),socket);var mesh=new NervRigidMeshSweepR52(xyz);
            parts.add(new EvaOriginalMeshGeometryR52.Part("capsule/"+entry.getKey(),"original-capsule",capsules.sourceFingerprint(),xyz,mesh.bounds()));
        }
        var seat=socket.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var bounds=pilot.getBoundingBox();
        double x=bounds.getXsize()/2,y=bounds.getYsize()/2,z=bounds.getZsize()/2;
        var root=EvaMechanicalFrameR52.frame(eva,1);var worldSeat=root.transformPoint(seat);var inverse=root.inverse();
        var corners=new Vec3[8];for(int i=0;i<8;i++)corners[i]=inverse.transformPoint(worldSeat.add((i&1)==0?-x:x,(i&2)==0?-y:y,(i&4)==0?-z:z));
        int[] indices={0,2,3,0,3,1,4,5,7,4,7,6,0,1,5,0,5,4,2,6,7,2,7,3,0,4,6,0,6,2,1,3,7,1,7,5};
        var xyz=new double[indices.length*3];for(int i=0;i<indices.length;i++){var v=corners[indices[i]];xyz[i*3]=v.x;xyz[i*3+1]=v.y;xyz[i*3+2]=v.z;}
        parts.add(new EvaOriginalMeshGeometryR52.Part("pilot","original-pilot",geometry.sourceFingerprint(),xyz,new NervRigidMeshSweepR52(xyz).bounds()));
        return new EvaOriginalMeshGeometryR52.Geometry(eva.getUnitVariant(),geometry.sourceFingerprint(),parts);
    }
    private static boolean frozenActorR53(EvaUnit01Entity eva)
    {
        return eva.isAlive()&&!eva.isExperimentalUnit()&&EvaShutdownR30.disabled(eva)&&!eva.isBerserk()
                &&!com.projectseele.physics.CombatBodyDynamics.active(eva)&&!EvaMechanicalFrameR52.active(eva)
                &&!EvaAirTransportR31.active(eva)&&!eva.hasActiveCarrierMotion()&&!eva.isLaunchSequenceActive();
    }
    private static final class FrozenActorContactR53
    {
        final UUID actor;final int variant;final RigidTransform frame;final CompoundTag body,hands;
        final String source;final List<NervRigidMeshSweepR52> meshes;final EvaOriginalMeshGeometryR52.Geometry moving;final RigidTransform captured;
        java.util.concurrent.CompletableFuture<NervRescueActorEgressR53> egress;String hold="immutable actor contact source not prepared";
        final Set<NervRigidMeshSweepR52> matchedMeshes=Collections.newSetFromMap(new WeakHashMap<>());
        FrozenActorContactR53(EvaUnit01Entity actor,RigidTransform frame,CompoundTag body,CompoundTag hands,
                EvaOriginalMeshGeometryR52.Geometry moving,RigidTransform captured,EvaOriginalMeshGeometryR52.Geometry obstacle)
        {
            this.actor=actor.getUUID();variant=actor.getUnitVariant();this.frame=frame;this.body=body.copy();this.hands=hands.copy();
            source=obstacle.sourceFingerprint();meshes=NervObstacleMeshesR53.body(obstacle);matchedMeshes.addAll(meshes);
            this.moving=moving;this.captured=captured;
        }
        boolean separates(RigidTransform from,RigidTransform to)
        {
            if(egress==null)
            {
                // Capture immutable values only: no live actor, world or owner
                // is reachable from the worker calculation.
                var bodySource=moving;var initial=captured;var obstacles=meshes;var fixed=frame;
                try{egress=NervGeometryWorkR53.submit(()->true,()->new NervRescueActorEgressR53(bodySource,initial,obstacles,fixed));}
                catch(java.util.concurrent.RejectedExecutionException busy){hold="immutable geometry worker busy";return false;}
            }
            if(!egress.isDone()){hold="immutable actor contact intervals preparing";return false;}
            try{var proof=egress.join();boolean clear=proof.separates(from,to);hold=clear?"":"new actor contact or movement outside captured vertical exit";return clear;}
            catch(java.util.concurrent.CompletionException|java.util.concurrent.CancellationException invalid)
            {hold="immutable actor contact source rejected: "+(invalid.getCause()==null?invalid:invalid.getCause());return false;}
        }
        boolean current(ServerLevel level,Entity observed,ObstacleMesh mesh)
        {
            if(!(observed instanceof EvaUnit01Entity eva)||!actor.equals(eva.getUUID())||level.getEntity(actor)!=eva
                    ||eva.getUnitVariant()!=variant||!frozenActorR53(eva)||!frame.equals(NervOwnerPlacementR52.actualRoot(eva))
                    ||!frame.equals(mesh.frame())||!frame.equals(mesh.endFrame())
                    ||!source.equals(EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52().sourceFingerprint())
                    ||!body.equals(EvaShutdownR30.encode(EvaBodyPose.sample(eva,1)))||!hands.equals(EvaFrozenHandsR52.capture(eva,1)))
            {hold="captured actor identity/pose/root/source changed";return false;}
            if(matchedMeshes.contains(mesh.mesh()))return true;
            // Geometry cache eviction may rebuild the same immutable source.
            var actual=mesh.mesh().triangles();
            for(var sourceMesh:meshes)if(Arrays.equals(sourceMesh.triangles(),actual)){matchedMeshes.add(mesh.mesh());return true;}
            hold="obstacle surface is not the captured actor body";return false;
        }
    }
    static boolean fixedHatchMemberR54(NervSiloHatchGeometryR52 source,RigidTransform frame,ObstacleMesh obstacle)
    {
        if(!obstacle.frame().equals(obstacle.endFrame()))return false;
        for(var piece:source.pieces(0))if(!piece.moving()&&frame.compose(piece.local()).equals(obstacle.frame()))
        {
            var mesh=NervObstacleMeshesR53.part(piece.part());
            if(mesh==obstacle.mesh()||Arrays.equals(mesh.triangles(),obstacle.mesh().triangles()))return true;
        }
        return false;
    }
    public static final class FlightPickupPreview
    {
        private NervRescueContactEgressR53 wreckEgress;
        private Set<AABB> initialWreckShapes;
        private boolean pickupSupportCapturedR54;
        private Map<UUID,FrozenActorContactR53> initialActorContacts=Map.of();
        private final Map<UUID,NervStationaryActorContactR54> initialStationaryContactsR54=new HashMap<>();
        private FrozenActorContactR53 retractActorR53;
        private Frame retractStartR53;
        private Map<NervRigidMeshSweepR52,Set<String>> retractPairsR53=Map.of();

        private final Original original;private final Kind kind;private final FootSupportFrameR52.Binding binding;private final RigidTransform root;
        private final EvaMechanicalFrameR52.HullCapture hull;private final EvaMechanicalFrameR52.OccupiedCapture occupied;private final NervHullPreviewR52 hullPreview;
        private final boolean carrierVisible,detachedCarrier;private final RigidTransform carrierFrame;private final float carrierRise,carrierRelease;private final boolean recoveryRack;private final double carrierDeckTravel;private final CompoundTag frozenBody,frozenHands;
        private final EvaOriginalMeshGeometryR52.Geometry geometry;private final List<Vec3> anchors;private final List<NervAirCradleContactsR52.Contact> contacts;private final List<NervRigidMeshSweepR52> surfaces;private final Vec3 pilotSeat,pilotHalf;
        private FlightPickupPreview(Original o,Kind k,FootSupportFrameR52.Binding b,RigidTransform r,EvaMechanicalFrameR52.HullCapture h,EvaMechanicalFrameR52.OccupiedCapture p,NervHullPreviewR52 hp,EvaOriginalMeshGeometryR52.Geometry g,List<Vec3> a,List<NervRigidMeshSweepR52> s,Vec3 seat,Vec3 half,boolean visible,float rise,float release,boolean rack,List<NervAirCradleContactsR52.Contact> contacts,CompoundTag body,CompoundTag hands,double deckTravel,boolean detached,RigidTransform carrier,boolean wreck,Set<AABB> initialWreckShapes)
        {this.initialWreckShapes=Set.copyOf(initialWreckShapes);wreckEgress=wreck?new NervRescueContactEgressR53(g,this.initialWreckShapes):null;detachedCarrier=detached;carrierFrame=carrier;carrierDeckTravel=deckTravel;frozenBody=body.copy();frozenHands=hands.copy();carrierVisible=visible;carrierRise=rise;carrierRelease=release;recoveryRack=rack;this.contacts=List.copyOf(contacts);original=o;kind=k;binding=b;root=r;hull=h;occupied=p;hullPreview=hp;geometry=g;anchors=List.copyOf(a);surfaces=List.copyOf(s);pilotSeat=seat;pilotHalf=half;}
        public FlightPickupPreview withContactsR53(List<NervAirCradleContactsR52.Contact> selected)
        {
            if(!NervAirCradleContactsR52.valid(geometry,selected))throw new IllegalArgumentException("Invalid original skin contacts");
            var next=new FlightPickupPreview(original,kind,binding,root,hull,occupied,hullPreview,geometry,
                    selected.stream().map(NervAirCradleContactsR52.Contact::centre).toList(),surfaces,pilotSeat,pilotHalf,
                    carrierVisible,carrierRise,carrierRelease,recoveryRack,selected,frozenBody,frozenHands,carrierDeckTravel,
                    detachedCarrier,carrierFrame,wreckEgress!=null,initialWreckShapes);
            next.initialActorContacts=initialActorContacts;next.initialStationaryContactsR54.putAll(initialStationaryContactsR54);
            next.pickupSupportCapturedR54=pickupSupportCapturedR54;return next;
        }
        public boolean capturePickupSupportR54(ServerLevel level,Entity aircraft,Frame stopped)
        {
            if(pickupSupportCapturedR54)return true;
            if(stopped.rig().deployment()!=0||!current(level)||!(aircraft instanceof UNTransportEntity)
                    ||!NervAirTransportManifestR52.same(stopped.plane(),NervAircraftFrameR52.actual((UNTransportEntity)aircraft))
                    ||stopped.cargo()!=null&&!NervAirTransportManifestR52.same(stopped.cargo(),root))return false;
            if(!NervTraversalPolicyR53.strict(level)){pickupSupportCapturedR54=true;return true;}
            // The waiting owner can clear the shutdown flag while retaining
            // this exact mechanical capture. Admission follows that capture,
            // not its obsolete damage mode. Read with the flight's same actor
            // collision context immediately before the first jaw deployment.
            var assembly=completeAssemblyR54();
            var initial=captureNativeSupportR54(level,aircraft,NervObstacleMeshesR53.body(assembly),root);
            if(initial==null)return false;
            initialWreckShapes=Set.copyOf(initial);wreckEgress=new NervRescueContactEgressR53(assembly,initialWreckShapes);
            pickupSupportCapturedR54=true;return true;
        }
        public void saveContactsR53(CompoundTag data)
        {
            var tag=new CompoundTag();tag.putString("Source",sourceFingerprint());tag.put("Body",frozenBody.copy());tag.put("Hands",frozenHands.copy());
            var list=new net.minecraft.nbt.ListTag();
            for(var c:contacts){var t=new CompoundTag();t.putString("Bone",c.bone());writeContactVectorR53(t,"Skin",c.skin());writeContactVectorR53(t,"Centre",c.centre());writeContactVectorR53(t,"Axis",c.axis());list.add(t);}
            tag.put("Contacts",list);data.put("RescueSkinContactsR53",tag);
        }
        public boolean beginClampRetractionR53(ServerLevel level,NervAirframeGeometryR52 source,Frame current,Frame next,CompoundTag data)
        {
            if(!NervTraversalPolicyR53.strict(level))return false;
            var sweep=source.sweep(current,next,anchors,jawAxes(),0,1,.005);var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
            for(int variant=0;variant<3;variant++)
            {
                var entry=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
                if(entry==null||entry.canonicalId().equals(original.eva())||!(level.getEntity(entry.canonicalId()) instanceof EvaUnit01Entity actor)||!frozenActorR53(actor))continue;
                var otherRoot=NervOwnerPlacementR52.actualRoot(actor);var pose=EvaBodyPose.sample(actor,1);var hands=EvaFrozenHandsR52.capture(actor,1);
                var other=EvaMechanicalFrameR52.serviceSourceHeldR52(actor)?EvaMechanicalFrameR52.serviceGeometryR52(actor):provider.evaluate(variant,pose,EvaFrozenHandsR52.decode(variant,provider.handContractFingerprint(variant),provider.handJoints(variant),hands));
                if(!NervObstacleMeshesR53.body(other).stream().anyMatch(mesh->sweep.intersects(mesh,otherRoot)))continue;
                var capture=new CompoundTag();capture.putUUID("Actor",actor.getUUID());capture.putInt("Variant",variant);
                capture.put("Body",EvaShutdownR30.encode(pose));capture.put("Hands",hands.copy());capture.putString("Source",other.sourceFingerprint());
                capture.put("Root",NervAircraftFrameR52.encodeRigid(otherRoot));NervAircraftFrameR52.putFrame(capture,"Start",current);
                data.put("RescueClampRetractionR53",capture);saveContactsR53(data);return true;
            }
            return false;
        }
        public boolean prepareClampRetractionR53(ServerLevel level,NervAirframeGeometryR52 source,CompoundTag data)
        {
            if(!NervTraversalPolicyR53.strict(level))return true;
            var tag=data.getCompound("RescueClampRetractionR53");if(!tag.hasUUID("Actor")||!(level.getEntity(tag.getUUID("Actor")) instanceof EvaUnit01Entity actor)||!frozenActorR53(actor))return false;
            var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var pose=EvaBodyPose.sample(actor,1);var hands=EvaFrozenHandsR52.capture(actor,1);var frame=NervOwnerPlacementR52.actualRoot(actor);
            var savedRoot=NervAircraftFrameR52.decodeRigid(tag.getCompound("Root"));
            // NBT canonicalizes signed zero. Compare the same numeric rotation,
            // without broadening position or angle tolerances.
            if(actor.getUnitVariant()!=tag.getInt("Variant")||!tag.getString("Source").equals(provider.sourceFingerprint())||!tag.getCompound("Body").equals(EvaShutdownR30.encode(pose))||!tag.getCompound("Hands").equals(hands)
                    ||!savedRoot.translation().equals(frame.translation())||savedRoot.qx()!=frame.qx()||savedRoot.qy()!=frame.qy()||savedRoot.qz()!=frame.qz()||savedRoot.qw()!=frame.qw())return false;
            var other=EvaMechanicalFrameR52.serviceSourceHeldR52(actor)?EvaMechanicalFrameR52.serviceGeometryR52(actor):provider.evaluate(actor.getUnitVariant(),pose,EvaFrozenHandsR52.decode(actor.getUnitVariant(),provider.handContractFingerprint(actor.getUnitVariant()),provider.handJoints(actor.getUnitVariant()),hands));
            if(retractActorR53!=null&&retractPairsR53.size()==retractActorR53.meshes.size()&&retractActorR53.meshes.equals(NervObstacleMeshesR53.body(other)))return true;
            var start=NervAircraftFrameR52.decode(tag.getCompound("Start"));var zero=new Frame(start.plane(),start.cargo(),new Rig(start.rig().hoist(),0,1));
            var initial=source.cradleParts(start,anchors,jawAxes(),true);var stowed=source.cradleParts(zero,anchors,jawAxes(),true);var pairs=new HashMap<NervRigidMeshSweepR52,Set<String>>();
            var bodyMeshes=NervObstacleMeshesR53.body(other);var allowed=new HashSet<String>();
            // A saved rig can already be inside the body, past its surface.
            // Retraction may cross that same surface on its way out. The six
            // original jaws have one finite return to a verified clear zero.
            for(var part:initial)if(part.name().startsWith("jaw/"))allowed.add(part.name());
            for(var part:stowed)if(allowed.contains(part.name()))
                for(var mesh:bodyMeshes)if(new NervRigidMeshSweepR52(part.xyz()).intersects(zero.plane(),zero.plane(),mesh,frame,frame,.005,Vec3.ZERO))return false;
            if(!allowed.isEmpty())for(var mesh:bodyMeshes)pairs.put(mesh,Set.copyOf(allowed));
            retractActorR53=new FrozenActorContactR53(actor,frame,tag.getCompound("Body"),hands,geometry,root,other);
            retractStartR53=start;retractPairsR53=Map.copyOf(pairs);return true;
        }
        private boolean existingClampRetractionR53(ServerLevel level,Entity actor,Frame from,Frame to,ObstacleMesh obstacle,NervAirframeGeometryR52 source,double rotorClock)
        {
            if(retractActorR53==null||!retractActorR53.current(level,actor,obstacle)||!from.plane().equals(retractStartR53.plane())||!to.plane().equals(from.plane())
                    ||!Objects.equals(from.cargo(),retractStartR53.cargo())||!Objects.equals(to.cargo(),from.cargo())
                    ||from.rig().hoist()!=retractStartR53.rig().hoist()||to.rig().hoist()!=from.rig().hoist()
                    ||from.rig().deployment()>retractStartR53.rig().deployment()||to.rig().deployment()>from.rig().deployment()
                    ||from.rig().jaws()!=1-from.rig().deployment()||to.rig().jaws()!=1-to.rig().deployment())return false;
            var allowed=new HashSet<String>();for(var parts:retractPairsR53.values())allowed.addAll(parts);
            if(allowed.isEmpty())return false;
            return !source.excludingCradlePartsR53(from,to,anchors,jawAxes(),allowed,rotorClock).intersects(obstacle.mesh(),obstacle.frame(),obstacle.endFrame());
        }
        public java.util.concurrent.CompletableFuture<ClampContactSelectionR53> selectClampContactsR53(
                ServerLevel level,UUID aircraft,NervAirframeGeometryR52 source,Frame stopped)
        {
            if(stopped.rig().deployment()!=0||!current(level))throw new IllegalStateException("Contact reselection requires actual retracted original clamp");
            var bounds=NervRigidMeshSweepR52.transformed(geometry.bounds(),root).inflate(10)
                    .minmax(new AABB(stopped.plane().translation(),stopped.plane().translation()).inflate(16));
            if(!EntryPlugEjectionR48.loaded(level,bounds))return null;
            var obstacles=new ArrayList<ObstacleMesh>();var labels=new ArrayList<String>();var actorBoxes=new ArrayList<AABB>();var own=new HashSet<>(members());own.add(aircraft);
            for(var actor:level.getEntities((Entity)null,bounds,e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
            {
                var meshes=obstacleMeshes(actor,source);
                if(meshes!=null&&!meshes.isEmpty()){obstacles.addAll(meshes);for(var ignored:meshes)labels.add(actor.getUUID().toString());}
                else actorBoxes.add(actor.getBoundingBox());
            }
            var fixed=detachedCarrierObstacles(level);if(fixed==null)return null;obstacles.addAll(fixed);for(var ignored:fixed)labels.add("original carrier");
            actorBoxes.addAll(NativeCollisionShapesR53.read(level,level.getEntity(aircraft),bounds));var blocks=List.copyOf(actorBoxes);
            var capturedObstacles=List.copyOf(obstacles);var capturedLabels=List.copyOf(labels);var bodySource=geometry;var hints=contacts.stream().map(NervAirCradleContactsR52.Contact::skin).toList();
            var plane=stopped.plane();var cargo=root;float hoist=stopped.rig().hoist();
            return NervGeometryWorkR53.submit(()->true,()->{var rejection=new String[]{"No original skin candidates"};var selected=NervAirCradleContactsR52.evaluate(bodySource,hints,candidate->{
                var a=candidate.stream().map(NervAirCradleContactsR52.Contact::centre).toList();var axes=candidate.stream().map(NervAirCradleContactsR52.Contact::axis).toList();
                // Reject the final collar/spine first, then prove every real clamp interval.
                for(int step=20;step>=0;step--)
                {
                    float t=step==20?1:step/20F,u=step==20?1:(step+1)/20F;
                    var from=new Frame(plane,cargo,new Rig(hoist,t,1-t));var to=new Frame(plane,cargo,new Rig(hoist,u,1-u));
                    var sweep=source.sweep(from,to,a,axes,0,1,.005);
                    for(int i=0;i<capturedObstacles.size();i++){var mesh=capturedObstacles.get(i);if(sweep.intersects(mesh.mesh(),mesh.frame(),mesh.endFrame())){rejection[0]="Clamp step "+step+" actor "+capturedLabels.get(i);return false;}}
                    for(var block:blocks)if(sweep.intersects(block)){rejection[0]="Clamp step "+step+" native shape "+block;return false;}
                }
                return true;
            });return new ClampContactSelectionR53(selected,selected.isEmpty()?rejection[0]:"");});
        }
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
        boolean existingWreckContactR53(RigidTransform from,RigidTransform to,AABB obstacle)
        {return wreckEgress!=null&&initialWreckShapes.contains(obstacle)&&wreckEgress.separates(root,from,to,obstacle);}
        private void captureActorContactsR53(ServerLevel level)
        {
            if(!(level.getEntity(original.eva()) instanceof EvaUnit01Entity stopped)||!EvaShutdownR30.disabled(stopped)||stopped.isBerserk()||com.projectseele.physics.CombatBodyDynamics.active(stopped)||!current(level))return;
            var captured=new HashMap<UUID,FrozenActorContactR53>();var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
            var ownBounds=NervRigidMeshSweepR52.transformed(geometry.bounds(),root);
            for(int variant=0;variant<3;variant++)
            {
                var entry=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
                if(entry==null||entry.canonicalId().equals(original.eva())
                        ||!(level.getEntity(entry.canonicalId()) instanceof EvaUnit01Entity actor)||!frozenActorR53(actor))continue;
                var otherRoot=NervOwnerPlacementR52.actualRoot(actor);
                if(!ownBounds.inflate(200).contains(otherRoot.translation()))continue;
                var body=EvaBodyPose.sample(actor,1);var hands=EvaFrozenHandsR52.capture(actor,1);
                var other=EvaMechanicalFrameR52.serviceSourceHeldR52(actor)?EvaMechanicalFrameR52.serviceGeometryR52(actor):provider.evaluate(variant,body,EvaFrozenHandsR52.decode(variant,provider.handContractFingerprint(variant),provider.handJoints(variant),hands));
                if(!ownBounds.intersects(NervRigidMeshSweepR52.transformed(other.bounds(),otherRoot)))continue;
                captured.put(actor.getUUID(),new FrozenActorContactR53(actor,otherRoot,EvaShutdownR30.encode(body),hands,completeAssemblyR54(),root,other));
            }
            initialActorContacts=Map.copyOf(captured);
        }
        public String actorContactHoldR53()
        {return initialActorContacts.values().stream().filter(c->!c.hold.isEmpty()).map(c->c.actor+": "+c.hold).collect(java.util.stream.Collectors.joining("; "));}
        boolean existingActorContactR53(ServerLevel level,Entity actor,RigidTransform from,RigidTransform to,ObstacleMesh obstacle)
        {
            if(actor instanceof NervSiloDoorEntity hatch&&hatch.actualOpenProgressR52()==0
                    &&obstacle.frame().equals(obstacle.endFrame())&&from.translation().x==to.translation().x
                    &&from.translation().z==to.translation().z&&to.translation().y<=from.translation().y
                    &&NervRigidMeshSweepR52.angular(from,to)<1e-10)
            {
                // Retain the existing float-source sole resting tolerance.
                double top=obstacle.mesh().envelope(obstacle.frame(),obstacle.endFrame()).maxY;
                double lowest=Math.min(NervRigidMeshSweepR52.transformed(geometry.bounds(),from).minY,
                        NervRigidMeshSweepR52.transformed(geometry.bounds(),to).minY);
                if(lowest>=top-1e-6&&!protectedLoadIntersectsR53(from,to,obstacle))return true;
            }
            if(!(actor instanceof LivingEntity))
            {
                var contact=initialStationaryContactsR54.get(actor.getUUID());
                if(contact==null)
                {
                    if(!NervAirTransportManifestR52.same(from,root))return false;
                    var snapshot=NervStationaryActorContactR54.snapshot(actor);
                    if(snapshot==null||!snapshot.contains(obstacle))return false;
                    try{contact=new NervStationaryActorContactR54(actor.getUUID(),snapshot,completeAssemblyR54(),root);}
                    catch(java.util.concurrent.RejectedExecutionException busy){return false;}
                    initialStationaryContactsR54.put(actor.getUUID(),contact);
                }
                return contact.separates(level,actor,from,to,obstacle);
            }
            if(initialActorContacts.isEmpty())captureActorContactsR53(level);
            var contact=initialActorContacts.get(actor.getUUID());
            return contact!=null&&contact.current(level,actor,obstacle)&&contact.separates(from,to);
        }
        private EvaOriginalMeshGeometryR52.Geometry completeAssemblyR54()
        {
            var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();
            for(int i=0;i<surfaces.size();i++)
            {
                var mesh=surfaces.get(i);
                parts.add(new EvaOriginalMeshGeometryR52.Part("assembly/"+i,"captured-original",geometry.sourceFingerprint(),mesh.triangles(),mesh.bounds()));
            }
            if(pilotSeat!=null)
            {
                // The real seated occupant is a world-axis box, expressed in
                // the same captured rigid frame as its original plug/body.
                var centre=root.transformPoint(pilotSeat);var inverse=root.inverse();var corners=new Vec3[8];
                for(int i=0;i<8;i++)corners[i]=inverse.transformPoint(centre.add((i&1)==0?-pilotHalf.x:pilotHalf.x,(i&2)==0?-pilotHalf.y:pilotHalf.y,(i&4)==0?-pilotHalf.z:pilotHalf.z));
                int[] indices={0,2,3,0,3,1,4,5,7,4,7,6,0,1,5,0,5,4,2,6,7,2,7,3,0,4,6,0,6,2,1,3,7,1,7,5};
                var xyz=new double[indices.length*3];for(int i=0;i<indices.length;i++){var v=corners[indices[i]];xyz[i*3]=v.x;xyz[i*3+1]=v.y;xyz[i*3+2]=v.z;}
                var mesh=new NervRigidMeshSweepR52(xyz);parts.add(new EvaOriginalMeshGeometryR52.Part("pilot","captured-original",geometry.sourceFingerprint(),xyz,mesh.bounds()));
            }
            return new EvaOriginalMeshGeometryR52.Geometry(original.variant(),geometry.sourceFingerprint(),parts);
        }
        private boolean protectedLoadIntersectsR53(RigidTransform from,RigidTransform to,ObstacleMesh obstacle)
        {
            for(int i=geometry.parts().size();i<surfaces.size();i++)
                if(surfaces.get(i).intersects(from,to,obstacle.mesh(),obstacle.frame(),obstacle.endFrame(),.005,Vec3.ZERO))return true;
            if(pilotSeat!=null)
            {
                var a=from.transformPoint(pilotSeat);var b=to.transformPoint(pilotSeat);
                var pilot=new AABB(a.subtract(pilotHalf),a.add(pilotHalf)).minmax(new AABB(b.subtract(pilotHalf),b.add(pilotHalf)))
                        .inflate(NervRigidMeshSweepR52.error(pilotSeat.length(),NervRigidMeshSweepR52.angular(from,to),1));
                if(obstacle.mesh().intersects(obstacle.frame(),obstacle.endFrame(),pilot,.005))return true;
            }
            return false;
        }
        boolean protectedLoadIntersectsR53(RigidTransform from,RigidTransform to,AABB obstacle)
        {
            for(int i=geometry.parts().size();i<surfaces.size();i++)if(surfaces.get(i).intersects(from,to,obstacle,.005))return true;
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
    public record ClampContactSelectionR53(List<NervAirCradleContactsR52.Contact> contacts,String reason){}
    private static void writeContactVectorR53(CompoundTag tag,String key,Vec3 v)
    {var t=new CompoundTag();t.putDouble("X",v.x);t.putDouble("Y",v.y);t.putDouble("Z",v.z);tag.put(key,t);}
    private static Vec3 readContactVectorR53(CompoundTag tag,String key)
    {var t=tag.getCompound(key);return new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z"));}
    public static FlightPickupPreview inspect(ServerLevel level,Original original,Kind kind,CompoundTag data)
    {
        var preview=inspect(level,original,kind);if(preview==null||!data.contains("RescueSkinContactsR53"))return preview;
        var tag=data.getCompound("RescueSkinContactsR53");
        if(!tag.getString("Source").equals(preview.sourceFingerprint())||!tag.getCompound("Body").equals(preview.frozenBody)||!tag.getCompound("Hands").equals(preview.frozenHands))
            return Set.of("CLAMP","RESELECT_RETRACT","RESELECT_CONTACT").contains(data.getString("FlightStage"))?null:preview;
        var list=tag.getList("Contacts",10);var selected=new ArrayList<NervAirCradleContactsR52.Contact>();
        for(int i=0;i<list.size();i++){var c=list.getCompound(i);selected.add(new NervAirCradleContactsR52.Contact(c.getString("Bone"),readContactVectorR53(c,"Skin"),readContactVectorR53(c,"Centre"),readContactVectorR53(c,"Axis")));}
        return NervAirCradleContactsR52.valid(preview.geometry,selected)?preview.withContactsR53(selected):null;
    }
    /** Read-only before leases/locking; no pose override or carrier rise. */
    public static FlightPickupPreview inspect(ServerLevel l,Original o,Kind kind)
    {
        if(!(l.getEntity(o.eva()) instanceof EvaUnit01Entity e)||!e.isAlive()||e.isExperimentalUnit()||e.getUnitVariant()!=o.variant()||!l.dimension().location().toString().equals(o.dimension()))return null;
        var fleet=EvaFleetSavedData.get(l.getServer()).entry(o.variant()).orElse(null);var deployed=NervRouteRuntimeR52.originalForFlight(l,o.variant(),o.owner());if(fleet==null||!fleet.canonicalId().equals(o.eva())||!o.plug().equals(fleet.entryPlugId())&&(kind!=Kind.HULL_ONLY_RECOVERY||fleet.entryPlugId()!=null||!EntryPlugDisposalR31.destroyed(l,o.plug()))||!AutoSortieR32.missionToken(l).equals(o.mission())&&(deployed==null||!deployed.equals(o)))return null;
        NervHullPreviewR52 hp=null;EvaMechanicalFrameR52.OccupiedCapture occupied=null;EvaMechanicalFrameR52.HullCapture hull=null;FootSupportFrameR52.Binding binding;RigidTransform frame;
        if(EvaMechanicalFrameR52.active(e)){if(EvaMechanicalFrameR52.kind(e)!=kind)return null;binding=EvaMechanicalFrameR52.measuredBinding(e,o);frame=EvaMechanicalFrameR52.frame(e,1);}
        else if(kind==Kind.HULL_ONLY_RECOVERY){hp=NervHullPreviewR52.inspect(e,o);if(hp==null)return null;hull=hp.capture();binding=hp.binding();frame=hp.frame();}
        else{occupied=EvaMechanicalFrameR52.prepareOccupiedRecovery(e,o);if(occupied==null)return null;binding=EvaMechanicalFrameR52.occupiedPreviewBinding(occupied);frame=EvaMechanicalFrameR52.occupiedPreviewFrame(occupied);}
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var body=EvaMechanicalFrameR52.active(e)?EvaMechanicalFrameR52.frozenLocalPose(e):EvaBodyPose.sample(e,1);var hands=EvaFrozenHandsR52.capture(e,1);
        var geometry=EvaMechanicalFrameR52.active(e)?EvaMechanicalFrameR52.capturedGeometry(e)
                :provider.evaluate(e.getUnitVariant(),body,EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),hands));
        var surfaces=new ArrayList<>(NervObstacleMeshesR53.body(geometry));
        var anchors=new ArrayList<Vec3>();for(String bone:new String[]{"arm_l","arm_r","leg_l","leg_r","shin_l","shin_r"}){var p=body.matrix(bone).transformPosition(new Vector3f(body.rig.get(bone).pivot()).add(0,0,2.5F/EvaScale.RENDER_SCALE)).mul(EvaScale.RENDER_SCALE);anchors.add(new Vec3(p.x,p.y,p.z));}
        boolean carrierVisible=NervMappedPlugMechanicsR52.actualCarrierVisibleR52(e);
        float rise=e.carrierRiseProgress(1),release=e.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(e.getLaunchTicks()-1)/18F):0;
        boolean detached=EvaMechanicalFrameR52.detachedCarrierR52(e);if(carrierVisible&&!detached){if(capsules==null)return null;try{surfaces.addAll(carrierMeshes(e));}catch(IOException missing){return null;}}
        var contacts=NervAirCradleContactsR52.evaluate(geometry,anchors);anchors=new ArrayList<>(contacts.stream().map(NervAirCradleContactsR52.Contact::centre).toList());
        Vec3 seat=null,half=null;if(kind==Kind.OCCUPIED)
        {
            if(capsules==null||!(l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity plug)||!(l.getEntity(o.pilot()) instanceof LivingEntity pilot)||pilot.getVehicle()!=plug||plug.getVehicle()!=e||plug.getFirstPassenger()!=pilot||!plug.isHatchFullySealed()||!plug.isLockedToEva())return null;
            surfaces.addAll(closedPlugMeshesR54(capsules,o.variant(),binding.plugInEva()));
            seat=binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var box=pilot.getBoundingBox();if(box.getCenter().distanceToSqr(frame.transformPoint(seat))>1e-8)return null;half=new Vec3(box.getXsize()/2,box.getYsize()/2,box.getZsize()/2);
        }
        var initialWreckShapes=captureNativeSupportR54(l,e,NervObstacleMeshesR53.body(geometry),frame);
        if(initialWreckShapes==null)return null;
        var result=new FlightPickupPreview(o,kind,binding,frame,hull,occupied,hp,geometry,anchors,surfaces,seat,half,carrierVisible,rise,release,e.recoveryRackR39(),contacts,EvaShutdownR30.encode(body),hands,EvaMechanicalFrameR52.carrierDeckTravelR52(e),detached,EvaMechanicalFrameR52.carrierFrameR52(e,1),true,initialWreckShapes);
        if(NervTraversalPolicyR53.strict(l))result.captureActorContactsR53(l);return result;
    }
    private static Set<AABB> captureNativeSupportR54(ServerLevel level,Entity actor,
            List<NervRigidMeshSweepR52> surfaces,RigidTransform frame)
    {
        if(!NervTraversalPolicyR53.strict(level))
        {
            for(var mesh:surfaces)if(!EntryPlugEjectionR48.loaded(level,mesh.envelope(frame,frame)))return null;
            return Set.of();
        }
        var initial=new HashSet<AABB>();
        for(var mesh:surfaces)
        {
            var bounds=mesh.envelope(frame,frame);
            if(!EntryPlugEjectionR48.loaded(level,bounds))return null;
            for(var obstacle:NativeCollisionShapesR53.read(level,actor,bounds))
                if(!initial.contains(obstacle)&&mesh.intersects(frame,frame,obstacle,.005))initial.add(obstacle);
        }
        // Freeze the whole contacted floor footprint before departure. Thin,
        // unwelded sole surfaces can sit below adjacent voxels of that floor.
        // Only connected, same-height native support under the real vertical
        // body sweep is included; overhead solids and unrelated floors remain
        // ordinary obstacles. No live world result is cached across captures.
        var floors=new HashSet<AABB>();
        for(var shape:initial)if(shape.maxY<=frame.translation().y+.005)floors.add(shape);
        if(floors.isEmpty())return Set.copyOf(initial);
        var candidates=new HashSet<AABB>();
        for(var mesh:surfaces)
        {
            var originalBounds=mesh.envelope(frame,frame);
            double rise=Math.max(0,frame.translation().y-originalBounds.minY+.01);
            if(rise==0)continue;
            var raised=new RigidTransform(frame.translation().add(0,rise,0),frame.qx(),frame.qy(),frame.qz(),frame.qw());
            var bounds=mesh.envelope(frame,raised);
            if(!EntryPlugEjectionR48.loaded(level,bounds))return null;
            for(var shape:NativeCollisionShapesR53.read(level,actor,bounds))
                if(shape.maxY<=frame.translation().y+.005&&!initial.contains(shape)
                        &&floors.stream().anyMatch(floor->Math.abs(floor.maxY-shape.maxY)<.005)
                        &&mesh.intersects(frame,raised,shape,.005))candidates.add(shape);
        }
        boolean changed;
        do
        {
            changed=false;
            for(var it=candidates.iterator();it.hasNext();)
            {
                var shape=it.next();
                if(floors.stream().anyMatch(floor->Math.abs(floor.maxY-shape.maxY)<.005
                        &&floor.inflate(.005).intersects(shape)))
                {floors.add(shape);initial.add(shape);it.remove();changed=true;}
            }
        }while(changed&&!candidates.isEmpty());
        return Set.copyOf(initial);
    }

    /** One immutable actual-source preparation for this call and tick. It
     * grants no actor, SPACE or motion admission by itself. */
    public static final class PreparedSourceSweepR52 {
        private final ServerLevel level;private final long at;private final NervAirframeGeometryR52 geometry;private final FlightPickupPreview preview;private final Frame from,to;private final double rotorFrom,rotorTo;private final boolean movingCargo;private final NervAirframeGeometryR52.Sweep sweep;private final List<AABB> envelopes;
        private PreparedSourceSweepR52(ServerLevel level,NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo)
        {
            this.level=level;this.at=level==null?Long.MIN_VALUE:level.getGameTime();this.geometry=geometry;this.preview=preview;this.from=from;this.to=to;this.rotorFrom=rotorFrom;this.rotorTo=rotorTo;this.movingCargo=movingCargo;
            var boxes=new ArrayList<AABB>();
            if(level!=null&&!NervTraversalPolicyR53.strict(level))
            {
                // Loading/display needs source bounds, not thousands of swept
                // clamp/rotor triangles whose collisions are permitted.
                sweep=null;boxes.add(geometry.bodyMesh().envelope(from.plane(),to.plane()));
                for(int i=0;i<4;i++)boxes.add(geometry.rotorMesh(i).envelope(from.plane().compose(geometry.rotorLocalFrame(i,rotorFrom)),to.plane().compose(geometry.rotorLocalFrame(i,rotorTo))));
            }
            else
            {
                sweep=geometry.sweep(from,to,preview==null?List.of():preview.anchors(),preview==null?List.of():preview.jawAxes(),rotorFrom,rotorTo,.005);
                boxes.addAll(sweep.envelopes());
            }
            if(movingCargo){if(preview==null)throw new IllegalArgumentException("Actual captured cargo source required");boxes.addAll(preview.cargoEnvelopes(root(preview,from),root(preview,to)));}
            envelopes=List.copyOf(boxes);
        }
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
    {return checkStep(l,manifest,geometry,aircraft,preview,from,to,spaces,bindings,rotorFrom,rotorTo,movingCargo,prepared,null);}
    private static CheckedFlightStep checkStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,boolean movingCargo,PreparedSourceSweepR52 prepared,NervRescueVegetationR53 staticCanopy)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo))return null;
        if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||movingCargo&&(preview==null||!preview.shapeCurrent(l)))return null;
        var sweep=prepared.sweep;if(preview==null)return null;
        var proof=new CheckedFlightStep(l,aircraft,preview,from,to,sweep,manifest.fingerprint(),movingCargo,preview.original(),preview.kind(),spaces,rotorFrom,rotorTo,geometry,prepared.envelopes());
        if(!NervTraversalPolicyR53.strict(l))return proof;
        var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null||manifest.directory().resource(id)==null||manifest.directory().resource(id).kind()!=ResourceKind.SPACE)return null;declared.addAll(b.spaces());}
        if(!authorizedDynamicSpacesR52(manifest,proof.envelopes(),spaces,bindings)||!stepObstaclesClearR53(l,p,preview,from,to,sweep,proof.envelopes(),declared,proof.own,movingCargo,staticCanopy))return null;
        return proof;
    }
    static CheckedFlightStep staticCanopyHoldR53(ServerLevel level,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,
            UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,
            Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,PreparedSourceSweepR52 prepared)
    {
        var job=NervAirTransportRuntimeR52.state(level).aircraft(aircraft);
        if(job==null||preview==null||job.payloadTransferred()||!job.original().equals(preview.original())
                ||!job.ownerData().getBoolean("RescueCanopyR53")||!NervAirTransportManifestR52.same(root(preview,from),root(preview,to))
                ||!(level.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva))return null;
        // Only the unchanged captured body can rest within compliant leaves.
        // Even while the aircraft approaches, every moving clamp stays strict.
        return checkStep(level,manifest,geometry,aircraft,preview,from,to,spaces,bindings,rotorFrom,rotorTo,true,prepared,new NervRescueVegetationR53(level,eva));
    }
    public static List<AABB> sourceEnvelopesR52(NervAirframeGeometryR52 geometry,FlightPickupPreview preview,Frame from,Frame to,double rotorFrom,double rotorTo,boolean movingCargo){return prepareSourceSweepR52(null,geometry,preview,from,to,rotorFrom,rotorTo,movingCargo).envelopes();}
    public static CheckedFlightStep checkAircraftStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,Original original,Kind kind,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo)
    {if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||p.carrying()||from.rig().deployment()!=0||to.rig().deployment()!=0||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||!NervAircraftFrameR52.frame(p,1).rig().equals(from.rig()))return null;return checkAircraftStep(l,manifest,geometry,aircraft,original,kind,from,to,spaces,bindings,rotorFrom,rotorTo,prepareSourceSweepR52(l,geometry,null,from,to,rotorFrom,rotorTo,false));}
    public static CheckedFlightStep checkAircraftStep(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,Original original,Kind kind,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,double rotorFrom,double rotorTo,PreparedSourceSweepR52 prepared)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,null,from,to,rotorFrom,rotorTo,false))return null;
        if(!(l.getEntity(aircraft) instanceof UNTransportEntity p)||!NervAircraftFrameR52.contextMatches(p,manifest)||p.carrying()||from.rig().deployment()!=0||to.rig().deployment()!=0||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(p),from.plane())||!NervAircraftFrameR52.frame(p,1).rig().equals(from.rig()))return null;
        var sweep=prepared.sweep;var proof=new CheckedFlightStep(l,aircraft,null,from,to,sweep,manifest.fingerprint(),false,original,kind,spaces,rotorFrom,rotorTo,geometry,prepared.envelopes());
        if(!NervTraversalPolicyR53.strict(l))return proof;
        var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null)return null;declared.addAll(b.spaces());}
        return authorizedDynamicSpacesR52(manifest,proof.envelopes(),spaces,bindings)&&stepObstaclesClearR53(l,p,null,from,to,sweep,proof.envelopes(),declared,Set.of(aircraft),false,null)?proof:null;
    }
    public static boolean pathClear(ServerLevel l,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings,boolean movingCargo,int ticks,NervFlightGatePlanR52 plan,PreparedSourceSweepR52 prepared)
    {
        if(prepared==null||!prepared.matchesR52(l,geometry,preview,from,to,0,ticks,movingCargo))return false;
        if(preview==null||!(l.getEntity(aircraft) instanceof UNTransportEntity p))return false;
        if(!NervTraversalPolicyR53.strict(l))return true;
        try
        {
            var sweep=prepared.sweep;var boxes=prepared.envelopes();var declared=new ArrayList<AABB>();for(String id:spaces){var b=bindings.get(id);if(b==null)return false;declared.addAll(b.spaces());}
            if(!authorizedDynamicSpacesR52(manifest,boxes,spaces,bindings))return false;
            var own=new HashSet<UUID>();own.add(aircraft);if(movingCargo){own.addAll(preview.members());if(NervTraversalPolicyR53.strict(l)&&sweep.airframeIntersectsCargo(preview.surfaces,from.cargo(),to.cargo()))return false;}return clear(l,p,preview,from,to,sweep,boxes,declared,own,movingCargo,plan);
        }
        catch(IllegalArgumentException|IllegalStateException blocked){return false;}
    }
    private static boolean authorizedDynamicSpacesR52(NervAirTransportManifestR52 manifest,List<AABB> envelopes,Set<String> spaces,Map<String,NervRouteNativeR52.Binding> bindings){if(manifest.directory().dynamicSpacesR52().domains().isEmpty())return true;try{return spaces.containsAll(manifest.directory().dynamicSpacesR52().required(manifest.dimension(),envelopes,bindings));}catch(IllegalArgumentException denied){return false;}}
    /** Read-only planning, or one actual recovery tick of canopy compression.
     * This never creates a movement proof; callers must rerun checkStep after
     * real block destruction and before either original actor can move. */
    static boolean recoveryCanopyR53(ServerLevel level,NervAirTransportManifestR52 manifest,NervAirframeGeometryR52 geometry,
            UUID aircraft,FlightPickupPreview preview,Frame from,Frame to,Set<String> spaces,
            Map<String,NervRouteNativeR52.Binding> bindings,PreparedSourceSweepR52 prepared,boolean compress)
    {
        if(preview==null||prepared==null||!prepared.matchesR52(level,geometry,preview,from,to,prepared.rotorFrom,prepared.rotorTo,true)
                ||!(level.getEntity(aircraft) instanceof UNTransportEntity plane)
                ||!(level.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva))return false;
        if(compress)
        {
            var job=NervAirTransportRuntimeR52.state(level).aircraft(aircraft);var context=NervRouteRuntimeR52.flightContext(level);
            if(job==null||context==null||job.cancelRequested()||job.payloadTransferred()||!job.original().equals(preview.original())
                    ||!job.ownerData().getBoolean("RescueCanopyR53")||!preview.shapeCurrent(level)
                    ||!NervAircraftFrameR52.contextMatches(plane,manifest)||!NervAirTransportManifestR52.same(NervAircraftFrameR52.actual(plane),from.plane())
                    ||prepared.rotorFrom!=NervAircraftFrameR52.rotorClock(plane)||prepared.rotorTo!=prepared.rotorFrom+1)return false;
            var lease=context.pool().queryFlight(job.task());if(lease==null||!lease.original().equals(job.original())||!aircraft.equals(lease.aircraft())
                    ||!context.pool().resourcesAvailable(job.task(),spaces))return false;
            String stage=job.ownerData().getString("FlightStage");
            boolean clamp=stage.equals("CLAMP")&&!job.carrying()&&to.rig().deployment()>from.rig().deployment()
                    &&to.rig().deployment()-from.rig().deployment()<=.050001;
            boolean tow=job.carrying()&&(stage.equals("EXTRACT")||stage.equals("LOADED")&&job.leg()==0)
                    &&from.cargo()!=null&&to.cargo()!=null&&from.cargo().translation().distanceToSqr(to.cargo().translation())>0;
            if(!clamp&&!tow)return false;
        }
        var declared=new ArrayList<AABB>();for(String id:spaces){var binding=bindings.get(id);if(binding==null)return false;declared.addAll(binding.spaces());}
        if(!authorizedDynamicSpacesR52(manifest,prepared.envelopes(),spaces,bindings)
                ||prepared.sweep.airframeIntersectsCargo(preview.surfaces,root(preview,from),root(preview,to)))return false;
        var canopy=new NervRescueVegetationR53(level,eva);var own=new HashSet<>(preview.members());own.add(aircraft);
        if(!clear(level,plane,preview,from,to,prepared.sweep,prepared.envelopes(),declared,own,true,null,canopy,false))return false;
        return !compress||!canopy.empty()&&canopy.compress();
    }
    /** Normal automatic transport permits overlap; strict diagnostics can
     * still inspect geometry without changing actor ownership or loading. */
    private static boolean stepObstaclesClearR53(ServerLevel level,Entity aircraft,FlightPickupPreview preview,
            Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,List<AABB> envelopes,List<AABB> declared,
            Set<UUID> own,boolean movingCargo,NervRescueVegetationR53 canopy)
    {
        if(!NervTraversalPolicyR53.strict(level))
        {
            return true;
        }
        if(movingCargo&&sweep.airframeIntersectsCargo(preview.surfaces,root(preview,from),root(preview,to)))return false;
        return clear(level,aircraft,preview,from,to,sweep,envelopes,declared,own,movingCargo,null,canopy,true);
    }
    private static boolean clear(ServerLevel l,Entity p,FlightPickupPreview preview,Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,List<AABB> envelopes,List<AABB> declared,Set<UUID> own,boolean movingCargo,NervFlightGatePlanR52 plan)
    {return clear(l,p,preview,from,to,sweep,envelopes,declared,own,movingCargo,plan,null,false);}
    private static boolean clear(ServerLevel l,Entity p,FlightPickupPreview preview,Frame from,Frame to,NervAirframeGeometryR52.Sweep sweep,List<AABB> envelopes,List<AABB> declared,Set<UUID> own,boolean movingCargo,NervFlightGatePlanR52 plan,NervRescueVegetationR53 canopy,boolean staticBodyOnly)
    {
        if(plan!=null&&!plan.current(l))return false;
        if(!NervTraversalPolicyR53.strict(l))
        {
            return true;
        }
        // Closing the clamps leaves the captured wreck exactly where it was.
        // Its pre-existing overlap is not a new movement collision; only the
        // moving clamp/airframe is swept until extraction actually starts.
        boolean cargoMoves=movingCargo&&!NervAirTransportManifestR52.same(root(preview,from),root(preview,to));
        boolean mechanicalRescue=false;
        if(preview!=null&&!NervTraversalPolicyR53.strict(l))
            for(var rescue:NervAirTransportRuntimeR52.state(l).jobs())
                if(rescue.active()&&rescue.original().equals(preview.original())&&rescue.ownerData().getBoolean("Returning"))
                {
                    String stage=rescue.ownerData().getString("FlightStage");
                    mechanicalRescue=stage.equals("CLAMP")||stage.equals("EXTRACT")||stage.equals("ALIGN")||stage.equals("LOADED")&&rescue.leg()==0;
                    break;
                }
        UUID receiverActor=null;var receiverBearings=new HashSet<ObstacleMesh>();var receiverGroup=new HashSet<ObstacleMesh>();
        if(movingCargo&&preview!=null&&p instanceof UNTransportEntity
                &&NervAirTransportManifestR52.same(root(preview,from),root(preview,to)))
        {
            var flight=NervAirTransportRuntimeR52.state(l).aircraft(p.getUUID());
            var carrier=NervOriginalCarrierR52.controller(l,preview.original());
            if(flight!=null&&!flight.payloadTransferred()&&flight.original().equals(preview.original())
                    &&Set.of("UNCLAMP","TRANSFER").contains(flight.ownerData().getString("FlightStage"))&&carrier!=null
                    &&l.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva)try
            {
                var body=EvaMechanicalFrameR52.capturedGeometry(eva);var at=root(preview,from);
                // Participation precedes contact; receiverReady still requires full
                // bearing before the aircraft can release its supported payload.
                if(!NervTraversalPolicyR53.strict(l))
                {receiverActor=carrier.getUUID();receiverGroup.addAll(NervOriginalCarrierR52.actualMeshesR52(carrier));}
                if(NervOriginalCarrierR52.carrierFootBearingR52(l,carrier,eva,body,at))
                {
                    receiverActor=carrier.getUUID();
                    var pads=CarrierFootBearingR53.selected();var mounting=CarrierMountProfileR53.read(carrier,1);
                    var carrierRoot=NervOriginalCarrierR52.actualRoot(carrier,1);
                    if(pads!=null)for(var part:NervOriginalCarrierR52.actualPartsR52(carrier))
                        if(part.role()==NervOriginalCarrierR52.Role.SOLE_BEARING)
                            for(var pad:pads.variant(eva.getUnitVariant()))if(pad.name().equals(part.name()))
                            {
                                var mesh=new ObstacleMesh(part.mesh(),part.frame());
                                if(CarrierFootBearingR53.permitsContact(pads,body,at,carrierRoot,mounting,CarrierAssemblyR53.selected(),pad.bone(),mesh))receiverBearings.add(mesh);
                            }
                    if(!receiverBearings.isEmpty())receiverActor=carrier.getUUID();
                }
            }catch(IOException unavailable){return false;}
        }
        // A supported handoff is one mechanical participation group in NORMAL.
        // STRICT still reports internal steel overlap while permitting the sole pads.
        var fixedCarriers=detachedCarrierObstacles(l);if(fixedCarriers==null)return false;for(var mesh:fixedCarriers)if(!receiverGroup.contains(mesh)&&(mechanicalRescue?sweep.aircraftIntersectsR53(mesh.mesh().envelope(mesh.frame(),mesh.endFrame())):sweep.intersects(mesh.mesh(),mesh.frame())||cargoMoves&&!receiverBearings.contains(mesh)&&preview.cargoIntersects(root(preview,from),root(preview,to),mesh.mesh(),mesh.frame())))return false;
        for(var box:envelopes)if(!NervAirspaceCoverageR52.covered(box,declared)||!EntryPlugEjectionR48.loaded(l,box))return false;
        var seen=new HashSet<UUID>();var blockObstacles=new ExactBlockObstaclesR52();
        java.util.function.Predicate<AABB> sourceIntersects=obstacle->{
            if(!blockObstacles.first(obstacle)||plan!=null&&plan.isDeclaredSeal(l,obstacle))return false;
            var movingRig=sweep;boolean assemblyIncluded=movingCargo;var captured=preview;
            if(assemblyIncluded&&captured!=null&&!NervTraversalPolicyR53.strict(l))
                for(var rescue:NervAirTransportRuntimeR52.state(l).jobs())
                    if(rescue.active()&&rescue.original().equals(captured.original())&&rescue.ownerData().getBoolean("Returning"))
                    {
                        String stage=rescue.ownerData().getString("FlightStage");
                        if(stage.equals("CLAMP")||stage.equals("EXTRACT")||stage.equals("ALIGN")||stage.equals("LOADED")&&rescue.leg()==0)
                            return movingRig.aircraftIntersectsR53(obstacle);
                        break;
                    }
            boolean rigHit=sweep.intersects(obstacle),hit=rigHit||movingCargo&&!NervAirTransportManifestR52.same(root(preview,from),root(preview,to))&&preview.cargoIntersects(root(preview,from),root(preview,to),obstacle);
            if(!hit)return false;
            if(!rigHit&&movingCargo&&preview.existingWreckContactR53(root(preview,from),root(preview,to),obstacle))return false;
            return canopy==null||!movingCargo||(staticBodyOnly?rigHit:sweep.aircraftIntersectsR53(obstacle))
                    ||preview.protectedLoadIntersectsR53(root(preview,from),root(preview,to),obstacle)||!canopy.contact(obstacle);
        };
        var blocks=BoundedNativeCollisionGroupsR52.clear(envelopes,box->EntryPlugEjectionR48.loaded(l,box),box->NativeCollisionShapesR53.read(l,p,box),(piece,obstacle)->sourceIntersects.test(obstacle));
        if(!blocks.clear())return false;
        for(var box:envelopes)
        {
            for(var e:l.getEntities((Entity)null,box.inflate(200),e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
            {
                if(!seen.add(e.getUUID())||!NervTraversalPolicyR53.strict(l)&&e.getUUID().equals(receiverActor))continue;List<ObstacleMesh> actual;var planned=plan==null?null:plan.openMeshes(e.getUUID());if(planned!=null){var converted=new ArrayList<ObstacleMesh>();for(var mesh:planned)converted.add(new ObstacleMesh(mesh.geometry(),mesh.frame()));actual=List.copyOf(converted);}else actual=obstacleMeshes(e,sweep.source());if(actual==null){var bounds=e instanceof UNTransportEntity plane?plane.getBoundingBoxForCulling():e.getBoundingBox();if(envelopes.stream().anyMatch(b->b.intersects(bounds)))return false;continue;}
                if(actual.isEmpty()){if(mechanicalRescue?sweep.aircraftIntersectsR53(e.getBoundingBox()):sweep.intersects(e.getBoundingBox())||cargoMoves&&preview.cargoIntersects(root(preview,from),root(preview,to),e.getBoundingBox()))return false;}
                else for(var mesh:actual)
                {
                    // Ground equipment can contact the assisted grippers and
                    // wreck during extraction. The aircraft itself stays clear.
                    if(mechanicalRescue)
                    {
                        if(sweep.aircraftIntersectsR53(mesh.mesh().envelope(mesh.frame(),mesh.endFrame())))return false;
                        continue;
                    }
                    if(sweep.intersects(mesh.mesh(),mesh.frame(),mesh.endFrame())&&(preview==null||!preview.existingClampRetractionR53(l,e,from,to,mesh,sweep.source(),p instanceof UNTransportEntity aircraft?NervAircraftFrameR52.rotorClock(aircraft):0)))return false;
                    if(cargoMoves&&!(e.getUUID().equals(receiverActor)&&receiverBearings.contains(mesh))&&preview.cargoIntersects(root(preview,from),root(preview,to),mesh.mesh(),mesh.frame(),mesh.endFrame())
                            &&!preview.existingActorContactR53(l,e,root(preview,from),root(preview,to),mesh))return false;
                }
            }
        }
        return true;
    }
    public record ObstacleMesh(NervRigidMeshSweepR52 mesh,RigidTransform frame,RigidTransform endFrame){public ObstacleMesh(NervRigidMeshSweepR52 mesh,RigidTransform frame){this(mesh,frame,frame);}}
    private record ClosedPlugMeshesR54(FullAssemblyGeometryR52.Provider source,int variant,RigidTransform plugInEva,List<NervRigidMeshSweepR52> meshes){}
    private static final Deque<ClosedPlugMeshesR54> CLOSED_PLUG_MESHES_R54=new ArrayDeque<>();
    private static synchronized List<NervRigidMeshSweepR52> closedPlugMeshesR54(FullAssemblyGeometryR52.Provider source,int variant,RigidTransform plugInEva)
    {
        // Cache only immutable local triangles. World frames, actors and block
        // contacts are still read for every inspection below.
        for(var known:CLOSED_PLUG_MESHES_R54)
            if(known.source()==source&&known.variant()==variant&&known.plugInEva().equals(plugInEva))return known.meshes();
        var meshes=new ArrayList<NervRigidMeshSweepR52>();
        for(var part:source.closedPlugParts(variant).values())meshes.add(new NervRigidMeshSweepR52(transform(part,plugInEva)));
        var result=List.copyOf(meshes);
        if(CLOSED_PLUG_MESHES_R54.size()>=12)CLOSED_PLUG_MESHES_R54.removeFirst();
        CLOSED_PLUG_MESHES_R54.addLast(new ClosedPlugMeshesR54(source,variant,plugInEva,result));return result;
    }
    private record CarrierMeshes(FullAssemblyGeometryR52.Provider source,int variant,float rise,boolean rack,float release,double travel,List<NervRigidMeshSweepR52> meshes){}
    private static final Map<UUID,CarrierMeshes> ACTUAL_CARRIER_MESHES=new HashMap<>();
    private static List<NervRigidMeshSweepR52> carrierMeshes(EvaUnit01Entity e)throws IOException
    {if(capsules==null)installCapsules();float rise=e.carrierRiseProgress(1),release=e.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(e.getLaunchTicks()-1)/18F):0;double travel=EvaMechanicalFrameR52.carrierDeckTravelR52(e);var old=ACTUAL_CARRIER_MESHES.get(e.getUUID());if(old!=null&&old.source()==capsules&&old.variant()==e.getUnitVariant()&&old.rise()==rise&&old.rack()==e.recoveryRackR39()&&old.release()==release&&old.travel()==travel)return old.meshes();var meshes=new ArrayList<NervRigidMeshSweepR52>();for(var part:capsules.carrierParts(e.getUnitVariant(),rise,e.recoveryRackR39(),release,travel).values())meshes.add(new NervRigidMeshSweepR52(part));var result=List.copyOf(meshes);ACTUAL_CARRIER_MESHES.put(e.getUUID(),new CarrierMeshes(capsules,e.getUnitVariant(),rise,e.recoveryRackR39(),release,travel,result));return result;}
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
    public static List<ObstacleMesh> actualObstacleMeshes(Entity actor)
    {
        return obstacleMeshes(actor,null);
    }
    private static synchronized NervAirframeGeometryR52 actualAircraftSource()throws IOException
    {
        if(actualAircraftSource==null)actualAircraftSource=NervAirframeGeometryR52.loadClasspath(Map.of("mesh/tv_facilities_r16.json",NervSiloHatchGeometryR52.SOURCE_SHA,"mesh/air_cradle_r31.json","20ca048a0e0cb5a5a4caaed5d8984cd6bef16d769a7a70db5055fa727b6eaa1b"));
        return actualAircraftSource;
    }
    private static List<ObstacleMesh> obstacleMeshes(Entity actor,NervAirframeGeometryR52 source)
    {
        try{return resolveObstacleMeshes(actor,source);}
        catch(IOException|IllegalArgumentException|IllegalStateException missing){return null;}
    }
    /** One dispatcher for both external machines and flight sweeps. Only an
     * aircraft needs the aircraft source; a door or cannon must not depend on it. */
    private static List<ObstacleMesh> resolveObstacleMeshes(Entity actor,NervAirframeGeometryR52 source)throws IOException
    {
        if(actor instanceof YashimaCannonEntityR52 gun)return YashimaCannonMeshR52.actualObstacleMeshesR52(gun);
        if(actor instanceof NervCarrierPlatformEntity gantry){try{if(NervFootGuideStationR52.declared(gantry))return NervFootGuideStationR52.actualMeshesR52(gantry);if(NervOriginalCarrierR52.declared(gantry))return NervOriginalCarrierR52.actualMeshesR52(gantry);if(gantry.isPlugCrane())return NervCraneGeometryR52.actualObstacleMeshesR52(gantry);if(!gantry.isRestraintGantry()||!gantry.hasDeclaredMachineFrameR52()||!gantry.declaredCollisionSourceR52().equals(selectedCageSourceR52()))return null;return NervPlantMotionR52.actualRenderedMeshesR52(gantry);}catch(IOException|IllegalStateException missing){return null;}}
        if(actor instanceof EvaUnit01Entity eva)
        {
            EvaOriginalMeshGeometryR52.Geometry geometry;
            if(EvaMechanicalFrameR52.active(eva))geometry=EvaMechanicalFrameR52.capturedGeometry(eva);
            else if(EvaMechanicalFrameR52.serviceSourceHeldR52(eva))geometry=EvaMechanicalFrameR52.serviceGeometryR52(eva);
            else
            {
                var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var body=EvaBodyPose.sample(eva,1);var hands=EvaFrozenHandsR52.capture(eva,1);
                geometry=provider.evaluate(eva.getUnitVariant(),body,EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),hands));
            }
            var root=NervOwnerPlacementR52.actualRoot(eva);var out=new ArrayList<ObstacleMesh>();
            for(var mesh:NervObstacleMeshesR53.body(geometry))out.add(new ObstacleMesh(mesh,root));
            if(!EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(eva)&&NervMappedPlugMechanicsR52.actualCarrierVisibleR52(eva))
            {
                try{for(var mesh:carrierMeshes(eva))out.add(new ObstacleMesh(mesh,EvaMechanicalFrameR52.carrierFrameR52(eva,1)));}
                catch(IOException missing){return null;}
            }
            return List.copyOf(out);
        }
        if(actor instanceof EntryPlugCarrierEntity plug){if(capsules==null)try{installCapsules();}catch(IOException missing){return null;}var out=new ArrayList<ObstacleMesh>();for(var part:NervObstacleMeshesR53.plugParts(capsules,plug.getAssignedVariant()).entrySet())out.add(new ObstacleMesh(part.getValue(),plug.getCanonicalTransform().compose(capsules.plugPartFrameR53(part.getKey(),plug.getHatchOpenAmount()))));return List.copyOf(out);}
        if(actor instanceof NervSiloDoorEntity hatch){if(hatch.declaredSpecR52()==null)return null;var out=new ArrayList<ObstacleMesh>();for(var piece:hatch.declaredGeometryR52().pieces(hatch.actualOpenProgressR52()))out.add(new ObstacleMesh(NervObstacleMeshesR53.part(piece.part()),hatch.actualFrameR52().compose(piece.local())));return List.copyOf(out);}
        if(actor instanceof NervHangarDoorEntity gate){if(gate.declaredStackR52()==null)return null;var out=new ArrayList<ObstacleMesh>();for(var piece:gate.declaredGeometryR52().pieces(gate.actualOpenProgressR52()))out.add(new ObstacleMesh(NervObstacleMeshesR53.part(piece.part()),gate.actualFrameR52().compose(piece.local())));return List.copyOf(out);}
        if(!(actor instanceof UNTransportEntity plane))return List.of();if(!NervAircraftFrameR52.active(plane)&&(plane.carrying()||plane.rig(1)!=0))return null;
        if(source==null)source=actualAircraftSource();
        var frame=NervAircraftFrameR52.active(plane)?NervAircraftFrameR52.frame(plane,1):new Frame(NervAircraftFrameR52.actual(plane),null,new Rig(plane.hoistDistance(),0,1));var out=new ArrayList<ObstacleMesh>();
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
        var boxes=preview.cargoEnvelopes(preview.root(),preview.root());var declared=new ArrayList<AABB>();for(String id:cargoSpaces){var b=bindings.get(id);if(b==null)return null;declared.addAll(b.spaces());}
        for(var box:boxes)if(!NervAirspaceCoverageR52.covered(box,declared)||!EntryPlugEjectionR48.loaded(level,box))return null;
        return new CheckedPickupHold(aircraft,preview,task);
    }
    private static boolean positiveBearing(ServerLevel level,FlightPickupPreview preview)
    {
        if(!(level.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva))return false;
        // Recovery clamps accept ledges, slopes and water. Actual pickup
        // contacts are captured at clamp time, not guessed from two foot points.
        return Double.isFinite(eva.position().lengthSqr())
                && eva.getY()>level.getMinBuildHeight() && eva.getY()<level.getMaxBuildHeight();
    }
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
        if(preview==null||preview.kind()!=Kind.OCCUPIED||receiver==null||!receiver.delivery()||!NervAirTransportManifestR52.same(stopped,receiver.stopped())||!(l.getEntity(preview.original().eva()) instanceof EvaUnit01Entity eva)||!NervAirTransportManifestR52.same(NervOwnerPlacementR52.actualRoot(eva),receiver.stopped())||!preview.current(l))return false;
        for(var c:receiver.supports())if(!l.hasChunkAt(c.position())||!net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(l.getBlockState(c.position())).equals(c.state()))return false;
        var nativeSupports=new ArrayList<AABB>();
        for(var c:receiver.supports())
            for(var box:l.getBlockState(c.position()).getCollisionShape(l,c.position(),net.minecraft.world.phys.shapes.CollisionContext.of(eva)).toAabbs())
                nativeSupports.add(box.move(c.position()));
        return finiteDeliverySolesR53(preview.geometry(),stopped,nativeSupports)
                &&EvaMechanicalReleaseR52.actualGroundBearingR52(l,eva,preview.geometry(),stopped);
    }
    /** Exact projected coverage of the actual lowest sole facets. Declared
     * native faces must cover their interiors as well as their vertices. */
    static boolean finiteDeliverySolesR53(EvaOriginalMeshGeometryR52.Geometry geometry,RigidTransform root,List<AABB> supports)
    {
        if(geometry==null||root==null||supports==null||supports.isEmpty()
                ||root.transformVector(new Vec3(0,1,0)).distanceTo(new Vec3(0,1,0))>1e-6)return false;
        for(String foot:List.of("foot_l","foot_r"))
        {
            var triangles=new ArrayList<List<Vec3>>();double lowest=Double.POSITIVE_INFINITY;
            for(var part:geometry.parts())if(part.bone().equals(foot))
            {
                var xyz=part.triangles();
                for(int i=0;i<xyz.length;i+=9)
                {
                    var triangle=new ArrayList<Vec3>(3);
                    for(int j=0;j<9;j+=3)
                    {
                        var p=root.transformPoint(new Vec3(xyz[i+j],xyz[i+j+1],xyz[i+j+2]));
                        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z))return false;
                        lowest=Math.min(lowest,p.y);triangle.add(p);
                    }
                    triangles.add(triangle);
                }
            }
            if(!Double.isFinite(lowest))return false;
            double finiteArea=0;
            for(var triangle:triangles)
            {
                final double bottom=lowest;
                if(triangle.stream().anyMatch(p->p.y>bottom+.002))continue;
                double area=soleAreaR53(triangle);if(area<=1e-10)continue;
                var eligible=supports.stream().filter(b->b.maxX>b.minX&&b.maxZ>b.minZ
                        &&triangle.stream().allMatch(p->Math.abs(p.y-b.maxY)<=.0021)).toList();
                if(!soleTriangleCoveredR53(triangle,area,eligible))return false;
                finiteArea+=area;
            }
            if(finiteArea<.0025)return false;
        }
        return true;
    }
    private static double soleAreaR53(List<Vec3> polygon)
    {
        if(polygon.size()<3)return 0;
        var origin=polygon.get(0);double twice=0;
        for(int i=1;i+1<polygon.size();i++)
        {
            var a=polygon.get(i).subtract(origin);var b=polygon.get(i+1).subtract(origin);
            twice+=a.x*b.z-a.z*b.x;
        }
        return Math.abs(twice)*.5;
    }
    private static List<Vec3> clipSoleR53(List<Vec3> polygon,int axis,double plane,boolean above)
    {
        if(polygon.isEmpty())return List.of();
        var out=new ArrayList<Vec3>();var previous=polygon.get(polygon.size()-1);
        double prior=(axis==0?previous.x:previous.z)-plane;boolean was=above?prior>=0:prior<=0;
        for(var current:polygon)
        {
            double next=(axis==0?current.x:current.z)-plane;boolean inside=above?next>=0:next<=0;
            if(inside!=was)out.add(previous.lerp(current,prior/(prior-next)));
            if(inside)out.add(current);previous=current;prior=next;was=inside;
        }
        return out;
    }
    private static boolean soleTriangleCoveredR53(List<Vec3> triangle,double area,List<AABB> supports)
    {
        double x0=triangle.stream().mapToDouble(p->p.x).min().orElseThrow(),x1=triangle.stream().mapToDouble(p->p.x).max().orElseThrow();
        double z0=triangle.stream().mapToDouble(p->p.z).min().orElseThrow(),z1=triangle.stream().mapToDouble(p->p.z).max().orElseThrow();
        var overlapping=supports.stream().filter(b->b.maxX>x0&&b.minX<x1&&b.maxZ>z0&&b.minZ<z1).toList();
        if(overlapping.isEmpty())return false;
        var xs=new TreeSet<Double>();var zs=new TreeSet<Double>();xs.add(x0);xs.add(x1);zs.add(z0);zs.add(z1);
        for(var b:overlapping)
        {
            xs.add(Math.max(x0,b.minX));xs.add(Math.min(x1,b.maxX));
            zs.add(Math.max(z0,b.minZ));zs.add(Math.min(z1,b.maxZ));
        }
        var x=new ArrayList<>(xs);var z=new ArrayList<>(zs);double covered=0;
        for(int i=1;i<x.size();i++)for(int j=1;j<z.size();j++)
        {
            double cx=(x.get(i-1)+x.get(i))*.5,cz=(z.get(j-1)+z.get(j))*.5;
            if(overlapping.stream().noneMatch(b->cx>=b.minX&&cx<=b.maxX&&cz>=b.minZ&&cz<=b.maxZ))continue;
            List<Vec3> polygon=triangle;
            polygon=clipSoleR53(polygon,0,x.get(i-1),true);polygon=clipSoleR53(polygon,0,x.get(i),false);
            polygon=clipSoleR53(polygon,2,z.get(j-1),true);polygon=clipSoleR53(polygon,2,z.get(j),false);
            covered+=soleAreaR53(polygon);
        }
        return covered>=area-Math.max(1e-9,area*1e-9);
    }
    public static CheckedAirDelivery delivery(ServerLevel l,CheckedFlightStep stopped,Receiver destination)
    {return supportedDelivery(l,stopped,destination)?new CheckedAirDelivery(stopped,destination):null;}
    private static boolean contains(AABB a,AABB b){return a.minX<=b.minX&&a.minY<=b.minY&&a.minZ<=b.minZ&&a.maxX>=b.maxX&&a.maxY>=b.maxY&&a.maxZ>=b.maxZ;}
    private static double[] transform(double[] xyz,RigidTransform f){var out=xyz.clone();for(int i=0;i<out.length;i+=3){var p=f.transformPoint(new Vec3(out[i],out[i+1],out[i+2]));out[i]=p.x;out[i+1]=p.y;out[i+2]=p.z;}return out;}
    private static RigidTransform root(FlightPickupPreview preview,Frame frame){return frame.cargo()!=null?frame.cargo():preview==null?null:preview.root();}
    private NervFlightProofR52(){}
}
