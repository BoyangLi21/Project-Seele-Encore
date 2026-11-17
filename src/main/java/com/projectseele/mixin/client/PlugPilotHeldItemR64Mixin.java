package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.client.cockpit.PilotCockpitR64;
import com.projectseele.entity.EntryPlugCarrierEntity;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.entity.layers.ItemInHandLayer;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R64: a pilot seated in the entry plug has a control yoke in each hand. Whatever the player carried when they
 * sat down (the NERV phone, usually) is not drawn in the figure's hands while it lies in the seat; it is drawn
 * again the moment they leave the capsule. The first-person hand is handled in ClientForgeEvents.onRenderHand.
 */
@Mixin(ItemInHandLayer.class)
public abstract class PlugPilotHeldItemR64Mixin
{
    @Inject(method = "render(Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/MultiBufferSource;ILnet/minecraft/world/entity/LivingEntity;FFFFFF)V",
            at = @At("HEAD"), cancellable = true)
    private void projectseele$nothingHeldInTheSeat(PoseStack pose, MultiBufferSource buffers, int light, LivingEntity entity,
            float limbSwing, float limbSwingAmount, float partial, float age, float headYaw, float headPitch, CallbackInfo callback)
    {
        if (PilotCockpitR64.ON && entity.getVehicle() instanceof EntryPlugCarrierEntity plug && plug.hasCanonicalPose()
                && (!plug.isLockedToEva() || plug.usesPhysicalPilotSeatR52()))
            callback.cancel();
    }
}
