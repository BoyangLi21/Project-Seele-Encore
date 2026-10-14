package com.projectseele.world;
import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.projectseele.entity.*;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** Actual selected R44 cage's authored finite collision members and original
 * release clocks. Root supplies its rigid world frame, never a new layout. */
public final class NervPlantMotionR52
{
    private record Component(String part,int variant,String motion,Vec3 normal,double outboard,Vec3 translation,float from,float to,List<AABB> boxes){}
    private static List<Component> components;private static String installedSha;private static Map<String,NervRigidMeshSweepR52> renderMeshes;
    private static NervRigidMeshSweepR52 fixedColumnsR52;
    private static double[] lowerColumnVerticesR52(JsonReader reader)throws IOException
    {
        double[] result=null;reader.beginObject();while(reader.hasNext())
        {if(!reader.nextName().equals("cage_frame_lower_r44")){reader.skipValue();continue;}var xyz=new double[16384];int count=0,index=0;reader.beginArray();while(reader.hasNext())
            {if(index++%6<3){if(count==xyz.length)xyz=Arrays.copyOf(xyz,xyz.length*2);xyz[count++]=Float.parseFloat(reader.nextString());}else reader.skipValue();}
            reader.endArray();if(index%18!=0)throw new IllegalStateException("Complete actual column triangles required");result=Arrays.copyOf(xyz,count);}
        reader.endObject();return result;
    }
    private static List<double[]> lowerColumnLastBoxesR52(JsonReader reader)throws IOException
    {
        List<double[]> result=null;reader.beginObject();while(reader.hasNext())
        {if(!reader.nextName().equals("cage_frame_lower_r44")){reader.skipValue();continue;}var last=new ArrayDeque<double[]>();reader.beginArray();while(reader.hasNext())
            {var box=new double[6];reader.beginArray();for(int corner=0;corner<2;corner++){reader.beginArray();for(int axis=0;axis<3;axis++)box[corner*3+axis]=reader.nextDouble();reader.endArray();}reader.endArray();if(last.size()==3)last.removeFirst();last.addLast(box);}
            reader.endArray();result=List.copyOf(last);}
        reader.endObject();return result;
    }
    /** Actual original rendered column triangles at the declared gantry frame.
     * The three below-floor crossbars are the only excluded members; no
     * native controller AABB substitutes for the complete fixed columns. */
    public static synchronized NervRigidMeshSweepR52 originalFixedColumnsR52()throws IOException
    {
        if(fixedColumnsR52!=null)return fixedColumnsR52;
        double[] values=null;List<double[]> boxes=null;int stride=-1;String frame=null;
        try(var input=EvaOriginalMeshGeometryR52.class.getResourceAsStream("/assets/projectseele/mesh/tv_shoulder_shells_r44.json"))
        {if(input==null)throw new IOException("Actual rendered classpath asset absent: mesh/tv_shoulder_shells_r44.json");try(var reader=new JsonReader(new InputStreamReader(input,StandardCharsets.UTF_8)))
            {reader.setLenient(true);reader.beginObject();while(reader.hasNext())switch(reader.nextName())
                {case "stride"->stride=reader.nextInt();case "frame"->frame=reader.nextString();case "parts"->values=lowerColumnVerticesR52(reader);case "collision_parts"->boxes=lowerColumnLastBoxesR52(reader);default->reader.skipValue();}
                reader.endObject();if(reader.peek()!=JsonToken.END_DOCUMENT)throw new IllegalStateException("Complete actual gantry JSON required");}}
        if(stride!=6||!"fixed_gantry_local_metres_world_axes".equals(frame))throw new IllegalStateException("Actual original gantry frame source changed");
        if(values==null||boxes==null||boxes.size()!=3)throw new IllegalStateException("Actual original lower column source and three crossbars required");var points=new double[values.length];int count=0;
        for(int i=0;i<values.length;i+=9){boolean lowerBar=false;double top=Math.max(values[i+1],Math.max(values[i+4],values[i+7]));if(top<=-.61999)for(var box:boxes){boolean inside=true;for(int c=0;c<9;c+=3)for(int axis=0;axis<3;axis++){double p=values[i+c+axis];inside&=p>=box[axis]-1e-5&&p<=box[axis+3]+1e-5;}lowerBar|=inside;}if(!lowerBar){System.arraycopy(values,i,points,count,9);count+=9;}}
        if(count/9!=4912)throw new IllegalStateException("Complete actual columns including all eight bottom triangles required");fixedColumnsR52=new NervRigidMeshSweepR52(Arrays.copyOf(points,count));return fixedColumnsR52;
    }
    public static synchronized void install(String expected)throws IOException
    {
        if(expected.equals(installedSha)&&components!=null)return;byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes("mesh/tv_shoulder_shells_r44.json");String sha;try{sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception e){throw new IllegalStateException(e);}if(!sha.equals(expected))throw new IllegalStateException("Actual cage selection changed");
        var root=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(!root.get("frame").getAsString().equals("fixed_gantry_local_metres_world_axes"))throw new IllegalStateException("Actual cage basis changed");var rows=new ArrayList<Component>();
        for(var value:root.getAsJsonArray("components")){var c=value.getAsJsonObject();String part=c.get("part").getAsString(),motion=c.get("motion").getAsString();if(part.startsWith("thin_side_rails"))continue;var boxes=new ArrayList<AABB>();for(var b:root.getAsJsonObject("collision_parts").getAsJsonArray(part)){var pair=b.getAsJsonArray();var lo=point(pair.get(0).getAsJsonArray());var hi=point(pair.get(1).getAsJsonArray());if(!(lo.x<hi.x&&lo.y<hi.y&&lo.z<hi.z))throw new IllegalStateException("Actual positive machinery volume required");boxes.add(new AABB(lo,hi));}
        Vec3 normal=Vec3.ZERO,translation=Vec3.ZERO;double outboard=0;float a=0,b=1;if(motion.equals("translation_only_with_exact_facet_pad")){normal=point(c.getAsJsonArray("normal"));outboard=c.get("outboard_m").getAsDouble();if(Math.abs(normal.length()-1)>.0001||Math.abs(Math.abs(outboard)-5.35)>.0001||c.get("normal_lift_m").getAsDouble()!=2.1)throw new IllegalStateException("Original facet release mismatch");}else if(motion.equals("telescoping_translation")){translation=point(c.getAsJsonArray("translation_open_local"));a=c.getAsJsonArray("opening_interval").get(0).getAsFloat();b=c.getAsJsonArray("opening_interval").get(1).getAsFloat();if(a<0||b>1||a>=b)throw new IllegalStateException("Actual release interval required");}else if(!motion.equals("fixed"))throw new IllegalStateException("Unknown original mechanism");rows.add(new Component(part,c.has("variant")?c.get("variant").getAsInt():-1,motion,normal,outboard,translation,a,b,List.copyOf(boxes)));}
        if(rows.isEmpty())throw new IllegalStateException("Actual complete cage absent");var meshes=new HashMap<String,NervRigidMeshSweepR52>();for(var c:rows){var values=root.getAsJsonObject("parts").getAsJsonArray(c.part);double[] xyz=new double[values.size()/2];for(int i=0,n=0;i<values.size();i+=6){xyz[n++]=values.get(i).getAsFloat();xyz[n++]=values.get(i+1).getAsFloat();xyz[n++]=values.get(i+2).getAsFloat();}meshes.put(c.part,new NervRigidMeshSweepR52(xyz));}renderMeshes=Map.copyOf(meshes);components=List.copyOf(rows);installedSha=expected;COLLISION_BOXES_R58.clear();
    }
    private static Vec3 point(JsonArray a){if(a.size()!=3)throw new IllegalStateException("Actual finite vector required");var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());if(!Double.isFinite(p.lengthSqr()))throw new IllegalStateException("Nonfinite actual mechanism");return p;}
    private static float ramp(float p,float a,float b){return EvaDorsalMechanism.smooth((p-a)/(b-a));}
    private static Vec3 move(Component c,float closed){float o=1-closed;return c.motion.equals("translation_only_with_exact_facet_pad")?c.normal.scale(2.1*ramp(o,0,.25F)).add(c.outboard*ramp(o,.23F,.88F),0,0):c.motion.equals("telescoping_translation")?c.translation.scale(ramp(o,c.from,c.to)):Vec3.ZERO;}
    private static JsonObject cageReceiptR52;
    private static JsonObject cageReceiptR52()
    {if(cageReceiptR52==null)try{cageReceiptR52=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/cage_collision_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject();}catch(IOException missing){throw new IllegalStateException("Actual cage source receipt absent",missing);}return cageReceiptR52;}
    static double cageCollisionRadiusR57()
    {double radius=cageReceiptR52().get("broadphase_radius_m").getAsDouble();if(!Double.isFinite(radius)||radius<=0)throw new IllegalStateException("Source-derived inventory radius required");return radius;}
    /** Client prediction uses the same declared source and synchronized machine
     * frame; it never queries the retired absolute R44 bay positions. */
    public static List<net.minecraft.world.phys.shapes.VoxelShape> declaredClientCollisions(net.minecraft.world.level.Level l,Entity actor,AABB query,List<net.minecraft.world.phys.shapes.VoxelShape> original)
    {
        if(!l.isClientSide||actor instanceof EvaUnit01Entity||actor instanceof NervCarrierPlatformEntity)return original;
        var receipt=cageReceiptR52();double radius=receipt.get("broadphase_radius_m").getAsDouble();if(!Double.isFinite(radius)||radius<=0)throw new IllegalStateException("Source-derived inventory radius required");var machines=l.getEntitiesOfClass(NervCarrierPlatformEntity.class,query.inflate(radius),e->e.isRestraintGantry()&&e.hasDeclaredMachineFrameR52()&&!e.declaredCollisionSourceR52().isEmpty());
        if(machines.isEmpty())return original;var result=new ArrayList<>(original);
        for(var machine:machines){try{install(machine.declaredCollisionSourceR52());}catch(IOException|IllegalStateException missing){return original;}var frame=RigidTransform.of(machine.position(),machine.declaredMachineRotationR52());result.addAll(actualCollisionMembers(machine.getUnitVariant(),frame,machine.getRestraintProgress(),machine.lowerFrameProgressR52(1),query));try{result.addAll(NervServiceFootDriveR52.collisions(machine,1,query));}catch(IOException missing){throw new IllegalStateException("Declared service drive source unavailable",missing);}}return result;
    }
    public static List<net.minecraft.world.phys.shapes.VoxelShape> actualCollisionMembers(int variant,RigidTransform frame,float closed,AABB query){return actualCollisionMembers(variant,frame,closed,Float.NaN,query);}
    private record CollisionPoseR58(String source,int variant,RigidTransform frame,int closedBits,int lowerBits){}
    private static final Map<CollisionPoseR58,List<AABB>> COLLISION_BOXES_R58=new LinkedHashMap<>();
    /** Immutable world boxes retain the exact original source pose and member order on both sides. */
    static synchronized List<AABB> collisionBoxesR58(int variant,RigidTransform frame,float closed,float lower)
    {
        if(components==null)return List.of();var key=new CollisionPoseR58(installedSha,variant,frame,Float.floatToRawIntBits(closed),Float.floatToRawIntBits(lower));var cached=COLLISION_BOXES_R58.get(key);if(cached!=null)return cached;
        var result=new ArrayList<AABB>();for(var c:components){if(c.variant>=0&&c.variant!=variant)continue;var movement=move(c,closed);for(var box:c.boxes){if(Float.isFinite(lower)&&c.part.equals("cage_frame_lower_r44")&&box.maxY<=-.61999)continue;var world=NervRigidMeshSweepR52.transformed(box.move(movement),frame);result.add(world);}}if(Float.isFinite(lower))try{result.addAll(NervLowerFrameR52.collisionBoxesR57(frame,lower));}catch(IOException failure){throw new IllegalStateException("Actual lower-frame source unavailable",failure);}var boxes=List.copyOf(result);if(COLLISION_BOXES_R58.size()>=8)COLLISION_BOXES_R58.remove(COLLISION_BOXES_R58.keySet().iterator().next());COLLISION_BOXES_R58.put(key,boxes);return boxes;
    }
    public static List<net.minecraft.world.phys.shapes.VoxelShape> actualCollisionMembers(int variant,RigidTransform frame,float closed,float lower,AABB query)
    {if(components==null)return List.of();var result=new ArrayList<net.minecraft.world.phys.shapes.VoxelShape>();for(var world:collisionBoxesR58(variant,frame,closed,lower))if(world.intersects(query))result.add(net.minecraft.world.phys.shapes.Shapes.create(world));return List.copyOf(result);}
    public static List<NervFlightProofR52.ObstacleMesh> actualRenderedMeshesR52(NervCarrierPlatformEntity machine)throws IOException {var result=new ArrayList<>(actualStructuralMeshesR52(machine));result.addAll(NervServiceFootDriveR52.actualMeshes(machine));if(NervMappedPlugMechanicsR52.selectedMachinery().selectedRunningDeckR52()&&machine.declaredServiceFootDriveR52()!=null){var lead=NervOriginalCarrierR52.actualLeadSampleR52(machine,1);if(lead==null)throw new IllegalStateException("Declared bay lead source clock unavailable");for(var p:NervLegacyCarrierRideR52.actualLeadPartsR52(lead))result.add(new NervFlightProofR52.ObstacleMesh(p.mesh(),p.frame()));}return List.copyOf(result);}
    public static List<NervFlightProofR52.ObstacleMesh> actualStructuralMeshesR52(NervCarrierPlatformEntity machine)throws IOException
    {install(machine.declaredCollisionSourceR52());var frame=RigidTransform.of(machine.position(),machine.declaredMachineRotationR52());var result=new ArrayList<NervFlightProofR52.ObstacleMesh>();if(machine.lowerFrameDeclaredR52())result.addAll(NervLowerFrameR52.actualMeshes(machine));else result.add(new NervFlightProofR52.ObstacleMesh(renderMeshes.get("cage_frame_lower_r44"),frame));for(var c:components){if(c.part.equals("cage_frame_lower_r44")||c.variant>=0&&c.variant!=machine.getUnitVariant())continue;result.add(new NervFlightProofR52.ObstacleMesh(renderMeshes.get(c.part),frame.compose(new RigidTransform(move(c,machine.getRestraintProgress()),0,0,0,1))));}result.addAll(NervShoulderBearingR52.actualMeshes(machine.getUnitVariant(),frame,machine.getRestraintProgress()));return List.copyOf(result);}
    public static boolean clearRestraints(ServerLevel l,int variant,RigidTransform root,float before,float after,Set<UUID> own)
    {
        if(components==null||!Float.isFinite(before+after)||before<0||after<0||before>1||after>1)return false;
        for(var c:components){if(c.motion.equals("fixed")||c.variant>=0&&c.variant!=variant)continue;var a=move(c,before);var b=move(c,after);for(var box:c.boxes){var local=box.move(a).minmax(box.move(b));var swept=NervRigidMeshSweepR52.transformed(local,root);if(!EntryPlugEjectionR48.loaded(l,swept))return false;for(var shape:l.getBlockCollisions((Entity)null,swept))for(var obstacle:shape.toAabbs())if(swept.intersects(obstacle))return false;for(var e:l.getEntities((Entity)null,swept,e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith())))if(swept.intersects(e.getBoundingBox()))return false;}}
        return true;
    }
    /** Original bridge segments change as complete owned voxel members.
     * Both removal and extension stop for a real outside occupant; extension
     * placement additionally goes through exact native collision checks. */
    public static boolean clearBridgeStep(ServerLevel l,List<NervAssemblyOwnerR52.Cell> cells,Set<UUID> own)
    {for(var c:cells){if(!l.hasChunkAt(c.at()))return false;var at=new AABB(c.at()).expandTowards(0,2,0);if(!l.getEntities((Entity)null,at,e->!own.contains(e.getUUID())&&e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith())).isEmpty())return false;}return true;}
    private NervPlantMotionR52(){}
}
