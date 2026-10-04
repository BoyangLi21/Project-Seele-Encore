package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;

/** Original TV11-inspired personnel pressure door; dimensions belong to the existing device. */
final class NervPressureDoorFinishR45
{
    private static final ResourceLocation FACE = new ResourceLocation("projectseele", "textures/entity/nerv_pressure_door_r45.png");
    private static final ResourceLocation METAL = new ResourceLocation("minecraft", "textures/block/white_concrete.png");
    private static final ResourceLocation HAZARD = new ResourceLocation("projectseele", "textures/entity/nerv_pressure_hazard_r45.png");

    static void leaf(PoseStack stack, MultiBufferSource buffers, int light, double x, boolean left)
    {
        // All moving geometry remains inside the original 1.48 x 2 x .1875 leaf.
        VertexConsumer metal = buffers.getBuffer(RenderType.entitySolid(METAL));
        VertexConsumer face = buffers.getBuffer(RenderType.entitySolid(FACE));
        double[][] edge = outline(x, 0, 1.48, 2, .055);
        for (int side : new int[] {-1, 1})
        {
            double[][] inset = outline(x + .035, .035, 1.41, 1.93, .048);
            for (int i = 0; i < 8; i++)
            {
                int j = (i + 1) % 8;
                int a=side>0?i:j,b=side>0?j:i;
                quad(stack, metal, light, 0x555e70,
                        point(edge[a], side * .047), point(edge[b], side * .047),
                        point(inset[b], side * .090), point(inset[a], side * .090));
                double[] centre = {x + .74, 1, side * .090};
                triangle(stack, face, light, 0xffffff, centre,
                        point(inset[a], side * .090),
                        point(inset[b], side * .090), x, left, side);
            }
        }
        for (int i = 0; i < 8; i++)
        {
            int j = (i + 1) % 8;
            quad(stack, metal, light, 0x263436, point(edge[i], -.047),
                    point(edge[j], -.047), point(edge[j], .047), point(edge[i], .047));
        }
    }

    static void identity(PoseStack stack, MultiBufferSource buffers, int light, double x, String front, String back)
    {
        Font font=Minecraft.getInstance().font;
        for(int side:new int[]{-1,1})
        {
            String label=side>0?front:back;
            float scale=Math.min(.065F,1.18F/Math.max(1,font.width(label)));
            stack.pushPose();stack.translate(x+.74,1.62,side*.092);
            if(side<0)stack.mulPose(Axis.YP.rotationDegrees(180));
            stack.scale(scale,-scale,scale);
            font.drawInBatch(label,-font.width(label)*.5F,0,0xff85352c,false,
                    stack.last().pose(),buffers,Font.DisplayMode.NORMAL,0,light);
            stack.popPose();
        }
    }

    static void frame(PoseStack stack, MultiBufferSource buffers, int light, float progress)
    {
        VertexConsumer out = buffers.getBuffer(RenderType.entitySolid(METAL));
        // The pressure seal, flange and fixed lintel are outside the three-lane opening.
        for (int side : new int[] {-1, 1})
        {
            double inner = side < 0 ? -1.535 : 1.5;
            box(stack, out, light, inner, 0, -.18, .035, 2, .36, 0x142322);
            box(stack, out, light, side < 0 ? -1.74 : 1.55, 0, -.25, .19, 2.20, .50, 0x415754);
            box(stack, out, light, side < 0 ? -1.78 : 1.74, 0, -.29, .04, 2.24, .58, 0x233735);
        }
        box(stack, out, light, -1.535, 2, -.18, 3.07, .035, .36, 0x142322);
        box(stack, out, light, -1.74, 2.05, -.25, 3.48, .15, .50, 0x415754);
        box(stack, out, light, -1.78, 2.20, -.29, 3.56, .04, .58, 0x233735);
        for (int side : new int[] {-1, 1})
        {
            double z = side * .256;
            box(stack, out, light, -.30, 2.07, z, .60, .11, .005, 0x152623);
            box(stack, out, LightTexture.FULL_BRIGHT, -.24, 2.102, z + side * .006,
                    .48, .045, .003, progress >= .82F ? 0x78a98d : 0xc17b4d);
            VertexConsumer hazard=buffers.getBuffer(RenderType.entitySolid(HAZARD));
            stripe(stack,hazard,light,-1.73,0,.17,2.19,side);
            stripe(stack,hazard,light,1.56,0,.17,2.19,side);
        }
    }

    private static void stripe(PoseStack stack,VertexConsumer out,int light,double x,double y,double w,double h,int side)
    {
        double[][] corners={{x,y},{x+w,y},{x+w,y+h},{x,y+h}};
        for(int i:new int[]{0,1,2,3})
        {
            double[] p=corners[side>0?i:3-i];
            vertex(stack,out,light,0xffffff,new double[]{p[0],p[1],side*.257},
                    (float)(p[0]*2),(float)(-p[1]*2),0,0,side);
        }
    }

    private static double[][] outline(double x, double y, double w, double h, double cut)
    {
        return new double[][] {{x+cut,y},{x+w-cut,y},{x+w,y+cut},{x+w,y+h-cut},
                {x+w-cut,y+h},{x+cut,y+h},{x,y+h-cut},{x,y+cut}};
    }
    private static double[] point(double[] xy, double z) { return new double[] {xy[0], xy[1], z}; }
    private static void triangle(PoseStack stack, VertexConsumer out, int light, int colour,
            double[] a, double[] b, double[] c, double x, boolean left, int side)
    {
        for (double[] p : new double[][] {a,b,c,c})
        {
            float u = (float)((p[0]-x)/1.48);
            vertex(stack,out,light,colour,p,left?u:1-u,1-(float)p[1]/2,0,0,side);
        }
    }
    private static void box(PoseStack stack, VertexConsumer out, int light,
            double x, double y, double z, double w, double h, double d, int colour)
    {
        double[][] p = {{x,y,z},{x+w,y,z},{x+w,y+h,z},{x,y+h,z},
                {x,y,z+d},{x+w,y,z+d},{x+w,y+h,z+d},{x,y+h,z+d}};
        for (int[] f : new int[][] {{0,3,2,1},{4,5,6,7},{0,4,7,3},{1,2,6,5},{0,1,5,4},{3,7,6,2}})
            quad(stack,out,light,colour,p[f[0]],p[f[1]],p[f[2]],p[f[3]]);
    }
    private static void quad(PoseStack stack, VertexConsumer out, int light, int colour,
            double[] a, double[] b, double[] c, double[] d)
    {
        double ax=b[0]-a[0],ay=b[1]-a[1],az=b[2]-a[2];
        double bx=c[0]-a[0],by=c[1]-a[1],bz=c[2]-a[2];
        double nx=ay*bz-az*by,ny=az*bx-ax*bz,nz=ax*by-ay*bx;
        double length=Math.sqrt(nx*nx+ny*ny+nz*nz);
        for (double[] p : new double[][] {a,b,c,d})
            vertex(stack,out,light,colour,p,0,0,(float)(nx/length),(float)(ny/length),(float)(nz/length));
    }
    private static void vertex(PoseStack stack, VertexConsumer out, int light, int colour,
            double[] p, float u, float v, float nx, float ny, float nz)
    {
        var pose=stack.last();
        out.vertex(pose.pose(),(float)p[0],(float)p[1],(float)p[2])
                .color(colour>>16&255,colour>>8&255,colour&255,255).uv(u,v)
                .overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light)
                .normal(pose.normal(),nx,ny,nz).endVertex();
    }
    private NervPressureDoorFinishR45() {}
}
