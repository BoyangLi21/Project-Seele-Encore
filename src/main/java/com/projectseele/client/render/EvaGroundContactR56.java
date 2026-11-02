package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The drawn body rests on the ground, whichever pose owner drew it.
 * <p>
 * A planted foot lies flat on its sole instead of balancing on a heel or
 * toe edge. Then the lowest part of the body, sole, knee, elbow, hand or
 * chest, is brought onto the ground: blending from standing to lying left
 * the folded body hanging up to five blocks in the air before it dropped.
 */
final class EvaGroundContactR56
{
    private static final String[] PARTS={"foot_l","foot_r","shin_l","shin_r","leg_l","leg_r","torso_lower","torso_upper",
            "arm_l","arm_r","forearm_l","forearm_r","hand_l","hand_r","head"};
    /** Rest-pose hull samples per part (model units): the extremes along 26 directions. */
    private static final Map<Integer,Map<String,Vector3f[]>> HULLS=new HashMap<>();
    private record Ankle(float x,float z,long time,float planted) {}
    /** Last ankle position per EVA and side (world), its frame time and planted weight. */
    private static final Map<String,Ankle> ANKLES=new HashMap<>();
    /** Seconds a foot takes to settle onto, or lift off, the ground. */
    private static final float PLANT_EASE=.09F;
    /** The other foot this high (blocks) means double support; this high, mid-swing. */
    private static final float STANCE_LOW=1.5F,STANCE_HIGH=5F;
    /** A sole this far above the ground still counts as planted (blocks), fading out by the second. */
    private static final float PLANT_NEAR=.3F,PLANT_FAR=1.8F;
    /**
     * An ankle moving faster than this (blocks per second) is swinging, not
     * planted. Kept well above a stance foot that skates with the clip: a
     * lower bar switched planted feet on and off between frames.
     */
    private static final float PLANT_SLOW=30F,PLANT_FAST=60F;
    /** Shin tilt from vertical (degrees) up to which the sole lies level, and from which the instep rests on the ground. */
    private static final float LEVEL_SHIN=40,INSTEP_SHIN=70;
    /** Ankle extension (foot rotX from the shin, degrees) of a foot resting on its instep. */
    private static final float INSTEP_POINT=Float.parseFloat(System.getProperty("projectseele.proneFootR56","-70"));
    /** The body is lowered at most this far onto the ground, and raised at most the second (blocks). */
    private static final float MAX_DROP=8F,MAX_LIFT=3F;

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(root==null||!applies(eva))return;
        var hulls=hulls(eva);
        if(hulls.isEmpty())return;
        float ground=root.m31();
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();
        // Feet are judged against the floor the body is about to be set on:
        // a folding body hanging in the air still stands on its feet.
        float floor=lowest(model,root,hulls);
        if(!Float.isFinite(floor))return;
        float left=soleHeight(model,root,hulls,"l")-floor,right=soleHeight(model,root,hulls,"r")-floor;
        settleFoot(eva,model,root,hulls,"l",floor,right,now);
        settleFoot(eva,model,root,hulls,"r",floor,left,now);
        float lowest=lowest(model,root,hulls);
        float gap=Mth.clamp(lowest-ground,-MAX_LIFT,MAX_DROP);
        if(Math.abs(gap)<.02F)return;
        var base=model.getBone("root").orElse(null);
        if(base==null)return;
        // Root offsets are model pixels; the world frame only turns and scales.
        base.setPosY(base.getPosY()-gap*16/EvaScale.RENDER_SCALE);
    }

    private static boolean applies(EvaUnit01Entity eva)
    {
        return eva.isPoweredOn()&&!eva.isCrucified()&&!eva.hasActiveCarrierMotion()&&!eva.isFirstBattleActive()
                &&!eva.isVisuallyAirborneForRender()&&!eva.isNervLogisticsLocked()&&!eva.isLaunchSequenceActive()
                &&eva.getActivationTicks()<=0&&eva.getVisualPose()==0&&!EvaShutdownR30.displayed(eva)
                &&!EvaAirTransportR31.active(eva)&&!com.projectseele.physics.CombatBodyDynamics.active(eva)
                &&(!eva.isExperimentalUnit()||EvaBodyPose.hasOwnUnRig(eva));
    }

    /**
     * Rest a foot that is on the ground the way its shin allows. Over a steep
     * shin (standing, squatting, the front foot of a kneel) the sole lies
     * level; under a shin lying along the ground (the rear leg of a kneel,
     * prone) the instep rests on the ground with the toes pointing back.
     * Blending prone by its progress instead pointed the feet of a body still
     * squatting, which stood on its toe tips.
     */
    private static float soleHeight(BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,String side)
    {
        var foot=model.getBone("foot_"+side).orElse(null);var points=hulls.get("foot_"+side);
        return foot==null||points==null?Float.POSITIVE_INFINITY:lowest(new Matrix4f(root).mul(EvaRigTransforms.model(foot)),points);
    }

    private static void settleFoot(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls,
                                   String side,float ground,float other,long now)
    {
        var foot=model.getBone("foot_"+side).orElse(null);var shin=model.getBone("shin_"+side).orElse(null);
        var points=hulls.get("foot_"+side);
        if(foot==null||shin==null||foot.getParent()==null||points==null)return;
        var matrix=new Matrix4f(root).mul(EvaRigTransforms.model(foot));
        float height=lowest(matrix,points)-ground;
        var ankle=matrix.transformPosition(EvaRigTransforms.pivot(foot));
        String key=eva.getId()+side;
        var last=ANKLES.get(key);
        float planted;
        if(last!=null&&last.time()==now)planted=last.planted();
        else
        {
            float dt=last==null?0:(now-last.time())/1e9F,speed=0;
            if(dt>0&&dt<.25F)speed=(float)Math.hypot(ankle.x-last.x(),ankle.z-last.z())/dt;
            float wanted=(1-step((height-PLANT_NEAR)/(PLANT_FAR-PLANT_NEAR)))*(1-step((speed-PLANT_SLOW)/(PLANT_FAST-PLANT_SLOW)));
            // A walking foot lies flat at mid-stance, while the other swings
            // high; at heel strike and push-off it keeps its roll. Lying, the
            // instep rests whatever the other foot does.
            float swing=step((other-STANCE_LOW)/(STANCE_HIGH-STANCE_LOW));
            wanted*=Mth.lerp(lying(model,side),swing,1);
            // Settle in and out over a few frames: a weight flickering with
            // the frame-to-frame speed snapped the foot between its poses.
            planted=dt>0&&dt<.25F?last.planted()+(wanted-last.planted())*(1-(float)Math.exp(-dt/PLANT_EASE)):wanted;
            if(ANKLES.size()>64)ANKLES.clear();
            ANKLES.put(key,new Ankle(ankle.x,ankle.z,now,planted));
        }
        if(planted<=.01F)return;
        var modelRotation=EvaRigTransforms.rotation(EvaRigTransforms.model(foot));
        var parent=EvaRigTransforms.rotation(EvaRigTransforms.model(foot.getParent()));
        var up=modelRotation.transform(new Vector3f(0,1,0));
        var level=new Quaternionf().rotationTo(up,new Vector3f(0,1,0)).mul(modelRotation);
        float lying=lying(model,side);
        var instep=new Quaternionf(parent).mul(new Quaternionf().rotationX(INSTEP_POINT*Mth.DEG_TO_RAD));
        var wanted=new Quaternionf(modelRotation).slerp(new Quaternionf(level).slerp(instep,lying),planted);
        EvaRigTransforms.rotate(foot,parent.invert().mul(wanted));
    }

    /** How far the shin lies along the ground: 0 steep (sole level), 1 lying (instep down). */
    private static float lying(BakedGeoModel model,String side)
    {
        var shin=model.getBone("shin_"+side).orElse(null);
        if(shin==null)return 0;
        // The shin runs from the knee down to the ankle along its local -Y.
        var along=EvaRigTransforms.rotation(EvaRigTransforms.model(shin)).transform(new Vector3f(0,-1,0));
        float tilt=(float)Math.toDegrees(Math.acos(Mth.clamp(-along.y,-1,1)));
        return step((tilt-LEVEL_SHIN)/(INSTEP_SHIN-LEVEL_SHIN));
    }

    private static float lowest(BakedGeoModel model,Matrix4f root,Map<String,Vector3f[]> hulls)
    {
        float lowest=Float.POSITIVE_INFINITY;
        for(String name:PARTS)
        {
            var bone=model.getBone(name).orElse(null);var points=hulls.get(name);
            if(bone==null||points==null||bone.isHidden())continue;
            lowest=Math.min(lowest,lowest(new Matrix4f(root).mul(EvaRigTransforms.model(bone)),points));
        }
        return lowest;
    }

    private static float lowest(Matrix4f matrix,Vector3f[] points)
    {
        float minimum=Float.POSITIVE_INFINITY;
        for(var p:points)minimum=Math.min(minimum,matrix.m01()*p.x+matrix.m11()*p.y+matrix.m21()*p.z+matrix.m31());
        return minimum;
    }

    private static float step(float t)
    {
        t=Mth.clamp(t,0,1);
        return t*t*(3-2*t);
    }

    private static Map<String,Vector3f[]> hulls(EvaUnit01Entity eva)
    {
        return HULLS.computeIfAbsent(EvaBodyPose.rigKey(eva),v->
        {
            Map<String,Vector3f[]> result=new HashMap<>();
            String asset=eva.isExperimentalUnit()?eva.experimentalAssetName():"eva_unit0"+v;
            try(var reader=Minecraft.getInstance().getResourceManager().getResource(new ResourceLocation("projectseele","mesh/"+asset+".mesh.json")).orElseThrow().openAsReader())
            {
                var document=JsonParser.parseReader(reader).getAsJsonObject();var parts=document.getAsJsonObject("parts");
                int stride=document.has("stride")?document.get("stride").getAsInt():8;
                List<Vector3f> directions=new ArrayList<>();
                for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++)
                    if(x!=0||y!=0||z!=0)directions.add(new Vector3f(x,y,z).normalize());
                for(String name:PARTS)
                {
                    if(!parts.has(name))continue;
                    var part=parts.getAsJsonObject(name);var pivot=part.getAsJsonArray("pivot");var a=part.getAsJsonArray("vertices");
                    float px=pivot.get(0).getAsFloat(),py=pivot.get(1).getAsFloat(),pz=pivot.get(2).getAsFloat();
                    Vector3f[] best=new Vector3f[directions.size()];float[] score=new float[directions.size()];
                    java.util.Arrays.fill(score,Float.NEGATIVE_INFINITY);
                    for(int i=0;i+2<a.size();i+=stride)
                    {
                        var p=new Vector3f(-(a.get(i).getAsFloat()+px)/16,(a.get(i+1).getAsFloat()+py)/16,(a.get(i+2).getAsFloat()+pz)/16);
                        for(int d=0;d<best.length;d++){float s=p.dot(directions.get(d));if(s>score[d]){score[d]=s;best[d]=p;}}
                    }
                    var kept=java.util.Arrays.stream(best).filter(java.util.Objects::nonNull).distinct().toArray(Vector3f[]::new);
                    if(kept.length>0)result.put(name,kept);
                }
            }
            catch(Exception failure){com.projectseele.ProjectSeele.LOGGER.warn("R56 ground contact hull unavailable for variant {}",v,failure);}
            return result;
        });
    }

    private EvaGroundContactR56() {}
}
