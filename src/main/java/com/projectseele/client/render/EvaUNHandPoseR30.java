package com.projectseele.client.render;

import com.projectseele.entity.*;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Both UN hands share an authored hinge basis, with independently curled phalanges. */
final class EvaUNHandPoseR30
{
    private record State(long at,float[] angles,float[] opposition){}
    private static final Map<EvaUnit01Entity,State> STATES=new WeakHashMap<>();
    static void resetEntityR31(EvaUnit01Entity eva){STATES.remove(eva);}
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(model.getBone("tripo_hand_adapter_r48").isPresent())
        {STATES.remove(eva);return EvaMotionEngineV2.BoneWrites.empty();}
        if(EvaGameplayMotionR32.sharedHands(eva,partial))
        {
            // The complete shared pose already owns these joints. The legacy
            // overlay used to overwrite its thumb opposition after sampling.
            STATES.remove(eva);return new EvaMotionEngineV2.BoneWrites(Set.of(),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
        }
        long now=System.nanoTime();State old=STATES.get(eva);float mix=old==null?1:(float)(1-Math.exp(-Math.min(.1,(now-old.at())/1e9)*20));
        float[] values=new float[30],opposition=new float[2];Set<String> changed=new LinkedHashSet<>();int at=0;
        int action=EvaCombatR31.action(eva);boolean grabbing=action>=EvaCombatR31.REACH&&action<=EvaCombatR31.THROW;
        boolean strike=eva.hasLiveActionForRender(partial)||eva.isFirstBattleActive()||action==EvaCombatR31.AIR_STRIKE||action==EvaCombatR31.AIR_SLAM,weapon=eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS,rifle=eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE;
        float stance=eva.rifleStanceLevel(partial),palmSupport=rifle&&stance>1&&stance<3?(float)Math.pow(Math.sin((stance-1)*Math.PI/2),2):0;
        for(String side:new String[]{"l","r"})for(String digit:new String[]{"index","middle","ring","little","thumb"})
        {
            String adapter="finger_"+digit+"_axis_"+side;
            model.getBone(adapter).ifPresent(b->{var s=b.getInitialSnapshot();b.setRotX(s.getRotX());b.setRotY(s.getRotY());b.setRotZ(s.getRotZ());b.setPosX(s.getOffsetX());b.setPosY(s.getOffsetY());b.setPosZ(s.getOffsetZ());});changed.add(adapter);
            if(digit.equals("thumb"))
            {
                int index=side.equals("l")?0:1;float target=(strike?100:weapon||grabbing?65:0)*(side.equals("l")?1-palmSupport:1);
                opposition[index]=old==null?target:old.opposition()[index]+(target-old.opposition()[index])*mix;
                model.getBone(adapter).ifPresent(b->b.setRotZ(b.getInitialSnapshot().getRotZ()+(float)Math.toRadians(opposition[index])*(side.equals("r")?1:-1)));
            }
            float[] goal=digit.equals("thumb")?(strike?new float[]{45,60,0}:weapon||grabbing?new float[]{28,42,0}:new float[]{6,12,0})
                    :grabbing?new float[]{34,48,25}
                    :rifle&&side.equals("r")&&digit.equals("index")?new float[]{12,24,8}
                    :weapon?new float[]{57,84,54}:strike?new float[]{70,105,70}:new float[]{10,14,7};
            for(int joint=0;joint<3;joint++,at++)
            {
                float target=goal[joint]*(side.equals("l")?1-palmSupport:1);values[at]=old==null?target:old.angles()[at]+(target-old.angles()[at])*mix;
                String name="finger_"+digit+(joint==0?"":joint==1?"_tip":"_distal")+"_"+side;var b=model.getBone(name).orElse(null);if(b==null)continue;
                var s=b.getInitialSnapshot();b.setRotX(s.getRotX());b.setRotY(s.getRotY());b.setRotZ(s.getRotZ()+(float)Math.toRadians(values[at]));
                b.setPosX(s.getOffsetX());b.setPosY(s.getOffsetY());b.setPosZ(s.getOffsetZ());changed.add(name);
            }
        }
        STATES.put(eva,new State(now,values,opposition));return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(changed),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaUNHandPoseR30(){}
}
