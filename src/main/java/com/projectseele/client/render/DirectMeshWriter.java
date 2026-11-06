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
    private static int plainState,widenedState;
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

    private static int tangent(float nx,float ny,float nz,float e1x,float e1y,float e1z,float e2x,float e2y,float e2z,float du1,float dv1,float du2,float dv2)
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

    private static int pack(float x,float y,float z,float w)
    {
        return (int)(x*127)&255|((int)(y*127)&255)<<8|((int)(z*127)&255)<<16|((int)(w*127)&255)<<24;
    }

    private static void widenedVertex(long p,float x,float y,float z,float u,float v,int color,int overlay,int light,int normal,int ids,short lastId,float midU,float midV,int tangent)
    {
        plainVertex(p,x,y,z,u,v,color,overlay,light,normal);
        memPutInt(p+36,ids);memPutShort(p+40,lastId);memPutFloat(p+42,midU);memPutFloat(p+46,midV);memPutInt(p+50,tangent);
    }
}
