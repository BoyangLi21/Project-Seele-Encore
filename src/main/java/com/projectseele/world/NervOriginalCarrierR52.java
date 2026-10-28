package com.projectseele.world;
import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** The three original imported carriers have independent actual controllers.
 * This moves no EVA and manufactures no second deck. Every accepted motion
 * uses the original full carrier source and the declared Root rail curve. */
public final class NervOriginalCarrierR52 {
 public static final String SOURCE_SHA="0fa6f8fe5e0d4195ae52702ecb0bcc366057ca76490b490ecae39892f91e7561";
 public enum Role { STRUCTURE,SOLE_BEARING,GUIDE,RUNNING_BOGIE }
 public record Part(String name,Role role,NervRigidMeshSweepR52 mesh,RigidTransform frame){}
 private static final Map<Integer,Map<String,NervRigidMeshSweepR52>> BASE=new HashMap<>();
 public static UUID proposedIdentityR52(long epoch,UUID eva){return UUID.nameUUIDFromBytes(("projectseele:r52:original-carrier:"+epoch+":"+eva).getBytes(StandardCharsets.UTF_8));}
 private static CompoundTag encode(RigidTransform f){return NervAircraftFrameR52.encodeRigid(f);}
 private static RigidTransform decode(CompoundTag t){return NervAircraftFrameR52.decodeRigid(t);}
 public static boolean declared(NervCarrierPlatformEntity e){var t=e.originalCarrierReadStateR53();return t.getString("Source").equals(SOURCE_SHA)&&t.getString("GuideSource").equals(NervFootGuideRigR52.SOURCE_SHA)&&t.hasUUID("OriginalEva")&&t.getLong("Epoch")>0;}
 public static UUID entityUUID(EvaUnit01Entity e){return EvaMechanicalFrameR52.originalCarrierUUIDR52(e);}
 public static NervCarrierPlatformEntity controller(ServerLevel l,Original o){var actor=l.getEntity(proposedIdentityR52(o.epoch(),o.eva()));return actor instanceof NervCarrierPlatformEntity n&&declared(n)&&n.getUnitVariant()==o.variant()&&n.originalCarrierStateR52().getUUID("OriginalEva").equals(o.eva())?n:null;}
 /** Read the fixed bay hardware's stored clock, including on clients. The
  * original carrier may currently be at a different exit or unloaded. */
 public static NervLegacyCarrierRideR52.LeadSampleR52 actualLeadSampleR52(NervCarrierPlatformEntity gantry,float partial){if(!gantry.isRestraintGantry()||!gantry.hasDeclaredMachineFrameR52()||gantry.getPersistentData().getLong("MachineEpochR52")<=0&&!gantry.level().isClientSide)return null;var spec=gantry.declaredServiceFootDriveR52();float rise=gantry.serviceLeadRiseR52(partial),bridge=gantry.serviceGuideBridgeR52(partial);long at=gantry.serviceLeadAtR52();if(spec==null||spec.variant()!=gantry.getUnitVariant()||!Float.isFinite(rise+bridge)||at==Long.MIN_VALUE)return null;return new NervLegacyCarrierRideR52.LeadSampleR52(spec,bridge,rise,at);}
 /** Only the paired source proof may advance a fixed bay's lift sample. */
 public static final class DeclaredLeadState {
  private final UUID actor;private final CompoundTag before,after;private final NervLegacyCarrierRideR52.AcceptedLeadStep proof;
  private DeclaredLeadState(NervCarrierPlatformEntity e,NervLegacyCarrierRideR52.AcceptedLeadStep proof,CompoundTag after){actor=e.getUUID();before=e.serviceLeadStateR52();this.after=after.copy();this.proof=proof;}
  public CompoundTag next(){return after.copy();}
  public boolean current(NervCarrierPlatformEntity e){return e.level() instanceof ServerLevel l&&actor.equals(e.getUUID())&&e.serviceLeadStateR52().equals(before)&&proof.current(l);}
 }
 public static boolean acceptLeadStepR52(ServerLevel l,NervLegacyCarrierRideR52.AcceptedLeadStep proof){if(proof==null||!proof.current(l)||!(l.getEntity(proof.gantry()) instanceof NervCarrierPlatformEntity g)||!(l.getEntity(proof.carrier()) instanceof NervCarrierPlatformEntity c)||!declared(c)||!Objects.equals(g.declaredServiceFootDriveR52(),proof.toSample().spec())||!NervAirTransportManifestR52.same(actualRoot(c,1),proof.toSample().spec().bay())||progress(c,1)!=proof.toSample().rise()||g.getPersistentData().getLong("MachineEpochR52")!=c.originalCarrierStateR52().getLong("Epoch")||!g.getPersistentData().getString("MachineDirectoryR52").equals(c.originalCarrierStateR52().getString("Directory")))return false;var tag=g.serviceLeadStateR52();tag.putFloat("PreviousLeadRise",proof.fromSample().rise());tag.putFloat("LeadRise",proof.toSample().rise());tag.putLong("LeadAt",proof.checkedAt());g.acceptServiceLeadStateR52(new DeclaredLeadState(g,proof,tag));return true;}
 public static FootSupportFrameR52.Binding nominalBinding(int variant)throws IOException {return NervFootGuideRigR52.nominalBinding(variant);}
 public static float progress(NervCarrierPlatformEntity e,float partial){var t=e.originalCarrierReadStateR53();if(!declared(e))return Float.NaN;return e.carrierVisualRiseR54(t.getFloat("Rise"),partial);}
 public static RigidTransform actualRoot(NervCarrierPlatformEntity e,float partial){var t=e.originalCarrierReadStateR53();if(!declared(e))throw new IllegalStateException("Original carrier source/controller required");var current=decode(t.getCompound("Current"));if(!e.level().isClientSide)return current;var eva=continuousEvaR52(e);if(eva!=null)return CarrierMountProfileR53.read(e,partial).controllerFrame(EvaMechanicalFrameR52.frame(eva,partial));double clock=e.mechanicalVisualFractionR54("carrier",t.getLong("At"),partial);var dock=dockVisualR52(t,clock);if(dock!=null)return NervFootGuideDockR52.root(dock.view(),dock.turn());var timeline=t.getCompound("RideTimelineR52");return !timeline.isEmpty()&&timeline.getLong("At")==t.getLong("At")?NervLegacyCarrierRideR52.rootAtR52(timeline,clock):decode(t.getCompound("Previous")).interpolate(current,clock);}
 private static EvaUnit01Entity continuousEvaR52(NervCarrierPlatformEntity e){var t=e.originalCarrierReadStateR53();if(!e.level().isClientSide||!t.getBoolean("Attached")||!t.hasUUID("OriginalEva"))return null;for(var eva:e.level().getEntitiesOfClass(EvaUnit01Entity.class,e.getBoundingBox().inflate(128),v->v.getUUID().equals(t.getUUID("OriginalEva"))))if(EvaMechanicalFrameR52.continuousWindowR52(eva))return eva;return null;}
 private static NervBankHeadTransferR53.Pose bankHeadVisualR53(NervCarrierPlatformEntity e,float partial){var t=e.originalCarrierReadStateR53();var head=t.getCompound(NervBankHeadTransferR53.KEY);if(head.isEmpty())return null;int clock=head.getInt("Clock");if(head.getLong("At")!=t.getLong("At")){if(NervBankHeadTransferR53.unfinished(head))throw new IllegalStateException("Unfinished local head clock detached from original carrier state");return null;}double blend=e.level().isClientSide?e.mechanicalVisualFractionR54("carrier",head.getLong("At"),partial):1;int previous=head.contains("PreviousClock")?head.getInt("PreviousClock"):Math.max(0,clock-1);return NervBankHeadTransferR53.pose(head,previous+blend*(clock-previous));}
 public static double headSlideR53(NervCarrierPlatformEntity e,float partial){var pose=bankHeadVisualR53(e,partial);return pose==null?0:pose.slide();}
 public static Vec3 uprightDirectionR52(NervCarrierPlatformEntity e,float partial){var bank=bankHeadVisualR53(e,partial);if(bank!=null)return bank.direction();var eva=continuousEvaR52(e);if(eva!=null)return EvaMechanicalFrameR52.continuousWindowTangentR52(eva,partial);var t=e.originalCarrierReadStateR53();return t.contains("OuterDirectionR52")?decode(t.getCompound("OuterDirectionR52")).translation():actualRoot(e,1).transformVector(new Vec3(0,0,1));}
 public static Vec3 guideUp(NervCarrierPlatformEntity e){var t=e.originalCarrierReadStateR53();return t.contains("GuideUp")?decode(t.getCompound("GuideUp")).translation():new Vec3(0,1,0);}
 public static Vec3 guideUp(NervCarrierPlatformEntity e,float partial){var current=guideUp(e);var t=e.originalCarrierReadStateR53();if(!e.level().isClientSide||!t.contains("PreviousGuideUp"))return current;var before=decode(t.getCompound("PreviousGuideUp")).translation();float blend=(float)e.mechanicalVisualFractionR54("carrier",t.getLong("At"),partial);var dock=dockVisualR52(t,blend);if(dock!=null)return NervFootGuideDockR52.guideUpR52(dock.view(),dock.turn());var turn=new org.joml.Quaternionf().rotationTo(before.toVector3f(),current.toVector3f());return new Vec3(new org.joml.Quaternionf().slerp(turn,blend).transform(before.toVector3f())).normalize();}
 public static NervLegacyCarrierRideR52.RidePose actualRidePoseR52(NervCarrierPlatformEntity e){if(!declared(e))throw new IllegalStateException("Actual original carrier required");return NervLegacyCarrierRideR52.decode(e.originalCarrierReadStateR53().getCompound("RidePoseR52"));}
 public static NervLegacyCarrierRideR52.RidePose actualRidePoseR52(NervCarrierPlatformEntity e,float partial){var t=e.originalCarrierReadStateR53();var current=actualRidePoseR52(e);if(!e.level().isClientSide)return current;var eva=continuousEvaR52(e);double blend=eva!=null?EvaMechanicalFrameR52.continuousWindowFractionR52(eva,partial):e.mechanicalVisualFractionR54("carrier",t.getLong("At"),partial);var timeline=t.getCompound("RideTimelineR52");return !timeline.isEmpty()&&timeline.getLong("At")==t.getLong("At")?NervLegacyCarrierRideR52.poseAtR52(timeline,blend):NervLegacyCarrierRideR52.interpolate(NervLegacyCarrierRideR52.decode(t.getCompound("PreviousRidePoseR52")),current,blend);}
 /** A source-checked slide/hinge step updates the same hardware clock. The
  * caller separately retains its physical RAIL/SPACE lease. */
 public static boolean acceptRideStepR52(ServerLevel l,NervLegacyCarrierRideR52.AcceptedRideStep proof){if(proof==null||!proof.current(l)||proof.checkedAt()!=l.getGameTime()||!(l.getEntity(proof.actor()) instanceof NervCarrierPlatformEntity e)||!actualRidePoseR52(e).equals(proof.fromPose()))return false;var tag=moved(e,proof.toRoot(),progress(e,1),guideUp(e));tag.put("PreviousRidePoseR52",NervLegacyCarrierRideR52.encode(proof.fromPose()));tag.put("RidePoseR52",NervLegacyCarrierRideR52.encode(proof.toPose()));tag.put("RideTimelineR52",proof.timelineState());e.acceptOriginalCarrierStateR52(new DeclaredState(e,tag));var p=proof.toRoot().translation();e.moveControlled(p.x,p.y,p.z);try{e.setBoundingBox(boundsR52(e));}catch(IOException missing){throw new IllegalStateException("Accepted real running shoe source unavailable",missing);}return true;}
 public static boolean attachedTo(NervCarrierPlatformEntity n,EvaUnit01Entity e){var t=n.originalCarrierReadStateR53();return declared(n)&&t.getBoolean("Attached")&&t.getUUID("OriginalEva").equals(e.getUUID());}
 /** Only this actual carried hardware may be omitted as a duplicate of the
  * captured assembly surface. Other carriers remain physical obstacles. */
 public static boolean isCapturedMemberR52(EvaUnit01Entity eva,Entity actor){if(!(actor instanceof NervCarrierPlatformEntity n)||!EvaMechanicalFrameR52.active(eva)||!attachedTo(n,eva)||!n.getUUID().equals(entityUUID(eva))||progress(n,1)!=1||n.originalCarrierStateR52().getLong("Epoch")!=EvaMechanicalFrameR52.epoch(eva))return false;return NervAirTransportManifestR52.same(CarrierMountProfileR53.read(n,1).payloadFrame(actualRoot(n,1)),EvaMechanicalFrameR52.frame(eva,1));}
 public static boolean setAttachedR52(ServerLevel l,NervCarrierPlatformEntity n,EvaUnit01Entity eva,boolean attached)throws IOException {if(!declared(n)||!n.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID()))return false;if(attached){if(!EvaMechanicalFrameR52.active(eva)||!NervAirTransportManifestR52.same(CarrierMountProfileR53.read(n,1).payloadFrame(actualRoot(n,1)),EvaMechanicalFrameR52.frame(eva,1))||(!NervR50CarrierModeR53.enabled()||CarrierMountProfileR53.read(n,1).aboveFloor()||CarrierMountProfileR53.read(n,1).shallowBay())&&!carrierFootBearingR52(l,n,eva,EvaMechanicalFrameR52.capturedGeometry(eva),EvaMechanicalFrameR52.frame(eva,1)))return false;}else if(!attachedTo(n,eva))return true;var tag=n.originalCarrierStateR52();tag.putBoolean("Attached",attached);n.acceptOriginalCarrierStateR52(new DeclaredState(n,tag));return true;}
 private static synchronized Map<String,NervRigidMeshSweepR52> base(int variant)throws IOException {NervOuterCarrierGuideR52.install();var known=BASE.get(variant);if(known!=null)return known;byte[] receipt=EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json");try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(receipt)).equals(SOURCE_SHA))throw new IllegalStateException("Original full carrier selection changed");}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}var result=new LinkedHashMap<String,NervRigidMeshSweepR52>();FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();NervMappedPlugMechanicsR52.selectedMachinery().carrierParts(variant,1,false,0,64).forEach((name,xyz)->result.put(name,new NervRigidMeshSweepR52(xyz)));known=Collections.unmodifiableMap(result);BASE.put(variant,known);return known;}
 public static List<Part> partsAtR52(int variant,RigidTransform root,float rise,Vec3 up)throws IOException {return partsAtR52(variant,root,rise,up,NervLegacyCarrierRideR52.rest());}
 public static List<Part> partsAtR52(int variant,RigidTransform root,float rise,Vec3 up,NervLegacyCarrierRideR52.RidePose ride)throws IOException {return partsAtR52(variant,root,rise,up,ride,root.transformVector(new Vec3(0,0,1)));}
 public static List<Part> partsAtR52(int variant,RigidTransform root,float rise,Vec3 up,NervLegacyCarrierRideR52.RidePose ride,Vec3 direction)throws IOException {return partsAtR53(variant,root,rise,up,ride,direction,0);}
 public static List<Part> partsAtR53(int variant,RigidTransform root,float rise,Vec3 up,NervLegacyCarrierRideR52.RidePose ride,Vec3 direction,double headSlide)throws IOException {return partsAtR53(variant,root,rise,up,ride,direction,headSlide,0);}
 public static List<Part> partsAtR53(int variant,RigidTransform root,float rise,Vec3 up,NervLegacyCarrierRideR52.RidePose ride,Vec3 direction,double headSlide,double rearLift,CarrierMountProfileR53.State mounting)throws IOException {
  if(!mounting.aboveFloor()&&!mounting.shallowBay()&&!mounting.supportOnly()&&mounting.transverse()==0)return partsAtR53(variant,root,rise,up,ride,direction,headSlide,rearLift);
  var replacement=Objects.requireNonNull(CarrierAssemblyR53.selected(),"Explicit supplied carrier source required");var soles=mounting.aboveFloor()||mounting.shallowBay()||mounting.supportOnly()?Objects.requireNonNull(CarrierFootBearingR53.selected(),"Calibrated finite sole support required"):null;
  boolean outlet=NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0;var carrierRoot=root.compose(new RigidTransform(new Vec3(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0),0,0,0,1));var result=new ArrayList<Part>();
  for(var p:base(variant).entrySet())if(!mounting.supportOnly()||p.getKey().equals("deck")||p.getKey().startsWith("toe_"))result.add(new Part(p.getKey(),Role.STRUCTURE,p.getValue(),carrierRoot.compose(replacement.frame(p.getKey(),outlet?1:rise,outlet?NervR50CarrierModeR53.launchJawReleaseR53(rise):0,0,mounting))));
  var rear=Objects.requireNonNull(CarrierRearGuideR53.selected(),"Calibrated source rear hardware required");for(var p:mounting.supportOnly()?List.<NervLegacyCarrierRideR52.Piece>of():rear.partsAt(carrierRoot,outlet?1:rise,direction,headSlide,rearLift,mounting))result.add(new Part(p.name(),Role.GUIDE,p.mesh(),p.frame()));
  if(soles!=null)result.addAll(CarrierFootBearingR53.partsAt(soles,variant,carrierRoot,mounting));return List.copyOf(result);
 }
 public static List<Part> partsAtR53(int variant,RigidTransform root,float rise,Vec3 up,NervLegacyCarrierRideR52.RidePose ride,Vec3 direction,double headSlide,double rearLift)throws IOException {if(!Float.isFinite(rise)||rise<0||rise>1)throw new IllegalArgumentException("Actual bounded original actuator required");var replacement=CarrierAssemblyR53.selected();if(replacement!=null){
  boolean outlet=NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0;
  var carrierRoot=root.compose(new RigidTransform(new Vec3(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0),0,0,0,1));
  var selectedParts=new ArrayList<Part>();
  for(var part:base(variant).entrySet())selectedParts.add(new Part(part.getKey(),Role.STRUCTURE,part.getValue(),carrierRoot.compose(replacement.frame(part.getKey(),outlet?1:rise,outlet?NervR50CarrierModeR53.launchJawReleaseR53(rise):0,0))));
  var rear=CarrierRearGuideR53.selected();if(rear!=null)for(var part:rear.partsAt(carrierRoot,outlet?1:rise,direction,headSlide,rearLift))selectedParts.add(new Part(part.name(),Role.GUIDE,part.mesh(),part.frame()));
  return List.copyOf(selectedParts);
 }if(NervR50CarrierModeR53.enabled()){var lowered=root.compose(new RigidTransform(new Vec3(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0),0,0,0,1));var oldParts=new ArrayList<Part>();var raised=root.compose(new RigidTransform(new Vec3(0,-64D*(1-rise),0),0,0,0,1));boolean outlet=NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0;for(var p:base(variant).entrySet())oldParts.add(new Part(p.getKey(),Role.STRUCTURE,p.getValue(),outlet?lowered:p.getKey().equals("deck")?root:raised));return List.copyOf(oldParts);}var raised=root.compose(new RigidTransform(new Vec3(0,-64D*(1-rise),0),0,0,0,1));var out=new ArrayList<Part>();for(var p:base(variant).entrySet())out.add(new Part(p.getKey(),Role.STRUCTURE,p.getValue(),p.getKey().equals("deck")?root:raised));return List.copyOf(out);}

 public static void resetOriginalAtBayR53(NervCarrierPlatformEntity e,RigidTransform bay){var t=moved(e,bay,0,new Vec3(0,1,0));t.put("Previous",encode(bay));t.putFloat("PreviousRise",0);t.putBoolean("Attached",false);t.put("RidePoseR52",NervLegacyCarrierRideR52.encode(NervLegacyCarrierRideR52.rest()));t.put("PreviousRidePoseR52",t.getCompound("RidePoseR52").copy());for(String key:List.of("DockR52","PreviousDockR52",NervBankHeadTransferR53.KEY,"RideTimelineR52","ContinuousR52","ForcedVisualPreviewR53","OuterDirectionR52"))t.remove(key);e.acceptOriginalCarrierStateR52(new DeclaredState(e,t));}
 /** Old maintenance resets retained the previous vertical launch tangent at the bay. */
 public static void restoreBayDirectionR53(NervCarrierPlatformEntity e){
  var bay=CarrierBayTrayR53.bay(e);if(bay==null||!NervAirTransportManifestR52.same(actualRoot(e,1),bay.root()))return;
  var state=e.originalCarrierStateR52();
  if(!state.contains("OuterDirectionR52")||state.contains("DockR52")||state.contains(NervBankHeadTransferR53.KEY)
     ||uprightDirectionR52(e,1).distanceTo(new Vec3(0,1,0))>1e-6)return;
  state.remove("OuterDirectionR52");e.acceptOriginalCarrierStateR52(new DeclaredState(e,state));
 }
 public static void restoreR50RiseR53(NervCarrierPlatformEntity e,float rise){var t=moved(e,actualRoot(e,1),rise,guideUp(e));e.acceptOriginalCarrierStateR52(new DeclaredState(e,t));}
 public static boolean alignR50ReceiverR53(NervCarrierPlatformEntity e,RigidTransform target){if(!NervR50CarrierModeR53.enabled()||!declared(e))return false;var from=actualRoot(e,1);double distance=from.translation().distanceTo(target.translation()),angle=from.rotationErrorDegrees(target);double fraction=Math.min(1,Math.min(distance>.25?.25/distance:1,angle>3?3/angle:1));var next=from.interpolate(target,fraction);e.acceptOriginalCarrierStateR52(new DeclaredState(e,moved(e,next,progress(e,1),guideUp(e))));return NervAirTransportManifestR52.same(next,target);}
 public static List<Part> actualPartsR52(NervCarrierPlatformEntity e)throws IOException {return partsAtR53(e.getUnitVariant(),actualRoot(e,1),progress(e,1),guideUp(e),actualRidePoseR52(e),uprightDirectionR52(e,1),headSlideR53(e,1),CarrierRearGuideR53.actualLift(e,1),CarrierMountProfileR53.read(e,1));}
 public static List<NervFlightProofR52.ObstacleMesh> actualMeshesR52(NervCarrierPlatformEntity e)throws IOException {var out=new ArrayList<NervFlightProofR52.ObstacleMesh>();for(var p:actualPartsR52(e))out.add(new NervFlightProofR52.ObstacleMesh(p.mesh(),p.frame()));return List.copyOf(out);}
 public static AABB raisedBoundsAtR52(int variant,RigidTransform root)throws IOException {AABB b=null;for(var p:partsAtR52(variant,root,1,new Vec3(0,1,0))){var box=p.mesh().envelope(p.frame(),p.frame());b=b==null?box:b.minmax(box);}return b;}
 public static AABB boundsR52(NervCarrierPlatformEntity e)throws IOException {AABB b=null;for(var p:actualPartsR52(e)){var box=p.mesh().envelope(p.frame(),p.frame());b=b==null?box:b.minmax(box);}return b;}
 /** Physical outlet bearing is independent of the jaw clock while the deck remains at its upper stop. */
 public static boolean outletFootBearingR53(ServerLevel level,NervCarrierPlatformEntity carrier,EvaUnit01Entity eva) {
  if(carrier==null||!declared(carrier)||!EvaMechanicalFrameR52.active(eva)||carrier.level()!=level||eva.level()!=level
      ||carrier.getUnitVariant()!=eva.getUnitVariant()||!carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID()))return false;
  var root=actualRoot(carrier,1);var mount=CarrierMountProfileR53.read(carrier,1);
  if(!mount.shallowBay()||mount.supportOnly()||mount.aboveFloor()||mount.elevation()!=0||mount.transverse()!=0
      ||NervR50CarrierModeR53.launchDeckDropR53(root,0)!=-64||NervR50CarrierModeR53.launchDeckDropR53(root,progress(carrier,1))!=0)return false;
  var pads=CarrierFootBearingR53.selected();return pads!=null&&CarrierFootBearingR53.bears(pads,EvaMechanicalFrameR52.capturedGeometry(eva),
      EvaMechanicalFrameR52.frame(eva,1),root,mount,CarrierAssemblyR53.selected());
 }
 public static boolean carrierFootBearingR52(ServerLevel l,NervCarrierPlatformEntity carrier,EvaUnit01Entity eva,EvaOriginalMeshGeometryR52.Geometry body,RigidTransform root)throws IOException {if(!declared(carrier)||progress(carrier,1)!=1||carrier.getUnitVariant()!=eva.getUnitVariant())return false;var mounting=CarrierMountProfileR53.read(carrier,1);if(mounting.aboveFloor()||mounting.shallowBay()){var pads=CarrierFootBearingR53.selected();return pads!=null&&carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID())&&CarrierFootBearingR53.bears(pads,body,root,actualRoot(carrier,1),mounting,CarrierAssemblyR53.selected());}if(NervR50CarrierModeR53.enabled())return carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID())&&NervAirTransportManifestR52.same(actualRoot(carrier,1),root);var local=actualRoot(carrier,1).inverse().compose(root);var transformed=new LinkedHashMap<String,double[]>();for(var p:body.parts()){var xyz=p.triangles();for(int i=0;i<xyz.length;i+=3){var q=local.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));xyz[i]=q.x;xyz[i+1]=q.y;xyz[i+2]=q.z;}transformed.put(p.bone()+"/"+transformed.size(),xyz);}for(String bone:List.of("foot_l","foot_r")){var points=new ArrayList<Vec3>();for(var p:body.parts())if(p.bone().equals(bone)){double low=p.bounds().minY;for(var vertex:p.vertices())if(vertex.y<=low+.002)points.add(local.transformPoint(vertex));}boolean finite=false;for(var p:points){double h=Double.NEGATIVE_INFINITY;for(var shoe:base(eva.getUnitVariant()).entrySet())if(shoe.getKey().startsWith("sole_bearing_"))h=Math.max(h,NervMappedPlugMechanicsR52.surfaceHeight(shoe.getValue().triangles(),p.x,p.z));if(!Double.isFinite(h)||Math.abs(h-p.y)>.002)return false;}for(int a=0;a<points.size()&&!finite;a++)for(int b=a+1;b<points.size()&&!finite;b++)for(int c=b+1;c<points.size();c++){var x=points.get(a);var y=points.get(b);var z=points.get(c);if(Math.abs((y.x-x.x)*(z.z-x.z)-(z.x-x.x)*(y.z-x.z))>.0025){finite=true;break;}}if(!finite)return false;}return true;}
 public static final class DeclaredState {
  private final UUID actor;private final long at;private final CompoundTag previous,next;
  private DeclaredState(NervCarrierPlatformEntity e,CompoundTag next){actor=e.getUUID();at=e.level().getGameTime();previous=e.originalCarrierStateR52();this.next=next.copy();}
  public boolean current(NervCarrierPlatformEntity e){return !e.level().isClientSide&&e.getUUID().equals(actor)&&e.level().getGameTime()==at&&e.originalCarrierStateR52().equals(previous);}
  public CompoundTag next(){return next.copy();}
 }
 public static boolean declareNewR52(NervCarrierPlatformEntity e,Original o,RigidTransform originalRoot,float actualRise){if(e.level().isClientSide||e.getUnitVariant()!=o.variant()||!e.getUUID().equals(proposedIdentityR52(o.epoch(),o.eva()))||!e.originalCarrierReadStateR53().isEmpty()||!e.hasDeclaredMachineFrameR52()||actualRise<0||actualRise>1)return false;var tag=new CompoundTag();tag.putString("Source",SOURCE_SHA);tag.putString("GuideSource",NervFootGuideRigR52.SOURCE_SHA);tag.putUUID("OriginalEva",o.eva());tag.putLong("Epoch",o.epoch());tag.putString("Directory",e.getPersistentData().getString("MachineDirectoryR52"));tag.put("Current",encode(originalRoot));tag.put("Previous",encode(originalRoot));tag.putFloat("Rise",actualRise);tag.putFloat("PreviousRise",actualRise);tag.putLong("At",e.level().getGameTime());tag.put("RidePoseR52",NervLegacyCarrierRideR52.encode(NervLegacyCarrierRideR52.rest()));tag.put("PreviousRidePoseR52",tag.getCompound("RidePoseR52").copy());tag.putBoolean("Attached",actualRise==1);e.acceptOriginalCarrierStateR52(new DeclaredState(e,tag));return declared(e);}
 public static boolean declareNewR52(NervCarrierPlatformEntity e,int variant,long epoch,UUID originalEva,RigidTransform originalRoot,float actualRise){if(e.level().isClientSide||e.getUnitVariant()!=variant||!e.getUUID().equals(proposedIdentityR52(epoch,originalEva))||!e.originalCarrierReadStateR53().isEmpty()||!e.hasDeclaredMachineFrameR52()||!Float.isFinite(actualRise)||actualRise<0||actualRise>1)return false;var tag=new CompoundTag();tag.putString("Source",SOURCE_SHA);tag.putString("GuideSource",NervFootGuideRigR52.SOURCE_SHA);tag.putUUID("OriginalEva",originalEva);tag.putLong("Epoch",epoch);tag.putString("Directory",e.getPersistentData().getString("MachineDirectoryR52"));tag.put("Current",encode(originalRoot));tag.put("Previous",encode(originalRoot));tag.putFloat("Rise",actualRise);tag.putFloat("PreviousRise",actualRise);tag.putLong("At",e.level().getGameTime());tag.put("RidePoseR52",NervLegacyCarrierRideR52.encode(NervLegacyCarrierRideR52.rest()));tag.put("PreviousRidePoseR52",tag.getCompound("RidePoseR52").copy());tag.putBoolean("Attached",false);e.acceptOriginalCarrierStateR52(new DeclaredState(e,tag));return declared(e);}
 public static final class CheckedStep {
  private final UUID actor;private final long at;private final CompoundTag before,after,mountBefore;private final List<AABB> envelopes;private final LeadMotionR52 lead;
  private CheckedStep(ServerLevel l,NervCarrierPlatformEntity e,CompoundTag after,List<AABB> boxes,LeadMotionR52 lead){actor=e.getUUID();at=l.getGameTime();before=e.originalCarrierStateR52();mountBefore=e.carrierMountProfileR53();this.after=after.copy();envelopes=List.copyOf(boxes);this.lead=lead;}
  public UUID actor(){return actor;}public List<AABB> envelopes(){return envelopes;}
  public long checkedAt(){return at;}public RigidTransform fromRoot(){return decode(before.getCompound("Current"));}public RigidTransform toRoot(){return decode(after.getCompound("Current"));}public float fromRise(){return before.getFloat("Rise");}public float toRise(){return after.getFloat("Rise");}
  public boolean current(ServerLevel l){return l.getGameTime()==at&&l.getEntity(actor) instanceof NervCarrierPlatformEntity e&&declared(e)&&e.originalCarrierStateR52().equals(before)&&e.carrierMountProfileR53().equals(mountBefore)&&(lead==null||l.getEntity(lead.gantry()) instanceof NervCarrierPlatformEntity g&&g.serviceLeadStateR52().equals(lead.before()));}
  public boolean commit(ServerLevel l){if(lead!=null||!current(l))return false;return writeCarrierR52(l);}
  public boolean commit(ServerLevel l,NervLegacyCarrierRideR52.AcceptedLeadStep proof){if(lead==null)return proof==null&&commit(l);if(!current(l)||proof==null||!proof.current(l)||proof.checkedAt()!=at||!proof.carrier().equals(actor)||!proof.gantry().equals(lead.gantry())||!proof.fromSample().equals(lead.from())||!proof.toSample().equals(lead.to()))return false;if(!writeCarrierR52(l))return false;if(!acceptLeadStepR52(l,proof))throw new IllegalStateException("Prevalidated paired lead state changed during original carrier commit");return true;}
  private boolean writeCarrierR52(ServerLevel l){var e=(NervCarrierPlatformEntity)l.getEntity(actor);e.acceptOriginalCarrierStateR52(new DeclaredState(e,after));var root=actualRoot(e,1);e.moveControlled(root.translation().x,root.translation().y,root.translation().z);try{e.setBoundingBox(boundsR52(e));}catch(IOException unavailable){throw new IllegalStateException("Verified original carrier source vanished",unavailable);}return true;}
 }
 public static boolean acceptDockStepR52(ServerLevel l,NervFootGuideDockR52.AcceptedDockStep proof){if(proof==null||!proof.current(l)||!(l.getEntity(proof.actor()) instanceof NervCarrierPlatformEntity e)||!NervAirTransportManifestR52.same(actualRoot(e,1),proof.fromRoot())||guideUp(e).distanceTo(proof.fromUp())>1e-6||progress(e,1)!=1)return false;var after=moved(e,proof.toRoot(),1,proof.toUp());if(!NervFootGuideStationR52.acceptDockStepR52(l,proof))return false;var beforeDock=proof.stationState();beforeDock.putString("Stage",proof.from().stage().name());beforeDock.putDouble("Fraction",proof.from().fraction());beforeDock.put("Pose",NervFootGuideDockR52.encodePose(NervFootGuideDockR52.stationPose(proof.spec(),proof.from())));after.put("PreviousDockR52",beforeDock);after.put("DockR52",proof.stationState());e.acceptOriginalCarrierStateR52(new DeclaredState(e,after));var p=proof.toRoot().translation();e.moveControlled(p.x,p.y,p.z);try{e.setBoundingBox(boundsR52(e));}catch(IOException missing){throw new IllegalStateException("Accepted physical docking source unavailable",missing);}return true;}
 private static CompoundTag moved(NervCarrierPlatformEntity e,RigidTransform root,float rise,Vec3 up){var t=e.originalCarrierStateR52();t.remove("RideTimelineR52");var dock=t.getCompound("DockR52");if(dock.getString("Stage").equals("RELEASE")&&dock.getDouble("Fraction")==1&&!NervAirTransportManifestR52.same(actualRoot(e,1),root)){t.remove("DockR52");t.remove("PreviousDockR52");}t.put("Previous",t.getCompound("Current").copy());if(t.contains("RidePoseR52"))t.put("PreviousRidePoseR52",t.getCompound("RidePoseR52").copy());t.put("Current",encode(root));t.putFloat("PreviousRise",t.getFloat("Rise"));t.putFloat("Rise",rise);t.putLong("At",e.level().getGameTime());t.put("PreviousGuideUp",encode(new RigidTransform(guideUp(e),0,0,0,1)));t.put("GuideUp",encode(new RigidTransform(up,0,0,0,1)));return t;}
 private record LeadMotionR52(UUID gantry,CompoundTag before,NervLegacyCarrierRideR52.LeadSampleR52 from,NervLegacyCarrierRideR52.LeadSampleR52 to){}
 private static DirectoryTrajectoryR52 verticalActuatorGuideR53(ServerLevel l,NervCarrierPlatformEntity carrier,RigidTransform root,float from,float to)throws IOException {
  var context=NervRouteRuntimeR52.flightContext(l);if(context==null||!context.directory().fingerprint().equals(carrier.originalCarrierStateR52().getString("Directory")))return null;var directory=context.directory();var binding=nominalBinding(carrier.getUnitVariant());double lowDrop=64*(1-Math.min(from,to)),highDrop=64*(1-Math.max(from,to));DirectoryTrajectoryR52 found=null;
  for(var route:directory.routes().values()){if(route.recovery()||route.variant()!=carrier.getUnitVariant())continue;var leg=directory.leg(route.legs().get(route.legs().size()-1));if(leg.centreCurve()==null||!NervAirTransportManifestR52.same(directory.sample(leg,1,binding).evaRoot(),root))continue;var segments=leg.centreCurve().segments();var tail=segments.get(segments.size()-1);var points=tail.controls();var delta=points.get(points.size()-1).subtract(points.get(0));if(tail.type()!=NervCentrelineCurveR52.Type.LINE||delta.horizontalDistanceSqr()>1e-12||delta.y+1e-6<lowDrop||delta.y<=0)return null;double length=directory.legLength(leg);var curve=new DirectoryTrajectoryR52(directory,leg,binding,(length-lowDrop)/length,(length-highDrop)/length);if(!NervAirTransportManifestR52.same(curve.sample(0).evaRoot(),new RigidTransform(root.translation().add(0,-lowDrop,0),root.qx(),root.qy(),root.qz(),root.qw()))||!NervAirTransportManifestR52.same(curve.sample(1).evaRoot(),new RigidTransform(root.translation().add(0,-highDrop,0),root.qx(),root.qy(),root.qz(),root.qw()))||uprightDirectionR52(carrier,1).distanceTo(new Vec3(0,1,0))>1e-5)return null;if(found!=null)return null;found=curve;}
  return found;
 }
 public static CheckedStep proposeActuator(ServerLevel l,NervCarrierPlatformEntity e,float from,float to,Set<UUID> own,NervCarrierPlatformEntity gantry,NervLegacyCarrierRideR52.LeadSampleR52 leadFrom,NervLegacyCarrierRideR52.LeadSampleR52 leadTo)throws IOException {if(!declared(e)||progress(e,1)!=from||gantry==null||leadFrom==null||leadTo==null||!Objects.equals(actualLeadSampleR52(gantry,1),leadFrom)||!leadFrom.spec().equals(leadTo.spec())||leadFrom.serviceBridge()!=1||leadTo.serviceBridge()!=1||leadFrom.rise()!=from||leadTo.rise()!=to||leadTo.at()!=l.getGameTime()||gantry.getPersistentData().getLong("MachineEpochR52")!=e.originalCarrierStateR52().getLong("Epoch")||!gantry.getPersistentData().getString("MachineDirectoryR52").equals(e.originalCarrierStateR52().getString("Directory")))return null;var root=actualRoot(e,1);if(!NervAirTransportManifestR52.same(root,leadFrom.spec().bay()))return null;return check(l,e,null,root,root,from,to,guideUp(e),own,new LeadMotionR52(gantry.getUUID(),gantry.serviceLeadStateR52(),leadFrom,leadTo));}
 public static CheckedStep proposeActuator(ServerLevel l,NervCarrierPlatformEntity e,float from,float to,Set<UUID> own)throws IOException {if(!declared(e)||progress(e,1)!=from)return null;var root=actualRoot(e,1);if(from!=to)for(var g:l.getEntitiesOfClass(NervCarrierPlatformEntity.class,new AABB(root.translation(),root.translation()).inflate(4))){var drive=g.isRestraintGantry()?g.declaredServiceFootDriveR52():null;if(drive!=null&&drive.variant()==e.getUnitVariant()&&NervAirTransportManifestR52.same(drive.bay(),root))return null;}return check(l,e,null,root,root,from,to,guideUp(e),own);}
 public static CheckedStep proposeShallowBayActuatorR53(ServerLevel level,NervCarrierPlatformEntity carrier,float from,float to,Set<UUID> own)throws IOException
 {
  if(!declared(carrier)||progress(carrier,1)!=from||Math.abs(to-from)>.1F)return null;
  var mount=CarrierMountProfileR53.read(carrier,1);var bay=CarrierBayTrayR53.bay(carrier);
  if(bay==null||!NervAirTransportManifestR52.same(actualRoot(carrier,1),bay.root()))return null;
  var proof=CarrierBayMotionR53.check(level,carrier,from,to,mount,own);
  if(!proof.clear())return rejectedR53(carrier,proof.rejection());
  REJECTIONS_R53.remove(carrier.getUUID());return new CheckedStep(level,carrier,moved(carrier,actualRoot(carrier,1),to,guideUp(carrier)),proof.envelopes(),null);
 }
 public static CheckedStep proposeOutletReturnR53(ServerLevel level,NervCarrierPlatformEntity carrier,
     EvaUnit01Entity eva,String routeId,float from,float to,Set<UUID> own)throws IOException
 {
  if(!declared(carrier)||!Float.isFinite(from+to)||from<0||from>1||to<0||to>from||from-to>.1F
      ||progress(carrier,1)!=from||!own.contains(carrier.getUUID())||!own.contains(eva.getUUID())
      ||!EvaMechanicalFrameR52.ballisticCustodyR52(eva)||!EvaMechanicalFrameR52.detachedCarrierR52(eva)
      ||attachedTo(carrier,eva)||!carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID()))
   return rejectedR53(carrier,"outlet/original_detached_custody_or_clock_changed");
  return proposeOutletStrokeR53(level,carrier,routeId,from,to,own,null);
 }
 public static CheckedStep proposeOutletReturnR53(ServerLevel level,NervCarrierPlatformEntity carrier,EvaUnit01Entity eva,
     String routeId,float from,float to,Set<UUID> own,NervBallisticHandoffR52.StepR53 payload)throws IOException {
  if(payload==null||!payload.current(level,eva)||!payload.original().eva().equals(eva.getUUID())
      ||!declared(carrier)||progress(carrier,1)!=from||to<0||to>from||from-to>.1F||from>.5F
      ||!own.contains(carrier.getUUID())||!own.contains(eva.getUUID())||attachedTo(carrier,eva)
      ||!EvaMechanicalFrameR52.detachedCarrierR52(eva)||!carrier.originalCarrierStateR52().getUUID("OriginalEva").equals(eva.getUUID()))
   return rejectedR53(carrier,"outlet/current_paired_body_step_required");
  return proposeOutletStrokeR53(level,carrier,routeId,from,to,own,payload);
 }
 /** An empty receiver may rise only on its actual installed outlet or bay.
  * Its hardware/ground/flight caller must cover the returned full envelopes. */
 public static CheckedStep proposeReceiverActuatorR53(ServerLevel level,NervCarrierPlatformEntity carrier,
     float from,float to,Set<UUID> own)throws IOException
 {
  if(!declared(carrier)||!Float.isFinite(from+to)||from<0||to>1||to<from||to-from>.1F
      ||progress(carrier,1)!=from||!own.contains(carrier.getUUID())||carrier.originalCarrierStateR52().getBoolean("Attached"))
   return rejectedR53(carrier,"receiver/empty_original_carrier_or_clock_changed");
  if(NervR50CarrierModeR53.launchDeckDropR53(actualRoot(carrier,1),0)!=-64)
   return proposeShallowBayActuatorR53(level,carrier,from,to,own);
  var context=NervRouteRuntimeR52.flightContext(level);if(context==null)return rejectedR53(carrier,"receiver/original_directory_missing");
  var directory=context.directory();var binding=nominalBinding(carrier.getUnitVariant());String routeId=null;
  for(var route:directory.routes().values())if(!route.recovery()&&route.variant()==carrier.getUnitVariant()&&!route.legs().isEmpty())
  {
   var leg=directory.leg(route.legs().get(route.legs().size()-1));
   if(!NervAirTransportManifestR52.same(directory.sample(leg,1,binding).evaRoot(),actualRoot(carrier,1)))continue;
   if(routeId!=null)return rejectedR53(carrier,"receiver/ambiguous_original_outlet");routeId=route.id();
  }
  if(routeId==null)return rejectedR53(carrier,"receiver/original_outlet_not_declared");
  return proposeOutletStrokeR53(level,carrier,routeId,from,to,own,null);
 }
 private static CheckedStep proposeOutletStrokeR53(ServerLevel level,NervCarrierPlatformEntity carrier,
     String routeId,float from,float to,Set<UUID> own,NervBallisticHandoffR52.StepR53 payload)throws IOException
 {
  var context=NervRouteRuntimeR52.flightContext(level);var root=actualRoot(carrier,1);
  if(context==null||!context.directory().fingerprint().equals(carrier.originalCarrierStateR52().getString("Directory")))
   return rejectedR53(carrier,"outlet/original_directory_changed");
  var directory=context.directory();var route=directory.route(routeId);
  if(route==null||route.recovery()||route.variant()!=carrier.getUnitVariant()||route.legs().isEmpty())
   return rejectedR53(carrier,"outlet/original_outbound_route_missing");
  var leg=directory.leg(route.legs().get(route.legs().size()-1));var binding=nominalBinding(carrier.getUnitVariant());
  if(leg.centreCurve()==null||!NervAirTransportManifestR52.same(directory.sample(leg,1,binding).evaRoot(),root))
   return rejectedR53(carrier,"outlet/original_endpoint_changed");
  var segments=leg.centreCurve().segments();var tail=segments.get(segments.size()-1);var points=tail.controls();
  var delta=points.get(points.size()-1).subtract(points.get(0));
  double low=-NervR50CarrierModeR53.launchDeckDropR53(root,Math.min(from,to)),high=-NervR50CarrierModeR53.launchDeckDropR53(root,Math.max(from,to));
  if(tail.type()!=NervCentrelineCurveR52.Type.LINE||delta.horizontalDistanceSqr()>1e-12||delta.y<=0||delta.y+1e-6<low)
   return rejectedR53(carrier,"outlet/original_vertical_tail_too_short");
  double length=directory.legLength(leg);
  var guide=new DirectoryTrajectoryR52(directory,leg,binding,(length-low)/length,(length-high)/length);
  var proof=CarrierOutletMotionR53.check(level,carrier,guide,from,to,payload,own);
  if(!proof.clear())return rejectedR53(carrier,proof.rejection());
  REJECTIONS_R53.remove(carrier.getUUID());
  return new CheckedStep(level,carrier,moved(carrier,root,to,guideUp(carrier)),proof.envelopes(),null);
 }
 public static CheckedStep propose(ServerLevel l,NervCarrierPlatformEntity e,DirectoryTrajectoryR52 curve,float from,float to,Set<UUID> own)throws IOException {if(curve==null||from!=1||to!=1||progress(e,1)!=1||!declared(e)||!NervAirTransportManifestR52.same(actualRoot(e,1),curve.sample(0).evaRoot()))return null;var up=NervFixedFootGuidesR52.up(curve.directory(),curve.leg());if(up==null)up=guideUp(e);if(up.distanceTo(guideUp(e))>1e-6)return null;return check(l,e,curve,curve.sample(0).evaRoot(),curve.sample(1).evaRoot(),from,to,up,own);}
 private static final boolean COLLISION_TRACE_R53=Boolean.getBoolean("projectseele.r53CarrierCollisionTrace");
 private record ActivePairR53(String part,int triangles,int peerTriangles,RigidTransform from,RigidTransform to,RigidTransform peer){}
 private static volatile ActivePairR53 activePairR53;
 private static boolean hits(Part p,Part q,NervFlightProofR52.ObstacleMesh m,double error){
  long start=COLLISION_TRACE_R53?System.nanoTime():0;
  if(COLLISION_TRACE_R53)activePairR53=new ActivePairR53(p.name(),p.mesh().triangleCount(),m.mesh().triangleCount(),p.frame(),q.frame(),m.frame());
  try{return p.mesh().intersects(p.frame(),q.frame(),m.mesh(),m.frame(),m.endFrame(),.003,new Vec3(error,error,error));}
  finally{if(COLLISION_TRACE_R53){long elapsed=(System.nanoTime()-start)/1_000_000;if(elapsed>=1000)com.projectseele.ProjectSeele.LOGGER.info("Carrier collision query took {} ms: {}",elapsed,activePairR53);activePairR53=null;}}
 }
 private record ActualObstaclesR53(boolean known,boolean ordinary,NervStaticSpatialIndexR52<NervFlightProofR52.ObstacleMesh> index){}
 private record LeadPairR53(NervLegacyCarrierRideR52.Piece from,NervLegacyCarrierRideR52.Piece to){}
 private record StaticSurfaceR53(NervRigidMeshSweepR52 mesh,RigidTransform frame){}
 private static final class AffineStaticChecksR53 {
  private final List<Part> from,to;
  private final Map<Integer,Set<StaticSurfaceR53>> cleared=new HashMap<>();
  AffineStaticChecksR53(List<Part> from,List<Part> to){this.from=from;this.to=to;}
  boolean hits(Part p,Part q,int index,NervFlightProofR52.ObstacleMesh obstacle,double error){
   if(from.isEmpty()||!obstacle.frame().equals(obstacle.endFrame()))return NervOriginalCarrierR52.hits(p,q,obstacle,error);
   var a=from.get(index);var b=to.get(index);if(!a.name().equals(p.name())||!b.name().equals(q.name())||a.mesh()!=p.mesh()||b.mesh()!=q.mesh())throw new IllegalStateException("Affine actuator source topology changed");
   var known=cleared.computeIfAbsent(index,unused->new HashSet<>());var surface=new StaticSurfaceR53(obstacle.mesh(),obstacle.frame());if(known.contains(surface))return false;
   if(NervOriginalCarrierR52.hits(a,b,obstacle,error))return true;known.add(surface);return false;
  }
 }
 private static NervStaticSpatialIndexR52<NervFlightProofR52.ObstacleMesh> obstacleIndexR53(List<NervFlightProofR52.ObstacleMesh> meshes){return new NervStaticSpatialIndexR52<>(meshes,m->m.mesh().envelope(m.frame(),m.endFrame()));}
 private static final Map<UUID,String> REJECTIONS_R53=new LinkedHashMap<>();
 public static String lastRejectionR53(NervCarrierPlatformEntity carrier){return REJECTIONS_R53.getOrDefault(carrier.getUUID(),"");}
 private static CheckedStep rejectedR53(NervCarrierPlatformEntity carrier,String detail){if(REJECTIONS_R53.size()>=32)REJECTIONS_R53.remove(REJECTIONS_R53.keySet().iterator().next());REJECTIONS_R53.put(carrier.getUUID(),detail);return null;}
 static String nativeBlockRejectionR53(List<Part> from,List<Part> to,double error,
   java.util.function.Predicate<AABB> loaded,java.util.function.Function<AABB,List<AABB>> read) {
  if(from.size()!=to.size())throw new IllegalStateException("Carrier source topology changed");
  var boxes=new ArrayList<AABB>();var nativeBounds=new ArrayList<AABB>();
  for(int i=0;i<from.size();i++){
   var p=from.get(i);var q=to.get(i);
   if(!p.name().equals(q.name())||p.mesh()!=q.mesh())throw new IllegalStateException("Carrier source topology changed");
   var envelope=p.mesh().envelope(p.frame(),q.frame());var box=envelope.inflate(error);
   if(!loaded.test(box))return p.name()+" / unloaded "+box;
   boxes.add(box);
   // Match visit's root broadphase, including its conservative yaw Y pad.
   // The .003 argument below subdivides rotation; it is not contact padding.
   double yawPad=NervRigidMeshSweepR52.yawOnly(p.frame(),q.frame())
     ?NervRigidMeshSweepR52.error(NervRigidMeshSweepR52.radius(p.mesh().bounds()),NervRigidMeshSweepR52.angular(p.frame(),q.frame()),1):0;
   nativeBounds.add(envelope.inflate(0,yawPad,0));
  }
  String[] rejection={null};
  // Keep the existing callback's two List captures for live class replacement.
  List<List<?>> sourceAndBounds=List.of(from,nativeBounds);
  var result=BoundedNativeCollisionGroupsR52.clear(boxes,loaded,read,(i,obstacle)->{
   // An in-flight callback created before replacement still captures from.
   Object first=((List<?>)sourceAndBounds).get(0);boolean legacy=first instanceof Part;
   var p=(Part)(legacy?((List<?>)sourceAndBounds).get(i):((List<?>)first).get(i));var q=to.get(i);
   var padded=obstacle.inflate(error);
   // Disconnect must be able to finish a long native query without moving
   // the carrier or waiting for every remaining rendered triangle.
   var server=net.minecraftforge.server.ServerLifecycleHooks.getCurrentServer();
   if(server!=null&&!server.isRunning()) {rejection[0]="native sweep cancelled during server shutdown";return true;}
   if(!legacy&&!((AABB)sourceAndBounds.get(1).get(i)).intersects(padded))return false;
   if(!p.mesh().intersects(p.frame(),q.frame(),padded,.003))return false;
   rejection[0]=p.name()+" / native block "+obstacle;return true;
  });
  return result.clear()?null:rejection[0]==null?"native block region unloaded":rejection[0];
 }
 private static String nativeBlockRejectionR53(ServerLevel l,NervCarrierPlatformEntity e,List<Part> from,List<Part> to,double error) {
  return nativeBlockRejectionR53(from,to,error,box->EntryPlugEjectionR48.loaded(l,box),box->{
   return NativeCollisionShapesR53.read(l,e,box);
  });
 }
 private static CheckedStep check(ServerLevel l,NervCarrierPlatformEntity e,DirectoryTrajectoryR52 curve,RigidTransform rootFrom,RigidTransform rootTo,float riseFrom,float riseTo,Vec3 up,Set<UUID> own)throws IOException {return check(l,e,curve,rootFrom,rootTo,riseFrom,riseTo,up,own,null);}
 private static CheckedStep check(ServerLevel l,NervCarrierPlatformEntity e,DirectoryTrajectoryR52 curve,RigidTransform rootFrom,RigidTransform rootTo,float riseFrom,float riseTo,Vec3 up,Set<UUID> own,LeadMotionR52 lead)throws IOException {
  return checkSliceR52(l,e,curve,rootFrom,rootTo,riseFrom,riseTo,up,own,lead,actualRidePoseR52(e),false);
 }
 private static CheckedStep checkSliceR52(ServerLevel l,NervCarrierPlatformEntity e,DirectoryTrajectoryR52 curve,RigidTransform rootFrom,RigidTransform rootTo,float riseFrom,float riseTo,Vec3 up,Set<UUID> own,LeadMotionR52 lead,NervLegacyCarrierRideR52.RidePose rideFrom,boolean suffix)throws IOException {
  // Empty carriers use the same authored, force-enabled legacy travel as a
  // loaded carrier. The old alternate proof path could strand only empty racks.
  if(NervR50CarrierModeR53.enabled()){
   if(!own.contains(e.getUUID())||!declared(e)||progress(e,1)!=riseFrom||!NervAirTransportManifestR52.same(actualRoot(e,1),rootFrom))return rejectedR53(e,"legacy_carrier_source_changed");
   var after=moved(e,rootTo,riseTo,up);List<AABB> rearBoxes=List.of();
   if(CarrierMountProfileR53.read(e,1).shallowBay()&&curve!=null){var tray=CarrierBayMotionR53.translation(l,e,curve,own);if(!tray.clear())return rejectedR53(e,tray.rejection());rearBoxes=tray.envelopes();}
   if(CarrierRearGuideR53.selected()!=null&&curve!=null){var rear=CarrierRearGuideMotionR53.continuous(l,e,List.of(curve),own);if(!rear.clear())return rejectedR53(e,rear.rejection());var allBoxes=new ArrayList<AABB>(rearBoxes);allBoxes.addAll(rear.envelopes());rearBoxes=List.copyOf(allBoxes);}
   if(curve!=null)after.put("OuterDirectionR52",encode(RigidTransform.of(NervOuterCarrierGuideR52.direction(curve,1),new org.joml.Quaternionf())));
   REJECTIONS_R53.remove(e.getUUID());return new CheckedStep(l,e,after,rearBoxes,lead);
  }
  if(!own.contains(e.getUUID()))return rejectedR53(e,"carrier_not_owned");var rideTo=rideFrom;NervLegacyCarrierRideR52.AcceptedRideStep running=null;DirectoryTrajectoryR52 actuatorGuide=null;var currentContext=NervRouteRuntimeR52.flightContext(l);if(curve==null&&lead==null&&riseFrom!=riseTo&&currentContext!=null&&currentContext.directory().schemaVersionR52()>=2){actuatorGuide=verticalActuatorGuideR53(l,e,rootFrom,riseFrom,riseTo);if(actuatorGuide==null||!NervUprightGuidewayR52.enabledForDirectoryR52(l,actuatorGuide.directory())||!NervUprightGuidewayR52.matchesDirectory(actuatorGuide.directory()))return rejectedR53(e,"actuator_guide_unavailable");}
  boolean outerGuide=curve!=null&&curve.leg().centreCurve()!=null;if(outerGuide){if(!NervUprightGuidewayR52.enabledForDirectoryR52(l,curve.directory())||!NervUprightGuidewayR52.matchesDirectory(curve.directory()))return rejectedR53(e,"route_guide_unavailable");}else if(curve!=null){var startHead=NervLegacyCarrierRideR52.targetFromActualHeadsR52(rootFrom);var endHead=NervLegacyCarrierRideR52.targetFromActualHeadsR52(rootTo);if(startHead!=null&&endHead!=null){running=suffix?NervLegacyCarrierRideR52.proposeRouteSliceR52(l,e,curve,rideFrom,own):NervLegacyCarrierRideR52.proposeRouteR52(l,e,curve,own);if(running==null)return rejectedR53(e,"legacy_running_ride_rejected="+curve.leg().id());rideTo=running.toPose();}else if(!rideFrom.equals(NervLegacyCarrierRideR52.rest()))return rejectedR53(e,"unbound_legacy_ride_not_rest");}var boxes=new ArrayList<AABB>();if(running!=null)boxes.addAll(running.envelopes());int divisions=curve==null?1:Math.max(16,curve.divisions(80,.003));if(lead!=null)divisions=Math.max(divisions,NervLegacyCarrierRideR52.leadSweepDivisionsR52(lead.from(),lead.to()));double error=curve==null?0:curve.error(80,divisions);if(lead!=null)error+=NervLegacyCarrierRideR52.leadSweepErrorR52(lead.from(),lead.to(),divisions);var binding=nominalBinding(e.getUnitVariant());if(!NervLegacyCarrierRideR52.finiteHousingRoofContactR52())return rejectedR53(e,"housing_roof_contact");int baseCount=base(e.getUnitVariant()).size();
  var times=checkedRideTimesR52(divisions,running);REJECTIONS_R53.remove(e.getUUID());
  boolean carrierKnot=CarrierAssemblyR53.selected()!=null&&Math.min(riseFrom,riseTo)<CarrierAssemblyR53.RISE_END&&Math.max(riseFrom,riseTo)>CarrierAssemblyR53.RISE_END;
  if(carrierKnot){var ordered=new TreeSet<Double>(times);ordered.add((CarrierAssemblyR53.RISE_END-riseFrom)/(double)(riseTo-riseFrom));times=List.copyOf(ordered);}
  // Cache a complete affine translation only within one actuator segment.
  boolean affineActuator=!carrierKnot&&curve==null&&running==null&&rootFrom.equals(rootTo)&&rideFrom.equals(rideTo);
  var staticChecks=new AffineStaticChecksR53(affineActuator?partsAtR52(e.getUnitVariant(),rootFrom,riseFrom,up,rideFrom,uprightDirectionR52(e,1)):List.of(),affineActuator?partsAtR52(e.getUnitVariant(),rootTo,riseTo,up,rideTo,uprightDirectionR52(e,1)):List.of());
  // The lead's angular subdivisions do not change this affine carrier path.
  // Read the same live block shapes once for its complete translation; every
  // source triangle still gets the original continuous collision test.
  if(affineActuator&&NervTraversalPolicyR53.strict(l)){var rejected=nativeBlockRejectionR53(l,e,staticChecks.from,staticChecks.to,error);if(rejected!=null)return rejectedR53(e,rejected);}
  // No actuator runs during this proof. Capture each neighboring surface once,
  // retaining exact swept bounds and source order for the narrow collision test.
  var actorSnapshots=new IdentityHashMap<Entity,ActualObstaclesR53>();
  var structures=new IdentityHashMap<NervCarrierPlatformEntity,NervStaticSpatialIndexR52<NervFlightProofR52.ObstacleMesh>>();
  var serviceGuides=new IdentityHashMap<NervCarrierPlatformEntity,NervStaticSpatialIndexR52<NervServiceFootDriveR52.Piece>>();
  var stationParts=new IdentityHashMap<NervCarrierPlatformEntity,NervStaticSpatialIndexR52<NervFootGuideDockR52.Piece>>();
  var fixedParts=new NervStaticSpatialIndexR52<>(NervLegacyCarrierRideR52.fixedPartsR52(),p->p.mesh().envelope(p.frame(),p.frame()));
  for(int step=0;step<times.size()-1;step++){
   var leads=new IdentityHashMap<NervCarrierPlatformEntity,NervStaticSpatialIndexR52<LeadPairR53>>();
   double a=times.get(step),b=times.get(step+1);if(outerGuide&&(!NervUprightGuidewayR52.finiteCaptureAtR52(curve,a)||!NervUprightGuidewayR52.finiteCaptureAtR52(curve,b)))return rejectedR53(e,"route_guide_capture leg="+curve.leg().id()+" interval="+curve.fromFraction()+".."+curve.toFraction()+" local="+a+".."+b);if(actuatorGuide!=null)for(double t:new double[]{a,(a+b)/2,b})if(!NervUprightGuidewayR52.finiteCaptureAtR52(actuatorGuide,riseTo>riseFrom?t:1-t))return rejectedR53(e,"actuator_guide_capture="+t);var ra=curve==null?rootFrom:curve.sample(a).evaRoot();var rb=curve==null?rootTo:curve.sample(b).evaRoot();float pa=(float)(riseFrom+(riseTo-riseFrom)*a),pb=(float)(riseFrom+(riseTo-riseFrom)*b);var A=partsAtR52(e.getUnitVariant(),ra,pa,up,running!=null?running.poseAt(a):NervLegacyCarrierRideR52.interpolate(rideFrom,rideTo,a),curve==null?uprightDirectionR52(e,1):NervOuterCarrierGuideR52.direction(curve,a));var B=partsAtR52(e.getUnitVariant(),rb,pb,up,running!=null?running.poseAt(b):NervLegacyCarrierRideR52.interpolate(rideFrom,rideTo,b),curve==null?uprightDirectionR52(e,1):NervOuterCarrierGuideR52.direction(curve,b));var guidesA=List.<NervFootGuideRigR52.Draw>of();var guidesB=List.<NervFootGuideRigR52.Draw>of();
   for(int i=0;i<A.size();i++){
    var p=A.get(i);var q=B.get(i);var ga=i>=baseCount&&i<baseCount+guidesA.size()?guidesA.get(i-baseCount):null;var gb=i>=baseCount&&i<baseCount+guidesB.size()?guidesB.get(i-baseCount):null;var bounds=p.mesh().envelope(p.frame(),q.frame()).inflate(error);boxes.add(bounds);if(!EntryPlugEjectionR48.loaded(l,bounds))return rejectedR53(e,"carrier_unloaded="+bounds);
    if(!NervTraversalPolicyR53.strict(l))continue;
    if(!affineActuator)for(var shape:l.getBlockCollisions(e,bounds))for(var obstacle:shape.toAabbs())if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.003))return rejectedR53(e,p.name()+" / native block "+obstacle);
    for(var actor:l.getEntities((Entity)null,bounds.inflate(200),x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()||x instanceof NervCarrierPlatformEntity||x instanceof NervSiloDoorEntity||x instanceof NervHangarDoorEntity||x instanceof UNTransportEntity))){
     if(actor instanceof NervCarrierPlatformEntity station&&NervFootGuideStationR52.declared(station)){var view=NervFootGuideStationR52.view(station);var pose=NervFootGuideStationR52.currentPose(station);if(!stationParts.containsKey(station))stationParts.put(station,new NervStaticSpatialIndexR52<>(NervFootGuideStationR52.actualPartsR52(station,1),part->part.mesh().envelope(part.frame(),part.frame())));for(var part:stationParts.get(station).query(bounds)){if(NervFootGuideDockR52.namedStationContactR52(p,q,view,pose,pose,part))continue;if(hits(p,q,new NervFlightProofR52.ObstacleMesh(part.mesh(),part.frame()),error))return rejectedR53(e,p.name()+" / station "+part.name());}}
     else if(actor instanceof NervCarrierPlatformEntity gantry&&gantry.isRestraintGantry()&&gantry.hasDeclaredMachineFrameR52()){
      if(!structures.containsKey(gantry))structures.put(gantry,obstacleIndexR53(NervPlantMotionR52.actualStructuralMeshesR52(gantry)));for(var m:structures.get(gantry).query(bounds))if(staticChecks.hits(p,q,i,m,error))return rejectedR53(e,p.name()+" / gantry "+gantry.position());
      var spec=gantry.declaredServiceFootDriveR52();if(spec!=null){
       if(!serviceGuides.containsKey(gantry))serviceGuides.put(gantry,new NervStaticSpatialIndexR52<>(NervServiceFootDriveR52.pieces(spec,gantry.serviceGuideBridgeR52(1)),g->g.mesh().envelope(g.frame(),g.frame())));
       for(var guide:serviceGuides.get(gantry).query(bounds)){if(ga!=null&&NervFootGuideRigR52.namedGuideContactR52(ga,gb,guide))continue;if(hits(p,q,new NervFlightProofR52.ObstacleMesh(guide.mesh(),guide.frame()),error))return rejectedR53(e,p.name()+" / service guide "+guide.name());}
       if(!leads.containsKey(gantry)){var now=actualLeadSampleR52(gantry,1);if(now==null)return rejectedR53(e,"bay_lead_state_missing");var la=lead!=null&&lead.gantry().equals(gantry.getUUID())?NervLegacyCarrierRideR52.interpolateLeadR52(lead.from(),lead.to(),a):now;var lb=lead!=null&&lead.gantry().equals(gantry.getUUID())?NervLegacyCarrierRideR52.interpolateLeadR52(lead.from(),lead.to(),b):now;var LA=NervLegacyCarrierRideR52.actualLeadPartsR52(la);var LB=la.equals(lb)?LA:NervLegacyCarrierRideR52.actualLeadPartsR52(lb);if(LA.size()!=LB.size())return rejectedR53(e,"bay_lead_topology_size");var pairs=new ArrayList<LeadPairR53>();for(int j=0;j<LA.size();j++){var x=LA.get(j);var y=LB.get(j);if(!x.name().equals(y.name())||x.mesh()!=y.mesh())return rejectedR53(e,"bay_lead_topology_changed");pairs.add(new LeadPairR53(x,y));}leads.put(gantry,new NervStaticSpatialIndexR52<>(pairs,pair->pair.from().mesh().envelope(pair.from().frame(),pair.to().frame())));}
       for(var pair:leads.get(gantry).query(bounds)){var x=pair.from();var y=pair.to();if(NervLegacyCarrierRideR52.namedLeadPadContactR52(p,q,x,y))continue;if(hits(p,q,new NervFlightProofR52.ObstacleMesh(x.mesh(),x.frame(),y.frame()),error))return rejectedR53(e,p.name()+" / bay lead "+x.name());}
      }
     }else{if(!actorSnapshots.containsKey(actor)){var actual=NervFlightProofR52.actualObstacleMeshes(actor);actorSnapshots.put(actor,new ActualObstaclesR53(actual!=null,actual!=null&&actual.isEmpty(),actual==null?null:obstacleIndexR53(actual)));}var actual=actorSnapshots.get(actor);if(!actual.known())return rejectedR53(e,"unknown collision actor "+actor);if(actual.ordinary()){if(p.mesh().intersects(p.frame(),q.frame(),actor.getBoundingBox().inflate(error),.003))return rejectedR53(e,p.name()+" / actor "+actor);}else for(var m:actual.index().query(bounds))if(staticChecks.hits(p,q,i,m,error))return rejectedR53(e,p.name()+" / actor "+actor);}
    }
    for(var fixed:fixedParts.query(bounds)){if(NervLegacyCarrierRideR52.namedHeadContactR52(p,q,fixed)||NervLegacyCarrierRideR52.namedDeckHeadContactR52(p,q,fixed)||NervLegacyCarrierRideR52.namedSoleHeadContactR52(p,q,fixed))continue;if(hits(p,q,new NervFlightProofR52.ObstacleMesh(fixed.mesh(),fixed.frame()),error))return rejectedR53(e,p.name()+" / fixed rail "+fixed.name());}
    for(var fixed:NervUprightGuidewayR52.actualPieces(l,bounds)){var contactCurve=outerGuide?curve:actuatorGuide;if(contactCurve!=null&&fixed.leg().equals(NervUprightGuidewayR52.canonicalPathR52(contactCurve.leg().id()))&&NervUprightGuidewayR52.namedCaptureContactR52(p,q,fixed))continue;var piece=fixed.steel();if(hits(p,q,new NervFlightProofR52.ObstacleMesh(piece.mesh(),piece.frame()),error))return rejectedR53(e,p.name()+" / upright guide "+fixed.leg()+" "+piece.name());}
    for(var fixed:NervFixedFootGuidesR52.actualPieces(l,bounds)){if(ga!=null&&NervFootGuideRigR52.namedGuideContactR52(ga,gb,fixed))continue;if(hits(p,q,new NervFlightProofR52.ObstacleMesh(fixed.mesh(),fixed.frame()),error))return rejectedR53(e,p.name()+" / foot guide "+fixed.name());}
   }
  }
  if(running!=null&&!(suffix?running.snapshotCurrentR52(l):running.current(l)))return rejectedR53(e,"legacy_ride_state_changed");var after=moved(e,rootTo,riseTo,up);if(curve!=null)after.put("OuterDirectionR52",encode(RigidTransform.of(NervOuterCarrierGuideR52.direction(curve,1),new org.joml.Quaternionf())));after.put("PreviousRidePoseR52",NervLegacyCarrierRideR52.encode(rideFrom));after.put("RidePoseR52",NervLegacyCarrierRideR52.encode(rideTo));if(running!=null)after.put("RideTimelineR52",running.timelineState());return new CheckedStep(l,e,after,boxes,lead);
 }
 /** One same-tick proof for an entire translated route step. Each suffix is
  * checked against the same immutable live state; only commit writes once. */
 public static final class CheckedContinuousStepR52 {
  private final CheckedStep whole;
  private final List<DirectoryTrajectoryR52> slices;private final boolean committable;
  private CheckedContinuousStepR52(CheckedStep whole,List<DirectoryTrajectoryR52> slices,boolean committable){this.whole=whole;this.slices=List.copyOf(slices);this.committable=committable;}
  public UUID actor(){return whole.actor();}public long checkedAt(){return whole.checkedAt();}
  public RigidTransform fromRoot(){return whole.fromRoot();}public RigidTransform toRoot(){return whole.toRoot();}
  public List<AABB> envelopes(){return whole.envelopes();}public List<DirectoryTrajectoryR52> slices(){return slices;}
  public boolean current(ServerLevel l){return whole.current(l);}public boolean commit(ServerLevel l){return committable&&whole.commit(l);}public boolean committable(){return committable;}
 }
 private static CheckedContinuousStepR52 continuousRejectedR53(NervCarrierPlatformEntity e,String reason){rejectedR53(e,reason);return null;}
 public static CheckedContinuousStepR52 proposeContinuousR52(ServerLevel l,NervCarrierPlatformEntity e,List<DirectoryTrajectoryR52> source,Vec3 fixedGuideUp,Set<UUID> own)throws IOException {
  return proposeContinuousR52(l,e,source,fixedGuideUp,own,null);
 }
 public static CheckedContinuousStepR52 proposeContinuousR52(ServerLevel l,NervCarrierPlatformEntity e,List<DirectoryTrajectoryR52> source,Vec3 fixedGuideUp,Set<UUID> own,NervRouteNativeR52.CheckedContinuousTraversalR52 coverage)throws IOException {
  // The caller's CheckedContinuousTraversal already covers the complete R50
  // body/deck/capsule against native obstacles. R52 added-shoe certificates
  // do not apply to the restored original carrier.
  if(NervR50CarrierModeR53.enabled()){
   // Full-route lookahead uses the same bounded 2048 slices as the native
   // assembly proof. The 64-slice limit belongs to a writable motion step.
   if(source==null||source.isEmpty()||source.size()>2048)return continuousRejectedR53(e,"continuous_source_slices="+(source==null?"null":source.size()));
   if(!declared(e)||progress(e,1)!=1||!own.contains(e.getUUID()))return continuousRejectedR53(e,"continuous_actual_carrier_state");
   if(!NervAirTransportManifestR52.same(actualRoot(e,1),source.get(0).sample(0).evaRoot()))return continuousRejectedR53(e,"continuous_initial_root actual="+actualRoot(e,1)+" required="+source.get(0).sample(0).evaRoot());
   List<AABB> rearBoxes=List.of();
   if(CarrierRearGuideR53.selected()!=null){restoreBayDirectionR53(e);if(headSlideR53(e,1)!=0||uprightDirectionR52(e,1).distanceTo(NervOuterCarrierGuideR52.direction(source.get(0),0))>1e-5)return continuousRejectedR53(e,"rear_initial_direction_or_lock_changed");var rear=CarrierRearGuideMotionR53.continuous(l,e,source,own,coverage);if(!rear.clear())return continuousRejectedR53(e,rear.rejection());var allBoxes=new ArrayList<AABB>(rearBoxes);allBoxes.addAll(rear.envelopes());rearBoxes=List.copyOf(allBoxes);}
   var last=source.get(source.size()-1);var after=moved(e,last.sample(1).evaRoot(),1,fixedGuideUp);after.put("OuterDirectionR52",encode(RigidTransform.of(NervOuterCarrierGuideR52.direction(last,1),new org.joml.Quaternionf())));REJECTIONS_R53.remove(e.getUUID());return new CheckedContinuousStepR52(new CheckedStep(l,e,after,rearBoxes,null),source,source.size()<=64);
  }

  if(headSlideR53(e,1)!=0||source==null||source.isEmpty()||source.size()>2048||fixedGuideUp==null||fixedGuideUp.distanceTo(new Vec3(0,1,0))>1e-8||!declared(e)||progress(e,1)!=1||!own.contains(e.getUUID())||guideUp(e).distanceTo(fixedGuideUp)>1e-8)return continuousRejectedR53(e,"continuous_state");
  var slices=List.copyOf(source);if(uprightDirectionR52(e,1).distanceTo(NervOuterCarrierGuideR52.direction(slices.get(0),0))>1e-5)return continuousRejectedR53(e,"continuous_initial_direction actual="+uprightDirectionR52(e,1)+" required="+NervOuterCarrierGuideR52.direction(slices.get(0),0));var before=e.originalCarrierStateR52();long tick=l.getGameTime();var initial=actualRoot(e,1);var next=initial;var nextDirection=uprightDirectionR52(e,1);var ride=actualRidePoseR52(e);var boxes=new ArrayList<AABB>();var timelines=new ArrayList<CompoundTag>();var lengths=new ArrayList<Double>();double total=0;
  for(var curve:slices){if(curve==null||nextDirection.distanceTo(NervOuterCarrierGuideR52.direction(curve,0))>1e-5||curve.leg().motion()==NervRouteDirectoryR52.Motion.FOOT_BEARING_TURN||curve.angularTravel()!=0||!NervAirTransportManifestR52.same(next,curve.sample(0).evaRoot())||curve.sample(0).evaRoot().rotationErrorDegrees(initial)>1e-6||curve.sample(1).evaRoot().rotationErrorDegrees(initial)>1e-6)return continuousRejectedR53(e,"continuous_slice_frame leg="+(curve==null?"null":curve.leg().id())+" from="+(curve==null?"null":curve.sample(0).evaRoot())+" prior="+next+" direction="+nextDirection);
   var checked=checkSliceR52(l,e,curve,next,curve.sample(1).evaRoot(),1,1,fixedGuideUp,own,null,ride,true);if(checked==null)return null;if(!checked.current(l))return continuousRejectedR53(e,"continuous_slice_stale="+curve.leg().id());boxes.addAll(checked.envelopes());next=checked.toRoot();nextDirection=NervOuterCarrierGuideR52.direction(curve,1);ride=NervLegacyCarrierRideR52.decode(checked.after.getCompound("RidePoseR52"));var timeline=checked.after.getCompound("RideTimelineR52");if(timeline.isEmpty()){timeline.putString("Source",NervLegacyCarrierRideR52.SOURCE_SHA);timeline.putString("Deck",NervLegacyCarrierRideR52.DECK_SHA);timeline.putLong("At",tick);var keys=new net.minecraft.nbt.ListTag();for(int k=0;k<2;k++){var key=new CompoundTag();key.putDouble("T",k);key.put("Root",encode(curve.sample(k).evaRoot()));key.put("Pose",NervLegacyCarrierRideR52.encode(ride));keys.add(key);}timeline.put("Samples",keys);}timelines.add(timeline);double length=curve.directory().legDistance(curve.leg(),curve.toFraction())-curve.directory().legDistance(curve.leg(),curve.fromFraction());if(!(length>0)||!Double.isFinite(length))return continuousRejectedR53(e,"continuous_slice_length="+length);lengths.add(length);total+=length;
  }
  if(l.getGameTime()!=tick||!e.originalCarrierStateR52().equals(before))return continuousRejectedR53(e,"continuous_live_state_changed");
  var after=moved(e,next,1,fixedGuideUp);after.remove("DockR52");after.remove("PreviousDockR52");after.put("OuterDirectionR52",encode(RigidTransform.of(NervOuterCarrierGuideR52.direction(slices.get(slices.size()-1),1),new org.joml.Quaternionf())));after.put("PreviousRidePoseR52",before.getCompound("RidePoseR52").copy());after.put("RidePoseR52",NervLegacyCarrierRideR52.encode(ride));var joined=new CompoundTag();joined.putString("Source",NervLegacyCarrierRideR52.SOURCE_SHA);joined.putString("Deck",NervLegacyCarrierRideR52.DECK_SHA);joined.putLong("At",tick);var samples=new net.minecraft.nbt.ListTag();double offset=0;
  for(int i=0;i<timelines.size();i++){var local=timelines.get(i).getList("Samples",net.minecraft.nbt.Tag.TAG_COMPOUND);for(int j=i==0?0:1;j<local.size();j++){var sample=((CompoundTag)local.get(j)).copy();sample.putDouble("T",(offset+sample.getDouble("T")*lengths.get(i))/total);samples.add(sample);}offset+=lengths.get(i);}
  boolean writable=slices.size()<=64&&samples.size()<=257;if(writable){((CompoundTag)samples.get(samples.size()-1)).putDouble("T",1);joined.put("Samples",samples);after.put("RideTimelineR52",joined);after.putBoolean("ContinuousR52",true);}return new CheckedContinuousStepR52(new CheckedStep(l,e,after,boxes,null),slices,writable);
 }
 /** Checked local head preparation while all four original pads still bear on level steel. */
 public static CheckedStep proposeBankHeadStepR53(ServerLevel l,NervCarrierPlatformEntity e,CompoundTag state,Set<UUID> own)throws IOException {return proposeBankHeadStepR53(l,e,state,own,1);}
 public static CheckedStep proposeBankHeadStepR53(ServerLevel l,NervCarrierPlatformEntity e,CompoundTag state,Set<UUID> own,int step)throws IOException {
  if(!declared(e)||progress(e,1)!=1||!own.contains(e.getUUID())||!state.getString("Directory").equals(e.originalCarrierStateR52().getString("Directory"))||!state.hasUUID("Task")||NervTraversalPolicyR53.strict(l)&&!NervBankHeadTransferR53.internalBearings())return null;
  int clock=state.getInt("Clock");if((step!=1&&step!=-1)||clock+step<0||clock+step>NervBankHeadTransferR53.TICKS)return null;var prior=e.originalCarrierStateR52().getCompound(NervBankHeadTransferR53.KEY);if(NervBankHeadTransferR53.unfinished(prior)&&!prior.equals(state))return null;
  var a=NervBankHeadTransferR53.pose(state,clock);var b=NervBankHeadTransferR53.pose(state,clock+step);if(uprightDirectionR52(e,1).distanceTo(a.direction())>1e-7||Math.abs(headSlideR53(e,1)-a.slide())>1e-8)return null;
  var root=actualRoot(e,1);
  if(NervR50CarrierModeR53.enabled()&&CarrierRearGuideR53.selected()!=null){var rear=CarrierRearGuideMotionR53.bank(l,e,state,step,own);if(!rear.clear())return rejectedR53(e,rear.rejection());var after=moved(e,root,1,guideUp(e));after.put(NervBankHeadTransferR53.KEY,NervBankHeadTransferR53.advance(state,step,l.getGameTime()));after.put("OuterDirectionR52",encode(RigidTransform.of(b.direction(),new org.joml.Quaternionf())));REJECTIONS_R53.remove(e.getUUID());return new CheckedStep(l,e,after,rear.envelopes(),null);}
  var ride=actualRidePoseR52(e);var pads=NervLegacyCarrierRideR52.finitePadBearingsR52(root,ride);if(pads.size()!=4||pads.stream().anyMatch(p->!p.bears()))return null;
  var A=NervOuterCarrierGuideR52.partsAt(root,1,a.direction(),a.slide());var B=NervOuterCarrierGuideR52.partsAt(root,1,b.direction(),b.slide());var stationary=partsAtR52(e.getUnitVariant(),root,1,guideUp(e),ride).stream().filter(p->!p.name().startsWith("outer/")).toList();var boxes=new ArrayList<AABB>();
  double angle=Math.acos(Math.max(-1,Math.min(1,a.direction().dot(b.direction()))));double error=angle==0?0:(.35+Math.abs(a.slide()))*angle*angle/8+2e-6;
  AABB area=null;for(int i=0;i<A.size();i++){var box=A.get(i).mesh().envelope(A.get(i).frame(),B.get(i).frame()).inflate(error);area=area==null?box:area.minmax(box);}var actorMeshes=new ArrayList<NervFlightProofR52.ObstacleMesh>();var ordinaryActors=new ArrayList<AABB>();
  if(NervTraversalPolicyR53.strict(l))for(var actor:l.getEntities((Entity)null,area.inflate(200),x->!x.getUUID().equals(e.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()||x instanceof NervCarrierPlatformEntity||x instanceof NervSiloDoorEntity||x instanceof NervHangarDoorEntity||x instanceof EntryPlugCarrierEntity||x instanceof UNTransportEntity))){var meshes=NervFlightProofR52.actualObstacleMeshes(actor);if(meshes==null)return null;if(meshes.isEmpty()){if(!own.contains(actor.getUUID()))ordinaryActors.add(actor.getBoundingBox());}else actorMeshes.addAll(meshes);}
  for(int i=0;i<A.size();i++){
   var pa=A.get(i);var pb=B.get(i);if(!pa.name().equals(pb.name())||pa.mesh()!=pb.mesh())return null;if(pa.frame().equals(pb.frame()))continue;
   var p=new Part(pa.name(),Role.RUNNING_BOGIE,pa.mesh(),pa.frame());var q=new Part(pb.name(),Role.RUNNING_BOGIE,pb.mesh(),pb.frame());var bounds=p.mesh().envelope(p.frame(),q.frame()).inflate(error);boxes.add(bounds);if(!EntryPlugEjectionR48.loaded(l,bounds))return null;
   if(!NervTraversalPolicyR53.strict(l))continue;
   for(var shape:l.getBlockCollisions(e,bounds))for(var obstacle:shape.toAabbs())if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.003))return null;
   for(var member:stationary)if(hits(p,q,new NervFlightProofR52.ObstacleMesh(member.mesh(),member.frame()),error))return null;
   for(var obstacle:ordinaryActors)if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.003))return null;
   for(var mesh:actorMeshes)if(hits(p,q,mesh,error))return null;
   for(var fixed:NervLegacyCarrierRideR52.fixedPartsR52())if(hits(p,q,new NervFlightProofR52.ObstacleMesh(fixed.mesh(),fixed.frame()),error))return null;
   for(var fixed:NervUprightGuidewayR52.actualPieces(l,bounds)){if(NervUprightGuidewayR52.namedCaptureContactR52(p,q,fixed))continue;var part=fixed.steel();if(hits(p,q,new NervFlightProofR52.ObstacleMesh(part.mesh(),part.frame()),error))return null;}
   for(var fixed:NervFixedFootGuidesR52.actualPieces(l,bounds))if(hits(p,q,new NervFlightProofR52.ObstacleMesh(fixed.mesh(),fixed.frame()),error))return null;
  }
  if(boxes.isEmpty())return null;var after=moved(e,root,1,guideUp(e));var next=NervBankHeadTransferR53.advance(state,step,l.getGameTime());after.put(NervBankHeadTransferR53.KEY,next);after.put("OuterDirectionR52",encode(RigidTransform.of(b.direction(),new org.joml.Quaternionf())));return new CheckedStep(l,e,after,boxes,null);
 }
 private record DockVisualR52(NervFootGuideDockR52.ViewSpec view,double turn){}
 /** The client follows the accepted canonical turn curve, including the
  * axis-plane projection used by the stator and persistent station source. */
 private static DockVisualR52 dockVisualR52(CompoundTag t,double blend){var current=t.getCompound("DockR52");var before=t.getCompound("PreviousDockR52");if(current.isEmpty()||before.isEmpty())return null;if(!current.getString("Source").equals(NervFootGuideDockR52.SOURCE_SHA)||!current.getString("Source").equals(before.getString("Source"))||!current.getString("Leg").equals(before.getString("Leg"))||!current.getCompound("View").equals(before.getCompound("View")))throw new IllegalStateException("Accepted canonical turn visual source required");var view=NervFootGuideDockR52.viewSpec(current.getCompound("View"));double from=NervFootGuideDockR52.decodePose(before.getCompound("Pose")).turn(),to=NervFootGuideDockR52.decodePose(current.getCompound("Pose")).turn();if(!NervAirTransportManifestR52.same(NervFootGuideDockR52.root(view,to),decode(t.getCompound("Current"))))return null;return new DockVisualR52(view,from+(to-from)*blend);}
 /** Preserve every checked running-shoe knot as a whole-carrier sweep
  * boundary. Uniform directory divisions remain for the curvature bound. */
 private static List<Double> checkedRideTimesR52(int divisions,NervLegacyCarrierRideR52.AcceptedRideStep running){var times=new TreeSet<Double>();for(int i=0;i<=divisions;i++)times.add(i/(double)divisions);if(running!=null)times.addAll(running.sampleTimes());return List.copyOf(times);}
 private NervOriginalCarrierR52(){}
}
