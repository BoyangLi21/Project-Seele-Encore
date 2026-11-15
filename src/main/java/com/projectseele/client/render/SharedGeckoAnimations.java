package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import net.minecraft.Util;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import software.bernie.geckolib.cache.GeckoLibCache;
import software.bernie.geckolib.core.animation.Animation;
import software.bernie.geckolib.loading.object.BakedAnimations;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * GeckoLib bakes every animation file on its own, and the EVA files are about 17 MB of keyframes each
 * once baked. Some of them are byte-for-byte copies of one another (units 00 and 02, unit 01 and UN-01).
 * After each resource load the copies are pointed at one baked set. Baked animations are only read.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class SharedGeckoAnimations
{
    /** The GeckoLib map this class has already looked at; GeckoLib installs a new one on every reload. */
    private static Map<ResourceLocation, BakedAnimations> seen;

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        Map<ResourceLocation, BakedAnimations> baked;
        try { baked = GeckoLibCache.getBakedAnimations(); }
        catch (RuntimeException notInitialised) { return; }
        if (baked == seen || baked.isEmpty()) return;
        seen = baked;
        List<ResourceLocation> files = new ArrayList<>();
        for (ResourceLocation file : baked.keySet()) if (file.getNamespace().equals(ProjectSeele.MODID)) files.add(file);
        if (files.size() < 2) return;
        ResourceManager manager = Minecraft.getInstance().getResourceManager();
        CompletableFuture.supplyAsync(() -> copies(manager, files), Util.backgroundExecutor())
                .thenAcceptAsync(groups -> share(baked, groups), Minecraft.getInstance());
    }

    /** Files with the same bytes, first file of each group first. Runs on a worker. */
    private static List<List<ResourceLocation>> copies(ResourceManager manager, List<ResourceLocation> files)
    {
        Map<String, List<ResourceLocation>> byContent = new LinkedHashMap<>();
        for (ResourceLocation file : files)
        {
            var resource = manager.getResource(file);
            if (resource.isEmpty()) continue;
            try (var stream = resource.get().open())
            {
                String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()));
                byContent.computeIfAbsent(digest, key -> new ArrayList<>()).add(file);
            }
            catch (IOException | NoSuchAlgorithmException unreadable)
            {
                // A file that cannot be read again is left with its own baked set.
            }
        }
        List<List<ResourceLocation>> groups = new ArrayList<>();
        for (List<ResourceLocation> group : byContent.values()) if (group.size() > 1) groups.add(group);
        return groups;
    }

    private static void share(Map<ResourceLocation, BakedAnimations> baked, List<List<ResourceLocation>> groups)
    {
        // Another reload finished meanwhile: its map gets its own pass.
        try { if (GeckoLibCache.getBakedAnimations() != baked) return; }
        catch (RuntimeException notInitialised) { return; }
        int shared = 0;
        for (List<ResourceLocation> group : groups)
        {
            BakedAnimations first = baked.get(group.get(0));
            if (first == null) continue;
            for (int i = 1; i < group.size(); i++)
            {
                BakedAnimations copy = baked.get(group.get(i));
                if (copy == null || copy == first || !sameShape(first, copy)) continue;
                baked.put(group.get(i), first);
                shared++;
            }
        }
        if (shared > 0) ProjectSeele.LOGGER.info("Animation files sharing another file's baked set: {}", shared);
    }

    /** The files have the same bytes; this only guards against a pack swapped while they were being read. */
    private static boolean sameShape(BakedAnimations a, BakedAnimations b)
    {
        if (!a.animations().keySet().equals(b.animations().keySet())) return false;
        for (Map.Entry<String, Animation> entry : a.animations().entrySet())
        {
            Animation other = b.animations().get(entry.getKey());
            if (other.length() != entry.getValue().length() || other.loopType() != entry.getValue().loopType()
                    || other.boneAnimations().length != entry.getValue().boneAnimations().length) return false;
        }
        return true;
    }

    private SharedGeckoAnimations()
    {
    }
}
