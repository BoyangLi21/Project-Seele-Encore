package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.culling.Frustum;
import com.mojang.math.Axis;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.EvaHangarBuilder;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.block.BlockRenderDispatcher;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.inventory.InventoryMenu;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/** Industrial carrier silhouette rendered by one tracked entity. */
public final class NervCarrierPlatformRenderer
        extends EntityRenderer<NervCarrierPlatformEntity>
{
    private final BlockRenderDispatcher blocks;

    public NervCarrierPlatformRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.blocks = context.getBlockRenderDispatcher();
        this.shadowRadius = 0.0F;
    }

    @Override
    public void render(NervCarrierPlatformEntity entity, float yaw,
                       float partialTick, PoseStack poses,
                       MultiBufferSource buffers, int packedLight)
    {
        if (entity.isRestraintGantry() && hasEarlierGantryCopy(entity))
        {
            return;
        }
        if (entity.isPlugCrane())
        {
            renderPlugCrane(entity, partialTick, poses, buffers, packedLight);
            super.render(entity, yaw, partialTick, poses, buffers,
                    packedLight);
            return;
        }
        if (entity.isPersonnelLift())
        {
            poses.pushPose();
            poses.mulPose(Axis.YP.rotationDegrees(entity.getYRot()));
            renderPersonnelLift(entity, poses, buffers, packedLight);
            poses.popPose();
            super.render(entity, yaw, partialTick, poses, buffers, packedLight);
            return;
        }
        float half = EvaHangarBuilder.CARRIER_HALF_EXTENT;
        float inner = half * 2.0F - 1.0F;
        float full = half * 2.0F + 1.0F;
        BlockState accent = switch (entity.getUnitVariant())
        {
            case 0 -> Blocks.ORANGE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.RED_CONCRETE.defaultBlockState();
            default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
        };
        // The parked wet cage already has an authored block deck. In that
        // state this transient entity contributes only the animated restraint
        // towers; drawing a second carrier deck causes z-fighting. A moving
        // carrier has no restraints and keeps the full rail-platform mesh.
        if (entity.isRestraintGantry() || entity.isPlugCrane())
        {
            if (entity.isRestraintGantry())
            {
                renderLclSurface(entity, partialTick, poses, buffers,
                        packedLight);
            }
            float service=entity.repairProgressR33();
            TvFacilityMeshes.withBuffers(buffers,()->
            {
                TvFacilityMeshes.cage(poses,packedLight,entity.getRestraintProgress(partialTick),entity.getUnitVariant());
                EvaBayMachineryR33.render(poses,service<0?-1:Math.min(1,service+partialTick/2400F),entity.tickCount+partialTick,15.2F,false,entity.getUnitVariant());
            });
            super.render(entity, yaw, partialTick, poses, buffers,
                    packedLight);
            return;
        }
        renderBlock(poses, buffers, packedLight,
                Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState(),
                -half + 0.5F, -0.28F, -half + 0.5F,
                inner, 0.35F, inner);
        renderBlock(poses, buffers, packedLight,
                Blocks.IRON_BLOCK.defaultBlockState(),
                -half - 0.5F, -0.27F, -half - 0.5F,
                full, 0.55F, 1.0F);
        renderBlock(poses, buffers, packedLight,
                Blocks.IRON_BLOCK.defaultBlockState(),
                -half - 0.5F, -0.27F, half - 0.5F,
                full, 0.55F, 1.0F);
        renderBlock(poses, buffers, packedLight,
                Blocks.IRON_BLOCK.defaultBlockState(),
                -half - 0.5F, -0.27F, -half + 0.5F,
                1.0F, 0.55F, inner);
        renderBlock(poses, buffers, packedLight,
                Blocks.IRON_BLOCK.defaultBlockState(),
                half - 0.5F, -0.27F, -half + 0.5F,
                1.0F, 0.55F, inner);
        // A visible under-carriage, traction spine and transverse sleepers
        // make transport read as a machine riding rails instead of an EVA
        // whose coordinates are simply interpolated through the tunnel.
        BlockState underframe = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        renderBlock(poses, buffers, packedLight, underframe,
                -6.2F, -0.72F, -half + 1.5F,
                1.25F, 0.42F, inner - 2.0F);
        renderBlock(poses, buffers, packedLight, underframe,
                4.95F, -0.72F, -half + 1.5F,
                1.25F, 0.42F, inner - 2.0F);
        for (float z = -11.0F; z <= 11.0F; z += 5.5F)
        {
            renderBlock(poses, buffers, packedLight,
                    Blocks.CUT_COPPER.defaultBlockState(),
                    -10.0F, -0.62F, z,
                    20.0F, 0.30F, 0.70F);
        }

        // Four magnetic bogies engage the two authored guide rails. They stay
        // with the moving entity, so the carrier reads as a rail machine.
        BlockState bogie = Blocks.POLISHED_BLACKSTONE.defaultBlockState();
        BlockState shoe = Blocks.COPPER_BLOCK.defaultBlockState();
        for (float x : new float[] {-5.65F, 4.65F})
        {
            for (float z : new float[] {-9.0F, 8.0F})
            {
                renderBlock(poses, buffers, packedLight, bogie,
                        x, -0.78F, z, 1.0F, 0.50F, 2.0F);
                renderBlock(poses, buffers, packedLight, shoe,
                        x + 0.15F, -0.92F, z + 0.25F,
                        0.70F, 0.18F, 1.50F);
            }
        }
        super.render(entity, yaw, partialTick, poses, buffers, packedLight);
    }

    /** Fractional surface between the authoritative full fluid layers. */
    private void renderLclSurface(NervCarrierPlatformEntity entity,
                                  float partialTick, PoseStack poses,
                                  MultiBufferSource buffers,
                                  int packedLight)
    {
        float level = entity.getLclVisualLevel(partialTick);
        if (level <= 0.01F || Math.abs(level-Math.round(level))<.002F)
        {
            return;
        }
        // Fractional drainage uses the same dense orange-red material as the
        // complete fluid layers; there must be no clear/purple flash at a step.
        var out=buffers.getBuffer(EnergyGlowR24.SMOKE);
        float y=level+.93F;
        int tint=com.projectseele.fluid.LclFluidType.TINT;
        for(float[] p:new float[][]{{-19.5F,26.5F,0,1},{19.5F,26.5F,1,1},{19.5F,-26.5F,1,0},{-19.5F,-26.5F,0,0}})
            out.vertex(poses.last().pose(),p[0],y,p[1]).color((tint>>16)&255,(tint>>8)&255,tint&255,(tint>>>24)&255).endVertex();
    }

    /**
     * Server-side reconciliation cannot prevent a just-discarded duplicate
     * from remaining in the client's interpolation queue for a few frames.
     * Rendering both identical opaque gantries is pure z-fighting, so the
     * client deterministically keeps only the lowest entity id at one anchor.
     */
    private static boolean hasEarlierGantryCopy(
            NervCarrierPlatformEntity entity)
    {
        AABB anchor = AABB.ofSize(entity.position(), 2.0D, 2.0D, 2.0D);
        return entity.level().getEntitiesOfClass(
                NervCarrierPlatformEntity.class, anchor,
                candidate -> candidate != entity
                        && candidate.isRestraintGantry()
                        && candidate.getUnitVariant()
                        == entity.getUnitVariant()
                        && candidate.getId() < entity.getId())
                .stream().findAny().isPresent();
    }

    @Override
    public boolean shouldRender(NervCarrierPlatformEntity entity,
                                Frustum frustum,
                                double cameraX, double cameraY,
                                double cameraZ)
    {
        if (entity.isRestraintGantry() || entity.isPlugCrane())
        {
            // These mechanisms are much larger than the entity's tiny
            // physical AABB.  Frustum-testing only that origin box made fixed
            // gantries blink and made a suspended plug crane disappear while
            // its lower spreader was still plainly in view.
            return true;
        }
        return super.shouldRender(entity, frustum, cameraX, cameraY,
                cameraZ);
    }

    /** A continuous suspended gantry with no persistent world-block debris. */
    private void renderPlugCrane(NervCarrierPlatformEntity entity,
                                 float partialTick,
                                 PoseStack poses,
                                 MultiBufferSource buffers,
                                 int packedLight)
    {
        PlugGantryRenderer.render(entity,partialTick,poses,buffers,packedLight);
    }

    /** Opposed shoulder and hip restraints which fold into the side towers. */
    private void renderWetCageRestraints(NervCarrierPlatformEntity entity,
                                         PoseStack poses,
                                         MultiBufferSource buffers,
                                         int packedLight,
                                         BlockState accent)
    {
        float progress = entity.getRestraintProgress();
        BlockState frame = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState hydraulic = Blocks.IRON_BLOCK.defaultBlockState();
        BlockState lamp = Blocks.SEA_LANTERN.defaultBlockState();
        for (int side : new int[] {-1, 1})
        {
            float towerX = side * 12.35F;
            for (float z : new float[] {-4.8F, 3.8F})
            {
                renderBlock(poses, buffers, packedLight, frame,
                        towerX - 0.65F, 0.25F, z,
                        1.30F, 60.0F, 1.0F);
                /*
                 * Lamps sit just outside the tower face.  They used to be
                 * scaled inside the deepslate column, leaving two opaque
                 * surfaces in the same depth plane; moving the camera then
                 * made the whole gantry appear to flash.
                 */
                float lampX = side < 0
                        ? towerX - 0.91F : towerX + 0.66F;
                renderBlock(poses, buffers, packedLight, lamp,
                        lampX, 56.4F, z + 0.10F,
                        0.25F, 0.70F, 0.80F);
            }
            /*
             * Cross-members span only the clear gap between the two column
             * faces.  The former 9.6/7.2-deep bars occupied the columns as
             * well, producing coplanar full-block faces over a 1-block strip
             * at both ends.  Exact butt joints preserve the silhouette while
             * giving the depth buffer one owner per visible surface.
             */
            renderBlock(poses, buffers, packedLight, frame,
                    towerX - 0.65F, 55.0F, -3.80F,
                    1.30F, 1.30F, 7.60F);
            renderBlock(poses, buffers, packedLight, frame,
                    towerX - 0.65F, 21.5F, -3.80F,
                    1.30F, 1.10F, 7.60F);

            // The imported shoulder's reviewed outer silhouette is
            // |x| ~= 7.69.  The old stroke ended at |x|=6.765 and therefore
            // put almost a full block of the jaw inside the triangle mesh.
            // Those intersecting opaque faces fought in the depth buffer only
            // while the first-person camera moved, which looked like the
            // entire restraint flashing.  Stop just outside the armour and
            // let the broad saddle communicate contact without coplanar or
            // intersecting faces.
            /*
             * Build each actuator as a single rod followed by one saddle.
             * The old version stacked a frame, coloured pad and three jaws in
             * the same volume.  Their opaque coplanar faces z-fought whenever
             * the camera moved.  These dimensions never overlap: adjacent
             * parts meet at one mechanical seam, and the inner saddle face
             * stops just outside the measured armour silhouette.
             */
            float towerInner = side < 0 ? towerX + 0.65F
                    : towerX - 0.65F;
            float shoulderReach = 0.85F + 3.01F * progress;
            float shoulderSaddleWidth = 0.46F;
            float shoulderRodLength = Math.max(0.20F,
                    shoulderReach - shoulderSaddleWidth);
            float shoulderRodX = side < 0
                    ? towerInner
                    : towerInner - shoulderRodLength;
            float shoulderSaddleX = side < 0
                    ? towerInner + shoulderRodLength
                    : towerInner - shoulderReach;
            for (float z : new float[] {-3.6F, -0.5F, 2.6F})
            {
                renderBlock(poses, buffers, packedLight, hydraulic,
                        shoulderRodX, 51.55F, z,
                        shoulderRodLength, 0.82F, 0.90F);
            }
            // Closed inner faces are x=-7.84/+7.84, just outside the reviewed
            // Unit-01 shoulder outline x=-7.69/+7.69.  The whole saddle was
            // raised 0.55 blocks so it clamps the shoulder rather than the
            // upper arm.
            renderBlock(poses, buffers, packedLight, accent,
                    shoulderSaddleX, 50.70F, -4.00F,
                    shoulderSaddleWidth, 3.15F, 8.00F);
            renderBlock(poses, buffers, packedLight, hydraulic,
                    shoulderSaddleX, 53.88F, -4.05F,
                    shoulderSaddleWidth, 0.42F, 1.30F);
            renderBlock(poses, buffers, packedLight, hydraulic,
                    shoulderSaddleX, 53.88F, 2.75F,
                    shoulderSaddleWidth, 0.42F, 1.30F);

            // The shin/leg outside edge at this height is |x| ~= 5.82.  The
            // former 3.1-block stroke stopped around |x|=9.25 and visibly
            // clamped empty air.  This longer actuator ends at |x|=5.90 and
            // uses a single four-block-tall saddle, again with no overlapping
            // pad geometry.
            float legReach = 0.85F + 4.85F * progress;
            float legSaddleWidth = 0.55F;
            float legRodLength = Math.max(0.20F,
                    legReach - legSaddleWidth);
            float legRodX = side < 0
                    ? towerInner : towerInner - legRodLength;
            float legSaddleX = side < 0
                    ? towerInner + legRodLength
                    : towerInner - legReach;
            renderBlock(poses, buffers, packedLight, hydraulic,
                    legRodX, 20.60F, -1.55F,
                    legRodLength, 0.78F, 3.10F);
            renderBlock(poses, buffers, packedLight, accent,
                    legSaddleX, 18.55F, -2.05F,
                    legSaddleWidth, 4.55F, 4.10F);
        }
    }

    /**
     * Fully enclosed five-by-five personnel car.
     *
     * <p>The first smooth-cabin prototype rendered an open maintenance deck
     * with rails.  That made the shaft wall look like the back of the lift and
     * removed the familiar enclosed car, door and floor controls.  Keep the
     * continuously moving entity, but render the same closed room silhouette
     * as the proven block cabin.  Local +Z is the doorway and the entity yaw
     * is aligned to the audited landing exit.</p>
     */
    private void renderPersonnelLift(NervCarrierPlatformEntity entity,
                                     PoseStack poses,
                                     MultiBufferSource buffers,
                                     int packedLight)
    {
        BlockState accent = switch (entity.getLiftAccent())
        {
            case 1 -> Blocks.PURPLE_CONCRETE.defaultBlockState();
            case 2 -> Blocks.CYAN_CONCRETE.defaultBlockState();
            case 3 -> Blocks.RED_CONCRETE.defaultBlockState();
            case 4 -> Blocks.YELLOW_CONCRETE.defaultBlockState();
            default -> Blocks.ORANGE_CONCRETE.defaultBlockState();
        };
        BlockState frame = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState shell = Blocks.IRON_BLOCK.defaultBlockState();
        BlockState lining = Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
        BlockState deck = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState lamp = Blocks.SEA_LANTERN.defaultBlockState();
        BlockState panel = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState door = Blocks.GRAY_STAINED_GLASS.defaultBlockState();

        // Structural floor and ceiling: no open shaft is visible from inside.
        renderBlock(poses, buffers, packedLight, frame,
                -2.4F, -0.20F, -2.4F, 4.8F, 0.20F, 4.8F);
        renderBlock(poses, buffers, packedLight, deck,
                -2.15F, 0.00F, -2.15F, 4.3F, 0.16F, 4.3F);
        renderBlock(poses, buffers, packedLight, shell,
                -2.4F, 3.24F, -2.4F, 4.8F, 0.22F, 4.8F);

        // Back and side walls are continuous slabs, not railings.
        renderBlock(poses, buffers, packedLight, shell,
                -2.4F, 0.00F, -2.4F, 4.8F, 3.24F, 0.18F);
        renderBlock(poses, buffers, packedLight, lining,
                -2.18F, 0.18F, -2.18F, 4.36F, 2.88F, 0.10F);
        renderBlock(poses, buffers, packedLight, shell,
                -2.4F, 0.00F, -2.4F, 0.18F, 3.24F, 4.8F);
        renderBlock(poses, buffers, packedLight, shell,
                2.22F, 0.00F, -2.4F, 0.18F, 3.24F, 4.8F);

        // Narrow front jambs leave a three-block-wide passenger aperture.
        renderBlock(poses, buffers, packedLight, shell,
                -2.4F, 0.00F, 2.22F, 0.90F, 3.24F, 0.18F);
        renderBlock(poses, buffers, packedLight, shell,
                1.50F, 0.00F, 2.22F, 0.90F, 3.24F, 0.18F);

        // Two real sliding leaves.  Open leaves park behind the jambs.
        if (entity.isLiftDoorOpen())
        {
            renderBlock(poses, buffers, packedLight, door,
                    -2.20F, 0.12F, 2.10F, 0.62F, 2.92F, 0.12F);
            renderBlock(poses, buffers, packedLight, door,
                    1.58F, 0.12F, 2.10F, 0.62F, 2.92F, 0.12F);
        }
        else
        {
            renderBlock(poses, buffers, packedLight, door,
                    -1.50F, 0.12F, 2.10F, 1.50F, 2.92F, 0.12F);
            renderBlock(poses, buffers, packedLight, door,
                    0.00F, 0.12F, 2.10F, 1.50F, 2.92F, 0.12F);
        }

        // Ceiling light and an unmistakable two-key UP/DOWN panel.
        renderBlock(poses, buffers, packedLight, lamp,
                -0.80F, 3.05F, -0.75F, 1.60F, 0.16F, 1.50F);
        renderBlock(poses, buffers, packedLight, panel,
                2.10F, 0.88F, 0.62F, 0.12F, 1.42F, 0.74F);
        renderBlock(poses, buffers, packedLight,
                Blocks.LIME_CONCRETE.defaultBlockState(),
                2.02F, 1.72F, 0.80F, 0.10F, 0.24F, 0.24F);
        renderBlock(poses, buffers, packedLight,
                Blocks.ORANGE_CONCRETE.defaultBlockState(),
                2.02F, 1.22F, 0.80F, 0.10F, 0.24F, 0.24F);
        renderBlock(poses, buffers, packedLight, accent,
                -0.10F, 0.17F, -2.08F, 0.20F, 0.05F, 4.12F);
    }

    private void renderBlock(PoseStack poses, MultiBufferSource buffers,
                             int packedLight, BlockState state,
                             float x, float y, float z,
                             float scaleX, float scaleY, float scaleZ)
    {
        poses.pushPose();
        poses.translate(x, y, z);
        poses.scale(scaleX, scaleY, scaleZ);
        this.blocks.renderSingleBlock(state, poses, buffers, packedLight,
                OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    @Override
    public ResourceLocation getTextureLocation(
            NervCarrierPlatformEntity entity)
    {
        return InventoryMenu.BLOCK_ATLAS;
    }
}
