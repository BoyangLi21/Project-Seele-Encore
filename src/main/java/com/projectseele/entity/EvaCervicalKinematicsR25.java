package com.projectseele.entity;

/** The head keeps its anatomical socket in every stance. */
public final class EvaCervicalKinematicsR25
{
    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample body,float partial)
    {
        if(eva.isExperimentalUnit()||eva.isBerserk()||eva.isFirstBattleActive()
                ||eva.isNervLogisticsLocked()||EvaShutdownR30.disabled(eva)
                ||EvaAirTransportR31.active(eva)||!body.rig.containsKey("neck"))return;
        float prone=net.minecraft.util.Mth.clamp((eva.rifleStanceLevel(partial)-2.25F)/.75F,0,1);
        prone=prone*prone*(3-2*prone);
        float lookUp=net.minecraft.util.Mth.clamp((-eva.pilotHeadPitchForRender(partial)-2F)/22F,0,1);
        lookUp=lookUp*lookUp*(3-2*lookUp);
        float forwardBlocks=2.5F*prone+1.2F*lookUp*(1-prone),upBlocks=.85F*prone+.70F*lookUp*(1-prone);
        if(forwardBlocks<=0)return;
        var forward=body.matrix("root").transformDirection(new org.joml.Vector3f(0,0,-1));forward.y=0;
        if(forward.lengthSquared()<1e-8F)return;forward.normalize();
        var displacement=forward.mul(forwardBlocks/EvaScale.RENDER_SCALE).add(0,upBlocks/EvaScale.RENDER_SCALE,0);
        String parent=body.rig.get("neck").parent();
        var local=new org.joml.Matrix4f(body.matrix(parent)).invert().transformDirection(displacement);
        // Translate the articulated cervical chain, keeping its bind pivots
        // and weighted neck sleeve intact. The discarded implementation moved
        // the pivot itself backwards, stretching the wrong bind geometry.
        body.positions.get("neck").add(local);body.dirty();
    }
    public static float modelOffset(EvaUnit01Entity eva,float partial)
    {
        // The old prone rebase moved the hinge five world blocks in both Y
        // and Z while the neck skin retained its original bind. Counter-
        // rotating the head then stretched that skin instead of articulating
        // the neck. Clearance must come from the authored joint rotations.
        return 0;
    }
    private EvaCervicalKinematicsR25() {}
}
