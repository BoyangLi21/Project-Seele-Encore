package com.projectseele.client.render;

import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import java.util.Map;
import java.util.HashMap;
import software.bernie.geckolib.cache.object.GeoBone;

/** One exact evaluated pose per source mesh, independent of entity lifetime. */
final class PosedMeshCacheR52
{
    private GeoBone root;
    private GeoBone[] bones;
    private GeoBone[] hierarchy;
    private GeoBone[] correctiveBones = new GeoBone[0];
    private GeoBone commonAncestor;
    private final String owningBone;
    private final Set<String> influences, correctives;
    private int[] channels;
    private WeakReference<Object> owner = new WeakReference<>(null);
    private long frame = Long.MIN_VALUE;
    private int partial;
    private long revision;
    private final Set<Object> sampled = Collections.newSetFromMap(new IdentityHashMap<>());

    PosedMeshCacheR52() { this(null, Set.of(), Set.of()); }
    PosedMeshCacheR52(String owningBone, Set<String> influences, Set<String> correctives)
    {
        this.owningBone = owningBone;
        this.influences = Set.copyOf(influences);
        this.correctives = Set.copyOf(correctives);
    }

    void prepare(Object owner, GeoBone root, long frame, float partial)
    {
        int partialBits = Float.floatToRawIntBits(partial);
        boolean sameEvaluation = this.root == root && this.owner.get() == owner
                && this.frame == frame && this.partial == partialBits;
        if (this.owner.get() != owner) this.owner = new WeakReference<>(owner);
        this.frame = frame;
        this.partial = partialBits;
        boolean changed = false;
        if (!sameEvaluation)
        {
            var current = new ArrayList<GeoBone>();
            collect(root, current);
            changed = this.root != root || this.hierarchy == null
                    || current.size() != this.hierarchy.length;
            if (!changed)
                for (int i = 0; i < this.hierarchy.length; i++)
                    if (this.hierarchy[i] != current.get(i)) { changed = true; break; }
            if (changed)
            {
                this.root = root;
                this.hierarchy = current.toArray(GeoBone[]::new);
                bindDependencies(current);
                this.channels = new int[this.bones.length * 12 + this.correctiveBones.length * 3];
            }
        }
        // Shadow, optical and main passes can run different final writers in
        // one frame. Frame/partial identity is not a pose revision.
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
        for (GeoBone bone : this.correctiveBones)
        {
            changed |= channel(at++, bone.getRotX());
            changed |= channel(at++, bone.getRotY());
            changed |= channel(at++, bone.getRotZ());
        }
        if (changed)
        {
            this.revision++;
            this.sampled.clear();
        }
    }

    private void bindDependencies(ArrayList<GeoBone> current)
    {
        if (this.owningBone == null) { this.bones = this.hierarchy; return; }
        Map<String, GeoBone> named = new HashMap<>();
        for (GeoBone bone : current) named.put(bone.getName(), bone);
        if (!named.containsKey(this.owningBone) || !named.keySet().containsAll(this.influences)
                || !named.keySet().containsAll(this.correctives))
        {
            // The original pairwise path can draw its rigid source when a
            // companion bone is absent. Preserve that loader's fallback/error.
            this.commonAncestor = null;
            this.bones = this.hierarchy;
            this.correctiveBones = new GeoBone[0];
            return;
        }
        GeoBone own = required(named, this.owningBone);
        this.commonAncestor = own;
        for (String name : this.influences)
        {
            GeoBone influence = required(named, name);
            while (!ancestor(this.commonAncestor, influence)) this.commonAncestor = this.commonAncestor.getParent();
        }
        Set<GeoBone> watched = Collections.newSetFromMap(new IdentityHashMap<>());
        watchBelow(own, this.commonAncestor, watched);
        for (String name : this.influences) watchBelow(required(named, name), this.commonAncestor, watched);
        this.bones = current.stream().filter(watched::contains).toArray(GeoBone[]::new);
        this.correctiveBones = this.correctives.stream().sorted().map(name -> required(named, name)).toArray(GeoBone[]::new);
    }
    private static GeoBone required(Map<String, GeoBone> named, String name)
    {
        GeoBone bone = named.get(name);
        if (bone == null) throw new IllegalStateException("Skin dependency bone missing: " + name);
        return bone;
    }
    private static boolean ancestor(GeoBone ancestor, GeoBone bone)
    {
        for (GeoBone at = bone; at != null; at = at.getParent()) if (at == ancestor) return true;
        return false;
    }
    private static void watchBelow(GeoBone bone, GeoBone ancestor, Set<GeoBone> watched)
    { for (GeoBone at = bone; at != ancestor; at = at.getParent()) watched.add(at); }
    GeoBone commonAncestor() { return this.commonAncestor; }

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
