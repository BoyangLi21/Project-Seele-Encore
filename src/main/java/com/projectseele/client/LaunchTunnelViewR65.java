package com.projectseele.client;

import com.mojang.blaze3d.shaders.FogShape;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.network.ClientboundLaunchRideR65;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.util.Mth;
import net.minecraft.world.level.material.FogType;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class LaunchTunnelViewR65
{
    private static ClientLevel level;
    private static ClientboundLaunchRideR65 ride;
    private static EvaUnit01Entity carrier;
    private static long epoch;
    private static long receivedSequence;

    public static void receive(ClientboundLaunchRideR65 packet)
    {
        var mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null) return;
        var eva = EvaPilotResolver.controlTarget(mc.player);
        if (eva == null || eva.getId() != packet.eva() || !EvaMechanicalFrameR52.active(eva)) return;
        level = mc.level;
        ride = packet;
        carrier = eva;
        epoch = EvaMechanicalFrameR52.epoch(eva);
        receivedSequence = EvaMechanicalFrameR52.continuousSequenceR52(eva);
    }

    @SubscribeEvent
    public static void logout(net.minecraftforge.client.event.ClientPlayerNetworkEvent.LoggingOut event)
    {
        ride = null;
        level = null;
        carrier = null;
    }

    private static float strength(Camera camera, float partial)
    {
        var mc = Minecraft.getInstance();
        if (ride == null || level != mc.level || mc.player == null || mc.getCameraEntity() != mc.player
                || camera.getFluidInCamera() != FogType.NONE) return 0;
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        if (eva == null || eva != carrier || EvaMechanicalFrameR52.epoch(eva) != epoch
                || !EvaMechanicalFrameR52.continuousWindowR52(eva)
                || EvaMechanicalFrameR52.detachedCarrierR52(eva)) return 0;
        // A stalled server freezes the vehicle in the shaft. Only accepted movement
        // samples can age its shutter packet while the client keeps drawing frames.
        long steps = EvaMechanicalFrameR52.continuousSequenceR52(eva) - receivedSequence;
        if (steps < 0) return 0;
        double age = steps + Mth.clamp(partial, 0, 1);
        double inside = (ride.exitY() - camera.getPosition().y) / 32;
        return (float)Mth.clamp(Math.min(inside, (14 - age) / 6), 0, 1);
    }

    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void fog(ViewportEvent.RenderFog event)
    {
        float weight = strength(event.getCamera(), (float)event.getPartialTick());
        if (weight <= 0) return;
        event.setNearPlaneDistance(Mth.lerp(weight, event.getNearPlaneDistance(), 27));
        event.setFarPlaneDistance(Mth.lerp(weight, event.getFarPlaneDistance(), 72));
        event.setFogShape(FogShape.SPHERE);
        event.setCanceled(true);
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void color(ViewportEvent.ComputeFogColor event)
    {
        float weight = strength(event.getCamera(), (float)event.getPartialTick());
        if (weight <= 0) return;
        event.setRed(Mth.lerp(weight, event.getRed(), .030F));
        event.setGreen(Mth.lerp(weight, event.getGreen(), .041F));
        event.setBlue(Mth.lerp(weight, event.getBlue(), .052F));
    }

    @SubscribeEvent
    public static void tunnel(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_LEVEL) return;
        float weight = strength(event.getCamera(), event.getPartialTick());
        if (weight <= 0) return;

        var pose = event.getPoseStack().last().pose();
        var eye = event.getCamera().getPosition();
        var tess = Tesselator.getInstance();
        var builder = tess.getBuilder();
        var oldShader = RenderSystem.getShader();
        RenderSystem.enableDepthTest();
        RenderSystem.disableCull();
        RenderSystem.setShader(GameRenderer::getPositionColorShader);
        try
        {
            if (!ride.shutters().isEmpty())
            {
                RenderSystem.depthMask(true);
                builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
                for (var gate : ride.shutters()) shutter(builder, pose, eye, gate);
                tess.end();
            }
            // Shader packs can supply their own sky/terrain fog. Depth-tested shells
            // also cover empty pixels and DH without copying or sampling a depth texture.
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.depthMask(false);
            builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
            for (int i = 5; i >= 1; i--)
            {
                float radius = 20 + 10 * i;
                int alpha = Math.round(255 * weight / (6 - i));
                shell(builder, pose, radius, alpha);
            }
            tess.end();
        }
        finally
        {
            RenderSystem.depthMask(true);
            RenderSystem.disableBlend();
            RenderSystem.enableCull();
            RenderSystem.setShader(() -> oldShader);
        }
    }

    private static void shell(BufferBuilder b, Matrix4f m, float r, int alpha)
    {
        // Cube faces meet edge-to-edge. The last face in depth is fully opaque.
        for (int axis = 0; axis < 3; axis++)
            for (int sign = -1; sign <= 1; sign += 2)
                for (int i = 0; i < 4; i++)
                {
                    float u = i == 0 || i == 3 ? -r : r, v = i < 2 ? -r : r;
                    b.vertex(m, axis == 0 ? sign*r : u, axis == 1 ? sign*r : axis == 0 ? u : v,
                            axis == 2 ? sign*r : v).color(8, 11, 14, alpha).endVertex();
                }
    }

    private static void shutter(BufferBuilder b, Matrix4f m, Vec3 eye, ClientboundLaunchRideR65.Shutter gate)
    {
        Vec3 n = gate.tangent();
        Vec3 right = new Vec3(-n.z, 0, n.x).normalize();
        Vec3 up = right.cross(n);
        // The upright body travels feet-first along the surveyed foot datum, with
        // the optical port high above it even where the track is nearly horizontal.
        Vec3 center = gate.foot().add(0, 28, 0).subtract(eye);
        double ahead = center.dot(n);
        if (ahead <= 22) return;
        double opening = Mth.clamp((72 - ahead) / 50, 0, 1);
        opening = opening * opening * (3 - 2 * opening);
        for (int side = -1; side <= 1; side += 2)
        {
            double edge = side * opening * 18, rim = side * 18;
            if (Math.abs(edge-rim) < .02) continue;
            panel(b, m, center, right, up, edge, rim, -32, 32, 41, 48, 53);
            var face = center.subtract(n.scale(.06));
            for (int y = -24; y <= 24; y += 8)
                panel(b, m, face, right, up, edge, rim, y, y+.28, 20, 25, 31);
            panel(b, m, face, right, up, edge, Mth.lerp(.075,edge,rim), -32, 32, 130, 85, 37);
        }
    }

    private static void panel(BufferBuilder b, Matrix4f m, Vec3 center, Vec3 right, Vec3 up,
            double a, double z, double bottom, double top, int r, int g, int blue)
    {
        for (int i = 0; i < 4; i++)
        {
            double x = i == 0 || i == 3 ? a : z, y = i < 2 ? bottom : top;
            b.vertex(m, (float)(center.x+right.x*x+up.x*y), (float)(center.y+up.y*y),
                    (float)(center.z+right.z*x+up.z*y)).color(r,g,blue,255).endVertex();
        }
    }

    private LaunchTunnelViewR65() {}
}
