package com.projectseele.mixin;

import com.projectseele.entity.GaghielEntity;
import com.projectseele.world.TvMarineDirectorR50;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** SBW has its own hit detector; its real projectile must use the same aquatic body and mouth aperture. */
@Pseudo
@Mixin(targets="com.atsuishio.superbwarfare.entity.projectile.ProjectileEntity",remap=false)
public abstract class SbwGaghielContactMixinR50
{
    @Unique private Vec3 seele$marineEntryVelocity;
    @Inject(method="onHitWater",at=@At("HEAD"))
    private void seele$rememberMarineWaterEntry(Vec3 location,net.minecraft.world.phys.BlockHitResult hit,CallbackInfo callback)
    {
        Projectile projectile=(Projectile)(Object)this;
        seele$marineEntryVelocity=TvMarineDirectorR50.waterPenetrationAllowedR50(projectile)?projectile.getDeltaMovement():null;
    }
    @Inject(method="onHitWater",at=@At("RETURN"))
    private void seele$penetratingMarineWaterEntry(Vec3 location,net.minecraft.world.phys.BlockHitResult hit,CallbackInfo callback)
    {
        // The pinned native method still emits its real splash and bubbles.
        // Only one contextual original-gun round per actual trigger retains
        // its momentum across the surface; all other SBW rounds keep 0.1.
        if(seele$marineEntryVelocity!=null)
        {((Projectile)(Object)this).setDeltaMovement(seele$marineEntryVelocity);seele$marineEntryVelocity=null;}
    }
    @Inject(method="getHitResult",at=@At("HEAD"),cancellable=true)
    private void seele$marineContact(Entity target,Vec3 from,Vec3 to,CallbackInfoReturnable<Object> result)
    {
        if(!(target instanceof GaghielEntity boss))return;
        var contact=boss.clipBody(from,to,.15);
        if(contact.isEmpty()){result.setReturnValue(null);return;}
        try
        {
            Vec3 point=contact.get();Projectile projectile=(Projectile)(Object)this;
            TvMarineDirectorR50.rememberProjectileContactR50(projectile,boss,point);
            Class<?> type=Class.forName("com.atsuishio.superbwarfare.world.phys.EntityResult");
            Object hit=type.getConstructor(Entity.class,Vec3.class,boolean.class,boolean.class).newInstance(target,point,false,false);
            result.setReturnValue(hit);
        }
        catch(ReflectiveOperationException failure)
        {throw new IllegalStateException("Pinned SBW EntityResult contract differs; marine contact cannot be substituted",failure);}
    }
}
