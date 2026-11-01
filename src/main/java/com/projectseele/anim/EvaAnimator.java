package com.projectseele.anim;

import java.util.HashMap;
import java.util.Map;

import com.projectseele.entity.CombatFeelR31;
import com.projectseele.entity.CombatReactionsR36;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaCombatR31;
import com.projectseele.entity.EvaFieldActionsR45;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaShieldRigR47;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaSprintR50;
import com.projectseele.entity.EvaSwordActionsR45;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaWeaponHandlingR45;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * Single full-body pose owner for the piloted EVAs (rig keys 0, 1, 2 and the
 * Unit-03 rig 4) whenever the motion pack covers the current state.
 *
 * Server and client evaluate the same function of synced entity signals, so
 * hit hulls and weapon sockets match what is drawn.  States the pack does not
 * cover yet return {@code false} from {@link #owns} and keep the legacy path.
 */
public final class EvaAnimator
{
    private static final boolean ENABLED = !"false".equalsIgnoreCase(System.getProperty("projectseele.anim3", "true"));

    private EvaAnimator() {}

    public static MotionPack.Variant variant(EvaUnit01Entity e)
    {
        if (!ENABLED)
        {
            return null;
        }
        MotionPack pack = MotionPack.get();
        if (pack == null)
        {
            return null;
        }
        if (e instanceof EvaPrototypeEntity un && un.getUNSerial() != 1)
        {
            return null;
        }
        return pack.variant(EvaBodyPose.rigKey(e));
    }

    /** Standing unarmed gait is driven by the pack's strides. */
    public static boolean handlesGait(EvaUnit01Entity e)
    {
        return variant(e) != null && e.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                && !e.isBerserk() && !e.isPilotCrouching() && !e.isPilotProne();
    }

    public static boolean owns(EvaUnit01Entity e, float partial)
    {
        if (variant(e) == null)
        {
            return false;
        }
        if (!e.isPoweredOn() || e.isBerserk() || e.getWeapon() != EvaUnit01Entity.WEAPON_FISTS)
        {
            return false;
        }
        if (e.isNervLogisticsLocked() || e.isFirstBattleActive() || e.isCrucified()
                || e.hasActiveCarrierMotion() || e.isLaunchSequenceActive() || e.hasFixedCannonR52()
                || e.getVisualPose() != EvaUnit01Entity.VISUAL_NORMAL || e.getMotionLabPhysicsPreview() != 0)
        {
            return false;
        }
        if (com.projectseele.physics.CombatBodyDynamics.active(e) || EvaMechanicalFrameR52.active(e)
                || EvaAirTransportR31.active(e) || EvaShutdownR30.disabled(e))
        {
            return false;
        }
        if (e.hasLiveActionForRender(partial) || e.isVisuallyAirborneForRender() || EvaCombatR31.active(e)
                || CombatReactionsR36.active(e) || CombatFeelR31.beat(e) != null)
        {
            return false;
        }
        if (EvaShieldRigR47.equipped(e) || EvaWeaponHandlingR45.active(e) || EvaFieldActionsR45.active(e)
                || EvaSwordActionsR45.active(e))
        {
            return false;
        }
        return e.rifleStanceLevel(partial) < 0.02F && e.rifleCrouchBlend(partial) < 0.02F
                && e.rifleProneBlend(partial) < 0.02F;
    }

    /** World-block distance of one gait cycle for the current walk/run/sprint mix. */
    public static double strideWorld(EvaUnit01Entity e, float run, float dash)
    {
        MotionPack.Variant v = variant(e);
        MotionPack.Clip walk = v.clip("walk");
        MotionPack.Clip running = v.clip("run");
        MotionPack.Clip sprint = v.clip("sprint");
        double stride = Mth.lerp(run, walk.stride, running.stride);
        if (sprint != null)
        {
            stride = Mth.lerp(dash * run, stride, sprint.stride);
        }
        return stride * EvaScale.RENDER_SCALE;
    }

    public static EvaBodyPose.Sample sample(EvaUnit01Entity e, float partial)
    {
        MotionPack.Variant v = variant(e);
        EvaBodyPose.Sample body = EvaBodyPose.neutralForTransportR32(e);
        for (var bone : body.rig.values())
        {
            if (bone.name().contains("_axis_"))
            {
                body.rotations.put(bone.name(), new Quaternionf(bone.bindRotation()));
            }
        }
        float phase = e.rifleGaitPhase(partial);
        phase -= Mth.floor(phase);
        float move = Mth.clamp(e.rifleMoveBlend(partial), 0, 1);
        float run = Mth.clamp(e.rifleRunBlend(partial), 0, 1);
        float dash = Mth.clamp(EvaSprintR50.blend(e, partial), 0, 1);
        double seconds = (e.level().getGameTime() + (double) partial) / 20.0;

        Map<String, Quaternionf> rot = new HashMap<>();
        Vector3f root = new Vector3f();
        float wIdle = 1 - move;
        float wWalk = move * (1 - run);
        float wRun = move * run * (1 - dash);
        float wSprint = move * run * dash;
        MotionPack.Clip sprint = v.clip("sprint");
        if (sprint == null)
        {
            wRun += wSprint;
            wSprint = 0;
        }
        MotionPack.Clip idle = v.clip("idle");
        if (wIdle > 1e-3F)
        {
            float pos = (float) ((seconds / idle.duration) % 1.0);
            idle.accumulate(idle.framePosition(pos), wIdle, rot, root);
        }
        if (wWalk > 1e-3F)
        {
            MotionPack.Clip walk = v.clip("walk");
            walk.accumulate(walk.framePosition(phase), wWalk, rot, root);
        }
        if (wRun > 1e-3F)
        {
            MotionPack.Clip running = v.clip("run");
            running.accumulate(running.framePosition(phase), wRun, rot, root);
        }
        if (wSprint > 1e-3F)
        {
            sprint.accumulate(sprint.framePosition(phase), wSprint, rot, root);
        }
        for (var entry : rot.entrySet())
        {
            if (body.rig.containsKey(entry.getKey()))
            {
                body.rotations.put(entry.getKey(), entry.getValue().normalize());
            }
        }
        body.positions.get("root").set(root);
        body.dirty();
        return body;
    }
}
