package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonReader;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import java.lang.reflect.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import org.joml.Vector3f;

/** Actual carrier source versus production rigid loader/PoseStack, plus actual
 * capsule loader vertices. No substitute asset, world or native actor creation. */
public final class FullAssemblyGeometryR52Test
{
    private static int checks,vertices;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static Object call(Object target,String name)throws Exception{var m=target.getClass().getDeclaredMethod(name);m.setAccessible(true);return m.invoke(target);}
    private static void openHatchChecks(FullAssemblyGeometryR52.Provider provider,int variant,Map<?,?> raw)throws Exception
    {
        var geo=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("geo/entry_plug_carrier.geo.json"),StandardCharsets.UTF_8)).getAsJsonObject();
        var model=Class.forName("com.projectseele.client.render.EvaRigTransforms").getDeclaredMethod("model",software.bernie.geckolib.cache.object.GeoBone.class);model.setAccessible(true);
        var geometry=provider.closedPlugParts(variant);
        for(var value:geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones"))
        {
            var spec=value.getAsJsonObject();String name=spec.get("name").getAsString();if(!geometry.containsKey(name))continue;
            var bone=new software.bernie.geckolib.cache.object.GeoBone(null,name,false,0D,false,false);var pivot=spec.getAsJsonArray("pivot");
            bone.setPivotX(-pivot.get(0).getAsFloat());bone.setPivotY(pivot.get(1).getAsFloat());bone.setPivotZ(pivot.get(2).getAsFloat());
            Object part=raw.get(name);float[] source=(float[])call(part,"vertices");float x=(float)call(part,"pivotX"),y=(float)call(part,"pivotY"),z=(float)call(part,"pivotZ");
            for(float opening:new float[]{0,.37F,1})
            {
                float sign=name.equals("plug_hatch_l")?1:name.equals("plug_hatch_r")?-1:0;
                bone.setRotZ((float)Math.toRadians(com.projectseele.world.EntryPlugKinematics.HATCH_OPEN_ANGLE_DEGREES*opening*sign));
                var matrix=(org.joml.Matrix4f)model.invoke(null,bone);var frame=provider.plugPartFrameR53(name,opening);var points=geometry.get(name);
                for(int at=0,n=0;at<source.length;at+=8,n+=3)
                {
                    var expected=matrix.transformPosition(new Vector3f(-(source[at]+x)/16,(source[at+1]+y)/16,(source[at+2]+z)/16)).mul(3.2F);
                    var actual=frame.transformPoint(new net.minecraft.world.phys.Vec3(points[n],points[n+1],points[n+2]));
                    check(actual.distanceTo(new net.minecraft.world.phys.Vec3(expected.x,expected.y,expected.z))<.0001,"Actual open capsule renderer mismatch: "+variant+" "+name+" "+opening);vertices++;
                }
            }
        }
    }
    public static void main(String[] args)throws Exception
    {
        var receipt=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonArray("files").forEach(v->hashes.put(v.getAsJsonObject().get("resource").getAsString(),v.getAsJsonObject().get("sha256").getAsString()));var provider=FullAssemblyGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,hashes);
        var renderer=Class.forName("com.projectseele.client.render.RigidMachineryPartR44");var read=renderer.getDeclaredMethod("readTextured",JsonReader.class);read.setAccessible(true);var encoded=renderer.getDeclaredField("vertices");encoded.setAccessible(true);var carrier=new HashMap<String,float[]>();double[] hinge=null;
        try(var json=new JsonReader(new InputStreamReader(new ByteArrayInputStream(EvaOriginalMeshGeometryR52.classpathBytes("mesh/tripo_carrier_r48.json")),StandardCharsets.UTF_8)))
        {
            json.beginObject();while(json.hasNext())switch(json.nextName())
            {case "parts"->{json.beginObject();while(json.hasNext()){String name=json.nextName();carrier.put(name,(float[])encoded.get(read.invoke(null,json)));}json.endObject();}case "anchors"->{json.beginObject();while(json.hasNext()){String name=json.nextName();if(name.equals("service_platform")){json.beginArray();hinge=new double[]{json.nextDouble(),json.nextDouble(),json.nextDouble()};json.endArray();}else json.skipValue();}json.endObject();}default->json.skipValue();}json.endObject();
        }
        check(carrier.size()==4&&hinge!=null,"Actual production carrier assembly/hinge missing");var results=new JsonArray();
        for(float[] state:new float[][]{{1,0,0},{.35F,1,.45F},{0,1,0}})
        {
            var actual=provider.carrierParts(state[0],state[1]>0,state[2]);double maximum=0;int triangles=0;
            for(var part:carrier.entrySet())
            {
                var pose=new PoseStack();String name=part.getKey();if(name.equals("deck")){if(state[1]>0)pose.translate(0,-3*(1-state[0]),0);}else{pose.translate(0,-64*(1-state[0]),0);if(name.equals("contact_pads"))pose.translate(0,0,1.5F*state[2]);if(name.equals("service_platform")){pose.translate(hinge[0],hinge[1],hinge[2]);pose.mulPose(Axis.ZP.rotationDegrees(-90));pose.translate(-hinge[0],-hinge[1],-hinge[2]);}}
                float[] source=part.getValue();double[] points=actual.get(name);check(points.length==source.length/44*9,"Original carrier topology changed");triangles+=points.length/9;
                for(int face=0,n=0;face<source.length;face+=44)for(int corner=0;corner<3;corner++,n+=3)
                {int at=face+corner*11;var p=pose.last().pose().transformPosition(new Vector3f(source[at],source[at+1],source[at+2]));double error=Math.sqrt(Math.pow(points[n]-p.x,2)+Math.pow(points[n+1]-p.y,2)+Math.pow(points[n+2]-p.z,2));maximum=Math.max(maximum,error);vertices++;check(error<.0001,"Actual Tripo transform mismatch part="+name+" error="+error);}
            }
            check(triangles==180000,"Incomplete original Tripo carrier triangles");var row=new JsonObject();row.addProperty("rise",state[0]);row.addProperty("recovery_rack",state[1]>0);row.addProperty("release",state[2]);row.addProperty("triangles",triangles);row.addProperty("maximum_error_metres",maximum);results.add(row);System.out.println(row);
        }
        var managerMethod=EvaOriginalMeshGeometryR52Test.class.getDeclaredMethod("manager",Path.class);managerMethod.setAccessible(true);var manager=(ResourceManager)managerMethod.invoke(null,Path.of(args[1]));var layer=Class.forName("com.projectseele.client.render.LocalTriangleMeshLayer");var load=layer.getDeclaredMethod("getMesh",ResourceManager.class,ResourceLocation.class);load.setAccessible(true);
        for(int variant=0;variant<3;variant++)
        {
            var mesh=load.invoke(null,manager,new ResourceLocation("projectseele","mesh/entry_plug_unit0"+variant+".mesh.json"));var raw=(Map<?,?>)call(mesh,"parts");var actual=provider.closedPlugParts(variant);check(actual.size()==3&&!actual.containsKey("plug_crane_collar"),"Station crane collar was falsely carried with locked original capsule");double maximum=0;int triangles=0;
            for(var part:actual.entrySet())
            {Object data=raw.get(part.getKey());float[] source=(float[])call(data,"vertices");float x=(float)call(data,"pivotX"),y=(float)call(data,"pivotY"),z=(float)call(data,"pivotZ");double[] points=part.getValue();triangles+=points.length/9;for(int at=0,n=0;at<source.length;at+=8,n+=3){var expected=new Vector3f(-(source[at]+x)/16,(source[at+1]+y)/16,(source[at+2]+z)/16).mul(3.2F);double error=Math.sqrt(Math.pow(points[n]-expected.x,2)+Math.pow(points[n+1]-expected.y,2)+Math.pow(points[n+2]-expected.z,2));maximum=Math.max(maximum,error);vertices++;check(error<.0001,"Actual closed original capsule mismatch rig="+variant+" part="+part.getKey());}}
            var row=new JsonObject();row.addProperty("capsule_variant",variant);row.addProperty("triangles",triangles);row.addProperty("maximum_error_metres",maximum);results.add(row);System.out.println(row);
            openHatchChecks(provider,variant,raw);
        }
        var report=new JsonObject();report.addProperty("actual_vertices_compared",vertices);report.addProperty("checks",checks);report.addProperty("native_acceptance",false);report.add("cases",results);Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");System.out.println("R52 actual original capsule/Tripo source+render-matrix PASS checks="+checks+" vertices="+vertices+"; no native world acceptance");
    }
    private FullAssemblyGeometryR52Test(){}
}
