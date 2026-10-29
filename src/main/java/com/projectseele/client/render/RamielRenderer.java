package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.RamielEntity;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.AABB;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * Renders the selected source model, with the built-in octahedron as fallback.
 * Charge light, core exposure and the beam use the existing entity-synced state.
 */
public class RamielRenderer extends EntityRenderer<RamielEntity>
{
    private static final ResourceLocation TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/ramiel.png");

    // Beam palette: white-hot core sheathed in violet-pink, matching the charge dust.
    private static final float[] BEAM_CORE_RGB = {1.0F, 0.98F, 0.96F};
    private static final float[] BEAM_HALO_RGB = {0.95F, 0.45F, 0.90F};
    private static final float[] RAY_RGB = {1.0F, 0.35F, 0.50F};

    public RamielRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public boolean shouldRender(RamielEntity entity, Frustum frustum,
                                double cameraX, double cameraY, double cameraZ)
    {
        if (!entity.shouldRender(cameraX, cameraY, cameraZ)) return false;
        // The supplied expanded form reaches 15.462 model units from its core.
        double radius = 16 * entity.modelScaleR52();
        double y = entity.getY() + entity.getBbHeight() * .5;
        var bounds=new AABB(entity.getX() - radius, y - radius, entity.getZ() - radius,
                entity.getX() + radius, y + radius, entity.getZ() + radius);
        if(entity.getBeamTicks()>0)bounds=bounds.minmax(new AABB(entity.getPosition(1),entity.getBeamEnd()).inflate(10));
        return frustum.isVisible(bounds);
    }

    @Override
    public void render(RamielEntity entity, float entityYaw, float partialTick, PoseStack poseStack,
                       MultiBufferSource buffer, int packedLight)
    {
        float coreHeight = entity.getBbHeight() * 0.5F;
        float beamTicks = entity.getBeamTicks() - partialTick;
        // 1 while the beam is solid, easing to 0 across the afterglow window.
        float beamGlow = beamTicks <= 0.0F ? 0.0F
                : Mth.clamp(beamTicks / (RamielEntity.BEAM_RENDER_TICKS - RamielEntity.BEAM_SOLID_TICKS), 0.0F, 1.0F);

        if (beamTicks > 0.0F)
        {
            renderBeam(entity, partialTick, beamTicks, poseStack, buffer, coreHeight);
        }

        if (entity.isDrilling() && entity.getDrillDepth() > 0.1F)
        {
            renderDrill(entity, partialTick, poseStack, buffer, coreHeight);
        }

        // ----- crystal body (spins around Y) -----
        poseStack.pushPose();
        poseStack.translate(0.0D, coreHeight, 0.0D);
        poseStack.scale(entity.modelScaleR52(),entity.modelScaleR52(),entity.modelScaleR52());
        poseStack.mulPose(Axis.YP.rotationDegrees(entity.getSpin(partialTick)));

        int fullBright = LightTexture.FULL_BRIGHT;
        float time = entity.tickCount + partialTick;

        // Shell halves part vertically to bare the core (the sniping window).
        float expose = entity.getExposeProgress(partialTick);
        float halfGap = 3.75F * expose;

        if (!RamielSourceModelR53.draw(poseStack, buffer, expose, time, entity.isCharging(), packedLight))
        {
            VertexConsumer body = buffer.getBuffer(RenderType.entityTranslucent(TEXTURE));
            float corePulse = entity.isCharging()
                    ? 1.1F + 0.3F * Mth.sin(time * 0.5F)
                    : 0.95F;
            corePulse *= 1.0F + 0.16F * expose * Mth.sin(time * 0.9F);
            float coreSize = (2.6F + 1.4F * expose) * corePulse;
            drawOctahedron(poseStack, body, coreSize,
                    1.0F, 0.12F + 0.45F * expose, 0.18F + 0.28F * expose, 1.0F, fullBright);

            // Shell flashes toward white while the beam is live.
            float shellR = Mth.lerp(beamGlow, 0.45F, 1.0F);
            float shellG = Mth.lerp(beamGlow, 0.72F, 0.95F);
            float shellB = 1.0F;

            poseStack.pushPose();
            poseStack.translate(0.0D, halfGap, 0.0D);
            drawOctahedronFaces(poseStack, body, 8.25F, 0, 4, shellR, shellG, shellB, 0.7F, fullBright);
            poseStack.popPose();

            poseStack.pushPose();
            poseStack.translate(0.0D, -halfGap, 0.0D);
            drawOctahedronFaces(poseStack, body, 8.25F, 4, 8, shellR, shellG, shellB, 0.7F, fullBright);
            poseStack.popPose();

            // A new render type may reuse the same BufferBuilder. Finish all
            // body vertices before acquiring its effect consumer.
            VertexConsumer glow = buffer.getBuffer(RenderType.lightning());
            poseStack.pushPose();
            poseStack.translate(0.0D, halfGap, 0.0D);
            drawOctahedronEdgeSet(poseStack, glow, 8.25F, 0.11F, TOP_EDGES,
                    0.75F, 0.92F, 1.0F, 0.55F + 0.4F * beamGlow);
            poseStack.popPose();
            poseStack.pushPose();
            poseStack.translate(0.0D, -halfGap, 0.0D);
            drawOctahedronEdgeSet(poseStack, glow, 8.25F, 0.11F, BOTTOM_EDGES,
                    0.75F, 0.92F, 1.0F, 0.55F + 0.4F * beamGlow);
            poseStack.popPose();

            // Luminous seam around the opened equator.
            if (expose > 0.05F)
            {
                Vector3f[] basis = {new Vector3f(1.0F, 0.0F, 0.0F), new Vector3f(0.0F, 0.0F, 1.0F)};
                RibbonRenderer.drawPolyRing(poseStack.last().pose(), glow, basis[0], basis[1], 4,
                        8.4F, 0.25F + 0.12F * Mth.sin(time * 0.8F),
                        1.0F, 0.55F, 0.75F, 0.5F * expose);
            }

        }
        poseStack.popPose();

        // ----- charge-up light convergence (world-aligned, does not spin) -----
        if (entity.isCharging())
        {
            poseStack.pushPose();
            poseStack.translate(0.0D, coreHeight, 0.0D);
            drawChargeRays(entity, partialTick, poseStack, buffer.getBuffer(RenderType.lightning()));
            poseStack.popPose();
        }

        super.render(entity, entityYaw, partialTick, poseStack, buffer, packedLight);
        com.projectseele.client.EncounterObserverCacheR45.markNormalDrawn(entity);
    }

