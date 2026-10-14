package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Full selected production crane inventory at an exact common pose endpoint.
 * This class supplies real geometry; it does not claim a two-pose chord is
 * the continuous curved rig trajectory or silently grant native clearance. */
public final class NervCraneGeometryR52
{
    private static NervCraneGeometryR52 obstacleSourceR52;
    private static volatile NervCraneGeometryR52 classpathSourceR52;
    private record ActualCraneMeshesR52(NervCranePoseR52.State state,List<NervFlightProofR52.ObstacleMesh> meshes){}
    private static final Map<com.projectseele.entity.NervCarrierPlatformEntity,ActualCraneMeshesR52> ACTUAL_CRANES_R52=new WeakHashMap<>();
    /** Same complete nineteen parts, real trolley frame, hoist offset,
     * reference and original gripper pose used by PlugGantryRenderer. */
    public static synchronized List<NervFlightProofR52.ObstacleMesh> actualObstacleMeshesR52(com.projectseele.entity.NervCarrierPlatformEntity e)throws IOException {if(!e.isPlugCrane()||!e.hasDeclaredMachineFrameR52())throw new IllegalStateException("Actual declared capsule hoist required");if(obstacleSourceR52==null)obstacleSourceR52=loadClasspath();var capsule=e.getCranePlug();var state=new NervCranePoseR52.State(RigidTransform.of(e.position(),e.declaredMachineRotationR52()),e.actualCraneBottomOffsetR52(),capsule==null?null:capsule.getCanonicalTransform(),capsule!=null,e.hasCraneReference()?e.position().add(e.getCraneReferenceAnchor()):null,e.hasCraneReference()?e.getCraneReferenceRotation():null);var old=ACTUAL_CRANES_R52.get(e);if(old!=null&&old.state().equals(state))return old.meshes();var out=new ArrayList<NervFlightProofR52.ObstacleMesh>();for(var p:obstacleSourceR52.parts(state.pose(obstacleSourceR52.mount())))out.add(new NervFlightProofR52.ObstacleMesh(new NervRigidMeshSweepR52(p.triangles()),p.frame()));if(out.size()!=19)throw new IllegalStateException("Complete actual hoist inventory required");var result=List.copyOf(out);ACTUAL_CRANES_R52.put(e,new ActualCraneMeshesR52(state,result));return result;}
    private static volatile double[] rollingWheel;
    /** Actual finite baked tread, rather than an analytic-circle contact.
     * The submillimetre bogie displacement keeps that same mesh on its rail. */
    public static double wheelBearingOffset(double phase)
    {
        var xyz=rollingWheel;if(xyz==null)synchronized(NervCraneGeometryR52.class){xyz=rollingWheel;if(xyz==null)try(var stream=new java.util.zip.GZIPInputStream(new ByteArrayInputStream(EvaOriginalMeshGeometryR52.classpathBytes("eva/actual_crane_procedural_triangles_r52.json.gz")))){byte[] bytes=stream.readAllBytes();require(sha(bytes).equals("3411018955aec9b8827dcfcc217275fffd3edbe8880d448500f06beefd216064"),"Actual wheel source changed");var array=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("parts").getAsJsonArray("wheel");xyz=new double[array.size()];for(int i=0;i<xyz.length;i++)xyz[i]=array.get(i).getAsDouble();rollingWheel=xyz;}catch(IOException missing){throw new IllegalStateException("Actual rendered rolling tread absent",missing);}}
        var q=new Quaternionf().rotationX((float)phase);double minimum=Double.POSITIVE_INFINITY;for(int i=0;i<xyz.length;i+=3){var v=q.transform(new Vector3f((float)xyz[i],(float)xyz[i+1],(float)xyz[i+2]));minimum=Math.min(minimum,v.y);}return -minimum;
    }
    public record Part(String name,double[] triangles,RigidTransform frame)
    {public Part{triangles=triangles.clone();}public double[] triangles(){return triangles.clone();}}
    private final Map<String,double[]> procedural,gripper;private final Map<String,Vec3> anchors;private final String source;
    private NervCraneGeometryR52(Map<String,double[]> proc,Map<String,double[]> grip,Map<String,Vec3> anchors,String source)
    {procedural=Map.copyOf(proc);gripper=Map.copyOf(grip);this.anchors=Map.copyOf(anchors);this.source=source;}
    public String sourceFingerprint(){return source;}public Vec3 mount(){return anchors.get("mount");}
    public static synchronized NervCraneGeometryR52 loadClasspath()throws IOException
    {if(classpathSourceR52!=null)return classpathSourceR52;var loaded=load(path->{if(path.equals("eva/actual_crane_procedural_triangles_r52.json"))try(var stream=new java.util.zip.GZIPInputStream(new ByteArrayInputStream(EvaOriginalMeshGeometryR52.classpathBytes(path+".gz")))){return stream.readAllBytes();}return EvaOriginalMeshGeometryR52.classpathBytes(path);},"3411018955aec9b8827dcfcc217275fffd3edbe8880d448500f06beefd216064","af16832dc6c143d3c6a23eb38811021b75c13860436682e8071b9990fc83067f");classpathSourceR52=loaded;return loaded;}
    public static boolean classpathReadyR52(){return classpathSourceR52!=null;}
    Map<String,double[]> rawParts(){var result=new HashMap<String,double[]>(procedural);gripper.forEach((name,xyz)->result.put("gripper/"+name,xyz));return Map.copyOf(result);}
    Vec3 jawPivot(String name){return anchors.get(name);}
    public static NervCraneGeometryR52 load(EvaOriginalMeshGeometryR52.ByteSource source,String proceduralSha,String gripperSha)throws IOException
    {
        byte[] proc=source.read("eva/actual_crane_procedural_triangles_r52.json"),grip=source.read("mesh/tripo_gripper_r48.json");require(sha(proc).equals(proceduralSha)&&sha(grip).equals(gripperSha),"Actual whole crane source identity changed");
        var document=JsonParser.parseString(new String(proc,StandardCharsets.UTF_8)).getAsJsonObject();require(document.get("schema").getAsString().equals("projectseele.r52.actual-crane-procedural-triangles.v1"),"Actual crane bake schema required");var meshes=new HashMap<String,double[]>();
        for(var row:document.getAsJsonObject("parts").entrySet()){var array=row.getValue().getAsJsonArray();require(array.size()>0&&array.size()%9==0,"Complete actual procedural triangles required");double[] xyz=new double[array.size()];for(int i=0;i<xyz.length;i++){xyz[i]=array.get(i).getAsDouble();require(Double.isFinite(xyz[i]),"Nonfinite crane geometry");}meshes.put(row.getKey(),xyz);}
        require(meshes.keySet().equals(Set.of("top","yoke","sheave","wheel","links","rope"))&&meshes.values().stream().mapToInt(x->x.length/9).sum()==28044,"Actual complete six procedural parts required");
        var jaws=new HashMap<String,double[]>();var anchors=new HashMap<String,Vec3>();int stride=-1;
        try(var json=new JsonReader(new InputStreamReader(new ByteArrayInputStream(grip),StandardCharsets.UTF_8)))
        {json.beginObject();while(json.hasNext())switch(json.nextName())
        {case "stride"->stride=json.nextInt();case "anchors"->{json.beginObject();while(json.hasNext()){String name=json.nextName();json.beginArray();var point=new Vec3(json.nextDouble(),json.nextDouble(),json.nextDouble());json.endArray();require(Double.isFinite(point.lengthSqr()),"Actual clamp anchor required");require(anchors.putIfAbsent(name,point)==null,"Duplicate clamp anchor");}json.endObject();}
        case "parts"->{json.beginObject();while(json.hasNext()){String name=json.nextName();require(jaws.putIfAbsent(name,positions(json))==null,"Duplicate actual clamp part");}json.endObject();}default->json.skipValue();}json.endObject();}
        require(stride==8&&jaws.keySet().equals(Set.of("body","jaw_left","jaw_right"))&&anchors.keySet().containsAll(Set.of("mount","jaw_left","jaw_right")),"Actual imported clamp selection incomplete");
        return new NervCraneGeometryR52(meshes,jaws,anchors,sha((proceduralSha+":"+gripperSha).getBytes(StandardCharsets.UTF_8)));
    }
    public List<Part> parts(NervCranePoseR52.Pose pose)
    {
        var result=new ArrayList<Part>();var root=pose.machine();result.add(new Part("top",procedural.get("top"),root));
        for(double x:new double[]{-4,4})for(double z:new double[]{-2.8,2.8})result.add(new Part("wheel/"+x+"/"+z,procedural.get("wheel"),root.compose(RigidTransform.of(new Vec3(x,wheelBearingOffset(root.translation().z/.38),z),new Quaternionf().rotationX((float)(root.translation().z/.38))))));
        result.add(new Part("yoke",procedural.get("yoke"),root.compose(new RigidTransform(pose.yoke(),0,0,0,1))));
        for(double x:new double[]{-2.4,2.4})for(double z:new double[]{-.78,.78})
        {var end=pose.yoke().add(x,0,z);rope(result,"hoist/"+x+"/"+z,new Vec3(x,-.7,z),end,.065,root);result.add(new Part("sheave/"+x+"/"+z,procedural.get("sheave"),root.compose(new RigidTransform(end,0,0,0,1))));}
        rope(result,"mount/left",pose.yoke().add(-1.8,-.2,0),pose.mount().add(-.5,0,0),.10,root);rope(result,"mount/right",pose.yoke().add(1.8,-.2,0),pose.mount().add(.5,0,0),.10,root);
        var frame=root.compose(pose.grip());result.add(new Part("gripper/body",gripper.get("body"),frame));
        for(String side:List.of("left","right")){String key="jaw_"+side;Vec3 pivot=anchors.get(key);var rotation=new Quaternionf().rotationZ((float)Math.toRadians((side.equals("left")?-1:1)*32*pose.released()));var turn=RigidTransform.of(Vec3.ZERO,rotation);var about=new RigidTransform(pivot.subtract(turn.transformVector(pivot)),turn.qx(),turn.qy(),turn.qz(),turn.qw());result.add(new Part("gripper/"+key,gripper.get(key),frame.compose(about)));}
        return List.copyOf(result);
    }
    public record Transform(RigidTransform frame,Vec3 scale)
    {Vec3 point(Vec3 p){return frame.transformPoint(p.multiply(scale));}}
    double[] sourceFor(String name){return name.startsWith("wheel/")?procedural.get("wheel"):name.startsWith("sheave/")?procedural.get("sheave"):name.startsWith("hoist/")||name.startsWith("mount/")?procedural.get("rope"):name.startsWith("gripper/")?gripper.get(name.substring(8)):procedural.get(name);}
    /** Same finite source meshes; only the actual cylinder's axial scale changes. */
    Map<String,Transform> transforms(NervCranePoseR52.Pose pose)
    {
        var out=new LinkedHashMap<String,Transform>();var root=pose.machine();var one=new Vec3(1,1,1);
        out.put("top",new Transform(root,one));
        for(double x:new double[]{-4,4})for(double z:new double[]{-2.8,2.8})out.put("wheel/"+x+"/"+z,new Transform(root.compose(RigidTransform.of(new Vec3(x,wheelBearingOffset(root.translation().z/.38),z),new Quaternionf().rotationX((float)(root.translation().z/.38)))),one));
        out.put("yoke",new Transform(root.compose(new RigidTransform(pose.yoke(),0,0,0,1)),one));
        for(double x:new double[]{-2.4,2.4})for(double z:new double[]{-.78,.78})
        {var end=pose.yoke().add(x,0,z);ropeTransform(out,"hoist/"+x+"/"+z,new Vec3(x,-.7,z),end,.065,root);out.put("sheave/"+x+"/"+z,new Transform(root.compose(new RigidTransform(end,0,0,0,1)),one));}
        ropeTransform(out,"mount/left",pose.yoke().add(-1.8,-.2,0),pose.mount().add(-.5,0,0),.10,root);ropeTransform(out,"mount/right",pose.yoke().add(1.8,-.2,0),pose.mount().add(.5,0,0),.10,root);
        var frame=root.compose(pose.grip());out.put("gripper/body",new Transform(frame,one));
        for(String side:List.of("left","right")){String key="jaw_"+side;Vec3 pivot=anchors.get(key);var rotation=new Quaternionf().rotationZ((float)Math.toRadians((side.equals("left")?-1:1)*32*pose.released()));var turn=RigidTransform.of(Vec3.ZERO,rotation);var about=new RigidTransform(pivot.subtract(turn.transformVector(pivot)),turn.qx(),turn.qy(),turn.qz(),turn.qw());out.put("gripper/"+key,new Transform(frame.compose(about),one));}
        return Map.copyOf(out);
    }
    private static void ropeTransform(Map<String,Transform> out,String name,Vec3 first,Vec3 last,double radius,RigidTransform root)
    {var d=last.subtract(first);double length=d.length();if(length<1e-6)throw new IllegalArgumentException("Actual full rope cannot vanish");out.put(name,new Transform(root.compose(NervCranePoseR52.originalHoistRopeFrameR63(first,last)),new Vec3((float)radius,(float)length,(float)radius)));}
    private void rope(List<Part> out,String name,Vec3 first,Vec3 last,double radius,RigidTransform root)
    {var delta=last.subtract(first);double length=delta.length();if(length<1e-6)return;double[] source=procedural.get("rope"),xyz=source.clone();for(int i=0;i<xyz.length;i+=3){xyz[i]*=(float)radius;xyz[i+1]*=(float)length;xyz[i+2]*=(float)radius;}out.add(new Part(name,xyz,root.compose(NervCranePoseR52.originalHoistRopeFrameR63(first,last))));}
    private static double[] positions(JsonReader json)throws IOException
    {var chunks=new ArrayList<float[]>();int count=0;json.beginArray();while(json.hasNext()){float f=Float.parseFloat(json.nextString());require(Float.isFinite(f),"Nonfinite actual clamp vertex");if(count%8192==0)chunks.add(new float[8192]);chunks.get(count/8192)[count%8192]=f;count++;}json.endArray();require(count>0&&count%24==0,"Actual clamp stride8 triangles required");var xyz=new double[count/8*3];for(int v=0;v<count/8;v++)for(int a=0;a<3;a++){int at=v*8+a;xyz[v*3+a]=chunks.get(at/8192)[at%8192];}return xyz;}
    private static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception impossible){throw new IllegalStateException(impossible);}}
    private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
}
