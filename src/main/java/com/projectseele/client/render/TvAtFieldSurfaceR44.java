package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/** Event-oriented octagonal membranes; presentation only, no damage or field-cost changes. */
public final class TvAtFieldSurfaceR44
{
    private static final int SIDES=8;
    private static final int EDGE_STEPS=6;
    private TvAtFieldSurfaceR44() { }

    public static void impact(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,
                              float normalizedAge,float intensity,float maximumRadius)
    {
        float t=Mth.clamp(normalizedAge,0,1);
        float life=(1-(float)Mth.smoothstep(Mth.clamp((t-.28F)/.67F,0,1)))*intensity;
        if(life<=.001F)return;
        float reveal=1-(float)Math.pow(1-Mth.clamp(t/.14F,0,1),3);
        membrane(pose,out,u,v,maximumRadius*.96F*reveal,life*(.022F+.085F*(1-Mth.clamp(t/.18F,0,1))));
        for(int ring=0;ring<9;ring++)
        {
            float local=t-ring*.014F;
            if(local<=0)continue;
            float spread=1-(float)Math.pow(1-Mth.clamp(local/.19F,0,1),3);
            float radius=maximumRadius*(.105F+ring*.105F)*(.40F+.60F*spread);
            float width=maximumRadius*(.031F+ring*.0017F);
            float onset=Mth.clamp(local/.028F,0,1);
            float alpha=life*onset*(.82F-ring*.035F);
            band(pose,out,u,v,radius,width,t,ring,alpha);
        }
    }

    private static void membrane(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,float radius,float alpha)
    {
        for(int edge=0;edge<SIDES;edge++)
        {
            float a=(float)(Math.PI/8+edge*Math.PI/4),b=a+(float)Math.PI/4;
            vertex(pose,out,u,v,0,0,.3F,alpha*.75F,0);
            vertex(pose,out,u,v,Mth.cos(a)*radius,Mth.sin(a)*radius,.1F,alpha,0);
            vertex(pose,out,u,v,Mth.cos(b)*radius,Mth.sin(b)*radius,.1F,alpha,0);
            vertex(pose,out,u,v,0,0,.3F,alpha*.75F,0);
        }
    }

    private static void band(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,
                             float radius,float width,float age,int ring,float alpha)
    {
        float[] across={0,.16F,.70F,.91F,1};
        float[] opacity={0,.82F,.95F,1,0};
        for(int edge=0;edge<SIDES;edge++)for(int step=0;step<EDGE_STEPS;step++)
        {
            float a=(float)(Math.PI/8+edge*Math.PI/4),b=a+(float)Math.PI/4;
            float t0=step/(float)EDGE_STEPS,t1=(step+1)/(float)EDGE_STEPS;
            float x0=Mth.lerp(t0,Mth.cos(a),Mth.cos(b)),y0=Mth.lerp(t0,Mth.sin(a),Mth.sin(b));
            float x1=Mth.lerp(t1,Mth.cos(a),Mth.cos(b)),y1=Mth.lerp(t1,Mth.sin(a),Mth.sin(b));
            float f0=fringe(edge+t0,age,ring),f1=fringe(edge+t1,age,ring);
            for(int strip=0;strip<across.length-1;strip++)
            {
                float c0=across[strip],c1=across[strip+1];
                float r00=radius-width+width*c0+f0*width*(1-c0)*.07F;
                float r01=radius-width+width*c1+f0*width*(1-c1)*.07F;
                float r10=radius-width+width*c0+f1*width*(1-c0)*.07F;
                float r11=radius-width+width*c1+f1*width*(1-c1)*.07F;
                float bow=width*.10F*(1-Mth.clamp(age/.45F,0,1));
                vertex(pose,out,u,v,x0*r00,y0*r00,c0,alpha*opacity[strip],f0*bow);
                vertex(pose,out,u,v,x1*r10,y1*r10,c0,alpha*opacity[strip],f1*bow);
                vertex(pose,out,u,v,x1*r11,y1*r11,c1,alpha*opacity[strip+1],f1*bow);
                vertex(pose,out,u,v,x0*r01,y0*r01,c1,alpha*opacity[strip+1],f0*bow);
            }
        }
    }

    private static float fringe(float edge,float age,int ring)
    {
        float angle=edge*(float)Math.PI/4;
        return .7F*Mth.sin(angle*3-age*10+ring*.6F)+.3F*Mth.sin(angle*7+age*8-ring*.4F);
    }

    private static void vertex(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,
                               float x,float y,float across,float alpha,float depth)
    {
        float rim=Mth.clamp((across-.62F)/.31F,0,1);
        float nx=u.y*v.z-u.z*v.y,ny=u.z*v.x-u.x*v.z,nz=u.x*v.y-u.y*v.x;
        out.vertex(pose,u.x*x+v.x*y+nx*depth,u.y*x+v.y*y+ny*depth,u.z*x+v.z*y+nz*depth)
                .color(1F,.25F+rim*.56F,.014F+rim*.36F,Mth.clamp(alpha,0,.92F)).endVertex();
    }
}