    /** The same selected model, drawn from the real server UUID snapshot. No client entity is spawned. */
    public static void renderObservedR52(com.projectseele.network.ClientboundEncounterObserverPacket.Snapshot state,
            float partial,long age,PoseStack poses,MultiBufferSource buffers)
    {
        float scale=state.height()/15F,center=state.height()*.5F;
        boolean charging=(state.flags()&com.projectseele.network.ClientboundEncounterObserverPacket.CHARGING)!=0;
        boolean exposed=(charging&&age<20||state.beamTicks()>age)&&(state.flags()&com.projectseele.network.ClientboundEncounterObserverPacket.EXPOSED)!=0;
        float time=state.poseTick()+partial,gap=exposed?3.75F:0;
        poses.pushPose();poses.translate(0,center,0);poses.scale(scale,scale,scale);poses.mulPose(Axis.YP.rotationDegrees(time*.75F));
        if (!RamielSourceModelR53.draw(poses,buffers,exposed?1:0,time,charging,LightTexture.pack(0,15)))
        {
            var body=buffers.getBuffer(RenderType.entityTranslucent(TEXTURE));
            float core=(exposed?4F:2.6F)*(charging?1.1F+.3F*Mth.sin(time*.5F):.95F);
            drawOctahedron(poses,body,core,1,.3F,.28F,1,LightTexture.FULL_BRIGHT);
            poses.pushPose();poses.translate(0,gap,0);drawOctahedronFaces(poses,body,8.25F,0,4,.45F,.72F,1,.7F,LightTexture.FULL_BRIGHT);poses.popPose();
            poses.pushPose();poses.translate(0,-gap,0);drawOctahedronFaces(poses,body,8.25F,4,8,.45F,.72F,1,.7F,LightTexture.FULL_BRIGHT);poses.popPose();
            var glow=buffers.getBuffer(RenderType.lightning());
            poses.pushPose();poses.translate(0,gap,0);drawOctahedronEdgeSet(poses,glow,8.25F,.11F,TOP_EDGES,.75F,.92F,1,.8F);poses.popPose();
            poses.pushPose();poses.translate(0,-gap,0);drawOctahedronEdgeSet(poses,glow,8.25F,.11F,BOTTOM_EDGES,.75F,.92F,1,.8F);poses.popPose();
        }
        poses.popPose();
        var glow=buffers.getBuffer(RenderType.lightning());
        if(state.beamTicks()>age)
        {
            Vec3 delta=state.beamEnd().subtract(state.position());var start=new Vector3f(0,center,0);var end=delta.toVector3f();
            renderSustainedBeam(poses.last().pose(),glow,start,end,state.beamTicks()-age-partial,
                    RamielEntity.YASHIMA_BEAM_TICKS_R54,time);
        }
        if(charging)
        { poses.pushPose();poses.translate(0,center,0);drawChargeRays(time,poses,glow);poses.popPose(); }
        if((state.flags()&com.projectseele.network.ClientboundEncounterObserverPacket.DRILLING)!=0&&state.drillDepth()>0)
            drawStarRibbon(poses.last().pose(),glow,new Vector3f(0,center,0),new Vector3f(0,center-state.drillDepth(),0),2.6F,2.6F,.35F,.65F,1,.75F);
    }

