package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.registry.ModItems;
import com.projectseele.world.NervAccessReaderEntityR44;
import com.projectseele.world.NervAccessReaderR44;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.blockentity.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.Direction;
import net.minecraft.world.item.*;
import net.minecraft.world.level.block.Blocks;

/** The presented card follows the reader slot; the LED is visible to nearby observers. */
public final class NervAccessReaderRendererR44 implements BlockEntityRenderer<NervAccessReaderEntityR44>
{
    public NervAccessReaderRendererR44(BlockEntityRendererProvider.Context context) {}
    @Override public void render(NervAccessReaderEntityR44 reader,float partial,PoseStack poses,MultiBufferSource buffers,int light,int overlay)
    {
        Direction facing=reader.getBlockState().getValue(NervAccessReaderR44.FACING);
        poses.pushPose();poses.translate(.5,0,.5);poses.mulPose(Axis.YP.rotationDegrees(180-facing.toYRot()));poses.translate(-.5,0,-.5);
        var led=switch(reader.indicator()){case 1->Blocks.ORANGE_CONCRETE;case 2->Blocks.LIME_CONCRETE;case 3->Blocks.RED_CONCRETE;default->Blocks.LIGHT_BLUE_CONCRETE;};
        poses.pushPose();poses.translate(.66,.63,.735);poses.scale(.075F,.025F,.025F);
        Minecraft.getInstance().getBlockRenderer().renderSingleBlock(led.defaultBlockState(),poses,buffers,15728880,OverlayTexture.NO_OVERLAY);poses.popPose();
        float t=reader.swipeProgress(partial);
        if(t>=0&&t<=1)
        {
            poses.pushPose();float u=t*t*(3-2*t);poses.translate(.82-.64*u,.38,.72);poses.scale(.36F,.36F,.36F);
            Minecraft.getInstance().getItemRenderer().renderStatic(new ItemStack(reader.presentedClearance()>=3?ModItems.TERMINAL_DOGMA_ACCESS_CARD.get():ModItems.NERV_EMPLOYEE_CARD.get()),ItemDisplayContext.FIXED,
                    light,OverlayTexture.NO_OVERLAY,poses,buffers,reader.getLevel(),0);poses.popPose();
        }
        poses.popPose();
    }
}
