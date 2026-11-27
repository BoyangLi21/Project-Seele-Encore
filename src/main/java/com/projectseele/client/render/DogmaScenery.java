package com.projectseele.client.render;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.GZIPInputStream;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManagerReloadListener;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterClientReloadListenersEvent;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/** Surveyed scenery. Opaque geometry writes depth before the lake and LCL translucent passes. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class DogmaScenery
{
    private static final ResourceLocation MODEL = new ResourceLocation(ProjectSeele.MODID, "geofront/survey_sculptures.bin.gz");
    private static final List<Piece> PIECES = new ArrayList<>();
    private static boolean attempted;
    private static boolean shaderLighting;
    private static java.lang.ref.WeakReference<net.minecraft.client.multiplayer.ClientLevel> lastLevel = new java.lang.ref.WeakReference<>(null);
    private static boolean surveyedWorld;

    private record Piece(VertexBuffer buffer, AABB bounds, int x, int y, int z) {}

    private static void clear()
    {
        for (Piece piece : PIECES) piece.buffer.close();
        PIECES.clear();
        attempted = false;
    }

    @Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
    public static final class Reload
    {
        @SubscribeEvent
        public static void register(RegisterClientReloadListenersEvent event)
        {
            event.registerReloadListener((ResourceManagerReloadListener) manager ->
                RenderSystem.recordRenderCall(DogmaScenery::clear));
        }
    }

    private static int[] channelTable(boolean underground)
    {
        int[] table = new int[256];
        for (int i = 0; i < table.length; i++)
        {
            // The shader composite receives linear radiance. An sRGB swatch submitted directly
            // is tone-mapped a second time, losing the creases of the face and mirror frame.
            double srgb = i / 255.0;
            double linear = srgb <= .04045 ? srgb / 12.92 : Math.pow((srgb + .055) / 1.055, 2.4);
            table[i] = shaderLighting ? (int)Math.round(255 * linear * (underground ? .38 : .55)) : i;
        }
        return table;
    }

    private static void load()
    {
        var resource = Minecraft.getInstance().getResourceManager().getResource(MODEL);
        attempted = true;
        if (resource.isEmpty()) return;
        try (var input = new DataInputStream(new BufferedInputStream(new GZIPInputStream(resource.get().open()))))
        {
            if (input.readInt() != 0x45564131) throw new IOException("Invalid scenery header");
            int pieces = input.readUnsignedShort();
            if (pieces > 64) throw new IOException("Too many survey pieces");
            for (int p = 0; p < pieces; p++)
            {
                int x = input.readInt(), y = input.readInt(), z = input.readInt();
                AABB bounds = new AABB(input.readFloat(), input.readFloat(), input.readFloat(),
                        input.readFloat(), input.readFloat(), input.readFloat()).move(x, y, z);
                int count = input.readInt(), indices = input.readInt();
                if (count <= 0 || count > 350000 || indices <= 0 || indices > 1500000 || indices % 3 != 0)
                    throw new IOException("Invalid survey piece size");
                int[] lut = channelTable(y < 0);
                float[] positions = new float[count * 3];
                int[] colours = new int[count];
                for (int v = 0; v < count; v++)
                {
                    for (int axis = 0; axis < 3; axis++) positions[3 * v + axis] = input.readFloat();
                    colours[v] = input.readInt();
                }
                BufferBuilder builder = new BufferBuilder(16 * indices);
                builder.begin(VertexFormat.Mode.TRIANGLES, DefaultVertexFormat.POSITION_COLOR);
                for (int n = 0; n < indices; n++)
                {
                    int v = input.readInt();
                    if (v < 0 || v >= count) throw new IOException("Invalid survey index");
                    int c = colours[v];
                    builder.vertex(positions[v * 3], positions[v * 3 + 1], positions[v * 3 + 2])
                            .color(lut[(c >> 16) & 255], lut[(c >> 8) & 255], lut[c & 255], 255).endVertex();
                }
                var buffer = new VertexBuffer(VertexBuffer.Usage.STATIC);
                buffer.bind();
                buffer.upload(builder.end());
                VertexBuffer.unbind();
                PIECES.add(new Piece(buffer, bounds, x, y, z));
            }
            if (input.read() != -1) throw new IOException("Trailing scenery data");
        }
        catch (Exception e)
        {
            clear();
            attempted = true;
            ProjectSeele.LOGGER.error("Unable to load GeoFront survey sculptures", e);
        }
    }

    @SubscribeEvent
    public static void render(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_CUTOUT_BLOCKS || ShaderShadowPassR44.active()) return;
        var mc = Minecraft.getInstance();
        if (mc.level == null || !mc.level.dimension().equals(FacilitySchemaV2.DIMENSION)) return;
        if (lastLevel.get() != mc.level)
        {
            lastLevel = new java.lang.ref.WeakReference<>(mc.level);
            var server = mc.getSingleplayerServer();
            surveyedWorld = server == null || java.nio.file.Files.isRegularFile(server.getWorldPath(
                    net.minecraft.world.level.storage.LevelResource.ROOT).resolve("r52/survey_scenery.json"));
        }
        if (!surveyedWorld) return;
        var camera = event.getCamera().getPosition();
        // These installations occupy two separated elevations of the private survey world.
        if (Math.abs(camera.y + 1237) > 110 && Math.abs(camera.y - 120) > 480) return;
        boolean shaders = ShaderShadowPassR44.enabled();
        if (shaderLighting != shaders)
        {
            clear();
            shaderLighting = shaders;
        }
        if (!attempted) load();
        var state = RenderType.debugQuads();
        boolean started = false;
        for (Piece piece : PIECES)
        {
            if (piece.bounds.distanceToSqr(camera) > 1024.0 * 1024.0 || !event.getFrustum().isVisible(piece.bounds)) continue;
            if (!started)
            {
                state.setupRenderState();
                RenderSystem.enableDepthTest();
                RenderSystem.depthMask(true);
                RenderSystem.disableCull();
                RenderSystem.disableBlend();
                started = true;
            }
            float light = piece.y > 0 ? .32F + .68F * (1F - mc.level.getSkyDarken() / 15F) : 1F;
            RenderSystem.setShaderColor(light, light, light, 1);
            Matrix4f view = new Matrix4f(event.getPoseStack().last().pose())
                    .translate((float)(piece.x - camera.x), (float)(piece.y - camera.y), (float)(piece.z - camera.z));
            piece.buffer.bind();
            piece.buffer.drawWithShader(view, event.getProjectionMatrix(), GameRenderer.getPositionColorShader());
        }
        if (started)
        {
            VertexBuffer.unbind();
            RenderSystem.setShaderColor(1, 1, 1, 1);
            RenderSystem.enableCull();
            state.clearRenderState();
        }
    }
}
