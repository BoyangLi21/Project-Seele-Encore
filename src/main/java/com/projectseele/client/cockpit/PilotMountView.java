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

    public static Angles plug(EntryPlugCarrierEntity plug, Entity pilot, float partial, float opticalBlend, float bodyYaw) {
        float inputYaw = pilot.getViewYRot(partial), inputPitch = pilot.getViewXRot(partial);
        if (seat != plug) {
            seat = plug;
            localYaw = localPitch = 0;
        } else {
            localYaw = Mth.clamp(localYaw + Mth.wrapDegrees(inputYaw - lastYaw), -65F, 65F);
            localPitch = pitch(localPitch + inputPitch - lastPitch);
        }
        lastYaw = inputYaw;
        lastPitch = inputPitch;
        Angles view = angles(plug.getInterpolatedCanonicalTransform(partial), localYaw, localPitch,
                opticalBlend, inputYaw, inputPitch, bodyYaw);
        bank = view.roll();
        return view;
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
