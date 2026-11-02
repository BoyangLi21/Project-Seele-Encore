package com.projectseele.entity;

import com.projectseele.physics.AnatomicalLimbConstraints;
import com.projectseele.physics.CombatBodyProfiles;
import org.joml.Vector3f;

/**
 * Knife strikes while lying prone. The drawn-knife arm is a standing pose,
 * and the prone attacks were authored for the old animation layer that the
 * shared body never draws; the arm stayed in place, driven into the floor.
 * Instead the strike arm drives the blade forward along the ground and
 * draws back: a quick stab for the light strike, a deeper one for the heavy.
 */
final class EvaProneKnifeR56
{
    /** Model units the hand travels forward at full extension (light, heavy). */
    private static final float LIGHT_REACH=1.1F,HEAVY_REACH=1.7F;

    static void stab(EvaUnit01Entity e,EvaBodyPose.Sample body,float partial,float weight)
    {
        float heavy=e.getCockpitSmashAnim(partial),light=e.getCockpitAttackAnim(partial);
        float phase=heavy>0?heavy:light;
        if(phase<=0||phase>=1||weight<=.01F)return;
        // Out fast, a short hold at full reach, and back.
        float extension=phase<.3F?ease(phase/.3F):phase<.5F?1:1-ease((phase-.5F)/.5F);
        var profile=CombatBodyProfiles.get(e);
        if(extension<=0||profile==null)return;
        var hand=body.matrix("hand_r").transformPosition(new Vector3f(body.rig.get("hand_r").pivot()));
        float reach=(heavy>0?HEAVY_REACH:LIGHT_REACH)*extension*weight;
        // Model forward is -Z; the blade skims the ground with a slight rise.
        var target=new Vector3f(hand).add(0,.18F*(float)Math.sin(Math.PI*extension)*weight,-reach);
        AnatomicalLimbConstraints.reachHand(body,profile,"r",target);
    }

    private static float ease(float t)
    {
        t=Math.max(0,Math.min(1,t));
        return t*t*(3-2*t);
    }

    private EvaProneKnifeR56() {}
}
