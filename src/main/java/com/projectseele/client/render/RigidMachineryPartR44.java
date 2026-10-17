package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.stream.JsonReader;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.OutlineBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import org.joml.Vector4f;
import org.joml.Matrix4f;
import java.util.Arrays;
import java.util.ArrayList;
import java.util.List;
import java.io.IOException;

/** Cached rigid geometry emitted through the ordinary entity material and shadow pass. */
final class RigidMachineryPartR44
{
    private static final ResourceLocation PAINT = new ResourceLocation("projectseele", "textures/entity/machinery_paint_r44.png");
    private static final int STRIDE = 11;
    private final float[] vertices;
    private final float[] bounds;
    private final ResourceLocation texture;
    private final boolean importedTriangles;

    private RigidMachineryPartR44(float[] vertices, float[] bounds)
    {
        this(vertices, bounds, PAINT);
    }

    private RigidMachineryPartR44(float[] vertices, float[] bounds, ResourceLocation texture)
    {
        this(vertices,bounds,texture,false);
    }

    private RigidMachineryPartR44(float[] vertices,float[] bounds,ResourceLocation texture,boolean importedTriangles)
    {
        this.vertices = vertices;
        this.bounds = bounds;
        this.texture = texture;
        this.importedTriangles=importedTriangles;
    }

    /** Imported rigid triangles keep their original UVs and smooth vertex normals. */
    static RigidMachineryPartR44 textured(JsonArray encoded, ResourceLocation texture)
    {
        if (encoded.size() % 24 != 0) throw new IllegalArgumentException("Triangle XYZ/UV/normal layout required");
        var builder = new TexturedBuilder();
        float[] triangle = new float[24];
        for (int start = 0; start < encoded.size(); start += 24)
        {
            for (int i = 0; i < 24; i++) triangle[i] = encoded.get(start + i).getAsFloat();
            builder.triangle(triangle);
        }
        return builder.finish(texture);
    }

    /** Texture may follow parts in a resource document. Bind only after the
     * whole assembly is validated; the primitive vertices are never copied. */
    RigidMachineryPartR44 withTexture(ResourceLocation material)
    {return new RigidMachineryPartR44(vertices,bounds,material,importedTriangles);}

    static RigidMachineryPartR44 readTextured(JsonReader encoded) throws IOException
    {
        var builder = new TexturedBuilder();
        float[] triangle = new float[24];int count = 0;
        encoded.beginArray();
        while(encoded.hasNext())
        {
            // Gson's numeric JsonPrimitive.getAsFloat uses this same decimal
            // to-float conversion. Reading as double first changes rounding.
            triangle[count++] = Float.parseFloat(encoded.nextString());
            if(count == 24){builder.triangle(triangle);count = 0;}
        }
        encoded.endArray();
        if(count != 0)throw new IllegalArgumentException("Triangle XYZ/UV/normal layout required");
        return builder.finish(null);
    }

    private static final class TexturedBuilder
    {
        private static final int CHUNK = STRIDE * 4 * 1024;
        private final List<float[]> chunks = new ArrayList<>();
        private final float[] box = {Float.POSITIVE_INFINITY,Float.POSITIVE_INFINITY,Float.POSITIVE_INFINITY,
                Float.NEGATIVE_INFINITY,Float.NEGATIVE_INFINITY,Float.NEGATIVE_INFINITY};
        private int size;
        void triangle(float[] source)
        {
            for(int i = 0;i < 24;i++)if(!Float.isFinite(source[i]))throw new IllegalArgumentException("Non-finite imported machinery");
            int cursor = size % CHUNK;if(cursor == 0)chunks.add(new float[CHUNK]);
            float[] out = chunks.get(chunks.size()-1);
            for(int corner = 0;corner < 4;corner++)
            {
                int offset = (corner == 3?2:corner)*8;
                float x = source[offset],y = source[offset+1],z = source[offset+2];
                box[0] = Math.min(box[0],x);box[1] = Math.min(box[1],y);box[2] = Math.min(box[2],z);
                box[3] = Math.max(box[3],x);box[4] = Math.max(box[4],y);box[5] = Math.max(box[5],z);
                out[cursor++] = x;out[cursor++] = y;out[cursor++] = z;
                out[cursor++] = 1;out[cursor++] = 1;out[cursor++] = 1;
                out[cursor++] = source[offset+5];out[cursor++] = source[offset+6];out[cursor++] = source[offset+7];
                out[cursor++] = source[offset+3];out[cursor++] = source[offset+4];
            }
            size = Math.addExact(size,STRIDE*4);
        }
        RigidMachineryPartR44 finish(ResourceLocation material)
        {
            float[] values = new float[size];int copied = 0;
            for(var chunk:chunks){int length = Math.min(CHUNK,size-copied);System.arraycopy(chunk,0,values,copied,length);copied += length;}
            return new RigidMachineryPartR44(values,box,material,true);
        }
    }

