package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.SeeleMonolithEntityR47;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;

/** Opaque depth-tested housing and emissive face, confined to its actual meeting prop. */
public final class SeeleMonolithRendererR47 extends EntityRenderer<SeeleMonolithEntityR47>
{
    private static final ResourceLocation MESH=new ResourceLocation(ProjectSeele.MODID,"mesh/seele_monolith_r47.mesh.json");
    private static final ResourceLocation BLACK=new ResourceLocation("minecraft","textures/block/black_concrete.png");
    private static final ResourceLocation LOGO=new ResourceLocation(ProjectSeele.MODID,"textures/entity/seele_logo_supplied_r47.png");
    private static final ResourceLocation WHITE=new ResourceLocation("minecraft","textures/block/white_concrete.png");
    private static final ResourceLocation DESK=new ResourceLocation(ProjectSeele.MODID,"mesh/seele_desk_r48.mesh.json");
    public SeeleMonolithRendererR47(EntityRendererProvider.Context context){super(context);shadowRadius=0;}
    @Override public ResourceLocation getTextureLocation(SeeleMonolithEntityR47 entity){return entity.number()==0?WHITE:BLACK;}
    @Override public void render(SeeleMonolithEntityR47 entity,float yaw,float partial,PoseStack poses,MultiBufferSource buffers,int light)
    {
        poses.pushPose();poses.mulPose(Axis.YP.rotationDegrees(180.0F-yaw));
        if(entity.number()==0)
        {
            // The real room circuit owns ambient light. A full-room emissive
            // wash would remain visible even after the operator switched it off.
            if(entity.meetingLightsR48())downlight(poses,buffers);
            // A lit white top is still an opaque, shaded surface. The old
            // fullbright desk and additive floor disk became a bloom hotspot.
            int deskLight=entity.meetingLightsR48()?net.minecraft.client.renderer.LightTexture.pack(9,0):light;
            LocalTriangleMeshLayer.renderStandalone(poses,buffers,DESK,WHITE,deskLight,OverlayTexture.NO_OVERLAY);
            poses.popPose();super.render(entity,yaw,partial,poses,buffers,light);return;
        }
        LocalTriangleMeshLayer.renderStandalone(poses,buffers,MESH,BLACK,light,OverlayTexture.NO_OVERLAY);
        if(!entity.meetingLightsR48())
        {
        var strip=buffers.getBuffer(RenderType.eyes(WHITE));var floor=poses.last().pose();var floorNormal=poses.last().normal();
        for(float[] p:new float[][]{{-1.12F,.016F,-.46F,0,0},{-1.12F,.016F,-.32F,0,1},{1.12F,.016F,-.32F,1,1},{1.12F,.016F,-.46F,1,0}})
            strip.vertex(floor,p[0],p[1],p[2]).color(180,205,255,255).uv(p[3],p[4]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(0xF000F0).normal(floorNormal,0,1,0).endVertex();
        }
        // UV selection uses the original PNG; no crop/repaint changes its supplied artwork.
        if(Minecraft.getInstance().getResourceManager().getResource(LOGO).isPresent())
            quad(poses,buffers,-.77F,2.80F,.77F,4.20F,-.177F,.02F,.23F,.98F,.85F);
        var font=Minecraft.getInstance().font;
        poses.pushPose();poses.translate(0,2.39,-.179);poses.scale(-.034F,-.034F,.034F);
        Matrix4f matrix=poses.last().pose();String number=String.format(java.util.Locale.ROOT,"%02d",entity.number());
        font.drawInBatch(number,-font.width(number)/2F,0,0xFFB81620,false,matrix,buffers,net.minecraft.client.gui.Font.DisplayMode.NORMAL,0,0xF000F0);
        poses.popPose();poses.pushPose();poses.translate(0,2.00,-.179);poses.scale(-.014F,-.014F,.014F);
        String label="SEELE "+number+"  SOUND ONLY";
        font.drawInBatch(label,-font.width(label)/2F,0,0xFF94151B,false,poses.last().pose(),buffers,net.minecraft.client.gui.Font.DisplayMode.NORMAL,0,0xF000F0);
        poses.popPose();poses.popPose();super.render(entity,yaw,partial,poses,buffers,light);
    }
    private static void quad(PoseStack poses,MultiBufferSource buffers,float left,float bottom,float right,float top,float z,float u0,float v0,float u1,float v1)
    {
        var consumer=buffers.getBuffer(RenderType.eyes(LOGO));var matrix=poses.last().pose();var normal=poses.last().normal();
        for(float[] p:new float[][]{{left,bottom,u1,v1},{left,top,u1,v0},{right,top,u0,v0},{right,bottom,u0,v1}})
            consumer.vertex(matrix,p[0],p[1],z).color(180,180,180,255).uv(p[2],p[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(0xF000F0).normal(normal,0,0,-1).endVertex();
    }
    private static void downlight(PoseStack poses,MultiBufferSource buffers)
    {
        var beam=buffers.getBuffer(RenderType.entityTranslucent(WHITE));
        var matrix=poses.last().pose();var normal=poses.last().normal();
        final int sides=40;
        for(int i=0;i<sides;i++)
        {
            double a=i*Math.PI*2/sides,b=(i+1)*Math.PI*2/sides;
            // Narrow overhead source fans out only as far as the desk top.
            float[][] points={{(float)Math.cos(a)*.13F,7.15F,(float)Math.sin(a)*.13F,4},
                    {(float)Math.cos(a)*2.18F,1.045F,(float)Math.sin(a)*.74F,10},
                    {(float)Math.cos(b)*2.18F,1.045F,(float)Math.sin(b)*.74F,10},
                    {(float)Math.cos(b)*.13F,7.15F,(float)Math.sin(b)*.13F,4}};
            for(float[] p:points)
                beam.vertex(matrix,p[0],p[1],p[2]).color(138,148,172,(int)p[3]).uv(.5F,.5F)
                        .overlayCoords(OverlayTexture.NO_OVERLAY).uv2(net.minecraft.client.renderer.LightTexture.pack(10,0))
                        .normal(normal,0,1,0).endVertex();
        }
    }
}
