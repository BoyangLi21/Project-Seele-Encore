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
    }
    private ShamshelWhipPose(){}
}
