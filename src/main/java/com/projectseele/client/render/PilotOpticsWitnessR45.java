package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.visual.CombatR31Review;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Opt-in receipt of the real first-person camera and the final rendered head. */
public final class PilotOpticsWitnessR45
{
    private static final String OUTPUT = System.getProperty("projectseele.pilotOpticsWitnessR45", "");
    private static long lastTick = Long.MIN_VALUE;
    private static int rows;
    private static boolean failed;
    private static final java.util.Map<String,Integer> shadowAdmitted=new java.util.LinkedHashMap<>();
    private static final java.util.Map<String,Integer> shadowRejected=new java.util.LinkedHashMap<>();

    public static void shadowAdmission(EvaUnit01Entity eva, String bone, boolean admitted)
    {
        if(OUTPUT.isBlank()||!ShaderShadowPassR44.active()
                ||!java.util.Set.of("head","torso_upper","torso_lower").contains(bone))return;
        var mc=Minecraft.getInstance();
        if(mc.player==null||!mc.options.getCameraType().isFirstPerson()||EvaPilotResolver.controlTarget(mc.player)!=eva)return;
        (admitted?shadowAdmitted:shadowRejected).merge(bone,1,Integer::sum);
    }

    public static void capture(EvaUnit01Entity eva, BakedGeoModel model, float partial, Matrix4f world)
    {
        if (OUTPUT.isBlank() || failed || world == null || rows >= 1400 || ShaderShadowPassR44.active()) return;
        var mc = Minecraft.getInstance();
        if (mc.player == null || mc.getCameraEntity() != mc.player
                || !mc.options.getCameraType().isFirstPerson()
                || EvaPilotResolver.controlTarget(mc.player) != eva) return;
        long tick = eva.level().getGameTime();
        if (tick == lastTick) return;
        var head = model.getBone("head").orElse(null);
        if (head == null) return;
        lastTick = tick;
        Vec3 rendered = new Vec3(EvaRigTransforms.point(head, EvaBodyPose.eyePoint(eva), world));
        Vec3 requested = eva.getPilotCameraSeatPosition(mc.player, partial).add(0, mc.player.getEyeHeight(), 0);
        Vec3 camera = mc.gameRenderer.getMainCamera().getPosition();
        var row = new JsonObject();
        row.addProperty("tick", tick);
        row.addProperty("review_tick", CombatR31Review.stageTicks);
        row.addProperty("stage", CombatR31Review.stageName);
        row.addProperty("variant", eva.getUnitVariant());
        row.addProperty("eva_uuid", eva.getUUID().toString());
        row.addProperty("partial", partial);
        row.addProperty("weapon", eva.getWeapon());
        row.addProperty("stance", eva.rifleStanceLevel(partial));
        row.addProperty("airborne", eva.isVisuallyAirborneForRender());
        row.addProperty("action", eva.hasLiveActionForRender(partial));
        row.addProperty("shared_body", EvaGameplayMotionR32.sharedBody(eva, partial));
        row.add("rendered_head_eye", vector(rendered));
        row.add("requested_eye", vector(requested));
        row.add("actual_camera", vector(camera));
        row.addProperty("request_to_rendered_metres", requested.distanceTo(rendered));
        row.addProperty("camera_to_request_metres", camera.distanceTo(requested));
        if(eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE&&eva.isPoweredOn()&&!eva.isNervLogisticsLocked())
        {
            var optical=eva.getAimDirectionForPoseCapture(partial).normalize();
            var rifle=com.projectseele.entity.EvaRifleKinematics.sample(eva,partial,optical);
            var end=rifle.eye().add(optical.scale(com.projectseele.config.SeeleConfig.EVA_RIFLE_RANGE.get()));
            var hit=eva.level().clip(new net.minecraft.world.level.ClipContext(rifle.eye(),end,
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
            var target=hit.getType()==net.minecraft.world.phys.HitResult.Type.MISS?end:hit.getLocation();
            var delta=target.subtract(rifle.muzzle());
            var aim=new JsonObject();aim.add("muzzle",vector(rifle.muzzle()));aim.add("forward",vector(rifle.forward()));
            aim.add("optical_block_or_end_target",vector(target));aim.addProperty("ready",rifle.ready());aim.addProperty("recoil",rifle.recoil());
            aim.addProperty("server_sight_blend",eva.rifleSightBlendR45(partial));aim.add("stock",vector(rifle.stock()));
            aim.addProperty("raw_ready_signal",eva.rifleReadyBlend(partial));
            aim.addProperty("sight_active",com.projectseele.client.ClientForgeEvents.isRifleSightActive(eva));
            aim.addProperty("target_ray_gap_metres",delta.subtract(rifle.forward().scale(delta.dot(rifle.forward()))).length());
            aim.addProperty("scope","Actual shared muzzle ray versus optical block/end target; not entity hit or server damage proof");
            row.add("rifle_aim",aim);
        }
        var admitted=new JsonObject();shadowAdmitted.forEach(admitted::addProperty);row.add("shadow_admitted_cumulative",admitted);
        var rejected=new JsonObject();shadowRejected.forEach(rejected::addProperty);row.add("shadow_rejected_cumulative",rejected);
        try
        {
            Path path = Path.of(OUTPUT);
            if (!path.isAbsolute()) throw new IllegalArgumentException("Optics receipt requires an absolute output path");
            Files.createDirectories(path.getParent());
            Files.writeString(path, row + System.lineSeparator(), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            rows++;
        }
        catch (Exception error)
        {
            failed = true;
            ProjectSeele.LOGGER.error("R45 pilot optics receipt failed", error);
        }
    }

    private static JsonArray vector(Vec3 point)
    {
        var array = new JsonArray(); array.add(point.x); array.add(point.y); array.add(point.z); return array;
    }
    private PilotOpticsWitnessR45() {}
}
