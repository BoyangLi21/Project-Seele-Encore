package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.entity.EvaCombatSupportR33;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleSignals;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;

/** Final bone FK and the actual CPU vertex submitted to the mesh renderer. */
public final class EvaFootWitnessR44
{
    private record Pending(long frame,JsonObject row){}
    private static final WeakIdentityMap<EvaUnit01Entity,Pending> PENDING=new WeakIdentityMap<>();
    private static final Map<ResourceLocation,String> HASHES=new HashMap<>();
    private static final Map<String,Integer> VERTICES=new HashMap<>();
    private static String codeHash;
    public static JsonObject capture(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f modelToWorld)
    {
        JsonObject row=new JsonObject();row.addProperty("gpu_output_sampled",false);
        row.addProperty("frame",FirstBattleSignals.clientFrameTime());row.addProperty("code_sha256",codeHash());
        String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+eva.getUnitVariant();
        row.addProperty("geometry_sha256",resourceHash(new ResourceLocation("projectseele","geo/"+asset+".geo.json")));
        row.addProperty("mesh_sha256",resourceHash(new ResourceLocation("projectseele","mesh/"+asset+".mesh.json")));
        var support=com.projectseele.entity.EvaCombatSupportR33.diagnosticR44(eva);JsonObject anchors=new JsonObject();row.add("support_r44",anchors);
        anchors.addProperty("locomotion",support.getBoolean("locomotion_r44"));anchors.addProperty("release_at",support.contains("release")?support.getLong("release"):-1);
        if(support.contains("client_release_ticks"))anchors.addProperty("client_release_ticks",support.getDouble("client_release_ticks"));
        anchors.addProperty("game_time",eva.level().getGameTime());anchors.addProperty("gait",eva.rifleGaitPhase(partial));anchors.addProperty("run",eva.rifleRunBlend(partial));anchors.addProperty("move",eva.rifleMoveBlend(partial));
        for(String side:new String[]{"l","r"})
        {
            anchors.addProperty(side+"active",support.getBoolean(side+"active"));anchors.addProperty(side+"source_plant",com.projectseele.entity.EvaBodyPose.locomotionPlantedR44(eva,side,partial));
            anchors.addProperty(side+"plant_at",support.getLong(side+"plant"));JsonArray point=new JsonArray();point.add(support.getDouble(side+"x"));point.add(support.getDouble(side+"y"));point.add(support.getDouble(side+"z"));anchors.add(side+"anchor",point);
            var floor=support.getCompound("free_floor_r44");for(String key:new String[]{"before_y","after_y","ground_y"})if(floor.contains(side+key))anchors.addProperty(side+key,floor.getDouble(side+key));
        }
        var clock=support.getList("position_phase_r44",net.minecraft.nbt.Tag.TAG_COMPOUND);JsonArray pairs=new JsonArray();anchors.add("position_phase",pairs);
        for(int i=0;i<clock.size();i++)
        {
            var sample=clock.getCompound(i);JsonObject pair=new JsonObject();pair.addProperty("tick",sample.getLong("tick"));
            for(String key:new String[]{"x","y","z"})pair.addProperty(key,sample.getDouble(key));for(String key:new String[]{"gait","run","move"})pair.addProperty(key,sample.getFloat(key));pairs.add(pair);
        }
        JsonObject toes=new JsonObject();row.add("final_bone_fk_world",toes);
        if(modelToWorld==null){row.addProperty("error","Renderer model-to-world matrix missing");return row;}
        for(String side:new String[]{"l","r"})model.getBone("foot_"+side).ifPresent(bone->{
            var marker=EvaRigTransforms.pivot(bone).add(EvaCombatSupportR33.toe(eva,side));
            toes.add(side,vector(EvaRigTransforms.point(bone,marker,modelToWorld)));
        });
        // The same JsonObject is filled later by the real draw path in this
        // frame. This never presents a previous-frame draw as a fresh sample.
        row.add("submitted_mesh_vertex_world",new JsonObject());
        PENDING.put(eva,new Pending(FirstBattleSignals.clientFrameTime(),row));return row;
    }
    public static void submitted(EvaUnit01Entity eva,GeoBone bone,ResourceLocation resource,float[] original,float[] submitted,
                                 int stride,float pivotX,float pivotY,float pivotZ,Matrix4f meshToWorld)
    {
        String side=bone.getName().equals("foot_l")?"l":bone.getName().equals("foot_r")?"r":"";
        var pending=PENDING.get(eva);if(side.isEmpty()||pending==null||pending.frame()!=FirstBattleSignals.clientFrameTime())return;
        var marker=EvaRigTransforms.pivot(bone).add(EvaCombatSupportR33.toe(eva,side));
        String key=resource+":"+side+":"+original.length+":"+marker;
        int index=VERTICES.computeIfAbsent(key,ignored->{
            float best=Float.POSITIVE_INFINITY;int selected=0;
            for(int at=0;at+stride<=original.length;at+=stride)
            {
                Vector3f point=new Vector3f(-(original[at]+pivotX),original[at+1]+pivotY,original[at+2]+pivotZ).div(16);
                float distance=point.distanceSquared(marker);if(distance<best){best=distance;selected=at;}
            }
            return selected;
        });
        if(index+2>=submitted.length)return;
        Vector3f point=new Vector3f(-(submitted[index]+pivotX),submitted[index+1]+pivotY,submitted[index+2]+pivotZ).div(16);
        var row=pending.row();row.getAsJsonObject("submitted_mesh_vertex_world").add(side,vector(meshToWorld.transformPosition(point)));
        float lowest=Float.POSITIVE_INFINITY;Vector3f lowPoint=new Vector3f(),work=new Vector3f();
        for(int at=0;at+stride<=submitted.length;at+=stride)
        {
            meshToWorld.transformPosition(work.set(-(submitted[at]+pivotX),submitted[at+1]+pivotY,submitted[at+2]+pivotZ).div(16));
            if(work.y<lowest){lowest=work.y;lowPoint.set(work);}
        }
        row.addProperty(side+"_submitted_min_y",lowest);row.add(side+"_submitted_lowest_world",vector(lowPoint));
        if(eva.level()!=null&&lowPoint.isFinite())
        {
            Vec3Floor.capture(eva,row,side,lowPoint);
        }
        row.addProperty(side+"_vertex_index",index/stride);row.addProperty(side+"_submitted_mesh_sha256",resourceHash(resource));
        row.addProperty("submitted_kind","CPU vertex after skinVertices, through actual renderer mesh-to-world; GPU output remains unsampled");
    }
    private static JsonArray vector(Vector3f point)
    {JsonArray row=new JsonArray();row.add(point.x);row.add(point.y);row.add(point.z);return row;}
    private static final class Vec3Floor
    {
        static void capture(EvaUnit01Entity eva,JsonObject row,String side,Vector3f point)
        {
            var from=new net.minecraft.world.phys.Vec3(point.x,point.y+2,point.z);
            var hit=eva.level().clip(new net.minecraft.world.level.ClipContext(from,from.add(0,-8,0),
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
            row.addProperty(side+"_ground_hit",hit.getType().toString());
            if(hit.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK)
            {
                row.addProperty(side+"_ground_y",hit.getLocation().y);row.addProperty(side+"_sole_clearance",point.y-hit.getLocation().y);
            }
        }
    }
    private static String resourceHash(ResourceLocation resource)
    {
        return HASHES.computeIfAbsent(resource,key->{
            try(var stream=Minecraft.getInstance().getResourceManager().getResource(key).orElseThrow().open())
            {return digest(stream);}
            catch(Exception failure){return "UNAVAILABLE:"+failure.getClass().getSimpleName();}
        });
    }
    private static String codeHash()
    {
        if(codeHash!=null)return codeHash;
        try
        {
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            for(Class<?> type:new Class<?>[]{EvaFootWitnessR44.class,EvaRigTransforms.class,com.projectseele.entity.EvaBodyPose.class,
                    com.projectseele.entity.EvaCombatSupportR33.class,com.projectseele.entity.EvaUnit01Entity.class,
                    com.projectseele.entity.EvaGameplayMotionR32.class,com.projectseele.entity.EvaPoseSignalClock.class,LocalTriangleMeshLayer.class})
            {
                try(var stream=type.getResourceAsStream("/"+type.getName().replace('.','/')+".class"))
                {if(stream==null)throw new IllegalStateException("Loaded class bytecode missing");digest.update(stream.readAllBytes());}
            }
            return codeHash=HexFormat.of().formatHex(digest.digest());
        }
        catch(Exception failure){throw new IllegalStateException("Final foot witness code identity unavailable",failure);}
    }
    private static String digest(InputStream stream)throws Exception
    {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");byte[] block=new byte[65536];int count;
        while((count=stream.read(block))>=0)if(count>0)digest.update(block,0,count);
        return HexFormat.of().formatHex(digest.digest());
    }
    private EvaFootWitnessR44(){}
}
