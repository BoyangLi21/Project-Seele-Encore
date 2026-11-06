package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.VertexConsumer;
import org.joml.Matrix4f;
import org.joml.Matrix3f;

/** Preserve Minecraft's vertex format while using BufferBuilder's complete-vertex fast path. */
public final class MeshVertexWriter
{
    public static void emit(VertexConsumer out,Matrix4f pose,Matrix3f normal,
                            float x,float y,float z,float u,float v,int light,int overlay,
                            float nx,float ny,float nz)
    {
        emitTinted(out,pose,normal,x,y,z,u,v,light,overlay,nx,ny,nz,1,1,1);
    }
    public static void emitTinted(VertexConsumer out,Matrix4f pose,Matrix3f normal,
                            float x,float y,float z,float u,float v,int light,int overlay,
                            float nx,float ny,float nz,float r,float g,float b)
    {
        float px=pose.m00()*x+pose.m10()*y+pose.m20()*z+pose.m30();
        float py=pose.m01()*x+pose.m11()*y+pose.m21()*z+pose.m31();
        float pz=pose.m02()*x+pose.m12()*y+pose.m22()*z+pose.m32();
        float ax=normal.m00()*nx+normal.m10()*ny+normal.m20()*nz;
        float ay=normal.m01()*nx+normal.m11()*ny+normal.m21()*nz;
        float az=normal.m02()*nx+normal.m12()*ny+normal.m22()*nz;
        out.vertex(px,py,pz,r,g,b,1,u,v,overlay,light,ax,ay,az);
    }
    /** Moves one {@code x y z nx ny nz} record into pose space in place, with the same arithmetic as {@link #emitTinted}. */
    public static void transform(float[] data,int at,Matrix4f pose,Matrix3f normal)
    {
        float x=data[at],y=data[at+1],z=data[at+2],nx=data[at+3],ny=data[at+4],nz=data[at+5];
        data[at]=pose.m00()*x+pose.m10()*y+pose.m20()*z+pose.m30();
        data[at+1]=pose.m01()*x+pose.m11()*y+pose.m21()*z+pose.m31();
        data[at+2]=pose.m02()*x+pose.m12()*y+pose.m22()*z+pose.m32();
        data[at+3]=normal.m00()*nx+normal.m10()*ny+normal.m20()*nz;
        data[at+4]=normal.m01()*nx+normal.m11()*ny+normal.m21()*nz;
        data[at+5]=normal.m02()*nx+normal.m12()*ny+normal.m22()*nz;
    }
    private MeshVertexWriter() {}
}
