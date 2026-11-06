package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.world.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.blockentity.*;
import net.minecraft.resources.ResourceLocation;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;

/** Shared, static GPU meshes; readable notices and server-synchronised local clocks. */
public final class PeriodFixtureRenderer implements BlockEntityRenderer<PeriodFixtureBlockEntity>
{
    private static final Map<String,VertexBuffer> PARTS=new HashMap<>();
    private static boolean attempted;
    public PeriodFixtureRenderer(BlockEntityRendererProvider.Context context) {}
    public static void clearCache()
    {
        RenderSystem.recordRenderCall(()->{PARTS.values().forEach(VertexBuffer::close);PARTS.clear();attempted=false;});
    }
    private static void load()
    {
        if(attempted)return;attempted=true;
        try(var input=Minecraft.getInstance().getResourceManager().open(new ResourceLocation(ProjectSeele.MODID,"mesh/period_details_r24.json"));
                var reader=new InputStreamReader(input,StandardCharsets.UTF_8))
        {
            var parts=JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("parts");
            for(var part:parts.entrySet())
            {
                var data=part.getValue().getAsJsonArray();BufferBuilder builder=new BufferBuilder(65536);
                if(data.size()%18!=0||data.size()>1_000_000)throw new IllegalArgumentException("Fixture mesh size");
                builder.begin(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.POSITION_COLOR);
                for(int i=0;i<data.size();i+=6)builder.vertex(data.get(i).getAsDouble(),data.get(i+1).getAsDouble(),data.get(i+2).getAsDouble())
                        .color(data.get(i+3).getAsInt(),data.get(i+4).getAsInt(),data.get(i+5).getAsInt(),255).endVertex();
                VertexBuffer buffer=new VertexBuffer(VertexBuffer.Usage.STATIC);buffer.bind();buffer.upload(builder.end());VertexBuffer.unbind();PARTS.put(part.getKey(),buffer);
            }
            ProjectSeele.LOGGER.info("Original period fixtures loaded: {} mesh parts",PARTS.size());
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("Period fixture resource rejected",failure);}
    }
    private static void mesh(String name,PoseStack pose,int light,float alpha)
    {
        load();var buffer=PARTS.get(name);if(buffer==null)return;
        var type=RenderType.debugQuads();type.setupRenderState();float brightness=.40F+.60F*Math.max((light>>4)&15,(light>>20)&15)/15F;
        if(alpha<1){RenderSystem.enableBlend();RenderSystem.defaultBlendFunc();RenderSystem.depthMask(false);}
        RenderSystem.setShaderColor(brightness,brightness,brightness,alpha);
        buffer.bind();buffer.drawWithShader(pose.last().pose(),RenderSystem.getProjectionMatrix(),GameRenderer.getPositionColorShader());VertexBuffer.unbind();
        RenderSystem.setShaderColor(1,1,1,1);if(alpha<1)RenderSystem.depthMask(true);type.clearRenderState();
    }
    private static void line(PoseStack pose,MultiBufferSource buffer,String text,double y,double z,float maximum,int colour)
    {line(pose,buffer,text,y,z,maximum,colour,.011F);}
    private static void line(PoseStack pose,MultiBufferSource buffer,String text,double y,double z,float maximum,int colour,float naturalScale)
    {
        var font=Minecraft.getInstance().font;float scale=Math.min(naturalScale,maximum/Math.max(1,font.width(text)));
        pose.pushPose();pose.translate(.5,y,z);pose.scale(scale,-scale,scale);
        font.drawInBatch(text,-font.width(text)/2F,0,colour,false,pose.last().pose(),buffer,net.minecraft.client.gui.Font.DisplayMode.NORMAL,0,15728880);
        pose.popPose();
    }
    @Override public void render(PeriodFixtureBlockEntity entity,float partial,PoseStack pose,MultiBufferSource buffers,int light,int overlay)
    {
        var state=entity.getBlockState();var kind=state.getValue(PeriodFixtureBlock.KIND);
        pose.pushPose();pose.translate(.5,0,.5);pose.mulPose(Axis.YP.rotationDegrees(-state.getValue(PeriodFixtureBlock.FACING).toYRot()));pose.translate(-.5,0,-.5);
        mesh(kind.getSerializedName(),pose,light,1);
        if(kind==PeriodFixtureBlock.Kind.VENDING_MACHINE)mesh("vending_glow",pose,LightTexture.FULL_BRIGHT,1);
        else if(kind==PeriodFixtureBlock.Kind.TECH_BENCH)mesh("tech_glow",pose,LightTexture.FULL_BRIGHT,1);
        if(kind==PeriodFixtureBlock.Kind.PUBLIC_PHONE)
        {mesh("phone_glass",pose,light,.20F);line(pose,buffers,"公用电话",2.035,.105,.75F,0xFFF1EDDA);}
        else if(kind==PeriodFixtureBlock.Kind.NOTICE_BOARD)
        {
            line(pose,buffers,entity.title(),1.785,.535,.75F,0xFFF0E9D2);int n=0;
            for(String text:entity.lines())line(pose,buffers,text,1.52-n++*.14,.537,.76F,0xFF293B33);
        }
        else if(kind==PeriodFixtureBlock.Kind.WALL_CLOCK)
        {
            var time=Instant.ofEpochMilli(entity.clockMillis()).atZone(ZoneId.of("Asia/Shanghai"));
            double minute=time.getMinute()+time.getSecond()/60D,hour=time.getHour()%12+minute/60D;
            pose.pushPose();pose.translate(.5,.5,.192);pose.mulPose(Axis.ZP.rotationDegrees((float)(-hour*30)));mesh("clock_hour",pose,light,1);pose.popPose();
            pose.pushPose();pose.translate(.5,.5,.204);pose.mulPose(Axis.ZP.rotationDegrees((float)(-minute*6)));mesh("clock_minute",pose,light,1);pose.popPose();
        }
        else if(kind==PeriodFixtureBlock.Kind.NEWSPAPER_RACK)
            line(pose,buffers,"报刊 · 书讯",1.742,.406,.71F,0xFFF0E9D2);
        else if(kind==PeriodFixtureBlock.Kind.VENDING_MACHINE)
            line(pose,buffers,"清凉饮料",1.878,1.001,.64F,0xFFF2EDD7,.009F);
        else if(kind==PeriodFixtureBlock.Kind.LETTER_BOX)
            line(pose,buffers,"邮便",1.01,.78,.35F,0xFFF2EDD7,.009F);
        else if(kind==PeriodFixtureBlock.Kind.SHOP_SIGN)
        {
            line(pose,buffers,entity.title(),.645,.153,2.5F,0xFF304C3B,.038F);
            if(!entity.lines().isEmpty())line(pose,buffers,entity.lines().get(0),.198,.153,2.4F,0xFF546556,.014F);
        }
        pose.popPose();
    }
}
