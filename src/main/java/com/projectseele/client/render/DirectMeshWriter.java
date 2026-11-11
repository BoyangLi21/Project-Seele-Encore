package com.projectseele.client.render;

import static org.lwjgl.system.MemoryUtil.memCopy;
import static org.lwjgl.system.MemoryUtil.memGetByte;
import static org.lwjgl.system.MemoryUtil.memGetInt;
import static org.lwjgl.system.MemoryUtil.memGetShort;
import static org.lwjgl.system.MemoryUtil.memPutFloat;
import static org.lwjgl.system.MemoryUtil.memPutInt;
import static org.lwjgl.system.MemoryUtil.memPutShort;
import static org.lwjgl.system.MemoryUtil.nmemAllocChecked;
import static org.lwjgl.system.MemoryUtil.nmemFree;

import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.ProjectSeele;
import net.minecraft.util.Mth;

/**
 * Writes a skinned triangle mesh into a quad buffer as raw bytes. The normal vertex
 * path walks the format one element at a time, and with a shader pack it costs most
 * of a frame for a large mesh.
 *
 * The result must equal the normal path byte for byte, so this copies what it does
 * for both entity formats, including Oculus replacing a quad's normals with its face
 * normal. Nothing checks that copy at compile time: the first mesh in each format
 * takes the normal path and is compared, and a difference disables raw writes.
 */
public final class DirectMeshWriter
{
    private static final int PLAIN_PADDING=35,WIDENED_PADDING=54,WIDENED_STRIDE=56;
    private static final int UNTESTED=0,TRUSTED=1,REJECTED=-1;
    private static final VertexFormat WIDENED=widenedFormat();
    private static int plainState,widenedState,triangleState;
    private static int[] packedNormals=new int[0];

    private DirectMeshWriter() {}

    private static VertexFormat widenedFormat()
    {
        try
        {
            VertexFormat format=(VertexFormat)Class.forName("net.irisshaders.iris.vertices.IrisVertexFormats").getField("ENTITY").get(null);
            return format.getVertexSize()==WIDENED_STRIDE?format:null;
        }
        catch(ReflectiveOperationException|LinkageError absent){return null;}
    }

    /**
     * @param skinned {@code x y z nx ny nz} in pose space per distinct input
     * @param inputs the distinct input of every corner, three per triangle
     * @param corners eight floats per corner with its UV at offsets 3 and 4
     */
    public static void write(VertexConsumer target,float[] skinned,int[] inputs,float[] corners,float alpha,int overlay,int light)
    {
        VertexFormat format=target instanceof DirectVertexTarget direct?direct.projectseele$quadFormat():null;
        boolean plain=format==DefaultVertexFormat.NEW_ENTITY,widened=format!=null&&format==WIDENED;
        int state=plain?plainState:widened?widenedState:REJECTED;
        if(state==REJECTED){submit(target,skinned,inputs,corners,alpha,overlay,light,0,inputs.length);return;}
        DirectVertexTarget buffer=(DirectVertexTarget)target;
        int stride=format.getVertexSize(),quads=inputs.length/3;
        if(state==UNTESTED)
        {
            submit(target,skinned,inputs,corners,alpha,overlay,light,0,inputs.length);
            boolean same=compare(buffer.projectseele$end()-(long)quads*4*stride,skinned,inputs,corners,alpha,overlay,light,plain,stride,quads);
            if(plain)plainState=same?TRUSTED:REJECTED;else widenedState=same?TRUSTED:REJECTED;
            if(same)ProjectSeele.LOGGER.info("Direct mesh writes verified for {} byte vertices",stride);
            else ProjectSeele.LOGGER.warn("Direct mesh writes disabled: {} byte vertices differ from the normal path",stride);
            return;
        }
        // The first quad carries what only the normal path knows, such as Oculus's entity ids.
        submit(target,skinned,inputs,corners,alpha,overlay,light,0,3);
        long last=buffer.projectseele$end()-stride;
        int ids=plain?0:memGetInt(last+36);short lastId=plain?0:memGetShort(last+40);
        long address=buffer.projectseele$reserve((quads-1)*4);
        if(plain)fillPlain(address,skinned,inputs,corners,alpha,overlay,light);
        else fillWidened(address,skinned,inputs,corners,alpha,overlay,light,ids,lastId);
    }

