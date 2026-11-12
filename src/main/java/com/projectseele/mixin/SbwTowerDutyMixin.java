package com.projectseele.mixin;

import com.projectseele.world.SbwIdlePause;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;

/** Tells {@link SbwIdlePause} which towers hold a target. */
@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.entity.vehicle.base.AutoAimableEntity", remap = false)
public abstract class SbwTowerDutyMixin implements SbwIdlePause.Tower
{
    @Shadow public abstract String getTargetUUID();

    @Override
    public boolean projectseele$hasTarget()
    {
        // SBW keeps an empty string for no target; anything it did not write counts as one.
        String target = getTargetUUID();
        return target == null || !target.isBlank() && !target.equals("undefined");
    }
}
