package com.projectseele.mixin;

import com.projectseele.world.CityExactShapeUnionR45;
import net.minecraft.nbt.CompoundTag;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Old350 logs/owner bytes are kept intact: only the in-memory NBT passed into stock fromNBT gets a verified ownership marker. */
@Pseudo
@Mixin(targets="com.simibubi.create.content.contraptions.AbstractContraptionEntity",remap=false)
public abstract class CitySavedOwnerUnionMixinR45
{
    @Unique private boolean seele$savedCityOwner;
    @Inject(method="readAdditional",at=@At("HEAD"),remap=false,require=1)
    private void seele$readOwner(CompoundTag tag,boolean spawnData,CallbackInfo callback)
    { seele$savedCityOwner=CityExactShapeUnionR45.legacyCityOwner(tag); }

    @ModifyArg(method="readAdditional",at=@At(value="INVOKE",target="Lcom/simibubi/create/content/contraptions/Contraption;fromNBT(Lnet/minecraft/world/level/Level;Lnet/minecraft/nbt/CompoundTag;Z)Lcom/simibubi/create/content/contraptions/Contraption;"),index=1,remap=false,require=1)
    private CompoundTag seele$markedRead(CompoundTag original)
    {
        if (!seele$savedCityOwner) return original;
        CompoundTag marked=original.copy();marked.putBoolean(CityExactShapeUnionR45.MARKER,true);return marked;
    }
}
