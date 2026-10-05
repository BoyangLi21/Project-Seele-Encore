package com.projectseele.client;

import java.awt.image.BufferedImage;
import java.io.IOException;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;


import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.client.visual.VisualCaptureManager;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.ClientboundPilotStatusPacket;
import com.projectseele.network.EvaVideoFrameTransport;
import com.projectseele.network.EvaFrameCodec;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaVideoFramePacket;
import com.projectseele.visual.GeoFrontCommands;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.FacilityV2CommandInteriorDirector;
import net.minecraft.world.level.block.Blocks;
import com.projectseele.world.NervOperationsCentreBuilder;
import com.projectseele.world.PerformanceCounters;
import com.projectseele.world.S20CommandPresentationDirector;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.CameraType;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.gui.Font;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.Util;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/**
 * Captures an independent first-person optical view and renders authenticated
 * remote frames on three physical 16:9 screens in NERV operations.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE,
        value = Dist.CLIENT)
public final class EvaCommandFeedClient
{
    public static boolean isOpticalRenderPass(){return captureRenderPass;}
    public static final IGuiOverlay CAPTURE_OVERLAY =
            (gui, graphics, partialTick, width, height) ->
            {
                if(!Minecraft.getInstance().options.getCameraType().isFirstPerson())captureIfDue(partialTick);
            };

    public static void opticalWorldRendered(float partial)
    {
        if(!captureRenderPass&&Minecraft.getInstance().options.getCameraType().isFirstPerson())captureIfDue(partial);
    }

    /**
     * Capture runs on operator demand; each JPEG fits the configured byte
     * budget before it reaches Minecraft's bounded chunk transport.
     */
    private static final long FRAME_STALE_NANOS = 1_500_000_000L;
    private static final double DISPLAY_RANGE_SQR = 150.0D * 150.0D;
    private static final float SCREEN_WIDTH = 10.5F;
    private static final float SCREEN_HEIGHT =
            SCREEN_WIDTH * ServerboundEvaVideoFramePacket.FRAME_HEIGHT
                    / ServerboundEvaVideoFramePacket.FRAME_WIDTH;
    private static final int[] SCREEN_X = {-12, 0, 12};
    /*
     * The S19 command asset already owns one measured amber sloped screen.
     * Divide that authored 15-block face into three optical feeds; never draw
     * the retired z=-68 video wall in front of it.
     */
    private static final double[] V2_SCREEN_X = {-4.0D, 1.0D, 6.0D};
    private static final double[] V2_SCREEN_Y =
            {-319.5D, -319.5D, -319.5D};
    private static final double[] V2_SCREEN_Z =
            {-36.0D, -36.0D, -36.0D};
    private static final float[] V2_SCREEN_YAW = {0.0F, 0.0F, 0.0F};
    private static final float[] V2_SCREEN_PITCH =
            {-27.3F, -27.3F, -27.3F};
    private static final float[] V2_SCREEN_WIDTH =
            {4.5F, 4.5F, 4.5F};
    /*
     * The upper authored mask is a tall 17x35 sloped plane.  Three landscape
     * pilot feeds therefore stack along its long axis instead of becoming
     * three tiny tiles across its narrow width.
     */
    private static final double[] S20_SCREEN_X = {28.0D, 28.0D, 28.0D};
    private static final double[] S20_SCREEN_Y =
            {-406.90D, -415.795D, -424.69D};
    private static final double[] S20_SCREEN_Z =
            {327.38D, 322.793D, 318.20D};
    private static final float S20_SCREEN_YAW = 180.0F;
    private static final float S20_UPPER_SCREEN_PITCH = -27.3F;
    /**
     * The measured mask lies at -68.8 degrees, which is almost flat: its
     * normal points nearly straight at the ceiling, so an operator standing in
     * front of it reads the pilot rows at a glancing angle.  Standing the
     * board up by seven degrees turns the face toward the room without pulling
     * the raster off the authored slope.
     */
    private static final float S20_LOWER_SCREEN_PITCH = -61.8F;
    private static final long SCREEN_TRANSITION_NANOS = 400_000_000L;
    private static final float[] SCREEN_VISIBILITY =
            {1.0F, 1.0F, 1.0F, 1.0F, 1.0F};
    private static final float[] SCREEN_TARGET =
            {1.0F, 1.0F, 1.0F, 1.0F, 1.0F};
    private static final AtomicBoolean CAPTURE_IN_FLIGHT =
            new AtomicBoolean();
    private static final AtomicInteger NEXT_CAPTURE_FRAME_ID =
            new AtomicInteger();
    private static final AtomicInteger CONNECTION_GENERATION =
            new AtomicInteger();
    private static final EvaVideoFrameTransport.Assembly[] INCOMING_FRAMES =
            new EvaVideoFrameTransport.Assembly[3];
    private record QueuedFrame(byte[] bytes,int generation) {}
    private record DecodedFrame(NativeImage image,int generation) {}
    private static final java.util.List<AtomicReference<QueuedFrame>> WAITING = java.util.List.of(
            new AtomicReference<>(),new AtomicReference<>(),new AtomicReference<>());
    private static final java.util.List<AtomicReference<DecodedFrame>> DECODED = java.util.List.of(
            new AtomicReference<>(),new AtomicReference<>(),new AtomicReference<>());
    private static final java.util.List<AtomicBoolean> DECODING = java.util.List.of(
            new AtomicBoolean(),new AtomicBoolean(),new AtomicBoolean());
    private static final java.util.List<AtomicBoolean> UPLOADING = java.util.List.of(
            new AtomicBoolean(),new AtomicBoolean(),new AtomicBoolean());
    private static final int[] NEWEST_FRAME_ID = new int[3];
    private static final boolean[] HAS_FRAME_ID = new boolean[3];
    private static TextureTarget firstPersonCaptureTarget;
    private static RenderTarget captureTargetOverride;
    private static boolean captureRenderPass;
    private static final DynamicTexture[] TEXTURES =
            new DynamicTexture[3];
    private static final long[] LAST_FRAME_NANOS = new long[3];
    private static final ResourceLocation[] TEXTURE_IDS = {
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_feed_00"),
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_feed_01"),
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_feed_02")
    };
    private static final DynamicTexture[] STANDBY_TEXTURES =
            new DynamicTexture[3];
    private static final ResourceLocation[] STANDBY_TEXTURE_IDS = {
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_standby_00"),
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_standby_01"),
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/eva_command_standby_02")
    };
    private static DynamicTexture tacticalTexture;
    private static final ResourceLocation TACTICAL_TEXTURE_ID =
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/nerv_tactical_overview");
    private static DynamicTexture cityTexture;
    private static final ResourceLocation CITY_TEXTURE_ID =
            new ResourceLocation(ProjectSeele.MODID,
                    "dynamic/tokyo3_retraction_monitor");
    private static final int CITY_TEXTURE_WIDTH = 768;
    private static final int CITY_TEXTURE_HEIGHT = 256;
    private static String cityPhase = "STANDBY";
    private static int cityDepth;
    private static int cityTargetDepth;
    private static int cityMaximumDepth = 1;
    private static float cityPhysicalRetractionFraction;
    private static String armamentState = "OFFLINE";
    private static boolean armamentStocked;
    private static int armamentLiftPercent;
    private static boolean cityTextureDirty = true;
    /*
     * The board is 15 blocks wide.  At 1/0.070 font pixels per block a line of
     * thirty-five characters just fits between its amber margins, which is the
     * widest row the status layout below ever produces.
     */
    private static final float TACTICAL_TEXT_SCALE = 0.070F;
    private static final int TACTICAL_LINE_HEIGHT = 20;
    private static final int TACTICAL_LEFT = -97;
    private static final int TACTICAL_TOP = -272;
    private static ClientboundPilotStatusPacket.Unit[] pilotStatus;
    private static final int[][] UNIT_COLOURS = {
            {232, 143, 38}, {144, 62, 205}, {210, 45, 52}
    };

    private static long nextCaptureNanos;
    private static volatile float compressionHint=.86F;
    private static final java.util.concurrent.atomic.AtomicLong REVIEW_CAPTURED=new java.util.concurrent.atomic.AtomicLong();
    private static final java.util.concurrent.atomic.AtomicLong REVIEW_ENCODED=new java.util.concurrent.atomic.AtomicLong();
    private static final java.util.concurrent.atomic.AtomicLong REVIEW_UPLOADED=new java.util.concurrent.atomic.AtomicLong();
    private static final java.util.concurrent.atomic.AtomicLong REVIEW_MAX_BYTES=new java.util.concurrent.atomic.AtomicLong();
    private static ClientLevel captureLevel;
    private static int captureEvaId = Integer.MIN_VALUE;
    private static ClientLevel activeLevel;
    private static boolean captureDemanded;
    private static long lastScreenTransitionNanos = System.nanoTime();

    private EvaCommandFeedClient() {}

    private static void captureIfDue(float partialTick)
    {
        Minecraft minecraft = Minecraft.getInstance();
        EvaUnit01Entity eva = minecraft.player == null
                ? null : EvaPilotResolver.controlTarget(minecraft.player);
        if (!SeeleConfig.liveCockpitVideoEnabled()
                || !captureDemanded
                || minecraft.player == null || minecraft.level == null
                || minecraft.screen != null
                || VisualCaptureManager.isSuppressingGui()
                || eva == null
                || eva.isExperimentalUnit()
                || EvaPilotResolver.pilot(eva) != minecraft.player
                || !eva.isAlive())
        {
            return;
        }
        if (captureLevel != minecraft.level || captureEvaId != eva.getId())
        {
            captureLevel = minecraft.level;
            captureEvaId = eva.getId();
            nextCaptureNanos = 0;
        }
        long now = System.nanoTime();
        long interval=1_000_000_000L / SeeleConfig.VIDEO_TARGET_FPS.get();
        if (now < nextCaptureNanos
                || !CAPTURE_IN_FLIGHT.compareAndSet(false, true))
        {
            return;
        }
        // Preserve cadence across render-frame rounding, without queuing a
        // catch-up burst after a pause or a slow encode.
        nextCaptureNanos = Math.max(nextCaptureNanos+interval,now+interval/4);

        NativeImage full;
        try
        {
            full = captureFirstPersonFrame(minecraft, partialTick);
            PerformanceCounters.recordFramebufferCapture();
            if(Boolean.getBoolean("projectseele.feedReviewR06"))REVIEW_CAPTURED.incrementAndGet();
        }
        catch (RuntimeException exception)
        {
            CAPTURE_IN_FLIGHT.set(false);
            ProjectSeele.LOGGER.warn(
                    "Unable to capture EVA command feed", exception);
            return;
        }
        int variant = eva.getUnitVariant();
        int sourceId = eva.getId();
        int generation = CONNECTION_GENERATION.get();
        Util.ioPool().execute(() -> encodeAndSend(
                minecraft, variant, generation, sourceId, full));
    }

    /**
     * Produces the pilot's optical view without changing the camera selected
     * on the pilot's monitor.  When the player is using third person, one
     * additional world+hand pass is rendered into a private target while the
     * normal framebuffer remains untouched.
     */
    private static NativeImage captureFirstPersonFrame(
            Minecraft minecraft, float partialTick)
    {
        RenderTarget mainTarget = minecraft.getMainRenderTarget();
        int readBuffer=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL30.GL_READ_FRAMEBUFFER_BINDING);
        int drawBuffer=org.lwjgl.opengl.GL11.glGetInteger(org.lwjgl.opengl.GL30.GL_DRAW_FRAMEBUFFER_BINDING);
        int width=SeeleConfig.VIDEO_CAPTURE_WIDTH.get()/16*16,height=width*9/16;
        if(firstPersonCaptureTarget==null)
            firstPersonCaptureTarget=new TextureTarget(width,height,true,Minecraft.ON_OSX);
        else if(firstPersonCaptureTarget.viewWidth!=width||firstPersonCaptureTarget.viewHeight!=height)
            firstPersonCaptureTarget.resize(width,height,Minecraft.ON_OSX);
        if (minecraft.options.getCameraType().isFirstPerson()&&!FirstBattleClient.active())
        {
            // Read back the stream-sized image, not a possible 4K/ultrawide display.
            int sourceWidth=mainTarget.viewWidth,sourceHeight=mainTarget.viewHeight;
            int cropWidth=Math.min(sourceWidth,sourceHeight*16/9),cropHeight=Math.min(sourceHeight,sourceWidth*9/16);
            int x=(sourceWidth-cropWidth)/2,y=(sourceHeight-cropHeight)/2;
            try
            {
                org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_READ_FRAMEBUFFER,mainTarget.frameBufferId);
                org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_DRAW_FRAMEBUFFER,firstPersonCaptureTarget.frameBufferId);
                org.lwjgl.opengl.GL30.glBlitFramebuffer(x,y,x+cropWidth,y+cropHeight,0,0,width,height,
                        org.lwjgl.opengl.GL11.GL_COLOR_BUFFER_BIT,org.lwjgl.opengl.GL11.GL_LINEAR);
                return Screenshot.takeScreenshot(firstPersonCaptureTarget);
            }
            finally
            {
                org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_READ_FRAMEBUFFER,readBuffer);
                org.lwjgl.opengl.GL30.glBindFramebuffer(org.lwjgl.opengl.GL30.GL_DRAW_FRAMEBUFFER,drawBuffer);
            }
        }

        CameraType originalCamera = minecraft.options.getCameraType();
        var modelView=com.mojang.blaze3d.systems.RenderSystem.getModelViewStack();
        var projection=new Matrix4f(com.mojang.blaze3d.systems.RenderSystem.getProjectionMatrix());
        var sorting=com.mojang.blaze3d.systems.RenderSystem.getVertexSorting();
        var inverseView=new Matrix3f(com.mojang.blaze3d.systems.RenderSystem.getInverseViewRotationMatrix());
        modelView.pushPose();
        try
        {
            // This pass starts inside a GUI overlay. Its global model-view
            // matrix still contains the GUI far-plane translation; world
            // entities would otherwise be clipped despite submitting vertices.
            modelView.setIdentity();com.mojang.blaze3d.systems.RenderSystem.applyModelViewMatrix();
            minecraft.options.setCameraType(CameraType.FIRST_PERSON);
            captureTargetOverride = firstPersonCaptureTarget;
            captureRenderPass = true;
            firstPersonCaptureTarget.setClearColor(0.0F, 0.0F, 0.0F, 1.0F);
            firstPersonCaptureTarget.clear(Minecraft.ON_OSX);
            firstPersonCaptureTarget.bindWrite(true);
            minecraft.gameRenderer.renderLevel(
                    partialTick, Util.getNanos(), new PoseStack());
            // renderLevel already includes GameRenderer's first-person hand
            // pass.  Calling it a second time produces doubled arms and depth
            // flicker in the command-room feed.
            return Screenshot.takeScreenshot(firstPersonCaptureTarget);
        }
        finally
        {
            captureTargetOverride = null;
            captureRenderPass = false;
            minecraft.options.setCameraType(originalCamera);
            modelView.popPose();com.mojang.blaze3d.systems.RenderSystem.applyModelViewMatrix();
            com.mojang.blaze3d.systems.RenderSystem.setProjectionMatrix(projection,sorting);
            com.mojang.blaze3d.systems.RenderSystem.setInverseViewRotationMatrix(inverseView);
            mainTarget.bindWrite(true);
        }
    }

    /** Used only by the Minecraft render-target mixin during the extra pass. */
    public static RenderTarget captureTargetOverride()
    {
        return captureRenderPass ? captureTargetOverride : null;
    }

    /**
     * The pilot client cannot know whether a remote operator is watching the
     * command wall. Server demand keeps GPU readback and image compression at
     * zero cost in normal one-player testing.
     */
    public static void setCaptureDemand(boolean demanded)
    {
        captureDemanded = demanded;
    }


    /** Applies the server-authoritative power state; rendering eases to it. */
    public static void setCommandScreenMask(int visibleMask)
    {
        for (int screen = 0; screen < SCREEN_TARGET.length; screen++)
        {
            SCREEN_TARGET[screen] = (visibleMask & 1 << screen) != 0
                    ? 1.0F : 0.0F;
        }
        lastScreenTransitionNanos = System.nanoTime();
    }

    private static void updateCommandScreenTransitions()
    {
        long now = System.nanoTime();
        float step = Math.min(1.0F,
                (now - lastScreenTransitionNanos)
                        / (float) SCREEN_TRANSITION_NANOS);
        lastScreenTransitionNanos = now;
        for (int screen = 0; screen < SCREEN_VISIBILITY.length; screen++)
        {
            float current = SCREEN_VISIBILITY[screen];
            float target = SCREEN_TARGET[screen];
            if (current < target)
            {
                SCREEN_VISIBILITY[screen] = Math.min(target, current + step);
            }
            else if (current > target)
            {
                SCREEN_VISIBILITY[screen] = Math.max(target, current - step);
            }
        }
    }

    private static void encodeAndSend(Minecraft minecraft, int variant,
                                      int generation, int sourceId, NativeImage full)
    {
        try (full)
        {
            EvaFrameCodec.Encoded encoded = encodeJpeg(full);
            byte[] png = encoded.bytes();
            if(Boolean.getBoolean("projectseele.feedReviewR06")) { REVIEW_ENCODED.incrementAndGet();REVIEW_MAX_BYTES.accumulateAndGet(png.length,Math::max); }
            compressionHint=encoded.quality();
            PerformanceCounters.recordPngEncode();
            if (png.length <= ServerboundEvaVideoFramePacket.MAX_FRAME_BYTES)
            {
                int frameId = NEXT_CAPTURE_FRAME_ID.incrementAndGet();
                int chunks = EvaVideoFrameTransport.chunkCount(png.length);
                minecraft.execute(() -> sendFrameChunks(minecraft, variant,
                        generation, sourceId, frameId, chunks, png));
            }
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.warn(
                    "Unable to encode EVA command feed", exception);
        }
        finally
        {
            CAPTURE_IN_FLIGHT.set(false);
        }
    }

    private static void sendFrameChunks(Minecraft minecraft, int variant,
                                        int generation, int sourceId, int frameId,
                                        int chunks, byte[] frame)
    {
        if (generation != CONNECTION_GENERATION.get()
                || !captureDemanded || minecraft.player == null
                || minecraft.level == null || minecraft.getConnection() == null)
        {
            return;
        }
        EvaUnit01Entity source=EvaPilotResolver.controlTarget(minecraft.player);
        if(source==null||source.getId()!=sourceId)return;
        for (int index = 0; index < chunks; index++)
        {
            SeeleNetwork.CHANNEL.sendToServer(
                    new ServerboundEvaVideoFramePacket(variant, frameId,
                            index, chunks, frame.length,
                            EvaVideoFrameTransport.chunk(frame, index)));
        }
    }

    public static void acceptFrameChunk(int variant, int frameId,
                                        int chunkIndex, int chunkCount,
                                        int totalBytes, byte[] chunk)
    {
        if (variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02
                || !EvaVideoFrameTransport.validHeader(chunkIndex,
                chunkCount, totalBytes, chunk))
        {
            return;
        }
        EvaVideoFrameTransport.Assembly assembly = INCOMING_FRAMES[variant];
        if(HAS_FRAME_ID[variant]&&frameId!=NEWEST_FRAME_ID[variant]&&frameId-NEWEST_FRAME_ID[variant]<=0)return;
        if(HAS_FRAME_ID[variant]&&frameId==NEWEST_FRAME_ID[variant]&&assembly==null)return;
        NEWEST_FRAME_ID[variant]=frameId;HAS_FRAME_ID[variant]=true;
        if (assembly == null || assembly.expired(System.nanoTime())
                || !assembly.matches(frameId, chunkCount, totalBytes))
        {
            assembly = new EvaVideoFrameTransport.Assembly(frameId,
                    chunkCount, totalBytes);
            INCOMING_FRAMES[variant] = assembly;
        }
        if (!assembly.accept(chunkIndex, chunk))
        {
            INCOMING_FRAMES[variant] = null;
            return;
        }
        if (assembly.complete())
        {
            INCOMING_FRAMES[variant] = null;
            byte[] frame = assembly.join();
            if (frame != null)
            {
                acceptFrame(variant, frame);
            }
        }
    }

    public static void resetConnectionState()
    {
        captureDemanded = false;
        cityPhysicalRetractionFraction = 0;
        cityPhase = "STANDBY"; cityDepth = cityTargetDepth = 0; cityMaximumDepth = 1;
        cityTextureDirty = true;
        CONNECTION_GENERATION.incrementAndGet();
        captureLevel = null;
        captureEvaId = Integer.MIN_VALUE;
        for (int variant = 0; variant < INCOMING_FRAMES.length; variant++)
        {
            INCOMING_FRAMES[variant] = null;
            HAS_FRAME_ID[variant]=false;WAITING.get(variant).set(null);
            var decoded=DECODED.get(variant).getAndSet(null);
            if(decoded!=null)decoded.image().close();
        }
    }

    public static void acceptFrame(int variant, byte[] png)
    {
        if (!SeeleConfig.videoFrameRelayEnabled()
                || variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02)
        {
            return;
        }
        if(EvaFrameCodec.inspect(png)==null)return;
        WAITING.get(variant).set(new QueuedFrame(png,CONNECTION_GENERATION.get()));
        startDecode(variant);
    }

    private static void startDecode(int variant)
    {
        if(!DECODING.get(variant).compareAndSet(false,true))return;
        Util.ioPool().execute(()->{
            try
            {
                QueuedFrame frame;
                while((frame=WAITING.get(variant).getAndSet(null))!=null)
                {
                    if(frame.generation()!=CONNECTION_GENERATION.get())continue;
                    // NativeImage.read(byte[]) copies the complete image onto
                    // LWJGL's small per-thread stack. Use heap-owned native input.
                    NativeImage image;
                    var input=org.lwjgl.system.MemoryUtil.memAlloc(frame.bytes().length);
                    try { input.put(frame.bytes()).flip();image=NativeImage.read(input); }
                    finally { org.lwjgl.system.MemoryUtil.memFree(input); }
                    if(!EvaFrameCodec.allowedSize(image.getWidth(),image.getHeight())
                            ||frame.generation()!=CONNECTION_GENERATION.get()||WAITING.get(variant).get()!=null)
                    {
                        image.close();continue;
                    }
                    var old=DECODED.get(variant).getAndSet(new DecodedFrame(image,frame.generation()));
                    if(old!=null)old.image().close();
                    scheduleUpload(variant);
                }
            }
            catch(IOException|RuntimeException failure)
            {
                ProjectSeele.LOGGER.warn("Rejected EVA command feed frame",failure);
            }
            finally
            {
                DECODING.get(variant).set(false);
                if(WAITING.get(variant).get()!=null)startDecode(variant);
            }
        });
    }

    private static void scheduleUpload(int variant)
    {
        if(!UPLOADING.get(variant).compareAndSet(false,true))return;
        Minecraft.getInstance().execute(()->{
            try
            {
                var frame=DECODED.get(variant).getAndSet(null);
                if(frame!=null)
                {
                    if(frame.generation()==CONNECTION_GENERATION.get())uploadFrame(variant,frame.image());
                    else frame.image().close();
                }
            }
            finally
            {
                UPLOADING.get(variant).set(false);
                if(DECODED.get(variant).get()!=null)scheduleUpload(variant);
            }
        });
    }

    private static void uploadFrame(int variant,NativeImage image)
    {
        try
        {
            Minecraft minecraft = Minecraft.getInstance();
            DynamicTexture texture = TEXTURES[variant];
            if(texture!=null&&(texture.getPixels()==null||texture.getPixels().getWidth()!=image.getWidth()
                    ||texture.getPixels().getHeight()!=image.getHeight()))
            {
                texture.close();texture=null;TEXTURES[variant]=null;
            }
            if (texture == null)
            {
                texture = new DynamicTexture(image);
                TEXTURES[variant] = texture;
                minecraft.getTextureManager().register(
                        TEXTURE_IDS[variant], texture);
            }
            else
            {
                texture.setPixels(image);
            }
            texture.upload();
            LAST_FRAME_NANOS[variant] = System.nanoTime();
            if(Boolean.getBoolean("projectseele.feedReviewR06"))REVIEW_UPLOADED.incrementAndGet();
        }
        catch (RuntimeException exception)
        {
            if (image != null)
            {
                image.close();
            }
            ProjectSeele.LOGGER.warn(
                    "Rejected EVA command feed frame", exception);
        }
    }

    /** True only while this client owns a recently decoded command-room frame. */
    public static long[] reviewCounts()
    {
        return new long[]{REVIEW_CAPTURED.get(),REVIEW_ENCODED.get(),REVIEW_UPLOADED.get(),REVIEW_MAX_BYTES.get()};
    }

    public static void saveReviewFeed(int variant,java.nio.file.Path file)
    {
        if(!Boolean.getBoolean("projectseele.feedReviewR06")||TEXTURES[variant]==null)return;
        var pixels=TEXTURES[variant].getPixels();if(pixels==null)return;
        var copy=new NativeImage(pixels.getWidth(),pixels.getHeight(),false);copy.copyFrom(pixels);
        Util.ioPool().execute(()->{
            try(copy){java.nio.file.Files.createDirectories(file.getParent());copy.writeToFile(file);}
            catch(IOException failure){ProjectSeele.LOGGER.warn("Saving feed review",failure);}
        });
    }

    public static boolean hasFreshFrame(int variant)
    {
        return variant >= EvaUnit01Entity.UNIT_00
                && variant <= EvaUnit01Entity.UNIT_02
                && TEXTURES[variant] != null
                && System.nanoTime() - LAST_FRAME_NANOS[variant]
                        <= FRAME_STALE_NANOS;
    }

    @SubscribeEvent
    public static void onRenderLevelStage(RenderLevelStageEvent event)
    {
        if (captureRenderPass)
        {
            return;
        }
        /*
         * Screens must be drawn before the translucent chunk layer.  Glass
         * writes depth, so the old AFTER_PARTICLES pass rejected every screen
         * fragment viewed through glass even though the glass was transparent.
         */
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_CUTOUT_BLOCKS)
        {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        ClientLevel level = minecraft.level;
        if (level == null || minecraft.player == null
                || !level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            activeLevel = level;
            PerformanceCounters.leaveClientScenario();
            return;
        }
        PerformanceCounters.recordClientFrame();
        if (activeLevel != level)
        {
            activeLevel = level;
            for (int index = 0; index < LAST_FRAME_NANOS.length; index++)
            {
                LAST_FRAME_NANOS[index] = 0L;
            }
        }

        var v2Centre = FacilitySchemaV2.CANDIDATE_CENTRES.get(
                FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX);
        var v2Marker = v2Centre.offset(
                FacilityV2CommandInteriorDirector.MARKER_X,
                FacilityV2CommandInteriorDirector.MARKER_Y,
                FacilityV2CommandInteriorDirector.MARKER_Z);
        boolean facilityV2 = level.getBlockState(v2Marker)
                .is(Blocks.RED_NETHER_BRICKS);
        boolean s20Marker = level.getBlockState(
                S20CommandPresentationDirector.COMMAND_MARKER)
                .is(Blocks.STRUCTURE_VOID);
        /*
         * The marker lives six chunks behind the command seats and may reach
         * the client after the room itself at short render distance.  The
         * approved physical screen-control bank is an equally strict local
         * signature and keeps every display from vanishing during that load
         * window.
         */
        boolean s20Controls = level.getBlockState(
                new net.minecraft.core.BlockPos(32, -407, 286))
                .getBlock()
                instanceof net.minecraft.world.level.block.ButtonBlock;
        boolean s20 = s20Marker || s20Controls;

        var origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        var importedAnchor = origin.offset(0, 17, 58);
        boolean importedVideoWall = level.getBlockState(
                importedAnchor.offset(0, 4, -1)).is(Blocks.BLACK_CONCRETE)
                && level.getBlockState(importedAnchor.offset(-18, 4, -1))
                .is(Blocks.POLISHED_DEEPSLATE);
        var anchor = s20 ? new net.minecraft.core.BlockPos(
                (int) S20CommandPresentationDirector.UPPER_SCREEN_X,
                (int) S20CommandPresentationDirector.UPPER_SCREEN_Y,
                (int) S20CommandPresentationDirector.UPPER_SCREEN_Z)
                : facilityV2 ? v2Centre.offset(1, -320, -36)
                : importedVideoWall ? importedAnchor
                : origin.offset(0, 7,
                        NervOperationsCentreBuilder.DISPLAY_Z + 1);
        if (minecraft.player.position().distanceToSqr(
                Vec3.atCenterOf(anchor)) > DISPLAY_RANGE_SQR)
        {
            return;
        }

        ensureStandbyTextures(minecraft);
        updateCommandScreenTransitions();
        if (s20)
        {
            ensureTacticalTexture(minecraft);
            ensureCityTexture(minecraft);
        }
        long now = System.nanoTime();
        Vec3 camera = event.getCamera().getPosition();
        for (int variant = 0; variant < 3; variant++)
        {
            boolean live = TEXTURES[variant] != null
                    && now - LAST_FRAME_NANOS[variant]
                    <= FRAME_STALE_NANOS;
            ResourceLocation texture = live ? TEXTURE_IDS[variant]
                    : STANDBY_TEXTURE_IDS[variant];
            if (s20)
            {
                Vec3 centre = new Vec3(
                        S20_SCREEN_X[variant],
                        S20_SCREEN_Y[variant],
                        S20_SCREEN_Z[variant]);
                renderScreen(event.getPoseStack(), camera, centre,
                        texture, minecraft, 15.0F,
                        15.0F * ServerboundEvaVideoFramePacket.FRAME_HEIGHT
                                / ServerboundEvaVideoFramePacket.FRAME_WIDTH,
                        S20_SCREEN_YAW, S20_UPPER_SCREEN_PITCH,
                        SCREEN_VISIBILITY[variant]);
            }
            else if (facilityV2)
            {
                Vec3 centre = new Vec3(
                        v2Centre.getX() + V2_SCREEN_X[variant] + 0.5D,
                        V2_SCREEN_Y[variant],
                        v2Centre.getZ() + V2_SCREEN_Z[variant] + 0.56D);
                float width = V2_SCREEN_WIDTH[variant];
                renderScreen(event.getPoseStack(), camera, centre,
                        texture, minecraft, width,
                        width * ServerboundEvaVideoFramePacket.FRAME_HEIGHT
                                / ServerboundEvaVideoFramePacket.FRAME_WIDTH,
                        V2_SCREEN_YAW[variant],
                        V2_SCREEN_PITCH[variant], 1.0F);
            }
            else
            {
                Vec3 centre = Vec3.atCenterOf(
                        anchor.offset(SCREEN_X[variant], 4, 0))
                        .add(0.0D, 0.0D, -0.48D);
                renderScreen(event.getPoseStack(), camera, centre,
                        texture, minecraft, SCREEN_WIDTH, SCREEN_HEIGHT,
                        0.0F, 0.0F, 1.0F);
            }
        }
        if (s20 && tacticalTexture != null)
        {
            renderScreen(event.getPoseStack(), camera, new Vec3(
                            S20CommandPresentationDirector.LOWER_SCREEN_X,
                            S20CommandPresentationDirector.LOWER_SCREEN_Y,
                            S20CommandPresentationDirector.LOWER_SCREEN_Z),
                    TACTICAL_TEXTURE_ID, minecraft, 15.0F, 40.5F,
                    S20_SCREEN_YAW, S20_LOWER_SCREEN_PITCH,
                    SCREEN_VISIBILITY[3]);
            renderPilotStatusBoard(event.getPoseStack(), camera, minecraft,
                    SCREEN_VISIBILITY[3]);
        }
        if (s20 && cityTexture != null)
        {
            renderScreen(event.getPoseStack(), camera, new Vec3(
                            S20CommandPresentationDirector.CITY_STATUS_CENTRE_X,
                            (S20CommandPresentationDirector.CITY_STATUS_FACE_TOP
                                    + S20CommandPresentationDirector
                                    .CITY_STATUS_FACE_BOTTOM) * 0.5D,
                            S20CommandPresentationDirector.CITY_STATUS_Z),
                    CITY_TEXTURE_ID, minecraft, 38.0F, 12.5F,
                    180.0F, 0.0F, SCREEN_VISIBILITY[4]);
        }
    }

    /** Receives the server-sampled fleet telemetry for the tactical board. */
    public static void setPilotStatus(
            ClientboundPilotStatusPacket.Unit[] units,
            String phase, int depth, int targetDepth, int maximumDepth,
            float physicalRetractionFraction,
            String towerState, boolean towerStocked, int towerLiftPercent)
    {
        pilotStatus = units;
        armamentState = towerState == null ? "OFFLINE" : towerState;
        armamentStocked = towerStocked;
        armamentLiftPercent = Mth.clamp(towerLiftPercent, 0, 100);
        String safePhase = phase == null ? "UNKNOWN" : phase;
        int safeMaximum = Math.max(1, maximumDepth);
        float safePhysicalFraction = Float.isFinite(physicalRetractionFraction) && physicalRetractionFraction >= 0
                ? Mth.clamp(physicalRetractionFraction, 0, 1) : cityPhysicalRetractionFraction;
        if (!safePhase.equals(cityPhase) || cityDepth != depth
                || cityTargetDepth != targetDepth
                || cityMaximumDepth != safeMaximum
                || Float.compare(cityPhysicalRetractionFraction, safePhysicalFraction) != 0)
        {
            cityPhase = safePhase;
            cityDepth = Math.max(0, depth);
            cityTargetDepth = Math.max(0, targetDepth);
            cityMaximumDepth = safeMaximum;
            cityPhysicalRetractionFraction = safePhysicalFraction;
            cityTextureDirty = true;
        }
    }

    private static EvaFrameCodec.Encoded encodeJpeg(NativeImage image) throws IOException
    {
        int width = image.getWidth();
        int height = image.getHeight();
        int[] rgb = image.getPixelsRGBA();
        for (int i = 0; i < rgb.length; i++)
        {
            int abgr = rgb[i];
            rgb[i] = (abgr & 0xFF) << 16
                    | (abgr >> 8 & 0xFF) << 8
                    | abgr >> 16 & 0xFF;
        }
        BufferedImage buffered = new BufferedImage(
                width, height, BufferedImage.TYPE_INT_RGB);
        buffered.setRGB(0, 0, width, height, rgb, 0, width);

        return EvaFrameCodec.encode(buffered,
                Math.min(SeeleConfig.VIDEO_JPEG_QUALITY.get().floatValue(),compressionHint+.01F),
                SeeleConfig.VIDEO_FRAME_BUDGET_KIB.get()*1024);
    }

    /**
     * Draws pilot telemetry on the lower orange board.
     *
     * <p>The board used to be a static painted texture, so it never said
     * anything about the three pilots it exists to monitor.  Text is laid on
     * the same authored plane as the raster and collapses with it when the
     * operator switches the screen off.</p>
     */
    private static void renderPilotStatusBoard(
            PoseStack poseStack, Vec3 camera, Minecraft minecraft,
            float visibility)
    {
        float eased = visibility * visibility * (3.0F - 2.0F * visibility);
        if (eased <= 0.05F)
        {
            return;
        }
        poseStack.pushPose();
        poseStack.translate(
                S20CommandPresentationDirector.LOWER_SCREEN_X - camera.x,
                S20CommandPresentationDirector.LOWER_SCREEN_Y - camera.y,
                S20CommandPresentationDirector.LOWER_SCREEN_Z - camera.z);
        /*
         * The raster plane is built as yaw 180 then pitch.  Conjugating that
         * pair by the yaw leaves a single opposite X rotation, which lands the
         * glyphs on the same plane while keeping the transform right-handed:
         * mirroring it instead reverses the winding and the text render type
         * culls every quad away.
         */
        poseStack.mulPose(Axis.XP.rotationDegrees(-S20_LOWER_SCREEN_PITCH));
        poseStack.translate(0.0D, 0.0D, -0.03D);
        poseStack.scale(1.0F, eased, 1.0F);
        poseStack.scale(-TACTICAL_TEXT_SCALE, -TACTICAL_TEXT_SCALE,
                TACTICAL_TEXT_SCALE);

        MultiBufferSource.BufferSource buffers =
                minecraft.renderBuffers().bufferSource();
        Font font = minecraft.font;
        Matrix4f pose = poseStack.last().pose();
        int amber = 0xFFF6A020;
        int rule = 0xFF6B4418;
        int label = 0xFF9FB2BD;
        int value = 0xFFE6ECEF;
        int alert = 0xFFFF4C4C;

        int row = 0;
        row = line(font, pose, buffers, row,
                "NERV MAGI / PILOT STATUS", amber);
        row = line(font, pose, buffers, row,
                "===============================", rule);
        ClientboundPilotStatusPacket.Unit[] units = pilotStatus;
        for (int variant = 0; variant < 3; variant++)
        {
            ClientboundPilotStatusPacket.Unit unit =
                    units == null || variant >= units.length
                            ? null : units[variant];
            int[] tint = UNIT_COLOURS[variant];
            int unitColour = 0xFF000000 | tint[0] << 16
                    | tint[1] << 8 | tint[2];
            if (unit == null)
            {
                row = line(font, pose, buffers, row,
                        String.format(Locale.ROOT, "EVA-%02d  AWAITING MAGI LINK",
                                variant), unitColour);
                row++;
                continue;
            }
            row = line(font, pose, buffers, row, String.format(Locale.ROOT,
                    "EVA-%02d  %s", variant, unit.phase()), unitColour);
            if (!unit.present())
            {
                row = line(font, pose, buffers, row,
                        "  NO CANONICAL CHASSIS", alert);
                row = line(font, pose, buffers, row,
                        "-------------------------------", rule);
                continue;
            }
            row = line(font, pose, buffers, row, String.format(Locale.ROOT,
                    "  PILOT  %s", unit.pilot().isEmpty()
                            ? "NONE / DUMMY PLUG" : unit.pilot()),
                    unit.pilot().isEmpty() ? label : value);
            row = line(font, pose, buffers, row, String.format(Locale.ROOT,
                    "  SYNC   %5.1f%%   AT %4.0f/%4.0f",
                    unit.sync() * 100.0F, unit.atEnergy(),
                    unit.atCapacity()), value);
            row = line(font, pose, buffers, row, String.format(Locale.ROOT,
                    "  POWER  %s", powerLabel(unit)),
                    unit.externalPower() ? value : amber);
            row = line(font, pose, buffers, row, String.format(Locale.ROOT,
                    "  HULL   %4.0f / %4.0f   FEED %s",
                    unit.health(), unit.maxHealth(),
                    unit.liveFeed() ? "LIVE" : "STBY"), value);
            if (unit.berserk())
            {
                row = line(font, pose, buffers, row,
                        "  *** BERSERK - NO CONTROL ***", alert);
            }
            row = line(font, pose, buffers, row,
                    "-------------------------------", rule);
        }
        row = line(font, pose, buffers, row,
                "GEOFRONT COMMAND LINK   ONLINE", amber);
        row++;
        row = line(font, pose, buffers, row,
                String.format(Locale.ROOT,
                        "ARMAMENT TOWER  %-12s %3d%%",
                        armamentState, armamentLiftPercent), amber);
        line(font, pose, buffers, row,
                "PALLET RIFLE    "
                        + (armamentStocked ? "LOADED" : "ISSUED / EMPTY"),
                armamentStocked ? value : alert);
        buffers.endBatch();
        poseStack.popPose();
    }

    private static int line(Font font, Matrix4f pose,
                            MultiBufferSource.BufferSource buffers,
                            int row, String text, int colour)
    {
        font.drawInBatch(text, TACTICAL_LEFT,
                TACTICAL_TOP + row * TACTICAL_LINE_HEIGHT, colour, false,
                pose, buffers, Font.DisplayMode.POLYGON_OFFSET, 0,
                LightTexture.FULL_BRIGHT);
        return row + 1;
    }

    private static String powerLabel(ClientboundPilotStatusPacket.Unit unit)
    {
        if (unit.externalPower())
        {
            return "EXTERNAL UMBILICAL";
        }
        int seconds = Math.max(0, unit.powerTicks()) / 20;
        return String.format(Locale.ROOT, "INTERNAL %02d:%02d",
                seconds / 60, seconds % 60);
    }

    private static void ensureTacticalTexture(Minecraft minecraft)
    {
        if (tacticalTexture != null)
        {
            return;
        }
        NativeImage image = new NativeImage(192, 384, false);
        int background = rgba(4, 6, 8, 255);
        int amber = rgba(246, 150, 32, 255);
        int red = rgba(215, 45, 42, 255);
        int dim = rgba(70, 35, 20, 255);
        for (int y = 0; y < image.getHeight(); y++)
        {
            for (int x = 0; x < image.getWidth(); x++)
            {
                boolean grid = x % 24 == 0 || y % 24 == 0;
                image.setPixelRGBA(x, y, grid ? dim : background);
            }
        }
        fillRect(image, 0, 0, 192, 4, amber);
        fillRect(image, 0, 380, 192, 4, amber);
        fillRect(image, 0, 0, 4, 384, amber);
        fillRect(image, 188, 0, 4, 384, amber);
        /*
         * Backdrop only.  The former painted bars and tactical diamond sat
         * where the pilot rows are now drawn and read as data they were not:
         * three faint bands mark the unit blocks and nothing else claims to
         * mean anything.
         */
        fillRect(image, 14, 30, 164, 2, red);
        for (int unit = 0; unit < 3; unit++)
        {
            int top = 52 + unit * 104;
            fillRect(image, 14, top, 164, 1, dim);
            fillRect(image, 14, top + 96, 164, 1, dim);
        }
        fillRect(image, 14, 356, 164, 2, red);
        tacticalTexture = new DynamicTexture(image);
        minecraft.getTextureManager().register(
                TACTICAL_TEXTURE_ID, tacticalTexture);
    }

    /**
     * Animated cross-section of the armoured Tokyo-3 blocks retracting into
     * GeoFront.  The rear wall is intentionally a model, not another page of
     * status text: each server telemetry update moves the tower silhouettes
     * along their guide shafts toward the reported depth.
     */
    private static void ensureCityTexture(Minecraft minecraft)
    {
        if (cityTexture != null && !cityTextureDirty)
        {
            return;
        }
        NativeImage image = new NativeImage(
                CITY_TEXTURE_WIDTH, CITY_TEXTURE_HEIGHT, false);
        int background = rgba(2, 9, 15, 255);
        int grid = rgba(8, 39, 52, 255);
        int cyan = rgba(75, 229, 240, 255);
        int dimCyan = rgba(14, 79, 91, 255);
        int amber = rgba(249, 155, 28, 255);
        int red = rgba(223, 54, 48, 255);
        for (int y = 0; y < CITY_TEXTURE_HEIGHT; y++)
        {
            for (int x = 0; x < CITY_TEXTURE_WIDTH; x++)
            {
                boolean major = x % 64 == 0 || y % 64 == 0;
                boolean minor = x % 16 == 0 || y % 16 == 0;
                image.setPixelRGBA(x, y,
                        major ? dimCyan : minor ? grid : background);
            }
        }
        fillRect(image, 0, 0, CITY_TEXTURE_WIDTH, 4, amber);
        fillRect(image, 0, CITY_TEXTURE_HEIGHT - 4,
                CITY_TEXTURE_WIDTH, 4, amber);
        fillRect(image, 0, 0, 4, CITY_TEXTURE_HEIGHT, amber);
        fillRect(image, CITY_TEXTURE_WIDTH - 4, 0,
                4, CITY_TEXTURE_HEIGHT, amber);

        String title = "CITY RETRACTION MONITOR";
        int titleScale = 4;
        int titleWidth = title.length() * 6 * titleScale - titleScale;
        drawMonitorText(image, (CITY_TEXTURE_WIDTH - titleWidth) / 2,
                13, title, titleScale, amber);

        /*
         * Keep a dedicated header band.  At the former surfaceY=72 the
         * tallest 65-pixel tower started at y=12 and crossed the four-times
         * scale title at y=13.  The city now begins below y=64 while retaining
         * enough shaft travel to make retraction legible.
         */
        int surfaceY = 126;
        int chamberY = 222;
        fillRect(image, 24, surfaceY, CITY_TEXTURE_WIDTH - 48, 3, cyan);
        fillRect(image, 24, chamberY, CITY_TEXTURE_WIDTH - 48, 3, cyan);
        for (int shaftX = 48; shaftX < CITY_TEXTURE_WIDTH - 40;
             shaftX += 48)
        {
            fillRect(image, shaftX, surfaceY + 4, 1,
                    chamberY - surfaceY - 5, dimCyan);
            for (int y = surfaceY + 8; y < chamberY - 5; y += 12)
            {
                fillRect(image, shaftX - 2, y, 5, 2, dimCyan);
            }
        }

        float depthFraction = cityPhysicalRetractionFraction;
        float targetFraction = Math.min(1.0F,
                cityTargetDepth / (float) Math.max(1, cityMaximumDepth));
        int deckY = surfaceY + 5
                + Math.round(depthFraction * (chamberY - surfaceY - 25));
        int targetY = surfaceY + 5
                + Math.round(targetFraction * (chamberY - surfaceY - 25));
        fillRect(image, 28, targetY, CITY_TEXTURE_WIDTH - 56, 2, amber);

        int[] towerHeight = {28, 48, 34, 60, 40, 52, 30, 65, 38, 55,
                31, 46, 58, 36};
        int[] towerWidth = {25, 30, 22, 34, 26, 29, 23, 35, 24, 31,
                22, 28, 33, 25};
        for (int index = 0; index < towerHeight.length; index++)
        {
            int x = 38 + index * 49;
            int width = towerWidth[index];
            int height = towerHeight[index];
            int top = Math.max(64, deckY - height);
            height = deckY - top;
            drawCityTower(image, x, top, width, height, cyan, dimCyan,
                    background);
        }
        fillRect(image, 25, deckY, CITY_TEXTURE_WIDTH - 50, 5, cyan);
        fillRect(image, 25, deckY + 5, CITY_TEXTURE_WIDTH - 50, 3,
                dimCyan);
        int stateColour = cityPhase.contains("FAULT")
                || cityPhase.contains("ABORT") ? red : amber;
        fillRect(image, 28, 44, 150, 5, stateColour);
        fillRect(image, CITY_TEXTURE_WIDTH - 178, 44, 150, 5,
                stateColour);

        if (cityTexture == null)
        {
            cityTexture = new DynamicTexture(image);
            minecraft.getTextureManager().register(
                    CITY_TEXTURE_ID, cityTexture);
        }
        else
        {
            NativeImage previous = cityTexture.getPixels();
            cityTexture.setPixels(image);
            if (previous != null)
            {
                previous.close();
            }
            cityTexture.upload();
        }
        cityTextureDirty = false;
    }

    private static void drawCityTower(NativeImage image, int x, int y,
                                      int width, int height,
                                      int outline, int dim, int background)
    {
        fillRect(image, x + 3, y + 4, width, height, dim);
        fillRect(image, x, y, width, height, background);
        fillRect(image, x, y, width, 2, outline);
        fillRect(image, x, y, 2, height, outline);
        fillRect(image, x + width - 2, y, 2, height, outline);
        fillRect(image, x, y + height - 2, width, 2, outline);
        fillRect(image, x + 4, y + 5, width - 8, 2, dim);
        for (int floor = y + 12; floor < y + height - 4; floor += 9)
        {
            fillRect(image, x + 4, floor, width - 8, 1, dim);
        }
    }

    private static void drawMonitorText(NativeImage image, int x, int y,
                                        String text, int scale, int colour)
    {
        int cursor = x;
        for (int index = 0; index < text.length(); index++)
        {
            int[] rows = monitorGlyph(text.charAt(index));
            for (int row = 0; row < rows.length; row++)
            {
                for (int column = 0; column < 5; column++)
                {
                    if ((rows[row] & 1 << (4 - column)) != 0)
                    {
                        fillRect(image, cursor + column * scale,
                                y + row * scale, scale, scale, colour);
                    }
                }
            }
            cursor += 6 * scale;
        }
    }

    private static int[] monitorGlyph(char character)
    {
        return switch (character)
        {
            case 'A' -> new int[] {14, 17, 17, 31, 17, 17, 17};
            case 'C' -> new int[] {14, 17, 16, 16, 16, 17, 14};
            case 'E' -> new int[] {31, 16, 16, 30, 16, 16, 31};
            case 'I' -> new int[] {31, 4, 4, 4, 4, 4, 31};
            case 'M' -> new int[] {17, 27, 21, 21, 17, 17, 17};
            case 'N' -> new int[] {17, 25, 25, 21, 19, 19, 17};
            case 'O' -> new int[] {14, 17, 17, 17, 17, 17, 14};
            case 'R' -> new int[] {30, 17, 17, 30, 20, 18, 17};
            case 'T' -> new int[] {31, 4, 4, 4, 4, 4, 4};
            case 'Y' -> new int[] {17, 17, 10, 4, 4, 4, 4};
            default -> new int[] {0, 0, 0, 0, 0, 0, 0};
        };
    }

    private static void ensureStandbyTextures(Minecraft minecraft)
    {
        for (int variant = 0; variant < STANDBY_TEXTURES.length; variant++)
        {
            if (STANDBY_TEXTURES[variant] != null)
            {
                continue;
            }
            NativeImage image = new NativeImage(
                    ServerboundEvaVideoFramePacket.FRAME_WIDTH,
                    ServerboundEvaVideoFramePacket.FRAME_HEIGHT, false);
            paintStandby(image, variant);
            DynamicTexture texture = new DynamicTexture(image);
            STANDBY_TEXTURES[variant] = texture;
            minecraft.getTextureManager().register(
                    STANDBY_TEXTURE_IDS[variant], texture);
        }
    }

    private static void paintStandby(NativeImage image, int variant)
    {
        int width = image.getWidth();
        int height = image.getHeight();
        int[] colour = UNIT_COLOURS[variant];
        int accent = rgba(colour[0], colour[1], colour[2], 255);
        int dim = rgba(colour[0] / 4, colour[1] / 4, colour[2] / 4, 255);
        int background = rgba(5, 9, 12, 255);
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                boolean scan = y % 8 == 0;
                boolean grid = x % 20 == 0 || y % 20 == 0;
                image.setPixelRGBA(x, y, scan || grid ? dim : background);
            }
        }
        fillRect(image, 0, 0, width, 3, accent);
        fillRect(image, 0, height - 3, width, 3, accent);
        fillRect(image, 0, 0, 3, height, accent);
        fillRect(image, width - 3, 0, 3, height, accent);
        fillRect(image, 8, 8, 36, 4, accent);
        fillRect(image, width - 44, 8, 36, 4, accent);
        drawDigit(image, 58, 27, 0, accent);
        drawDigit(image, 82, 27, variant, accent);
        for (int bar = 0; bar < 7; bar++)
        {
            fillRect(image, 24 + bar * 17, 72, 11, 3,
                    bar < 2 ? accent : dim);
        }
    }

    private static void drawDigit(NativeImage image, int x, int y,
                                  int digit, int colour)
    {
        int mask = switch (digit)
        {
            case 1 -> 0b0000110;
            case 2 -> 0b1011011;
            default -> 0b0111111;
        };
        if ((mask & 0b0000001) != 0)
        {
            fillRect(image, x + 3, y, 13, 3, colour);
        }
        if ((mask & 0b0000010) != 0)
        {
            fillRect(image, x + 16, y + 3, 3, 12, colour);
        }
        if ((mask & 0b0000100) != 0)
        {
            fillRect(image, x + 16, y + 18, 3, 12, colour);
        }
        if ((mask & 0b0001000) != 0)
        {
            fillRect(image, x + 3, y + 30, 13, 3, colour);
        }
        if ((mask & 0b0010000) != 0)
        {
            fillRect(image, x, y + 18, 3, 12, colour);
        }
        if ((mask & 0b0100000) != 0)
        {
            fillRect(image, x, y + 3, 3, 12, colour);
        }
        if ((mask & 0b1000000) != 0)
        {
            fillRect(image, x + 3, y + 15, 13, 3, colour);
        }
    }

    private static void fillRect(NativeImage image, int x, int y,
                                 int width, int height, int colour)
    {
        for (int py = y; py < y + height; py++)
        {
            for (int px = x; px < x + width; px++)
            {
                image.setPixelRGBA(px, py, colour);
            }
        }
    }

    private static int rgba(int red, int green, int blue, int alpha)
    {
        return alpha << 24 | blue << 16 | green << 8 | red;
    }

    private static void renderScreen(PoseStack poseStack, Vec3 camera,
                                     Vec3 centre,
                                     ResourceLocation texture,
                                     Minecraft minecraft,
                                     float width, float height,
                                     float yaw, float pitch,
                                     float visibility)
    {
        float eased = visibility * visibility
                * (3.0F - 2.0F * visibility);
        if (eased <= 0.003F)
        {
            return;
        }
        poseStack.pushPose();
        poseStack.translate(centre.x - camera.x,
                centre.y - camera.y, centre.z - camera.z);
        poseStack.mulPose(Axis.YP.rotationDegrees(yaw));
        poseStack.mulPose(Axis.XP.rotationDegrees(pitch));
        // NERV-style power-on/off: luminance fades while the raster opens or
        // collapses vertically from its centre over roughly 0.4 seconds.
        poseStack.scale(1.0F, Math.max(0.015F, eased), 1.0F);
        MultiBufferSource.BufferSource buffers =
                minecraft.renderBuffers().bufferSource();
        RenderType renderType = RenderType.entityTranslucent(texture);
        VertexConsumer consumer = buffers.getBuffer(renderType);
        Matrix4f pose = poseStack.last().pose();
        Matrix3f normal = poseStack.last().normal();
        float halfWidth = width * 0.5F;
        float halfHeight = height * 0.5F;
        vertex(consumer, pose, normal,
                -halfWidth, -halfHeight, 0.0F, 0.0F, 1.0F, eased);
        vertex(consumer, pose, normal,
                halfWidth, -halfHeight, 0.0F, 1.0F, 1.0F, eased);
        vertex(consumer, pose, normal,
                halfWidth, halfHeight, 0.0F, 1.0F, 0.0F, eased);
        vertex(consumer, pose, normal,
                -halfWidth, halfHeight, 0.0F, 0.0F, 0.0F, eased);
        // The measured S20 masks are viewed both directly and through the
        // command glazing.  Emit the reverse winding as well: relying on one
        // guessed normal made every raster disappear when the camera crossed
        // the authored plane, even though the physical display was present.
        vertex(consumer, pose, normal,
                -halfWidth, halfHeight, -0.002F, 0.0F, 0.0F, eased, -1.0F);
        vertex(consumer, pose, normal,
                halfWidth, halfHeight, -0.002F, 1.0F, 0.0F, eased, -1.0F);
        vertex(consumer, pose, normal,
                halfWidth, -halfHeight, -0.002F, 1.0F, 1.0F, eased, -1.0F);
        vertex(consumer, pose, normal,
                -halfWidth, -halfHeight, -0.002F, 0.0F, 1.0F, eased, -1.0F);
        buffers.endBatch(renderType);
        poseStack.popPose();
    }

    private static void vertex(VertexConsumer consumer, Matrix4f pose,
                               Matrix3f normal, float x, float y, float z,
                               float u, float v, float alpha)
    {
        vertex(consumer, pose, normal, x, y, z, u, v, alpha, 1.0F);
    }

    private static void vertex(VertexConsumer consumer, Matrix4f pose,
                               Matrix3f normal, float x, float y, float z,
                               float u, float v, float alpha, float normalZ)
    {
        consumer.vertex(pose, x, y, z)
                .color(255, 255, 255,
                        Math.max(0, Math.min(255,
                                Math.round(alpha * 255.0F))))
                .uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(LightTexture.FULL_BRIGHT)
                .normal(normal, 0.0F, 0.0F, normalZ)
                .endVertex();
    }
}