    // =====================================================================
    // Beam
    // =====================================================================

    private static void renderBeam(RamielEntity entity, float partialTick, float beamTicks,
                                   PoseStack poseStack, MultiBufferSource buffer, float coreHeight)
    {
        Vec3 entityPos = entity.getPosition(partialTick);
        Vec3 endWorld = entity.getBeamEnd();
        Vector3f start = new Vector3f(0.0F, coreHeight, 0.0F);
        Vector3f end = new Vector3f(
                (float) (endWorld.x - entityPos.x),
                (float) (endWorld.y - entityPos.y),
                (float) (endWorld.z - entityPos.z));

        VertexConsumer consumer = buffer.getBuffer(RenderType.lightning());
        poseStack.pushPose();
        renderSustainedBeam(poseStack.last().pose(),consumer,start,end,beamTicks,
                entity.getBeamDurationR54(),entity.tickCount+partialTick);
        poseStack.popPose();
    }

    private static void renderSustainedBeam(Matrix4f pose,VertexConsumer out,Vector3f start,Vector3f end,
            float remaining,int duration,float time)
    {
        float alpha=Mth.clamp(remaining/4F,0,1);
        float pulse=1F+.06F*Mth.sin(time*1.8F);
        float flash=remaining>duration-2?1.35F:1F;
        RibbonRenderer.drawSoftStarRibbon(pose,out,start,end,10F*pulse,10F*pulse,.65F,.28F,1F,alpha*.3F);
        drawStarRibbon(pose,out,start,end,4F*flash,4F*flash,
                BEAM_HALO_RGB[0],BEAM_HALO_RGB[1],BEAM_HALO_RGB[2],alpha*.65F);
        drawStarRibbon(pose,out,start,end,2.2F*flash,2.2F*flash,
                BEAM_CORE_RGB[0],BEAM_CORE_RGB[1],BEAM_CORE_RGB[2],alpha);
        // A bounded contact ring supplies impact motion without spawning particle clouds.
        Vector3f axis=new Vector3f(end).sub(start);
        if(axis.lengthSquared()<.001F)return;
        axis.normalize();
        Vector3f across=new Vector3f(axis).cross(Math.abs(axis.y)<.9F?new Vector3f(0,1,0):new Vector3f(1,0,0)).normalize();
        Vector3f up=new Vector3f(axis).cross(across).normalize();
        // Eight travelling bands give the sustained column visible energy flow.
        float length=start.distance(end);
        for(int band=0;band<8;band++)
        {
            float along=((time*.025F+band/8F)%1F)*length;
            Vector3f center=new Vector3f(start).fma(along,axis);
            Vector3f tail=new Vector3f(center).fma(Math.min(12F,length-along),axis);
            drawStarRibbon(pose,out,center,tail,4.6F,4.6F,.9F,.55F,1F,alpha*.4F);
        }
        float radius=5F+2F*(.5F+.5F*Mth.sin(time*.7F));
        for(int i=0;i<16;i++)
        {
            float a=i*Mth.TWO_PI/16F,b=(i+1)*Mth.TWO_PI/16F;
            Vector3f p=new Vector3f(end).fma(radius*Mth.cos(a),across).fma(radius*Mth.sin(a),up);
            Vector3f q=new Vector3f(end).fma(radius*Mth.cos(b),across).fma(radius*Mth.sin(b),up);
            drawStarRibbon(pose,out,p,q,.3F,.3F,1F,.7F,1F,alpha*.7F);
        }
    }

