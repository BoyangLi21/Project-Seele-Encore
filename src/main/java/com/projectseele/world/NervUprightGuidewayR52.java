package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Two compact outer captured runners on the unchanged original deck.
 * The deck frame never derives its orientation from a rail tangent. All
 * world positions come from the declared directory curve and fixed mounts. */
public final class NervUprightGuidewayR52 {
 public static final String SOURCE="facility/r52_upright_guideway_paths.json";
 public record RailPiece(String name,String leg,int side,String component,NervServiceFootDriveR52.Piece steel){}
 public record Anchor(String leg,BlockPos at,String state,Vec3 bearing,Vec3 normal,String seatPiece){}
 private record PathBinding(String leg,String reverse,int variant,RigidTransform from,RigidTransform to,JsonObject curve){}
 private static List<RailPiece> fixed;
 private static List<Anchor> anchors;
 private static List<PathBinding> paths;
 private static String installedSha="";
 private static boolean supportsComplete;
 private static NervStaticSpatialIndexR52<RailPiece> index;
 private static final Map<ServerLevel,String> ENABLED=new WeakHashMap<>();
 public static String sourceSha256(){return installedSha;}
 public static synchronized void install(byte[] source,String expectedSha,NervRouteDirectoryR52 directory)throws IOException {
  if(expectedSha==null||!expectedSha.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Explicit actual upright guideway bytes SHA required");
  String sha;try{sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(source));}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}if(!sha.equals(expectedSha))throw new IllegalArgumentException("Actual upright guideway bytes differ");
  if(fixed!=null){if(!installedSha.equals(sha)||!matchesDirectory(directory))throw new IllegalStateException("A different upright guideway is already installed");return;}
  NervOuterCarrierGuideR52.install();var binding=new ArrayList<PathBinding>();var steel=new ArrayList<RailPiece>();var names=new HashSet<String>();var feet=new ArrayList<Anchor>();String schema=null,model=null,transfer=null;boolean complete=false;
  // The actual source is over 180 MB. Consume one authored primitive at a
  // time; a full decimal String/Gson tree would exceed the native host heap.
  try(var reader=new JsonReader(new InputStreamReader(new ByteArrayInputStream(source),StandardCharsets.UTF_8))){reader.beginObject();while(reader.hasNext()){String key=reader.nextName();switch(key){
   case "schema" -> schema=reader.nextString();case "head_transfer_source_sha256" -> transfer=reader.nextString();case "model_source_sha256" -> model=reader.nextString();case "supports_complete" -> complete=reader.nextBoolean();
   case "paths" -> {reader.beginArray();while(reader.hasNext()){var p=JsonParser.parseReader(reader).getAsJsonObject();binding.add(new PathBinding(p.get("leg").getAsString(),p.get("reverse_leg").getAsString(),p.get("variant").getAsInt(),readFrame(p.getAsJsonObject("from")),readFrame(p.getAsJsonObject("to")),p.getAsJsonObject("centre_curve").deepCopy()));}reader.endArray();}
   case "pieces" -> {reader.beginArray();while(reader.hasNext()){var p=readSteelR52(reader);if(!names.add(p.name()))throw new IllegalArgumentException("Unique exact upright steel source pieces required");steel.add(p);}reader.endArray();}
   case "anchors" -> {reader.beginArray();while(reader.hasNext()){var a=JsonParser.parseReader(reader).getAsJsonObject();var at=a.getAsJsonArray("at");var n=readPoint(a.getAsJsonArray("normal"));if(Math.abs(n.length()-1)>1e-9||Math.abs(n.x)+Math.abs(n.y)+Math.abs(n.z)!=1)throw new IllegalArgumentException("Actual finite native face required");feet.add(new Anchor(a.get("leg").getAsString(),new BlockPos(at.get(0).getAsInt(),at.get(1).getAsInt(),at.get(2).getAsInt()),a.get("state").getAsString(),readPoint(a.getAsJsonArray("bearing")),n,a.get("seat_piece").getAsString()));}reader.endArray();}
   default -> reader.skipValue();
  }}reader.endObject();}
  if(!"projectseele.r52.upright-captured-paths.v1".equals(schema)||!NervOuterCarrierGuideR52.SOURCE_SHA.equals(model)||!NervBankHeadTransferR53.SOURCE_SHA.equals(transfer)||binding.isEmpty()||steel.isEmpty()||feet.stream().anyMatch(a->!names.contains(a.seatPiece())))throw new IllegalArgumentException("Selected real outer model, paths, steel and native seats required");paths=List.copyOf(binding);fixed=List.copyOf(steel);anchors=List.copyOf(feet);installedSha=sha;supportsComplete=complete;index=new NervStaticSpatialIndexR52<>(fixed,p->p.steel().mesh().envelope(p.steel().frame(),p.steel().frame()));if(!matchesDirectory(directory)){paths=null;fixed=null;anchors=null;index=null;installedSha="";supportsComplete=false;throw new IllegalArgumentException("Upright source controls/Root directory differ");}
 }
 private static RailPiece readSteelR52(JsonReader reader)throws IOException {String name=null,leg=null,component=null;int side=0;RigidTransform frame=null;double[] rgb=null;reader.beginObject();while(reader.hasNext()){switch(reader.nextName()){case "name" -> name=reader.nextString();case "leg" -> leg=reader.nextString();case "side" -> side=reader.nextInt();case "component" -> component=reader.nextString();case "frame" -> frame=readFrame(JsonParser.parseReader(reader).getAsJsonObject());case "triangles_rgb" -> {double[] values=new double[256];int n=0;reader.beginArray();while(reader.hasNext()){if(n==values.length)values=Arrays.copyOf(values,n*2);double v=reader.nextDouble();if(!Double.isFinite(v))throw new IllegalArgumentException("Finite actual upright vertices required");values[n++]=v;}reader.endArray();rgb=Arrays.copyOf(values,n);}default -> reader.skipValue();}}reader.endObject();if(name==null||leg==null||frame==null||side!=-1&&side!=1||component==null||!Set.of("head","web","bracket","native_seat").contains(component)||rgb==null||rgb.length==0||rgb.length%18!=0)throw new IllegalArgumentException("Complete actual fixed upright primitive required");double[] xyz=new double[rgb.length/2];for(int i=0,k=0;i<rgb.length;i+=6){xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];}return new RailPiece(name,leg,side,component,new NervServiceFootDriveR52.Piece(name,rgb,new NervRigidMeshSweepR52(xyz),frame,false));}
 /** Pure visual read. Consumers must build unpublished local buffers; only a
  * normal return permits publication after the complete original-byte SHA.
  * This does not install paths, change physics fields or enable movement. */
 public static void readVisualR52(InputStream source,String expectedSha,java.util.function.Consumer<RailPiece> pieceConsumer,java.util.function.Consumer<Anchor> anchorConsumer)throws IOException {
  if(expectedSha==null||!expectedSha.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Explicit installed visual bytes SHA required");MessageDigest digest;try{digest=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}String schema=null,model=null,transfer=null;boolean complete=false;int pieceCount=0,anchorCount=0;var names=new HashSet<String>();var anchorNames=new HashSet<String>();
  try(var stream=new DigestInputStream(source,digest);var reader=new JsonReader(new InputStreamReader(stream,StandardCharsets.UTF_8))){reader.beginObject();while(reader.hasNext()){switch(reader.nextName()){
   case "schema" -> schema=reader.nextString();case "head_transfer_source_sha256" -> transfer=reader.nextString();case "model_source_sha256" -> model=reader.nextString();case "supports_complete" -> complete=reader.nextBoolean();
   case "pieces" -> {reader.beginArray();while(reader.hasNext()){var p=readSteelR52(reader);if(!names.add(p.name()))throw new IllegalArgumentException("Duplicate visual steel name");pieceConsumer.accept(p);pieceCount++;}reader.endArray();}
   case "anchors" -> {reader.beginArray();while(reader.hasNext()){var a=JsonParser.parseReader(reader).getAsJsonObject();var at=a.getAsJsonArray("at");var n=readPoint(a.getAsJsonArray("normal"));if(Math.abs(n.length()-1)>1e-9||Math.abs(n.x)+Math.abs(n.y)+Math.abs(n.z)!=1)throw new IllegalArgumentException("Actual visual native face required");var p=new Anchor(a.get("leg").getAsString(),new BlockPos(at.get(0).getAsInt(),at.get(1).getAsInt(),at.get(2).getAsInt()),a.get("state").getAsString(),readPoint(a.getAsJsonArray("bearing")),n,a.get("seat_piece").getAsString());anchorNames.add(p.seatPiece());anchorConsumer.accept(p);anchorCount++;}reader.endArray();}
   default -> reader.skipValue();
  }}reader.endObject();if(reader.peek()!=com.google.gson.stream.JsonToken.END_DOCUMENT)throw new IllegalArgumentException("One exact visual source document required");}
  if(!"projectseele.r52.upright-captured-paths.v1".equals(schema)||!NervOuterCarrierGuideR52.SOURCE_SHA.equals(model)||!NervBankHeadTransferR53.SOURCE_SHA.equals(transfer)||!complete||pieceCount==0||anchorCount==0||!names.containsAll(anchorNames)||!expectedSha.equals(HexFormat.of().formatHex(digest.digest())))throw new IllegalArgumentException("Exact final model/steel/native supports/visual bytes SHA required");
 }
 private static Vec3 readPoint(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
 private static RigidTransform readFrame(JsonObject a){var q=a.getAsJsonArray("quaternion_xyzw");return RigidTransform.of(readPoint(a.getAsJsonArray("translation")),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()));}
 public static boolean matchesDirectory(NervRouteDirectoryR52 d){if(paths==null)return false;for(var p:paths){var l=d.leg(p.leg());var r=d.leg(p.reverse());if(l==null||r==null||l.centreCurve()==null||l.motion()==NervRouteDirectoryR52.Motion.FOOT_BEARING_TURN||!l.centreCurve().toJson().equals(p.curve())||!d.node(l.from()).footFrame().equals(p.from())||!d.node(l.to()).footFrame().equals(p.to())||!r.from().equals(l.to())||!r.to().equals(l.from())||NervMechanicalRailBindingR52.variant(d,l.id())!=p.variant())return false;}return true;}
 public static List<RailPiece> pieces(){if(fixed==null)throw new IllegalStateException("Explicit selected upright paths not installed");return fixed;}
 public static List<Anchor> anchors(){if(anchors==null)throw new IllegalStateException("Explicit selected upright anchors not installed");return anchors;}
 public static Set<ChunkPos> foundationChunks(){var out=new HashSet<ChunkPos>();for(var a:anchors())out.add(new ChunkPos(a.at()));return Set.copyOf(out);}
 // A repainted support remains the same bearing. The measured contact face,
 // not its decorative block identifier, determines physical support.
 private static boolean bears(ServerLevel l,Anchor a){if(l.getChunkSource().getChunkNow(a.at().getX()>>4,a.at().getZ()>>4)==null)return false;var n=a.normal();var u=Math.abs(n.x)>.5?new Vec3(0,1,0):new Vec3(1,0,0);var v=n.cross(u);for(var b:l.getBlockState(a.at()).getCollisionShape(l,a.at()).toAabbs()){b=b.move(a.at());boolean good=true;for(double x:new double[]{-.05,0,.05})for(double z:new double[]{-.05,0,.05}){var p=a.bearing().add(u.scale(x)).add(v.scale(z));double plane=n.x>0?b.maxX:n.x<0?b.minX:n.y>0?b.maxY:n.y<0?b.minY:n.z>0?b.maxZ:b.minZ;double coordinate=n.x!=0?p.x:n.y!=0?p.y:p.z;if(Math.abs(coordinate-plane)>.0002||p.x<b.minX-.0002||p.x>b.maxX+.0002||p.y<b.minY-.0002||p.y>b.maxY+.0002||p.z<b.minZ-.0002||p.z>b.maxZ+.0002)good=false;}if(good)return true;}return false;}
 public static boolean pathAnchorsBearR52(ServerLevel l,String leg){boolean found=false;for(var a:anchors())if(a.leg().equals(leg)){found=true;if(!bears(l,a))return false;}return found;}
 public static synchronized void enable(ServerLevel l,NervRouteDirectoryR52 d){if(!supportsComplete||!matchesDirectory(d)||anchors().isEmpty())throw new IllegalStateException("Exact upright paths and all real native supports required");for(var p:paths)if(!pathAnchorsBearR52(l,p.leg()))throw new IllegalStateException("Actual upright native bearing missing: "+p.leg());ENABLED.put(l,d.fingerprint());}
 public static boolean enabledForDirectoryR52(ServerLevel l,NervRouteDirectoryR52 d){return d.fingerprint().equals(ENABLED.get(l));}
 public static List<RailPiece> actualPieces(ServerLevel l,AABB query){return ENABLED.containsKey(l)?index.query(query):List.of();}
 public static String canonicalPathR52(String leg){if(paths==null)return null;for(var p:paths)if(p.leg().equals(leg)||p.reverse().equals(leg))return p.leg();return null;}
 /** The actual narrow upper/lower/side bearing plates meet actual fixed
  * head facets. This is checked in the independently transported head frame,
  * including vertical/hanging travel; it never infers support from a centre. */
 public static boolean finiteCaptureAtR52(DirectoryTrajectoryR52 curve,double t)throws IOException {
  if(paths==null||!matchesDirectory(curve.directory()))return false;String canonical=canonicalPathR52(curve.leg().id());if(canonical==null)return false;var root=curve.sample(t).evaRoot();var direction=NervOuterCarrierGuideR52.direction(curve,t);var parts=NervOuterCarrierGuideR52.partsAt(root,1,direction);int bearings=0;
  for(var part:parts){if(!Set.of("upper_bearing","lower_bearing","side_bearing").contains(part.role()))continue;int side=part.name().startsWith("outer/-1/")?-1:1;var b=part.mesh().bounds();int axis=part.role().equals("side_bearing")?0:1;double plane=part.role().equals("upper_bearing")?b.minY:part.role().equals("lower_bearing")?b.maxY:part.name().endsWith("/-1")?b.maxX:b.minX;var query=part.mesh().envelope(part.frame(),part.frame()).inflate(.001);var candidates=index.query(query).stream().filter(p->p.side()==side&&p.component().equals("head")&&p.leg().equals(canonical)).toList();if(candidates.isEmpty())return false;var xyz=part.mesh().triangles();var points=new HashSet<Vec3>();for(int n=0;n<xyz.length;n+=3){double c=axis==0?xyz[n]:xyz[n+1];if(Math.abs(c-plane)<1e-7)points.add(part.frame().transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2])));}if(points.size()<3)return false;
   for(var point:points){double nearest=Double.POSITIVE_INFINITY;for(var p:candidates){var v=p.steel().mesh().triangles();var f=p.steel().frame();for(int n=0;n<v.length;n+=9){var a=f.transformPoint(new Vec3(v[n],v[n+1],v[n+2]));var b0=f.transformPoint(new Vec3(v[n+3],v[n+4],v[n+5]));var c=f.transformPoint(new Vec3(v[n+6],v[n+7],v[n+8]));nearest=Math.min(nearest,NervShoulderBearingR52.triangleDistanceR52(point,a,b0,c));}}if(nearest>.0002)return false;}bearings++;
  }return bearings==10;
 }
 /** Only selected primary plate facets may touch the corresponding real head.
  * Structure, joints, foreign lanes and the web never receive this allowance. */
 public static boolean namedCaptureContactR52(NervOriginalCarrierR52.Part from,NervOriginalCarrierR52.Part to,RailPiece fixed){
  if(!fixed.component().equals("head")||!from.name().equals(to.name()))return false;int side=from.name().startsWith("outer/-1/")?-1:1;if(fixed.side()!=side)return false;try{for(var p:NervOuterCarrierGuideR52.templates())if(p.name().equals(from.name())&&p.mesh()==from.mesh()&&p.mesh()==to.mesh()&&Set.of("upper_bearing","lower_bearing","side_bearing").contains(p.role())){for(var part:List.of(from,to)){var direction=part.frame().transformVector(p.role().equals("upper_bearing")?new Vec3(0,1,0):p.role().equals("lower_bearing")?new Vec3(0,-1,0):new Vec3(p.name().endsWith("/-1")?-1:1,0,0));var vertices=part.mesh().triangles();var source=fixed.steel().mesh().triangles();var frame=fixed.steel().frame();for(int v=0;v<vertices.length;v+=3){var point=part.frame().transformPoint(new Vec3(vertices[v],vertices[v+1],vertices[v+2]));double nearest=Double.POSITIVE_INFINITY,signed=Double.NEGATIVE_INFINITY;for(int n=0;n<source.length;n+=9){var a=frame.transformPoint(new Vec3(source[n],source[n+1],source[n+2]));var b=frame.transformPoint(new Vec3(source[n+3],source[n+4],source[n+5]));var c=frame.transformPoint(new Vec3(source[n+6],source[n+7],source[n+8]));var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()<1e-20)continue;normal=normal.normalize();if(Math.abs(normal.dot(direction))<.95)continue;if(normal.dot(direction)<0)normal=normal.scale(-1);double distance=NervShoulderBearingR52.triangleDistanceR52(point,a,b,c);if(distance<nearest){nearest=distance;signed=point.subtract(a).dot(normal);}}if(signed<-.0002)return false;}}return true;}}catch(IOException missing){return false;}return false;
 }
 public static final String PROFILE="projectseele.r52.upright-captured-guideway.v1";
 public record CrossSection(String name,double minX,double minY,double maxX,double maxY){}
 public record RunnerSample(RigidTransform frame,double yaw,double pitch){}
 private static final List<Vec3> MOUNTS=List.of(new Vec3(-6,-2.12,-10),new Vec3(-6,-2.12,10),new Vec3(6,-2.12,-10),new Vec3(6,-2.12,10));
 /** Profile coordinates are in the independent runner frame: Z along rail,
  * Y its capture normal, X across rail. The original pad bottom is Y=-.08. */
 public static List<CrossSection> railSectionR52(){return List.of(new CrossSection("head",-.30,-.20,.30,-.08),new CrossSection("web",-.10,-.55,.10,-.20));}
 public static List<Vec3> mountOffsetsR52(){return MOUNTS;}
 public static RunnerSample sampleR52(RigidTransform fixedDeck,int shoe,Vec3 worldTangent){return sampleR52(fixedDeck,shoe,worldTangent,0);}
 public static RunnerSample sampleR52(RigidTransform fixedDeck,int shoe,Vec3 worldTangent,double verticalYaw){
  if(shoe<0||shoe>=4||fixedDeck.transformVector(new Vec3(0,1,0)).distanceTo(new Vec3(0,1,0))>1e-5||worldTangent==null||!Double.isFinite(worldTangent.lengthSqr())||worldTangent.lengthSqr()<1e-12)throw new IllegalArgumentException("Fixed upright deck and real nonzero route tangent required");
  var local=fixedDeck.inverse().transformVector(worldTangent.normalize());double h=Math.hypot(local.x,local.z),yaw=h>1e-9?Math.atan2(local.x,local.z):verticalYaw,pitch=-Math.atan2(local.y,h);
  var frame=fixedDeck.compose(RigidTransform.of(MOUNTS.get(shoe),new Quaternionf().rotationY((float)yaw).rotateX((float)pitch)));return new RunnerSample(frame,yaw,pitch);
 }
 public static RunnerSample sampleR52(DirectoryTrajectoryR52 curve,int shoe,double t){return sampleR52(curve.sample(t).evaRoot(),shoe,curve.directory().tangent(curve.leg(),curve.fromFraction()+(curve.toFraction()-curve.fromFraction())*t));}
 /** Real compact cheeks, upper crossbar and two under-flange captures.
  * Every added box touches another steel box or the unchanged original fork. */
 public static List<NervLegacyCarrierRideR52.Piece> capturedRunnerPartsR52(String prefix,RigidTransform frame){
  var out=new ArrayList<NervLegacyCarrierRideR52.Piece>();
  add(out,prefix+"/capture_crossbar",new AABB(-.344,-.035,-.20,.344,-.020,.20),frame);
  for(int side:new int[]{-1,1}){
   double lo=side<0?-.344:.302,hi=side<0?-.302:.344;
   add(out,prefix+"/capture_cheek/"+side,new AABB(lo,-.244,-.20,hi,-.020,.20),frame);
   add(out,prefix+"/capture_under/"+side,new AABB(side<0?-.344:.21,-.244,-.20,side<0?-.21:.344,-.202,.20),frame);
  }return List.copyOf(out);
 }
 private static void add(List<NervLegacyCarrierRideR52.Piece> out,String name,AABB bounds,RigidTransform frame){var p=NervServiceFootDriveR52.box(name,bounds,frame,true);out.add(new NervLegacyCarrierRideR52.Piece(name,p.mesh(),p.rgb(),frame,"compact_capture"));}
 /** Paired actual annular thrust faces at the original pin. The fixed upper
  * flange meets the existing lower telescope steel; the rotating lower flange
  * and short web meet the original hinge pin, whose X hinge carries pitch. */
 public static List<NervLegacyCarrierRideR52.Piece> yawBearingPartsR52(String prefix,RigidTransform pin,double yaw){
  var turned=pin.compose(RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationY((float)yaw)));var out=new ArrayList<NervLegacyCarrierRideR52.Piece>();
  out.add(disc(prefix+"/yaw_fixed",pin,.030,.045));out.add(disc(prefix+"/yaw_rotor",turned,.015,.030));
  add(out,prefix+"/yaw_pin_web",new AABB(-.05,-.01,-.04,.05,.030,.04),turned);return List.copyOf(out);
 }
 private static NervLegacyCarrierRideR52.Piece disc(String name,RigidTransform frame,double bottom,double top){
  var a=new ArrayList<Double>();int n=32;double radius=.24;
  for(int i=0;i<n;i++){double u=2*Math.PI*i/n,v=2*Math.PI*(i+1)/n;var A=new Vec3(radius*Math.cos(u),bottom,radius*Math.sin(u));var B=new Vec3(radius*Math.cos(v),bottom,radius*Math.sin(v));var C=new Vec3(B.x,top,B.z);var D=new Vec3(A.x,top,A.z);tri(a,A,B,C);tri(a,A,C,D);tri(a,new Vec3(0,bottom,0),B,A);tri(a,new Vec3(0,top,0),D,C);}
  double[] rgb=a.stream().mapToDouble(x->x).toArray(),xyz=new double[rgb.length/2];for(int i=0,k=0;i<rgb.length;i+=6){xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];}return new NervLegacyCarrierRideR52.Piece(name,new NervRigidMeshSweepR52(xyz),rgb,frame,"yaw_bearing");
 }
 private static void tri(List<Double> out,Vec3... p){for(var v:p)for(double d:new double[]{v.x,v.y,v.z,.36,.43,.48})out.add((double)(float)d);}
 /** Same measured original mount followed by XYZ translation. This method
  * supplies Root geometry offsets; it creates no path or world coordinates. */
 public static Vec3 railCentreR52(DirectoryTrajectoryR52 curve,int shoe,double t){return curve.sample(t).evaRoot().transformPoint(MOUNTS.get(shoe));}
 private NervUprightGuidewayR52(){}
}
