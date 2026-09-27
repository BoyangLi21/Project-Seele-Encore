package com.projectseele.client.render;

import com.mojang.blaze3d.platform.NativeImage;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.resources.ResourceLocation;
import java.util.HashMap;
import java.util.Map;

/** Change the actual eye surface, including the unlit state, not a floating particle. */
final class EvaEyeMaterialsR42
{
    private static final Map<String, ResourceLocation> CACHE = new HashMap<>();

    static ResourceLocation texture(EvaUnit01Entity eva, ResourceLocation normal)
    {
        if (eva.getUnitVariant() != EvaUnit01Entity.UNIT_01 || eva.isExperimentalUnit()) return normal;
        boolean lit = EvaDorsalMechanism.eyesEnabled(eva);
        if (lit && !eva.isBerserk() && !eva.isFirstBattleActive()) return normal;
        String state = lit ? "berserk" : "dormant";
        return CACHE.computeIfAbsent(normal + "/" + state, key -> create(normal, state, lit));
    }

    private static ResourceLocation create(ResourceLocation source, String state, boolean lit)
    {
        var minecraft = Minecraft.getInstance();
        try (var stream = minecraft.getResourceManager().open(source))
        {
            NativeImage mask = NativeImage.read(stream);
            for (int y = 0; y < mask.getHeight(); y++) for (int x = 0; x < mask.getWidth(); x++)
            {
                int rgba = mask.getPixelRGBA(x, y), alpha = rgba >>> 24;
                if (alpha == 0) continue;
                int luminance = Math.max(rgba & 255, Math.max(rgba >>> 8 & 255, rgba >>> 16 & 255));
                int red = lit ? luminance : 3, green = lit ? luminance / 24 : 3, blue = lit ? luminance / 32 : 4;
                mask.setPixelRGBA(x, y, alpha << 24 | blue << 16 | green << 8 | red);
            }
            var id = new ResourceLocation(ProjectSeele.MODID, "dynamic/unit01_eyes_" + state);
            minecraft.getTextureManager().register(id, new DynamicTexture(mask));
            return id;
        }
        catch (Exception error)
        {
            ProjectSeele.LOGGER.error("Unit-01 eye material unavailable: {}", source, error);
            return source;
        }
    }

    static void reload()
    {
        CACHE.values().stream().distinct().forEach(Minecraft.getInstance().getTextureManager()::release);
        CACHE.clear();
    }
    private EvaEyeMaterialsR42() {}
}
