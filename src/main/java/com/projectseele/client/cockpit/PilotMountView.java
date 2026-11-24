package com.projectseele.client.cockpit;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.RigidTransform;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Mouse look inside a moving seat. The same interpolated transform drives the eye and the horizon. */
@Mod.EventBusSubscriber(modid = "projectseele", value = Dist.CLIENT)
public final class PilotMountView {
    private static EntryPlugCarrierEntity seat;
    private static float lastYaw, lastPitch, localYaw, localPitch, bank;
    /** Where the pilot looked climbing in, against the seat's straight ahead; it settles away once the insertion begins. */
    private static float boardYaw, boardPitch;
    private static long frameNanos;
    /** The settling's time constant: 95% of the way to the seat's straight ahead in about 1.4 seconds. */
    static final float SETTLE_SECONDS = .45F;

    public record Angles(float yaw, float pitch, float roll) {}

    public static boolean fixed(EvaUnit01Entity eva) {
        return eva.isNervLogisticsLocked() || eva.isLaunchSequenceActive() || eva.hasActiveCarrierMotion()
                || EvaMechanicalFrameR52.active(eva) || EvaAirTransportR31.active(eva)
                || eva.isCrucified() || eva.fixedCannonOperatingR52();
    }

    public static float yaw(float input, float centre) {
        return centre + Mth.clamp(Mth.wrapDegrees(input - centre), -65F, 65F);
    }

    public static float pitch(float input) { return Mth.clamp(input, -55F, 60F); }

    public static void leave() { seat = null; bank = 0; }

    /**
     * R65 (owner's feedback 2, item 15): the first picture in the plug turned the view by itself. It jumped to the
     * seat's straight ahead whatever way the pilot faced climbing in (from the east platform, the hatch is to the
     * pilot's right: a turn of some 80 degrees to the left and 36 up, in one frame); and the pilot's own angles
     * stayed as they were outside, so the glide into the Unit's optics swung the view again, back to them.
     * Now the first pictures look where the pilot looked; once the hatch is shut and the insertion begins, that
     * look settles to the seat's straight ahead (the cabin's own picture, and the Unit's front once synchronised)
     * in about a second and a half, before the capsule itself moves; the mouse keeps the seat's range about it.
     * The pilot's own angles follow what is shown, so nothing turns at the hand-over to the Unit's optics.
     */
    public static Angles plug(EntryPlugCarrierEntity plug, Entity pilot, float partial, float opticalBlend, float bodyYaw) {
        float inputYaw = pilot.getViewYRot(partial), inputPitch = pilot.getViewXRot(partial);
        RigidTransform frame = plug.getInterpolatedCanonicalTransform(partial);
        long now = System.nanoTime();
        if (seat != plug) {
            seat = plug;
            float[] look = local(frame, inputYaw, inputPitch);
            boardYaw = look[0];
            boardPitch = look[1];
            localYaw = localPitch = 0;
        } else {
            localYaw = Mth.clamp(localYaw + Mth.wrapDegrees(inputYaw - lastYaw), -65F, 65F);
            localPitch = pitch(localPitch + inputPitch - lastPitch);
            if (plug.getInsertionStage() != EntryPlugCarrierEntity.STAGE_SUSPENDED && plug.getInsertionStage() != EntryPlugCarrierEntity.STAGE_OCCUPIED) {
                float keep = settle((now - frameNanos) / 1e9F);
                boardYaw *= keep;
                boardPitch *= keep;
                if (Math.abs(boardYaw) < .01F && Math.abs(boardPitch) < .01F) boardYaw = boardPitch = 0;
            }
        }
        frameNanos = now;
        Angles view = angles(frame, localYaw + boardYaw, Mth.clamp(localPitch + boardPitch, -89F, 89F), opticalBlend, inputYaw, inputPitch, bodyYaw);
        if (pilot instanceof net.minecraft.client.player.LocalPlayer self) {
            // What the mouse adds between two frames still reaches the next one; nothing else turns the pilot.
            self.setYRot(view.yaw());
            self.setXRot(view.pitch());
            self.yRotO = view.yaw();
            self.xRotO = view.pitch();
            self.setYHeadRot(view.yaw());
            lastYaw = view.yaw();
            lastPitch = view.pitch();
        } else {
            lastYaw = inputYaw;
            lastPitch = inputPitch;
        }
        bank = view.roll();
        return view;
    }

    /** The share of the boarding look kept over a frame of this many seconds (a long or a missing frame counts as a tenth of a second). */
    static float settle(float seconds) {
        return (float) Math.exp(-Mth.clamp(seconds, 0F, .1F) / SETTLE_SECONDS);
    }

    /** The seat's look (yaw from straight ahead, pitch) that points where the world angles point. */
    static float[] local(RigidTransform frame, float yaw, float pitch) {
        Vec3 forward = EntryPlugKinematics.PILOT_VIEW_FORWARD_P;
        Vec3 side = forward.cross(new Vec3(0, 1, 0)).normalize();
        Vec3 up = side.cross(forward);
        Vec3 look = frame.inverse().transformVector(Vec3.directionFromRotation(pitch, yaw));
        double el = -Math.asin(Mth.clamp(look.dot(up), -1, 1));
        double az = Math.atan2(look.dot(side), look.dot(forward));
        return new float[]{(float) Math.toDegrees(az), (float) Math.toDegrees(el)};
    }

    static Angles angles(RigidTransform frame, float localYaw, float localPitch, float opticalBlend,
            float inputYaw, float inputPitch, float bodyYaw) {
        Vec3 forward = EntryPlugKinematics.PILOT_VIEW_FORWARD_P;
        Vec3 side = forward.cross(new Vec3(0, 1, 0)).normalize();
        Vec3 up = side.cross(forward);
        double az = Math.toRadians(localYaw), el = Math.toRadians(localPitch);
        Vec3 horizontal = forward.scale(Math.cos(az)).add(side.scale(Math.sin(az)));
        Vec3 direction = frame.transformVector(horizontal.scale(Math.cos(el)).subtract(up.scale(Math.sin(el))));
        Vec3 headUp = frame.transformVector(up.scale(Math.cos(el)).add(horizontal.scale(Math.sin(el))));
        float yaw = (float) Math.toDegrees(Math.atan2(-direction.x, direction.z));
        float pitch = (float) -Math.toDegrees(Math.atan2(direction.y, direction.horizontalDistance()));
        Vec3 screenLeft = new Vec3(Math.cos(Math.toRadians(yaw)), 0, Math.sin(Math.toRadians(yaw)));
        Vec3 screenUp = direction.cross(screenLeft);
        float roll = (float) Math.toDegrees(Math.atan2(-headUp.dot(screenLeft), headUp.dot(screenUp))) * (1 - opticalBlend);
        return new Angles(Mth.rotLerp(opticalBlend, yaw, yaw(inputYaw, bodyYaw)),
                Mth.lerp(opticalBlend, pitch, pitch(inputPitch)), roll);
    }

    @SubscribeEvent
    public static void roll(ViewportEvent.ComputeCameraAngles event) {
        if (seat != null && !event.getCamera().isDetached() && event.getCamera().getEntity() != null && event.getCamera().getEntity().getVehicle() == seat)
            event.setRoll(event.getRoll() + bank);
    }

    private PilotMountView() {}
}
