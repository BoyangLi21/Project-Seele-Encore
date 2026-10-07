package com.projectseele.client.render;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.projectseele.ProjectSeele;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterShadersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import java.io.IOException;
import java.util.IdentityHashMap;
import java.util.Map;

/** Rigid local parts keep their real bone matrices and exact UVs on the GPU. Weighted seams stay on their existing path. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT,bus=Mod.EventBusSubscriber.Bus.MOD)
public final class RigidCapsuleGpu
{
    private static ShaderInstance shader;
    private static boolean shaderApiResolved,externalShader;
    private static Object shaderApi;
    private static java.lang.reflect.Method shaderPackActive;
    private static long shaderQueryTick=Long.MIN_VALUE;
    private static final Map<Object,VertexBuffer> PARTS=new IdentityHashMap<>();
    private record ExternalMesh(VertexBuffer buffer,int light,int overlay){}
    private static final Map<Object,Map<ResourceLocation,ExternalMesh>> EXTERNAL_PARTS=new IdentityHashMap<>();
    private static boolean externalReadyLogged;
    public static long drawCalls;
    static ShaderInstance machineryShader(){return shader;}
    @SubscribeEvent public static void register(RegisterShadersEvent event)throws IOException
    {
        event.registerShader(new ShaderInstance(event.getResourceProvider(),new ResourceLocation(ProjectSeele.MODID,"rigid_capsule"),DefaultVertexFormat.NEW_ENTITY),instance->{shader=instance;ProjectSeele.LOGGER.info("Rigid local-mesh GPU shader ready");});
    }
    public static boolean draw(Object key,float[] vertices,int stride,float px,float py,float pz,
                               ResourceLocation texture,PoseStack poses,int light,int overlay)
    {return draw(key,vertices,stride,px,py,pz,texture,poses,light,overlay,1,1,1);}
    public static boolean draw(Object key,float[] vertices,int stride,float px,float py,float pz,
                               ResourceLocation texture,PoseStack poses,int light,int overlay,float r,float g,float b)
    {
        if(shader==null||Boolean.getBoolean("projectseele.disableRigidCapsuleGpu"))return false;
        if(externalShaderActive())return drawExternal(key,vertices,stride,px,py,pz,texture,poses,light,overlay,r,g,b);
        VertexBuffer mesh=PARTS.get(key);
        if(mesh==null)
        {
            int count=vertices.length/stride/3*4;
            BufferBuilder builder=new BufferBuilder(Math.max(1024,count*DefaultVertexFormat.NEW_ENTITY.getVertexSize()+64));
            builder.begin(VertexFormat.Mode.QUADS,DefaultVertexFormat.NEW_ENTITY);
            for(int i=0;i+stride*3<=vertices.length;i+=stride*3)
            {
                vertex(builder,vertices,i,px,py,pz,r,g,b);vertex(builder,vertices,i+stride,px,py,pz,r,g,b);vertex(builder,vertices,i+stride*2,px,py,pz,r,g,b);vertex(builder,vertices,i+stride*2,px,py,pz,r,g,b);
            }
            mesh=new VertexBuffer(VertexBuffer.Usage.STATIC);mesh.bind();mesh.upload(builder.end());VertexBuffer.unbind();PARTS.put(key,mesh);
            if(PARTS.size()==1)ProjectSeele.LOGGER.info("Rigid local-mesh GPU draw path active; first part vertices={}",count);
        }
        var type=ModelRenderTypesR49.entity(texture);type.setupRenderState();RenderSystem.setShader(()->shader);
        shader.safeGetUniform("BoneMat").set(poses.last().pose());shader.safeGetUniform("BoneNormal").set(poses.last().normal());
        shader.safeGetUniform("FrameLight").set((float)(light&65535),(float)(light>>>16&65535));
        shader.safeGetUniform("FrameOverlay").set((float)(overlay&65535),(float)(overlay>>>16&65535));
        mesh.bind();mesh.drawWithShader(RenderSystem.getModelViewMatrix(),RenderSystem.getProjectionMatrix(),shader);VertexBuffer.unbind();type.clearRenderState();drawCalls++;return true;
    }
    private static void vertex(BufferBuilder b,float[] a,int i,float px,float py,float pz,float r,float g,float blue)
    {
        b.vertex(-(a[i]+px)/16,(a[i+1]+py)/16,(a[i+2]+pz)/16,r,g,blue,1,a[i+3],a[i+4],0,0,-a[i+5],a[i+6],a[i+7]);
    }
    private static boolean drawExternal(Object key,float[] vertices,int stride,float px,float py,float pz,ResourceLocation texture,PoseStack poses,int light,int overlay,float r,float g,float b)
    {
        var type=ModelRenderTypesR49.entity(texture);type.setupRenderState();var active=RenderSystem.getShader();
        if(active==null||!active.getClass().getName().contains("ExtendedShader")){type.clearRenderState();return false;}
        var layers=EXTERNAL_PARTS.computeIfAbsent(key,k->new java.util.HashMap<>());var cached=layers.get(texture);
        if(cached==null||cached.light()!=light||cached.overlay()!=overlay)
        {
            if(cached!=null)cached.buffer().close();int count=vertices.length/stride/3*4;
            // Iris extends this builder with its own entity/tangent attributes.
            // Reuse the active shader and framebuffer instead of bypassing it
            // with our vanilla-only shader. ExtendedShader derives its normal
            // matrix from the supplied model-view matrix on every apply().
            BufferBuilder builder=new BufferBuilder(Math.max(1024,count*96+64));builder.begin(VertexFormat.Mode.QUADS,DefaultVertexFormat.NEW_ENTITY);
            for(int i=0;i+stride*3<=vertices.length;i+=stride*3)for(int corner:new int[]{0,1,2,2})
            {int at=i+corner*stride;builder.vertex(-(vertices[at]+px)/16,(vertices[at+1]+py)/16,(vertices[at+2]+pz)/16,r,g,b,1,vertices[at+3],vertices[at+4],overlay,light,-vertices[at+5],vertices[at+6],vertices[at+7]);}
            VertexBuffer buffer=new VertexBuffer(VertexBuffer.Usage.STATIC);buffer.bind();buffer.upload(builder.end());VertexBuffer.unbind();cached=new ExternalMesh(buffer,light,overlay);layers.put(texture,cached);
        }
        var combined=new Matrix4f(RenderSystem.getModelViewMatrix()).mul(poses.last().pose());cached.buffer().bind();cached.buffer().drawWithShader(combined,RenderSystem.getProjectionMatrix(),active);EvaMaterialAuditR37.capture(texture,active);VertexBuffer.unbind();type.clearRenderState();drawCalls++;
        if(!externalReadyLogged){externalReadyLogged=true;ProjectSeele.LOGGER.info("R30 rigid GPU buffers active inside the Oculus entity pipeline");}
        return true;
    }
    public static void clear()
    {
        Runnable release=()->{PARTS.values().forEach(VertexBuffer::close);PARTS.clear();EXTERNAL_PARTS.values().forEach(v->v.values().forEach(p->p.buffer().close()));EXTERNAL_PARTS.clear();};
        if(RenderSystem.isOnRenderThread())release.run();else RenderSystem.recordRenderCall(release::run);
    }
    private static boolean externalShaderActive()
    {
        if(!shaderApiResolved)
        {
            shaderApiResolved=true;
            if(!net.minecraftforge.fml.ModList.get().isLoaded("oculus"))return false;
            try
            {
                var api=Class.forName("net.irisshaders.iris.api.v0.IrisApi");shaderApi=api.getMethod("getInstance").invoke(null);shaderPackActive=api.getMethod("isShaderPackInUse");
            }
            catch(ReflectiveOperationException error){externalShader=true;ProjectSeele.LOGGER.warn("Oculus API unavailable; using standard entity vertices",error);}
        }
        if(shaderPackActive==null)return externalShader;
        long now=System.nanoTime()/50_000_000L;
        if(now!=shaderQueryTick)
        {
            shaderQueryTick=now;
            try{externalShader=(boolean)shaderPackActive.invoke(shaderApi);}
            catch(ReflectiveOperationException error){externalShader=true;}
        }
        return externalShader;
    }
    private RigidCapsuleGpu() {}
}