    private static void submit(VertexConsumer target,float[] s,int[] inputs,float[] v,float alpha,int overlay,int light,int from,int to)
    {
        for(int corner=from;corner<to;corner++)
        {
            int at=inputs[corner]*6,i=corner*8;
            target.vertex(s[at],s[at+1],s[at+2],1,1,1,alpha,v[i+3],v[i+4],overlay,light,s[at+3],s[at+4],s[at+5]);
            if(corner%3==2)target.vertex(s[at],s[at+1],s[at+2],1,1,1,alpha,v[i+3],v[i+4],overlay,light,s[at+3],s[at+4],s[at+5]);
        }
    }

    private static boolean compare(long written,float[] skinned,int[] inputs,float[] corners,float alpha,int overlay,int light,boolean plain,int stride,int quads)
    {
        long size=(long)quads*4*stride,copy=nmemAllocChecked(size);
        try
        {
            memCopy(written,copy,4L*stride);
            long last=written+3L*stride;
            if(plain)fillPlain(copy+4L*stride,skinned,inputs,corners,alpha,overlay,light);
            else fillWidened(copy+4L*stride,skinned,inputs,corners,alpha,overlay,light,memGetInt(last+36),memGetShort(last+40));
            for(long at=0;at<size;at++)
            {
                int inVertex=(int)(at%stride);
                if(plain?inVertex==PLAIN_PADDING:inVertex>=WIDENED_PADDING)continue;
                if(memGetByte(written+at)!=memGetByte(copy+at))return false;
            }
            return true;
        }
        finally{nmemFree(copy);}
    }

    /**
     * The part upload of {@link RigidCapsuleGpu}: every corner as
     * {@code vertex(-(x+px)/16,(y+py)/16,(z+pz)/16, r,g,b,1, u,v, overlay,light, -nx,ny,nz)} into a triangle buffer.
     * Under a shader pack Oculus widens that buffer, and the EVA's posed parts go through it every frame in
     * both passes. Triangles keep their own normals there and get a tangent per corner.
     */
    public static void uploadTriangles(BufferBuilder builder,float[] vertices,int stride,float px,float py,float pz,
                                       float r,float g,float b,int overlay,int light)
    {
        int corners=vertices.length/(stride*3)*3;
        VertexFormat format=(Object)builder instanceof DirectVertexTarget direct?direct.projectseele$triangleFormat():null;
        if(format==null||format!=WIDENED||triangleState==REJECTED||corners<6)
        {
            submitTriangles(builder,vertices,stride,px,py,pz,r,g,b,overlay,light,0,corners);return;
        }
        DirectVertexTarget buffer=(DirectVertexTarget)(Object)builder;
        if(triangleState==UNTESTED)
        {
            submitTriangles(builder,vertices,stride,px,py,pz,r,g,b,overlay,light,0,corners);
            boolean same=compareTriangles(buffer.projectseele$end()-(long)corners*WIDENED_STRIDE,vertices,stride,px,py,pz,r,g,b,overlay,light,corners);
            triangleState=same?TRUSTED:REJECTED;
            if(same)ProjectSeele.LOGGER.info("Direct triangle uploads verified for {} byte vertices",WIDENED_STRIDE);
            else ProjectSeele.LOGGER.warn("Direct triangle uploads disabled: {} byte vertices differ from the normal path",WIDENED_STRIDE);
            return;
        }
        // The first triangle carries what only the normal path knows, such as Oculus's entity ids.
        submitTriangles(builder,vertices,stride,px,py,pz,r,g,b,overlay,light,0,3);
        long last=buffer.projectseele$end()-WIDENED_STRIDE;
        int ids=memGetInt(last+36);short lastId=memGetShort(last+40);
        fillTriangles(buffer.projectseele$reserve(corners-3),vertices,stride,px,py,pz,r,g,b,overlay,light,ids,lastId,3,corners);
    }

