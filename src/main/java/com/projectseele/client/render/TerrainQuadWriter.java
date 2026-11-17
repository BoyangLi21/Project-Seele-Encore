package com.projectseele.client.render;

import static org.lwjgl.system.MemoryUtil.memGetByte;
import static org.lwjgl.system.MemoryUtil.memGetInt;
import static org.lwjgl.system.MemoryUtil.memPutFloat;
import static org.lwjgl.system.MemoryUtil.memPutInt;
import static org.lwjgl.system.MemoryUtil.nmemAllocChecked;
import static org.lwjgl.system.MemoryUtil.nmemFree;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.ProjectSeele;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.Arrays;

/**
 * Block quads into a buffer that a shader pack has widened, as raw bytes.
 *
 * Under a shader pack Create cannot instance a moving contraption and pushes every vertex of it through the
 * buffer's element-by-element path each frame, in both passes. A lifted city district is tens of thousands of
 * blocks, and that path took two fifths of the render thread while the city moved. The bytes written here are the
 * ones that path writes, including what Oculus adds per quad (face normal, tangent, mid texture and mid block).
 *
 * Nothing checks that copy at compile time, so the first large meshes go through the normal path and are compared
 * byte for byte; raw writes start only after they match, and one difference turns them off for good. The first
 * quad of every mesh always takes the normal path, because it carries the block ids only Oculus knows.
 */
public final class TerrainQuadWriter
{
    private static final int STRIDE=52,UNTESTED=0,TRUSTED=1,REJECTED=-1;
    /** Meshes that must match before raw writes start, and the least quads a mesh needs to count. */
    private static final int CHECKED_MESHES=3,CHECKED_QUADS=64;
    private static final VertexFormat TERRAIN;
    private static final MethodHandle LOCAL_X,LOCAL_Y,LOCAL_Z,PENDING;
    private static int state,matched;

    // The mesh being drawn: one renderInto call on the render thread.
    private static VertexConsumer consumer;
    private static DirectVertexTarget target;
    private static int count,ids,localX,localY,localZ;
    private static boolean raw,recording;
    private static final float[] stage=new float[4*12];
    private static final int[] stageBits=new int[4*2];
    private static float[] recorded=new float[1<<14];
    private static int[] recordedBits=new int[1<<12];

    static
    {
        VertexFormat format=null;MethodHandle x=null,y=null,z=null,pending=null;
        try
        {
            format=(VertexFormat)Class.forName("net.irisshaders.iris.vertices.IrisVertexFormats").getField("TERRAIN").get(null);
            Class<?> builder=Class.forName("net.irisshaders.iris.vertices.IrisExtendedBufferBuilder");
            MethodHandles.Lookup lookup=MethodHandles.publicLookup();MethodType integer=MethodType.methodType(int.class);
            x=lookup.findVirtual(builder,"iris$currentLocalPosX",integer);y=lookup.findVirtual(builder,"iris$currentLocalPosY",integer);
            z=lookup.findVirtual(builder,"iris$currentLocalPosZ",integer);pending=lookup.findVirtual(builder,"iris$vertexCount",integer);
            if(format.getVertexSize()!=STRIDE)format=null;
        }
        catch(ReflectiveOperationException|LinkageError absent){format=null;}
        TERRAIN=format;LOCAL_X=x;LOCAL_Y=y;LOCAL_Z=z;PENDING=pending;
    }

    private TerrainQuadWriter() {}

    /** Start of one mesh. Without this, or for any other kind of buffer, every vertex takes the normal path. */
    public static void begin(VertexConsumer buffer)
    {
        consumer=null;target=null;count=0;raw=false;recording=false;
        if(state==REJECTED||TERRAIN==null||!RenderSystem.isOnRenderThread())return;
        if(buffer instanceof DirectVertexTarget direct&&direct.projectseele$quadFormat()==TERRAIN&&local(PENDING,buffer)==0)
        {
            consumer=buffer;target=direct;recording=state==UNTESTED;
        }
    }

