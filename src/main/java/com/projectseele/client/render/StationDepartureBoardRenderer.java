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
        if(board.routeMap()&&board.rows().stream().anyMatch(s->s.startsWith("│")||s.startsWith("●")))
        {
            routeMapFace(board,poses,buffers,false);routeMapFace(board,poses,buffers,true);return;
        }
        boolean direction=board.getBlockState().getValue(StationDepartureBoardBlock.WAYFINDING);
        boolean compact=board.getBlockState().getBlock() instanceof StationDepartureBoardBlock b&&b.compact();
        float scale=board.routeMap()?Math.min(.017F,1.34F/(34+Math.max(0,board.rows().size()-1)*11)):compact?.0104F:direction?.020F:.0145F;
        float width=board.routeMap()?2.64F/scale:compact?75:direction?132:2.7F/scale;
        poses.pushPose();poses.translate(.5,compact?.805:direction?1.73:1.08,.5);
        poses.mulPose(Axis.YP.rotationDegrees(-board.getBlockState().getValue(StationDepartureBoardBlock.FACING).toYRot()));
        // Keep the glyph plane physically clear of the panel; its readability
        // must not depend on a shader's polygon-offset implementation.
        poses.translate(0,0,compact?-.27:.205);poses.scale(scale,-scale,scale);
        if(compact&&direction&&!board.routeMap())
        {
            boolean lift=!board.rows().isEmpty()&&board.rows().stream().allMatch(s->s.endsWith(" · 直梯"));
            line(lift?"乘电梯换层":board.station(),0,0xffedbd55,width,poses,buffers);
            for(int i=0;i<Math.min(3,board.rows().size());i++)line(compactDestination(board.rows().get(i),lift),18+i*16,
                    i==0?0xffe9efde:0xffa9d9ae,width,poses,buffers);
        }
        else
        {
            line(board.title(),0,0xffedbd55,width,poses,buffers);
            line(board.station(),11,0xffabbec5,width,poses,buffers);
            for(int i=0;i<board.rows().size();i++) line(board.rows().get(i),25+i*(board.routeMap()?11:13),
                    board.rows().get(i).contains("本站")?0xffffd572:i==0?0xffe9efde:0xffa9d9ae,width,poses,buffers);
        }
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
    private void routeMapFace(StationDepartureBoardBlockEntity board,PoseStack poses,MultiBufferSource buffers,boolean rear)
    {
        var stops=board.rows().stream().filter(s->s.startsWith("│")||s.startsWith("●")).toList();
        int rows=(stops.size()+1)/2;
        float gap=Math.min(.18F,.54F/Math.max(1,rows-1));
        float lettering=Math.min(.0155F,gap/11);
        poses.pushPose();poses.translate(.5,1.78,.5);
        poses.mulPose(Axis.YP.rotationDegrees((rear?180:0)-board.getBlockState().getValue(StationDepartureBoardBlock.FACING).toYRot()));
        poses.translate(0,0,rear?.145:.205);
        physicalLine(board.title(),0,0,.021F,2.60F,0xffedbd55,poses,buffers);
        physicalLine(board.station(),0,.22F,.017F,2.60F,0xffe9efde,poses,buffers);
        for(int i=0;i<stops.size();i++)
        {
            String source=stops.get(i);boolean current=source.contains("本站");
            String label=source.substring(1).trim().replace("  本站","").replace("本站","").trim();
            physicalLine(String.format(java.util.Locale.ROOT,"%02d %s",i+1,label),i<rows?-.67F:.67F,
                    .45F+(i%rows)*gap,lettering,1.24F,current?0xffffd572:0xffdbe9e4,poses,buffers);
        }
        var footer=board.rows().stream().filter(s->!s.startsWith("│")&&!s.startsWith("●")).toList();
        if(!footer.isEmpty())physicalLine(footer.get(0),0,1.12F,.014F,2.60F,0xffa9d9ae,poses,buffers);
        if(footer.size()>1)physicalLine(footer.get(footer.size()-1),0,1.31F,.0105F,2.60F,0xffabbec5,poses,buffers);
        poses.popPose();
    }
    private void physicalLine(String text,float x,float y,float scale,float width,int color,PoseStack poses,MultiBufferSource buffers)
    {
        poses.pushPose();poses.translate(x,-y,0);poses.scale(scale,-scale,scale);
        line(text,0,color,width/scale,poses,buffers);poses.popPose();
    }
    private static String reverseArrow(String text)
    {
        if(text.isEmpty()||text.endsWith(" · 直梯"))return text;
        char arrow=switch(text.charAt(0)){case '←'->'→';case '→'->'←';case '↑'->'↓';case '↓'->'↑';default->text.charAt(0);};
        return arrow+text.substring(1);
    }
    private static String compactDestination(String text,boolean sharedLiftHeader)
    {
        return text.replace("机库登机层","机库登机").replace("总部火车站","总部站")
                .replace("金字塔接驳站","金字塔站").replace("发射区车站","发射区站")
                .replace(" · 直梯",sharedLiftHeader?"":" · 梯");
    }
    private void line(String text,int y,int color,float width,PoseStack poses,MultiBufferSource buffers)
    {
        poses.pushPose();float fit=Math.min(1,width/Math.max(1,font.width(text)));poses.translate(0,y,0);poses.scale(fit,1,1);
        font.drawInBatch(text,-font.width(text)/2F,0,color,false,poses.last().pose(),buffers,Font.DisplayMode.NORMAL,0,15728880);
        poses.popPose();
    }
    @Override public int getViewDistance() { return 96; }
}
