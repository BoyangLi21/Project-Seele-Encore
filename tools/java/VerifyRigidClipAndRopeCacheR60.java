package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.world.NervLowerFrameR52;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Vector4f;

/** Isolated real builder/source and conservative clip checks; no Level, Entity, rendering or game. */
public final class VerifyRigidClipAndRopeCacheR60
{
    private static int clipChecks,sourceRopes,worldVertices;
    private static Object field(Object value,String name)throws Exception{Field f=value.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(value);}
    private static void expect(boolean actual,boolean expected,String name){clipChecks++;if(actual!=expected)throw new AssertionError(name+" expected="+expected+" actual="+actual);}
    private static void equalPart(Object original,Object cached,Matrix4f pose)throws Exception
    {
        float[] a=(float[])field(original,"vertices"),b=(float[])field(cached,"vertices");if(a.length!=b.length)throw new AssertionError("Original full encoded vertices changed");
        for(int i=0;i<a.length;i++)if(Float.floatToRawIntBits(a[i])!=Float.floatToRawIntBits(b[i]))throw new AssertionError("XYZ/RGB/UV/normal bits changed at"+i);
        if(!Arrays.equals((float[])field(original,"bounds"),(float[])field(cached,"bounds"))||!field(original,"texture").equals(field(cached,"texture"))||!field(original,"importedTriangles").equals(field(cached,"importedTriangles")))throw new AssertionError("Bounds/material/primitive changed");
        for(int i=0;i<a.length;i+=11){var p=pose.transformPosition(new Vector3f(a[i],a[i+1],a[i+2]));var q=pose.transformPosition(new Vector3f(b[i],b[i+1],b[i+2]));if(Float.floatToRawIntBits(p.x)!=Float.floatToRawIntBits(q.x)||Float.floatToRawIntBits(p.y)!=Float.floatToRawIntBits(q.y)||Float.floatToRawIntBits(p.z)!=Float.floatToRawIntBits(q.z))throw new AssertionError("Transformed source world vertex changed");worldVertices++;}
    }
    private static boolean reject(float[] box,Matrix4f p,Matrix4f v,Matrix4f m){return RigidMachineryPartR44.outsideClipR60(box,p,v,m);}
    private static boolean visible(Vector4f p){return p.w>0&&p.x>=-p.w&&p.x<=p.w&&p.y>=-p.w&&p.y<=p.w&&p.z>=-p.w&&p.z<=p.w;}
    public static void main(String[] args)throws Exception
    {
        if(args.length!=1)throw new IllegalArgumentException("Fresh external report required");Path output=Path.of(args[0]);if(Files.exists(output))throw new IllegalArgumentException("Fresh report required");for(Path p=output.toAbsolutePath();p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        var id=new Matrix4f();float[] small={-.2F,-.2F,-.2F,.2F,.2F,.2F};expect(reject(small,id,id,id),false,"visible origin");
        for(int axis=0;axis<3;axis++)for(int side:new int[]{-1,1}){float[] b=small.clone();b[axis]=side<0?-3:2;b[axis+3]=side<0?-2:3;expect(reject(b,id,id,id),true,"outside plane"+axis+"/"+side);}
        expect(reject(new float[]{1,-.1F,-.1F,1,.1F,.1F},id,id,id),false,"exact touching plane retained");expect(reject(new float[]{1.000001F,-.1F,-.1F,1.2F,.1F,.1F},id,id,id),false,"uncertain float boundary retained");
        expect(reject(small,id,id,new Matrix4f().translation(4,0,0)),true,"pose translation cannot be omitted");expect(reject(small,id,id,new Matrix4f().translation(4,0,0).rotateXYZ(.3F,.4F,.2F).scale(-2,3,.5F)),true,"mirror rotation nonuniform scale");
        var projection=new Matrix4f().perspective((float)Math.toRadians(70),16F/9,.05F,1000);expect(reject(small,projection,id,new Matrix4f().translation(0,0,-10)),false,"perspective visible");expect(reject(small,projection,id,new Matrix4f().translation(1000,0,-10)),true,"perspective outside");expect(reject(small,projection,id,new Matrix4f().translation(0,0,10)),true,"fully behind camera negative w");expect(reject(new float[]{-1,-1,-1,1,1,1},projection,id,id),false,"eye and near plane crossing retained");
        var nan=new Matrix4f().m00(Float.NaN);expect(reject(small,projection,id,nan),false,"NaN transform draws");expect(reject(new float[]{Float.NaN,0,0,1,1,1},projection,id,id),false,"NaN bounds draws");expect(reject(new float[]{2,0,0,1,1,1},projection,id,id),false,"invalid bounds draws");
        var random=new Random(600053);int randomRejected=0;
        for(int n=0;n<2500;n++)
        {
            var model=new Matrix4f().translation(random.nextFloat()*60-30,random.nextFloat()*40-20,random.nextFloat()*70-60).rotateXYZ(random.nextFloat()*6,random.nextFloat()*6,random.nextFloat()*6).scale((random.nextBoolean()?-1:1)*(.2F+random.nextFloat()*4),.2F+random.nextFloat()*4,.2F+random.nextFloat()*4);
            var view=new Matrix4f().rotateXYZ(.1F,.2F,.03F).translate(0,-.5F,0);float size=.1F+random.nextFloat()*4;float[] box={-size,-size,-size,size,size,size};boolean outside=reject(box,projection,view,model);clipChecks++;if(!outside)continue;randomRejected++;
            // Independent sequential shader products test actual interior points.
            for(int x=0;x<5;x++)for(int y=0;y<5;y++)for(int z=0;z<5;z++){var p=new Vector4f(-size+2*size*x/4,-size+2*size*y/4,-size+2*size*z/4,1);model.transform(p);view.transform(p);projection.transform(p);if(visible(p))throw new AssertionError("False-negative homogeneous reject at case"+n);}
        }
        double[] sample=null;int idleRopes=0;
        for(double progress:new double[]{0,.05,.15,.299,.3,.31,.374,.375,.4,.45,.6,.849,.85,.9,1})for(var piece:NervLowerFrameR52.pieces(progress))if(piece.kind().equals("rope"))
        {
            if(progress==0)idleRopes++;if(sample==null)sample=piece.rgb().clone();var data=new JsonArray();for(double v:piece.rgb())data.add(v);var old=RigidMachineryPartBaselineR60.triangles(data);var cached=NervLowerFrameRendererR52.ropeMeshR60(piece.name(),piece.rgb());if(cached!=NervLowerFrameRendererR52.ropeMeshR60(piece.name(),piece.rgb().clone()))throw new AssertionError("Same complete raw source bits rebuilt identity");
            var t=piece.local().translation();var pose=new Matrix4f().translation(72.5F,-1062.96F,328.5F).rotateXYZ(.21F,(float)Math.PI,.17F).scale(-1,1.3F,.8F).translate((float)t.x,(float)t.y,(float)t.z);equalPart(old,cached,pose);sourceRopes++;
        }
        if(idleRopes!=4)throw new AssertionError("Three actual idle gantries must create4*3 prior meshes/frame");
        Class<?> key=Class.forName("com.projectseele.client.render.NervLowerFrameRendererR52$RopeKeyR60");var ctor=key.getDeclaredConstructor(String.class,String.class,String.class,long[].class);ctor.setAccessible(true);long[] left={0,31},right={1,0};Object a=ctor.newInstance("source","name","material",left),b=ctor.newInstance("source","name","material",right);if(a.hashCode()!=b.hashCode()||a.equals(b))throw new AssertionError("Hash-only key collision accepted");left[0]=7;if(!a.equals(ctor.newInstance("source","name","material",new long[]{0,31})))throw new AssertionError("Key borrowed mutable source bits");if(a.equals(ctor.newInstance("source","name","other-material",new long[]{0,31})))throw new AssertionError("Material omitted from key");
        Field cacheField=NervLowerFrameRendererR52.class.getDeclaredField("ROPES_R60");cacheField.setAccessible(true);@SuppressWarnings("unchecked")Map<Object,Object> cache=(Map<Object,Object>)cacheField.get(null);var first=NervLowerFrameRendererR52.ropeMeshR60("eviction-old",sample);for(int i=0;i<80;i++)NervLowerFrameRendererR52.ropeMeshR60("eviction"+i,sample);if(cache.size()!=64||cache.containsValue(first))throw new AssertionError("Rope cache eviction/cap failed");var newFirst=NervLowerFrameRendererR52.ropeMeshR60("eviction-old",sample);if(newFirst==first)throw new AssertionError("Evicted identity retained by source cache");
        var report=new LinkedHashMap<String,Object>();report.put("passed",true);report.put("clip_checks",clipChecks);report.put("random_strict_rejects_without_visible_interior",randomRejected);report.put("float_uncertainty_nan_crossing_retained",true);report.put("actual_source_ropes_bit_exact",sourceRopes);report.put("world_transformed_vertices_bit_exact",worldVertices);report.put("idle_original_ropes_per_gantry",idleRopes);report.put("prior_three_gantry_new_identities_per_frame",idleRopes*3);report.put("exact_identity_reuse_hash_collision_negative_material_key_and_defensive_bits",true);report.put("bounded_source_rope_cache",64);report.put("evicted_source_identity_absent",true);report.put("native_fps_or_gpu_submit_pass",false);report.put("scope","Actual Source builder and selected Jar ropes; isolated CPU matrix/cache checks only. No Level, Entity, GL draws, World or game start.");Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
    }
}
