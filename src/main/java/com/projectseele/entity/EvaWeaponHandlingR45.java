package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.util.Mth;

/** Candidate equipment handoff. The server owns the instant a weapon changes hands. */
public final class EvaWeaponHandlingR45
{
    private static final EntityDataAccessor<CompoundTag> STATE=
            SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data){data.define(STATE,new CompoundTag());}
    public static boolean available(EvaUnit01Entity e)
    {
        return com.projectseele.config.PortableRuntimeOwnersR45.weaponHandling()&&!e.isExperimentalUnit()
                &&EvaAnatomicalHandsR45.knifeAttachment(e)!=null
                &&EvaBodyPose.combatCaptureReadyR31(e,"r32_knife_draw")
                &&EvaBodyPose.combatCaptureReadyR31(e,"r32_knife_stow");
    }
    static CompoundTag swordActionR45(EvaUnit01Entity e)
    {return e.getEntityData().get(STATE).getCompound("sword_action_r45");}
    static void swordActionR45(EvaUnit01Entity e,CompoundTag value)
    {var state=e.getEntityData().get(STATE).copy();if(value.isEmpty())state.remove("sword_action_r45");else state.put("sword_action_r45",value);e.getEntityData().set(STATE,state);}
    static CompoundTag fieldActionR45(EvaUnit01Entity e)
    {return e.getEntityData().get(STATE).getCompound("field_action_r45");}
    static void fieldActionR45(EvaUnit01Entity e,CompoundTag value)
    {var state=e.getEntityData().get(STATE).copy();if(value.isEmpty())state.remove("field_action_r45");else state.put("field_action_r45",value);e.getEntityData().set(STATE,state);}
    public static boolean active(EvaUnit01Entity e)
    {return e.getEntityData().get(STATE).contains("started");}
    public static boolean holding(EvaUnit01Entity e,float partial)
    {
        return available(e)&&e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE&&!active(e)&&!EvaFieldActionsR45.active(e)
                &&!e.hasLiveActionForRender(partial)&&!e.hasLegacyStrikeForRender()
                &&!e.isNervLogisticsLocked()&&!e.isFirstBattleActive()&&!EvaShutdownR30.disabled(e);
    }
    private static EvaBodyPose.Sample hold(EvaUnit01Entity e,EvaBodyPose.Sample body)
    {
        var end=EvaBodyPose.gameplayClip(e,"knife_draw",1);
        for(String name:java.util.List.of("arm_r","forearm_r","wrist_r","hand_r"))
        {
            body.rotations.put(name,new org.joml.Quaternionf(end.rotations.get(name)));
            body.positions.put(name,new org.joml.Vector3f(end.positions.get(name)));
        }
        body.dirty();return body;
    }
    public static boolean request(EvaUnit01Entity e,int weapon)
    {
        if(!available(e)||e.level().isClientSide||active(e)||EvaFieldActionsR45.active(e)||!e.onGround()
                ||e.rifleStanceLevel(0)>.01F||!e.isPoweredOn()||e.isNervLogisticsLocked()
                ||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)||e.getPilotEntity()==null)return false;
        int old=e.getWeapon();
        boolean draw=old==EvaUnit01Entity.WEAPON_FISTS&&weapon==EvaUnit01Entity.WEAPON_KNIFE;
        boolean stow=old==EvaUnit01Entity.WEAPON_KNIFE&&weapon==EvaUnit01Entity.WEAPON_FISTS;
        if(!draw&&!stow)return false;
        var state=new CompoundTag();
        state.put("from_pose",EvaShutdownR30.encode(EvaBodyPose.sample(e,0)));
        state.putInt("before",old);state.putInt("after",weapon);state.putBoolean("draw",draw);
        state.putLong("started",e.level().getGameTime());state.putInt("duration",40);
        e.getEntityData().set(STATE,state);
        return true;
    }
    public static float phase(EvaUnit01Entity e,float partial)
    {
        var s=e.getEntityData().get(STATE);if(!s.contains("started"))return 1;
        return Mth.clamp((e.level().getGameTime()-s.getLong("started")+(e.level().isClientSide?partial:0))
                /(float)Math.max(1,s.getInt("duration")),0,1);
    }
    public static float drawPhase(EvaUnit01Entity e,float partial)
    {float t=phase(e,partial);return e.getEntityData().get(STATE).getBoolean("draw")?t:1-t;}
    private static float ease(float t)
    {t=Mth.clamp(t,0,1);return t*t*t*(10+t*(-15+6*t));}
    public static float closure(EvaUnit01Entity e,float partial)
    {return Mth.clamp((drawPhase(e,partial)-.42F)/.12F,0,1);}
    public static float hatchOpen(EvaUnit01Entity e,float partial)
    {if(!active(e))return 0;float t=drawPhase(e,partial);return ease((t-.04F)/.12F)*(1-ease((t-.72F)/.14F));}
    public static float carriage(EvaUnit01Entity e,float partial)
    {if(!active(e))return 0;float t=drawPhase(e,partial);return ease((t-.12F)/.16F)*(1-ease((t-.64F)/.08F));}
    public static float jointClosure(EvaUnit01Entity e,String digit,int index,float partial)
    {
        float t=closure(e,partial);
        if(digit.equals("thumb"))return ease((drawPhase(e,partial)-.16F)/.20F);
        if(digit.startsWith("cup_")||index==0)return ease(t/.5F);
        return index==1?ease((t-.35F)/.65F):ease((t-.45F)/.55F);
    }
    public static boolean knifeVisible(EvaUnit01Entity e,float partial)
    {
        if(available(e)&&e.isNervLogisticsLocked())return false;
        return active(e)?drawPhase(e,partial)>=.08F:e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE;
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!active(e))return;
        var state=e.getEntityData().get(STATE);
        if(!e.isPoweredOn()||e.getPilotEntity()==null||e.isNervLogisticsLocked()||e.isFirstBattleActive()
                ||EvaShutdownR30.disabled(e)||com.projectseele.physics.CombatBodyDynamics.active(e))
        {e.getEntityData().set(STATE,new CompoundTag());return;}
        float t=phase(e,0),handoff=state.getBoolean("draw")?.54F:.46F;
        if(t>=handoff&&!state.getBoolean("committed"))
        {
            e.commitHandledWeaponR45(state.getInt("after"));
            state=state.copy();state.putBoolean("committed",true);e.getEntityData().set(STATE,state);
        }
        if(t>=1)e.getEntityData().set(STATE,new CompoundTag());
    }
    public static EvaBodyPose.Sample apply(EvaUnit01Entity e,EvaBodyPose.Sample base,float partial)
    {
        if(!active(e))return holding(e,partial)?hold(e,base):base;
        var state=e.getEntityData().get(STATE);float t=phase(e,partial);
        var pose=EvaBodyPose.gameplayClip(e,state.getBoolean("draw")?"knife_draw":"knife_stow",t);
        var rackLocal=pose.matrix("torso_upper").invert().mul(pose.matrix("knife"));
        if(t<.24F)
        {
            var from=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(state.getCompound("from_pose"),from);
            pose=EvaBodyPose.blend(from,pose,ease(t/.24F));
        }
        // The return-to-control blend uses the current underlying stance.
        // Knife attachment is restored after interpolation, never lerped
        // independently through the fingers during the release window.
        if(t>.75F)
        {
            var end=state.getBoolean("draw")?hold(e,base):base;
            pose=EvaBodyPose.blend(pose,end,ease((t-.75F)/.25F));
        }
        if(drawPhase(e,partial)>=.54F)EvaAnatomicalHandsR45.attachKnife(e,pose);
        else
        {
            // While the rack owns the knife, body entry/release blending must
            // not interpolate its transform in hand space. Preserve the
            // carriage in chest space and solve its local transform anew.
            var bone=pose.rig.get("knife");var local=pose.matrix(bone.parent()).invert()
                    .mul(pose.matrix("torso_upper")).mul(rackLocal);
            var q=local.getUnnormalizedRotation(new org.joml.Quaternionf()).normalize();
            var position=local.getTranslation(new org.joml.Vector3f()).sub(bone.pivot())
                    .add(q.transform(new org.joml.Vector3f(bone.pivot())));
            pose.rotations.put("knife",q);pose.positions.put("knife",position);pose.dirty();
        }
        return pose;
    }
    private EvaWeaponHandlingR45(){}
}
