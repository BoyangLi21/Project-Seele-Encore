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
    private static float localYaw, localPitch, bank;
    /** The mouse's movement since the last frame drawn in the plug (degrees), from Entity.turn. */
    private static float mouseYaw, mousePitch;

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

    /** The mouse turned the pilot by these degrees; the plug's look takes them on its next frame. */
    public static void mouse(float yaw, float pitch) {
        if (seat == null) return;
        mouseYaw += yaw;
        mousePitch += pitch;
    }

    /** Boarding seats the pilot facing the cabin front. After boarding only the mouse changes the local look. */
    public static Angles plug(EntryPlugCarrierEntity plug, Entity pilot, float partial, float opticalBlend, float bodyYaw) {
        if (seat != plug) {
            seat = plug;
            localYaw = localPitch = 0;
        } else {
            localYaw = Mth.clamp(localYaw + mouseYaw, -65F, 65F);
            localPitch = pitch(localPitch + mousePitch);
        }
        mouseYaw = mousePitch = 0;
        RigidTransform frame = plug.getInterpolatedCanonicalTransform(partial);
        Angles view = angles(frame, localYaw, localPitch, opticalBlend, bodyYaw);
        bank = view.roll();
        if (pilot instanceof net.minecraft.client.player.LocalPlayer self) {
            // The first frame of EVA optics starts from the last frame drawn in the physical seat.
            self.setYRot(view.yaw());
            self.setXRot(view.pitch());
            self.yRotO = view.yaw();
            self.xRotO = view.pitch();
            self.setYHeadRot(view.yaw());
        }
        return view;
    }

    static Angles angles(RigidTransform frame, float localYaw, float localPitch, float opticalBlend, float bodyYaw) {
        Vec3 forward = EntryPlugKinematics.CABIN_VIEW_FORWARD_P;
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
        return new Angles(Mth.rotLerp(opticalBlend, yaw, bodyYaw + localYaw),
                Mth.lerp(opticalBlend, pitch, localPitch), roll);
    }

    @SubscribeEvent
    public static void roll(ViewportEvent.ComputeCameraAngles event) {
        if (seat != null && !event.getCamera().isDetached() && event.getCamera().getEntity() != null && event.getCamera().getEntity().getVehicle() == seat)
            event.setRoll(event.getRoll() + bank);
    }

    private PilotMountView() {}
}