    static RigidMachineryPartR44 triangles(JsonArray encoded)
    {
        if (encoded.size() % 18 != 0) throw new IllegalArgumentException("Triangle RGB layout required");
        Builder builder = new Builder();
        for (int i = 0; i < encoded.size(); i += 18)
        {
            Vec3 a = point(encoded, i), b = point(encoded, i + 6), c = point(encoded, i + 12);
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.lengthSqr() < 1e-12) continue;
            normal = normal.normalize();
            builder.vertex(a, normal, encoded, i, 0, 0);
            builder.vertex(b, normal, encoded, i + 6, 1, 0);
            builder.vertex(c, normal, encoded, i + 12, 1, 1);
            builder.vertex(c, normal, encoded, i + 12, 1, 1);
        }
        return builder.finish();
    }
    /** New upright model/path schema stores RGB in0..1, unlike old TV byte RGB. */
    static RigidMachineryPartR44 trianglesNormalizedR52(double[] rgb)
    {if(rgb.length%18!=0)throw new IllegalArgumentException("Actual normalized triangle RGB required");var b=new Builder();for(int i=0;i<rgb.length;i+=18)b.triangleNormalizedR52(rgb,i,com.projectseele.world.RigidTransform.identity(),Vec3.ZERO);return b.finish();}

    private static Vec3 point(JsonArray data, int index)
    {
        return new Vec3(data.get(index).getAsDouble(), data.get(index + 1).getAsDouble(), data.get(index + 2).getAsDouble());
    }

    float[] bounds()
    {
        return bounds.clone();
    }

    void draw(PoseStack poses, MultiBufferSource buffers, int light)
    {
        if(RigidMachineryGpuR44.enabled()&&!(buffers instanceof OutlineBufferSource)
                &&!ShaderShadowPassR44.active()&&!Boolean.getBoolean("projectseele.r44NativeCraneMeshWitness")
                &&outsideClipR60(bounds,RenderSystem.getProjectionMatrix(),RenderSystem.getModelViewMatrix(),poses.last().pose()))return;
        drawWithProofR52(poses,buffers,light);
    }
    private static double[] absoluteProductR60(Matrix4f matrix,double[] v)
    {
        var result=new double[4];for(int row=0;row<4;row++)for(int column=0;column<4;column++)result[row]+=Math.abs((double)matrix.get(column,row))*v[column];return result;
    }
    /** Reject only when every actual float bound corner lies strictly outside one homogeneous clip plane. */
    static boolean outsideClipR60(float[] b,Matrix4f projection,Matrix4f modelView,Matrix4f pose)
    {
        if(b.length!=6)return false;for(float value:b)if(!Float.isFinite(value))return false;if(b[0]>b[3]||b[1]>b[4]||b[2]>b[5])return false;
        var magnitude=absoluteProductR60(projection,absoluteProductR60(modelView,absoluteProductR60(pose,new double[]{Math.max(Math.abs(b[0]),Math.abs(b[3])),Math.max(Math.abs(b[1]),Math.abs(b[4])),Math.max(Math.abs(b[2]),Math.abs(b[5])),1})));
        double absolute=1;for(double value:magnitude){if(!Double.isFinite(value))return false;absolute=Math.max(absolute,value);}
        // Three float matrix products have at most21 dot-product rounding stages.
        // A128-unit-roundoff envelope also covers association/FMA differences.
        double epsilon=128*Math.scalb(1D,-24)*absolute;var viewProjection=new Matrix4f(projection).mul(modelView);boolean[] outside={true,true,true,true,true,true};
        for(int corner=0;corner<8;corner++){
            var p=new Vector4f(b[(corner&1)==0?0:3],b[(corner&2)==0?1:4],b[(corner&4)==0?2:5],1);pose.transform(p);viewProjection.transform(p);
            if(!Float.isFinite(p.x)||!Float.isFinite(p.y)||!Float.isFinite(p.z)||!Float.isFinite(p.w))return false;
            outside[0]&=(double)p.x+p.w<-epsilon;outside[1]&=(double)p.w-p.x<-epsilon;outside[2]&=(double)p.y+p.w<-epsilon;outside[3]&=(double)p.w-p.y<-epsilon;outside[4]&=(double)p.z+p.w<-epsilon;outside[5]&=(double)p.w-p.z<-epsilon;
        }
        for(boolean plane:outside)if(plane)return true;return false;
    }
    /** True means the real cached GPU mesh was submitted in this shader pass. */
    boolean drawWithProofR52(PoseStack poses, MultiBufferSource buffers, int light)
    {
        TvCraneMeshWitnessR44.part(vertices,poses);
        // Keep the source arrays unchanged. Only imported smooth triangles
        // omit their duplicated fourth point; vanilla outlines remain quads.
        boolean triangles=importedTriangles&&!(buffers instanceof OutlineBufferSource);
        if (RigidMachineryGpuR44.draw(this, vertices, texture, poses, buffers, light,triangles)) return true;
        VertexConsumer out = buffers.getBuffer(triangles?ModelRenderTypesR49.solidTriangles(texture):ModelRenderTypesR49.solid(texture));
        var frame = poses.last();
        boolean reflected = frame.pose().determinant() < 0;
        Vector3f normal = new Vector3f();
        for (int quad = 0; quad < vertices.length; quad += STRIDE * 4)
        {
            int corners=triangles?3:4;
            for (int j = 0; j < corners; j++)
            {
                int index = quad + (reflected ? corners-1-j : j) * STRIDE;
                normal.set(vertices[index + 6], vertices[index + 7], vertices[index + 8]);
                normal.mul(frame.normal()).normalize();
                out.vertex(frame.pose(), vertices[index], vertices[index + 1], vertices[index + 2])
                        .color(vertices[index + 3], vertices[index + 4], vertices[index + 5], 1)
                        .uv(vertices[index + 9], vertices[index + 10])
                        .overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light)
                        .normal(normal.x, normal.y, normal.z).endVertex();
            }
        }
        return false;
    }

    static final class Builder
    {
        private float[] data = new float[4096];
        private int size;
        private final float[] box = {Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY,
                Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY};

        void quad(Vec3 a, Vec3 b, Vec3 c, Vec3 d, int color)
        {
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.lengthSqr() < 1e-12) return;
            normal = normal.normalize();
            float red = ((color >> 16) & 255) / 255F;
            float green = ((color >> 8) & 255) / 255F;
            float blue = (color & 255) / 255F;
            vertex(a, normal, red, green, blue, 0, 0);
            vertex(b, normal, red, green, blue, 1, 0);
            vertex(c, normal, red, green, blue, 1, 1);
            vertex(d, normal, red, green, blue, 0, 1);
        }

        private void vertex(Vec3 p, Vec3 normal, JsonArray source, int index, float u, float v)
        {
            vertex(p, normal, source.get(index + 3).getAsFloat() / 255,
                    source.get(index + 4).getAsFloat() / 255, source.get(index + 5).getAsFloat() / 255, u, v);
        }

        private void vertex(Vec3 p, Vec3 n, float red, float green, float blue, float u, float v)
        {
            if (size + STRIDE > data.length) data = Arrays.copyOf(data, data.length * 2);
            float[] values = {(float)p.x, (float)p.y, (float)p.z, red, green, blue, (float)n.x, (float)n.y, (float)n.z, u, v};
            for (int i = 0; i < values.length; i++)
            {
                if (!Float.isFinite(values[i])) throw new IllegalArgumentException("Non-finite machinery vertex");
                data[size++] = values[i];
            }
            box[0] = Math.min(box[0], (float)p.x); box[3] = Math.max(box[3], (float)p.x);
            box[1] = Math.min(box[1], (float)p.y); box[4] = Math.max(box[4], (float)p.y);
            box[2] = Math.min(box[2], (float)p.z); box[5] = Math.max(box[5], (float)p.z);
        }

        RigidMachineryPartR44 finish()
        {
            if (size == 0) Arrays.fill(box, 0);
            return new RigidMachineryPartR44(Arrays.copyOf(data, size), box.clone());
        }
        void triangleNormalizedR52(double[] source,int offset,com.projectseele.world.RigidTransform frame,Vec3 origin)
        {
            var a=frame.transformPoint(new Vec3(source[offset],source[offset+1],source[offset+2])).subtract(origin);
            var b=frame.transformPoint(new Vec3(source[offset+6],source[offset+7],source[offset+8])).subtract(origin);
            var c=frame.transformPoint(new Vec3(source[offset+12],source[offset+13],source[offset+14])).subtract(origin);
            var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()<1e-12)return;normal=normal.normalize();
            normalizedVertexR52(a,normal,source,offset,0,0);normalizedVertexR52(b,normal,source,offset+6,1,0);normalizedVertexR52(c,normal,source,offset+12,1,1);normalizedVertexR52(c,normal,source,offset+12,1,1);
        }
        private void normalizedVertexR52(Vec3 p,Vec3 normal,double[] source,int offset,float u,float v)
        {for(int i=3;i<6;i++)if(!Double.isFinite(source[offset+i])||source[offset+i]<0||source[offset+i]>1)throw new IllegalArgumentException("Actual upright normalized RGB outside0..1");vertex(p,normal,(float)source[offset+3],(float)source[offset+4],(float)source[offset+5],u,v);}
    }
}