    public static void vertex(VertexConsumer buffer,float x,float y,float z,float r,float g,float b,float a,float u,float v,int overlay,int light,float nx,float ny,float nz)
    {
        if(buffer!=consumer){buffer.vertex(x,y,z,r,g,b,a,u,v,overlay,light,nx,ny,nz);return;}
        int index=count++;
        if(!raw)
        {
            buffer.vertex(x,y,z,r,g,b,a,u,v,overlay,light,nx,ny,nz);
            if(index==3)
            {
                // The buffer must still be between quads of the widened block format; then its last vertex shows the ids.
                if(target.projectseele$quadFormat()!=TERRAIN){consumer=null;return;}
                ids=memGetInt(target.projectseele$end()-STRIDE+32);
                localX=local(LOCAL_X,buffer);localY=local(LOCAL_Y,buffer);localZ=local(LOCAL_Z,buffer);
                raw=state==TRUSTED;
            }
            else if(index>3&&recording)record(index-4,x,y,z,u,v,color(r,g,b,a),light);
            return;
        }
        int corner=index&3,at=corner*12;float[] s=stage;int[] n=stageBits;
        s[at]=x;s[at+1]=y;s[at+2]=z;s[at+3]=r;s[at+4]=g;s[at+5]=b;s[at+6]=a;s[at+7]=u;s[at+8]=v;s[at+9]=nx;s[at+10]=ny;s[at+11]=nz;
        n[corner*2]=overlay;n[corner*2+1]=light;
        if(corner==3)
        {
            long p=target.projectseele$reserve(4);
            quad(p,s[0],s[1],s[2],s[7],s[8],color(s[3],s[4],s[5],s[6]),n[1],
                    s[12],s[13],s[14],s[19],s[20],color(s[15],s[16],s[17],s[18]),n[3],
                    s[24],s[25],s[26],s[31],s[32],color(s[27],s[28],s[29],s[30]),n[5],
                    s[36],s[37],s[38],s[43],s[44],color(s[39],s[40],s[41],s[42]),n[7],
                    ids,localX,localY,localZ);
        }
    }

    /** End of the mesh: corners of an unfinished quad go the normal way, and a recorded mesh is compared. */
    public static void end()
    {
        VertexConsumer buffer=consumer;
        if(buffer==null)return;
        consumer=null;
        if(raw)
        {
            float[] s=stage;int[] n=stageBits;
            for(int corner=0,left=count&3;corner<left;corner++)
            {
                int at=corner*12;
                buffer.vertex(s[at],s[at+1],s[at+2],s[at+3],s[at+4],s[at+5],s[at+6],s[at+7],s[at+8],n[corner*2],n[corner*2+1],s[at+9],s[at+10],s[at+11]);
            }
            return;
        }
        int quads=(count-4)/4;
        if(!recording||count<4||(count&3)!=0||quads<CHECKED_QUADS||state!=UNTESTED||target.projectseele$quadFormat()!=TERRAIN)return;
        long size=(long)quads*4*STRIDE,written=target.projectseele$end()-size,copy=nmemAllocChecked(size);
        try
        {
            float[] f=recorded;int[] n=recordedBits;
            for(int q=0;q<quads;q++)
            {
                int a=q*20,i=q*8;
                quad(copy+(long)q*4*STRIDE,f[a],f[a+1],f[a+2],f[a+3],f[a+4],n[i],n[i+1],
                        f[a+5],f[a+6],f[a+7],f[a+8],f[a+9],n[i+2],n[i+3],
                        f[a+10],f[a+11],f[a+12],f[a+13],f[a+14],n[i+4],n[i+5],
                        f[a+15],f[a+16],f[a+17],f[a+18],f[a+19],n[i+6],n[i+7],ids,localX,localY,localZ);
            }
            for(long at=0;at<size;at++)if(memGetByte(written+at)!=memGetByte(copy+at))
            {
                state=REJECTED;
                ProjectSeele.LOGGER.warn("Direct block quads disabled: vertex {} byte {} is {} on the normal path and {} here",at/STRIDE,at%STRIDE,memGetByte(written+at),memGetByte(copy+at));
                return;
            }
        }
        finally{nmemFree(copy);}
        if(++matched>=CHECKED_MESHES)
        {
            state=TRUSTED;
            ProjectSeele.LOGGER.info("Direct block quads verified for {} byte vertices over {} meshes, the last of {} quads",STRIDE,matched,quads);
        }
    }

