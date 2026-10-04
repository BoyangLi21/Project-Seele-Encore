package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.FirstBattleClip;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import org.joml.Vector3f;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Private topology-preserving soft-tissue performance, sampled on the shared actor clock. */
public final class SachielWrapSurface
{
    private static boolean attempted;
    private static Data data;
    private record Data(int start,int fps,int unique,int[] indices,float[] uv,float[][] positions,float[][] normals) {}
    public record Frame(Data source,int a,int b,float blend)
    {
        public int vertexCount(){return source.indices.length;}
        public float u(int vertex){return source.uv[vertex*2];}
        public float v(int vertex){return source.uv[vertex*2+1];}
        public void sample(int vertex,Vector3f point,Vector3f normal)
        {
            int i=source.indices[vertex]*3;
            float[] p=source.positions[a],q=source.positions[b],n=source.normals[a],m=source.normals[b];
            point.set(p[i]+(q[i]-p[i])*blend,p[i+1]+(q[i+1]-p[i+1])*blend,p[i+2]+(q[i+2]-p[i+2])*blend);
            normal.set(n[i]+(m[i]-n[i])*blend,n[i+1]+(m[i+1]-n[i+1])*blend,n[i+2]+(m[i+2]-n[i+2])*blend).normalize();
        }
    }
    public static void clear(){data=null;attempted=false;}
    public static void prepare(ResourceLocation mesh,int vertices)
    {
        if(!attempted&&!FirstBattleClip.surfaceHash().isEmpty()&&mesh.getPath().endsWith("sachiel.mesh.json"))load(mesh,vertices);
    }
    public static Frame frame(ResourceLocation mesh,int vertexCount,float seconds)
    {
        if(FirstBattleClip.surfaceHash().isEmpty()||!mesh.getPath().endsWith("sachiel.mesh.json"))return null;
        if(!attempted)load(mesh,vertexCount);
        if(data==null)return null;
        float f=seconds*data.fps-data.start;
        if(f<-.002F)return null;
        // Keep the final enveloping surface through the authoritative death gate;
        // a delayed removal packet must not reveal the old skeleton for one frame.
        f=Math.max(0,Math.min(data.positions.length-1,f));
        int a=(int)f,b=Math.min(a+1,data.positions.length-1);return new Frame(data,a,b,f-a);
    }
    private static void load(ResourceLocation mesh,int vertexCount)
    {
        attempted=true;
        try
        {
            Path path=com.projectseele.entity.CombatMotionResourcesR44.instancePath("projectseele-local-maps/sachiel_wrap_r14.bin");
            long size=Files.size(path);if(size<60||size>96*1024*1024)throw new IllegalArgumentException("Invalid wrap cache size");
            byte[] bytes=Files.readAllBytes(path);var digest=MessageDigest.getInstance("SHA-256");
            if(!HexFormat.of().formatHex(digest.digest(bytes)).equals(FirstBattleClip.surfaceHash()))throw new IllegalArgumentException("Movie / surface fingerprint mismatch");
            var buffer=ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
            if(buffer.getInt()!=0x53573134)throw new IllegalArgumentException("Invalid wrap cache header");
            int start=buffer.getInt(),count=buffer.getInt(),fps=buffer.getInt(),unique=buffer.getInt(),full=buffer.getInt(),base=buffer.getInt();
            if(start!=489||count!=70||fps!=30||unique<3||unique>100000||base!=vertexCount||full<base||full>700000||full%3!=0)throw new IllegalArgumentException("Invalid wrap cache topology");
            byte[] expected=new byte[32];buffer.get(expected);
            var resource=Minecraft.getInstance().getResourceManager().getResource(mesh).orElseThrow();
            try(var stream=resource.open())
            {
                if(!MessageDigest.isEqual(expected,digest.digest(stream.readAllBytes())))throw new IllegalArgumentException("Angel mesh / surface fingerprint mismatch");
            }
            if(size!=60L+full*12L+count*unique*12L)throw new IllegalArgumentException("Truncated wrap cache");
            int[] index=new int[full];for(int i=0;i<full;i++){index[i]=buffer.getInt();if(index[i]<0||index[i]>=unique)throw new IllegalArgumentException("Invalid wrap vertex index");}
            float[] uv=new float[full*2];for(int i=0;i<uv.length;i++){uv[i]=buffer.getFloat();if(!Float.isFinite(uv[i]))throw new IllegalArgumentException("Invalid wrap UV");}
            float[][] positions=new float[count][unique*3],normals=new float[count][unique*3];
            for(int f=0;f<count;f++)
            {
                float[] p=positions[f],n=normals[f];
                for(int i=0;i<p.length;i++){p[i]=buffer.getFloat();if(!Float.isFinite(p[i])||Math.abs(p[i])>512)throw new IllegalArgumentException("Invalid wrap coordinate");}
                for(int i=0;i<full;i+=3)
                {
                    int a=index[i]*3,b=index[i+1]*3,c=index[i+2]*3;
                    float ux=p[b]-p[a],uy=p[b+1]-p[a+1],uz=p[b+2]-p[a+2],vx=p[c]-p[a],vy=p[c+1]-p[a+1],vz=p[c+2]-p[a+2];
                    float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
                    n[a]+=nx;n[a+1]+=ny;n[a+2]+=nz;n[b]+=nx;n[b+1]+=ny;n[b+2]+=nz;n[c]+=nx;n[c+1]+=ny;n[c+2]+=nz;
                }
                for(int i=0;i<n.length;i+=3)
                {
                    float length=(float)Math.sqrt(n[i]*n[i]+n[i+1]*n[i+1]+n[i+2]*n[i+2]);
                    if(length<1e-8F){n[i+1]=1;continue;}n[i]/=length;n[i+1]/=length;n[i+2]/=length;
                }
            }
            data=new Data(start,fps,unique,index,uv,positions,normals);
            ProjectSeele.LOGGER.info("R14 Sachiel surface accepted: frames={} vertices={} bytes={}",count,unique,size);
        }
        catch(Exception e){ProjectSeele.LOGGER.error("R14 Sachiel surface rejected; retaining skeletal fallback",e);}
    }
    private SachielWrapSurface() {}
}
