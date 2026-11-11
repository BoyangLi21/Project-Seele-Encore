package com.projectseele.mixin;

import com.projectseele.world.SbwIdlePause;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;

/** Tells {@link SbwIdlePause} which towers are switched on: those look for targets in their own tick. */
@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.entity.vehicle.base.AutoAimableEntity", remap = false)
public abstract class SbwTowerDutyMixin implements SbwIdlePause.Tower
{
    @Shadow public abstract boolean getActive();

    @Override
    public boolean projectseele$onDuty()
    {
        return getActive();
    }
}
