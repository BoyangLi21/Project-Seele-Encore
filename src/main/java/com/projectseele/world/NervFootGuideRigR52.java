package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Matrix3f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Explicit foot-end side carriages. The existing body/Tripo frame carries
 * the short sole-axis rotors; the two stators retain the actual bearing axis
 * and world up during the Root's foot-axis turn. Both use this same source. */
public final class NervFootGuideRigR52 {
 public static final String SOURCE="mesh/foot_guide_rig_r52.json";
 public static final String SOURCE_SHA="cdb42ec6d3856675c26ab5c037927e1821de5bffcb563e7918a9d00ad51391e3";
 public static final double HALF_WIDTH=14.95,AXIS_EXTENSION=14.75,ROW=2.9,REAR=.8,WEB_HALF=.03,PAD_HALF=.15;
 public record Part(String name,String role,double[] rgb,NervRigidMeshSweepR52 mesh){}
 public record Draw(Part part,RigidTransform frame){}
 private static List<Part> parts,bearingParts;private static Map<Integer,FootSupportFrameR52.Binding> nominal;
 public static synchronized void install()throws IOException {
  if(parts!=null)return;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Actual foot-guide rig source changed");}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
  var data=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(!data.get("schema").getAsString().equals("projectseele.r52.engineered-foot-guide-rig.v1")||data.get("stride").getAsInt()!=6)throw new IllegalStateException("Explicit actual foot-guide source required");var out=new ArrayList<Part>();for(var value:data.getAsJsonArray("members")){var row=value.getAsJsonObject();String name=row.get("part").getAsString(),role=row.get("role").getAsString();if(!Set.of("rotor","stator").contains(role))throw new IllegalStateException("Unknown actual foot-guide attachment");var a=data.getAsJsonObject("parts").getAsJsonArray(name);double[] rgb=new double[a.size()],xyz=new double[a.size()/2];for(int i=0,n=0;i<rgb.length;i+=6){for(int c=0;c<6;c++)rgb[i+c]=a.get(i+c).getAsFloat();xyz[n++]=rgb[i];xyz[n++]=rgb[i+1];xyz[n++]=rgb[i+2];}out.add(new Part(name,role,rgb,new NervRigidMeshSweepR52(xyz)));}
  var bindings=new HashMap<Integer,FootSupportFrameR52.Binding>();for(int v=0;v<3;v++){var b=data.getAsJsonObject("nominal_sole_bindings").getAsJsonObject(Integer.toString(v));bindings.put(v,new FootSupportFrameR52.Binding(point(b.getAsJsonArray("l")),point(b.getAsJsonArray("r")),RigidTransform.identity()));}parts=List.copyOf(out);nominal=Map.copyOf(bindings);var centred=new ArrayList<Part>();for(var p:parts){int side=p.name().split("_")[3].equals("-1")?-1:1;double[] rgb=p.rgb().clone(),xyz=new double[rgb.length/2];for(int i=0,n=0;i<rgb.length;i+=6){rgb[i]=(float)(rgb[i]-side*AXIS_EXTENSION);xyz[n++]=rgb[i];xyz[n++]=rgb[i+1];xyz[n++]=rgb[i+2];}centred.add(new Part(p.name(),p.role(),rgb,new NervRigidMeshSweepR52(xyz)));}bearingParts=List.copyOf(centred);
 }
 private static Vec3 point(JsonArray p){return new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());}
 public static List<Part> parts()throws IOException {install();return parts;}
 public static FootSupportFrameR52.Binding nominalBinding(int variant)throws IOException {install();var b=nominal.get(variant);if(b==null)throw new IllegalArgumentException("Actual unit variant required");return b;}
 public static RigidTransform bearingFrame(Vec3 centre,Vec3 axis,Vec3 up) {
  var x=axis.normalize();if(Math.abs(x.dot(up.normalize()))>.00001)throw new IllegalStateException("Actual source sole bearing axis is incompatible with the declared guide up");var y=up.normalize();var z=x.cross(y).normalize();var matrix=new Matrix3f().setColumn(0,new Vector3f((float)x.x,(float)x.y,(float)x.z)).setColumn(1,new Vector3f((float)y.x,(float)y.y,(float)y.z)).setColumn(2,new Vector3f((float)z.x,(float)z.y,(float)z.z));return RigidTransform.of(centre,new Quaternionf().setFromNormalized(matrix).normalize());
 }
 public static RigidTransform localBearing(FootSupportFrameR52.Binding binding){return bearingFrame(binding.contactCentre(),binding.rightFoot().subtract(binding.leftFoot()),new Vec3(0,1,0));}
 public static List<Draw> draws(FootSupportFrameR52.Binding binding,RigidTransform carrierRoot,float rise)throws IOException {
  return draws(binding,carrierRoot,rise,new Vec3(0,1,0));
 }
 /** The bearing centres stay exactly on the original two-foot axis. The
  * real annular stators align with the physical guide tangent; their small
  * skew is admitted only by an actual rotor/bore triangle pair proof. */
 public static List<Draw> draws(FootSupportFrameR52.Binding binding,RigidTransform carrierRoot,float rise,Vec3 guideUp)throws IOException {
  install();if(!Float.isFinite(rise)||rise<0||rise>1||!Double.isFinite(guideUp.lengthSqr())||guideUp.length()<.999)throw new IllegalArgumentException("Actual accepted carrier/guide sample required");var moving=carrierRoot.compose(new RigidTransform(new Vec3(0,-64*(1-rise),0),0,0,0,1));var rotor=moving.compose(localBearing(binding));var axis=moving.transformVector(binding.rightFoot().subtract(binding.leftFoot())).normalize();var up=guideUp.normalize();var normal=axis.subtract(up.scale(axis.dot(up))).normalize();if(normal.lengthSqr()<.999)throw new IllegalStateException("Guide tangent parallels original sole axis");var result=new ArrayList<Draw>();for(var p:bearingParts){int side=p.name().split("_")[3].equals("-1")?-1:1;var centre=rotor.transformPoint(new Vec3(side*AXIS_EXTENSION,0,0));var f=p.role().equals("rotor")?rotor.compose(new RigidTransform(new Vec3(side*AXIS_EXTENSION,0,0),0,0,0,1)):bearingFrame(centre,normal,up);result.add(new Draw(p,f));}return List.copyOf(result);
 }
 public static List<Draw> draws(EvaUnit01Entity e,float partial)throws IOException {if(EvaMechanicalFrameR52.hasOriginalCarrierControllerR52(e)){NervOuterCarrierGuideR52.install();return List.of();}if(!EvaMechanicalFrameR52.groundGuidesDeclaredR52(e))return List.of();return draws(EvaMechanicalFrameR52.groundGuideBindingR52(e),EvaMechanicalFrameR52.carrierFrameR52(e,partial),e.carrierRiseProgress(partial));}
 public static List<NervFlightProofR52.ObstacleMesh> actualMeshes(EvaUnit01Entity e,float partial)throws IOException {var result=new ArrayList<NervFlightProofR52.ObstacleMesh>();for(var d:draws(e,partial))result.add(new NervFlightProofR52.ObstacleMesh(d.part().mesh(),d.frame()));return List.copyOf(result);}
 public static AABB bounds(FootSupportFrameR52.Binding b,RigidTransform root,float rise)throws IOException {AABB result=null;for(var d:draws(b,root,rise)){var box=d.part().mesh().envelope(d.frame(),d.frame());result=result==null?box:result.minmax(box);}return result;}
 /** Finite lower bore faces carry the original cylindrical axle. The 0.2mm
  * allowance is a measured mating fit, never a whole-part collision waiver. */
 public record AxleFit(double area,double maximumFitError,double upwardNormal){}
 private record FitMemo(RigidTransform relative,AxleFit fit){}
 private static final Map<String,FitMemo> AXLE_FITS=new HashMap<>();
 public static List<AxleFit> actualAxleFitsR52(FootSupportFrameR52.Binding binding,RigidTransform root,float rise,Vec3 up)throws IOException {var all=draws(binding,root,rise,up);var out=new ArrayList<AxleFit>();for(int side:new int[]{-1,1})out.add(axleFit(all.stream().filter(d->d.part().name().equals("foot_guide_rotor_"+side)).findFirst().orElseThrow(),all.stream().filter(d->d.part().name().equals("foot_guide_stator_"+side)).findFirst().orElseThrow()));return List.copyOf(out);}
 public static boolean actualAxleBearingR52(FootSupportFrameR52.Binding binding,RigidTransform root,float rise,Vec3 up)throws IOException {
  var all=draws(binding,root,rise,up);for(int side:new int[]{-1,1}){var rotor=all.stream().filter(d->d.part().name().equals("foot_guide_rotor_"+side)).findFirst().orElseThrow();var stator=all.stream().filter(d->d.part().name().equals("foot_guide_stator_"+side)).findFirst().orElseThrow();var fit=axleFit(rotor,stator);if(fit.area()<.005||fit.maximumFitError()>.0002||fit.upwardNormal()<.1)return false;}return true;
 }
 private static AxleFit axleFit(Draw rotor,Draw stator){var relative=rotor.frame().inverse().compose(stator.frame());var gravity=stator.frame().inverse().transformVector(new Vec3(0,1,0));String key=Math.round(gravity.x*1e7)+"/"+Math.round(gravity.y*1e7)+"/"+Math.round(gravity.z*1e7)+"/"+stator.part().name()+"/"+Math.round(relative.qx()*1e7)+"/"+Math.round(relative.qy()*1e7)+"/"+Math.round(relative.qz()*1e7)+"/"+Math.round(relative.qw()*1e7);FitMemo saved; synchronized(AXLE_FITS){saved=AXLE_FITS.get(key);}if(saved!=null&&saved.relative().translation().distanceTo(relative.translation())<1e-8&&saved.relative().rotationErrorDegrees(relative)<1e-7)return saved.fit();
  var xyz=stator.part().mesh().triangles();var shaft=rotor.part().mesh().triangles();double area=0,maximum=0,upward=1;for(int i=0;i<xyz.length;i+=9){var a=new Vec3(xyz[i],xyz[i+1],xyz[i+2]);var b=new Vec3(xyz[i+3],xyz[i+4],xyz[i+5]);var c=new Vec3(xyz[i+6],xyz[i+7],xyz[i+8]);if(a.y>1e-7||b.y>1e-7||c.y>1e-7||Math.abs(Math.hypot(a.y,a.z)-.18)>1e-6||Math.abs(Math.hypot(b.y,b.z)-.18)>1e-6||Math.abs(Math.hypot(c.y,c.z)-.18)>1e-6)continue;var n=b.subtract(a).cross(c.subtract(a));double patch=n.length()*.5;if(patch<1e-8)continue;n=n.normalize();var centre=a.add(b).add(c).scale(1D/3);if(n.dot(new Vec3(0,-centre.y,-centre.z))<0)n=n.scale(-1);double supporting=stator.frame().transformVector(n).y;if(supporting<=.1)continue;double gap=0;for(var weights:List.of(new double[]{.6,.2,.2},new double[]{.2,.6,.2},new double[]{.2,.2,.6})){var p=relative.transformPoint(a.scale(weights[0]).add(b.scale(weights[1])).add(c.scale(weights[2])));double closest=Double.POSITIVE_INFINITY;for(int j=0;j<shaft.length;j+=9){if(p.x<Math.min(shaft[j],Math.min(shaft[j+3],shaft[j+6]))-.0003||p.x>Math.max(shaft[j],Math.max(shaft[j+3],shaft[j+6]))+.0003||p.y<Math.min(shaft[j+1],Math.min(shaft[j+4],shaft[j+7]))-.0003||p.y>Math.max(shaft[j+1],Math.max(shaft[j+4],shaft[j+7]))+.0003||p.z<Math.min(shaft[j+2],Math.min(shaft[j+5],shaft[j+8]))-.0003||p.z>Math.max(shaft[j+2],Math.max(shaft[j+5],shaft[j+8]))+.0003)continue;closest=Math.min(closest,NervShoulderBearingR52.triangleDistanceR52(p,new Vec3(shaft[j],shaft[j+1],shaft[j+2]),new Vec3(shaft[j+3],shaft[j+4],shaft[j+5]),new Vec3(shaft[j+6],shaft[j+7],shaft[j+8])));}gap=Math.max(gap,closest);}if(gap>.0002)return new AxleFit(0,gap,supporting);area+=patch;maximum=Math.max(maximum,gap);upward=Math.min(upward,supporting);}
  var result=new AxleFit(area,maximum,upward);synchronized(AXLE_FITS){if(AXLE_FITS.size()>128)AXLE_FITS.clear();AXLE_FITS.put(key,new FitMemo(relative,result));}return result;
 }
 /** Only the actual opposed pad/T-head planes or the four bottom spine
  * triangles on a rest plinth admit tangent contact. All vertices stay in
  * an exterior half space at both ends of this affine service-lift stroke. */
 public static boolean namedGuideContactR52(Draw from,Draw to,NervServiceFootDriveR52.Piece guide){
  if(guide.name().startsWith("service_rest_plinth/")&&from.part().name().startsWith("foot_guide_stator_")){var plinth=guide.mesh().envelope(guide.frame(),guide.frame());for(var d:List.of(from,to))if(d.part().mesh().envelope(d.frame(),d.frame()).minY<plinth.maxY-.000003)return false;return true;}
  if(!from.part().name().startsWith("foot_guide_pad_")||!guide.name().endsWith("/0")||!guide.name().startsWith("service_fixed_")&&!guide.name().startsWith("service_bridge/")&&!guide.name().startsWith("ground_rail/"))return false;
  var target=guide.mesh().bounds();boolean inner=from.part().name().endsWith("_inner");int side=from.part().name().split("_")[3].equals("-1")?-1:1;double plane=side<0?-target.maxX:target.minX,opposite=side<0?-target.minX:target.maxX;for(var d:List.of(from,to)){var relative=guide.frame().inverse().compose(d.frame());for(int i=0;i<d.part().rgb().length;i+=6){var p=relative.transformPoint(new Vec3(d.part().rgb()[i],d.part().rgb()[i+1],d.part().rgb()[i+2]));if(inner?side*p.x>plane+.000003:side*p.x<opposite-.000003)return false;}}return true;
 }
 private NervFootGuideRigR52(){}
}
