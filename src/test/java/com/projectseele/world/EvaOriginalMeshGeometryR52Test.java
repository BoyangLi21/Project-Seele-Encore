package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.util.QuaternionChannelsR45;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.PackResources;
import net.minecraft.server.packs.resources.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;

/** Actual selected asset vertices compared with existing production renderer
 * getMesh/skinVertices/EvaRigTransforms. No replacement test skin model. */
public final class EvaOriginalMeshGeometryR52Test
{
    private static int checks,vertices;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static void rejects(Runnable action,String why){boolean failed=false;try{action.run();}catch(RuntimeException expected){failed=true;}check(failed,why);}
    private static JsonObject json(Path file)throws Exception{return JsonParser.parseString(Files.readString(file)).getAsJsonObject();}
    private static Object call(Object target,String name)throws Exception{var method=target.getClass().getDeclaredMethod(name);method.setAccessible(true);return method.invoke(target);}
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static EvaBodyPose.Sample body(JsonObject data,int variant)
    {
        var bones=new LinkedHashMap<String,EvaBodyPose.Bone>();for(var value:data.getAsJsonObject("rigs").getAsJsonArray(Integer.toString(variant)))
        {var b=value.getAsJsonObject();var e=b.has("rotation")?vector(b.getAsJsonArray("rotation")):b.has("bindRotationDegrees")?vector(b.getAsJsonArray("bindRotationDegrees")):new Vector3f();e.mul((float)Math.PI/180);String n=b.get("name").getAsString();bones.put(n,new EvaBodyPose.Bone(n,b.has("parent")?b.get("parent").getAsString():null,vector(b.getAsJsonArray("pivot")).mul(-1,1,1).div(16),new Quaternionf().rotationZYX(e.z,-e.y,-e.x)));}
        var pose=new EvaBodyPose.Sample(Map.copyOf(bones));for(var b:bones.values())pose.rotations.put(b.name(),new Quaternionf(b.bindRotation()));pose.dirty();return pose;
    }
    private static Map<String,GeoBone> renderedBones(JsonObject geo,EvaBodyPose.Sample body,EvaAnatomicalHandsR45.Pose hands)
    {
        var specs=new LinkedHashMap<String,JsonObject>();for(var row:geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones"))specs.put(row.getAsJsonObject().get("name").getAsString(),row.getAsJsonObject());
        var bones=new HashMap<String,GeoBone>();while(bones.size()<specs.size())
        {
            int before=bones.size();for(var entry:specs.entrySet())
            {
                String n=entry.getKey();if(bones.containsKey(n))continue;var spec=entry.getValue();String parent=spec.has("parent")?spec.get("parent").getAsString():null;if(parent!=null&&!bones.containsKey(parent))continue;
                var bone=new GeoBone(parent==null?null:bones.get(parent),n,false,0D,false,false);if(parent!=null)bones.get(parent).getChildBones().add(bone);
                var pivot=body.rig.containsKey(n)?new Vector3f(body.rig.get(n).pivot()).mul(16):vector(spec.getAsJsonArray("pivot")).mul(-1,1,1);bone.setPivotX(pivot.x);bone.setPivotY(pivot.y);bone.setPivotZ(pivot.z);
                var e=spec.has("rotation")?vector(spec.getAsJsonArray("rotation")).mul((float)Math.PI/180):new Vector3f();var q=body.rotations.getOrDefault(n,hands.rotations().getOrDefault(n,new Quaternionf().rotationZYX(e.z,-e.y,-e.x)));
                var actual=QuaternionChannelsR45.euler(q);bone.setRotX(actual.x);bone.setRotY(actual.y);bone.setRotZ(actual.z);var p=body.positions.getOrDefault(n,new Vector3f());bone.setPosX(-p.x*16);bone.setPosY(p.y*16);bone.setPosZ(p.z*16);bone.setScaleX(1);bone.setScaleY(1);bone.setScaleZ(1);bones.put(n,bone);
            }
            check(bones.size()>before,"Actual GEO parent graph could not be constructed");
        }
        return bones;
    }
    private static ResourceManager manager(Path assets)
    {
        var pack=(PackResources)Proxy.newProxyInstance(EvaOriginalMeshGeometryR52Test.class.getClassLoader(),new Class<?>[]{PackResources.class},(p,m,args)->m.getName().equals("packId")?"actual-selected-r51":m.getName().equals("isBuiltin")?false:null);
        return (ResourceManager)Proxy.newProxyInstance(EvaOriginalMeshGeometryR52Test.class.getClassLoader(),new Class<?>[]{ResourceManager.class},(p,m,args)->{
            if(m.getName().equals("getResource")){var key=(ResourceLocation)args[0];Path path=assets.resolve(key.getPath());return Files.isRegularFile(path)?Optional.of(new Resource(pack,()->Files.newInputStream(path))):Optional.empty();}
            if(m.getName().equals("getNamespaces"))return Set.of("projectseele");throw new UnsupportedOperationException(m.getName());});
    }
    public static void main(String[] args)throws Exception
    {
        Path assets=Path.of(args[0]),bodyFile=Path.of(args[1]),receiptFile=Path.of(args[2]);var receipt=json(receiptFile);var hashes=new HashMap<String,String>();for(var row:receipt.getAsJsonArray("files")){var r=row.getAsJsonObject();hashes.put(r.get("resource").getAsString(),r.get("sha256").getAsString());}
        var provider=EvaOriginalMeshGeometryR52.load(assets,hashes);var classpath=EvaOriginalMeshGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,hashes);
        check(classpath.sourceFingerprint().equals(provider.sourceFingerprint()),"JAR and actual selected asset hashes differ");
        var bodyData=json(bodyFile);var resourceManager=manager(assets);
        var factoryGate=provider.getClass().getDeclaredMethod("validateBody",int.class,EvaBodyPose.Sample.class,boolean.class);factoryGate.setAccessible(true);
        var layer=Class.forName("com.projectseele.client.render.LocalTriangleMeshLayer");var load=layer.getDeclaredMethod("getMesh",ResourceManager.class,ResourceLocation.class);load.setAccessible(true);
        var rigTransforms=Class.forName("com.projectseele.client.render.EvaRigTransforms");var model=rigTransforms.getDeclaredMethod("model",GeoBone.class);model.setAccessible(true);
        var results=new JsonArray();
        for(int variant=0;variant<3;variant++)
        {
            String stem="eva_unit0"+variant;var geo=json(assets.resolve("geo/"+stem+".geo.json"));var handRaw=json(assets.resolve("mesh/"+stem+"_anatomical_hands_r45.mesh.json"));var handRotations=new HashMap<String,Quaternionf>();
            for(var raw:geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones")){var row=raw.getAsJsonObject();String n=row.get("name").getAsString();if(!provider.handJoints(variant).contains(n))continue;var e=vector(row.getAsJsonArray("rotation")).mul((float)Math.PI/180);handRotations.put(n,new Quaternionf().rotationZYX(e.z,-e.y,-e.x));}
            check(handRotations.size()==34,"Actual hand source did not provide all 34 frozen joints");
            factoryGate.invoke(provider,variant,body(bodyData,variant),true);check(true,"Actual factory source was rejected");
            var bentFactory=body(bodyData,variant);bentFactory.rotations.put("forearm_l",new Quaternionf().rotationX(.4F));bentFactory.dirty();boolean rejected=false;try{factoryGate.invoke(provider,variant,bentFactory,true);}catch(InvocationTargetException expected){rejected=true;}check(rejected,"Articulated body was silently commissioned as exact factory pose");
            final int selected=variant;rejects(()->provider.evaluate(selected,body(bodyData,(selected+1)%3),new EvaAnatomicalHandsR45.Pose("source","source",Map.copyOf(handRotations))),"Another rig's body pivot/source was accepted");
            Object bodyMesh=load.invoke(null,resourceManager,new ResourceLocation("projectseele","mesh/"+stem+".mesh.json")),handMesh=load.invoke(null,resourceManager,new ResourceLocation("projectseele","mesh/"+stem+"_anatomical_hands_r45.mesh.json"));check(bodyMesh!=null&&handMesh!=null,"Existing production renderer rejected actual selected meshes");
            Method skin=null;for(var method:layer.getDeclaredMethods())if(method.getName().equals("skinVertices")&&method.getParameterCount()==3){skin=method;skin.setAccessible(true);}check(skin!=null,"Actual production skin evaluator missing");
            for(int scenario=0;scenario<4;scenario++)
            {
                var body=body(bodyData,variant);var rotations=new HashMap<String,Quaternionf>();handRotations.forEach((n,q)->rotations.put(n,new Quaternionf(q)));
                if(scenario==1){body.rotations.put("forearm_l",new Quaternionf().rotationXYZ(.8F,-.23F,.16F));body.rotations.put("wrist_l",new Quaternionf().rotationXYZ(.3F,.2F,-.4F));body.rotations.put("arm_r",new Quaternionf().rotationXYZ(-.3F,.5F,.4F));body.dirty();}
                if(scenario==3){body.rotations.put("root",new Quaternionf().rotationX((float)Math.PI/2));body.rotations.put("shin_l",new Quaternionf().rotationX(.23F));body.dirty();}
                if(scenario==2)for(var value:handRaw.getAsJsonObject("jointSkins").entrySet())for(var row:value.getValue().getAsJsonObject().getAsJsonObject("contactCorrectiveR45").getAsJsonObject("local_quaternion_xyzw").entrySet()){var q=row.getValue().getAsJsonArray();rotations.put(row.getKey(),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()).normalize());}
                var hands=new EvaAnatomicalHandsR45.Pose("actual_source","actual_source",Map.copyOf(rotations));var snapshot=EvaFrozenHandsR52.encode(variant,provider.handContractFingerprint(variant),hands);var roundtrip=EvaFrozenHandsR52.decode(variant,provider.handContractFingerprint(variant),provider.handJoints(variant),snapshot);check(roundtrip.rotations().size()==34,"Shared hand snapshot did not preserve complete source");
                var geometry=provider.evaluate(variant,body,roundtrip);check(geometry.parts().stream().anyMatch(p->p.bone().equals("arm_l"))&&geometry.parts().stream().anyMatch(p->p.bone().equals("forearm_r"))&&geometry.parts().stream().filter(p->p.bone().startsWith("hand_")).mapToInt(EvaOriginalMeshGeometryR52.Part::triangleCount).sum()==27104,"Full actual arms/hands geometry was omitted");
                var bones=renderedBones(geo,body,roundtrip);double maximum=0,handMaximum=0;int compared=0;
                for(var part:geometry.parts())
                {
                    Object mesh=part.resource().contains("anatomical")?handMesh:bodyMesh;var rawParts=(Map<?,?>)call(mesh,"parts");Object rawPart=rawParts.get(part.bone());check(rawPart!=null,"Provider selected a part absent from production renderer");
                    float[] values=(float[])skin.invoke(null,mesh,rawPart,bones.get(part.bone()));float x=(float)call(rawPart,"pivotX"),y=(float)call(rawPart,"pivotY"),z=(float)call(rawPart,"pivotZ");Matrix4f matrix=(Matrix4f)model.invoke(null,bones.get(part.bone()));double[] actual=part.triangles();check(actual.length==values.length/8*3,"Provider changed actual source topology/count");
                    for(int i=0,n=0;i<values.length;i+=8,n+=3)
                    {
                        var expected=matrix.transformPosition(new Vector3f(-(values[i]+x)/16,(values[i+1]+y)/16,(values[i+2]+z)/16)).mul(EvaScale.RENDER_SCALE);double error=Math.sqrt(Math.pow(actual[n]-expected.x,2)+Math.pow(actual[n+1]-expected.y,2)+Math.pow(actual[n+2]-expected.z,2));maximum=Math.max(maximum,error);if(part.bone().startsWith("hand_"))handMaximum=Math.max(handMaximum,error);vertices++;compared++;
                        check(error<=.0001,"Actual renderer/provider vertex mismatch unit="+variant+" scenario="+scenario+" part="+part.bone()+" vertex="+(i/8)+" error="+error);
                    }
                }
                var result=new JsonObject();result.addProperty("variant",variant);result.addProperty("scenario",scenario==0?"factory_bind":scenario==1?"articulated_comparison_only":scenario==2?"actual_corrective_targets":"frozen_fallen_comparison");result.addProperty("parts",geometry.parts().size());result.addProperty("triangles",geometry.triangleCount());result.addProperty("compared_vertices",compared);result.addProperty("max_render_provider_error_metres",maximum);result.addProperty("max_hand_error_metres",handMaximum);results.add(result);System.out.println(result);
                var damaged=snapshot.copy();damaged.getCompound("Bones").remove(provider.handJoints(variant).iterator().next());final int v=variant;rejects(()->EvaFrozenHandsR52.decode(v,provider.handContractFingerprint(v),provider.handJoints(v),damaged),"Partial anatomical snapshot was admitted");
                var foreign=snapshot.copy();foreign.putString("ContractSHA256","a".repeat(64));rejects(()->EvaFrozenHandsR52.decode(v,provider.handContractFingerprint(v),provider.handJoints(v),foreign),"Foreign hand source silently matched frozen pose");
            }
        }
        var result=new JsonObject();result.addProperty("checks",checks);result.addProperty("actual_vertices_compared",vertices);result.add("scenarios",results);result.addProperty("native_world_acceptance",false);Files.writeString(Path.of(args[3]),result.toString()+"\n");System.out.println("R52 actual renderer/full-mesh provider PASS checks="+checks+" vertices="+vertices+"; no gameplay/native world acceptance");
    }
    private EvaOriginalMeshGeometryR52Test(){}
}