    private static void record(int vertex,float x,float y,float z,float u,float v,int color,int light)
    {
        if(vertex*5+5>recorded.length)recorded=Arrays.copyOf(recorded,recorded.length*2);
        if(vertex*2+2>recordedBits.length)recordedBits=Arrays.copyOf(recordedBits,recordedBits.length*2);
        int at=vertex*5;
        recorded[at]=x;recorded[at+1]=y;recorded[at+2]=z;recorded[at+3]=u;recorded[at+4]=v;
        recordedBits[vertex*2]=color;recordedBits[vertex*2+1]=light;
    }

    private static int local(MethodHandle getter,VertexConsumer buffer)
    {
        try{return (int)getter.invoke(buffer);}
        catch(Throwable changed){state=REJECTED;return -1;}
    }

    private static int color(float r,float g,float b,float a)
    {
        return (int)(r*255.0F)&255|((int)(g*255.0F)&255)<<8|((int)(b*255.0F)&255)<<16|((int)(a*255.0F)&255)<<24;
    }

    /** One quad as the normal path leaves it once Oculus has filled in the quad's shared values. */
    private static void quad(long p,float x0,float y0,float z0,float u0,float v0,int c0,int l0,
                             float x1,float y1,float z1,float u1,float v1,int c1,int l1,
                             float x2,float y2,float z2,float u2,float v2,int c2,int l2,
                             float x3,float y3,float z3,float u3,float v3,int c3,int l3,int ids,int lx,int ly,int lz)
    {
        float midU=(0F+u0+u1+u2+u3)/4,midV=(0F+v0+v1+v2+v3)/4;
        float dx0=x2-x0,dy0=y2-y0,dz0=z2-z0,dx1=x3-x1,dy1=y3-y1,dz1=z3-z1;
        float nx=dy0*dz1-dz0*dy1,ny=dz0*dx1-dx0*dz1,nz=dx0*dy1-dy0*dx1;
        float length=(float)Math.sqrt(nx*nx+ny*ny+nz*nz);
        if(length!=0){nx/=length;ny/=length;nz/=length;}
        int normal=DirectMeshWriter.pack(nx,ny,nz,0),tangent=DirectMeshWriter.tangent(nx,ny,nz,x1-x0,y1-y0,z1-z0,dx0,dy0,dz0,u1-u0,v1-v0,u2-u0,v2-v0);
        corner(p,x0,y0,z0,u0,v0,c0,l0,normal,ids,midU,midV,tangent,lx,ly,lz);
        corner(p+STRIDE,x1,y1,z1,u1,v1,c1,l1,normal,ids,midU,midV,tangent,lx,ly,lz);
        corner(p+2*STRIDE,x2,y2,z2,u2,v2,c2,l2,normal,ids,midU,midV,tangent,lx,ly,lz);
        corner(p+3*STRIDE,x3,y3,z3,u3,v3,c3,l3,normal,ids,midU,midV,tangent,lx,ly,lz);
    }

    private static void corner(long p,float x,float y,float z,float u,float v,int color,int light,int normal,int ids,float midU,float midV,int tangent,int lx,int ly,int lz)
    {
        memPutFloat(p,x);memPutFloat(p+4,y);memPutFloat(p+8,z);memPutInt(p+12,color);
        memPutFloat(p+16,u);memPutFloat(p+20,v);memPutInt(p+24,light);memPutInt(p+28,normal);
        memPutInt(p+32,ids);memPutFloat(p+36,midU);memPutFloat(p+40,midV);memPutInt(p+44,tangent);
        // Oculus: the offset from the vertex to the middle of the block being drawn, in 64ths, one byte per axis.
        memPutInt(p+48,(int)((lx+.5F-x)*64.0F)&255|((int)((ly+.5F-y)*64.0F)&255)<<8|((int)((lz+.5F-z)*64.0F)&255)<<16);
    }
}
