package com.projectseele.client;

import com.projectseele.ProjectSeele;
import java.lang.reflect.Method;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;

/** Keeps near LOD terrain on screen until the vanilla sections that replace it have been meshed. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class DhNearFillR61
{
    private static final int SAMPLE_EVERY_FRAMES = 6;
    private static final int MINIMUM_COLUMNS = 6;
    private static final float BUILT_FRACTION = .85F;
    private static final float RELEASE_PER_SAMPLE = .08F;

    private static Method instance;
    private static Method sectionReady;
    private static boolean unavailable;
    private static int frames;
    private static volatile float fill;

    public static double current()
    {
        return fill;
    }

    @SubscribeEvent
    public static void frame(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_ENTITIES || unavailable || ++frames % SAMPLE_EVERY_FRAMES != 0) return;
        var minecraft = Minecraft.getInstance();
        if (minecraft.level == null || !bind()) return;
        boolean missing;
        try
        {
            Object renderer = instance.invoke(null);
            missing = renderer != null && nearTerrainMissing(minecraft, event.getFrustum(), event.getCamera().getPosition(), renderer);
        }
        catch (ReflectiveOperationException failure)
        {
            unavailable = true;
            ProjectSeele.LOGGER.error("Embeddium section query rejected; LOD near fade left alone", failure);
            return;
        }
        fill = missing ? 1F : Math.max(0F, fill - RELEASE_PER_SAMPLE);
    }

    private static boolean nearTerrainMissing(Minecraft minecraft, Frustum frustum, Vec3 camera, Object renderer)
            throws ReflectiveOperationException
    {
        var level = minecraft.level;
        if (!level.canSeeSky(BlockPos.containing(camera))) return false;
        int radius = (int) Math.ceil(minecraft.options.getEffectiveRenderDistance() * .7F);
        int centreX = SectionPos.blockToSectionCoord(camera.x), centreZ = SectionPos.blockToSectionCoord(camera.z);
        int columns = 0, built = 0;
        for (int x = -radius; x <= radius; x++)
        {
            for (int z = -radius; z <= radius; z++)
            {
                if (x * x + z * z > radius * radius) continue;
                int cx = centreX + x, cz = centreZ + z;
                boolean loaded = level.hasChunk(cx, cz);
                int top = loaded ? level.getChunk(cx, cz).getHeight(Heightmap.Types.WORLD_SURFACE, 8, 8) : level.getSeaLevel();
                if (top <= level.getMinBuildHeight()) continue;
                int cy = SectionPos.blockToSectionCoord(top - 1);
                var box = new AABB(cx * 16D, cy * 16D, cz * 16D, cx * 16D + 16D, cy * 16D + 16D, cz * 16D + 16D);
                if (!frustum.isVisible(box)) continue;
                columns++;
                if (loaded && (Boolean) sectionReady.invoke(renderer, cx, cy, cz)) built++;
            }
        }
        return columns >= MINIMUM_COLUMNS && built < columns * BUILT_FRACTION;
    }

    private static boolean bind()
    {
        if (sectionReady != null) return true;
        if (!ModList.get().isLoaded("embeddium"))
        {
            unavailable = true;
            return false;
        }
        try
        {
            var type = Class.forName("me.jellysquid.mods.sodium.client.render.SodiumWorldRenderer");
            instance = type.getMethod("instanceNullable");
            sectionReady = type.getMethod("isSectionReady", int.class, int.class, int.class);
            return true;
        }
        catch (ReflectiveOperationException failure)
        {
            unavailable = true;
            ProjectSeele.LOGGER.error("Embeddium section query missing; LOD near fade left alone", failure);
            return false;
        }
    }

    private DhNearFillR61() { }
}
