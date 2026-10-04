package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.world.DeadSeaArchiveEntityR45;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.blockentity.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/** Shared immutable geometry, ordinary light and material pass, no screen-space overlay. */
public final class DeadSeaArchiveRendererR45 implements BlockEntityRenderer<DeadSeaArchiveEntityR45>
{
    private static final ResourceLocation TEXTURE=new ResourceLocation("projectseele","textures/block/dead_sea_archive_r45.png");
    private static float[] geometry;
    private static final int[] TRIANGLE_CORNERS={0,8,16,16};
    public DeadSeaArchiveRendererR45(BlockEntityRendererProvider.Context context){}
    public static void clearCache(){geometry=null;}
    private static float[] geometry()
    {
        if(geometry!=null)return geometry;
        try(var stream=Minecraft.getInstance().getResourceManager().open(new ResourceLocation("projectseele","mesh/dead_sea_archive_r45.mesh.json"));
                var reader=new InputStreamReader(stream,StandardCharsets.UTF_8))
        {
            var data=JsonParser.parseReader(reader).getAsJsonObject();var values=data.getAsJsonArray("vertices");
            if(data.get("stride").getAsInt()!=8||values.size()%24!=0||values.size()>2_000_000)throw new IllegalArgumentException("Archive mesh contract");
            geometry=new float[values.size()];for(int i=0;i<values.size();i++){geometry[i]=values.get(i).getAsFloat();if(!Float.isFinite(geometry[i]))throw new IllegalArgumentException("Archive vertex");}
            return geometry;
        }
        catch(Exception failure){throw new IllegalStateException("Archive resource rejected",failure);}
    }
    @Override public void render(DeadSeaArchiveEntityR45 entity,float partial,PoseStack pose,MultiBufferSource buffers,int light,int overlay)
    {
        pose.pushPose();pose.translate(.5,0,.5);pose.mulPose(Axis.YP.rotationDegrees(180-entity.getBlockState().getValue(HorizontalDirectionalBlock.FACING).toYRot()));pose.translate(-.5,0,-.5);
        var consumer=buffers.getBuffer(RenderType.entityCutoutNoCull(TEXTURE));var matrix=pose.last().pose();var normal=pose.last().normal();var vertices=geometry();
        // Minecraft's entity material is QUADS. Repeat the last vertex of
        // each authored triangle instead of grouping unrelated triangles.
        for(int triangle=0;triangle<vertices.length;triangle+=24)for(int offset:TRIANGLE_CORNERS)
        {
            int i=triangle+offset;consumer.vertex(matrix,vertices[i],vertices[i+1],vertices[i+2]).color(255,255,255,255)
                    .uv(vertices[i+3],vertices[i+4]).overlayCoords(overlay).uv2(light).normal(normal,vertices[i+5],vertices[i+6],vertices[i+7]).endVertex();
        }
        pose.popPose();
    }
    @Override public int getViewDistance(){return 64;}
}
