package com.projectseele.mixin.client;

import com.projectseele.ProjectSeele;
import com.projectseele.client.YashimaBlackoutR64;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Iterator;
import java.util.concurrent.locks.ReentrantLock;

/**
 * R64, the Yashima blackout in Distant Horizons' far view (2.3.4): the tree of far-view sections is made known to
 * the blackout, which has every section's picture built again when the lights go out and come back. The tree's own
 * reloadPos is what Distant Horizons uses when a chunk has changed: the section's stored picture is dropped and a
 * new one is built and put up in place of the old, which stays until then. (Its clearRenderDataCache, the only way
 * the public interface offers, closes every section first: the far view is gone until all of it is built again.)
 */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.render.LodQuadTree", remap = false)
public abstract class YashimaBlackoutDhTreeR64Mixin implements YashimaBlackoutR64.FarView
{
    @Shadow @Final private ReentrantLock treeReadWriteLock;

    @Shadow public abstract void reloadPos(long section);

    @Inject(method = "<init>", at = @At("RETURN"), require = 0)
    private void seele$known(CallbackInfo info)
    {
        YashimaBlackoutR64.farView(this);
    }

    @Unique
    @Override
    public boolean seele$relight()
    {
        long[] sections = new long[1024];
        int count = 0;
        try
        {
            // The tree's nodes are its parent class's to list (QuadTree.nodeIterator), each with its section's place.
            Method nodes = this.getClass().getMethod("nodeIterator");
            Field place = null;
            // Distant Horizons' own threads walk and change the tree under this lock.
            this.treeReadWriteLock.lock();
            try
            {
                for (Iterator<?> each = (Iterator<?>) nodes.invoke(this); each.hasNext(); )
                {
                    Object node = each.next();
                    if (node == null) continue;
                    if (place == null) place = node.getClass().getField("sectionPos");
                    if (count == sections.length) sections = java.util.Arrays.copyOf(sections, count * 2);
                    sections[count++] = place.getLong(node);
                }
            }
            finally
            {
                this.treeReadWriteLock.unlock();
            }
        }
        catch (ReflectiveOperationException | RuntimeException failure)
        {
            ProjectSeele.LOGGER.warn("Yashima blackout: the far view's sections could not be listed", failure);
            return false;
        }
        for (int i = 0; i < count; i++) this.reloadPos(sections[i]);
        return true;
    }
}
