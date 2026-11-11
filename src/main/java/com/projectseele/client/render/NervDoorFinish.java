package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;

/** Original restrained pressure-door panels shared by personnel and cage doors. */
final class NervDoorFinish
{
    private static final ResourceLocation METAL=new ResourceLocation("minecraft","textures/block/white_concrete.png");
    static void leaf(PoseStack stack,MultiBufferSource buffers,int light,double x,double y,double z,double width,double height,double depth,boolean dark)
    {
        var out=buffers.getBuffer(RenderType.entitySolid(METAL));int base=dark?0x28322f:0x9aa69d,edge=dark?0x141d1d:0x4e6059;
        box(stack,out,light,x,y,z,width,height,depth,edge);
        double border=Math.min(.08,width*.08),face=.012;
        for(int side:new int[]{-1,1})
        {
            double plane=side<0?z-face:z+depth;
            box(stack,out,light,x+border,y+.07,plane,width-2*border,height-.14,face,base);
            double stripe=Math.min(.06,height*.025),sy=y+height*.27;
            box(stack,out,light,x+border,sy,plane+side*.006,width-2*border,stripe,.009,0x853f32);
            box(stack,out,light,x+border,sy-stripe*.7,plane+side*.013,width-2*border,stripe*.35,.009,0xc6bda0);
            int ribs=Math.max(1,Math.min(10,(int)(height/2.5)));
            for(int i=1;i<=ribs;i++)box(stack,out,light,x+border,y+height*i/(ribs+1),plane+side*.017,width-2*border,.014,.009,edge);
            double hx=x+width*.76,hy=y+Math.min(1.28,height*.6);
            box(stack,out,light,hx,hy,plane+side*.026,Math.min(.12,width*.12),Math.min(.26,height*.1),.025,0x293b36);
            box(stack,out,light,x+width*.17,y+height*.84,plane+side*.02,Math.min(.15,width*.16),.045,.018,0xd0be8b);
        }
    }
    /**
     * Jambs and head stand {@value #INSET} block inside the opening. Flush with it, their inner faces
     * lay in the planes of the wall's own faces around the opening and flickered against them
     * (z-fighting), more with distance and under a shader pack's temporal anti-aliasing.
     */
    private static final double INSET=.02;
    static void frame(PoseStack stack,MultiBufferSource buffers,int light,double half,double height,boolean open)
    {
        var out=buffers.getBuffer(RenderType.entitySolid(METAL));
        box(stack,out,light,-half-.09,0,-.12,.09+INSET,height,.24,0x263832);box(stack,out,light,half-INSET,0,-.12,.09+INSET,height,.24,0x263832);
        box(stack,out,light,-half-.09,height-INSET,-.12,2*half+.18,.08+INSET,.24,0x263832);
        // The status lights stand clear of the head's faces for the same reason.
        for(double z:new double[]{-.142,.13})box(stack,out,LightTexture.FULL_BRIGHT,-.18,height+.015,z,.36,.026,.012,open?0x7cbe89:0xb86647);
    }
    private static void box(PoseStack stack,VertexConsumer out,int light,double x,double y,double z,double w,double h,double d,int colour)
    {
        float[][] p={{(float)x,(float)y,(float)z},{(float)(x+w),(float)y,(float)z},{(float)(x+w),(float)(y+h),(float)z},{(float)x,(float)(y+h),(float)z},
                {(float)x,(float)y,(float)(z+d)},{(float)(x+w),(float)y,(float)(z+d)},{(float)(x+w),(float)(y+h),(float)(z+d)},{(float)x,(float)(y+h),(float)(z+d)}};
        int[][] f={{0,3,2,1},{4,5,6,7},{0,4,7,3},{1,2,6,5},{0,1,5,4},{3,7,6,2}};
        float[][] n={{0,0,-1},{0,0,1},{-1,0,0},{1,0,0},{0,-1,0},{0,1,0}};var pose=stack.last();
        for(int a=0;a<6;a++)for(int b=0;b<4;b++)
        {
            var v=p[f[a][b]];out.vertex(pose.pose(),v[0],v[1],v[2]).color((colour>>16)&255,(colour>>8)&255,colour&255,255).uv(b==1||b==2?1:0,b<2?1:0).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(pose.normal(),n[a][0],n[a][1],n[a][2]).endVertex();
        }
    }
    private NervDoorFinish(){}
}