    private static void drawStarRibbon(Matrix4f pose, VertexConsumer consumer, Vector3f start, Vector3f end,
                                       float startWidth, float endWidth, float r, float g, float b, float a)
    {
        RibbonRenderer.drawStarRibbon(pose, consumer, start, end, startWidth, endWidth, r, g, b, a);
    }

    /** Downward boring column while the phase-two drill is active. */
    private static void renderDrill(RamielEntity entity, float partialTick,
                                    PoseStack poseStack, MultiBufferSource buffer, float coreHeight)
    {
        float time = entity.tickCount + partialTick;
        float flicker = 0.75F + 0.25F * Mth.sin(time * 1.7F);
        Vector3f start = new Vector3f(0.0F, coreHeight, 0.0F);
        Vector3f end = new Vector3f(0.0F, coreHeight - entity.getDrillDepth(), 0.0F);

        VertexConsumer consumer = buffer.getBuffer(RenderType.lightning());
        poseStack.pushPose();
        Matrix4f pose = poseStack.last().pose();
        drawStarRibbon(pose, consumer, start, end, 2.6F, 1.8F,
                BEAM_HALO_RGB[0], BEAM_HALO_RGB[1], BEAM_HALO_RGB[2], 0.45F * flicker);
        drawStarRibbon(pose, consumer, start, end, 1.1F, 0.7F,
                BEAM_CORE_RGB[0], BEAM_CORE_RGB[1], BEAM_CORE_RGB[2], 0.9F * flicker);
        poseStack.popPose();
    }

    private static void drawChargeRays(RamielEntity entity, float partialTick,
                                       PoseStack poseStack, VertexConsumer consumer)
    { drawChargeRays(entity.tickCount+partialTick,poseStack,consumer); }

    private static void drawChargeRays(float time,PoseStack poseStack,VertexConsumer consumer)
    {
        Matrix4f pose = poseStack.last().pose();
        for (int i = 0; i < 8; i++)
        {
            float azimuth = (float) Math.toRadians(i * 45.0F + time * 1.8F);
            float pitch = (float) Math.toRadians((i % 2 == 0 ? 24.0F : -18.0F)
                    + 8.0F * Mth.sin(time * 0.11F + i));
            float radius = 18.75F;
            Vector3f outer = new Vector3f(
                    radius * Mth.cos(pitch) * Mth.cos(azimuth),
                    radius * Mth.sin(pitch),
                    radius * Mth.cos(pitch) * Mth.sin(azimuth));
            float pulse = 0.28F + 0.30F * Mth.sin(time * 0.35F + i * 1.3F);
            // Rays thicken toward the core: energy pouring inward.
            drawStarRibbon(pose, consumer, outer, new Vector3f(0.0F, 0.0F, 0.0F),
                    0.06F, 0.55F, RAY_RGB[0], RAY_RGB[1], RAY_RGB[2], Math.max(pulse, 0.05F));
        }
    }

    // =====================================================================
    // Octahedron body
    // =====================================================================

