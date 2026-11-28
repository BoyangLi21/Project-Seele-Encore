package com.projectseele.client;

import com.projectseele.ProjectSeele;
import java.io.*;
import java.nio.FloatBuffer;
import java.util.zip.GZIPInputStream;
import it.unimi.dsi.fastutil.longs.LongArrayList;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.lwjgl.BufferUtils;
import org.lwjgl.system.MemoryStack;
import static org.lwjgl.opengl.GL33C.*;

/** Reads the same 100 registered cargo frames as the mechanical lift. The DH database stays intact. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class CitySkylineR66 {
    private static final int COUNT=100, STRIDE=16;
    private static final int MIN_X=-312, MIN_Z=0, WIDTH=608, HEIGHT=560;
    private static final short[] columnRoof=new short[WIDTH*HEIGHT];
    private static final int[][] specs=new int[COUNT][8];
    private static byte[] survey;
    private static volatile ClientLevel bound;
    private static volatile boolean unavailable;
    private static int program, vao, vbo, instances, sampler, colourFbo, colourTexture, screenW, screenH, composite, query;
    private static boolean captured, queryPending;
    private static long lastQuery = -1;
    private static final int[] firstQuad=new int[COUNT], quadCount=new int[COUNT];
    private static volatile long filtered;
    private static float lastReview=-5;
    private static final boolean REVIEW=Boolean.getBoolean("projectseele.citySkylineReviewR66");

    /** Called on the game thread, only for a server-authorised saved city. */
    static void bind(ClientLevel level, boolean enabled) {
        if ((!enabled && bound==null) || enabled && bound==level || unavailable) return;
        try {
            if(enabled && survey==null) {
                if(CitySkylineR66.class.getResource("/assets/projectseele/city/city_shells_r66.bin.gz")==null) {
                    unavailable=true;
                    return;
                }
                loadSurvey();
            }
            lastDh=null; lastWorld=null;
            bound=enabled?level:null;
            // Old rendered sections may predate the authoritative login snapshot.
            if (level!=null) YashimaBlackoutR64.rebuildFarView();
        } catch(IOException failure) {
            unavailable=true; bound=null; ProjectSeele.LOGGER.warn("Cannot load surveyed Tokyo-3 skyline",failure);
        }
    }
    private static void loadSurvey() throws IOException {
        try (var raw=CitySkylineR66.class.getResourceAsStream("/assets/projectseele/city/city_shells_r66.bin.gz")) {
            if(raw==null)throw new IOException("Missing Tokyo-3 surveyed shell");
            try(var zip=new GZIPInputStream(raw)){ survey=zip.readAllBytes(); }
        }
        try(var in=new DataInputStream(new ByteArrayInputStream(survey))) {
            if(in.readInt()!=0x54333636 || in.readUnsignedShort()!=COUNT)throw new IOException("Skyline header");
            for(int i=0;i<COUNT;i++){
                int[] s=specs[i];for(int k=0;k<8;k++)s[k]=in.readShort();
                int n=in.readInt();if(n<=0||n>100000)throw new IOException("Invalid skyline surface count");
                firstQuad[i]=instances;quadCount[i]=n;instances+=n;int roof=0;
                for(int q=0;q<n;q++){int face=in.readUnsignedByte(),plane=in.readShort();in.skipNBytes(10);if(face==4)roof=Math.max(roof,plane);}
                for(int x=s[0]+s[4];x<=s[0]+s[5];x++)for(int z=s[2]+s[6];z<=s[2]+s[7];z++){
                    int k=(z-MIN_Z)*WIDTH+x-MIN_X;
                    if(x<MIN_X||z<MIN_Z||x>=MIN_X+WIDTH||z>=MIN_Z+HEIGHT||columnRoof[k]!=0)throw new IOException("Unexpected skyline footprint");
                    columnRoof[k]=(short)(s[1]+roof);
                }
            }
            if(in.read()!=-1 || instances>1000000)throw new IOException("Invalid skyline survey length");
        }
    }
    /** A transient DH meshing input for an authored shaft. No geometry or database outside it changes. */
    public static LongArrayList surveyColumn(Object dhLevel,int x,int z,LongArrayList original) {
        ClientLevel world=bound;
        if(world==null || original==null || x<MIN_X || z<MIN_Z || x>=MIN_X+WIDTH || z>=MIN_Z+HEIGHT) return original;
        int top=columnRoof[(z-MIN_Z)*WIDTH+x-MIN_X];
        if(top==0 || !dimensionMatches(dhLevel,world))return original;
        int low=81-world.getMinBuildHeight(), high=top-world.getMinBuildHeight();
        LongArrayList visible=null;
        // DH 2.3.4 FullDataPointUtil: [ID:32 | height:12 | relative bottom:12 | light:8].
        for(int i=0;i<original.size();i++){
            long p=original.getLong(i);int bottom=(int)(p>>>44)&4095, end=bottom+((int)(p>>>32)&4095);
            if(end<=low || bottom>=high){if(visible!=null)visible.add(p);continue;}
            if(visible==null){visible=new LongArrayList(original.size()+1);for(int j=0;j<i;j++)visible.add(original.getLong(j));}
            if(end>high) visible.add(segment(p,high,end-high));
            if(bottom<low) visible.add(segment(p,bottom,low-bottom));
        }
        if(visible==null)return original;
        if(REVIEW)filtered++;
        return visible;
    }
    private static long segment(long p,int bottom,int height){return (p & 0xff000000ffffffffL)|((long)height<<32)|((long)bottom<<44);}
    private static volatile Object lastDh,lastWorld;
    private static boolean dimensionMatches(Object dh,ClientLevel world){
        if(dh==lastDh && world==lastWorld)return true;
        try{
            Object wrapper=dh.getClass().getMethod("getLevelWrapper").invoke(dh);
            Object nativeLevel=wrapper.getClass().getMethod("getWrappedMcObject").invoke(wrapper);
            // In an integrated world DH's combined server/client level returns the
            // ServerLevel for each dimension. Its client wrapper aliases the current view
            // even for the Nether, so qualify the actual source's dimension here.
            if(nativeLevel!=world && !(nativeLevel instanceof net.minecraft.server.level.ServerLevel server
                    && server.dimension().equals(world.dimension())))return false;
            lastDh=dh;lastWorld=world;return true;
        }catch(ReflectiveOperationException e){return false;}
    }
    private static void initialize() throws IOException {
        FloatBuffer values=BufferUtils.createFloatBuffer(Math.multiplyExact(instances,STRIDE));
        try(var in=new DataInputStream(new ByteArrayInputStream(survey))) {
            in.skipNBytes(6);
            for(int i=0;i<COUNT;i++) {
                int[] s=specs[i];in.skipNBytes(16);int n=in.readInt();
                for(int j=0;j<n;j++){
                    int face=in.readUnsignedByte(),plane=in.readShort(),u=in.readShort(),w=in.readShort(),length=in.readUnsignedByte(),height=in.readUnsignedByte();
                    values.put(s[0]).put(s[1]).put(s[2]).put(s[3]-s[1]);
                    values.put(face).put(plane).put(u).put(w);
                    values.put(length).put(height).put(i).put(CityLightWavesR65.district(s[0],s[2]));
                    values.put(in.readUnsignedByte()/255F).put(in.readUnsignedByte()/255F).put(in.readUnsignedByte()/255F).put(in.readUnsignedByte());
                }
            }
        }
        program=CityNightLightsR65.link("city_skyline_r66.vsh","city_skyline_r66.fsh");
        vao=glGenVertexArrays();glBindVertexArray(vao);vbo=glGenBuffers();glBindBuffer(GL_ARRAY_BUFFER,vbo);
        glBufferData(GL_ARRAY_BUFFER,values.flip(),GL_STATIC_DRAW);
        for(int i=0;i<4;i++){glEnableVertexAttribArray(i);glVertexAttribPointer(i,4,GL_FLOAT,false,STRIDE*4,16L*i);glVertexAttribDivisor(i,1);}
        sampler=glGenSamplers();glSamplerParameteri(sampler,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glSamplerParameteri(sampler,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    }
    private static int uniform(String name){return glGetUniformLocation(program,name);}
    private static int shellDepth, nativeCopy;

    /** City shells need a writable depth buffer of their own. Native and DH depths are read-only inputs. */
    private static boolean beginColour(int[] box) {
        int source=glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING);
        if(box[0]!=0 || box[1]!=0 || source==0)return false;
        int type=glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE);
        if(type!=GL_TEXTURE && type!=GL_RENDERBUFFER)return false;
        int attachment=glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME);
        if(colourFbo==0)colourFbo=glGenFramebuffers();
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER,colourFbo);
        if(screenW!=box[2]||screenH!=box[3]) {
            if(colourTexture!=0)glDeleteTextures(colourTexture);
            colourTexture=glGenTextures();glActiveTexture(GL_TEXTURE8);glBindTexture(GL_TEXTURE_2D,colourTexture);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,box[2],box[3],0,GL_RGBA,GL_UNSIGNED_BYTE,0L);
            glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,colourTexture,0);glDrawBuffer(GL_COLOR_ATTACHMENT0);
            int previous=glGetInteger(GL_RENDERBUFFER_BINDING);
            if(shellDepth==0)shellDepth=glGenRenderbuffers();
            glBindRenderbuffer(GL_RENDERBUFFER,shellDepth);
            glRenderbufferStorage(GL_RENDERBUFFER,GL_DEPTH_COMPONENT32F,box[2],box[3]);
            glFramebufferRenderbuffer(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_RENDERBUFFER,shellDepth);
            glBindRenderbuffer(GL_RENDERBUFFER,previous);
            if(nativeCopy!=0){glDeleteTextures(nativeCopy);nativeCopy=0;}
            screenW=box[2];screenH=box[3];
        }
        if(glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)return false;
        glActiveTexture(GL_TEXTURE9);
        if(type==GL_TEXTURE)glBindTexture(GL_TEXTURE_2D,attachment);
        else {
            if(nativeCopy==0) {
                nativeCopy=glGenTextures();glBindTexture(GL_TEXTURE_2D,nativeCopy);
                glTexImage2D(GL_TEXTURE_2D,0,GL_DEPTH_COMPONENT32F,screenW,screenH,0,GL_DEPTH_COMPONENT,GL_FLOAT,0L);
                glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAX_LEVEL,0);
            } else glBindTexture(GL_TEXTURE_2D,nativeCopy);
            int previous=glGetInteger(GL_READ_FRAMEBUFFER_BINDING);
            glBindFramebuffer(GL_READ_FRAMEBUFFER,source);
            glCopyTexSubImage2D(GL_TEXTURE_2D,0,0,0,0,0,screenW,screenH);
            glBindFramebuffer(GL_READ_FRAMEBUFFER,previous);
        }
        glBindSampler(9,sampler);glUniform1i(uniform("nativeDepth"),9);
        glDisable(GL_SCISSOR_TEST);glDisable(GL_STENCIL_TEST);glColorMaski(0,true,true,true,true);glDepthMask(true);
        glClearBufferfv(GL_COLOR,0,new float[]{0,0,0,0});glClearBufferfv(GL_DEPTH,0,new float[]{1});
        return true;
    }
    @SubscribeEvent public static void frame(net.minecraftforge.event.TickEvent.RenderTickEvent event) {
        if(event.phase==net.minecraftforge.event.TickEvent.Phase.START)captured=false;
    }
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.HIGHEST)
    public static void compose(net.minecraftforge.client.event.RenderGuiEvent.Pre event) {
        afterLevel();
    }
    /** Resolve after postprocessing and before the hand, also when the HUD is hidden. */
    public static void afterLevel() {
        if(!captured||unavailable)return;
        captured=false;
        try(var state=new CityNightLightsR65.RenderState()) {
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER,Minecraft.getInstance().getMainRenderTarget().frameBufferId);
            if(composite==0){composite=CityNightLightsR65.link("city_composite.vsh","city_skyline_composite_r66.fsh");
                glUseProgram(composite);glUniform1i(glGetUniformLocation(composite,"skyline"),8);}
            glUseProgram(composite);glBindVertexArray(vao);glActiveTexture(GL_TEXTURE8);glBindTexture(GL_TEXTURE_2D,colourTexture);glBindSampler(8,sampler);
            glDisable(GL_SCISSOR_TEST);glDisable(GL_STENCIL_TEST);glDisable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);glDepthMask(false);
            glColorMaski(0,true,true,true,true);glEnablei(GL_BLEND,0);
            CityNightLightsR65.blend(GL_FUNC_ADD,GL_FUNC_ADD,GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_ZERO,GL_ONE);
            glDrawArrays(GL_TRIANGLES,0,3);
        }catch(IOException | RuntimeException | LinkageError ex){unavailable=true;bound=null;YashimaBlackoutR64.rebuildFarView();ProjectSeele.LOGGER.warn("Cannot composite Tokyo-3 skyline",ex);}
    }
    private static void quadRange(int i){
        for(int a=0;a<4;a++)glVertexAttribPointer(a,4,GL_FLOAT,false,STRIDE*4,(long)firstQuad[i]*STRIDE*4+a*16L);
        glDrawArraysInstanced(GL_TRIANGLES,0,6,quadCount[i]);
    }
    @SubscribeEvent public static void render(RenderLevelStageEvent event) {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS || unavailable || bound==null
                || com.projectseele.client.render.ShaderShadowPassR44.active())return;
        var mc=Minecraft.getInstance();var world=mc.level;
        if(world==null||world!=bound)return;
        var eye=event.getCamera().getPosition();if(eye.y<58||Math.abs(eye.x-30)>4000||Math.abs(eye.z-220)>4000)return;
        float[] offsets=CityNightLightsR65.skylineOffsets(world,world.getGameTime()+event.getPartialTick());if(offsets==null)return;
        try(var state=new CityNightLightsR65.RenderState();var mem=MemoryStack.stackPush()){
            glActiveTexture(GL_TEXTURE9);
            int oldTexture=glGetInteger(GL_TEXTURE_BINDING_2D), oldSampler=glGetIntegeri(GL_SAMPLER_BINDING,9);
            try {
            if(program==0)initialize();
            glUseProgram(program);glBindVertexArray(vao);
            glUniformMatrix4fv(uniform("pose"),false,event.getPoseStack().last().pose().get(mem.mallocFloat(16)));
            glUniformMatrix4fv(uniform("projection"),false,event.getProjectionMatrix().get(mem.mallocFloat(16)));
            glUniform3f(uniform("eye"),(float)eye.x,(float)eye.y,(float)eye.z);
            glUniform1fv(uniform("retraction"),offsets);
            glUniform1f(uniform("nativeRange"),Math.max(32,(mc.options.getEffectiveRenderDistance()-2)*16));
            float day=TvYashimaNightClientR54.night(world)?0:world.getSkyDarken(event.getPartialTick());
            glUniform1f(uniform("daylight"),day);
            glUniform1fv(uniform("power"),CityLightWavesR65.lightLevels());
            var fog=com.mojang.blaze3d.systems.RenderSystem.getShaderFogColor();glUniform3f(uniform("fogTint"),fog[0],fog[1],fog[2]);
            var depth=RamielTerrainDepthR64.sample(event.getProjectionMatrix());
            if(depth!=null && glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING)!=0 && glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE)==GL_TEXTURE
                && glGetFramebufferAttachmentParameteri(GL_DRAW_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME)==depth.texture())depth=null;
            int[] box=new int[4];glGetIntegerv(GL_VIEWPORT,box);if(!beginColour(box))return;glUniform4f(uniform("viewport"),box[0],box[1],box[2],box[3]);
            glActiveTexture(GL_TEXTURE8);glBindSampler(8,sampler);glBindTexture(GL_TEXTURE_2D,depth==null?0:depth.texture());
            glUniform1i(uniform("lod"),8);glUniform1i(uniform("haveLod"),depth==null?0:1);
            if(depth!=null)glUniform2f(uniform("lodTransform"),depth.scale(),depth.offset());
            glDisable(GL_CULL_FACE);glEnable(GL_DEPTH_TEST);glDepthFunc(GL_LESS);glDepthMask(true);glDisablei(GL_BLEND,0);
            glBindBuffer(GL_ARRAY_BUFFER,vbo);
            if(REVIEW && queryPending && glGetQueryObjecti(query,GL_QUERY_RESULT_AVAILABLE)!=0){
                int count=glGetQueryObjecti(query,GL_QUERY_RESULT);queryPending=false;
                ProjectSeele.LOGGER.info("R66 surveyed facade pixels before composition={} phase37={}",count,offsets[37]);
            }
            boolean sample=REVIEW && !queryPending && world.getGameTime()-lastQuery>=40;
            if(sample){if(query==0)query=glGenQueries();glBeginQuery(GL_SAMPLES_PASSED,query);lastQuery=world.getGameTime();}
            try {
                double near=Math.max(32,(mc.options.getEffectiveRenderDistance()-2)*16);
                for(int i=0;i<COUNT;i++){int[] t=specs[i];if(offsets[i]<0 || Math.max(Math.abs(t[0]-eye.x),Math.abs(t[2]-eye.z))<near || offsets[i]>=.9999F)continue;quadRange(i);}
            }finally{if(sample){glEndQuery(GL_SAMPLES_PASSED);queryPending=true;}}
            captured=true;
            if(REVIEW && Math.abs(lastReview-offsets[37])>.025F){lastReview=offsets[37];ProjectSeele.LOGGER.info("R66 fixed observer eye {} tower37={} cargoQuads={} clippedDhColumns={}",event.getCamera().getBlockPosition(),lastReview,instances,filtered);}
            } finally {
                glActiveTexture(GL_TEXTURE9);glBindTexture(GL_TEXTURE_2D,oldTexture);glBindSampler(9,oldSampler);
            }
        }catch(IOException | RuntimeException | LinkageError ex){unavailable=true;bound=null;YashimaBlackoutR64.rebuildFarView();ProjectSeele.LOGGER.warn("Tokyo-3 skyline renderer unavailable",ex);}
    }
    private CitySkylineR66() {}
}