    private static void submitTriangles(BufferBuilder builder,float[] v,int stride,float px,float py,float pz,float r,float g,float b,int overlay,int light,int from,int to)
    {
        for(int corner=from;corner<to;corner++)
        {
            int at=corner*stride;
            builder.vertex(-(v[at]+px)/16,(v[at+1]+py)/16,(v[at+2]+pz)/16,r,g,b,1,v[at+3],v[at+4],overlay,light,-v[at+5],v[at+6],v[at+7]);
        }
    }

    private static boolean compareTriangles(long written,float[] vertices,int stride,float px,float py,float pz,float r,float g,float b,int overlay,int light,int corners)
    {
        long size=(long)corners*WIDENED_STRIDE,copy=nmemAllocChecked(size);
        try
        {
            memCopy(written,copy,3L*WIDENED_STRIDE);
            long last=written+2L*WIDENED_STRIDE;
            fillTriangles(copy+3L*WIDENED_STRIDE,vertices,stride,px,py,pz,r,g,b,overlay,light,memGetInt(last+36),memGetShort(last+40),3,corners);
            for(long at=0;at<size;at++)
            {
                // Byte 35 pads the normal, and Oculus leaves a triangle's normal as it was written.
                int inVertex=(int)(at%WIDENED_STRIDE);
                if(inVertex==PLAIN_PADDING||inVertex>=WIDENED_PADDING)continue;
                if(memGetByte(written+at)!=memGetByte(copy+at))return false;
            }
            return true;
        }
        finally{nmemFree(copy);}
    }

    private static void fillTriangles(long p,float[] v,int stride,float px,float py,float pz,float r,float g,float b,int overlay,int light,int ids,short lastId,int from,int to)
    {
        int color=(int)(r*255.0F)&255|((int)(g*255.0F)&255)<<8|((int)(b*255.0F)&255)<<16|255<<24;
        for(int corner=from;corner<to;corner+=3)
        {
            int a=corner*stride,b1=a+stride,c=b1+stride;
            float x0=-(v[a]+px)/16,y0=(v[a+1]+py)/16,z0=(v[a+2]+pz)/16;
            float x1=-(v[b1]+px)/16,y1=(v[b1+1]+py)/16,z1=(v[b1+2]+pz)/16;
            float x2=-(v[c]+px)/16,y2=(v[c+1]+py)/16,z2=(v[c+2]+pz)/16;
            float u0=v[a+3],v0=v[a+4],u1=v[b1+3],v1=v[b1+4],u2=v[c+3],v2=v[c+4];
            int n0=normalByte(-v[a+5])|normalByte(v[a+6])<<8|normalByte(v[a+7])<<16;
            int n1=normalByte(-v[b1+5])|normalByte(v[b1+6])<<8|normalByte(v[b1+7])<<16;
            int n2=normalByte(-v[c+5])|normalByte(v[c+6])<<8|normalByte(v[c+7])<<16;
            float midU=(0F+u0+u1+u2)/3,midV=(0F+v0+v1+v2)/3;
            widenedVertex(p,x0,y0,z0,u0,v0,color,overlay,light,n0,ids,lastId,midU,midV,smoothTangent(n0,x0,y0,z0,x1,y1,z1,x2,y2,z2,u0,v0,u1,v1,u2,v2));
            widenedVertex(p+56,x1,y1,z1,u1,v1,color,overlay,light,n1,ids,lastId,midU,midV,smoothTangent(n1,x0,y0,z0,x1,y1,z1,x2,y2,z2,u0,v0,u1,v1,u2,v2));
            widenedVertex(p+112,x2,y2,z2,u2,v2,color,overlay,light,n2,ids,lastId,midU,midV,smoothTangent(n2,x0,y0,z0,x1,y1,z1,x2,y2,z2,u0,v0,u1,v1,u2,v2));
            p+=168;
        }
    }

