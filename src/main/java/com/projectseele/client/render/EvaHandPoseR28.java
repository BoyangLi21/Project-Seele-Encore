package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Digit adapters define the hinge basis; legacy motion must never animate that basis. */
final class EvaHandPoseR28
{
    private record State(long frame,float[] curl) {}
    private static final Map<EvaUnit01Entity,State> STATES=new WeakHashMap<>();
    static void resetEntityR31(EvaUnit01Entity eva){STATES.remove(eva);}
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(eva.isFirstBattleActive())return EvaMotionEngineV2.BoneWrites.empty();
        if(eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS&&com.projectseele.entity.EvaGameplayMotionR32.sharedBody(eva,partial))
        {STATES.remove(eva);return EvaMotionEngineV2.BoneWrites.empty();}
        if(com.projectseele.entity.EvaBodyPose.hasTerrainStances()
                &&!com.projectseele.entity.EvaShutdownR30.disabled(eva)
                &&!com.projectseele.entity.EvaAirTransportR31.active(eva))
        {
            var body=com.projectseele.entity.EvaBodyPose.sample(eva,partial);
            com.projectseele.entity.EvaHandsR41.apply(eva,body,partial);
            Set<String> names=new LinkedHashSet<>();
            for(String name:body.rig.keySet())if(name.startsWith("finger_"))model.getBone(name).ifPresent(b->{
                EvaRigTransforms.rotate(b,body.rotations.get(name));var p=body.positions.get(name);
                b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);names.add(name);
            });
            STATES.remove(eva);
            return new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.copyOf(names),"MOTION_ENGINE_LIVE_ACTION");
        }
        if(model.getBone("r30_hand_frame_r").isPresent())return EvaUNHandPoseR30.apply(eva,model,partial);
        if(com.projectseele.entity.EvaGameplayMotionR32.sharedHands(eva,partial))
        {STATES.remove(eva);return EvaMotionEngineV2.BoneWrites.empty();}
        if(model.getBone("finger_index_axis_r").isEmpty())return EvaMotionEngineV2.BoneWrites.empty();
        long now=System.nanoTime();var old=STATES.get(eva);
        float blend=old==null?1:(float)(1-Math.exp(-Math.min(.1,(now-old.frame())/1e9)*20));
        float[] values=new float[15];Set<String> written=new LinkedHashSet<>();int i=0;
        int action=com.projectseele.entity.EvaCombatR31.action(eva);
        boolean grabbing=action>=com.projectseele.entity.EvaCombatR31.REACH&&action<=com.projectseele.entity.EvaCombatR31.THROW;
        boolean strike=eva.hasLiveActionForRender(partial)||eva.isFirstBattleActive()||action==1||action==2;
        boolean rifle=eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE;
        boolean weapon=eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS;
        for(String digit:new String[]{"index","middle","ring","little"})
        {
            String axis="finger_"+digit+"_axis_r";
            model.getBone(axis).ifPresent(b->{var bind=b.getInitialSnapshot();b.setRotX(bind.getRotX());b.setRotY(bind.getRotY());b.setRotZ(bind.getRotZ());b.setPosX(bind.getOffsetX());b.setPosY(bind.getOffsetY());b.setPosZ(bind.getOffsetZ());});
            written.add(axis);
            float[] target=grabbing?new float[]{34,48,25}:rifle&&digit.equals("index")?new float[]{18,28,12}:
                    weapon?new float[]{55,74,36}:strike?new float[]{64,82,48}:new float[]{12,20,10};
            String[] names={"finger_"+digit+"_r","finger_"+digit+"_tip_r","finger_"+digit+"_distal_r"};
            for(int joint=0;joint<3;joint++,i++)
            {
                values[i]=old==null?target[joint]:old.curl()[i]+(target[joint]-old.curl()[i])*blend;
                var bone=model.getBone(names[joint]).orElse(null);if(bone==null)continue;
                var bind=bone.getInitialSnapshot();bone.setRotX(bind.getRotX());bone.setRotY(bind.getRotY());
                bone.setRotZ(bind.getRotZ()+(float)Math.toRadians(values[i]));
                bone.setPosX(bind.getOffsetX());bone.setPosY(bind.getOffsetY());bone.setPosZ(bind.getOffsetZ());written.add(names[joint]);
            }
        }
        var thumb=model.getBone("finger_thumb_r").orElse(null);
        var thumbTip=model.getBone("finger_thumb_tip_r").orElse(null);
        var middle=model.getBone("finger_middle_r").orElse(null);
        if(thumb!=null&&thumbTip!=null&&middle!=null)
        {
            var tangent=EvaRigTransforms.pivot(thumbTip).sub(EvaRigTransforms.pivot(thumb));
            var toward=EvaRigTransforms.pivot(middle).sub(EvaRigTransforms.pivot(thumb));
            var axis=tangent.cross(toward);if(axis.lengthSquared()>.00001F)axis.normalize();else axis.set(0,0,1);
            int j=0;for(String name:new String[]{"finger_thumb_r","finger_thumb_tip_r","finger_thumb_distal_r"})
            {
                float target=(weapon||strike||grabbing?new float[]{30,36,18}:new float[]{8,12,6})[j];
                values[12+j]=old==null?target:old.curl()[12+j]+(target-old.curl()[12+j])*blend;
                var bone=model.getBone(name).orElse(null);if(bone!=null)
                {
                    var bind=bone.getInitialSnapshot();var q=new org.joml.Quaternionf().rotationZYX(bind.getRotZ(),bind.getRotY(),bind.getRotX());
                    q.rotateAxis((float)Math.toRadians(values[12+j]),axis);EvaRigTransforms.rotate(bone,q);
                    bone.setPosX(bind.getOffsetX());bone.setPosY(bind.getOffsetY());bone.setPosZ(bind.getOffsetZ());written.add(name);
                }
                j++;
            }
        }
        STATES.put(eva,new State(now,values));
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(written),Set.copyOf(written),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaHandPoseR28(){}
}
