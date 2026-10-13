package com.projectseele.world;

import com.google.gson.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.*;

/** Two real compact outer captures. The original deck and EVA keep their
 * frame; only the captured rail head takes the independently transported
 * track frame. The source contains measured original deck weld facets. */
public final class NervOuterCarrierGuideR52 {
 public static final String SOURCE="mesh/upright_outer_captured_r52.json",SOURCE_SHA="026215b88520d6f965dbb1a9303fbaf0fee8d4f912d8d1c668d6f26619e8a632";
 public record Template(String name,String frame,String role,NervRigidMeshSweepR52 mesh,double[] rgb){}
 private static List<Template> parts;
 public static boolean selected(){return parts!=null;}
 public static synchronized void install()throws IOException {
  if(parts!=null)return;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
  try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Actual selected outer-capture source differs");}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
  var source=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
  if(!source.get("schema").getAsString().equals("projectseele.r52.upright-outer-captured-model.v1")||!source.get("original_full_source_sha256").getAsString().equals(NervOriginalCarrierR52.SOURCE_SHA)||!source.get("original_running_source_sha256").getAsString().equals(NervLegacyCarrierRideR52.SOURCE_SHA))throw new IllegalStateException("Original full carrier/deck dependency differs");
  var out=new ArrayList<Template>();for(var value:source.getAsJsonArray("parts")){var p=value.getAsJsonObject();String frame=p.get("frame").getAsString();if(!Set.of("ROOT","RUNNER_NEG","RUNNER_POS").contains(frame))throw new IllegalStateException("Unknown real outer capture frame");var a=p.getAsJsonArray("triangles_rgb");if(a.size()%18!=0||a.isEmpty())throw new IllegalStateException("Complete actual outer steel triangles required");double[] rgb=new double[a.size()],xyz=new double[a.size()/2];for(int i=0,k=0;i<rgb.length;i+=6){for(int c=0;c<6;c++)rgb[i+c]=a.get(i+c).getAsDouble();xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];}out.add(new Template(p.get("name").getAsString(),frame,p.get("role").getAsString(),new NervRigidMeshSweepR52(xyz),rgb));}parts=List.copyOf(out);
 }
 public static List<Template> templates()throws IOException{install();return parts;}
 public static Vec3 ballLocal(int side){if(side!=-1&&side!=1)throw new IllegalArgumentException("Actual opposed outer capture required");return new Vec3(side*15,-3.42,side*14.78);}
 /** X is the fixed deck X projected perpendicular to the rail tangent.
  * This frame stays continuous through the declared vertical joins and does
  * not reset azimuth or rotate the carried assembly. */
 public static RigidTransform headFrame(RigidTransform deck,int side,Vec3 worldDirection){
  if(deck.transformVector(new Vec3(0,1,0)).distanceTo(new Vec3(0,1,0))>1e-5||worldDirection==null||!Double.isFinite(worldDirection.lengthSqr())||worldDirection.lengthSqr()<1e-12)throw new IllegalArgumentException("Actual fixed upright deck and nonzero track direction required");
  var z=worldDirection.normalize();var fixedX=deck.transformVector(new Vec3(1,0,0));var x=fixedX.subtract(z.scale(fixedX.dot(z)));if(x.lengthSqr()<.01)throw new IllegalArgumentException("Declared guide tangent degenerates the transported capture frame");x=x.normalize();var y=z.cross(x).normalize();var m=new Matrix3f().setColumn(0,x.toVector3f()).setColumn(1,y.toVector3f()).setColumn(2,z.toVector3f());var q=new Quaternionf().setFromNormalized(m).normalize();var centre=deck.transformPoint(ballLocal(side));return RigidTransform.of(centre.subtract(y.scale(.35)),q);
 }
 public static List<NervLegacyCarrierRideR52.Piece> partsAt(RigidTransform root,float rise,Vec3 direction)throws IOException {
  install();if(!Float.isFinite(rise)||rise<0||rise>1)throw new IllegalArgumentException("Actual original lift state required");var deck=root.compose(new RigidTransform(new Vec3(0,-64*(1-rise),0),0,0,0,1));var negative=headFrame(deck,-1,direction);var positive=headFrame(deck,1,direction);var out=new ArrayList<NervLegacyCarrierRideR52.Piece>();for(var p:parts){var frame=p.frame().equals("ROOT")?deck:p.frame().equals("RUNNER_NEG")?negative:positive;out.add(new NervLegacyCarrierRideR52.Piece(p.name(),p.mesh(),p.rgb(),frame,p.role()));}return List.copyOf(out);
 }
 public static Vec3 direction(DirectoryTrajectoryR52 curve,double t){double f=curve.directory().intervalFraction(curve.leg(),curve.fromFraction(),curve.toFraction(),t);var d=curve.directory().tangent(curve.leg(),f);for(var route:curve.directory().routes().values()){int index=route.legs().indexOf(curve.leg().id());if(index<0||!route.recovery())continue;var forward=curve.directory().route(route.reverseOf());if(forward==null||forward.legs().size()!=route.legs().size())throw new IllegalStateException("Actual declared reverse route pair required");var canonical=curve.directory().leg(forward.legs().get(forward.legs().size()-1-index));if(canonical==null||!canonical.from().equals(curve.leg().to())||!canonical.to().equals(curve.leg().from()))throw new IllegalStateException("Reverse capture guide endpoints differ");return d.scale(-1);}return d;}
 private NervOuterCarrierGuideR52(){}
}
