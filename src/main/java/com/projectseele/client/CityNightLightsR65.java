package com.projectseele.client;

import com.projectseele.ProjectSeele;
import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.zip.GZIPInputStream;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.lwjgl.opengl.GL;
import org.lwjgl.system.MemoryStack;

import static org.lwjgl.opengl.GL33C.*;

/** Exterior city lights in world space. The immutable point buffer is shared by all city and mission states. */
@Mod.EventBusSubscriber(modid="projectseele", value=Dist.CLIENT)
public final class CityNightLightsR65
{
    private static final int OWNERS=100, STRIDE=9, DEPTH_UNIT=8, TERRAIN_UNIT=9;
    private static ClientLevel world;
    private static long updated;
    private static boolean city, failed, reported;
    private static final float[] from=new float[OWNERS], target=new float[OWNERS], shown=new float[OWNERS];
    private static int program, array, buffer, sampler, count, terrainTexture, heightBuffer;
    private static int colourTarget, colourTexture, colourWidth, colourHeight, composite;
    private static boolean captured;
    private static int pose, projection, eye, viewport, levels, owners, nativeRange, lod, transform, available;
    private static final boolean REVIEW=Boolean.getBoolean("projectseele.cityLightsReviewR65");

    public static void receive(ResourceLocation dimension, byte[] offsets)
    {
        ClientLevel level=Minecraft.getInstance().level;
        if (level==null || !level.dimension().location().equals(dimension)) return;
        if (offsets.length!=0 && offsets.length!=1 && offsets.length!=OWNERS) return;
        boolean newWorld=level!=world || !city;
        city=offsets.length!=0;
        world=level;
        if (!city) return;
        interpolate(level.getGameTime());
        for (int i=0;i<OWNERS;i++)
        {
            int value=Byte.toUnsignedInt(offsets.length==1?offsets[0]:offsets[i]);
            float next=value==255?-2F:value/254F;
            from[i]=newWorld || next<0 || shown[i]<0?next:shown[i];
            target[i]=next;
        }
        updated=level.getGameTime();
    }

    @SubscribeEvent
    public static void tick(net.minecraftforge.event.TickEvent.ClientTickEvent e)
    {
        if (e.phase==net.minecraftforge.event.TickEvent.Phase.END && world!=Minecraft.getInstance().level)
        {
            world=null;
            city=false;
            reported=false;
        }
    }

    private static void interpolate(double tick)
    {
        float t=(float)Math.max(0,Math.min(1,(tick-updated)/20.0));
        for (int i=0;i<OWNERS;i++) shown[i]=from[i]+t*(target[i]-from[i]);
    }

