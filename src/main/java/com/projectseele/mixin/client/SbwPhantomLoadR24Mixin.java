package com.projectseele.mixin.client;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;

@Pseudo
@Mixin(targets="com.atsuishio.superbwarfare.client.ClientSyncedEntityHandler",remap=false)
public abstract class SbwPhantomLoadR24Mixin
{
    @Redirect(method="syncWorldRender",at=@At(value="INVOKE",target="Lnet/minecraft/world/entity/Entity;load(Lnet/minecraft/nbt/CompoundTag;)V",remap=true),remap=false)
    private static void seele$measureRemoteCopy(Entity entity,CompoundTag tag)
    {com.projectseele.client.SbwPhantomLoadR24.load(entity,tag);}
}
