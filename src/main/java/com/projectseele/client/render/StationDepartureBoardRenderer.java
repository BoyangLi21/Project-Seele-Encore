package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.world.StationDepartureBoardBlock;
import com.projectseele.world.StationDepartureBoardBlockEntity;
import net.minecraft.client.gui.Font;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider;

public final class StationDepartureBoardRenderer implements BlockEntityRenderer<StationDepartureBoardBlockEntity>
{
    private final Font font;
    public StationDepartureBoardRenderer(BlockEntityRendererProvider.Context context) { font=context.getFont(); }
    @Override public void render(StationDepartureBoardBlockEntity board,float partial,PoseStack poses,MultiBufferSource buffers,int light,int overlay)
    {
        boolean direction=board.getBlockState().getValue(StationDepartureBoardBlock.WAYFINDING);
        boolean compact=board.getBlockState().getBlock() instanceof StationDepartureBoardBlock b&&b.compact();
        float scale=board.routeMap()?Math.min(.017F,1.34F/(34+Math.max(0,board.rows().size()-1)*11)):compact?.0104F:direction?.020F:.0145F;
        float width=board.routeMap()?2.64F/scale:compact?75:direction?132:2.7F/scale;
        poses.pushPose();poses.translate(.5,compact?.805:direction?1.73:1.08,.5);
        poses.mulPose(Axis.YP.rotationDegrees(-board.getBlockState().getValue(StationDepartureBoardBlock.FACING).toYRot()));
        // Keep the glyph plane physically clear of the panel; its readability
        // must not depend on a shader's polygon-offset implementation.
        poses.translate(0,0,compact?-.27:.205);poses.scale(scale,-scale,scale);
        line(board.title(),0,0xffedbd55,width,poses,buffers);
        line(board.station(),11,0xffabbec5,width,poses,buffers);
        for(int i=0;i<board.rows().size();i++) line(board.rows().get(i),25+i*(board.routeMap()?11:13),
                board.rows().get(i).contains("本站")?0xffffd572:i==0?0xffe9efde:0xffa9d9ae,width,poses,buffers);
        poses.popPose();
        if(!compact)
        {
            // Suspended signs are approached from both ends of a platform.
            // Keep the rear legend above the original wall-mount bracket.
            float rearScale=direction?.016F:.014F;
            poses.pushPose();poses.translate(.5,direction?1.82:1.16,.5);
            poses.mulPose(Axis.YP.rotationDegrees(180-board.getBlockState().getValue(StationDepartureBoardBlock.FACING).toYRot()));
            poses.translate(0,0,.145);poses.scale(rearScale,-rearScale,rearScale);
            float rearWidth=2.64F/rearScale;
            line(board.title(),0,0xffedbd55,rearWidth,poses,buffers);
            line(board.station(),11,0xffdbe4e6,rearWidth,poses,buffers);
            if(direction)for(int i=0;i<Math.min(3,board.rows().size());i++)
                line(board.routeMap()?board.rows().get(i):reverseArrow(board.rows().get(i)),25+i*13,
                        i==0?0xffe9efde:0xffa9d9ae,rearWidth,poses,buffers);
            poses.popPose();
        }
    }
    private static String reverseArrow(String text)
    {
        if(text.isEmpty()||text.endsWith(" · 直梯"))return text;
        char arrow=switch(text.charAt(0)){case '←'->'→';case '→'->'←';case '↑'->'↓';case '↓'->'↑';default->text.charAt(0);};
        return arrow+text.substring(1);
    }
    private void line(String text,int y,int color,float width,PoseStack poses,MultiBufferSource buffers)
    {
        poses.pushPose();float fit=Math.min(1,width/Math.max(1,font.width(text)));poses.translate(0,y,0);poses.scale(fit,1,1);
        font.drawInBatch(text,-font.width(text)/2F,0,color,false,poses.last().pose(),buffers,Font.DisplayMode.NORMAL,0,15728880);
        poses.popPose();
    }
    @Override public int getViewDistance() { return 96; }
}
