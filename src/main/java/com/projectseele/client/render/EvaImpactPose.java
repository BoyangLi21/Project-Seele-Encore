package com.projectseele.client.render;
import com.projectseele.entity.*;
import net.minecraft.world.entity.LivingEntity;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;
public final class EvaImpactPose
{
    public static EvaMotionEngineV2.BoneWrites apply(LivingEntity entity,BakedGeoModel model,float partial)
    {
        if(entity instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(entity))return EvaMotionEngineV2.BoneWrites.empty();
        if(entity instanceof EvaUnit01Entity eva&&(eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()))return EvaMotionEngineV2.BoneWrites.empty();
        if(entity instanceof EvaUnit01Entity eva&&eva.isPoweredOn()&&eva.getActivationTicks()==0&&EvaBodyPose.hasTerrainStances()&&!eva.isVisuallyAirborneForRender()&&!eva.hasLiveActionForRender(partial)&&(eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||eva.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE))return EvaMotionEngineV2.BoneWrites.empty();
        var p=EvaImpactResponse.sample(entity,partial);if(p.energy()<.001)return EvaMotionEngineV2.BoneWrites.empty();Set<String> names=new LinkedHashSet<>();
        if(entity instanceof ShamshelEntity shamshel)
        {
            for(String name:List.of("body","head"))model.getBone(name).ifPresent(b->{
                var rotation=com.projectseele.physics.ShamshelContactPoseR48.impact(shamshel,name,new org.joml.Vector3f(b.getRotX(),b.getRotY(),b.getRotZ()),partial);
                b.setRotX(rotation.x);b.setRotY(rotation.y);b.setRotZ(rotation.z);names.add(name);
            });
            return new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
        }
        for(String n:List.of("torso_lower","torso_upper","body","head"))model.getBone(n).ifPresent(b->{float w=n.equals("torso_lower")?.25F:n.equals("head")?.35F:.75F;b.setRotX(b.getRotX()+p.pitch()*w);b.setRotZ(b.getRotZ()+p.roll()*w);if(n.equals("head"))b.setRotX(b.getRotX()+p.head());names.add(n);});
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaImpactPose() {}
}
