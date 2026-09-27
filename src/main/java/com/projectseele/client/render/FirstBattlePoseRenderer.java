package com.projectseele.client.render;

import com.projectseele.entity.FirstBattleClip;
import com.projectseele.entity.FirstBattleSignals;
import net.minecraft.world.entity.Entity;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.Map;
import java.util.HashMap;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.GeoBone;

/** A single pose writer for both actors of the authored battle. */
public final class FirstBattlePoseRenderer
{
    private static final class LastPose
    {
        long tick,frame;
        final Map<String,float[]> bones=new HashMap<>();
    }
    private static final com.projectseele.util.WeakIdentityMap<Entity,LastPose> LAST=new com.projectseele.util.WeakIdentityMap<>();
    /** Record the pose that was really drawn, after all ordinary motion writers.
     * It is reused only for the non-contact entry window of a nearby scene. */
    public static void remember(Entity entity,GeoBone root)
    {
        if(!(entity instanceof com.projectseele.entity.SachielEntity)
                &&!(entity instanceof com.projectseele.entity.EvaUnit01Entity eva&&eva.getUnitVariant()==1&&!eva.isExperimentalUnit()))return;
        if(entity instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(entity))return;
        var snapshot=LAST.computeIfAbsent(entity,key->new LastPose());long frame=FirstBattleSignals.clientFrameTime();
        if(snapshot.frame==frame)return;snapshot.frame=frame;snapshot.tick=entity.level().getGameTime();record(root,snapshot);
    }
    private static void record(GeoBone bone,LastPose snapshot)
    {
        var a=snapshot.bones.computeIfAbsent(bone.getName(),key->new float[6]);
        a[0]=bone.getRotX();a[1]=bone.getRotY();a[2]=bone.getRotZ();a[3]=bone.getPosX();a[4]=bone.getPosY();a[5]=bone.getPosZ();
        for(var child:bone.getChildBones())record(child,snapshot);
    }
    public static EvaMotionEngineV2.BoneWrites apply(Entity entity,BakedGeoModel model,float partial)
    {
        if(!(entity instanceof FirstBattleSignals.Actor actor)||!actor.firstBattleSignals().active(entity)||!FirstBattleClip.ready())return EvaMotionEngineV2.BoneWrites.empty();
        float time=actor.firstBattleSignals().time(entity,partial);
        var pose=FirstBattleClip.pose(actor.isFirstBattleEva(),time);
        var origin=LAST.get(entity);float entry=Math.min(1,time/.4F);entry=entry*entry*entry*(10+entry*(-15+6*entry));
        boolean blend=origin!=null&&entity.level().getGameTime()-origin.tick<16&&entry<1;
        Set<String> rotations=new LinkedHashSet<>(),positions=new LinkedHashSet<>();
        for(int i=0;i<pose.names().length;i++)
        {
            String name=pose.names()[i];var bone=model.getBone(name).orElse(null);if(bone==null)continue;
            var euler=EvaMotionEngineV2.motionQuaternionToAuthoredEuler(pose.rotations()[i]);var p=pose.positions()[i];
            bone.setRotX(-euler.x);bone.setRotY(-euler.y);bone.setRotZ(euler.z);bone.setPosX(p.x);bone.setPosY(p.y);bone.setPosZ(p.z);
            var old=blend?origin.bones.get(name):null;
            if(old!=null)
            {
                var q=new Quaternionf().rotationZYX(old[2],old[1],old[0]).slerp(new Quaternionf().rotationZYX(euler.z,-euler.y,-euler.x),entry);
                EvaRigTransforms.rotate(bone,q);
                bone.setPosX(old[3]+(p.x-old[3])*entry);bone.setPosY(old[4]+(p.y-old[4])*entry);bone.setPosZ(old[5]+(p.z-old[5])*entry);
            }
            bone.setScaleX(1);bone.setScaleY(1);bone.setScaleZ(1);
            rotations.add(name);positions.add(name);
        }
        if(actor.isFirstBattleEva())for(String side:new String[]{"l","r"})
        {
            model.getBone("shin_"+side).ifPresent(b->EvaRigTransforms.hinge(b,EvaRigTransforms.knee(b)));
            model.getBone("forearm_"+side).ifPresent(b->EvaRigTransforms.hinge(b,EvaRigTransforms.elbow(b,side)));
        }
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations),Set.copyOf(positions),EvaMotionEngineV2.OWNER_LIVE_ACTION);
    }
    private FirstBattlePoseRenderer() {}
}
