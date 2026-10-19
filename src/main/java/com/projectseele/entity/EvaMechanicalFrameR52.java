package com.projectseele.entity;

import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.FootSupportFrameR52;
import com.projectseele.world.NervRouteReservationsR52.Original;
import com.projectseele.world.RigidTransform;
import com.projectseele.world.EvaOriginalMeshGeometryR52;
import com.projectseele.world.TransportMembershipR52;
import com.projectseele.world.TransportMembershipR52.Kind;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.joml.Matrix4f;
import net.minecraft.world.phys.AABB;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/** One accepted rigid sample owns body, sole bearings, capsule and pilot.
 * Route admission, native clearance and actual machine readiness stay with
 * the route owner. This class neither reserves nor starts a movement. */
public final class EvaMechanicalFrameR52
{
    private static final EntityDataAccessor<CompoundTag> SAMPLE = SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private record CapturedGeometry(long at,EvaOriginalMeshGeometryR52.Geometry geometry){}
    private record HeldGeometry(long at,float open,float bow,CompoundTag body,CompoundTag hands,EvaOriginalMeshGeometryR52.Geometry geometry){}
    private static final Map<EvaUnit01Entity,CapturedGeometry> GEOMETRY=new WeakHashMap<>();
    private static final Map<EvaUnit01Entity,HeldGeometry> HELD_GEOMETRY=new WeakHashMap<>();
    private static volatile boolean geometryInstalled;
    /** Explicit commissioning hook; uses the packaged source receipt, without
     * extracting or copying the already installed original model files. */
    public static synchronized void installGeometry() throws java.io.IOException
    {
        if(!geometryInstalled){EvaOriginalMeshGeometryR52.installClasspath();geometryInstalled=true;}
    }
    /** Forge fires this before loadLevel/entity deserialization on both
     * dedicated and integrated servers. Only immutable selected CPU resources
     * are read; a failed selection prevents startup instead of losing an EVA
     * or inventing collision bounds. Later Owner warmup shares this provider. */
    public static void prepareBeforeServerLoadR52(net.minecraftforge.event.server.ServerAboutToStartEvent event)
    {
        try
        {
            installGeometry();
            EvaBodyPose.prepareBeforeServerLoadR53();
            com.projectseele.world.NervRootAssemblyInstallationR52.prepareBeforeServerLoadR53(event.getServer());
        }
        catch(java.io.IOException failure){throw new IllegalStateException("Original packaged mesh provider failed before entity load",failure);}
    }
    /** Registering this nested subscriber does not initialize the outer
     * SAMPLE accessor. Complete the ordinary base-class helper order first,
     * before any subclass descriptors or resource preloading can run. */
    @net.minecraftforge.fml.common.Mod.EventBusSubscriber(modid="projectseele",bus=net.minecraftforge.fml.common.Mod.EventBusSubscriber.Bus.FORGE)
    public static final class BeforeServerLoadSubscriberR52
    {
        @net.minecraftforge.eventbus.api.SubscribeEvent
        public static void beforeServerLoad(net.minecraftforge.event.server.ServerAboutToStartEvent event)
        {
            try{Class.forName(EvaUnit01Entity.class.getName(),true,EvaUnit01Entity.class.getClassLoader());}
            catch(ClassNotFoundException impossible){throw new IllegalStateException("Original EVA base class absent",impossible);}
            if(com.projectseele.world.NervRouteRuntimeR52.mapRebuildEnabledR52())prepareBeforeServerLoadR52(event);
        }
        private BeforeServerLoadSubscriberR52(){}
    }
    public static boolean geometryReadyR52(){return geometryInstalled;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(SAMPLE,new CompoundTag());}
    public static void resetOriginalMaintenanceR53(EvaUnit01Entity eva){var old=eva.getEntityData().get(SAMPLE);var next=new CompoundTag();for(String key:List.of("PlantCarrierR52","OriginalCarrierUUIDR52","OriginalCarrierEntityR52"))if(old.contains(key))next.put(key,old.get(key).copy());eva.getEntityData().set(SAMPLE,next);GEOMETRY.remove(eva);HELD_GEOMETRY.remove(eva);}
    public static boolean active(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getBoolean("Active");}
    public static RigidTransform carriedPlugTransformR53(EvaUnit01Entity eva,float partial)
    {if(!active(eva))throw new IllegalStateException("Actual carried capsule frame required");return frame(eva,partial).compose(decode(eva.getEntityData().get(SAMPLE).getCompound("PlugLocal")));}
    public static boolean ballisticCustodyR52(EvaUnit01Entity eva){return active(eva)&&eva.getEntityData().get(SAMPLE).getBoolean("BallisticR52");}
    public static java.util.UUID originalCarrierUUIDR52(EvaUnit01Entity e){var t=e.getEntityData().get(SAMPLE);return t.hasUUID("OriginalCarrierUUIDR52")?t.getUUID("OriginalCarrierUUIDR52"):null;}
    public static boolean hasOriginalCarrierControllerR52(EvaUnit01Entity e){return originalCarrierUUIDR52(e)!=null;}
    public static NervCarrierPlatformEntity originalCarrierControllerR52(EvaUnit01Entity e){var t=e.getEntityData().get(SAMPLE);if(!t.hasUUID("OriginalCarrierUUIDR52"))return null;var actor=e.level() instanceof ServerLevel l?l.getEntity(t.getUUID("OriginalCarrierUUIDR52")):e.level().getEntity(t.getInt("OriginalCarrierEntityR52"));if(e.level().isClientSide&&(actor==null||!actor.getUUID().equals(t.getUUID("OriginalCarrierUUIDR52"))))
    {
        for(var candidate:e.level().getEntitiesOfClass(NervCarrierPlatformEntity.class,e.getBoundingBox().inflate(96)))
            if(candidate.getUUID().equals(t.getUUID("OriginalCarrierUUIDR52")))
            {actor=candidate;var synced=t.copy();synced.putInt("OriginalCarrierEntityR52",candidate.getId());e.getEntityData().set(SAMPLE,synced);break;}
    }
    return actor instanceof NervCarrierPlatformEntity n&&n.getUUID().equals(t.getUUID("OriginalCarrierUUIDR52"))&&com.projectseele.world.NervOriginalCarrierR52.declared(n)&&n.originalCarrierStateR52().getUUID("OriginalEva").equals(e.getUUID())?n:null;}
    public static void bindOriginalCarrierControllerR52(EvaUnit01Entity e,NervCarrierPlatformEntity n){if(e.level().isClientSide||!com.projectseele.world.NervOriginalCarrierR52.declared(n)||!n.originalCarrierStateR52().getUUID("OriginalEva").equals(e.getUUID()))throw new IllegalStateException("Actual original carrier/controller identity required");var t=e.getEntityData().get(SAMPLE).copy();if(t.hasUUID("OriginalCarrierUUIDR52")&&!t.getUUID("OriginalCarrierUUIDR52").equals(n.getUUID()))throw new IllegalStateException("Original carrier identity cannot be replaced");t.putUUID("OriginalCarrierUUIDR52",n.getUUID());t.putInt("OriginalCarrierEntityR52",n.getId());e.getEntityData().set(SAMPLE,t);}
    public static boolean detachedCarrierR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getBoolean("CarrierDetachedR52");}
    /** A deployed dolly stays at its audited well while the original EVA
     * follows native gravity. Renderer, gate guard and sweep share this frame. */
    public static RigidTransform carrierFrameR52(EvaUnit01Entity eva,float partial)
    {var controller=originalCarrierControllerR52(eva);if(controller!=null)return com.projectseele.world.NervOriginalCarrierR52.actualRoot(controller,partial);if(hasOriginalCarrierControllerR52(eva)&&!eva.level().isClientSide)throw new IllegalStateException("Declared original carrier controller is not loaded");var t=eva.getEntityData().get(SAMPLE);return detachedCarrierR52(eva)?decode(t.getCompound("CarrierRootR52")):active(eva)?frame(eva,partial):com.projectseele.world.NervOwnerPlacementR52.actualRoot(eva);}
    public static boolean reattachCarrierR52(EvaUnit01Entity eva)
    {if(!(eva.level() instanceof ServerLevel level)||!same(carrierFrameR52(eva,1),com.projectseele.world.NervOwnerPlacementR52.actualRoot(eva))||!com.projectseele.world.NervMappedPlugMechanicsR52.actualCarrierFootBearing(level,eva))return false;var controller=originalCarrierControllerR52(eva);if(controller!=null)try{if(!com.projectseele.world.NervOriginalCarrierR52.setAttachedR52(level,controller,eva,true))return false;}catch(java.io.IOException missing){return false;}var tag=eva.getEntityData().get(SAMPLE).copy();tag.remove("CarrierDetachedR52");tag.remove("CarrierRootR52");eva.getEntityData().set(SAMPLE,tag);return true;}
    public static int ballisticTicksR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getInt("BallisticTicksR52");}
    public static CompoundTag groundReleaseStateR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getCompound("GroundReleaseR52").copy();}
    public static void groundReleaseStateR52(EvaUnit01Entity eva,CompoundTag state)
    {if(eva.level().isClientSide||!active(eva))throw new IllegalStateException("Actual server mechanical source required");var next=eva.getEntityData().get(SAMPLE).copy();next.put("GroundReleaseR52",state.copy());eva.getEntityData().set(SAMPLE,next);}
    public static boolean applyGroundedPoseR52(EvaUnit01Entity eva,Original original,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands,EvaOriginalMeshGeometryR52.Geometry geometry)
    {
        if(!active(eva)||epoch(eva)!=original.epoch()||originalPlug(eva,original)==null||!geometry.sourceFingerprint().equals(capturedGeometry(eva).sourceFingerprint()))return false;
        var root=frame(eva,1);var forward=root.transformVector(new Vec3(0,0,1));float yaw=180-(float)(Math.atan2(forward.x,forward.z)*Mth.RAD_TO_DEG);var plug=emptySocketReferenceR52(body,EvaRifleKinematics.frameWorldR52(eva.position(),yaw),EvaDorsalProfile.of(eva));var priorBody=EvaShutdownR30.encode(frozenLocalPose(eva));var cradle=EvaAirTransportR31.cradleStateR50(eva).copy();cradle.put("Origin",EvaShutdownR30.encode(body));cradle.put(EvaFrozenHandsR52.KEY,EvaFrozenHandsR52.encode(eva.getUnitVariant(),EvaAnatomicalHandsR45.contractFingerprintR45(eva.getUnitVariant()),hands));
        EvaAirTransportR31.cradleStateR50(eva,cradle);var tag=eva.getEntityData().get(SAMPLE).copy();tag.put("RecoveryPreviousBodyR52",priorBody);tag.putLong("RecoveryAtR52",eva.level().getGameTime());tag.put("PlugLocal",encode(root.inverse().compose(plug)));tag.putLong("CapturedAt",eva.level().getGameTime());eva.getEntityData().set(SAMPLE,tag);synchronized(GEOMETRY){GEOMETRY.put(eva,new CapturedGeometry(eva.level().getGameTime(),geometry));}eva.setBoundingBox(bounds(eva));originalPlug(eva,original).setCanonicalTransform(plug);originalPlug(eva,original).syncPilotPositionNow();return true;
    }
    /** A private-constructor full-source proof owns each small airborne
     * recovery change. The separated original capsule/pilot are untouched. */
    public static boolean acceptRecoveryStepR52(EvaUnit01Entity eva,com.projectseele.world.NervHullGroundRecoveryR52.AcceptedRecoveryStep proof){if(!(eva.level() instanceof ServerLevel l)||proof==null||!proof.current(l)||!proof.original().eva().equals(eva.getUUID())||!active(eva)||!flightCustody(eva)||kind(eva)!=Kind.HULL_ONLY_RECOVERY||epoch(eva)!=proof.original().epoch()||proof.checkedAt()!=l.getGameTime()||!same(frame(eva,1),proof.fromRoot())||!proof.sourceFingerprint().equals(capturedGeometry(eva).sourceFingerprint())||!EvaFrozenHandsR52.capture(eva,1).equals(proof.hands()))return false;var nextBody=proof.toBody();var priorBody=proof.fromBody();if(!EvaPoseSnapshotR50.bones(nextBody).equals(EvaPoseSnapshotR50.bones(priorBody)))return false;for(String bone:EvaPoseSnapshotR50.bones(nextBody)){var row=nextBody.getList(bone,net.minecraft.nbt.Tag.TAG_FLOAT);if(row.size()!=9||row.getFloat(6)!=1||row.getFloat(7)!=1||row.getFloat(8)!=1)return false;}var cradle=EvaAirTransportR31.cradleStateR50(eva).copy();cradle.put("Origin",nextBody.copy());EvaAirTransportR31.cradleStateR50(eva,cradle);var tag=eva.getEntityData().get(SAMPLE).copy();tag.put("Previous",encode(proof.fromRoot()));tag.put("Current",encode(proof.toRoot()));tag.put("RecoveryPreviousBodyR52",priorBody.copy());tag.putLong("RecoveryAtR52",l.getGameTime());tag.putLong("AcceptedAt",l.getGameTime());tag.putLong("CapturedAt",l.getGameTime());tag.put("Left",point(proof.binding().leftFoot()));tag.put("Right",point(proof.binding().rightFoot()));tag.put("PlugLocal",encode(proof.binding().plugInEva()));eva.getEntityData().set(SAMPLE,tag);synchronized(GEOMETRY){GEOMETRY.put(eva,new CapturedGeometry(l.getGameTime(),proof.geometry()));}var p=proof.toRoot().translation();eva.setPos(p.x,p.y,p.z);eva.setBoundingBox(bounds(eva));eva.setDeltaMovement(Vec3.ZERO);eva.resetFallDistance();return true;}
    public static boolean beginBallisticR52(EvaUnit01Entity eva,Original original,double velocity)
    {
        if(!(eva.level() instanceof ServerLevel)||eva.noPhysics||!active(eva)||ballisticCustodyR52(eva)||kind(eva)!=Kind.OCCUPIED||epoch(eva)!=original.epoch()||originalPlug(eva,original)==null||eva.carrierRiseProgress(1)!=1||!Double.isFinite(velocity)||velocity<=0)return false;
        var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-baseYaw(eva))*Mth.DEG_TO_RAD));if(!same(basis,frame(eva,1))||detachedCarrierR52(eva)&&!same(carrierFrameR52(eva,1),basis))return false;
        var carrier=originalCarrierControllerR52(eva);if(carrier!=null)try{if(!com.projectseele.world.NervOriginalCarrierR52.setAttachedR52((ServerLevel)eva.level(),carrier,eva,false))return false;}catch(java.io.IOException missing){return false;}var t=eva.getEntityData().get(SAMPLE).copy();t.putBoolean("CarrierDetachedR52",true);t.put("CarrierRootR52",encode(basis));t.putBoolean("BallisticR52",true);t.putInt("BallisticTicksR52",0);t.putDouble("BallisticInitialVelocityR53",velocity);t.putLong("BallisticLastTickR52",Long.MIN_VALUE);eva.getEntityData().set(SAMPLE,t);
        eva.clearSortieDestination();eva.getNavigation().stop();eva.setTarget(null);eva.setNoGravity(false);eva.setOnGround(false);eva.setDeltaMovement(0,velocity,0);eva.hasImpulse=true;eva.resetFallDistance();return true;
    }
    /** R50 scripted departure retains the original impulse and actor roots.
     * Ordinary movement outside this handoff keeps native collision response. */
    public static void travelBallisticR52(EvaUnit01Entity eva)
    {
        if(!ballisticCustodyR52(eva)||!(eva.level() instanceof ServerLevel level))return;var old=eva.getEntityData().get(SAMPLE);if(old.getLong("BallisticLastTickR52")==level.getGameTime())return;
        boolean scripted=com.projectseele.world.NervR50CarrierModeR53.enabled();
        if(scripted&&old.getInt("BallisticTicksR52")>=com.projectseele.world.NervBallisticHandoffR52.FLIGHT_TICKS)
        {
            eva.setDeltaMovement(Vec3.ZERO);
            return;
        }
        // Native landing has already stopped the body. Retain that accepted
        // tick while ordinary release waits; a removed real bearing resumes
        // the native gravity path below, even after a release was captured.
        if(eva.onGround()&&eva.getDeltaMovement().lengthSqr()<1e-10&&EvaMechanicalReleaseR52.actualGroundBearingR52(level,eva,capturedGeometry(eva),frame(eva,1)))return;
        var before=eva.getBoundingBox();var previous=frame(eva,1);var velocity=eva.getDeltaMovement();
        if(scripted&&old.contains("BallisticInitialVelocityR53"))
        {
            double gravity=eva.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get()),v=old.getDouble("BallisticInitialVelocityR53");
            for(int tick=0;tick<old.getInt("BallisticTicksR52");tick++)v=(v-gravity)*.98;
            velocity=new Vec3(0,v,0);
        }
        boolean priorPhysics=eva.noPhysics;if(scripted)eva.noPhysics=true;
        eva.getPersistentData().putBoolean("MechanicalNativeMoveR53",true);
        try{if(scripted)eva.setBoundingBox(before.move(velocity));else eva.move(net.minecraft.world.entity.MoverType.SELF,velocity);}
        finally{eva.noPhysics=priorPhysics;eva.getPersistentData().remove("MechanicalNativeMoveR53");}
        var root=rootAfterNativeMove(previous.translation(),before,eva.getBoundingBox());var current=new RigidTransform(root,previous.qx(),previous.qy(),previous.qz(),previous.qw());
        var next=old.copy();next.put("Previous",encode(previous));next.put("Current",encode(current));next.putLong("AcceptedAt",level.getGameTime());next.putLong("BallisticLastTickR52",level.getGameTime());next.putInt("BallisticTicksR52",old.getInt("BallisticTicksR52")+1);eva.getEntityData().set(SAMPLE,next);eva.setPos(root.x,root.y,root.z);eva.setBoundingBox(bounds(eva));
        double gravity=eva.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get());eva.setDeltaMovement(!scripted&&eva.onGround()?Vec3.ZERO:new Vec3(velocity.x*.91,(scripted?velocity.y-gravity:eva.verticalCollision?0:velocity.y-gravity)*.98,velocity.z*.91));eva.resetFallDistance();eva.hasImpulse=true;
        if(level.getEntity(next.getUUID("Plug")) instanceof EntryPlugCarrierEntity plug&&plug.getVehicle()==eva){plug.setCanonicalTransform(current.compose(decode(next.getCompound("PlugLocal"))));plug.syncPilotPositionNow();}
    }
    private static void retainCarrier(CompoundTag old,CompoundTag next)
    {next.putBoolean("PlantCarrierR52",old.getBoolean("PlantCarrierR52"));if(old.hasUUID("OriginalCarrierUUIDR52")){next.putUUID("OriginalCarrierUUIDR52",old.getUUID("OriginalCarrierUUIDR52"));next.putInt("OriginalCarrierEntityR52",old.getInt("OriginalCarrierEntityR52"));}if(old.contains("GroundGuideSourceR52")){next.putString("GroundGuideSourceR52",old.getString("GroundGuideSourceR52"));if(old.contains("Left")&&old.contains("Right")){next.put("GuideLeftR52",old.getCompound("Left").copy());next.put("GuideRightR52",old.getCompound("Right").copy());}else if(old.contains("GuideLeftR52")&&old.contains("GuideRightR52")){next.put("GuideLeftR52",old.getCompound("GuideLeftR52").copy());next.put("GuideRightR52",old.getCompound("GuideRightR52").copy());}}if(old.getBoolean("CarrierDetachedR52")){next.putBoolean("CarrierDetachedR52",true);next.put("CarrierRootR52",old.getCompound("CarrierRootR52").copy());}}
    public static boolean plantCarrierDeclaredR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getBoolean("PlantCarrierR52");}
    public static boolean groundGuidesDeclaredR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getString("GroundGuideSourceR52").equals(com.projectseele.world.NervFootGuideRigR52.SOURCE_SHA);}
    public static void declareGroundGuidesR52(EvaUnit01Entity eva){if(eva.level().isClientSide)throw new IllegalStateException("Actual server guide declaration required");var tag=eva.getEntityData().get(SAMPLE).copy();tag.putString("GroundGuideSourceR52",com.projectseele.world.NervFootGuideRigR52.SOURCE_SHA);eva.getEntityData().set(SAMPLE,tag);}
    public static FootSupportFrameR52.Binding groundGuideBindingR52(EvaUnit01Entity eva){var tag=eva.getEntityData().get(SAMPLE);if(active(eva)&&tag.contains("Left")&&tag.contains("Right"))return new FootSupportFrameR52.Binding(point(tag.getCompound("Left")),point(tag.getCompound("Right")),RigidTransform.identity());if(tag.contains("GuideLeftR52")&&tag.contains("GuideRightR52"))return new FootSupportFrameR52.Binding(point(tag.getCompound("GuideLeftR52")),point(tag.getCompound("GuideRightR52")),RigidTransform.identity());try{return com.projectseele.world.NervFootGuideRigR52.nominalBinding(eva.getUnitVariant());}catch(java.io.IOException missing){throw new IllegalStateException("Actual declared guide binding unavailable",missing);}}
    public static boolean serviceSourceHeldR52(EvaUnit01Entity eva){boolean held=!active(eva)&&eva.getEntityData().get(SAMPLE).getBoolean("ServiceSourceHeldR52");if(held&&eva.level().isClientSide&&!geometryInstalled)try{installGeometry();}catch(java.io.IOException missing){throw new IllegalStateException("Original service render source unavailable",missing);}return held;}
    public static EvaAnatomicalHandsR45.Pose serviceHandsR52(EvaUnit01Entity eva)
    {if(!serviceSourceHeldR52(eva))throw new IllegalStateException("Actual occupied service source absent");var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();return EvaFrozenHandsR52.decode(eva.getUnitVariant(),provider.handContractFingerprint(eva.getUnitVariant()),provider.handJoints(eva.getUnitVariant()),eva.getEntityData().get(SAMPLE).getCompound("HeldHands"));}
    public static EvaBodyPose.Sample serviceBodyR52(EvaUnit01Entity eva)
    {if(!serviceSourceHeldR52(eva))throw new IllegalStateException("Actual occupied service source absent");var data=eva.getEntityData().get(SAMPLE);var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();if(!data.getString("HeldGeometrySource").equals(provider.sourceFingerprint()))throw new IllegalStateException("Held actual occupied service geometry changed");var body=EvaBodyPose.neutralForTransportR32(eva);var encoded=data.getCompound("HeldBody");if(!EvaPoseSnapshotR50.bones(encoded).equals(body.rig.keySet()))throw new IllegalStateException("Saved held service body lost original bones");for(String bone:body.rig.keySet()){var row=encoded.getList(bone,net.minecraft.nbt.Tag.TAG_FLOAT);if(row.size()!=9||row.getFloat(6)!=1||row.getFloat(7)!=1||row.getFloat(8)!=1)throw new IllegalStateException("Saved held service body changed original unit-scale channels");}EvaShutdownR30.decode(encoded,body);return com.projectseele.world.NervServiceBodyPoseR52.applyDorsal(body,EvaDorsalProfile.of(eva),EvaDorsalMechanism.open(eva),EvaDorsalMechanism.bow(eva));}
    public static EvaOriginalMeshGeometryR52.Geometry serviceGeometryR52(EvaUnit01Entity eva)
    {
        var data=eva.getEntityData().get(SAMPLE);var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();if(!serviceSourceHeldR52(eva)||!data.getString("HeldGeometrySource").equals(provider.sourceFingerprint()))throw new IllegalStateException("Held actual occupied geometry/source absent");long at=data.getLong("HeldAt");float open=EvaDorsalMechanism.open(eva),bow=EvaDorsalMechanism.bow(eva);var body=data.getCompound("HeldBody");var hands=data.getCompound("HeldHands");synchronized(HELD_GEOMETRY){var old=HELD_GEOMETRY.get(eva);if(old!=null&&old.at()==at&&old.open()==open&&old.bow()==bow&&old.body().equals(body)&&old.hands().equals(hands))return old.geometry();var geometry=provider.evaluateMechanicalService(eva.getUnitVariant(),serviceBodyR52(eva),serviceHandsR52(eva),open>=.002F);HELD_GEOMETRY.put(eva,new HeldGeometry(at,open,bow,body.copy(),hands.copy(),geometry));return geometry;}
    }
    public static AABB serviceBoundsR52(EvaUnit01Entity eva)
    {var geometry=serviceGeometryR52(eva);var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-eva.getEntityData().get(SAMPLE).getFloat("HeldYaw"))*Mth.DEG_TO_RAD));AABB result=null;for(var p:geometry.parts()){var b=com.projectseele.world.NervRigidMeshSweepR52.transformed(p.bounds(),basis);result=result==null?b:result.minmax(b);}return result;}
    /** Atomic custody handoff to the original stationary service mechanism.
     * The real dorsal channels remain live; clearing the transport sample
     * cannot expose a factory pose or discard the 34 captured hand joints. */
    public static boolean releaseToServiceR52(EvaUnit01Entity eva,Original original)
    {
        if(serviceSourceHeldR52(eva)&&epoch(eva)==original.epoch()&&eva.getUUID().equals(original.eva())&&eva.isNervLogisticsLocked()&&originalPlug(eva,original)!=null)
        {eva.setBoundingBox(serviceBoundsR52(eva));return true;}
        if(!active(eva)||kind(eva)!=Kind.OCCUPIED||epoch(eva)!=original.epoch()||!eva.isNervLogisticsLocked()||originalPlug(eva,original)==null)return false;
        var received=frame(eva,1);var forward=received.transformVector(new Vec3(0,0,1));float heldYaw=180-(float)(Math.atan2(forward.x,forward.z)*Mth.RAD_TO_DEG);
        var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-heldYaw)*Mth.DEG_TO_RAD));if(!same(basis,received)||EvaDorsalMechanism.open(eva)>=.0001F||EvaDorsalMechanism.bow(eva)>=.0001F)return false;
        var body=EvaShutdownR30.encode(frozenLocalPose(eva));var hands=EvaAirTransportR31.cradleStateR50(eva).getCompound(EvaFrozenHandsR52.KEY).copy();String source=capturedGeometry(eva).sourceFingerprint();var stance=originalStanceR52(eva);
        eva.adoptVerifiedMechanicalReleaseYawR52(heldYaw);
        var tag=new CompoundTag();retainCarrier(eva.getEntityData().get(SAMPLE),tag);tag.putBoolean("ServiceSourceHeldR52",true);tag.put("HeldBody",body);tag.put("HeldHands",hands);tag.putString("HeldGeometrySource",source);tag.putFloat("HeldYaw",heldYaw);tag.putLong("HeldAt",eva.level().getGameTime());tag.putLong("Epoch",original.epoch());tag.put("OriginStance",stance);
        // Publish the held source before clearing its old cradle. Capsule
        // synchronization never observes an intervening factory skeleton.
        eva.getEntityData().set(SAMPLE,tag);EvaAirTransportR31.clear(eva);synchronized(GEOMETRY){GEOMETRY.remove(eva);}eva.setBoundingBox(serviceBoundsR52(eva));originalPlug(eva,original).syncPilotPositionNow();return true;
    }
    /** Preserve the final recovered skeleton and all 34 hands in the original
     * service sample after the owner proves real pads and a restored floor. */
    public static boolean releaseHullToServiceR52(EvaUnit01Entity eva,Original original)
    {
        if(serviceSourceHeldR52(eva)&&kind(eva)==Kind.HULL_ONLY_RECOVERY&&epoch(eva)==original.epoch()&&originalHull(eva,original)&&eva.isNervLogisticsLocked())
        {eva.setBoundingBox(serviceBoundsR52(eva));return true;}
        if(!active(eva)||kind(eva)!=Kind.HULL_ONLY_RECOVERY||epoch(eva)!=original.epoch()||!originalHull(eva,original)||!eva.isNervLogisticsLocked())return false;
        var received=frame(eva,1);var forward=received.transformVector(new Vec3(0,0,1));float yaw=180-(float)(Math.atan2(forward.x,forward.z)*Mth.RAD_TO_DEG);
        var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-yaw)*Mth.DEG_TO_RAD));if(!same(basis,received))return false;
        var body=frozenLocalPose(eva);var hands=EvaFrozenHandsR52.frozen(eva);var frozenHands=EvaAirTransportR31.cradleStateR50(eva).getCompound(EvaFrozenHandsR52.KEY).copy();String source=capturedGeometry(eva).sourceFingerprint();var world=bounds(eva);var stance=originalStanceR52(eva);
        eva.adoptVerifiedMechanicalReleaseYawR52(yaw);
        var tag=new CompoundTag();retainCarrier(eva.getEntityData().get(SAMPLE),tag);tag.putBoolean("ServiceSourceHeldR52",true);tag.putString("Kind",Kind.HULL_ONLY_RECOVERY.name());tag.put("HeldBody",EvaShutdownR30.encode(body));tag.put("HeldHands",frozenHands);tag.putString("HeldGeometrySource",source);tag.putFloat("HeldYaw",yaw);tag.putLong("HeldAt",eva.level().getGameTime());tag.putLong("Epoch",original.epoch());tag.put("OriginStance",stance);
        hands.rotations().forEach((name,q)->{body.rotations.put(name,new Quaternionf(q));body.positions.put(name,new Vector3f());});EvaShutdownR30.physicalRest(eva,body,world);
        eva.getEntityData().set(SAMPLE,tag);EvaAirTransportR31.clear(eva);synchronized(GEOMETRY){GEOMETRY.remove(eva);}eva.setBoundingBox(serviceBoundsR52(eva));return true;
    }
    public static double carrierDeckTravelR52(EvaUnit01Entity eva){return eva.recoveryRackR39()?3:0;}
    public static void declarePlantCarrierR52(EvaUnit01Entity eva)
    {if(!(eva.level() instanceof net.minecraft.server.level.ServerLevel level)||!com.projectseele.world.NervRouteRuntimeR52.claimed(level)||eva.isExperimentalUnit())throw new IllegalStateException("Claimed actual original plant required");var tag=eva.getEntityData().get(SAMPLE).copy();tag.putBoolean("PlantCarrierR52",true);eva.getEntityData().set(SAMPLE,tag);}
    public static boolean flightCustody(EvaUnit01Entity eva){return active(eva)&&eva.getEntityData().get(SAMPLE).getBoolean("FlightCustody");}
    public static boolean flightCarrierVisible(EvaUnit01Entity eva){return flightCustody(eva)&&eva.getEntityData().get(SAMPLE).getBoolean("ActualCarrierVisible");}
    /** Preserve the actual pre-pickup carrier inventory in the same sample
     * that owns the frozen body; capture must not make a hidden rack appear. */
    public static void setFlightCustody(EvaUnit01Entity eva,boolean flight,boolean actualCarrierVisible)
    {if(!active(eva))throw new IllegalStateException("Actual rigid custody required");var data=eva.getEntityData().get(SAMPLE).copy();data.putBoolean("FlightCustody",flight);data.putBoolean("ActualCarrierVisible",actualCarrierVisible);eva.getEntityData().set(SAMPLE,data);}
    public static void save(EvaUnit01Entity eva,CompoundTag tag){tag.put("R52MechanicalSample",eva.getEntityData().get(SAMPLE).copy());}
    public static void load(EvaUnit01Entity eva,CompoundTag tag){eva.getEntityData().set(SAMPLE,tag.getCompound("R52MechanicalSample").copy());}
    public static float baseYaw(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getFloat("BaseYaw");}
    public static long epoch(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getLong("Epoch");}
    public static Kind kind(EvaUnit01Entity eva)
    {var t=eva.getEntityData().get(SAMPLE);return t.contains("Kind")?Kind.valueOf(t.getString("Kind")):Kind.OCCUPIED;}
    public static boolean releasedHullRest(EvaUnit01Entity eva)
    {return eva.getEntityData().get(SAMPLE).getBoolean("ReleasedHull")&&!active(eva)&&kind(eva)==Kind.HULL_ONLY_RECOVERY
            &&EvaShutdownR30.disabled(eva)&&eva.getPassengers().isEmpty()&&!EvaAirTransportR31.active(eva)&&!com.projectseele.physics.CombatBodyDynamics.active(eva);}
    public static Vec3 rootAfterNativeMove(Vec3 previousRoot,AABB before,AABB after)
    {return EvaMechanicalFrameMathR52.rootAfterNativeMove(previousRoot,before,after);}
    /** Read before obtaining the mechanical lock; this is actual displayed
     * stopped custody, not a pose selected after a locked factory override. */
    public static final class HullCapture
    {
        private final Original original;private final CompoundTag stopped,hands;private final Vec3 position;private final float yaw;
        private HullCapture(Original original,CompoundTag stopped,CompoundTag hands,Vec3 position,float yaw)
        {this.original=original;this.stopped=stopped.copy();this.hands=hands.copy();this.position=position;this.yaw=yaw;}
    }
    public static HullCapture prepareHullCapture(EvaUnit01Entity eva,Original original)
    {
        if(!originalHull(eva,original)||!geometryInstalled||eva.isNervLogisticsLocked()||!EvaShutdownR30.displayed(eva)||EvaShutdownR30.pose(eva).isEmpty()
                ||EvaAirTransportR31.active(eva)||eva.hasActiveCarrierMotion()||eva.isLaunchSequenceActive()||eva.isFirstBattleActive()
                ||com.projectseele.physics.CombatBodyDynamics.active(eva)||EvaShutdownR30.collapse(eva,1)!=1)return null;
        var actual=EvaBodyPose.sample(eva,1);var retained=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(EvaShutdownR30.pose(eva),retained);
        if(!samePose(actual,retained))return null;
        return new HullCapture(original,EvaShutdownR30.pose(eva),EvaFrozenHandsR52.capture(eva,1),eva.position(),EvaAirTransportR31.frameYaw(eva,1));
    }

    /** Observed occupied field custody before any plant lock; same frozen
     * renderer joints/hand pose and real capsule relation are retained. */
    public static final class OccupiedCapture
    {
        private final Original original;private final CompoundTag body,hands,stance;private final Vec3 position;private final float yaw;private final RigidTransform plug;private final EvaOriginalMeshGeometryR52.Geometry geometry;
        private OccupiedCapture(Original o,EvaBodyPose.Sample body,CompoundTag hands,EvaUnit01Entity e,float yaw,RigidTransform plug,EvaOriginalMeshGeometryR52.Geometry geometry)
        {original=o;this.body=EvaShutdownR30.encode(body);this.hands=hands.copy();stance=e.captureMechanicalStanceR52();if(com.projectseele.world.NervR50CarrierModeR53.enabled()){var guide=groundGuideBindingR52(e);stance.put("R50GuideLeftR53",point(guide.leftFoot()));stance.put("R50GuideRightR53",point(guide.rightFoot()));}position=e.position();this.yaw=yaw;this.plug=plug;this.geometry=geometry;}
    }
    public static OccupiedCapture prepareOccupiedRecovery(EvaUnit01Entity e,Original o)
    {
        var plug=originalPlug(e,o);if(plug==null||!geometryInstalled||e.isNervLogisticsLocked()||e.isFirstBattleActive()||e.isBerserk()||e.isLaunchSequenceActive()||e.hasActiveCarrierMotion()
                ||EvaAirTransportR31.active(e)||com.projectseele.physics.CombatBodyDynamics.active(e)||!com.projectseele.world.NervR50CarrierModeR53.enabled()&&!com.projectseele.world.EvaLogisticsDirector.recoveryMotionSettled(e)
                ||!plug.isHatchFullySealed())return null;
        if(!com.projectseele.world.NervR50CarrierModeR53.enabled()&&(e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||EvaShieldRigR47.equipped(e)||EvaDorsalMechanism.open(e)>=.0001F||EvaDorsalMechanism.bow(e)>=.0001F||EvaBerserkMotionR34.mouth(e,1)!=0))return null;
        var body=EvaBodyPose.sample(e,1);var hands=EvaFrozenHandsR52.capture(e,1);var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var geometry=provider.evaluate(e.getUnitVariant(),body,EvaFrozenHandsR52.decode(e.getUnitVariant(),provider.handContractFingerprint(e.getUnitVariant()),provider.handJoints(e.getUnitVariant()),hands));
        float yaw=EvaAirTransportR31.frameYaw(e,1);var socket=emptySocketReferenceR52(body,EvaRifleKinematics.frameWorldR52(e.position(),yaw),EvaDorsalProfile.of(e));if(!com.projectseele.world.NervR50CarrierModeR53.enabled()&&!same(socket,plug.getCanonicalTransform()))return null;
        return new OccupiedCapture(o,body,hands,e,yaw,plug.getCanonicalTransform(),geometry);
    }
    public static boolean occupiedPreviewCurrent(EvaUnit01Entity e,Original o,OccupiedCapture proof)
    {if(proof==null||!proof.original.equals(o)||e.isNervLogisticsLocked()||e.position().distanceToSqr(proof.position)>1e-12||e.yBodyRot!=proof.yaw)return false;var plug=originalPlug(e,o);if(plug==null||!same(plug.getCanonicalTransform(),proof.plug))return false;var body=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(proof.body,body);return samePose(body,EvaBodyPose.sample(e,1))&&EvaFrozenHandsR52.capture(e,1).equals(proof.hands);}
    public static FootSupportFrameR52.Binding occupiedPreviewBinding(OccupiedCapture proof)
    {var basis=RigidTransform.of(proof.position,new Quaternionf().rotationY((180-proof.yaw)*Mth.DEG_TO_RAD));return new FootSupportFrameR52.Binding(proof.stance.contains("R50GuideLeftR53")?point(proof.stance.getCompound("R50GuideLeftR53")):sole(proof.geometry,"foot_l"),proof.stance.contains("R50GuideRightR53")?point(proof.stance.getCompound("R50GuideRightR53")):sole(proof.geometry,"foot_r"),basis.inverse().compose(proof.plug));}
    public static RigidTransform occupiedPreviewFrame(OccupiedCapture proof)
    {return RigidTransform.of(proof.position,new Quaternionf().rotationY((180-proof.yaw)*Mth.DEG_TO_RAD));}
    public static boolean captureOccupiedRecovery(EvaUnit01Entity e,Original o,OccupiedCapture proof)
    {return proof!=null&&capture(e,o,Kind.OCCUPIED,null,proof);}

    private static CompoundTag encode(RigidTransform frame)
    {
        var t=new CompoundTag();t.putDouble("X",frame.translation().x);t.putDouble("Y",frame.translation().y);t.putDouble("Z",frame.translation().z);
        t.putFloat("QX",frame.qx());t.putFloat("QY",frame.qy());t.putFloat("QZ",frame.qz());t.putFloat("QW",frame.qw());return t;
    }
    private static RigidTransform decode(CompoundTag t)
    {
        var point=new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z"));
        float x=t.getFloat("QX"),y=t.getFloat("QY"),z=t.getFloat("QZ"),w=t.getFloat("QW");
        if(!Double.isFinite(point.lengthSqr())||!Float.isFinite(x+y+z+w)||Math.abs(x*x+y*y+z*z+w*w-1)>.002)
            throw new IllegalStateException("Invalid saved mechanical rigid frame");
        return new RigidTransform(point,x,y,z,w);
    }
    private record ClientContinuousWindowR52(long sequence,int receivedEntityTick,CompoundTag encoded,com.projectseele.world.DirectoryTrajectoryR52.PortableWindowR52 path,com.projectseele.world.NervMechanicalTravelR52.ContinuousProfile profile,long ticks){}
    private static final Map<EvaUnit01Entity,ClientContinuousWindowR52> CLIENT_CONTINUOUS_R52=new WeakHashMap<>();
    private record ClientContinuousReceiptR52(long sequence,int entityTick){}
    private static final Map<EvaUnit01Entity,ClientContinuousReceiptR52> CLIENT_CONTINUOUS_RECEIPTS_R52=new WeakHashMap<>();
    /** Latch receipt on the actual synchronized accessor callback, before any component renders. */
    public static void onSyncedDataUpdatedR52(EvaUnit01Entity eva,EntityDataAccessor<?> key)
    {if(!eva.level().isClientSide||key!=SAMPLE)return;var tag=eva.getEntityData().get(SAMPLE);synchronized(CLIENT_CONTINUOUS_R52){if(!tag.contains("ContinuousWindowR52",net.minecraft.nbt.Tag.TAG_COMPOUND)){CLIENT_CONTINUOUS_R52.remove(eva);CLIENT_CONTINUOUS_RECEIPTS_R52.remove(eva);return;}long sequence=tag.getCompound("ContinuousWindowR52").getLong("Sequence");var previous=CLIENT_CONTINUOUS_RECEIPTS_R52.get(eva);if(previous==null||previous.sequence()!=sequence)CLIENT_CONTINUOUS_RECEIPTS_R52.put(eva,new ClientContinuousReceiptR52(sequence,eva.tickCount));}}
    private static int receivedContinuousTickR52(EvaUnit01Entity eva,long sequence)
    {var receipt=CLIENT_CONTINUOUS_RECEIPTS_R52.get(eva);return receipt!=null&&receipt.sequence()==sequence?receipt.entityTick():eva.tickCount;}

    /** EVA, original capsule and original carrier consume this same received curve window. */
    public static boolean continuousWindowR52(EvaUnit01Entity eva)
    {return active(eva)&&eva.getEntityData().get(SAMPLE).contains("ContinuousWindowR52",net.minecraft.nbt.Tag.TAG_COMPOUND);}
    private static com.projectseele.world.NervMechanicalTravelR52.ContinuousProfile continuousProfileR52(CompoundTag tag)
    {return new com.projectseele.world.NervMechanicalTravelR52.ContinuousProfile(tag.getDouble("FromMetres"),tag.getDouble("ToMetres"),tag.getDouble("CruiseMps"),tag.getDouble("AccelerationMps2"),tag.getDouble("DecelerationMps2"),tag.getDouble("InitialMps"));}
    private static RigidTransform continuousFrameR52(EvaUnit01Entity eva,CompoundTag sample,RigidTransform current,float partial)
    {
        if(sample.getBoolean("ContinuousHeldR52"))return current;var encoded=sample.getCompound("ContinuousWindowR52");long sequence=encoded.getLong("Sequence");
        synchronized(CLIENT_CONTINUOUS_R52)
        {
            try
            {
                var cached=CLIENT_CONTINUOUS_R52.get(eva);if(cached==null||cached.sequence()!=sequence||!cached.encoded().equals(encoded))
                {var clock=encoded.getCompound("Clock");long ticks=clock.getLong("Ticks");if(ticks<0)throw new IllegalArgumentException("Invalid received monotone distance clock");cached=new ClientContinuousWindowR52(sequence,receivedContinuousTickR52(eva,sequence),encoded.copy(),com.projectseele.world.DirectoryTrajectoryR52.decodePortableR52(encoded.getCompound("Path")),continuousProfileR52(clock),ticks);CLIENT_CONTINUOUS_R52.put(eva,cached);}
                // Arrival/entity ticks advance independently of any world-time correction.
                double alpha=Mth.clamp((long)eva.tickCount-cached.receivedEntityTick()+(double)partial,0,1),start=cached.profile().distanceAt(cached.ticks());double local=cached.profile().distanceAt(cached.ticks()+alpha)-start;
                return cached.path().sample(Mth.clamp(local,0,cached.path().lengthMetres()));
            }
            catch(IllegalArgumentException|IllegalStateException invalid){return current;}
        }
    }
    /** Carrier runner/capture rendering uses the same distance fraction as its EVA frame. */
    public static double continuousWindowFractionR52(EvaUnit01Entity eva,float partial)
    {
        var tag=eva.getEntityData().get(SAMPLE);if(!eva.level().isClientSide||!continuousWindowR52(eva)||tag.getBoolean("ContinuousHeldR52"))return 1;
        continuousFrameR52(eva,tag,decode(tag.getCompound("Current")),partial);synchronized(CLIENT_CONTINUOUS_R52){var cached=CLIENT_CONTINUOUS_R52.get(eva);if(cached==null||cached.path().lengthMetres()<=0)return 1;double alpha=Mth.clamp((long)eva.tickCount-cached.receivedEntityTick()+(double)partial,0,1);return Mth.clamp((cached.profile().distanceAt(cached.ticks()+alpha)-cached.profile().distanceAt(cached.ticks()))/cached.path().lengthMetres(),0,1);}
    }
    /** Canonical forward guide direction from the same exact arc-distance window, including recovery. */
    public static Vec3 continuousWindowTangentR52(EvaUnit01Entity eva,float partial)
    {
        var sample=eva.getEntityData().get(SAMPLE);if(!continuousWindowR52(eva))return frame(eva,1).transformVector(new Vec3(0,0,1));var encoded=sample.getCompound("ContinuousWindowR52");
        synchronized(CLIENT_CONTINUOUS_R52)
        {
            var cached=CLIENT_CONTINUOUS_R52.get(eva);if(cached==null||cached.sequence()!=encoded.getLong("Sequence")||!cached.encoded().equals(encoded))
            {var clock=encoded.getCompound("Clock");long ticks=clock.getLong("Ticks");if(ticks<0)throw new IllegalStateException("Invalid shared guide distance clock");cached=new ClientContinuousWindowR52(encoded.getLong("Sequence"),receivedContinuousTickR52(eva,encoded.getLong("Sequence")),encoded.copy(),com.projectseele.world.DirectoryTrajectoryR52.decodePortableR52(encoded.getCompound("Path")),continuousProfileR52(clock),ticks);CLIENT_CONTINUOUS_R52.put(eva,cached);}
            double alpha=!eva.level().isClientSide||sample.getBoolean("ContinuousHeldR52")?1:Mth.clamp((long)eva.tickCount-cached.receivedEntityTick()+(double)partial,0,1);double local=cached.profile().distanceAt(cached.ticks()+alpha)-cached.profile().distanceAt(cached.ticks());return cached.path().tangent(Mth.clamp(local,0,cached.path().lengthMetres()));
        }
    }
    public static void holdContinuousR52(EvaUnit01Entity eva)
    {if(eva.level().isClientSide||!continuousWindowR52(eva))return;var old=eva.getEntityData().get(SAMPLE);if(old.getBoolean("ContinuousHeldR52"))return;var next=old.copy();next.putBoolean("ContinuousHeldR52",true);next.put("Previous",next.getCompound("Current").copy());eva.getEntityData().set(SAMPLE,next);}
    public static RigidTransform frame(EvaUnit01Entity eva,float partial)
    {
        var t=eva.getEntityData().get(SAMPLE);var current=decode(t.getCompound("Current"));
        if(!eva.level().isClientSide)return current;
        if(continuousWindowR52(eva))return continuousFrameR52(eva,t,current,partial);
        var originalCarrier=originalCarrierControllerR52(eva);if(originalCarrier!=null&&com.projectseele.world.NervOriginalCarrierR52.attachedTo(originalCarrier,eva)&&originalCarrier.originalCarrierStateR52().getLong("At")==t.getLong("AcceptedAt")&&same(com.projectseele.world.NervAircraftFrameR52.decodeRigid(originalCarrier.originalCarrierStateR52().getCompound("Current")),current))return com.projectseele.world.NervOriginalCarrierR52.actualRoot(originalCarrier,partial);
        double elapsed=eva.level().getGameTime()-t.getLong("AcceptedAt");
        return decode(t.getCompound("Previous")).interpolate(current,Mth.clamp(elapsed+partial,0,1));
    }
    private static EntryPlugCarrierEntity originalPlug(EvaUnit01Entity eva,Original original)
    {
        if(!(eva.level() instanceof ServerLevel level)||!eva.getUUID().equals(original.eva())||eva.getUnitVariant()!=original.variant()
                ||!level.dimension().location().toString().equals(original.dimension())||eva.getPassengers().size()!=1)return null;
        if(!(level.getEntity(original.plug()) instanceof EntryPlugCarrierEntity plug)||plug.getVehicle()!=eva||!plug.isLockedToEva())return null;
        var pilot=level.getEntity(original.pilot());
        return pilot!=null&&pilot.getVehicle()==plug&&plug.getPassengers().size()==1?plug:null;
    }
    private static boolean originalHull(EvaUnit01Entity eva,Original original)
    {
        return eva.level() instanceof ServerLevel&&eva.getUUID().equals(original.eva())&&eva.getUnitVariant()==original.variant()
                &&eva.level().dimension().location().toString().equals(original.dimension())
                &&TransportMembershipR52.hullRecoveryAdmission(original,eva.getPersistentData(),eva.getPassengers().stream().map(e->e.getUUID()).collect(java.util.stream.Collectors.toSet()),
                        eva.isEntryPlugInserted(),EvaShutdownR30.disabled(eva));
    }
    /** Inspect the actual sole vertices and capsule, with no pose/state edits. */
    public static FootSupportFrameR52.Binding measuredBinding(EvaUnit01Entity eva,Original original)
    {
        boolean hull=active(eva)&&kind(eva)==Kind.HULL_ONLY_RECOVERY;
        if(hull?!originalHull(eva,original):originalPlug(eva,original)==null)throw new IllegalStateException("Original physical custody absent");
        if(active(eva))
        {
            var t=eva.getEntityData().get(SAMPLE);
            if(t.getLong("Epoch")!=original.epoch())throw new IllegalStateException("Mechanical epoch differs");
            return new FootSupportFrameR52.Binding(point(t.getCompound("Left")),point(t.getCompound("Right")),decode(t.getCompound("PlugLocal")));
        }
        throw new IllegalStateException("Capture the complete actual mesh and hand pose before requesting its binding");
    }
    /** Unturned articulated source for the route owner's swept mesh query.
     * Apply the proposed world frame exactly once, never to an already turned pose. */
    public static EvaBodyPose.Sample frozenLocalPose(EvaUnit01Entity eva)
    {
        if(!active(eva))throw new IllegalStateException("Mechanical capture absent");
        var result=EvaBodyPose.neutralForTransportR32(eva);
        EvaShutdownR30.decode(EvaAirTransportR31.cradleStateR50(eva).getCompound("Origin"),result);
        return result;
    }
    public static EvaOriginalMeshGeometryR52.Geometry capturedGeometry(EvaUnit01Entity eva)
    {
        if(!active(eva))throw new IllegalStateException("Original complete geometry has not been captured");
        // Never acquire the source-install monitor from a loaded server EVA.
        // A missing/failed startup hook must reject, not perform tick IO or
        // substitute an empty mesh/broadphase. Remote clients retain their
        // existing strict first-use source installation.
        if(!geometryInstalled&&!eva.level().isClientSide)throw new IllegalStateException("Original packaged mesh provider not prepared before server entity load");
        var t=eva.getEntityData().get(SAMPLE);
        synchronized(GEOMETRY)
        {
            var cached=GEOMETRY.get(eva);long captured=t.getLong("CapturedAt");
            if(cached!=null&&cached.at()==captured)return cached.geometry();
            if(!geometryInstalled)
            {
                try{installGeometry();}
                catch(java.io.IOException failure){throw new IllegalStateException("Original packaged mesh provider is not available",failure);}
            }
            var geometry=EvaOriginalMeshGeometryR52.parts(eva,frozenLocalPose(eva));
            if(!geometry.sourceFingerprint().equals(EvaAirTransportR31.cradleStateR50(eva).getString("GeometrySourceR52")))
                throw new IllegalStateException("Captured mechanical mesh source changed");
            GEOMETRY.put(eva,new CapturedGeometry(captured,geometry));return geometry;
        }
    }
    public static FootSupportFrameR52.Binding sourceSoleBindingR52(EvaOriginalMeshGeometryR52.Geometry geometry,RigidTransform plugLocal){return new FootSupportFrameR52.Binding(sole(geometry,"foot_l"),sole(geometry,"foot_r"),plugLocal);}
    private static Vec3 sole(EvaOriginalMeshGeometryR52.Geometry geometry,String bone)
    {
        var vertices=new java.util.ArrayList<Vec3>();
        for(var part:geometry.parts())if(part.bone().equals(bone))vertices.addAll(part.vertices());
        if(vertices.isEmpty())throw new IllegalStateException("Actual sole mesh absent: "+bone);
        double low=vertices.stream().mapToDouble(p->p.y).min().orElseThrow();
        // Geometric extrema bound the real contact patch. Its midpoint does
        // not depend on repeated vertices from triangle tessellation.
        double minX=Double.POSITIVE_INFINITY,minZ=minX,maxX=Double.NEGATIVE_INFINITY,maxZ=maxX;
        for(var p:vertices)if(p.y<=low+.02){minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minZ=Math.min(minZ,p.z);maxZ=Math.max(maxZ,p.z);}
        return new Vec3((minX+maxX)*.5,low,(minZ+maxZ)*.5);
    }
    /** All original visible parts replace the upright broadphase while a
     * rigid carrier turns. The native route owner still checks separate full
     * body/carrier/capsule sweeps; this box is not a clearance bypass. */
    public static AABB bounds(EvaUnit01Entity eva)
    {
        var geometry=capturedGeometry(eva);
        var frame=frame(eva,1);AABB result=null;
        // Each bound encloses that complete actual part. Broadphase does not
        // turn concave cavities into a solid collision volume; the owner uses
        // the retained source triangles for its separate native swept check.
        for(var part:geometry.parts())
        {
            var b=part.bounds();
            for(double x:new double[]{b.minX,b.maxX})for(double y:new double[]{b.minY,b.maxY})for(double z:new double[]{b.minZ,b.maxZ})
            {var p=frame.transformPoint(new Vec3(x,y,z));var box=new AABB(p,p);result=result==null?box:result.minmax(box);}
        }
        return result;
    }
    private static CompoundTag point(Vec3 p){var t=new CompoundTag();t.putDouble("X",p.x);t.putDouble("Y",p.y);t.putDouble("Z",p.z);return t;}
    private static Vec3 point(CompoundTag t){return new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z"));}
    private static boolean same(RigidTransform a,RigidTransform b)
    {return a.translation().distanceToSqr(b.translation())<=4e-6&&a.rotationErrorDegrees(b)<=.04;}

    /** Capture after real carrier/plug interlocks admit the assembly. Body,
     * joints and relations stay unchanged; the old optical rider proxy is
     * synchronized to its existing physical capsule seat, with independent POV. */
    public static boolean capture(EvaUnit01Entity eva,Original original)
    {return capture(eva,original,Kind.OCCUPIED,null,null);}
    /** A separated capsule/pilot remains at its real location during this
     * hull-only capture. Its old UUIDs are provenance, never moving members. */
    public static boolean captureHull(EvaUnit01Entity eva,Original original)
    {
        if(active(eva))return originalHull(eva,original)&&kind(eva)==Kind.HULL_ONLY_RECOVERY&&epoch(eva)==original.epoch();
        // Caller must retain the pre-lock proof. An already locked factory
        // view cannot silently be replaced by a different fallen snapshot.
        return false;
    }
    public static boolean captureHull(EvaUnit01Entity eva,Original original,HullCapture observedBeforeLock)
    {return capture(eva,original,Kind.HULL_ONLY_RECOVERY,observedBeforeLock,null);}
    private static boolean capture(EvaUnit01Entity eva,Original original,Kind wantedKind,HullCapture hullCapture,OccupiedCapture occupiedCapture)
    {
        boolean hull=wantedKind==Kind.HULL_ONLY_RECOVERY;var plug=hull?null:originalPlug(eva,original);
        if(hull?!originalHull(eva,original):plug==null)return false;
        if(active(eva))return kind(eva)==wantedKind&&epoch(eva)==original.epoch();
        if(!geometryInstalled||occupiedCapture==null&&hullCapture==null&&!eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaAirTransportR31.active(eva)||eva.hasActiveCarrierMotion())return false;
        EvaBodyPose.Sample pose;CompoundTag hands;
        if(hull)
        {
            if(hullCapture==null||!hullCapture.original.equals(original)||eva.position().distanceToSqr(hullCapture.position)>1e-12
                    ||!EvaShutdownR30.pose(eva).equals(hullCapture.stopped)||eva.yBodyRot!=hullCapture.yaw||com.projectseele.physics.CombatBodyDynamics.active(eva))return false;
            pose=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(hullCapture.stopped,pose);hands=hullCapture.hands.copy();
        }
        else if(occupiedCapture!=null)
        {if(!occupiedCapture.original.equals(original)||eva.isNervLogisticsLocked()||eva.position().distanceToSqr(occupiedCapture.position)>1e-12||!same(plug.getCanonicalTransform(),occupiedCapture.plug)||eva.yBodyRot!=occupiedCapture.yaw)return false;pose=EvaBodyPose.neutralForTransportR32(eva);EvaShutdownR30.decode(occupiedCapture.body,pose);if(!samePose(pose,EvaBodyPose.sample(eva,1))||!EvaFrozenHandsR52.capture(eva,1).equals(occupiedCapture.hands))return false;hands=occupiedCapture.hands.copy();}
        else{pose=EvaBodyPose.sample(eva,1);hands=EvaFrozenHandsR52.capture(eva,1);}
        var geometry=occupiedCapture!=null?occupiedCapture.geometry:hull?EvaOriginalMeshGeometryR52.partsForFrozenRecovery(eva,pose,hands):EvaOriginalMeshGeometryR52.partsForCapture(eva,pose,hands);
        float capturedYaw=hull?hullCapture.yaw:occupiedCapture!=null?occupiedCapture.yaw:eva.mechanicalYawR52();
        var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-capturedYaw)*Mth.DEG_TO_RAD));
        var reference=hull?emptySocketReferenceR52(pose,EvaRifleKinematics.frameWorldR52(eva.position(),capturedYaw),EvaDorsalProfile.of(eva)):plug.getCanonicalTransform();
        var binding=occupiedCapture!=null&&com.projectseele.world.NervR50CarrierModeR53.enabled()?occupiedPreviewBinding(occupiedCapture):new FootSupportFrameR52.Binding(sole(geometry,"foot_l"),sole(geometry,"foot_r"),basis.inverse().compose(reference));
        if(!same(basis.compose(binding.plugInEva()),reference))return false;
        var t=new CompoundTag();retainCarrier(eva.getEntityData().get(SAMPLE),t);if(!hull)t.put("OriginStance",occupiedCapture==null?eva.captureMechanicalStanceR52():occupiedCapture.stance.copy());t.putBoolean("Active",true);t.putLong("Epoch",original.epoch());t.putFloat("BaseYaw",capturedYaw);
        t.putString("Kind",wantedKind.name());
        t.putLong("CapturedAt",eva.level().getGameTime());
        t.put("Previous",encode(basis));t.put("Current",encode(basis));t.putLong("AcceptedAt",eva.level().getGameTime());
        t.put("Left",point(binding.leftFoot()));t.put("Right",point(binding.rightFoot()));t.put("PlugLocal",encode(binding.plugInEva()));
        t.putUUID("Plug",original.plug());t.putUUID("Pilot",original.pilot());
        var origin=new CompoundTag();origin.putBoolean("Active",true);origin.putBoolean("MechanicalFrameR52",true);
        origin.putBoolean("FrozenRecoveryR52",hull);origin.putBoolean("FrozenOccupiedRecoveryR52",occupiedCapture!=null);
        origin.put(EvaFrozenHandsR52.KEY,hands);origin.putString("GeometrySourceR52",geometry.sourceFingerprint());
        origin.put("Origin",EvaShutdownR30.encode(pose));origin.putFloat("FromRestraint",1);origin.putFloat("ToRestraint",1);
        origin.putInt("Duration",1);origin.putLong("Since",eva.level().getGameTime());
        if(occupiedCapture!=null){eva.setNervLogisticsLocked(true);eva.adoptOccupiedMechanicalYawR52(capturedYaw);}else if(hull){eva.setNervLogisticsLocked(true);eva.adoptStoppedHullYawR52(capturedYaw);}
        com.projectseele.physics.CombatBodyDynamics.cancel(eva);
        synchronized(GEOMETRY){GEOMETRY.put(eva,new CapturedGeometry(eva.level().getGameTime(),geometry));}
        EvaAirTransportR31.cradleStateR50(eva,origin);eva.getEntityData().set(SAMPLE,t);eva.setBoundingBox(bounds(eva));
        if(plug!=null)plug.syncPilotPositionNow();return true;
    }

    /** The route owner must validate its full native sweep before this call. */
    public static boolean applyVerifiedContinuousR52(EvaUnit01Entity eva,Original original,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,List<com.projectseele.world.DirectoryTrajectoryR52> paths,CompoundTag clock)
    {
        if(eva.level().isClientSide||paths==null||paths.isEmpty()||paths.size()>64||clock.isEmpty()||paths.stream().anyMatch(p->!p.pureTranslation()))return false;
        var profile=continuousProfileR52(clock);long ticks=clock.getLong("Ticks");if(ticks<0||ticks==Long.MAX_VALUE||Math.abs(profile.distanceAt(ticks)-clock.getDouble("DistanceMetres"))>1e-6)return false;
        var encoded=com.projectseele.world.DirectoryTrajectoryR52.encodePortableR52(paths);var portable=com.projectseele.world.DirectoryTrajectoryR52.decodePortableR52(encoded);double travel=profile.distanceAt(ticks+1)-profile.distanceAt(ticks);
        if(travel<0||Math.abs(portable.lengthMetres()-travel)>1e-6||!same(portable.sample(0),from.evaRoot())||!same(portable.sample(portable.lengthMetres()),to.evaRoot())||from.evaRoot().rotationErrorDegrees(to.evaRoot())>.0001)return false;
        var window=new CompoundTag();long prior=eva.getEntityData().get(SAMPLE).getLong("ContinuousSequenceR52");if(prior==Long.MAX_VALUE)throw new IllegalStateException("Monotone mechanical sample sequence exhausted");window.putLong("Sequence",prior+1);window.put("Path",encoded);window.put("Clock",clock.copy());boolean accepted=applyVerifiedR52(eva,original,from,to,window);if(!accepted&&(eva.position().distanceToSqr(from.evaRoot().translation())>4e-6||!same(frame(eva,1),from.evaRoot())))throw new IllegalStateException("Continuous physical assembly commit failed after changing actual frame");return accepted;
    }
    public static boolean applyVerified(EvaUnit01Entity eva,Original original,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to)
    {return applyVerifiedR52(eva,original,from,to,null);}
    private static boolean applyVerifiedR52(EvaUnit01Entity eva,Original original,FootSupportFrameR52.Sample from,FootSupportFrameR52.Sample to,CompoundTag continuous)
    {
        if(!active(eva))return false;boolean hull=kind(eva)==Kind.HULL_ONLY_RECOVERY;var plug=hull?null:originalPlug(eva,original);
        if((hull?!originalHull(eva,original):plug==null)||epoch(eva)!=original.epoch()||!same(frame(eva,1),from.evaRoot())
                ||eva.position().distanceToSqr(from.evaRoot().translation())>4e-6||!hull&&!same(plug.getCanonicalTransform(),from.plugWorld()))return false;
        var binding=measuredBinding(eva,original);
        if(to.leftContact().distanceToSqr(to.evaRoot().transformPoint(binding.leftFoot()))>4e-6
                ||to.rightContact().distanceToSqr(to.evaRoot().transformPoint(binding.rightFoot()))>4e-6
                ||!same(to.plugWorld(),to.evaRoot().compose(binding.plugInEva())))return false;
        var old=eva.getEntityData().get(SAMPLE);var next=old.copy();next.put("Previous",encode(from.evaRoot()));next.put("Current",encode(to.evaRoot()));
        next.putLong("AcceptedAt",eva.level().getGameTime());if(continuous==null){next.remove("ContinuousWindowR52");next.remove("ContinuousHeldR52");}else{next.put("ContinuousWindowR52",continuous);next.putLong("ContinuousSequenceR52",continuous.getLong("Sequence"));next.remove("ContinuousHeldR52");}eva.getEntityData().set(SAMPLE,next);
        // The canonical socket must independently produce the proposed plug
        // pose from that same frozen body and the new complete rigid frame.
        var independent=hull?EntryPlugKinematics.posedSocketTransform(eva,1).compose(RigidTransform.of(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS),new Quaternionf())):EntryPlugKinematics.lockedTransform(eva);
        if(!same(independent,to.plugWorld()))
        {eva.getEntityData().set(SAMPLE,old);return false;}
        if(hull)eva.moveHullOnRigidNervCarrierR52(to.evaRoot().translation(),baseYaw(eva));
        else eva.moveOnRigidNervCarrierR52(to.evaRoot().translation(),baseYaw(eva),plug,to.plugWorld());
        return (hull||same(plug.getCanonicalTransform(),to.plugWorld()))&&eva.position().distanceToSqr(to.evaRoot().translation())<=4e-6;
    }

    /** Same local rigid root rotation is consumed by CPU sockets and Gecko.
     * The frozen articulated pose is never replaced with a new rest skeleton. */
    public static EvaBodyPose.Sample sample(EvaUnit01Entity eva,EvaBodyPose.Sample result,float partial,CompoundTag origin)
    {
        EvaShutdownR30.decode(origin,result);
        var recovery=eva.getEntityData().get(SAMPLE);if(eva.level().isClientSide&&!continuousWindowR52(eva)&&recovery.contains("RecoveryPreviousBodyR52")){var previous=new EvaBodyPose.Sample(result.rig);EvaShutdownR30.decode(recovery.getCompound("RecoveryPreviousBodyR52"),previous);float blend=(float)Mth.clamp(eva.level().getGameTime()-recovery.getLong("RecoveryAtR52")+(double)partial,0,1);result=com.projectseele.world.NervHullGroundRecoveryR52.mix(previous,result,blend);}
        var outer=new Quaternionf().rotationY((180-baseYaw(eva))*Mth.DEG_TO_RAD);
        var composed=FootSupportFrameR52.composeModelRoot(result.rig.get("root").pivot(),result.positions.get("root"),
                result.rotations.get("root"),outer,frame(eva,partial).rotation());
        result.positions.put("root",composed.offset());result.rotations.put("root",composed.rotation());
        result.dirty();return result;
    }
    public static CompoundTag originalStanceR52(EvaUnit01Entity eva){return eva.getEntityData().get(SAMPLE).getCompound("OriginStance").copy();}
    /** Cancellation before pickup returns control at the unchanged capture frame. */
    public static boolean releaseWaitingPickupR53(EvaUnit01Entity eva,Original original,RigidTransform waiting)
    {
        if(!flightCustody(eva)||!same(frame(eva,1),waiting)||eva.position().distanceToSqr(waiting.translation())>4e-6
                ||epoch(eva)!=original.epoch()||kind(eva)==Kind.OCCUPIED&&originalPlug(eva,original)==null)return false;
        if(kind(eva)==Kind.OCCUPIED)eva.restoreMechanicalStanceR52(originalStanceR52(eva));
        if(!releaseUpright(eva,original))return false;
        eva.setNervLogisticsLocked(false);eva.setNoGravity(false);return true;
    }
    public static boolean releaseUpright(EvaUnit01Entity eva,Original original)
    {
        if(com.projectseele.world.NervR50CarrierModeR53.enabled()&&ballisticCustodyR52(eva))eva.restoreMechanicalStanceR52(originalStanceR52(eva));
        if(!active(eva)||epoch(eva)!=original.epoch()||(kind(eva)==Kind.HULL_ONLY_RECOVERY?!originalHull(eva,original):originalPlug(eva,original)==null))return false;
        var basis=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-baseYaw(eva))*Mth.DEG_TO_RAD));
        if(!same(basis,frame(eva,1)))return false;
        boolean hull=kind(eva)==Kind.HULL_ONLY_RECOVERY;
        if(hull)
        {
            var stopped=frozenLocalPose(eva);var hands=EvaFrozenHandsR52.frozen(eva);
            // The existing stopped-pose codec also retains the final 34 hand
            // channels, so clearing the carrier never relaxes them privately.
            hands.rotations().forEach((name,q)->{stopped.rotations.put(name,new Quaternionf(q));stopped.positions.put(name,new Vector3f());});
            EvaShutdownR30.physicalRest(eva,stopped,bounds(eva));
        }
        var released=new CompoundTag();retainCarrier(eva.getEntityData().get(SAMPLE),released);if(hull){released.putString("Kind",Kind.HULL_ONLY_RECOVERY.name());released.putBoolean("ReleasedHull",true);}
        eva.getEntityData().set(SAMPLE,released);EvaAirTransportR31.clear(eva);
        if(hull){eva.setNervLogisticsLocked(false);eva.setNoGravity(false);}
        synchronized(GEOMETRY){GEOMETRY.remove(eva);}eva.setBoundingBox(eva.makeBoundingBox());
        var plug=originalPlug(eva,original);if(plug!=null)plug.syncPilotPositionNow();return true;
    }
    /** A checked aircraft may deliver a different real yaw than pickup.
     * Only the current upright sample is admitted; no turn, translation or
     * pose is invented at release. HULL delivery is deliberately rejected. */
    public static boolean releaseFlightUpright(EvaUnit01Entity eva,Original original,RigidTransform checked)
    {
        if(!flightCustody(eva)||kind(eva)!=Kind.OCCUPIED||epoch(eva)!=original.epoch()||originalPlug(eva,original)==null||!same(frame(eva,1),checked)||eva.position().distanceToSqr(checked.translation())>4e-6)return false;
        var up=checked.transformVector(new Vec3(0,1,0));var forward=checked.transformVector(new Vec3(0,0,1));if(up.distanceToSqr(new Vec3(0,1,0))>1e-10||Math.abs(forward.y)>1e-5)return false;
        float actualYaw=(float)(180-Math.toDegrees(Math.atan2(forward.x,forward.z)));actualYaw=Mth.wrapDegrees(actualYaw);var actual=RigidTransform.of(eva.position(),new Quaternionf().rotationY((180-actualYaw)*Mth.DEG_TO_RAD));if(!same(actual,checked))return false;
        var data=eva.getEntityData().get(SAMPLE).copy();data.putFloat("BaseYaw",actualYaw);eva.getEntityData().set(SAMPLE,data);eva.adoptVerifiedMechanicalReleaseYawR52(actualYaw);return releaseUpright(eva,original);
    }
    /** Same posed chest/profile math as EntryPlugKinematics, applied to the
     * verified pre-lock body rather than its unrelated upright plant branch. */
    public static RigidTransform emptySocketReferenceR52(EvaBodyPose.Sample body,Matrix4f world,EvaDorsalProfile.Profile profile)
    {return EvaMechanicalFrameMathR52.emptySocket(body,world,profile);}
    private static boolean samePose(EvaBodyPose.Sample a,EvaBodyPose.Sample b)
    {
        if(!a.rig.keySet().equals(b.rig.keySet()))return false;
        for(String name:a.rig.keySet()){var q=a.rotations.get(name);var r=b.rotations.get(name);float sign=q.dot(r)<0?-1:1;
            if(Math.abs(q.x-r.x*sign)>1e-6||Math.abs(q.y-r.y*sign)>1e-6||Math.abs(q.z-r.z*sign)>1e-6||Math.abs(q.w-r.w*sign)>1e-6
                    ||a.positions.get(name).distanceSquared(b.positions.get(name))>1e-12)return false;}return true;
    }
    private EvaMechanicalFrameR52(){}
}
