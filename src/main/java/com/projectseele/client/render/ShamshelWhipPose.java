package com.projectseele.client.render;

import com.projectseele.entity.*;
import software.bernie.geckolib.cache.object.BakedGeoModel;

final class ShamshelWhipPose
{
    static void apply(ShamshelEntity actor,BakedGeoModel model,float partial)
    {
        float age=actor.isSweeping()?actor.sweepAge(partial):-1;
        java.util.function.Consumer<software.bernie.geckolib.cache.object.GeoBone> apply=new java.util.function.Consumer<>(){
            @Override public void accept(software.bernie.geckolib.cache.object.GeoBone bone){
                var value=com.projectseele.physics.ShamshelContactPoseR48.base(actor,bone.getName(),
                        new org.joml.Vector3f(bone.getRotX(),bone.getRotY(),bone.getRotZ()),partial);
                bone.setRotX(value.x);bone.setRotY(value.y);bone.setRotZ(value.z);bone.getChildBones().forEach(this);
            }};
        model.topLevelBones().forEach(apply);
        if((com.projectseele.visual.TvCampaignR24Review.ENABLED||com.projectseele.visual.CombatR29Review.ENABLED)&&actor.isSweeping())
        {
            var root=new org.joml.Matrix4f().translation(actor.getPosition(partial).toVector3f()).rotateY((float)Math.toRadians(180-actor.sweepYaw())).scale(5);
            var expected=ShamshelWhipMotion.points(actor,age,partial);int side=actor.sweepSide();
            for(int i=0;i<4;i++)
            {
                var bone=model.getBone("whip_"+(side>0?"l":"r")+"_"+i).orElseThrow();
                float error=EvaRigTransforms.point(bone,EvaRigTransforms.pivot(bone),root).distance(expected.get(i).toVector3f());
                com.projectseele.visual.TvCampaignR24Review.maxWhipRigError=Math.max(com.projectseele.visual.TvCampaignR24Review.maxWhipRigError,error);
                com.projectseele.visual.TvCampaignR24Review.whipRigSamples++;
                com.projectseele.visual.CombatR29Review.maxWhipError=Math.max(com.projectseele.visual.CombatR29Review.maxWhipError,error);com.projectseele.visual.CombatR29Review.whipSamples++;
            }
        }
    }
    private ShamshelWhipPose(){}
}
