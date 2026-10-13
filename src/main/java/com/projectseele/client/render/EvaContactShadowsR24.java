package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.util.*;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.entity.FirstBattleSignals;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL13;
import org.lwjgl.opengl.GL14;
import org.lwjgl.opengl.GL20;
import org.lwjgl.opengl.GL30;
import org.lwjgl.system.MemoryStack;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraftforge.eventbus.api.EventPriority;

/** Contact shade under the actual submitted toes/kneepads in the directed ground grapple. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EvaContactShadowsR24
{
    private record Contact(Vec3 point,float radius,float alpha,long frame,float sole,double floor){}
    private static final Map<EvaUnit01Entity,Map<String,Contact>> CONTACTS=new WeakHashMap<>();
    private static final ResourceLocation TEXTURE=new ResourceLocation("minecraft","textures/misc/shadow.png");
    // Oculus defers the global entity buffer and its endBatch(type) is a no-op.
    // Draw after Iris's deferred pass, which begins at the translucent phase.
    private static final MultiBufferSource.BufferSource DECALS=MultiBufferSource.immediate(new BufferBuilder(4096));
    private static JsonObject drawReceiptR52;
    private static int lastTraceBucketR52=-1,traceRowsR52;
    private static boolean traceStartedR52,traceFailedR52;
    public static boolean tracingDrawR52(){return drawReceiptR52!=null;}
    public static void capture(EvaUnit01Entity eva,String part,float[] vertices,int stride,float px,float py,float pz,Matrix4f matrix)
    {
        if(!eva.isFirstBattleActive()||ShaderShadowPassR44.active()||!(part.startsWith("foot_")||part.startsWith("shin_")))return;
        long frame=FirstBattleSignals.clientFrameTime();var slots=CONTACTS.computeIfAbsent(eva,key->new HashMap<>());var old=slots.get(part);
        if(old!=null&&old.frame==frame)return;
        float minimum=Float.POSITIVE_INFINITY;Vector3f point=new Vector3f();
        for(int i=0;i<vertices.length;i+=stride)
        {matrix.transformPosition(point.set(-(vertices[i]+px)/16,(vertices[i+1]+py)/16,(vertices[i+2]+pz)/16));minimum=Math.min(minimum,point.y);}
        double x=0,z=0;int count=0;
        for(int i=0;i<vertices.length;i+=stride)
        {
            matrix.transformPosition(point.set(-(vertices[i]+px)/16,(vertices[i+1]+py)/16,(vertices[i+2]+pz)/16));
            if(point.y<=minimum+.30){x+=point.x;z+=point.z;count++;}
        }
        if(count==0)return;x/=count;z/=count;float radius=part.startsWith("foot_")?4.1F:2.5F;
        Vec3 centre=new Vec3(x,minimum,z);double floor=ground(eva,centre);
        float alpha=Double.isFinite(floor)?(float)(.34*Math.max(0,1-Math.max(0,minimum-floor)/1.8)):0;
        if(alpha>0)
            for(double[] edge:new double[][]{{-radius,-radius},{radius,-radius},{-radius,radius},{radius,radius}})
            {
                double height=ground(eva,centre.add(edge[0],0,edge[1]));
                if(!Double.isFinite(height)||Math.abs(height-floor)>.15){alpha=0;break;}
            }
        slots.put(part,new Contact(new Vec3(x,Double.isFinite(floor)?floor+.018:minimum,z),radius,alpha,frame,minimum,floor));
    }
    private static double ground(EvaUnit01Entity eva,Vec3 near)
    {
        var hit=eva.level().clip(new ClipContext(near.add(0,.35,0),near.add(0,-2,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
        return hit.getType()==HitResult.Type.BLOCK?hit.getLocation().y:Double.NaN;
    }
    @SubscribeEvent(priority=EventPriority.LOWEST) public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS||ShaderShadowPassR44.active()||CONTACTS.isEmpty())return;var mc=Minecraft.getInstance();if(mc.level==null)return;
        var pose=event.getPoseStack();var camera=event.getCamera().getPosition();long frame=FirstBattleSignals.clientFrameTime();var type=ContactLayer.TYPE;var target=DECALS.getBuffer(type);
        Matrix4f eventPoseBefore=FirstBattleRuntimeWitnessR52.ENABLED?new Matrix4f(pose.last().pose()):null;
        JsonObject receipt=null;int bucket=-1,quads=0;JsonObject captured=null;
        pose.pushPose();pose.translate(-camera.x,-camera.y,-camera.z);
        for(var entry:List.copyOf(CONTACTS.entrySet()))
        {
            var actor=entry.getKey();if(actor==null||actor.level()!=mc.level||!actor.isFirstBattleActive())continue;
            bucket=actor.firstBattleSignals().age(actor)/10;
            if(FirstBattleRuntimeWitnessR52.ENABLED&&!traceFailedR52&&traceRowsR52<48&&bucket>lastTraceBucketR52)
            {receipt=new JsonObject();captured=new JsonObject();receipt.addProperty("clip_sha256",com.projectseele.entity.FirstBattleClip.fingerprint());receipt.addProperty("age",actor.firstBattleSignals().age(actor));receipt.addProperty("seconds",actor.firstBattleSignals().time(actor,1));receipt.addProperty("frame_nanos",frame);receipt.addProperty("stage","AFTER_TRANSLUCENT_BLOCKS");receipt.addProperty("render_type","seele_ground_contact_r52");receipt.addProperty("buffer_class",DECALS.getClass().getName());receipt.addProperty("shader_pack_active",ShaderShadowPassR44.enabled());receipt.addProperty("effective_render_distance_blocks",mc.options.getEffectiveRenderDistance()*16);receipt.add("event_pose_before_camera_translation",matrixJsonR52(eventPoseBefore));receipt.add("event_pose_after_camera_translation",matrixJsonR52(pose.last().pose()));JsonArray cam=new JsonArray();cam.add(camera.x);cam.add(camera.y);cam.add(camera.z);receipt.add("camera_world",cam);}
            for(var sample:entry.getValue().entrySet())
            {
                var contact=sample.getValue();
                if(receipt!=null){JsonObject c=new JsonObject();c.addProperty("same_main_frame",contact.frame==frame);c.addProperty("submitted_sole_y",contact.sole);c.addProperty("ground_probe_block_hit",Double.isFinite(contact.floor));if(Double.isFinite(contact.floor))c.addProperty("ground_y",contact.floor);c.addProperty("alpha",contact.alpha);c.addProperty("radius",contact.radius);JsonArray centre=new JsonArray();centre.add(contact.point.x);centre.add(contact.point.y);centre.add(contact.point.z);c.add("quad_centre_world",centre);Vector3f submitted=pose.last().pose().transformPosition(new Vector3f((float)contact.point.x,(float)contact.point.y,(float)contact.point.z));JsonArray submittedPoint=new JsonArray();submittedPoint.add(submitted.x);submittedPoint.add(submitted.y);submittedPoint.add(submitted.z);c.add("quad_centre_submitted",submittedPoint);captured.add(sample.getKey(),c);}
                if(contact.alpha<=0||contact.frame!=frame)continue;
                float x=(float)contact.point.x,y=(float)contact.point.y,z=(float)contact.point.z,r=contact.radius;
                vertex(target,pose,x-r,y,z-r,0,0,contact.alpha);vertex(target,pose,x-r,y,z+r,0,1,contact.alpha);
                vertex(target,pose,x+r,y,z+r,1,1,contact.alpha);vertex(target,pose,x+r,y,z-r,1,0,contact.alpha);
                quads++;
            }
        }
        pose.popPose();
        if(receipt!=null){receipt.add("captures",captured);receipt.addProperty("submitted_quads",quads);receipt.add("actual_draws",new JsonArray());drawReceiptR52=receipt;}
        try{DECALS.endBatch(type);}finally{drawReceiptR52=null;}
        if(receipt!=null)writeReceiptR52(receipt,bucket);
    }
    /** Called immediately after ShaderInstance.apply and before the real VertexBuffer draw. */
    public static void actualDrawR52(net.minecraft.client.renderer.ShaderInstance shader,Matrix4f modelView,Matrix4f projection)
    {
        if(drawReceiptR52==null)return;JsonObject draw=new JsonObject();draw.addProperty("shader_class",shader.getClass().getName());draw.addProperty("shader_name",shader.getName());int program=GL11.glGetInteger(GL20.GL_CURRENT_PROGRAM);draw.addProperty("program",program);draw.addProperty("draw_framebuffer",GL11.glGetInteger(GL30.GL_DRAW_FRAMEBUFFER_BINDING));
        int far=GL20.glGetUniformLocation(program,"far");if(far>=0)draw.addProperty("shader_far_uniform",GL20.glGetUniformf(program,far));
        int water=GL20.glGetUniformLocation(program,"isEyeInWater");if(water>=0)draw.addProperty("shader_is_eye_in_water",GL20.glGetUniformi(program,water));
        draw.addProperty("actual_camera_fluid",Minecraft.getInstance().gameRenderer.getMainCamera().getFluidInCamera().name());
        int tex=GL20.glGetUniformLocation(program,"tex");if(tex>=0){int unit=GL20.glGetUniformi(program,tex);draw.addProperty("tex_sampler_unit",unit);int previous=GL11.glGetInteger(GL13.GL_ACTIVE_TEXTURE);try{GL13.glActiveTexture(GL13.GL_TEXTURE0+unit);draw.addProperty("tex_binding_2d",GL11.glGetInteger(GL11.GL_TEXTURE_BINDING_2D));draw.addProperty("tex_width",GL11.glGetTexLevelParameteri(GL11.GL_TEXTURE_2D,0,GL11.GL_TEXTURE_WIDTH));draw.addProperty("tex_height",GL11.glGetTexLevelParameteri(GL11.GL_TEXTURE_2D,0,GL11.GL_TEXTURE_HEIGHT));}finally{GL13.glActiveTexture(previous);}}
        JsonArray targets=new JsonArray();for(int i=0;i<8;i++)targets.add(GL11.glGetInteger(GL20.GL_DRAW_BUFFER0+i));draw.add("draw_buffers",targets);
        draw.addProperty("blend",GL11.glIsEnabled(GL11.GL_BLEND));draw.addProperty("blend_src_rgb",GL11.glGetInteger(GL14.GL_BLEND_SRC_RGB));draw.addProperty("blend_dst_rgb",GL11.glGetInteger(GL14.GL_BLEND_DST_RGB));draw.addProperty("depth_test",GL11.glIsEnabled(GL11.GL_DEPTH_TEST));draw.addProperty("depth_function",GL11.glGetInteger(GL11.GL_DEPTH_FUNC));draw.addProperty("depth_write",GL11.glGetBoolean(GL11.GL_DEPTH_WRITEMASK));draw.addProperty("cull",GL11.glIsEnabled(GL11.GL_CULL_FACE));
        try(var stack=MemoryStack.stackPush()){var bytes=stack.malloc(4);GL11.glGetBooleanv(GL11.GL_COLOR_WRITEMASK,bytes);JsonArray mask=new JsonArray();for(int i=0;i<4;i++)mask.add(bytes.get(i)!=0);draw.add("color_write",mask);}
        JsonArray mv=new JsonArray(),pr=new JsonArray();for(float v:modelView.get(new float[16]))mv.add(v);for(float v:projection.get(new float[16]))pr.add(v);draw.add("model_view",mv);draw.add("projection",pr);drawReceiptR52.getAsJsonArray("actual_draws").add(draw);
    }
    private static void writeReceiptR52(JsonObject value,int bucket)
    {
        try{String declared=System.getProperty("projectseele.firstBattleRuntimeWitnessR52Output","");Path primary=declared.isBlank()?Minecraft.getInstance().gameDirectory.toPath().resolve("logs/first_battle_runtime_r52.jsonl"):Path.of(declared);Path path=primary.resolveSibling("contact_shade.jsonl");Files.createDirectories(path.toAbsolutePath().getParent());if(!traceStartedR52){Files.writeString(path,"",StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);traceStartedR52=true;}Files.writeString(path,value+System.lineSeparator(),StandardOpenOption.APPEND);lastTraceBucketR52=bucket;traceRowsR52++;}
        catch(Exception failure){traceFailedR52=true;ProjectSeele.LOGGER.error("First-battle contact shade receipt failed",failure);}
    }
    private static void vertex(com.mojang.blaze3d.vertex.VertexConsumer target,com.mojang.blaze3d.vertex.PoseStack pose,float x,float y,float z,float u,float v,float alpha)
    {target.vertex(pose.last().pose(),x,y,z).color(0F,0F,0F,alpha).uv(u,v).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(LightTexture.FULL_BRIGHT).normal(pose.last().normal(),0,1,0).endVertex();}
    private static JsonArray matrixJsonR52(Matrix4f matrix)
    {JsonArray values=new JsonArray();for(float value:matrix.get(new float[16]))values.add(value);return values;}
    private abstract static class ContactLayer extends RenderType
    {
        // Keep Iris's entity shader override, but do not replace the ground's
        // depth with the transparent rectangle surrounding a radial shadow.
        private static final RenderType TYPE=create("seele_ground_contact_r52",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.QUADS,4096,false,false,CompositeState.builder()
                        .setShaderState(RENDERTYPE_ENTITY_TRANSLUCENT_SHADER)
                        .setTextureState(new TextureStateShard(TEXTURE,true,false))
                        .setTransparencyState(TRANSLUCENT_TRANSPARENCY).setCullState(NO_CULL)
                        .setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE)
                        .setLayeringState(VIEW_OFFSET_Z_LAYERING).createCompositeState(false));
        private ContactLayer(){super("seele_ground_contact_definition",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.QUADS,256,false,false,()->{},()->{});}
    }
    private EvaContactShadowsR24(){}
}
