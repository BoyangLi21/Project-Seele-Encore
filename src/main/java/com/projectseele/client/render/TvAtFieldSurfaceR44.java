package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/** Original octagonal field bands. This is presentation geometry, not damage logic.
 * A single winding plus a no-cull material avoids applying alpha twice to each
 * transparent face. Impact/deployment and paired tearing still need distinct
 * authoritative event/actor anchors before this candidate can replace all FX. */
public final class TvAtFieldSurfaceR44
{
    private static final int SIDES = 8;
    private static final int EDGE_STEPS = 8;

    private TvAtFieldSurfaceR44() {}

    public static void impact(Matrix4f pose, VertexConsumer out, Vector3f u, Vector3f v,
                              float normalizedAge, float intensity,float maximumRadius)
    {
        float t=Mth.clamp(normalizedAge,0,1);
        for(int ring=0;ring<4;ring++)
        {
            float local=t-ring*.055F;
            if(local<=0)continue;
            float spread=1-(float)Math.pow(1-Mth.clamp(local/.34F,0,1),3);
            float reveal=Mth.clamp(local/.065F,0,1);
            float decay=1-(float)Mth.smoothstep(Mth.clamp((local-.34F)/.53F,0,1));
            float radius=(2.0F+ring*2.25F)*(.63F+.37F*spread)*maximumRadius/8.75F;
            float width=Math.max(.30F,radius*.145F);
            float alpha=reveal*decay*intensity*(.58F-ring*.055F);
            if(alpha<=.001F)continue;
            band(pose,out,u,v,radius,width,t,ring,alpha);
        }
    }

    private static void band(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,
                             float radius,float width,float age,int ring,float alpha)
    {
        // Firm inner orange band, a lighter outer rim and soft irregular
        // interference at its boundary. The centre remains transparent.
        float[] across={0,.14F,.64F,.84F,1};
        float[] opacity={0,.75F,.86F,1,0};
        for(int edge=0;edge<SIDES;edge++)for(int step=0;step<EDGE_STEPS;step++)
        {
            float a=(float)(Math.PI/8+edge*Math.PI/4),b=a+(float)(Math.PI/4);
            float t0=step/(float)EDGE_STEPS,t1=(step+1)/(float)EDGE_STEPS;
            float x0=Mth.lerp(t0,Mth.cos(a),Mth.cos(b)),y0=Mth.lerp(t0,Mth.sin(a),Mth.sin(b));
            float x1=Mth.lerp(t1,Mth.cos(a),Mth.cos(b)),y1=Mth.lerp(t1,Mth.sin(a),Mth.sin(b));
            float s0=edge+t0,s1=edge+t1;
            float f0=fringe(s0,age,ring),f1=fringe(s1,age,ring);
            for(int strip=0;strip<across.length-1;strip++)
            {
                float c0=across[strip],c1=across[strip+1];
                float r00=radius-width+width*c0+f0*width*(1-c0)*.20F;
                float r01=radius-width+width*c1+f0*width*(1-c1)*.20F;
                float r10=radius-width+width*c0+f1*width*(1-c0)*.20F;
                float r11=radius-width+width*c1+f1*width*(1-c1)*.20F;
                // One transparent surface, no offset boards intersecting a body.
                vertex(pose,out,u,v,x0*r00,y0*r00,c0,alpha*opacity[strip]);
                vertex(pose,out,u,v,x1*r10,y1*r10,c0,alpha*opacity[strip]);
                vertex(pose,out,u,v,x1*r11,y1*r11,c1,alpha*opacity[strip+1]);
                vertex(pose,out,u,v,x0*r01,y0*r01,c1,alpha*opacity[strip+1]);
            }
        }
    }

    private static float fringe(float edge,float age,int ring)
    {
        // Periodic around the full octagon, so the seam cannot jump or open.
        float angle=edge*(float)(Math.PI/4);
        return .57F*Mth.sin(angle*19+age*17+ring*1.7F)
                +.28F*Mth.sin(angle*31-age*12+ring*2.1F)
                +.15F*Mth.sin(angle*47+age*9-ring);
    }

    private static void vertex(Matrix4f pose,VertexConsumer out,Vector3f u,Vector3f v,
                               float x,float y,float across,float alpha)
    {
        float rim=Mth.clamp((across-.62F)/.3F,0,1);
        out.vertex(pose,u.x*x+v.x*y,u.y*x+v.y*y,u.z*x+v.z*y)
                .color(1F,.29F+rim*.30F,.018F+rim*.13F,Mth.clamp(alpha,0,.8F)).endVertex();
    }
}
