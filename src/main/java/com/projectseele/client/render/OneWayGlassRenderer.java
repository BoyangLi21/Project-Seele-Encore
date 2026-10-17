package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.registry.ModBlocks;
import com.projectseele.world.OneWayGlassBlock;
import com.projectseele.world.OneWayGlassBlockEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.block.BlockRenderDispatcher;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider;
import net.minecraft.util.RandomSource;
import net.minecraftforge.client.model.data.ModelData;

/** The whole stepped pane becomes optically open from the room, including its ledges. */
public final class OneWayGlassRenderer implements BlockEntityRenderer<OneWayGlassBlockEntity>
{
    private final BlockRenderDispatcher blocks;
    private final RandomSource random=RandomSource.create(19);
    public OneWayGlassRenderer(BlockEntityRendererProvider.Context context){blocks=context.getBlockRenderDispatcher();}

    @Override public void render(OneWayGlassBlockEntity pane,float partial,PoseStack pose,MultiBufferSource buffers,int light,int overlay)
    {
        var level=pane.getLevel();if(level==null)return;
        var camera=Minecraft.getInstance().gameRenderer.getMainCamera().getPosition();var state=pane.getBlockState();
        boolean inside;
        if(state.getValue(OneWayGlassBlock.PYRAMID))
        {
            inside=com.projectseele.client.FacilityFrameClientR52.insidePyramid(Minecraft.getInstance().level,camera);
        }
        else
        {
            var facing=state.getValue(OneWayGlassBlock.FACING);var pos=pane.getBlockPos();
            inside=(camera.x-pos.getX()-.5)*facing.getStepX()+(camera.z-pos.getZ()-.5)*facing.getStepZ()<0;
        }
        if(inside)return;
        // Use the terrain shader and the same model/light sampling as neighboring
        // facade blocks, rather than a differently shaded translucent entity skin.
        var material=ModBlocks.NERV_PYRAMID_PANEL.get().defaultBlockState();random.setSeed(material.getSeed(pane.getBlockPos()));
        blocks.renderBatched(material,pane.getBlockPos(),level,pose,buffers.getBuffer(RenderType.solid()),true,random,ModelData.EMPTY,RenderType.solid());
    }
    @Override public int getViewDistance(){return 4096;}
    @Override public boolean shouldRenderOffScreen(OneWayGlassBlockEntity pane){return true;}
}
