package com.projectseele.client.render;

import net.minecraft.client.resources.language.I18n;
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
    private static final char SPLIT='|';
    private static final float SUB_OFFSET=8.4F,SUB_SCALE=.56F;
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
            if(board.roomPlaqueR52())
            {
                line(board.station(),8,0xffe2e5df,width,poses,buffers);
                for(int i=0;i<Math.min(3,board.rows().size());i++)
                    line(board.rows().get(i),25+i*13,i==0?0xffc77764:0xffaab7b6,width,poses,buffers);
                poses.popPose();return;
            }
            boolean lift=!board.rows().isEmpty()&&board.rows().stream().allMatch(s->s.endsWith(" · 直梯"));
            line(lift?I18n.get("sign.projectseele.lift_transfer"):board.station(),0,0xffedbd55,width,poses,buffers);
            // a small "Chinese · English" line under each row needs the rows a little higher to clear the panel's lower edge
            boolean split=board.rows().stream().anyMatch(s->s.indexOf(SPLIT)>0);
            for(int i=0;i<Math.min(3,board.rows().size());i++)line(compactDestination(board.rows().get(i),lift),split?17+i*15:18+i*16,
                    i==0?0xffe9efde:0xffa9d9ae,width,poses,buffers);
        }
        else
        {
            // rows with a small "Chinese · English" line under them need more room: shrink the group so it keeps its height
            boolean split=!board.routeMap()&&board.rows().stream().anyMatch(s->s.indexOf(SPLIT)>0);
            float group=split?.87F:1F;poses.scale(group,group,1);
            line(board.title(),0,0xffedbd55,width/group,poses,buffers);
            line(board.station(),11,0xffabbec5,width/group,poses,buffers);
            for(int i=0;i<board.rows().size();i++) line(board.rows().get(i),25+i*(board.routeMap()?11:split?15:13),
                    board.rows().get(i).contains("本站")?0xffffd572:i==0?0xffe9efde:0xffa9d9ae,width/group,poses,buffers);
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
            var rearRows=board.rearGuideBound()?board.rearRows():board.rows().stream().map(StationDepartureBoardRenderer::reverseArrow).toList();
            boolean split=direction&&!board.routeMap()&&rearRows.stream().anyMatch(s->s.indexOf(SPLIT)>0);
            float group=split?.87F:1F;poses.scale(group,group,1);
            float rearWidth=2.64F/rearScale/group;
            line(board.title(),0,0xffedbd55,rearWidth,poses,buffers);
            line(board.station(),11,0xffdbe4e6,rearWidth,poses,buffers);
            if(direction)for(int i=0;i<Math.min(3,rearRows.size());i++)
                line(board.routeMap()?board.rows().get(i):rearRows.get(i),25+i*(split?15:13),
                        i==0?0xffe9efde:0xffa9d9ae,rearWidth,poses,buffers);
            poses.popPose();
        }
    }
    private void routeMapFace(StationDepartureBoardBlockEntity board,PoseStack poses,MultiBufferSource buffers,boolean rear)
    {
        var stops=board.rows().stream().filter(s->s.startsWith("│")||s.startsWith("●")).toList();
        poses.pushPose();poses.translate(.5,1.78,.5);
        poses.mulPose(Axis.YP.rotationDegrees((rear?180:0)-board.getBlockState().getValue(StationDepartureBoardBlock.FACING).toYRot()));
        poses.translate(0,0,rear?.145:.205);
        String service=board.title().strip().split("\\s+",2)[0];
        int routeColor=routeColor(service);
        physicalLine(I18n.get("sign.projectseele.route_map", service),0,0,.021F,2.60F,routeColor,poses,buffers);
        physicalLine(currentStation(board.station()),0,.22F,.017F,2.60F,0xffe9efde,poses,buffers);
        if(stops.size()<=4)
        {
            float gap=1.76F/Math.max(1,stops.size()-1);
            for(int i=0;i<stops.size()-1;i++)
                physicalLine("━━━━━━",-.88F+(i+.5F)*gap,.60F,.027F,gap-.12F,routeColor,poses,buffers);
            for(int i=0;i<stops.size();i++)
            {
                String source=stops.get(i);boolean current=source.contains("本站");
                float x=stops.size()==1?0:-.88F+i*gap;
                physicalLine(current?"●":"○",x,.54F,.036F,.25F,current?0xffffd572:routeColor,poses,buffers);
                physicalLine(stopName(source),x,.82F,.014F,Math.min(.84F,gap-.06F),
                        current?0xffffd572:0xffdbe9e4,poses,buffers);
            }
        }
        else
        {
            int rows=(stops.size()+1)/2;
            float gap=Math.min(.18F,.57F/Math.max(1,rows-1));
            float lettering=Math.min(.0145F,gap/11);
            for(int i=0;i<stops.size();i++)
            {
                int row=i%rows;float x=i<rows?-1.24F:.10F,y=.45F+row*gap;
                String source=stops.get(i);boolean current=source.contains("本站");
                if(row>0)physicalLine("│",x,y-gap*.70F,.019F,.09F,routeColor,poses,buffers);
                physicalLine(current?"●":"○",x,y,.018F,.14F,current?0xffffd572:routeColor,poses,buffers);
                physicalLine(stopName(source),x+.63F,y,lettering,1.10F,
                        current?0xffffd572:0xffdbe9e4,poses,buffers);
            }
            // Order follows the real service, while the physical departure
            // arrow below changes on the rear. Do not invent station numbers
            // that would change when the opposite service reverses its list.
            physicalLine(I18n.get("sign.projectseele.continued"),0,1.015F,.008F,.24F,routeColor,poses,buffers);
        }
        var footer=board.rows().stream().filter(s->!s.startsWith("│")&&!s.startsWith("●")).toList();
        if(!footer.isEmpty())physicalLine(rear?reversePhysicalDirection(footer.get(0)):footer.get(0),0,1.12F,.014F,2.60F,0xffa9d9ae,poses,buffers);
        if(footer.size()>1)physicalLine(footer.get(footer.size()-1),0,1.31F,.0105F,2.60F,0xffabbec5,poses,buffers);
        poses.popPose();
    }
    private static String stopName(String source)
    {
        String name=source.substring(1).replace("本站","").strip();
        String[] names=name.split("\\|",-1);
        String language=net.minecraft.client.Minecraft.getInstance().getLanguageManager().getSelected();
        int index=language.startsWith("en_")?2:language.startsWith("zh_")?1:0;
        return index<names.length&&!names[index].isBlank()?names[index].strip():names[0].strip();
    }
    private static String currentStation(String station)
    {
        int split=station.indexOf(SPLIT);
        String name = split > 0 ? station.substring(0, split) : station;
        String here = I18n.get("sign.projectseele.current_stop", name);
        return split > 0 ? here + station.substring(split) : here;
    }
    private static int routeColor(String service)
    {
        return switch(service)
        {
            case "R1" -> 0xff8ac9a4;
            case "S1" -> 0xffe9b06d;
            case "U1" -> 0xff8bc5e0;
            case "U2" -> 0xffd5b778;
            case "F1" -> 0xff8bd7d3;
            case "F2" -> 0xffb9b3e7;
            default -> 0xffedbd55;
        };
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
    private static String reversePhysicalDirection(String text)
    {
        // The full diagram is readable from both platform approaches; a
        // relative train-direction arrow must reverse on the opposite face.
        var result = new StringBuilder(text.length());
        for (char c : text.toCharArray())
        {
            result.append(switch (c)
            {
                case '←' -> '→'; case '→' -> '←';
                case '↑' -> '↓'; case '↓' -> '↑';
                default -> c;
            });
        }
        return result.toString();
    }
    private static String compactDestination(String text,boolean sharedLiftHeader)
    {
        return text.replace("机库登机层","机库登机").replace("总部火车站","总部站")
                .replace("金字塔接驳站","金字塔站").replace("发射区车站","发射区站")
                .replace(" · 直梯",sharedLiftHeader?"":" · 梯");
    }
    /** "日本語|中文|English": the Japanese part on the line, the rest in small type under it. */
    private void line(String text,int y,int color,float width,PoseStack poses,MultiBufferSource buffers)
    {
        int split=text.indexOf(SPLIT);
        if(split>0)
        {
            String sub=String.join(" · ",java.util.Arrays.stream(text.substring(split+1).split("\\|")).map(String::strip)
                    .filter(s->!s.isEmpty()).toList());
            text=text.substring(0,split).strip();
            if(!sub.isEmpty())
            {
                poses.pushPose();poses.translate(0,y+SUB_OFFSET,0);poses.scale(SUB_SCALE,SUB_SCALE,1);
                draw(sub,(color&0xff000000)|((color&0x00fefefe)>>1)+0x00303030,width/SUB_SCALE,poses,buffers);
                poses.popPose();
            }
        }
        poses.pushPose();poses.translate(0,y,0);draw(text,color,width,poses,buffers);poses.popPose();
    }
    private void draw(String text,int color,float width,PoseStack poses,MultiBufferSource buffers)
    {
        float fit=Math.min(1,width/Math.max(1,font.width(text)));poses.scale(fit,1,1);
        font.drawInBatch(text,-font.width(text)/2F,0,color,false,poses.last().pose(),buffers,Font.DisplayMode.NORMAL,0,15728880);
    }
    @Override public int getViewDistance() { return 96; }
}
