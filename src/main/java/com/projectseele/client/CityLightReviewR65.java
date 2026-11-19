package com.projectseele.client;

import com.projectseele.ProjectSeele;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Locale;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import static org.lwjgl.opengl.GL33C.*;

/** Opt-in frame evidence at the emplaced gun. Asynchronous sample queries never stall the game. */
@Mod.EventBusSubscriber(modid="projectseele", value=Dist.CLIENT)
public final class CityLightReviewR65
{
    private static final boolean ACTIVE=Boolean.getBoolean("projectseele.cityLightsReviewR65");
    private static int query, samples, frames, frameSamples, lastBands=-1, shots;
    private static boolean pending;
    private static long sampleTick=-40, intervalStart;
    private static Path directory;

    static boolean beginSample(long tick)
    {
        if (pending || tick-sampleTick<10 || glGetQueryi(GL_SAMPLES_PASSED,GL_CURRENT_QUERY)!=0) return false;
        if (query==0) query=glGenQueries();
        sampleTick=tick;
        glBeginQuery(GL_SAMPLES_PASSED,query);
        return true;
    }
    static void endSample(){glEndQuery(GL_SAMPLES_PASSED);pending=true;}

    @SubscribeEvent
    public static void frame(TickEvent.RenderTickEvent event)
    {
        if (!ACTIVE || event.phase!=TickEvent.Phase.END) return;
        if (pending && glGetQueryObjecti(query,GL_QUERY_RESULT_AVAILABLE)!=0)
        {
            samples=glGetQueryObjecti(query,GL_QUERY_RESULT);pending=false;
        }
        var mc=Minecraft.getInstance();
        if (mc.level==null || mc.player==null) return;
        var camera=mc.gameRenderer.getMainCamera();var p=camera.getPosition();
        if (Math.abs(p.x+1243)>180 || Math.abs(p.z+1401)>180 || p.y<115) return;
        if (!TvYashimaNightClientR54.night(mc.level) && !CityLightWavesR65.restoring(mc.level)) return;
        try {
            if (directory==null){
                directory=mc.gameDirectory.toPath().resolve("screenshots/city-lights-r65");
                Files.createDirectories(directory);
                Files.writeString(directory.resolve("frames.csv"),"tick,x,y,z,yaw,pitch,lit_districts,mean_fps,max_visible_samples\n");
            }
            int lit=0;
            for(float b:CityLightWavesR65.lightLevels()) if(b>.5F) lit++;
            long now=System.nanoTime();
            if(intervalStart==0)intervalStart=now;
            frames++;
            if (lit>0) frameSamples=Math.max(frameSamples,samples);
            if(now-intervalStart>=1_000_000_000L){
                String row=String.format(Locale.ROOT,"%d,%.2f,%.2f,%.2f,%.2f,%.2f,%d,%.2f,%d%n",
                    mc.level.getGameTime(),p.x,p.y,p.z,camera.getYRot(),camera.getXRot(),lit,frames*1e9/(now-intervalStart),frameSamples);
                Files.writeString(directory.resolve("frames.csv"),row,StandardOpenOption.APPEND);
                frameSamples=frames=0;intervalStart=now;
            }
            if (lit!=lastBands && (lit==8 || lit==6 || lit==4 || lit==2 || lit==0) && shots<24){
                Screenshot.grab(mc.gameDirectory,String.format(Locale.ROOT,"city-lights-r65/%02d_%d_lit.png",++shots,lit),
                        mc.getMainRenderTarget(),ignored->{});
            }
            lastBands=lit;
        } catch(IOException e){throw new IllegalStateException("City light evidence",e);}
    }
    private static int lastCompositeState=-1, comparisonIndex;

    /** In review mode only, two reads of the same final colour target isolate this pass from animation and shaders. */
    static Comparison beforeComposite(float firstTower) throws IOException
    {
        var mc=Minecraft.getInstance();
        if(mc.level==null || comparisonIndex>=28) return null;
        var pos=mc.gameRenderer.getMainCamera().getPosition();
        if(Math.abs(pos.x+1243)>180 || Math.abs(pos.z+1401)>180 || pos.y<115) return null;
        int lit=0;
        for(float b:CityLightWavesR65.lightLevels()) if(b>.5F)lit++;
        int key=lit*2+(firstTower>.5F?1:0);
        if(key==lastCompositeState) return null;
        lastCompositeState=key;
        int[] size=new int[4];glGetIntegerv(GL_VIEWPORT,size);
        if(size[2]<=0 || size[3]<=0 || size[2]*(long)size[3]>9000000) return null;
        var dir=mc.gameDirectory.toPath().resolve("screenshots/city-lights-r65/final-colour");
        Files.createDirectories(dir);
        return new Comparison(dir,++comparisonIndex,lit,firstTower,size);
    }

    record Comparison(Path dir,int index,int lit,float tower,int[] rect,byte[] before)
    {
        Comparison(Path dir,int index,int lit,float tower,int[] rect)
        {
            this(dir,index,lit,tower,rect,readFinal(rect));
        }
        void finish() throws IOException
        {
            byte[] after=readFinal(rect);
            int width=rect[2],height=rect[3],changed=0,peak=0;
            long gain=0;
            var image=new java.awt.image.BufferedImage(width,height,java.awt.image.BufferedImage.TYPE_INT_RGB);
            for(int y=0;y<height;y++)for(int x=0;x<width;x++)
            {
                int j=(y*width+x)*4,d=0,rgb=0;
                for(int i=0;i<3;i++) {
                    int now=after[j+i]&255,old=before[j+i]&255;
                    d=Math.max(d,now-old);
                    gain+=now-old;
                    rgb=rgb<<8|now;
                }
                if(d>3) changed++;
                peak=Math.max(peak,d);
                image.setRGB(x,height-1-y,rgb);
            }
            String file=String.format(Locale.ROOT,"%02d-%d-lit.png",index,lit);
            javax.imageio.ImageIO.write(image,"PNG",dir.resolve(file).toFile());
            String row=String.format(Locale.ROOT,"%d,%d,%.3f,%d,%d,%d,%s%n",index,lit,tower,changed,peak,gain,file);
            Files.writeString(dir.resolve("rgb.csv"),row,StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
        private static byte[] readFinal(int[] rect)
        {
            int oldRead=glGetInteger(GL_READ_FRAMEBUFFER_BINDING),buffer=glGetInteger(GL_PIXEL_PACK_BUFFER_BINDING);
            byte[] pixels=new byte[rect[2]*rect[3]*4];
            var data=org.lwjgl.system.MemoryUtil.memAlloc(pixels.length);
            try {
                glBindFramebuffer(GL_READ_FRAMEBUFFER,glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING));
                glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
                glReadPixels(rect[0],rect[1],rect[2],rect[3],GL_RGBA,GL_UNSIGNED_BYTE,data);
                data.get(pixels);
                return pixels;
            } finally {
                glBindBuffer(GL_PIXEL_PACK_BUFFER,buffer);
                glBindFramebuffer(GL_READ_FRAMEBUFFER,oldRead);
                org.lwjgl.system.MemoryUtil.memFree(data);
            }
        }
    }
    private CityLightReviewR65(){}
}
