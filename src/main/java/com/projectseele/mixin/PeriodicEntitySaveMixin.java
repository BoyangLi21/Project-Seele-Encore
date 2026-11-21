package com.projectseele.mixin;

import com.projectseele.world.PeriodicEntitySave;
import it.unimi.dsi.fastutil.longs.LongConsumer;
import it.unimi.dsi.fastutil.longs.LongLinkedOpenHashSet;
import it.unimi.dsi.fastutil.longs.LongSet;
import net.minecraft.world.level.entity.PersistentEntitySectionManager;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(PersistentEntitySectionManager.class)
abstract class PeriodicEntitySaveMixin implements PeriodicEntitySave
{
    @Unique private boolean seele$periodic;
    @Unique private final LongLinkedOpenHashSet seele$pending = new LongLinkedOpenHashSet();
    @Unique private LongConsumer seele$saveChunk;

    @Override public void seele$periodicSave(boolean scheduled) { seele$periodic = scheduled; }

    @Redirect(method = "autoSave", at = @At(value = "INVOKE", remap = false,
            target = "Lit/unimi/dsi/fastutil/longs/LongSet;forEach(Lit/unimi/dsi/fastutil/longs/LongConsumer;)V"))
    private void seele$budgetScheduledSave(LongSet chunks, LongConsumer save)
    {
        if (!seele$periodic)
        {
            var it = chunks.iterator();
            while (it.hasNext()) save.accept(it.nextLong());
            return;
        }
        seele$periodic = false;
        seele$pending.addAll(chunks);
        seele$saveChunk = save;
    }

    @Inject(method = "tick", at = @At("RETURN"))
    private void seele$drainScheduledSave(CallbackInfo ci)
    {
        if (seele$saveChunk == null) return;
        long deadline = System.nanoTime() + 2_000_000L;
        while (!seele$pending.isEmpty())
        {
            long chunk = seele$pending.firstLong();
            seele$saveChunk.accept(chunk);
            seele$pending.remove(chunk);
            if (System.nanoTime() >= deadline) return;
        }
        seele$saveChunk = null;
    }

    @Inject(method = "saveAll", at = @At("RETURN"))
    private void seele$finishedFullSave(CallbackInfo ci)
    {
        seele$pending.clear();
        seele$saveChunk = null;
    }
}
