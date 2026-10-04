package com.projectseele.physics;

import com.google.gson.*;
import com.projectseele.entity.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Measured body frames are optional until a matching complete profile set is installed. */
public final class CombatBodyProfiles
{
    public static final float MODEL_TO_PHYSICS=.2F,BLOCK_TO_PHYSICS=.04F;
    public record Recovery(String[] names,Quaternionf[][] rotations,Vector3f[][] positions,float duration,float[] frontY) {}
    public record Profile(String key,JsonObject definition,Map<String,EvaBodyPose.Bone> rig,Recovery recovery) {}
    private static Map<String,Profile> profiles;
    private static String loadedFingerprint="ABSENT";
    public static synchronized String fingerprint(){get(null);return loadedFingerprint;}
    public static String key(net.minecraft.world.entity.LivingEntity entity)
    {return entity instanceof EvaPrototypeEntity un?Integer.toString(3+un.getUNSerial()):entity instanceof EvaUnit01Entity eva?Integer.toString(eva.getUnitVariant()):entity instanceof SachielEntity?"sachiel":"";}
    public static synchronized Profile get(net.minecraft.world.entity.LivingEntity entity)
    {
        if(profiles==null)
        {
            Path path=CombatMotionResourcesR44.instancePath(System.getProperty("projectseele.bodyPhysicsProfiles","projectseele-local-maps/articulated_bodies_r35.json"));
            if(!Files.isRegularFile(path)){profiles=Map.of();return null;}
            try
            {
                byte[] bytes=Files.readAllBytes(path);
                loadedFingerprint=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
                com.projectseele.ProjectSeele.LOGGER.info("Combat physical profile resolved: file={} sha256={}",path.toAbsolutePath().normalize(),loadedFingerprint);
                var json=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
                if(!"projectseele.articulated-body.v1".equals(json.get("schema").getAsString()))throw new IllegalArgumentException("Body profile version");
                Map<String,Profile> result=new HashMap<>();
                for(var entry:json.getAsJsonObject("models").entrySet())
                {
                    var definition=entry.getValue().getAsJsonObject();Map<String,EvaBodyPose.Bone> rig=new LinkedHashMap<>();
                    for(var row:definition.getAsJsonArray("render_rig"))
                    {
                        var b=row.getAsJsonObject();var pivot=vector(b.getAsJsonArray("pivot")).mul(-1,1,1).div(16);
                        Vector3f angle=b.has("rotation")?vector(b.getAsJsonArray("rotation")).mul((float)Math.PI/180):new Vector3f();
                        String name=b.get("name").getAsString();rig.put(name,new EvaBodyPose.Bone(name,b.has("parent")?b.get("parent").getAsString():null,pivot,new Quaternionf().rotationZYX(angle.z,-angle.y,-angle.x)));
                    }
                    int count=definition.getAsJsonArray("bodies").size();if(count<5||count>24)throw new IllegalArgumentException("Physical body count");
                    Recovery recovery=null;
                    if(definition.has("recovery"))
                    {
                        var clip=definition.getAsJsonObject("recovery");var names=clip.getAsJsonArray("bones");String[] order=new String[names.size()];for(int i=0;i<order.length;i++)order[i]=names.get(i).getAsString();
                        var frames=clip.getAsJsonArray("frames");Quaternionf[][] q=new Quaternionf[frames.size()][order.length];Vector3f[][] p=new Vector3f[frames.size()][order.length];
                        for(int f=0;f<frames.size();f++)
                        {
                            var frame=frames.get(f).getAsJsonObject();var rotations=frame.getAsJsonArray("rotation_wxyz");
                            for(int b=0;b<order.length;b++)
                            {
                                var v=rotations.get(b).getAsJsonArray();q[f][b]=new Quaternionf(-v.get(1).getAsFloat(),-v.get(2).getAsFloat(),v.get(3).getAsFloat(),v.get(0).getAsFloat()).normalize();
                                Vector3f pos=order[b].equals("root")?vector(frame.getAsJsonArray("root_m")).mul(112):frame.getAsJsonObject("bone_position_xyz").has(order[b])?vector(frame.getAsJsonObject("bone_position_xyz").getAsJsonArray(order[b])):new Vector3f();p[f][b]=pos.mul(-1,1,1).div(16);
                            }
                        }
                        float[] front=new float[frames.size()];if(clip.has("features"))for(int i=0;i<front.length;i++)front[i]=clip.getAsJsonArray("features").get(i).getAsJsonArray().get(0).getAsFloat();
                        recovery=new Recovery(order,q,p,clip.get("duration_seconds").getAsFloat(),front);
                    }
                    result.put(entry.getKey(),new Profile(entry.getKey(),definition,Map.copyOf(rig),recovery));
                }
                profiles=Map.copyOf(result);
            }
            catch(Exception error){throw new IllegalStateException("Rejected physical skeleton profiles",error);}
        }
        return profiles.get(key(entity));
    }
    public static Vector3f vector(JsonArray a)
    {return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    public static Map<String,Matrix4f> physicalMatrices(EvaBodyPose.Sample pose,Profile profile)
    {
        Map<String,Matrix4f> result=new LinkedHashMap<>();
        for(var element:profile.definition.getAsJsonArray("bodies"))
        {String name=element.getAsJsonObject().get("name").getAsString();Matrix4f m=new Matrix4f(pose.matrix(name));m.m30(m.m30()*MODEL_TO_PHYSICS).m31(m.m31()*MODEL_TO_PHYSICS).m32(m.m32()*MODEL_TO_PHYSICS);result.put(name,m);}
        return result;
    }
    public static EvaBodyPose.Sample copy(EvaBodyPose.Sample source)
    {var result=new EvaBodyPose.Sample(source.rig);for(String n:source.rig.keySet()){result.rotations.put(n,new Quaternionf(source.rotations.get(n)));result.positions.put(n,new Vector3f(source.positions.get(n)));}return result;}
    public static EvaBodyPose.Sample canonical(EvaBodyPose.Sample source,Profile profile)
    {
        var result=new EvaBodyPose.Sample(profile.rig());Map<String,Matrix4f> matrices=new HashMap<>();
        for(String name:source.rig.keySet())if(result.rig.containsKey(name))matrices.put(name,source.matrix(name));
        Set<String> visited=new HashSet<>();for(String name:result.rig.keySet())apply(name,result,matrices,visited);return result;
    }
    public static EvaBodyPose.Sample recovery(Profile profile,float progress)
    {
        var clip=profile.recovery;var pose=new EvaBodyPose.Sample(profile.rig);float frame=Math.max(0,Math.min(1,progress))*(clip.rotations.length-1);int a=(int)frame,b=Math.min(a+1,clip.rotations.length-1);
        for(int i=0;i<clip.names.length;i++){String n=clip.names[i];pose.rotations.put(n,new Quaternionf(clip.rotations[a][i]).slerp(clip.rotations[b][i],frame-a));pose.positions.put(n,new Vector3f(clip.positions[a][i]).lerp(clip.positions[b][i],frame-a));}
        pose.dirty();return pose;
    }
    public static EvaBodyPose.Sample render(EvaBodyPose.Sample template,Map<String,Matrix4f> deformations,Vector3f offset)
    {
        var result=copy(template);Map<String,Matrix4f> desired=new HashMap<>();
        for(var entry:deformations.entrySet())
        {Matrix4f m=new Matrix4f(entry.getValue());m.m30((m.m30()-offset.x)/MODEL_TO_PHYSICS).m31((m.m31()-offset.y)/MODEL_TO_PHYSICS).m32((m.m32()-offset.z)/MODEL_TO_PHYSICS);desired.put(entry.getKey(),m);}
        desired.put("root",desired.get("torso_lower"));Set<String> visited=new HashSet<>();
        for(String n:result.rig.keySet())apply(n,result,desired,visited);
        return result;
    }
    private static void apply(String name,EvaBodyPose.Sample result,Map<String,Matrix4f> desired,Set<String> visited)
    {
        if(!visited.add(name))return;String parent=result.rig.get(name).parent();if(parent!=null)apply(parent,result,desired,visited);
        if(!desired.containsKey(name))return;
        Matrix4f local=parent==null?new Matrix4f(desired.get(name)):new Matrix4f(result.matrix(parent)).invert().mul(desired.get(name));
        Quaternionf q=local.getUnnormalizedRotation(new Quaternionf()).normalize();Vector3f pivot=result.rig.get(name).pivot();
        result.rotations.put(name,q);result.positions.put(name,local.getTranslation(new Vector3f()).sub(pivot).add(q.transform(new Vector3f(pivot))));result.dirty();
    }
    private CombatBodyProfiles(){}
}
