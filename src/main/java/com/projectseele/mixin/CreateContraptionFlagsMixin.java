package com.projectseele.mixin;

import it.unimi.dsi.fastutil.objects.Object2BooleanArrayMap;
import it.unimi.dsi.fastutil.objects.Object2BooleanMap;
import it.unimi.dsi.fastutil.objects.Object2BooleanOpenHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.Tag;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Create keeps one flag per contraption block in an array map, which walks every earlier entry on each put and
 * each lookup. A city district carries tens of thousands of blocks, so reading one stalled the server for about a
 * second, and each client again. Create only puts, looks up and clears this map, so a hash map answers the same.
 */
@Pseudo
@Mixin(targets="com.simibubi.create.content.contraptions.Contraption",remap=false)
public abstract class CreateContraptionFlagsMixin
{
    @Shadow(remap=false) public Object2BooleanMap<BlockPos> isLegacy;

    /** The reader clears the map first, so an empty one in its place changes nothing it holds. */
    @Inject(method="readBlocksCompound",at=@At("HEAD"),remap=false,require=1)
    private void seele$hashedFlags(Tag compound,Level level,boolean paletted,CallbackInfo callback)
    {
        if(isLegacy.getClass()==Object2BooleanArrayMap.class)isLegacy=new Object2BooleanOpenHashMap<>();
    }
}
