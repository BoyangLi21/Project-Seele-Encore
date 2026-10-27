package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Original six shoulder pads with the measured final hydraulic stroke.
 * The renderer, moving obstacles and finite skin bearing use these points. */
public final class NervShoulderBearingR52 {
 public static final String SOURCE="mesh/hangar_shoulder_contacts_r52.json";
 public static final String SOURCE_SHA="324d7f539fed7e7a83fb0420d30fbadc432ccfbe5bcfcf7a269aedd99025226e";
 public record Pad(int variant,int side,String part,Vec3 normal,List<Vec3> points,List<Vec3> anchors,List<Vec3> links,double finalStroke){}
 private static List<Pad> pads;private static Map<String,double[]> triangles;
 public static synchronized void install()throws IOException {
  if(pads!=null)return;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
  try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Actual shoulder closure source changed");}catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
  var root=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(root.get("stride").getAsInt()!=6)throw new IllegalStateException("Actual shoulder RGB triangles required");var rows=new ArrayList<Pad>();
  for(var raw:root.getAsJsonArray("contacts")){var p=raw.getAsJsonObject();var row=new Pad(p.get("variant").getAsInt(),p.get("side").getAsInt(),p.get("part").getAsString(),point(p.getAsJsonArray("normal")),points(p.getAsJsonArray("points")),points(p.getAsJsonArray("anchors")),points(p.getAsJsonArray("links")),p.get("closure_stroke_m").getAsDouble());if(row.points().size()!=3||row.anchors().size()!=2||row.links().size()!=2||row.finalStroke()<.03||row.finalStroke()>.031||Math.abs(row.normal().length()-1)>.000001)throw new IllegalStateException("Actual finite original pad calibration required");rows.add(row);}
  if(rows.size()!=6)throw new IllegalStateException("All six original shoulder contacts required");var all=new HashMap<String,double[]>();for(var entry:root.getAsJsonObject("parts").entrySet()){var a=entry.getValue().getAsJsonArray();double[] xyz=new double[a.size()/2];for(int i=0,n=0;i<a.size();i+=6){xyz[n++]=a.get(i).getAsFloat();xyz[n++]=a.get(i+1).getAsFloat();xyz[n++]=a.get(i+2).getAsFloat();}all.put(entry.getKey(),xyz);}pads=List.copyOf(rows);triangles=Map.copyOf(all);
 }
 private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
 private static List<Vec3> points(JsonArray a){var out=new ArrayList<Vec3>();for(var x:a)out.add(point(x.getAsJsonArray()));return List.copyOf(out);}
 public static List<Pad> pads()throws IOException {install();return pads;}
 public static Vec3 movement(Pad p,float opening){if(!Float.isFinite(opening)||opening<0||opening>1)throw new IllegalArgumentException("Actual shoulder opening clock required");float lift=EvaDorsalMechanism.smooth(opening/.25F),out=EvaDorsalMechanism.smooth((opening-.23F)/.65F);return p.normal().scale(2.1*lift-p.finalStroke()*(1-lift)).add(p.side()*5.35*out,0,0);}
 public static Vec3 movement(int variant,int side,float opening){try{install();return movement(pads.stream().filter(p->p.variant()==variant&&p.side()==side).findFirst().orElseThrow(),opening);}catch(IOException unavailable){throw new IllegalStateException("Actual shoulder source unavailable",unavailable);}}
 public static boolean bears(EvaOriginalMeshGeometryR52.Geometry body,RigidTransform bodyRoot,RigidTransform gantry,int variant,CarrierMountProfileR53.State mounting)throws IOException {
  return bears(body,bodyRoot,mounting.payloadFrame(gantry),variant);
 }
 public static boolean permitsPadContactR52(EvaOriginalMeshGeometryR52.Geometry body,RigidTransform bodyRoot,RigidTransform gantry,int variant,String bone,NervFlightProofR52.ObstacleMesh obstacle,CarrierMountProfileR53.State mounting)throws IOException {
  return permitsPadContactR52(body,bodyRoot,mounting.payloadFrame(gantry),variant,bone,obstacle);
 }
 public static boolean bears(EvaOriginalMeshGeometryR52.Geometry body,RigidTransform bodyRoot,RigidTransform gantry,int variant)throws IOException {
  return bears(body.parts(),bodyRoot,gantry,variant);
 }
 public static boolean bears(List<EvaOriginalMeshGeometryR52.Part> parts,RigidTransform bodyRoot,RigidTransform gantry,int variant)throws IOException {
  install();var local=bodyRoot.inverse().compose(gantry);int bearing=0;for(var p:pads)if(p.variant()==variant){var moved=movement(p,0);var face=p.points().stream().map(v->local.transformPoint(v.add(moved))).toList();if(face.get(1).subtract(face.get(0)).cross(face.get(2).subtract(face.get(0))).length()*.5<.04)return false;for(var v:face){double best=Double.POSITIVE_INFINITY;for(var skin:parts)if(skin.bone().equals(p.side()<0?"arm_l":"arm_r")){var xyz=skin.triangles();for(int i=0;i<xyz.length;i+=9)best=Math.min(best,triangleDistanceR52(v,new Vec3(xyz[i],xyz[i+1],xyz[i+2]),new Vec3(xyz[i+3],xyz[i+4],xyz[i+5]),new Vec3(xyz[i+6],xyz[i+7],xyz[i+8])));}if(best>.002)return false;}bearing++;}return bearing==2;
 }
 /** Only the measured arm facet may touch its exact selected pad. Clip the
  * actual skin triangles to the finite pad footprint before checking the
  * pad's exterior half-space, so a remote arm vertex grants no exemption. */
 public static boolean permitsPadContactR52(EvaOriginalMeshGeometryR52.Geometry body,RigidTransform bodyRoot,RigidTransform gantry,int variant,String bone,NervFlightProofR52.ObstacleMesh obstacle)throws IOException {
  install();if(!bone.equals("arm_l")&&!bone.equals("arm_r")||!bears(body,bodyRoot,gantry,variant))return false;int side=bone.equals("arm_l")?-1:1;var pad=pads.stream().filter(p->p.variant()==variant&&p.side()==side).findFirst().orElseThrow();var local=new RigidTransform(movement(pad,0),0,0,0,1);var expected=gantry.compose(local);if(!NervAirTransportManifestR52.same(obstacle.frame(),expected)||!NervAirTransportManifestR52.same(obstacle.endFrame(),expected)||!Arrays.equals(obstacle.mesh().triangles(),triangles.get(pad.part())))return false;
  var worldPoints=pad.points().stream().map(p->gantry.transformPoint(p.add(movement(pad,0)))).toList();var normal=gantry.transformVector(pad.normal());double plane=normal.dot(worldPoints.get(0));boolean tested=false;for(var skin:body.parts())if(skin.bone().equals(bone)){var xyz=skin.triangles();for(int i=0;i<xyz.length;i+=9){List<Vec3> poly=new ArrayList<>();for(int n=0;n<9;n+=3)poly.add(bodyRoot.transformPoint(new Vec3(xyz[i+n],xyz[i+n+1],xyz[i+n+2])));for(int edge=0;edge<3&&!poly.isEmpty();edge++){var origin=worldPoints.get(edge);var inward=normal.cross(worldPoints.get((edge+1)%3).subtract(origin));if(inward.dot(worldPoints.get((edge+2)%3).subtract(origin))<0)inward=inward.scale(-1);poly=clip(poly,origin,inward);}for(var p:poly){tested=true;if(normal.dot(p)-plane>.0002)return false;}}}return tested;
 }
 private static List<Vec3> clip(List<Vec3> polygon,Vec3 origin,Vec3 inward){var out=new ArrayList<Vec3>();var before=polygon.get(polygon.size()-1);double old=before.subtract(origin).dot(inward);for(var now:polygon){double value=now.subtract(origin).dot(inward);if((old>=0)!=(value>=0)){double t=old/(old-value);out.add(before.add(now.subtract(before).scale(t)));}if(value>=0)out.add(now);before=now;old=value;}return out;}
 private static double edgeDistance(Vec3 p,Vec3 a,Vec3 b){var d=b.subtract(a);double t=d.lengthSqr()==0?0:Math.max(0,Math.min(1,p.subtract(a).dot(d)/d.lengthSqr()));return p.distanceTo(a.add(d.scale(t)));}
 public static double triangleDistanceR52(Vec3 p,Vec3 a,Vec3 b,Vec3 c){var ab=b.subtract(a);var ac=c.subtract(a);var normal=ab.cross(ac);double n=normal.length();if(n<1e-12)return Math.min(edgeDistance(p,a,b),Math.min(edgeDistance(p,b,c),edgeDistance(p,c,a)));normal=normal.scale(1/n);double height=p.subtract(a).dot(normal);var q=p.subtract(normal.scale(height));double d00=ab.dot(ab),d01=ab.dot(ac),d11=ac.dot(ac),d20=q.subtract(a).dot(ab),d21=q.subtract(a).dot(ac),den=d00*d11-d01*d01;double v=(d11*d20-d01*d21)/den,w=(d00*d21-d01*d20)/den;if(v>=-1e-8&&w>=-1e-8&&v+w<=1+1e-8)return Math.abs(height);return Math.min(edgeDistance(p,a,b),Math.min(edgeDistance(p,b,c),edgeDistance(p,c,a)));}
 private record MeshKey(String name,double stretch){}
 private static final Map<MeshKey,NervRigidMeshSweepR52> meshes=new LinkedHashMap<>();
 private static synchronized NervFlightProofR52.ObstacleMesh mesh(String name,RigidTransform f,double stretch)
 {
  var key=new MeshKey(name,stretch);var mesh=meshes.get(key);
  if(mesh==null){var xyz=triangles.get(name).clone();if(stretch!=1)for(int i=2;i<xyz.length;i+=3)xyz[i]*=stretch;mesh=new NervRigidMeshSweepR52(xyz);if(meshes.size()>=64)meshes.remove(meshes.keySet().iterator().next());meshes.put(key,mesh);}
  return new NervFlightProofR52.ObstacleMesh(mesh,f);
 }
 public record PlacedSource(String part,RigidTransform frame,double stretch){}
 public static List<PlacedSource> transforms(int variant,RigidTransform gantry,float closed,CarrierMountProfileR53.State mounting)throws IOException {
  install();var out=new ArrayList<PlacedSource>();for(var p:pads)if(p.variant()==variant){var move=mounting.shoulderMovement(movement(p,1-closed));out.add(new PlacedSource(p.part(),gantry.compose(new RigidTransform(move,0,0,0,1)),1));for(int i=0;i<2;i++){var anchor=p.anchors().get(i);var end=p.links().get(i).add(move);var delta=end.subtract(anchor);double length=delta.length();if(length<=2.22)throw new IllegalStateException("Actual shoulder actuator exhausted");var turn=new Quaternionf().rotationTo(0,0,1,(float)(delta.x/length),(float)(delta.y/length),(float)(delta.z/length));var frame=gantry.compose(RigidTransform.of(anchor,turn));out.add(new PlacedSource("shoulder_joint",frame,1));out.add(new PlacedSource("shoulder_barrel",frame,1));out.add(new PlacedSource("shoulder_piston_unit",frame.compose(new RigidTransform(new Vec3(0,0,2.18),0,0,0,1)),length-2.18));var endFrame=mounting.aboveFloor()?gantry.compose(RigidTransform.of(end,mounting.shoulderEndRotation(p.normal(),turn))):frame.compose(new RigidTransform(new Vec3(0,0,length),0,0,0,1));out.add(new PlacedSource("shoulder_joint",endFrame,1));}}return List.copyOf(out);
 }
 public static List<NervFlightProofR52.ObstacleMesh> actualMeshes(int variant,RigidTransform gantry,float closed)throws IOException {return actualMeshes(variant,gantry,closed,CarrierMountProfileR53.LEGACY);}
 public static List<NervFlightProofR52.ObstacleMesh> actualMeshes(int variant,RigidTransform gantry,float closed,CarrierMountProfileR53.State mounting)throws IOException {
  var out=new ArrayList<NervFlightProofR52.ObstacleMesh>();for(var p:transforms(variant,gantry,closed,mounting))out.add(mesh(p.part(),p.frame(),p.stretch()));return List.copyOf(out);
 }
 private NervShoulderBearingR52(){}
}