    /** Oculus's per-corner tangent for a triangle: the corners are flattened onto the plane of that corner's stored normal first. */
    private static int smoothTangent(int packedNormal,float x0,float y0,float z0,float x1,float y1,float z1,float x2,float y2,float z2,
                                     float u0,float v0,float u1,float v1,float u2,float v2)
    {
        float nx=(byte)(packedNormal&255)*.007874016F,ny=(byte)(packedNormal>>8&255)*.007874016F,nz=(byte)(packedNormal>>16&255)*.007874016F;
        float d0=x0*nx+y0*ny+z0*nz,d1=x1*nx+y1*ny+z1*nz,d2=x2*nx+y2*ny+z2*nz;
        x0=x0-d0*nx;y0=y0-d0*ny;z0=z0-d0*nz;
        x1=x1-d1*nx;y1=y1-d1*ny;z1=z1-d1*nz;
        x2=x2-d2*nx;y2=y2-d2*ny;z2=z2-d2*nz;
        float e1x=x1-x0,e1y=y1-y0,e1z=z1-z0,e2x=x2-x0,e2y=y2-y0,e2z=z2-z0;
        float du1=u1-u0,dv1=v1-v0,du2=u2-u0,dv2=v2-v0;
        float denominator=du1*dv2-du2*dv1,f=denominator==0?1:1/denominator;
        float tx=f*(dv2*e1x-dv1*e2x),ty=f*(dv2*e1y-dv1*e2y),tz=f*(dv2*e1z-dv1*e2z);
        float scale=inverseRoot(tx*tx+ty*ty+tz*tz);tx*=scale;ty*=scale;tz*=scale;
        float bx=f*(-du2*e1x+du1*e2x),by=f*(-du2*e1y+du1*e2y),bz=f*(-du2*e1z+du1*e2z);
        scale=inverseRoot(bx*bx+by*by+bz*bz);bx*=scale;by*=scale;bz*=scale;
        float cx=ty*nz-tz*ny,cy=tz*nx-tx*nz,cz=tx*ny-ty*nx;
        return pack(tx,ty,tz,bx*cx+by*cy+bz*cz<0?-1:1);
    }

    private static void fillPlain(long p,float[] s,int[] inputs,float[] v,float alpha,int overlay,int light)
    {
        int distinct=s.length/6,color=color(alpha);
        if(packedNormals.length<distinct)packedNormals=new int[distinct];
        int[] normals=packedNormals;
        for(int input=0;input<distinct;input++)
        {
            int at=input*6;
            normals[input]=normalByte(s[at+3])|normalByte(s[at+4])<<8|normalByte(s[at+5])<<16;
        }
        for(int corner=3;corner<inputs.length;corner++)
        {
            int input=inputs[corner],at=input*6,i=corner*8;
            plainVertex(p,s[at],s[at+1],s[at+2],v[i+3],v[i+4],color,overlay,light,normals[input]);p+=36;
            if(corner%3==2){plainVertex(p,s[at],s[at+1],s[at+2],v[i+3],v[i+4],color,overlay,light,normals[input]);p+=36;}
        }
    }

    private static int normalByte(float value){return (int)(Mth.clamp(value,-1,1)*127)&255;}

    private static int color(float alpha){return (int)(alpha*255)<<24|0xFFFFFF;}

    private static void plainVertex(long p,float x,float y,float z,float u,float v,int color,int overlay,int light,int normal)
    {
        memPutFloat(p,x);memPutFloat(p+4,y);memPutFloat(p+8,z);memPutInt(p+12,color);
        memPutFloat(p+16,u);memPutFloat(p+20,v);memPutInt(p+24,overlay);memPutInt(p+28,light);memPutInt(p+32,normal);
    }

