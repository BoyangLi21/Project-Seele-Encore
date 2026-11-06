package com.projectseele.mixin;

import it.unimi.dsi.fastutil.ints.Int2ObjectMap;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.SynchedEntityData;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Overwrite;
import org.spongepowered.asm.mixin.Shadow;

/**
 * Items are only added by define() while an entity is being constructed, so
 * after that the id map is read-only and the read lock taken by every get()
 * and set() is pure overhead. Minecraft 1.20.2 dropped the lock for the same
 * reason; createDataItem keeps its write lock.
 */
@Mixin(SynchedEntityData.class)
public abstract class SynchedEntityDataReadMixin
{
    @Shadow @Final private Int2ObjectMap<SynchedEntityData.DataItem<?>> itemsById;

    /**
     * @author Project SEELE
     * @reason Lock-free lookup in the construction-time item map.
     */
    @Overwrite
    @SuppressWarnings("unchecked")
    private <T> SynchedEntityData.DataItem<T> getItem(EntityDataAccessor<T> key)
    {
        return (SynchedEntityData.DataItem<T>) this.itemsById.get(key.getId());
    }
}
