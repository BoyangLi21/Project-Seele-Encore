package com.projectseele.mixin.client;

import com.projectseele.client.CommanderPoseClient;
import com.projectseele.client.UltramanClientState;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.client.model.PlayerModel;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Applies the iconic elbows-supported, hands-before-mouth commander pose after
 * vanilla has resolved riding, held items and head tracking for this frame.
 */
@Mixin(PlayerModel.class)
public abstract class PlayerModelGendoPoseMixin
{
    @Inject(method = "setupAnim(Lnet/minecraft/world/entity/LivingEntity;FFFFF)V",
            at = @At("TAIL"))
    private void projectSeele$applyCommanderPose(LivingEntity entity,
            float limbSwing, float limbSwingAmount, float ageInTicks,
            float netHeadYaw, float headPitch, CallbackInfo callback)
    {
        if(entity.getVehicle() instanceof com.projectseele.entity.EntryPlugCarrierEntity plug&&plug.hasCanonicalPose()
                &&(!plug.isLockedToEva()||plug.usesPhysicalPilotSeatR52()))
        {
            PlayerModel<?> model=(PlayerModel<?>)(Object)this;
            model.body.xRot=model.body.yRot=model.body.zRot=0;
            model.rightLeg.xRot=model.leftLeg.xRot=-.08F;
            model.rightLeg.yRot=model.leftLeg.yRot=0;
            model.rightLeg.zRot=.025F;model.leftLeg.zRot=-.025F;
            model.rightArm.xRot=model.leftArm.xRot=-.18F;
            model.rightArm.yRot=model.leftArm.yRot=0;
            model.rightArm.zRot=.05F;model.leftArm.zRot=-.05F;
            model.head.yRot=net.minecraft.util.Mth.clamp(model.head.yRot,-.45F,.45F);
            model.head.xRot=net.minecraft.util.Mth.clamp(model.head.xRot,-.25F,.25F);
            model.rightSleeve.copyFrom(model.rightArm);model.leftSleeve.copyFrom(model.leftArm);
            model.rightPants.copyFrom(model.rightLeg);model.leftPants.copyFrom(model.leftLeg);
            model.jacket.copyFrom(model.body);model.hat.copyFrom(model.head);
            return;
        }
        if (entity instanceof AbstractClientPlayer player
                && UltramanClientState.hayataPose(player))
        {
            PlayerModel<?> model = (PlayerModel<?>)(Object)this;
            model.rightArm.xRot = (float)Math.toRadians(-164.0D);
            model.rightArm.yRot = (float)Math.toRadians(-8.0D);
            model.rightArm.zRot = (float)Math.toRadians(8.0D);
            model.leftArm.xRot = (float)Math.toRadians(-64.0D);
            model.leftArm.yRot = (float)Math.toRadians(18.0D);
            model.leftArm.zRot = (float)Math.toRadians(-24.0D);
            model.rightSleeve.copyFrom(model.rightArm);
            model.leftSleeve.copyFrom(model.leftArm);
            model.head.xRot = (float)Math.toRadians(-12.0D);
            model.hat.copyFrom(model.head);
            return;
        }
        if (!entity.isPassenger() || !CommanderPoseClient.isActive(entity))
        {
            return;
        }

        PlayerModel<?> model = (PlayerModel<?>)(Object)this;
        // The vanilla player arm is a single rigid cuboid, so it cannot place
        // an elbow on the desk and then bend the forearm back toward the face.
        // A dedicated two-segment render layer supplies both arms while this
        // pose is active; hide only the vanilla straight-arm geometry.
        model.rightArm.visible = false;
        model.leftArm.visible = false;
        model.rightSleeve.visible = false;
        model.leftSleeve.visible = false;
    }
}
