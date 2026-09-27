package com.projectseele.client;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.ArrayList;
import com.google.gson.JsonParser;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/**
 * Local image plates used by the command room and commander's office.
 *
 * <p>The image is read from the game directory rather than the mod jar, so the
 * plate can be replaced without a rebuild and no third-party artwork is
 * committed to this repository.  Drop the file at
 * {@code projectseele-local-maps/tree_of_life.png} and
 * {@code projectseele-local-maps/nerv_logo.png}; if either is absent only that
 * plate is omitted and its authored wall remains visible.</p>
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class TreeOfLifeWallClient
{
    private static final Path TREE_SOURCE = Paths.get(
            "projectseele-local-maps", "tree_of_life.png");
    private static final Path NERV_SOURCE = Paths.get(
            "projectseele-local-maps", "nerv_logo.png");
    private static final Path NERV_REFINED = Paths.get("projectseele-local-maps", "nerv_logo_r04.png");
    private static List<Plate> r04Plates;
    private static final ResourceLocation TREE_TEXTURE_ID = new ResourceLocation(
            ProjectSeele.MODID, "dynamic/tree_of_life_wall");
    private static final ResourceLocation NERV_TEXTURE_ID = new ResourceLocation(
            ProjectSeele.MODID, "dynamic/nerv_logo_wall");

    /* Both plates reuse the user-local image; no third-party scan is packed in
     * the jar.  The command plate faces +Z.  The upper-pyramid office plate
     * sits just north of its south feature wall and faces -Z into the room. */
    private static final List<Plate> TREE_PLATES = List.of(
            new Plate(new Vec3(20.5D, -414.5D, 257.98D),
                    10.0F, 9.0F, 0.0F),
            // Seen from the north side of the south wall. The authored white
            // Blocks x=20..40 occupy [20,41], whose physical centre is 30.5.
            new Plate(new Vec3(30.5D, -322.0D, 339.98D),
                    12.0F, 10.0F, 180.0F));
    private static final List<Plate> NERV_PLATES = List.of(
            // Block z=311 occupies [311,312]; the office is on its south
            // side, so the image must sit beyond z=312 rather than inside it.
            new Plate(new Vec3(30.5D, -322.0D, 312.01D),
                    11.0F, 15.0F, 0.0F),
            // Main command dais: centred on the five-wide black feature wall
            // at z=272 and facing south toward the commander's seat.
            new Plate(new Vec3(28.5D, -402.0D, 273.01D),
                    4.5F, 5.0F, 0.0F));
    private static float treeImageAspect = 0.75F;
    private static float nervImageAspect = 1.0F;
    private static final double RANGE_SQR = 96.0D * 96.0D;

    private static DynamicTexture treeTexture;
    private static DynamicTexture nervTexture;
    private static boolean treeSourceChecked;
    private static boolean nervSourceChecked;

    private TreeOfLifeWallClient() {}

    @SubscribeEvent
    public static void onRenderLevel(RenderLevelStageEvent event)
    {
        // Kept solely to reproduce the old shader/depth bug in an isolated
        // review. Production images are mounted, culled block entities.
        if(!Boolean.getBoolean("projectseele.legacyWallArtReview"))return;
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS)
        {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level == null || minecraft.player == null
                || !minecraft.level.dimension().equals(
                        FacilitySchemaV2.DIMENSION))
        {
            return;
        }
        Vec3 camera = event.getCamera().getPosition();
        PoseStack poseStack = event.getPoseStack();
        MultiBufferSource.BufferSource buffers =
                minecraft.renderBuffers().bufferSource();
        if (ensureTreeTexture(minecraft))
        {
            renderPlates(minecraft, poseStack, buffers, camera,
                    TREE_TEXTURE_ID, TREE_PLATES, treeImageAspect);
        }
        if (ensureNervTexture(minecraft))
        {
            renderPlates(minecraft, poseStack, buffers, camera,
                    NERV_TEXTURE_ID, NERV_PLATES, nervImageAspect);
            if (minecraft.getSingleplayerServer() != null && minecraft.getSingleplayerServer()
                    .getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).normalize()
                    .getFileName().toString().equals("SEELE_TV_WORLD_PREVIEW_20260906"))
                renderPlates(minecraft, poseStack, buffers, camera, NERV_TEXTURE_ID, refinedPlates(), nervImageAspect);
        }
    }

    private static void renderPlates(
            Minecraft minecraft, PoseStack poseStack,
            MultiBufferSource.BufferSource buffers, Vec3 camera,
            ResourceLocation textureId, List<Plate> plates, float aspect)
    {
        RenderType renderType = RenderType.entityTranslucent(textureId);
        VertexConsumer consumer = buffers.getBuffer(renderType);
        boolean rendered = false;
        for (Plate plate : plates)
        {
            if (minecraft.player.position().distanceToSqr(plate.centre())
                    > RANGE_SQR)
            {
                continue;
            }
            poseStack.pushPose();
            poseStack.translate(plate.centre().x - camera.x,
                    plate.centre().y - camera.y,
                    plate.centre().z - camera.z);
            poseStack.mulPose(Axis.YP.rotationDegrees(plate.yaw()));
            Matrix4f pose = poseStack.last().pose();
            Matrix3f normal = poseStack.last().normal();
            float halfWidth = Math.min(plate.maxWidth(),
                    plate.height() * aspect) * 0.5F;
            float halfHeight = plate.height() * 0.5F;
            // Wound toward +Z before the per-plate yaw is applied.
            // World-facing plates are viewed from opposite sides after yaw;
            // U must follow local X or both supplied images appear mirrored.
            vertex(consumer, pose, normal, halfWidth, -halfHeight,
                    0.0F, 1.0F, 1.0F);
            vertex(consumer, pose, normal, -halfWidth, -halfHeight,
                    0.0F, 0.0F, 1.0F);
            vertex(consumer, pose, normal, -halfWidth, halfHeight,
                    0.0F, 0.0F, 0.0F);
            vertex(consumer, pose, normal, halfWidth, halfHeight,
                    0.0F, 1.0F, 0.0F);
            poseStack.popPose();
            rendered = true;
        }
        if (!rendered)
        {
            return;
        }
        buffers.endBatch(renderType);
    }

    private static List<Plate> refinedPlates()
    {
        if (r04Plates != null) return r04Plates;
        r04Plates = new ArrayList<>();
        Path path = Paths.get("projectseele-local-maps", "r04_wall_plates.json");
        if (!Files.isRegularFile(path)) return r04Plates;
        try (var reader = Files.newBufferedReader(path))
        {
            for (var row : JsonParser.parseReader(reader).getAsJsonArray())
            {
                var d = row.getAsJsonObject(); var p = d.getAsJsonArray("position");
                r04Plates.add(new Plate(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),
                        d.get("size").getAsFloat(),d.get("size").getAsFloat(),d.get("yaw").getAsFloat()));
            }
        }
        catch (Exception error) { ProjectSeele.LOGGER.warn("R04 wall plaques unavailable", error); }
        return r04Plates;
    }

    private static boolean ensureTreeTexture(Minecraft minecraft)
    {
        if (treeTexture != null)
        {
            return true;
        }
        if (treeSourceChecked)
        {
            return false;
        }
        treeSourceChecked = true;
        if (!Files.isRegularFile(TREE_SOURCE))
        {
            ProjectSeele.LOGGER.info(
                    "Tree-of-life wall idle: no image at {}", TREE_SOURCE);
            return false;
        }
        try (InputStream stream = Files.newInputStream(TREE_SOURCE))
        {
            NativeImage image = NativeImage.read(stream);
            // Derive the plate from the image rather than stretching the
            // image to a guessed plate: a different scan can be dropped in
            // later without it going oval.
            treeImageAspect = image.getWidth() / (float) image.getHeight();
            treeTexture = new DynamicTexture(image);
            minecraft.getTextureManager().register(
                    TREE_TEXTURE_ID, treeTexture);
            ProjectSeele.LOGGER.info(
                    "Tree-of-life walls loaded {}x{} from {}; plates={}",
                    image.getWidth(), image.getHeight(), TREE_SOURCE,
                    TREE_PLATES.size());
            return true;
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error(
                    "Tree-of-life wall image unreadable", exception);
            return false;
        }
    }

    private static boolean ensureNervTexture(Minecraft minecraft)
    {
        if (nervTexture != null)
        {
            return true;
        }
        if (nervSourceChecked)
        {
            return false;
        }
        nervSourceChecked = true;
        if (!Files.isRegularFile(NERV_SOURCE))
        {
            ProjectSeele.LOGGER.info(
                    "NERV office wall idle: no image at {}", NERV_SOURCE);
            return false;
        }
        try (InputStream stream = Files.newInputStream(Files.isRegularFile(NERV_REFINED) ? NERV_REFINED : NERV_SOURCE))
        {
            NativeImage image = NativeImage.read(stream);
            removeBakedCheckerboard(image);
            nervImageAspect = image.getWidth() / (float) image.getHeight();
            nervTexture = new DynamicTexture(image);
            minecraft.getTextureManager().register(
                    NERV_TEXTURE_ID, nervTexture);
            ProjectSeele.LOGGER.info(
                    "NERV office wall loaded {}x{} from {}",
                    image.getWidth(), image.getHeight(), NERV_SOURCE);
            return true;
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error(
                    "NERV office wall image unreadable", exception);
            return false;
        }
    }

    /** Shared local-only logo texture for moving NERV machinery. */
    public static ResourceLocation nervLogoTexture(Minecraft minecraft)
    {
        return ensureNervTexture(minecraft) ? NERV_TEXTURE_ID : null;
    }
    public static ResourceLocation artworkTexture(String artwork)
    {
        Minecraft mc=Minecraft.getInstance();
        return artwork.equals("tree")?(ensureTreeTexture(mc)?TREE_TEXTURE_ID:null):nervLogoTexture(mc);
    }
    public static float artworkAspect(String artwork)
    {return artwork.equals("tree")?treeImageAspect:nervImageAspect;}

    /**
     * The supplied logo has a light checkerboard baked into its RGB pixels.
     * Remove only nearly neutral light pixels at load time, preserving the
     * original red artwork and its antialiased edge over the black wall.
     */
    private static void removeBakedCheckerboard(NativeImage image)
    {
        for (int y = 0; y < image.getHeight(); y++)
        {
            for (int x = 0; x < image.getWidth(); x++)
            {
                int pixel = image.getPixelRGBA(x, y);
                // NativeImage#getPixelRGBA uses native ABGR ordering.
                int red = pixel & 0xFF;
                int green = pixel >> 8 & 0xFF;
                int blue = pixel >> 16 & 0xFF;
                int brightest = Math.max(red, Math.max(green, blue));
                int darkest = Math.min(red, Math.min(green, blue));
                if (brightest >= 180 && brightest - darkest <= 48)
                {
                    image.setPixelRGBA(x, y, 0);
                }
            }
        }
    }

    /** Forces a re-read after the file on disk has been replaced. */
    public static void reload()
    {
        if (treeTexture != null)
        {
            Minecraft.getInstance().getTextureManager().release(
                    TREE_TEXTURE_ID);
            treeTexture.close();
            treeTexture = null;
        }
        if (nervTexture != null)
        {
            Minecraft.getInstance().getTextureManager().release(
                    NERV_TEXTURE_ID);
            nervTexture.close();
            nervTexture = null;
        }
        treeSourceChecked = false;
        nervSourceChecked = false;
    }

    private static void vertex(VertexConsumer consumer, Matrix4f pose,
                               Matrix3f normal, float x, float y, float z,
                               float u, float v)
    {
        consumer.vertex(pose, x, y, z)
                .color(255, 255, 255, 255)
                .uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(LightTexture.FULL_BRIGHT)
                .normal(normal, 0.0F, 0.0F, 1.0F)
                .endVertex();
    }

    private record Plate(Vec3 centre, float height, float maxWidth, float yaw)
    {
    }
}
