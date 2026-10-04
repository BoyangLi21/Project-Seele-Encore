package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Recorded hand brace, foot plant and hip drive with measured body support. */
public final class EvaRecoveryPoseR31
{
    private record Profile(String[] names,Quaternionf[][] rotations,Vector3f[][] positions,
                           Map<String,float[]> support,Vector3f sole,Vector3f anchor) {}
    private static volatile Map<Integer,Profile> profiles;
    private static Vector3f vector(JsonArray a)
    {
        if(a.size()!=3)throw new IllegalArgumentException("Recovery vector length");
        Vector3f v=new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());
        if(!v.isFinite())throw new IllegalArgumentException("Nonfinite recovery vector");return v;
    }
    private static synchronized Map<Integer,Profile> profiles()
    {
        if(profiles!=null)return profiles;
        Path path=CombatMotionResourcesR44.instancePath(System.getProperty("projectseele.recoveryPoseReview","projectseele-local-maps/eva_recovery_r31.json"));
        if(!Files.isRegularFile(path)){profiles=Map.of();return profiles;}
        try
        {
            var all=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if(!"projectseele.recovery-r31.v1".equals(all.get("schema").getAsString()))throw new IllegalArgumentException("Recovery schema");
            var order=all.getAsJsonArray("bones");String[] names=new String[order.size()];for(int i=0;i<names.length;i++)names[i]=order.get(i).getAsString();
            Map<Integer,Profile> result=new HashMap<>();
            for(var entry:all.getAsJsonObject("models").entrySet())
            {
                var model=entry.getValue().getAsJsonObject();var frames=model.getAsJsonArray("frames");if(frames.size()<2||frames.size()>600)throw new IllegalArgumentException("Recovery sample count");
                Quaternionf[][] rotations=new Quaternionf[frames.size()][names.length];Vector3f[][] positions=new Vector3f[frames.size()][names.length];
                for(int f=0;f<frames.size();f++)
                {
                    var frame=frames.get(f).getAsJsonObject();var qs=frame.getAsJsonArray("rotation_xyzw");var ps=frame.getAsJsonArray("positions");
                    if(qs.size()!=names.length||ps.size()!=names.length)throw new IllegalArgumentException("Recovery bone count");
                    for(int n=0;n<names.length;n++)
                    {
                        var q=qs.get(n).getAsJsonArray();Quaternionf rotation=new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
                        if(!rotation.isFinite()||Math.abs(rotation.lengthSquared()-1)>.001)throw new IllegalArgumentException("Recovery quaternion");
                        rotations[f][n]=rotation.normalize();positions[f][n]=vector(ps.get(n).getAsJsonArray());
                    }
                }
                Map<String,float[]> support=new HashMap<>();
                for(var part:model.getAsJsonObject("support").entrySet())
                {
                    var points=part.getValue().getAsJsonArray();float[] packed=new float[points.size()*3];
                    for(int i=0;i<points.size();i++){var v=vector(points.get(i).getAsJsonArray());packed[i*3]=v.x;packed[i*3+1]=v.y;packed[i*3+2]=v.z;}support.put(part.getKey(),packed);
                }
                result.put(Integer.parseInt(entry.getKey()),new Profile(names,rotations,positions,Map.copyOf(support),vector(model.getAsJsonArray("sole_l")),vector(model.getAsJsonArray("anchor"))));
            }
            profiles=Map.copyOf(result);ProjectSeele.LOGGER.info("R31 measured recovery profiles loaded: {} rigs",profiles.size());return profiles;
        }
        catch(Exception error)
        {ProjectSeele.LOGGER.error("R31 recovery profile unavailable; retain existing reaction fallback",error);profiles=Map.of();return profiles;}
    }
    public static boolean ready(EvaUnit01Entity eva)
    {int key=EvaBodyPose.rigKey(eva);return (!eva.isExperimentalUnit()||key>=3)&&profiles().containsKey(key);}
    public static synchronized void reload(){profiles=null;}
    private static EvaBodyPose.Sample copy(EvaBodyPose.Sample source)
    {
        var result=new EvaBodyPose.Sample(source.rig);
        for(String name:source.rig.keySet()){result.rotations.put(name,new Quaternionf(source.rotations.get(name)));result.positions.put(name,new Vector3f(source.positions.get(name)));}return result;
    }
    private static EvaBodyPose.Sample mix(EvaBodyPose.Sample a,EvaBodyPose.Sample b,float amount)
    {
        var result=copy(a);
        for(String name:result.rig.keySet()){result.rotations.get(name).slerp(b.rotations.get(name),amount);result.positions.get(name).lerp(b.positions.get(name),amount);}result.dirty();return result;
    }
    private static EvaBodyPose.Sample recorded(EvaBodyPose.Sample template,Profile profile,float progress)
    {
        var result=new EvaBodyPose.Sample(template.rig);
        for(var bone:result.rig.values())if(bone.name().contains("_axis_"))result.rotations.put(bone.name(),new Quaternionf(bone.bindRotation()));
        float frame=Mth.clamp(progress,0,1)*(profile.rotations.length-1);int a=(int)frame,b=Math.min(a+1,profile.rotations.length-1);float blend=frame-a;
        for(int i=0;i<profile.names.length;i++)
        {
            String name=profile.names[i];if(!result.rig.containsKey(name))continue;
            result.rotations.put(name,new Quaternionf(profile.rotations[a][i]).slerp(profile.rotations[b][i],blend));result.positions.put(name,new Vector3f(profile.positions[a][i]).lerp(profile.positions[b][i],blend));
        }
        result.dirty();return result;
    }
    private static void hinges(EvaBodyPose.Sample sample)
    {
        for(String side:List.of("l","r"))for(String family:List.of("shin_","forearm_"))
        {
            String name=family+side;if(!sample.rig.containsKey(name))continue;
            String marker=(family.equals("shin_")?"r30_knee_socket_":"r30_elbow_socket_")+side;
            Vector3f centre=sample.rig.containsKey(marker)?new Vector3f(sample.rig.get(marker).pivot())
                    :family.equals("shin_")?new Vector3f(sample.rig.get(name).pivot()).add(0,11.4F/16,0)
                    :new Vector3f(side.equals("l")?-23.489652F:23.489652F,123.435069F,7.737214F).div(16);
            var delta=centre.sub(sample.rig.get(name).pivot());
            sample.positions.put(name,new Vector3f(delta).sub(sample.rotations.get(name).transform(new Vector3f(delta))));
        }
        sample.dirty();
    }
    private static void support(EvaBodyPose.Sample sample,Profile profile,float lock,float grounding)
    {
        // Interpolating the old hinge translations independently of their
        // quaternions opens the elbow/knee seam during a large get-up blend.
        hinges(sample);
        if(lock>0&&sample.rig.containsKey("foot_l"))
        {
            var point=sample.matrix("foot_l").transformPosition(new Vector3f(profile.sole));
            sample.positions.get("root").add((profile.anchor.x-point.x)*lock,0,(profile.anchor.z-point.z)*lock);sample.dirty();
        }
        float floor=Float.POSITIVE_INFINITY;
        for(var part:profile.support.entrySet())
        {
            if(!sample.rig.containsKey(part.getKey()))continue;var m=sample.matrix(part.getKey());float[] points=part.getValue();
            for(int i=0;i<points.length;i+=3)floor=Math.min(floor,m.m01()*points[i]+m.m11()*points[i+1]+m.m21()*points[i+2]+m.m31());
        }
        if(Float.isFinite(floor)){sample.positions.get("root").y-=floor*(floor<0?1:grounding);sample.dirty();}
    }
    public static int recoveryStart(int duration){return Math.max(10,duration-44);}
    public static String stage(float age,int duration,boolean airborne)
    {
        int start=recoveryStart(duration);if(duration!=46&&age<9)return "fall";if(airborne||age<start)return "fallen";
        float u=(age-start)/Math.max(1,duration-start);return u<.22F?"hand_brace":u<.50F?"foot_plant":u<.82F?"hip_drive":"settle";
    }
    /** Caller retains reaction ownership; returned samples never scale or mutate the input poses. */
    public static EvaBodyPose.Sample apply(EvaUnit01Entity eva,EvaBodyPose.Sample live,EvaBodyPose.Sample fallen,
                                          float age,int duration,boolean airborne)
    {
        Profile profile=profiles().get(EvaBodyPose.rigKey(eva));if(profile==null)return live;
        int start=recoveryStart(duration);
        if(airborne||age<start)
        {
            // CombatFeel.travel emits the 46-tick DOWN after a thrown body
            // lands. It is already fallen; starting from live would stand it
            // up for one frame before playing a second fall.
            float fall=duration==46?1:EvaDorsalMechanism.smooth(age/9F);var result=mix(live,fallen,fall);support(result,profile,fall,fall);return result;
        }
        float u=Mth.clamp((age-start)/Math.max(1,duration-start),0,1);
        if(u>=1)return live;
        var captured=recorded(live,profile,u);float entry=EvaDorsalMechanism.smooth(u/.18F);
        var result=mix(fallen,captured,entry);float settle=EvaDorsalMechanism.smooth((u-.80F)/.20F);
        result=mix(result,live,settle);support(result,profile,1-settle,1-settle);return result;
    }
    private EvaRecoveryPoseR31() {}
}
