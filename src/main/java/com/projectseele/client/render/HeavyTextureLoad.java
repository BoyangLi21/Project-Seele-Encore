package com.projectseele.client.render;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.platform.TextureUtil;
import com.mojang.blaze3d.systems.RenderSystem;
import com.projectseele.ProjectSeele;
import net.minecraft.Util;
import net.minecraft.client.renderer.texture.SimpleTexture;
import net.minecraft.client.resources.metadata.animation.AnimationMetadataSection;
import net.minecraft.client.resources.metadata.texture.TextureMetadataSection;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.PreparableReloadListener;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.server.packs.resources.SimplePreparableReloadListener;
import net.minecraft.util.profiling.ProfilerFiller;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;

/**
 * Vanilla decodes an entity texture on the render thread the first time something
 * draws with it. GeckoLib swaps in its own texture class and decodes there too, and
 * Oculus does the same for the normal and specular maps. The 4096 x 4096 textures of
 * the UN units and carriers made that a freeze of about two seconds the first time
 * such a unit came into view. Here the decode runs on a worker thread, and the
 * texture is a one-pixel placeholder until the pixels arrive: the unit shows up a
 * moment late instead of stopping the game.
 */
public final class HeavyTextureLoad
{
    /** Implemented on SimpleTexture by the mixin, which can reach the texture's fields. */
    public interface Target
    {
        ResourceLocation projectseele$location();

        int projectseele$nextGeneration();

        void projectseele$finish(NativeImage image, boolean blur, boolean clamp, int generation);
    }

    private record Decoded(NativeImage image, boolean blur, boolean clamp)
    {
    }

    private static final boolean DISABLED = Boolean.getBoolean("projectseele.syncHeavyTextures");
    /** 1024 x 1024 decodes in a couple of frames; anything from there up goes to a worker. */
    private static final long HEAVY_PIXELS = 1024L * 1024L;
    private static final String FOLDER = "textures/entity";
    private static final String GECKOLIB_TEXTURE = "software.bernie.geckolib.cache.texture.AnimatableTexture";

    /** Found on a worker thread at every resource reload, so the render thread never opens a file to ask. */
    private static volatile Set<ResourceLocation> heavy = Set.of();

    public static PreparableReloadListener reloadListener()
    {
        return new SimplePreparableReloadListener<Set<ResourceLocation>>()
        {
            @Override
            protected Set<ResourceLocation> prepare(ResourceManager manager, ProfilerFiller profiler)
            {
                Set<ResourceLocation> found = new HashSet<>();
                Map<ResourceLocation, Resource> textures = manager.listResources(FOLDER,
                        location -> location.getNamespace().equals(ProjectSeele.MODID) && location.getPath().endsWith(".png"));
                for (Map.Entry<ResourceLocation, Resource> entry : textures.entrySet())
                    if (heavy(entry.getValue())) found.add(entry.getKey());
                return Set.copyOf(found);
            }

            @Override
            protected void apply(Set<ResourceLocation> found, ResourceManager manager, ProfilerFiller profiler)
            {
                heavy = found;
                ProjectSeele.LOGGER.info("Entity textures decoded off the render thread: {}", found.size());
            }
        };
    }

    /** True when the load was taken over, so the caller skips its own blocking load. */
    public static boolean begin(SimpleTexture texture, ResourceManager manager)
    {
        if (DISABLED || !RenderSystem.isOnRenderThread()) return false;
        // Other subclasses (preloaded textures, downloaded skins) have their own loading.
        Class<?> type = texture.getClass();
        if (type != SimpleTexture.class && !type.getName().equals(GECKOLIB_TEXTURE)) return false;
        Target target = (Target) texture;
        ResourceLocation location = target.projectseele$location();
        if (!heavy.contains(location)) return false;
        int generation = target.projectseele$nextGeneration();
        TextureUtil.prepareImage(texture.getId(), 0, 1, 1);
        try (NativeImage pixel = new NativeImage(1, 1, false))
        {
            pixel.setPixelRGBA(0, 0, placeholder(location.getPath()));
            pixel.upload(0, 0, 0, 0, 0, 1, 1, false, false, false, false);
        }
        long started = System.nanoTime();
        CompletableFuture.supplyAsync(() -> decode(manager, location), Util.backgroundExecutor())
                .whenComplete((decoded, failure) -> RenderSystem.recordRenderCall(() ->
                {
                    if (failure != null || decoded == null)
                    {
                        ProjectSeele.LOGGER.error("Texture {} could not be decoded off the render thread; it stays blank", location, failure);
                        return;
                    }
                    ProjectSeele.LOGGER.info("Texture {} ({}x{}) decoded off the render thread in {} ms", location,
                            decoded.image().getWidth(), decoded.image().getHeight(), (System.nanoTime() - started) / 1_000_000L);
                    target.projectseele$finish(decoded.image(), decoded.blur(), decoded.clamp(), generation);
                }));
        return true;
    }

    /** Reads the size from the PNG header only. Animated textures keep GeckoLib's loader. */
    private static boolean heavy(Resource resource)
    {
        try (InputStream in = resource.open())
        {
            byte[] head = in.readNBytes(24);
            if (head.length < 24 || head[1] != 'P' || head[2] != 'N' || head[3] != 'G') return false;
            long width = ByteBuffer.wrap(head, 16, 4).getInt() & 0xFFFFFFFFL;
            long height = ByteBuffer.wrap(head, 20, 4).getInt() & 0xFFFFFFFFL;
            if (width * height < HEAVY_PIXELS) return false;
            return resource.metadata().getSection(AnimationMetadataSection.SERIALIZER).isEmpty();
        }
        catch (IOException | RuntimeException failure)
        {
            return false;
        }
    }

    /**
     * ABGR. Colour and eye textures are cutout, so a clear pixel keeps the unit unseen until its
     * pixels are there. The shader pack's maps get neutral values: a flat normal, and no shine or glow.
     */
    private static int placeholder(String path)
    {
        if (path.endsWith("_n.png")) return 0xFFFF8080;
        if (path.endsWith("_s.png")) return 0xFF000000;
        return 0;
    }

    private static Decoded decode(ResourceManager manager, ResourceLocation location)
    {
        try
        {
            Resource resource = manager.getResourceOrThrow(location);
            NativeImage image;
            try (InputStream in = resource.open())
            {
                image = NativeImage.read(in);
            }
            TextureMetadataSection meta = null;
            try
            {
                meta = resource.metadata().getSection(TextureMetadataSection.SERIALIZER).orElse(null);
            }
            catch (RuntimeException | IOException unreadable)
            {
                // Same as vanilla: a broken .mcmeta means default filtering.
            }
            return new Decoded(image, meta != null && meta.isBlur(), meta != null && meta.isClamp());
        }
        catch (IOException failure)
        {
            throw new UncheckedIOException(failure);
        }
    }

    private HeavyTextureLoad()
    {
    }
}
