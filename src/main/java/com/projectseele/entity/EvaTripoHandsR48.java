package com.projectseele.entity;

import com.projectseele.util.WeakIdentityMap;
import com.projectseele.ProjectSeele;
import com.google.gson.JsonParser;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.HashMap;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** The supplied UN hands retain their curved neutral surface and measured phalange pivots. */
public final class EvaTripoHandsR48
{
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    private static final Map<String,float[]> FISTS=loadFists();
    private static final class State { double time=Double.NaN;float left,right; }
    public static boolean enabled(EvaUnit01Entity eva,EvaBodyPose.Sample pose)
    {return eva.isExperimentalUnit()&&pose.rig.containsKey("tripo_hand_adapter_r48");}
    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample pose,float partial)
    {
        if(!enabled(eva,pose))return;
        int weapon=eva.getWeapon(),action=EvaCombatR31.action(eva);
        boolean attack=eva.hasLiveActionForRender(partial)||action!=0;
        boolean gun=weapon==EvaUnit01Entity.WEAPON_RIFLE||weapon==EvaUnit01Entity.WEAPON_CANNON;
        boolean armed=weapon!=EvaUnit01Entity.WEAPON_FISTS;
        float right=armed||attack?1:0,left=gun||attack?1:0;
        var state=STATES.computeIfAbsent(eva,e->new State());double now=eva.level().getGameTime()+(double)partial;
        float blend=Double.isFinite(state.time)&&now>=state.time?(float)(1-Math.exp(-Math.min(2,now-state.time)/2.4)):1;
        state.left=Mth.lerp(blend,state.left,left);state.right=Mth.lerp(blend,state.right,right);state.time=now;
        float supported=!armed?Mth.clamp((eva.rifleStanceLevel(partial)-1)/2,0,1):0;
        for(String side:new String[]{"l","r"})
        {
            float weight=side.equals("l")?state.left:state.right;
            float sign=side.equals("r")?-1:1;
            for(String digit:new String[]{"index","middle","ring","little"})
            {
                float[] authored=FISTS.get(EvaBodyPose.rigKey(eva)+"/"+side+"/"+digit);
                float[] flex=authored==null?fistFlex(pose,side,digit):authored.clone();
                if(gun&&side.equals("r")&&digit.equals("index"))flex=new float[]{8*sign,12*sign,5*sign};
                else if(gun)for(int j=0;j<3;j++)flex[j]*=.72F;
                for(int joint=0;joint<3;joint++)
                {
                    String name="finger_"+digit+(joint==0?"":joint==1?"_tip":"_distal")+"_"+side;
                    if(!pose.rig.containsKey(name))continue;
                    float angle=(flex[joint]*weight-(joint==0?8:10)*supported*sign)*Mth.DEG_TO_RAD;
                    pose.rotations.put(name,new Quaternionf().rotationZ(angle));pose.positions.put(name,new Vector3f());
                }
            }
            float mirror=side.equals("r")?1:-1;
            for(int joint=0;joint<3;joint++)
            {
                String name="finger_thumb"+(joint==0?"":joint==1?"_tip":"_distal")+"_"+side;
                if(!pose.rig.containsKey(name))continue;
                pose.rotations.put(name,new Quaternionf().rotationY((joint==0?70:0)*mirror*weight*Mth.DEG_TO_RAD)
                        .rotateZ((joint==0?-20:joint==1?40:20)*mirror*weight*Mth.DEG_TO_RAD));
                pose.positions.put(name,new Vector3f());
            }
            if(!armed&&!attack&&eva.rifleStanceLevel(partial)<.3F)
            {
                for(String name:new String[]{"wrist_"+side,"hand_"+side})if(pose.rig.containsKey(name))
                {pose.rotations.put(name,new Quaternionf());pose.positions.put(name,new Vector3f());}
            }
        }
        pose.dirty();
    }
    private static Map<String,float[]> loadFists()
    {
        try(var stream=EvaTripoHandsR48.class.getResourceAsStream("/assets/projectseele/motion/un_finger_poses_r48.json"))
        {
            if(stream==null)return Map.of();
            var data=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();
            if(data.get("schema").getAsInt()!=48)throw new IllegalArgumentException("UN finger pose version");
            var result=new HashMap<String,float[]>();
            for(int key:new int[]{3,4})for(String side:new String[]{"l","r"})for(String digit:new String[]{"index","middle","ring","little"})
            {
                var a=data.getAsJsonObject("fist").getAsJsonObject(Integer.toString(key)).getAsJsonObject(side).getAsJsonArray(digit);
                if(a.size()!=3)throw new IllegalArgumentException("Incomplete measured finger chain");
                float[] v=new float[3];for(int j=0;j<3;j++)
                {v[j]=a.get(j).getAsFloat();if(!Float.isFinite(v[j])||Math.abs(v[j])>145)throw new IllegalArgumentException("Invalid finger flexion");}
                result.put(key+"/"+side+"/"+digit,v);
            }
            return Map.copyOf(result);
        }
        catch(Exception error){ProjectSeele.LOGGER.error("R48 measured UN finger poses rejected",error);return Map.of();}
    }
    public static EvaAnatomicalHandsR45.Grip grip(EvaUnit01Entity eva,EvaBodyPose.Sample pose,String side)
    {
        if(!enabled(eva,pose))return null;
        Vector3f wrist=pose.rig.get("hand_"+side).pivot(),knuckles=new Vector3f();
        for(String digit:new String[]{"index","middle","ring","little"})knuckles.add(pose.rig.get("finger_"+digit+"_"+side).pivot());
        knuckles.mul(.25F);Vector3f along=new Vector3f(knuckles).sub(wrist).normalize();
        Vector3f across=new Vector3f(pose.rig.get("finger_little_"+side).pivot()).sub(pose.rig.get("finger_index_"+side).pivot()).normalize();
        Vector3f palm=new Vector3f(wrist).lerp(knuckles,.55F).add(side.equals("r")?-.085F:.085F,0,0);
        return new EvaAnatomicalHandsR45.Grip(palm,along,across,new Quaternionf(),new Vector3f());
    }
    private static float[] fistFlex(EvaBodyPose.Sample pose,String side,String digit)
    {
        String base="finger_"+digit,tip="tripo_tip_"+base+"_distal_"+side;
        Vector3f[] points={pose.rig.get(base+"_"+side).pivot(),pose.rig.get(base+"_tip_"+side).pivot(),pose.rig.get(base+"_distal_"+side).pivot(),null};
        points[3]=pose.rig.containsKey(tip)?pose.rig.get(tip).pivot():new Vector3f(points[2]).mul(2).sub(points[1]);
        float inward=side.equals("r")?-1:1;
        float[][] directions={{.985F*inward,-.174F},{.342F*inward,.940F},{-.714F*inward,.700F}};
        float[] result=new float[3];float previous=0;
        for(int j=0;j<3;j++)
        {
            Vector3f neutral=new Vector3f(points[j+1]).sub(points[j]);
            float cumulative=Mth.wrapDegrees((float)Math.toDegrees(Math.atan2(directions[j][1],directions[j][0])-Math.atan2(neutral.y,neutral.x)));
            float delta=Mth.wrapDegrees(cumulative-previous);result[j]=delta;previous+=delta;
        }
        return result;
    }
    private EvaTripoHandsR48() { }
}
