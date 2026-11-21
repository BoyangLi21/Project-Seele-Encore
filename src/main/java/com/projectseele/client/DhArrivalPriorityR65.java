package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.TvWorldPreviewTerrain;
import it.unimi.dsi.fastutil.longs.Long2IntOpenHashMap;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.concurrent.TimeUnit;

/** Prioritizes requested, final-detail meshes visible after a GeoFront arrival. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class DhArrivalPriorityR65
{
    private static final long ARRIVAL_WINDOW = TimeUnit.SECONDS.toNanos(75);
    private static final int[] SURFACE_DISTANCES = {144, 384, 896};
    private static volatile Long2IntOpenHashMap visible;
    private static ClientLevel previousLevel;
    private static Vec3 previousPosition, sampledPosition;
    private static long deadline, lastSample;
    private static float sampledYaw, sampledPitch;
    private static boolean unavailable;
    private static Field sectionPosition;

    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut event)
    {
        visible = null;
        previousLevel = null;
        previousPosition = null;
        sampledPosition = null;
        deadline = 0;
    }

    @SubscribeEvent public static void camera(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_ENTITIES) return;
        var level = Minecraft.getInstance().level;
        var camera = event.getCamera();
        var eye = camera.getPosition();
        long now = System.nanoTime();
        if (level != previousLevel || previousPosition == null || previousPosition.distanceToSqr(eye) > 128 * 128)
        {
            deadline = now + ARRIVAL_WINDOW;
            sampledPosition = null;
        }
        previousLevel = level;
        previousPosition = eye;
        if (level == null || !FacilitySchemaV2.DIMENSION.equals(level.dimension()) || now >= deadline)
        {
            visible = null;
            return;
        }
        float yaw = camera.getYRot(), pitch = camera.getXRot();
        if (sampledPosition != null && (now - lastSample < 350_000_000L ||
                (sampledPosition.distanceToSqr(eye) < 64 && Math.abs(yaw - sampledYaw) < 4 && Math.abs(pitch - sampledPitch) < 4))) return;
        sampledPosition = eye;
        sampledYaw = yaw;
        sampledPitch = pitch;
        lastSample = now;
        float halfWidth = 1 / event.getProjectionMatrix().m00(), halfHeight = 1 / event.getProjectionMatrix().m11();
        Vec3 forward = Vec3.directionFromRotation(pitch, yaw), right = Vec3.directionFromRotation(0, yaw + 90);
        Vec3 up = right.cross(forward);
        var scores = new Long2IntOpenHashMap();
        for (int x = -64; x <= 64; x += 64)
            for (int z = -64; z <= 64; z += 64) add(scores, eye.x + x, eye.z + z, 64);

        boolean dome = inCavern(eye.x, eye.y, eye.z);
        for (int row = -4; row <= 4; row++)
        {
            for (int column = -6; column <= 6; column++)
            {
                var ray = forward.add(right.scale(column * halfWidth / 6.3)).add(up.scale(row * halfHeight / 4.3)).normalize();
                int weight = Math.abs(column) <= 4 && Math.abs(row) <= 2 ? 8 : 3;
                if (dome)
                {
                    for (int distance = 32; distance <= 3712; distance += 32)
                    {
                        double x = eye.x + ray.x * distance, y = eye.y + ray.y * distance, z = eye.z + ray.z * distance;
                        if (!inCavern(x, y, z)) { add(scores, x, z, weight); break; }
                    }
                }
                else
                {
                    for (int distance : SURFACE_DISTANCES)
                        add(scores, eye.x + ray.x * distance, eye.z + ray.z * distance, weight);
                }
            }
        }
        visible = scores;
    }

    private static boolean inCavern(double x, double y, double z)
    {
        if (y <= TvWorldPreviewTerrain.FLOOR_Y - 12 || y >= TvWorldPreviewTerrain.ROOF_Y + 2) return false;
        return y <= TvWorldPreviewTerrain.roof((int)Math.floor(x), (int)Math.floor(z));
    }

    private static void add(Long2IntOpenHashMap scores, double x, double z, int weight)
    {
        // DH 2.3.4 section positions store the detail byte, then signed 28-bit X and Z.
        for (int detail = 6; detail <= 10; detail++)
        {
            int sx = ((int)Math.floor(x)) >> detail, sz = ((int)Math.floor(z)) >> detail;
            scores.addTo(position(detail, sx, sz), weight);
            if (detail > 6)
            {
                // Cover the visible spans between rays on steep surfaces, including tile edges.
                int neighbor = Math.max(1, weight / 4);
                scores.addTo(position(detail, sx - 1, sz), neighbor);
                scores.addTo(position(detail, sx + 1, sz), neighbor);
                scores.addTo(position(detail, sx, sz - 1), neighbor);
                scores.addTo(position(detail, sx, sz + 1), neighbor);
            }
        }
    }

    private static long position(int detail, int x, int z)
    {
        return detail | ((x & 0x0FFFFFFFL) << 8) | ((z & 0x0FFFFFFFL) << 36);
    }

    public static void sort(ArrayList<Object> sections, Comparator<Object> nativeOrder)
    {
        var scores = visible;
        if (scores == null || unavailable || sections.size() < 2) { sections.sort(nativeOrder); return; }
        var ranks = new IdentityHashMap<Object, Integer>();
        try
        {
            if (sectionPosition == null) sectionPosition = sections.get(0).getClass().getField("pos");
            for (Object section : sections)
            {
                int score = scores.get(sectionPosition.getLong(section));
                if (score != 0) ranks.put(section, score);
            }
        }
        catch (ReflectiveOperationException failure)
        {
            unavailable = true;
            ProjectSeele.LOGGER.warn("Could not prioritize distant terrain after arrival", failure);
        }
        sections.sort((left, right) -> {
            int order = Integer.compare(ranks.getOrDefault(right, 0), ranks.getOrDefault(left, 0));
            return order != 0 ? order : nativeOrder.compare(left, right);
        });
    }

    private DhArrivalPriorityR65() {}
}