    /** Oculus's quad handling with the fourth corner repeating the third, as every quad here does. */
    private static void fillWidened(long p,float[] s,int[] inputs,float[] v,float alpha,int overlay,int light,int ids,short lastId)
    {
        int color=color(alpha);
        for(int corner=3;corner<inputs.length;corner+=3)
        {
            int a=inputs[corner]*6,b=inputs[corner+1]*6,c=inputs[corner+2]*6,ia=corner*8,ib=ia+8,ic=ib+8;
            float x0=s[a],y0=s[a+1],z0=s[a+2],x1=s[b],y1=s[b+1],z1=s[b+2],x2=s[c],y2=s[c+1],z2=s[c+2];
            float u0=v[ia+3],v0=v[ia+4],u1=v[ib+3],v1=v[ib+4],u2=v[ic+3],v2=v[ic+4];
            float midU=(0F+u0+u1+u2+u2)/4,midV=(0F+v0+v1+v2+v2)/4;
            float dx0=x2-x0,dy0=y2-y0,dz0=z2-z0,dx1=x2-x1,dy1=y2-y1,dz1=z2-z1;
            float nx=dy0*dz1-dz0*dy1,ny=dz0*dx1-dx0*dz1,nz=dx0*dy1-dy0*dx1;
            float length=(float)Math.sqrt(nx*nx+ny*ny+nz*nz);
            if(length!=0){nx/=length;ny/=length;nz/=length;}
            int normal=pack(nx,ny,nz,0),tangent=tangent(nx,ny,nz,x1-x0,y1-y0,z1-z0,dx0,dy0,dz0,u1-u0,v1-v0,u2-u0,v2-v0);
            widenedVertex(p,x0,y0,z0,u0,v0,color,overlay,light,normal,ids,lastId,midU,midV,tangent);
            widenedVertex(p+56,x1,y1,z1,u1,v1,color,overlay,light,normal,ids,lastId,midU,midV,tangent);
            widenedVertex(p+112,x2,y2,z2,u2,v2,color,overlay,light,normal,ids,lastId,midU,midV,tangent);
            widenedVertex(p+168,x2,y2,z2,u2,v2,color,overlay,light,normal,ids,lastId,midU,midV,tangent);
            p+=224;
        }
    }

    static int tangent(float nx,float ny,float nz,float e1x,float e1y,float e1z,float e2x,float e2y,float e2z,float du1,float dv1,float du2,float dv2)
    {
        float denominator=du1*dv2-du2*dv1,f=denominator==0?1:1/denominator;
        float tx=f*(dv2*e1x-dv1*e2x),ty=f*(dv2*e1y-dv1*e2y),tz=f*(dv2*e1z-dv1*e2z);
        float scale=inverseRoot(tx*tx+ty*ty+tz*tz);tx*=scale;ty*=scale;tz*=scale;
        float bx=f*(-du2*e1x+du1*e2x),by=f*(-du2*e1y+du1*e2y),bz=f*(-du2*e1z+du1*e2z);
        scale=inverseRoot(bx*bx+by*by+bz*bz);bx*=scale;by*=scale;bz*=scale;
        float px=ty*nz-tz*ny,py=tz*nx-tx*nz,pz=tx*ny-ty*nx;
        return pack(tx,ty,tz,bx*px+by*py+bz*pz<0?-1:1);
    }

    private static float inverseRoot(float value){return value==0?1:(float)(1/Math.sqrt(value));}

    static int pack(float x,float y,float z,float w)
    {
        return (int)(x*127)&255|((int)(y*127)&255)<<8|((int)(z*127)&255)<<16|((int)(w*127)&255)<<24;
    }

    private static void widenedVertex(long p,float x,float y,float z,float u,float v,int color,int overlay,int light,int normal,int ids,short lastId,float midU,float midV,int tangent)
    {
        plainVertex(p,x,y,z,u,v,color,overlay,light,normal);
        memPutInt(p+36,ids);memPutShort(p+40,lastId);memPutFloat(p+42,midU);memPutFloat(p+46,midV);memPutInt(p+50,tangent);
    }
}
