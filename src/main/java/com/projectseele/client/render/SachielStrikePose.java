package com.projectseele.client.render;

import com.projectseele.entity.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

public final class SachielStrikePose
{
    public static void apply(SachielEntity actor,BakedGeoModel model,float partial)
    {
        if(actor.isFirstBattleActive())return;
        if(!actor.isStrikeActive())
        {
            if(SachielGameplayMotionR32.directed()&&!EvaCombatR31.holds(actor))write(model,SachielGameplayMotionR32.locomotion(actor,partial));
            return;
        }
        int mode=actor.strikeMode();float age=actor.strikeAge(partial),w=SachielStrike.weight(mode,age);
        if(SachielGameplayMotionR32.ready())
        {
            var pose=SachielGameplayMotionR32.pose(actor,age);
            float blend=Math.min(1,age/4)*(1-net.minecraft.util.Mth.clamp((age-SachielStrike.duration(mode)+6)/6,0,1));
            for(String name:pose.rig.keySet())model.getBone(name).ifPresent(b->{
                var rotation=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()).slerp(pose.rotations.get(name),blend);EvaRigTransforms.rotate(b,rotation);
                var p=pose.positions.get(name);b.setPosX(net.minecraft.util.Mth.lerp(blend,b.getPosX(),-p.x*16));b.setPosY(net.minecraft.util.Mth.lerp(blend,b.getPosY(),p.y*16));b.setPosZ(net.minecraft.util.Mth.lerp(blend,b.getPosZ(),p.z*16));
            });return;
        }
        float chamber=SachielStrike.prepare(mode,age),drive=SachielStrike.drive(mode,age)*(1-SachielStrike.release(mode,age));
        boolean left=mode==SachielStrike.HOOK,both=SachielStrike.bothHands(mode);
        for(boolean upper:new boolean[]{false,true})
        {
            var rotation=SachielStrike.torsoRotation(mode,age,upper);
            model.getBone(upper?"torso_upper":"torso_lower").ifPresent(b->{b.setRotX(b.getRotX()+(rotation.x-b.getRotX())*w);b.setRotY(b.getRotY()+(rotation.y-b.getRotY())*w);b.setRotZ(b.getRotZ()*(1-w));});
        }
        for(String side:new String[]{"l","r"})
        {
            float sign=(side.equals("l")==left)?1:-1;
            model.getBone("leg_"+side).ifPresent(b->b.setRotX(b.getRotX()+(.11F*chamber-sign*.18F*drive)*w));
            model.getBone("shin_"+side).ifPresent(b->b.setRotX(b.getRotX()-.19F*w));
            model.getBone("foot_"+side).ifPresent(b->b.setRotX(b.getRotX()+.08F*w));
        }
        solve(actor,model,partial,age,left);
        if(both)solve(actor,model,partial,age,!left);
        else
        {
            String guard=left?"r":"l";
            model.getBone("arm_"+guard).ifPresent(b->b.setRotX(b.getRotX()-.18F*w));
            model.getBone("forearm_"+guard).ifPresent(b->b.setRotX(b.getRotX()-.28F*w));
        }
        model.getBone("head").ifPresent(b->b.setRotX(b.getRotX()-.07F*w));
    }
    private static void write(BakedGeoModel model,EvaBodyPose.Sample pose)
    {
        for(String n:pose.rig.keySet())model.getBone(n).ifPresent(b->{EvaRigTransforms.rotate(b,pose.rotations.get(n));var p=pose.positions.get(n);b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);});
    }
    private static void solve(SachielEntity actor,BakedGeoModel model,float partial,float age,boolean left)
    {
        var frame=SachielStrike.sample(actor,age,partial,left);
        String side=left?"l":"r";var upper=model.getBone("arm_"+side).orElse(null);var lower=model.getBone("forearm_"+side).orElse(null);var hand=model.getBone("hand_"+side).orElse(null);if(upper==null||lower==null||hand==null)return;
        var bones=new software.bernie.geckolib.cache.object.GeoBone[]{upper,lower,hand};
        var before=new float[3][6];
        for(int i=0;i<3;i++){var b=bones[i];before[i]=new float[]{b.getRotX(),b.getRotY(),b.getRotZ(),b.getPosX(),b.getPosY(),b.getPosZ()};}
        var rotation=new Quaternionf().rotationTo(new Vector3f(0,0,-1),frame.direction().toVector3f());
        EvaRigTransforms.solveGenericArm(upper,lower,hand,frame.hand().toVector3f(),rotation,new Vector3f(left?1:-1,-.5F,.2F),SachielStrike.root(actor,partial));
        // Full IK only during contact. Blend back to the live walk pose, not a hard-coded idle.
        float blend=SachielStrike.weight(actor.strikeMode(),age);
        for(int i=0;i<3;i++)
        {
            var b=bones[i];var a=before[i];var from=new Quaternionf().rotationZYX(a[2],a[1],a[0]);
            var to=new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX());
            var r=EvaMotionEngineV2.motionQuaternionToAuthoredEuler(from.slerp(to,blend));
            b.setRotX(r.x);b.setRotY(r.y);b.setRotZ(r.z);
            b.setPosX(a[3]+(b.getPosX()-a[3])*blend);b.setPosY(a[4]+(b.getPosY()-a[4])*blend);b.setPosZ(a[5]+(b.getPosZ()-a[5])*blend);
        }
    }
    private SachielStrikePose() {}
}
