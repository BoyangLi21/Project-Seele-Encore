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
    private record Mesh(VertexBuffer buffer,long revision,float red,float green,float blue) {}
    private static final Map<Object,Mesh> PARTS=new IdentityHashMap<>();
    private record MaterialIds(int entity,int blockEntity,int item) {}
    private record ExternalKey(ResourceLocation texture,boolean shadow,int light,int overlay,
                               int red,int green,int blue,MaterialIds material) {}
    private record ExternalMesh(VertexBuffer buffer,long revision,int light,int overlay,float red,float green,float blue,MaterialIds material,boolean shadow){}
    private static final class ExternalStates
    {
        final BoundedRenderStatesR52<ExternalKey,ExternalMesh> variants;
        ExternalKey last;
        long geometryRevision=Long.MIN_VALUE;
        ExternalStates(int limit){variants=new BoundedRenderStatesR52<>(limit,value->value.buffer().close());}
    }
    private static final Map<Object,ExternalStates> EXTERNAL_PARTS=new IdentityHashMap<>();
    private static boolean externalReadyLogged;
    private static boolean posedReadyLogged;
    private static boolean materialApiResolved;
    private static Object materialState;
    private static java.lang.reflect.Method materialEntity,materialBlockEntity,materialItem;
    // MemoryTracker owns a raw malloc block, not a GC-cleaned direct buffer.
    // Keep one growing uploader for all parts and retain it across reloads.
    private static BufferBuilder uploadBuilder;
    public static long drawCalls;
    public static long posedUploads,posedDrawCalls;
    public static long uploadBuilderCreations;
    public static long rigidExternalHits,rigidExternalMisses,externalStateEvictions;
    public static long rigidLightSwitches,rigidOverlaySwitches,rigidMaterialSwitches,rigidShadowSwitches;
    private static int stateDiagnostics;
    public static long posedColdUploads,posedRevisionUploads,posedShadingOnlyUploads;
    public static long posedMaterialUploads,posedLightUploads,posedOverlayUploads,posedTintUploads,posedPassChangedUploads;
    public static long posedStateHits,posedStateMisses,posedOldStateReleases;
    private static int posedDiagnostics;
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
    {return drawPosed(key,0,vertices,stride,px,py,pz,texture,poses,light,overlay,r,g,b);}
    /** Geometry revision is exact pose state; buffers are bounded by source parts, not entities. */
    static boolean drawPosed(Object key,long revision,float[] vertices,int stride,float px,float py,float pz,
                             ResourceLocation texture,PoseStack poses,int light,int overlay,float r,float g,float b)
    {
        if(shader==null||Boolean.getBoolean("projectseele.disableRigidCapsuleGpu")
                ||revision>0&&Boolean.getBoolean("projectseele.disablePosedMeshGpuR52"))return false;
        if(externalShaderActive())return drawExternal(key,revision,vertices,stride,px,py,pz,texture,poses,light,overlay,r,g,b);
        Mesh mesh=PARTS.get(key);
        if(mesh==null||mesh.revision()!=revision||mesh.red()!=r||mesh.green()!=g||mesh.blue()!=b)
        {
            int count=vertices.length/stride;
            BufferBuilder builder=beginUpload();
            for(int i=0;i+stride*3<=vertices.length;i+=stride*3)
            {
                vertex(builder,vertices,i,px,py,pz,r,g,b);vertex(builder,vertices,i+stride,px,py,pz,r,g,b);vertex(builder,vertices,i+stride*2,px,py,pz,r,g,b);
            }
            var buffer=mesh==null?new VertexBuffer(revision==0?VertexBuffer.Usage.STATIC:VertexBuffer.Usage.DYNAMIC):mesh.buffer();
            if(!upload(buffer,builder)){if(mesh==null)buffer.close();return false;}
            mesh=new Mesh(buffer,revision,r,g,b);PARTS.put(key,mesh);
            if(revision>0)posedUploads++;
            if(PARTS.size()==1)ProjectSeele.LOGGER.info("Rigid local-mesh GPU draw path active; first part vertices={}",count);
        }
        var type=ModelRenderTypesR49.entityTriangles(texture);type.setupRenderState();RenderSystem.setShader(()->shader);
        shader.safeGetUniform("BoneMat").set(poses.last().pose());shader.safeGetUniform("BoneNormal").set(poses.last().normal());
        shader.safeGetUniform("FrameLight").set((float)(light&65535),(float)(light>>>16&65535));
        shader.safeGetUniform("FrameOverlay").set((float)(overlay&65535),(float)(overlay>>>16&65535));
        mesh.buffer().bind();mesh.buffer().drawWithShader(RenderSystem.getModelViewMatrix(),RenderSystem.getProjectionMatrix(),shader);VertexBuffer.unbind();type.clearRenderState();drawCalls++;posedDraw(revision);return true;
    }
    private static void vertex(BufferBuilder b,float[] a,int i,float px,float py,float pz,float r,float g,float blue)
    {
        b.vertex(-(a[i]+px)/16,(a[i+1]+py)/16,(a[i+2]+pz)/16,r,g,blue,1,a[i+3],a[i+4],0,0,-a[i+5],a[i+6],a[i+7]);
    }
    private static boolean drawExternal(Object key,long revision,float[] vertices,int stride,float px,float py,float pz,ResourceLocation texture,PoseStack poses,int light,int overlay,float r,float g,float b)
    {
        var material=materialIds();if(material==null)return false;
        var type=ModelRenderTypesR49.entityTriangles(texture);type.setupRenderState();var active=RenderSystem.getShader();
        if(active==null||!active.getClass().getName().contains("ExtendedShader")){type.clearRenderState();return false;}
        var states=EXTERNAL_PARTS.computeIfAbsent(key,k->new ExternalStates(4));
        boolean shadow=ShaderShadowPassR44.active();
        var state=new ExternalKey(texture,shadow,light,overlay,
                Float.floatToRawIntBits(r),Float.floatToRawIntBits(g),Float.floatToRawIntBits(b),material);
        var cached=states.variants.get(state);
        if(revision>0)
        {
            if(cached==null)posedStateMisses++;else posedStateHits++;
            if(states.geometryRevision!=revision)
            {
                // Other shading slots belong to the old evaluated geometry.
                // Keep the selected VBO for an in-place update; release the rest.
                posedOldStateReleases+=states.variants.retain(state);
                states.geometryRevision=revision;
            }
        }
        if(revision==0)
        {
            if(cached==null)rigidExternalMisses++;else rigidExternalHits++;
            if(states.last!=null&&!states.last.equals(state))
            {
                if(states.last.light()!=state.light())rigidLightSwitches++;
                if(states.last.overlay()!=state.overlay())rigidOverlaySwitches++;
                if(!states.last.material().equals(state.material()))rigidMaterialSwitches++;
                if(states.last.shadow()!=state.shadow())rigidShadowSwitches++;
                if(cached==null&&stateDiagnostics<8)
                {
                    stateDiagnostics++;
                    ProjectSeele.LOGGER.info("R52 rigid VBO state transition: previous={} current={}",states.last,state);
                }
            }
        }
        states.last=state;
        if(cached==null||cached.revision()!=revision||cached.light()!=light||cached.overlay()!=overlay
                ||cached.red()!=r||cached.green()!=g||cached.blue()!=b||!cached.material().equals(material))
        {
            int count=vertices.length/stride;
            // Iris extends this builder with its own entity/tangent attributes.
            // Reuse the active shader and framebuffer instead of bypassing it
            // with our vanilla-only shader. ExtendedShader derives its normal
            // matrix from the supplied model-view matrix on every apply().
            BufferBuilder builder=beginUpload();
            for(int i=0;i+stride*3<=vertices.length;i+=stride*3)for(int corner=0;corner<3;corner++)
            {int at=i+corner*stride;builder.vertex(-(vertices[at]+px)/16,(vertices[at+1]+py)/16,(vertices[at+2]+pz)/16,r,g,b,1,vertices[at+3],vertices[at+4],overlay,light,-vertices[at+5],vertices[at+6],vertices[at+7]);}
            VertexBuffer buffer=cached==null?new VertexBuffer(revision==0?VertexBuffer.Usage.STATIC:VertexBuffer.Usage.DYNAMIC):cached.buffer();
            if(!upload(buffer,builder)){if(cached==null)buffer.close();type.clearRenderState();return false;}
            if(revision>0)
            {
                if(cached==null)posedColdUploads++;
                else
                {
                    boolean geometry=cached.revision()!=revision;
                    if(geometry)posedRevisionUploads++;else posedShadingOnlyUploads++;
                    if(!cached.material().equals(material))posedMaterialUploads++;
                    if(cached.light()!=light)posedLightUploads++;
                    if(cached.overlay()!=overlay)posedOverlayUploads++;
                    if(cached.red()!=r||cached.green()!=g||cached.blue()!=b)posedTintUploads++;
                    if(cached.shadow()!=shadow)posedPassChangedUploads++;
                    if(posedDiagnostics<8)
                    {
                        posedDiagnostics++;
                        ProjectSeele.LOGGER.info("R52 weighted VBO upload: texture={} revision={}->{} material={}->{} light={}->{} overlay={}->{} shadow={}->{} geometryChanged={}",
                                texture,cached.revision(),revision,cached.material(),material,cached.light(),light,cached.overlay(),overlay,cached.shadow(),shadow,geometry);
                    }
                }
            }
            cached=new ExternalMesh(buffer,revision,light,overlay,r,g,b,material,shadow);
            if(states.variants.put(state,cached))externalStateEvictions++;
            if(revision>0)posedUploads++;
        }
        var combined=new Matrix4f(RenderSystem.getModelViewMatrix()).mul(poses.last().pose());cached.buffer().bind();cached.buffer().drawWithShader(combined,RenderSystem.getProjectionMatrix(),active);EvaMaterialAuditR37.capture(texture,active);VertexBuffer.unbind();type.clearRenderState();drawCalls++;posedDraw(revision);
        if(!externalReadyLogged){externalReadyLogged=true;ProjectSeele.LOGGER.info("R30 rigid GPU buffers active inside the Oculus entity pipeline");}
        return true;
    }
    public static void clear()
    {
        Runnable release=()->{PARTS.values().forEach(p->p.buffer().close());PARTS.clear();EXTERNAL_PARTS.values().forEach(v->v.variants.clear());EXTERNAL_PARTS.clear();if(uploadBuilder!=null)uploadBuilder.clear();};
        if(RenderSystem.isOnRenderThread())release.run();else RenderSystem.recordRenderCall(release::run);
    }
    static BufferBuilder beginUpload()
    {
        RenderSystem.assertOnRenderThread();
        if(uploadBuilder==null){uploadBuilder=new BufferBuilder(256);uploadBuilderCreations++;}
        uploadBuilder.begin(VertexFormat.Mode.TRIANGLES,DefaultVertexFormat.NEW_ENTITY);
        return uploadBuilder;
    }
    private static boolean upload(VertexBuffer buffer,BufferBuilder builder)
    {
        var rendered=builder.end();
        // VertexBuffer.upload returns before releasing a batch on an invalid
        // handle. Release that fallback explicitly so the uploader can begin again.
        if(buffer.isInvalid()){rendered.release();return false;}
        buffer.bind();
        try{buffer.upload(rendered);return true;}
        finally{VertexBuffer.unbind();}
    }
    private static void posedDraw(long revision)
    {
        if(revision<=0)return;
        posedDrawCalls++;
        if(!posedReadyLogged)
        {
            posedReadyLogged=true;
            ProjectSeele.LOGGER.info("R52 posed local-mesh GPU buffers active; exact geometry revision, original shader vertex attributes, source-part cache keys");
        }
    }
    private static MaterialIds materialIds()
    {
        if(!materialApiResolved)
        {
            materialApiResolved=true;
            try
            {
                var type=Class.forName("net.irisshaders.iris.uniforms.CapturedRenderingState");
                materialState=type.getField("INSTANCE").get(null);
                materialEntity=type.getMethod("getCurrentRenderedEntity");
                materialBlockEntity=type.getMethod("getCurrentRenderedBlockEntity");
                materialItem=type.getMethod("getCurrentRenderedItem");
            }
            catch(ReflectiveOperationException unavailable){return null;}
        }
        if(materialState==null||materialEntity==null||materialBlockEntity==null||materialItem==null)return null;
        try{return new MaterialIds((Integer)materialEntity.invoke(materialState),(Integer)materialBlockEntity.invoke(materialState),(Integer)materialItem.invoke(materialState));}
        catch(ReflectiveOperationException unavailable){return null;}
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