    @SubscribeEvent
    public static void render(RenderLevelStageEvent e)
    {
        if (e.getStage()!=RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS || failed
                || com.projectseele.client.render.ShaderShadowPassR44.active()) return;
        Minecraft mc=Minecraft.getInstance();
        var level=mc.level;
        if (level==null || level!=world || !city || !GL.getCapabilities().OpenGL33) return;
        if (!TvYashimaNightClientR54.night(level) && !CityLightWavesR65.restoring(level)) return;
        if (!com.projectseele.config.SeeleConfig.YASHIMA_BLACKOUT.get() && !TvYashimaNightClientR54.night(level)) return;
        var camera=e.getCamera().getPosition();
        if (camera.y<58 || Math.abs(camera.x-30)>4300 || Math.abs(camera.z-240)>4300) return;
        float[] brightness=CityLightWavesR65.lightLevels();
        boolean any=false;
        for (float value:brightness) if (value>.001F) {any=true;break;}
        if (!any) return;
        if (REVIEW && Boolean.getBoolean("projectseele.cityLightsBaselineR65")) return;
        interpolate(level.getGameTime()+e.getPartialTick());
        try (var state=new RenderState(); var stack=MemoryStack.stackPush())
        {
            if (program==0) initialize();
            int[] box=new int[4]; glGetIntegerv(GL_VIEWPORT,box);
            if (box[2]<=0 || box[3]<=0) return;
            var terrain=RamielTerrainDepthR64.sample(e.getProjectionMatrix());
            if (terrain!=null && glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING)!=0
                    && glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE)==GL_TEXTURE
                    && glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME)==terrain.texture()) terrain=null;
            if (!captureTarget(box)) return;
            glUseProgram(program); glBindVertexArray(array);
            glUniformMatrix4fv(pose,false,e.getPoseStack().last().pose().get(stack.mallocFloat(16)));
            glUniformMatrix4fv(projection,false,e.getProjectionMatrix().get(stack.mallocFloat(16)));
            glUniform3f(eye,(float)camera.x,(float)camera.y,(float)camera.z);
            glUniform4f(viewport,box[0],box[1],box[2],box[3]);
            glUniform1fv(owners,shown); glUniform1fv(levels,brightness);
            glUniform1f(nativeRange,mc.options.getEffectiveRenderDistance()*16F);
            glUniform1i(available,terrain==null?0:1);
            glActiveTexture(GL_TEXTURE0+TERRAIN_UNIT);
            glBindTexture(GL_TEXTURE_BUFFER,terrainTexture);
            glActiveTexture(GL_TEXTURE0+DEPTH_UNIT);
            glBindSampler(DEPTH_UNIT,sampler);
            glBindTexture(GL_TEXTURE_2D,terrain==null?0:terrain.texture());
            if (terrain!=null) glUniform2f(transform,terrain.scale(),terrain.offset());
            glEnable(GL_PROGRAM_POINT_SIZE); glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LEQUAL); glDepthMask(false);
            glEnablei(GL_BLEND,0);
            blend(GL_FUNC_ADD,GL_FUNC_ADD,GL_SRC_ALPHA,GL_ONE,GL_ZERO,GL_ONE);
            boolean sample = REVIEW && CityLightReviewR65.beginSample(level.getGameTime());
            try { glDrawArrays(GL_POINTS,0,count); captured=true; }
            finally { if (sample) CityLightReviewR65.endSample(); }
            if (!reported || (REVIEW && level.getGameTime()%100==0 && lastReport!=level.getGameTime()))
            {
                reported=true; lastReport=level.getGameTime();
                ProjectSeele.LOGGER.info("City lights R65: {} surveyed points, DH depth {}, camera {}, district brightness {}, first tower {}",
                        count,terrain!=null,e.getCamera().getBlockPosition(),Arrays.toString(brightness),shown[0]);
            }
        }
        catch (IOException | RuntimeException | LinkageError problem)
        {
            failed=true;
            ProjectSeele.LOGGER.warn("Cannot draw GeoFront city lights",problem);
        }
    }

    @SubscribeEvent
    public static void frame(net.minecraftforge.event.TickEvent.RenderTickEvent event)
    {
        if (event.phase==net.minecraftforge.event.TickEvent.Phase.START) captured=false;
    }

    /** Borrow the opaque scene depth, keeping the passed light colour separate from the shader pack's fog pass. */
    private static boolean captureTarget(int[] box)
    {
        if (box[0]!=0 || box[1]!=0 || glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING)==0) return false;
        int type=glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE);
        if (type!=GL_TEXTURE && type!=GL_RENDERBUFFER) return false;
        int attachment=glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME);
        if (colourTarget==0) colourTarget=glGenFramebuffers();
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER,colourTarget);
        if (colourWidth!=box[2] || colourHeight!=box[3])
        {
            if(colourTexture!=0) glDeleteTextures(colourTexture);
            colourTexture=glGenTextures();
            glActiveTexture(GL_TEXTURE0+DEPTH_UNIT);
            glBindTexture(GL_TEXTURE_2D,colourTexture);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,box[2],box[3],0,GL_RGBA,GL_UNSIGNED_BYTE,0L);
            glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,colourTexture,0);
            glDrawBuffer(GL_COLOR_ATTACHMENT0);
            colourWidth=box[2];colourHeight=box[3];
        }
        if (type==GL_TEXTURE) glFramebufferTexture(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,attachment,0);
        else glFramebufferRenderbuffer(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_RENDERBUFFER,attachment);
        if (glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE) return false;
        glDisable(GL_SCISSOR_TEST);
        glDisable(GL_STENCIL_TEST);
        glColorMaski(0,true,true,true,true);
        glClearBufferfv(GL_COLOR,0,new float[]{0,0,0,0});
        return true;
    }

    /** World post-processing is finished here. The GUI overlays will be drawn after the additive light pass. */
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.HIGHEST)
    public static void compose(net.minecraftforge.client.event.RenderGuiEvent.Pre event)
    {
        if (!captured || failed) return;
        captured=false;
        try (var state=new RenderState())
        {
            if (composite==0)
            {
                composite=link("city_composite.vsh","city_composite.fsh");
                glUseProgram(composite);
                glUniform1i(glGetUniformLocation(composite,"lights"),DEPTH_UNIT);
            }
            glUseProgram(composite);
            glBindVertexArray(array);
            glActiveTexture(GL_TEXTURE0+DEPTH_UNIT);
            glBindTexture(GL_TEXTURE_2D,colourTexture);
            glBindSampler(DEPTH_UNIT,sampler);
            glDisable(GL_SCISSOR_TEST);glDisable(GL_STENCIL_TEST);glDisable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);
            glDepthMask(false);glColorMaski(0,true,true,true,true);
            glEnablei(GL_BLEND,0);
            blend(GL_FUNC_ADD,GL_FUNC_ADD,GL_ONE,GL_ONE,GL_ZERO,GL_ONE);
            var proof=REVIEW?CityLightReviewR65.beforeComposite(shown[0]):null;
            try { glDrawArrays(GL_TRIANGLES,0,3); }
            finally { if(proof!=null) proof.finish(); }
        } catch(IOException | RuntimeException | LinkageError problem) {
            failed=true;
            ProjectSeele.LOGGER.warn("Cannot composite GeoFront city lights",problem);
        }
    }

    private static long lastReport=Long.MIN_VALUE;

    private static void initialize() throws IOException
    {
        float[] points;
        var raw=CityNightLightsR65.class.getResourceAsStream("/assets/projectseele/city/night_lights_r65.bin.gz");
        if (raw==null) throw new IOException("Missing city light survey");
        try (var data=new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw))))
        {
            if (data.readInt()!=0x4c523635 || data.readUnsignedShort()!=OWNERS) throw new IOException("City light survey format");
            count=data.readInt();
            if (count<1 || count>60000) throw new IOException("City light count");
            int[] base=new int[OWNERS], drop=new int[OWNERS];
            for (int i=0;i<OWNERS;i++) {base[i]=data.readShort();drop[i]=data.readShort();}
            points=new float[count*STRIDE];
            for (int i=0;i<count;i++)
            {
                int x=data.readShort(),y=data.readShort(),z=data.readShort();
                int kind=data.readUnsignedByte(), face=data.readUnsignedByte(), owner=data.readUnsignedByte();
                if (kind<1 || kind>3 || face>4 || (owner>=OWNERS && owner!=255)) throw new IOException("Invalid light anchor");
                int j=i*STRIDE;
                points[j]=x+.5F; points[j+1]=y+.5F; points[j+2]=z+.5F;
                points[j+3]=kind; points[j+4]=face; points[j+5]=owner==255?-1:owner;
                points[j+6]=owner==255?0:base[owner]; points[j+7]=owner==255?0:drop[owner];
                points[j+8]=CityLightWavesR65.district(x,z);
            }
            if (data.read()!=-1) throw new IOException("Trailing city light data");
        }
        program=link("city_lights.vsh","city_lights.fsh");
        glUseProgram(program);
        pose=uniform("pose");projection=uniform("projection");eye=uniform("eye");viewport=uniform("viewport");
        levels=uniform("brightness");owners=uniform("retraction");nativeRange=uniform("nativeRange");
        lod=uniform("lod");transform=uniform("lodTransform");available=uniform("haveLod");glUniform1i(lod,DEPTH_UNIT);
        initializeTerrain();
        array=glGenVertexArrays();buffer=glGenBuffers();glBindVertexArray(array);glBindBuffer(GL_ARRAY_BUFFER,buffer);
        glBufferData(GL_ARRAY_BUFFER,points,GL_STATIC_DRAW);
        for (int i=0;i<3;i++){glEnableVertexAttribArray(i);glVertexAttribPointer(i,3,GL_FLOAT,false,STRIDE*4,i*12L);}
        sampler=glGenSamplers();
        glSamplerParameteri(sampler,GL_TEXTURE_MIN_FILTER,GL_NEAREST); glSamplerParameteri(sampler,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    }

    private static void initializeTerrain() throws IOException
    {
        var input=CityNightLightsR65.class.getResourceAsStream("/assets/projectseele/city/night_terrain_r65.bin.gz");
        if (input==null) throw new IOException("Missing GeoFront surface survey");
        try (var data=new DataInputStream(new BufferedInputStream(new GZIPInputStream(input))))
        {
            if (data.readInt()!=0x48523635) throw new IOException("GeoFront surface survey format");
            int x=data.readShort(),z=data.readShort(),w=data.readUnsignedShort(),h=data.readUnsignedShort();
            if (w==0 || h==0 || w*h>100000 || data.readUnsignedShort()!=8) throw new IOException("GeoFront surface survey size");
            float[] heights=new float[w*h];
            for (int i=0;i<heights.length;i++) heights[i]=data.readShort();
            if(data.read()!=-1) throw new IOException("Trailing GeoFront surface survey");
            glUniform1i(uniform("terrainHeights"),TERRAIN_UNIT);
            glUniform4i(uniform("terrainBounds"),x,z,w,h);
            int old=glGetInteger(GL_TEXTURE_BUFFER);
            glActiveTexture(GL_TEXTURE0+TERRAIN_UNIT);
            terrainTexture=glGenTextures();
            heightBuffer=glGenBuffers();
            try {
                glBindBuffer(GL_TEXTURE_BUFFER,heightBuffer);
                glBufferData(GL_TEXTURE_BUFFER,heights,GL_STATIC_DRAW);
                glBindTexture(GL_TEXTURE_BUFFER,terrainTexture);
                glTexBuffer(GL_TEXTURE_BUFFER,GL_R32F,heightBuffer);
            } finally {
                glBindBuffer(GL_TEXTURE_BUFFER,old);
            }
        }
    }

    private static int link(String vertexFile,String fragmentFile) throws IOException
    {
        int vertex=shader(GL_VERTEX_SHADER,vertexFile), fragment=shader(GL_FRAGMENT_SHADER,fragmentFile);
        int linked=glCreateProgram();
        glAttachShader(linked,vertex);glAttachShader(linked,fragment);glLinkProgram(linked);
        glDeleteShader(vertex);glDeleteShader(fragment);
        if(glGetProgrami(linked,GL_LINK_STATUS)==0) throw new IOException(glGetProgramInfoLog(linked));
        return linked;
    }

    private static int shader(int kind,String name) throws IOException
    {
        String path="/assets/projectseele/shaders/core/"+name;
        try (var stream=CityNightLightsR65.class.getResourceAsStream(path))
        {
            if(stream==null) throw new IOException(path);
            int id=glCreateShader(kind);glShaderSource(id,new String(stream.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8));
            glCompileShader(id);
            if(glGetShaderi(id,GL_COMPILE_STATUS)==0){String message=glGetShaderInfoLog(id);glDeleteShader(id);throw new IOException(message);}
            return id;
        }
    }
    private static int uniform(String name) {return glGetUniformLocation(program,name);}

    private static void blend(int rgbEq,int alphaEq,int rgbSrc,int rgbDst,int alphaSrc,int alphaDst)
    {
        var caps=GL.getCapabilities();
        if(caps.OpenGL40) {
            org.lwjgl.opengl.GL40C.glBlendEquationSeparatei(0,rgbEq,alphaEq);
            org.lwjgl.opengl.GL40C.glBlendFuncSeparatei(0,rgbSrc,rgbDst,alphaSrc,alphaDst);
        } else if(caps.GL_ARB_draw_buffers_blend) {
            org.lwjgl.opengl.ARBDrawBuffersBlend.glBlendEquationSeparateiARB(0,rgbEq,alphaEq);
            org.lwjgl.opengl.ARBDrawBuffersBlend.glBlendFuncSeparateiARB(0,rgbSrc,rgbDst,alphaSrc,alphaDst);
        } else {
            glBlendEquationSeparate(rgbEq,alphaEq);
            glBlendFuncSeparate(rgbSrc,rgbDst,alphaSrc,alphaDst);
        }
    }

    private static final class RenderState implements AutoCloseable
    {
        final int shader=glGetInteger(GL_CURRENT_PROGRAM),vao=glGetInteger(GL_VERTEX_ARRAY_BINDING),vbo=glGetInteger(GL_ARRAY_BUFFER_BINDING);
        final int draw=glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING);
        final int active=glGetInteger(GL_ACTIVE_TEXTURE),func=glGetInteger(GL_DEPTH_FUNC),tex,samp,terrain;
        final int src=glGetInteger(GL_BLEND_SRC_RGB),dst=glGetInteger(GL_BLEND_DST_RGB),sa=glGetInteger(GL_BLEND_SRC_ALPHA),da=glGetInteger(GL_BLEND_DST_ALPHA);
        final int eq=glGetInteger(GL_BLEND_EQUATION_RGB),ea=glGetInteger(GL_BLEND_EQUATION_ALPHA);
        final boolean mask=glGetBoolean(GL_DEPTH_WRITEMASK),depth=glIsEnabled(GL_DEPTH_TEST),blend=glIsEnabledi(GL_BLEND,0),size=glIsEnabled(GL_PROGRAM_POINT_SIZE);
        final boolean scissor=glIsEnabled(GL_SCISSOR_TEST),stencil=glIsEnabled(GL_STENCIL_TEST),cull=glIsEnabled(GL_CULL_FACE);
        final byte[] rgba=new byte[4];
        RenderState(){
            try(var stack=MemoryStack.stackPush()){
                var mask=stack.malloc(4);
                glGetBooleanv(GL_COLOR_WRITEMASK,mask);
                mask.get(rgba);
            }
glActiveTexture(GL_TEXTURE0+TERRAIN_UNIT);terrain=glGetInteger(GL_TEXTURE_BINDING_BUFFER);glActiveTexture(GL_TEXTURE0+DEPTH_UNIT);tex=glGetInteger(GL_TEXTURE_BINDING_2D);samp=glGetIntegeri(GL_SAMPLER_BINDING,DEPTH_UNIT);}
        public void close()
        {
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER,draw);
            glColorMaski(0,rgba[0]!=0,rgba[1]!=0,rgba[2]!=0,rgba[3]!=0);
            set(GL_SCISSOR_TEST,scissor);set(GL_STENCIL_TEST,stencil);set(GL_CULL_FACE,cull);
            glActiveTexture(GL_TEXTURE0+TERRAIN_UNIT);glBindTexture(GL_TEXTURE_BUFFER,terrain);
            glActiveTexture(GL_TEXTURE0+DEPTH_UNIT);glBindTexture(GL_TEXTURE_2D,tex);glBindSampler(DEPTH_UNIT,samp);glActiveTexture(active);
            glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,vbo);glUseProgram(shader);
            glDepthMask(mask);glDepthFunc(func);blend(eq,ea,src,dst,sa,da);
            set(GL_DEPTH_TEST,depth);if(blend)glEnablei(GL_BLEND,0);else glDisablei(GL_BLEND,0);set(GL_PROGRAM_POINT_SIZE,size);
        }
        private static void set(int flag,boolean value){if(value)glEnable(flag);else glDisable(flag);}
    }
    private CityNightLightsR65() {}
}
