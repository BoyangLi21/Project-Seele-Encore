package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraft.client.renderer.RenderType;

/** Test against solid scenery, but never write depth between coplanar glow layers. */
public abstract class EnergyGlowR24 extends RenderType
{
    public static final RenderType SMOKE=create("seele_cloud_volume",DefaultVertexFormat.POSITION_COLOR,VertexFormat.Mode.QUADS,32768,false,true,
            CompositeState.builder().setShaderState(POSITION_COLOR_SHADER).setTransparencyState(TRANSLUCENT_TRANSPARENCY)
                    .setCullState(NO_CULL).setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE).createCompositeState(false));
    public static final RenderType CROSS=create("seele_cross_glow",DefaultVertexFormat.POSITION_COLOR,VertexFormat.Mode.QUADS,32768,false,false,
            CompositeState.builder().setShaderState(POSITION_COLOR_SHADER).setTransparencyState(LIGHTNING_TRANSPARENCY)
                    .setCullState(CULL).setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE).createCompositeState(false));
    private EnergyGlowR24()
    {super("seele_cross_glow_definition",DefaultVertexFormat.POSITION_COLOR,VertexFormat.Mode.QUADS,256,false,false,()->{},()->{});}
}
