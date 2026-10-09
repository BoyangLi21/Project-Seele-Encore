package com.projectseele.client.render;

import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import software.bernie.geckolib.cache.object.GeoBone;

/** One exact evaluated pose per source mesh, independent of entity lifetime. */
final class PosedMeshCacheR52
{
    private GeoBone root;
    private GeoBone[] bones;
    private int[] channels;
    private WeakReference<Object> owner = new WeakReference<>(null);
    private long frame = Long.MIN_VALUE;
    private int partial;
    private long revision;
    private final Set<Object> sampled = Collections.newSetFromMap(new IdentityHashMap<>());

    void prepare(Object owner, GeoBone root, long frame, float partial)
    {
        int partialBits = Float.floatToRawIntBits(partial);
        if (this.root == root && this.owner.get() == owner
                && this.frame == frame && this.partial == partialBits)
            return;
        this.owner = new WeakReference<>(owner);
        this.frame = frame;
        this.partial = partialBits;
        var hierarchy = new ArrayList<GeoBone>();
        collect(root, hierarchy);
        boolean changed = this.root != root || this.bones == null
                || hierarchy.size() != this.bones.length;
        if (!changed)
            for (int i = 0; i < this.bones.length; i++)
                if (this.bones[i] != hierarchy.get(i)) { changed = true; break; }
        if (changed)
        {
            this.root = root;
            this.bones = hierarchy.toArray(GeoBone[]::new);
            this.channels = new int[this.bones.length * 12];
        }
        int at = 0;
        for (GeoBone bone : this.bones)
        {
            changed |= channel(at++, bone.getRotX());
            changed |= channel(at++, bone.getRotY());
            changed |= channel(at++, bone.getRotZ());
            changed |= channel(at++, bone.getPosX());
            changed |= channel(at++, bone.getPosY());
            changed |= channel(at++, bone.getPosZ());
            changed |= channel(at++, bone.getScaleX());
            changed |= channel(at++, bone.getScaleY());
            changed |= channel(at++, bone.getScaleZ());
            changed |= channel(at++, bone.getPivotX());
            changed |= channel(at++, bone.getPivotY());
            changed |= channel(at++, bone.getPivotZ());
        }
        if (changed)
        {
            this.revision++;
            this.sampled.clear();
        }
    }

    private boolean channel(int at, float value)
    {
        int bits = Float.floatToRawIntBits(value);
        boolean changed = this.channels[at] != bits;
        this.channels[at] = bits;
        return changed;
    }

    private static void collect(GeoBone bone, ArrayList<GeoBone> result)
    {
        result.add(bone);
        for (GeoBone child : bone.getChildBones()) collect(child, result);
    }

    boolean sampled(Object skin) { return this.sampled.contains(skin); }
    void remember(Object skin) { this.sampled.add(skin); }
    long revision() { return this.revision; }
}
