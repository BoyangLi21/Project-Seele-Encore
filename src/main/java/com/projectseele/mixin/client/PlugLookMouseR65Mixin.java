package com.projectseele.mixin.client;

import com.projectseele.client.cockpit.PilotMountView;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R65 (owner's feedback 2, item 15): the look inside the entry plug takes the mouse's own movement. Read as the
 * difference of the pilot's angles from frame to frame, it also took whatever else moved them, and the look drifted
 * away from the seat's straight ahead while it settled (55 degrees by the lock, 2026-11-24).
 */
@Mixin(Entity.class)
public abstract class PlugLookMouseR65Mixin
{
    @Inject(method = "turn", at = @At("HEAD"))
    private void projectseele$plugLookMouse(double yaw, double pitch, CallbackInfo callback)
    {
        // Entity.turn scales the mouse by 0.15 into degrees.
        if ((Object) this == Minecraft.getInstance().player) PilotMountView.mouse((float) yaw * .15F, (float) pitch * .15F);
    }
}