    private static final Vector3f[] UNIT_VERTS = {
            new Vector3f(0.0F, 1.0F, 0.0F),   // 0: top apex
            new Vector3f(0.0F, -1.0F, 0.0F),  // 1: bottom apex
            new Vector3f(1.0F, 0.0F, 0.0F),   // 2: +X
            new Vector3f(0.0F, 0.0F, 1.0F),   // 3: +Z
            new Vector3f(-1.0F, 0.0F, 0.0F),  // 4: -X
            new Vector3f(0.0F, 0.0F, -1.0F)   // 5: -Z
    };
    private static final int[][] FACES = {
            {0, 2, 3}, {0, 3, 4}, {0, 4, 5}, {0, 5, 2},
            {1, 3, 2}, {1, 4, 3}, {1, 5, 4}, {1, 2, 5}
    };
    private static final int[][] EDGES = {
            {0, 2}, {0, 3}, {0, 4}, {0, 5},
            {1, 2}, {1, 3}, {1, 4}, {1, 5},
            {2, 3}, {3, 4}, {4, 5}, {5, 2}
    };
    // Each shell half keeps its apex edges plus its own copy of the equator.
    private static final int[] TOP_EDGES = {0, 1, 2, 3, 8, 9, 10, 11};
    private static final int[] BOTTOM_EDGES = {4, 5, 6, 7, 8, 9, 10, 11};

    private static void drawOctahedron(PoseStack poseStack, VertexConsumer consumer, float size,
                                       float red, float green, float blue, float alpha, int packedLight)
    {
        drawOctahedronFaces(poseStack, consumer, size, 0, FACES.length, red, green, blue, alpha, packedLight);
    }

    /** Draws faces [from, to) — 0..4 is the top pyramid, 4..8 the bottom. */
    private static void drawOctahedronFaces(PoseStack poseStack, VertexConsumer consumer, float size,
                                            int from, int to,
                                            float red, float green, float blue, float alpha, int packedLight)
    {
        Matrix4f pose = poseStack.last().pose();
        Matrix3f normalPose = poseStack.last().normal();
        float[][] uvs = {{0.5F, 0.0F}, {0.0F, 1.0F}, {1.0F, 1.0F}};

        for (int f = from; f < to; f++)
        {
            Vector3f a = new Vector3f(UNIT_VERTS[FACES[f][0]]).mul(size);
            Vector3f b = new Vector3f(UNIT_VERTS[FACES[f][1]]).mul(size);
            Vector3f c = new Vector3f(UNIT_VERTS[FACES[f][2]]).mul(size);
            Vector3f normal = new Vector3f(b).sub(a).cross(new Vector3f(c).sub(a)).normalize();
            // Slight per-face shade variation sells the faceted crystal look.
            float shade = 0.82F + 0.06F * (f % 4);
            float r = red * shade;
            float g = green * shade;
            float bl = blue * shade;
            // Each triangle goes out as a quad with the last vertex repeated.
            putVertex(pose, normalPose, consumer, a, r, g, bl, alpha, uvs[0], normal, packedLight);
            putVertex(pose, normalPose, consumer, b, r, g, bl, alpha, uvs[1], normal, packedLight);
            putVertex(pose, normalPose, consumer, c, r, g, bl, alpha, uvs[2], normal, packedLight);
            putVertex(pose, normalPose, consumer, c, r, g, bl, alpha, uvs[2], normal, packedLight);
        }
    }

    /** Thin luminous ribbons along the given edge indices give the crystal its cut. */
    private static void drawOctahedronEdgeSet(PoseStack poseStack, VertexConsumer consumer, float size,
                                              float width, int[] edgeIndices,
                                              float r, float g, float b, float a)
    {
        Matrix4f pose = poseStack.last().pose();
        for (int index : edgeIndices)
        {
            int[] edge = EDGES[index];
            Vector3f from = new Vector3f(UNIT_VERTS[edge[0]]).mul(size);
            Vector3f to = new Vector3f(UNIT_VERTS[edge[1]]).mul(size);
            drawStarRibbon(pose, consumer, from, to, width, width, r, g, b, a);
        }
    }

    private static void putVertex(Matrix4f pose, Matrix3f normalPose, VertexConsumer consumer, Vector3f pos,
                                  float r, float g, float b, float a, float[] uv, Vector3f normal, int light)
    {
        consumer.vertex(pose, pos.x(), pos.y(), pos.z())
                .color(r, g, b, a)
                .uv(uv[0], uv[1])
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(light)
                .normal(normalPose, normal.x(), normal.y(), normal.z())
                .endVertex();
    }

    @Override
    public ResourceLocation getTextureLocation(RamielEntity entity)
    {
        return TEXTURE;
    }
}
