package com.projectseele.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.world.entity.HumanoidArm;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.client.extensions.common.IClientItemExtensions;

/** Short presentation and return in first person; ordinary carrying stays vanilla. */
public final class NervCardPresentationR44 implements IClientItemExtensions
{
    @Override public boolean applyForgeHandTransform(PoseStack poses,LocalPlayer player,HumanoidArm arm,ItemStack stack,float partial,float equip,float swing)
    {
        if(!player.isUsingItem()||player.getUseItem()!=stack)return false;
        float t=Math.max(0,Math.min(1,(12-player.getUseItemRemainingTicks()+partial)/12));
        float reach=t<.25F?t/.25F:t>.8F?(1-t)/.2F:1;reach=reach*reach*(3-2*reach);
        int side=arm==HumanoidArm.RIGHT?1:-1;
        poses.translate(side*(.56-.25*reach),-.52+.2*reach-equip*.6,-.72-.13*reach);
        poses.mulPose(Axis.YP.rotationDegrees(side*(-8-32*reach)));poses.mulPose(Axis.ZP.rotationDegrees(side*(-4-12*reach)));
        poses.mulPose(Axis.XP.rotationDegrees(-6+16*reach));return true;
    }
}
