package com.projectseele.client.render;

import software.bernie.geckolib.cache.object.GeoBone;

/** A second native render pass may commit new bone channels in the same frame. */
public final class PosedMeshCacheR52Test
{
    public static void main(String[] args)
    {
        var root = new GeoBone(null, "root", false, 0D, false, false);
        var arm = new GeoBone(root, "arm_l", false, 0D, false, false);
        root.getChildBones().add(arm);
        var cache = new PosedMeshCacheR52();
        Object actor = new Object(), skin = new Object();
        cache.prepare(actor, root, 123L, .5F);
        long first = cache.revision();
        cache.remember(skin);
        arm.setRotX(1F);
        cache.prepare(actor, root, 123L, .5F);
        if (cache.revision() <= first || cache.sampled(skin))
            throw new AssertionError("Same frame pose writer retained stale skin and GPU revision");
        cache.remember(skin);
        long unchanged = cache.revision();
        cache.prepare(actor, root, 123L, .5F);
        if (cache.revision() != unchanged || !cache.sampled(skin))
            throw new AssertionError("Identical channels unnecessarily invalidated evaluated skin");
        root.setPosY(2F);
        cache.prepare(actor, root, 123L, .5F);
        if (cache.revision() <= unchanged || cache.sampled(skin))
            throw new AssertionError("Same frame root update retained stale evaluated skin");
        long changed = cache.revision();
        cache.remember(skin);
        cache.prepare(new Object(), root, 124L, .75F);
        if (cache.revision() != changed || !cache.sampled(skin))
            throw new AssertionError("Identical geometry on another actor should share the exact skin");
        var missingCompanion = new PosedMeshCacheR52("arm_l", java.util.Set.of("missing_hand"), java.util.Set.of());
        missingCompanion.prepare(actor, root, 124L, .75F);
        if (missingCompanion.commonAncestor() != null)
            throw new AssertionError("Missing pairwise companion must retain the original rigid fallback path");
        System.out.println("PASS: same-frame arm/root writers invalidate skin and GPU revision; unchanged pose reuses exact buffers");
    }
}
