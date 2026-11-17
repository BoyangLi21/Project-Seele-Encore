package com.projectseele.client.cockpit;

import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.client.ClientForgeEvents;
import com.projectseele.client.EvaCommandFeedClient;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;

/**
 * R64: the pilot's first-person view rides the Unit's head less hard.
 * <p>
 * The first-person camera stood exactly at the drawn head's optical point, so every bob of the walk, every sway of
 * the run and every thrust of a blow reached the picture whole. The pilot does not sit in the head: the plug shows
 * the head's picture on its wall. Here the eye follows where the head settles (a spring without overshoot) and
 * takes only a share of what the head does about that; in the air and on a landing it takes more than half of it,
 * so a jump still falls and a landing still sinks. The eye never leaves the head by more than a set reach, and by
 * least downwards and backwards, where the Unit's own neck and chest are: no posture change (a crouch, going prone,
 * a knock-down) and no thrust of a blow can leave it inside the body. The arithmetic is ViewSteadyMathR64.
 * <p>
 * Sights are exact rays: with the rifle sight or the cannon scope up the eye is the head's again.
 * Rollback: -Dprojectseele.cockpitR64=false, or cockpit.steadyView = 0 in the client config.
 */
public final class PilotViewSteadyR64
{
    /** A footfall's turn of the view is this share of what it was (the landing's is kept whole). */
    public static final float STEP_KICK = .45F;
    /** A blow's swing and rattle of the view is this share of what it was. */
    public static final float BLOW_SHAKE = .70F;

    /**
     * While a blow is thrown the eye keeps this share of its lag behind the head. A hook turns the trunk under the
     * head: an eye left four or five blocks behind stood where the shoulder came round to, and the shoulder and
     * the upper arm filled a third of the picture (2026-11-17, the drive's second punch: 5.3 blocks from the head).
     * Nearer the head the arm crosses the picture as a blow does and the shoulder stays out of it.
     */
    public static final float BLOW_STEADY = .45F;

    private static final ViewSteadyMathR64 MATH = new ViewSteadyMathR64();
    private static java.util.UUID actor;
    private static long frame;
    private static int airTicks, lastTick = Integer.MIN_VALUE;
    /** What the last frame was given and what it gave back, and what was left out (for the review and the seat's sway). */
    private static Vec3 raw = Vec3.ZERO, out = Vec3.ZERO, removed = Vec3.ZERO;

    private PilotViewSteadyR64() {}

    /** 0 off .. 1 as designed. */
    public static double amount()
    {
        return PilotCockpitR64.ON ? SeeleConfig.COCKPIT_STEADY_VIEW.get() : 0;
    }

    public static float stepKick()
    {
        return (float) Mth.lerp(amount(), 1, STEP_KICK);
    }

    public static float blowShake()
    {
        return (float) Mth.lerp(amount(), 1, BLOW_SHAKE);
    }

    /** The head's optical point the last frame was given. */
    public static Vec3 raw() { return raw; }
    /** What the eye did not take of the head's movement this frame, in the body's frame (right, up, forward; blocks). */
    public static Vec3 removed() { return removed; }

    /** The eye for this frame, given the head's optical point. */
    public static Vec3 apply(EvaUnit01Entity eva, float partial, Vec3 eye)
    {
        // The optical broadcast is another picture of the same frame and must not advance the eye.
        if (EvaCommandFeedClient.isOpticalRenderPass()) return eye;
        raw = eye;
        double amount = amount();
        if (amount <= 0 || held(eva)) { actor = null; out = eye; removed = Vec3.ZERO; return eye; }
        long now = AircraftRenderClockR21.frameNanos();
        Vec3 base = eva.getPosition(partial);
        float yaw = Mth.rotLerp(partial, eva.yBodyRotO, eva.yBodyRot) * Mth.DEG_TO_RAD;
        double sin = Math.sin(yaw), cos = Math.cos(yaw);
        Vec3 d = eye.subtract(base);
        // The body's frame: to its right, up, forward.
        double lx = -d.x * cos - d.z * sin, ly = d.y, lz = -d.x * sin + d.z * cos;
        double dt = (now - frame) / 1e9;
        if (!eva.getUUID().equals(actor) || dt < 0 || dt > .25)
        {
            actor = eva.getUUID(); frame = now; airTicks = 0;
            MATH.reset(lx, ly, lz);
            out = eye; removed = Vec3.ZERO; return eye;
        }
        if (dt == 0) return out;
        frame = now;
        // Whether the Unit is in the air is looked at once a tick; three ticks off the ground is a jump or a fall.
        if (eva.tickCount != lastTick)
        {
            lastTick = eva.tickCount;
            airTicks = eva.onGround() && !eva.isVisuallyAirborneForRender() ? 0 : airTicks + 1;
        }
        boolean sighted = ClientForgeEvents.isRifleSightActive(eva) || ClientForgeEvents.isCannonScopeActive(eva);
        MATH.step(lx, ly, lz, dt, airTicks >= 3, sighted ? 0 : striking(eva, partial) ? amount * BLOW_STEADY : amount);
        double ox = MATH.offsetX, oy = MATH.offsetY, oz = MATH.offsetZ;
        removed = new Vec3(-ox, -oy, -oz);
        out = eye.add(-ox * cos - oz * sin, oy, -ox * sin + oz * cos);
        return out;
    }

    /** A blow is being thrown (a punch, a kick, the knife, the smash): the arms swing through where a lagging eye would be. */
    private static boolean striking(EvaUnit01Entity eva, float partial)
    {
        return eva.getOrdinaryAttackStage() >= 0 || eva.isHeavyMotionActive() || eva.getCockpitAttackAnim(partial) > 0
                || eva.getCockpitSmashAnim(partial) > 0 || eva.getKnifeMotionType(partial) >= 0;
    }

    /** Carried by the facility, an aircraft or a scripted scene, or down: the head is not walking, nothing to steady. */
    private static boolean held(EvaUnit01Entity eva)
    {
        return eva.isNervLogisticsLocked() || eva.isLaunchSequenceActive() || eva.hasActiveCarrierMotion()
                || EvaMechanicalFrameR52.active(eva) || EvaAirTransportR31.active(eva) || EvaShutdownR30.displayed(eva)
                || eva.isFirstBattleActive();
    }
}
