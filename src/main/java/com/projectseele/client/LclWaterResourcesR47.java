package com.projectseele.client;

import com.mojang.blaze3d.platform.NativeImage;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.MultiPackResourceManager;
import net.minecraft.server.packs.resources.Resource;
import java.io.ByteArrayInputStream;
import java.io.IOException;

/** Generated aliases follow the current reload's selected water pack, including PBR/animation resources. */
public final class LclWaterResourcesR47
{
    public static ResourceLocation waterSource(ResourceLocation requested)
    {
        if (!requested.getNamespace().equals("projectseele")) return null;
        for (String kind : new String[] {"still", "flow"})
        {
            String prefix = "textures/block/lcl_" + kind;
            if (!requested.getPath().startsWith(prefix)) continue;
            String suffix = requested.getPath().substring(prefix.length());
            if (!java.util.Set.of(".png", ".png.mcmeta", "_n.png", "_n.png.mcmeta",
                    "_s.png", "_s.png.mcmeta").contains(suffix)) return null;
            return new ResourceLocation("minecraft", "textures/block/water_" + kind + suffix);
        }
        return null;
    }
    public static Resource alias(MultiPackResourceManager manager, ResourceLocation sourceId, Resource source)
    {
        String path = sourceId.getPath();
        if (!(path.equals("textures/block/water_still.png") || path.equals("textures/block/water_flow.png")))
            return source; // exact mcmeta, normal and specular bytes; no recolouring of those channels
        return new Resource(source.source(), () -> new ByteArrayInputStream(neutral(source)),
                source::metadata);
    }
    private static byte[] neutral(Resource source) throws IOException
    {
        try (var stream = source.open(); var image = NativeImage.read(stream))
        {
            // NativeImage is ABGR. Blue/green pack pigment multiplies an orange
            // vertex tint into green; neutralise every frame before atlas upload.
            // HSV value retains the pack's ripple intensity, with alpha unchanged.
            for (int y = 0; y < image.getHeight(); y++)
                for (int x = 0; x < image.getWidth(); x++)
                {
                    int pixel = image.getPixelRGBA(x, y);
                    int value = Math.max(pixel & 255, Math.max((pixel >>> 8) & 255, (pixel >>> 16) & 255));
                    image.setPixelRGBA(x, y, (pixel & 0xff000000) | value | (value << 8) | (value << 16));
                }
            return image.asByteArray();
        }
    }
    private LclWaterResourcesR47() {}
}
