package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.world.ArmamentTowerLogicR64;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Draws what moves on a spare-weapon tower. Nothing while it is stowed: the building and the lot are real blocks.
 *
 * <p>City lowered: the lot's hatch sinks and slides away under the ground, and a pod dressed like the top of the
 * building rises through the opening. City raised: the roof locks lift, the door goes up into its lintel and the
 * rifle shows in the bay behind it. Hatch and door are drawn from what the client saw standing there, so the
 * moving plates look like the blocks they replace.</p>
 */
final class ArmamentTowerRenderR64
{
    private static final ResourceLocation RIFLE_MESH = new ResourceLocation(ProjectSeele.MODID, "mesh/eva_pallet_smg.mesh.json");
    private static final ResourceLocation RIFLE_TEXTURE = new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_pallet_smg.png");
    // The colours of an A-1 building as tools/map_buildings/city_restyle.py draws it: grey-green armour, grey seams.
    private static final BlockState WALL = Blocks.CYAN_TERRACOTTA.defaultBlockState();
    private static final BlockState SEAM = Blocks.GRAY_CONCRETE.defaultBlockState();
    private static final BlockState FLOOR = Blocks.POLISHED_ANDESITE.defaultBlockState();
    private static final BlockState ROOF = Blocks.GRAY_CONCRETE.defaultBlockState();
    private static final BlockState FRAME = Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState SLAT_A = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
    private static final BlockState SLAT_B = Blocks.DEEPSLATE_TILES.defaultBlockState();
    private static final BlockState YELLOW = Blocks.YELLOW_CONCRETE.defaultBlockState();
    private static final BlockState BLACK = Blocks.BLACK_CONCRETE.defaultBlockState();
    private static final BlockState GUIDE = Blocks.QUARTZ_PILLAR.defaultBlockState();
    private static final BlockState PIN = Blocks.IRON_BARS.defaultBlockState();
    private static final BlockState LAMP = Blocks.SHROOMLIGHT.defaultBlockState();
    private static final int FULL_BRIGHT = 0x00F000F0;
    private static final int OUT = ArmamentTowerLogicR64.HALF - 1;
    /** The weapon stands in the middle of the five cells between the wall and the building's core. */
    private static final double RIFLE_BACK = OUT - 3.0D;
    /** The rifle's mesh is 13 long about a point 1.3 off its middle; this centres it in the door. */
    private static final double RIFLE_CENTRE = 1.3D;
    private static final int WALL_ROWS = ArmamentTowerLogicR64.POD_HEIGHT - 2;

    static void render(NervArmamentStationEntity station, float partialTick, PoseStack poses, MultiBufferSource buffers, int light)
    {
        int state = station.getStationState(), run = station.towerRunR64();
        if (state == NervArmamentStationEntity.STOWED || run == ArmamentTowerLogicR64.NONE) return;
        var door = station.towerDoorR64();
        int facing = station.towerFacingR64();
        float lift = station.getLiftProgress(partialTick), hatch = station.getHatchProgress(partialTick), open = station.getDoorProgress(partialTick);
        // Lamps flash while anything moves and burn steadily while the weapon is offered.
        boolean lit = state == NervArmamentStationEntity.READY || (station.level().getGameTime() / 6) % 2 == 0;
        BlockState[] seen = station.towerClientCellsR64();
        var lot = station.towerLotR64();

        // The remembered blocks keep the way they face, so they are drawn before the frame is turned to the door.
        if (run == ArmamentTowerLogicR64.LOWERED && hatch < .999F && seen != null)
        {
            float sink = Math.min(1F, hatch * 4F), slide = Math.max(0F, (hatch - .25F) / .75F) * (OUT + .6F);
            var cells = ArmamentTowerLogicR64.hatchCells(lot);
            for (int i = 0; i < cells.size() && i < seen.length; i++)
            {
                if (seen[i].isAir()) continue;
                int dx = cells.get(i)[0] - lot.cx(), dz = cells.get(i)[2] - lot.cz();
                block(poses, buffers, light, seen[i], dx + (dx < 0 ? -slide : slide), -sink, dz);
            }
        }
        boolean doorOut = run == ArmamentTowerLogicR64.RAISED && ArmamentTowerLogicR64.cellsOut(run, state);
        if (doorOut && open < .999F && seen != null)
        {
            var cells = ArmamentTowerLogicR64.doorCells(lot, facing, door);
            double shift = open * door.height();
            for (int i = 0; i < cells.size() && i < seen.length; i++)
            {
                int row = i / door.width();
                // A row that has reached the lintel is inside it.
                if (seen[i].isAir() || row + shift > door.height() - 1) continue;
                int[] cell = cells.get(i);
                block(poses, buffers, light, seen[i], cell[0] - lot.cx(), cell[1] - lot.baseY() + shift, cell[2] - lot.cz());
            }
        }

        // The bay has work lights: what stands in it does not go dark in the building's own shade.
        int bayLight = LightTexture.pack(Math.max(13, LightTexture.block(light)), LightTexture.sky(light));
        poses.pushPose();
        // From here +z is the side the door is on.
        poses.mulPose(Axis.YP.rotationDegrees(facing == 1 ? -90F : facing == 2 ? 180F : facing == 3 ? 90F : 0F));
        if (run == ArmamentTowerLogicR64.LOWERED)
        {
            double base = -ArmamentTowerLogicR64.POD_TRAVEL * (1.0D - lift);
            pod(poses, buffers, light, bayLight, base, door, open, lit);
            if (station.isStocked()) rifle(poses, buffers, bayLight, base + 1.0D);
            roof(poses, buffers, light, base + ArmamentTowerLogicR64.POD_HEIGHT, open, lit, true);
        }
        else
        {
            if (doorOut)
            {
                if (seen == null && open < .999F) slats(poses, buffers, light, door.bottom(), door, open);
                if (station.isStocked()) rifle(poses, buffers, bayLight, door.bottom());
            }
            // On the standing building only what moves is drawn: the locks, and the lamps while they are dark.
            roof(poses, buffers, light, station.towerHeightR64() + 1.0D, hatch, lit, false);
        }
        poses.popPose();
    }

    /** The pod of the lowered run, dressed as the building: floor, armour walls with seams, iron door frame, warning band, roof slab. */
    private static void pod(PoseStack poses, MultiBufferSource buffers, int light, int bayLight, double base,
            ArmamentTowerLogicR64.Door door, float open, boolean lit)
    {
        double edge = OUT + .5D, inner = OUT - .5D;
        int side = door.width() / 2, doorTop = door.bottom() + door.height(), plateRows = WALL_ROWS - 1;
        panel(poses, buffers, light, FLOOR, -edge, base, -edge, 2 * OUT + 1, 1, 2 * OUT + 1);
        // The corners are seams; the two beside the door are its iron jambs up to the lintel.
        for (int x : new int[]{-OUT, OUT})
        {
            panel(poses, buffers, light, SEAM, x - .5D, base + 1, -edge, 1, plateRows, 1);
            panel(poses, buffers, light, FRAME, x - .5D, base + 1, inner, 1, Math.min(doorTop, plateRows), 1);
            if (doorTop < plateRows) panel(poses, buffers, light, SEAM, x - .5D, base + 1 + doorTop, inner, 1, plateRows - doorTop, 1);
        }
        for (int row = 1; row <= plateRows; )
        {
            boolean seam = row % 8 == 0;
            int rows = seam ? 1 : Math.min(8 - row % 8, plateRows - row + 1);
            BlockState plate = seam ? SEAM : WALL;
            panel(poses, buffers, light, plate, -inner, base + row, -edge, 2 * OUT - 1, rows, 1);
            panel(poses, buffers, light, plate, -edge, base + row, -inner, 1, rows, 2 * OUT - 1);
            panel(poses, buffers, light, plate, inner, base + row, -inner, 1, rows, 2 * OUT - 1);
            // The door side: the strips beside the door, and the full width above its lintel.
            if (side < OUT - 1)
            {
                panel(poses, buffers, light, plate, -inner, base + row, inner, OUT - 1 - side, rows, 1);
                panel(poses, buffers, light, plate, side + .5D, base + row, inner, OUT - 1 - side, rows, 1);
            }
            int from = Math.max(row, doorTop + 1), above = row + rows - from;
            if (above > 0) panel(poses, buffers, light, plate, -side - .5D, base + from, inner, door.width(), above, 1);
            row += rows;
        }
        // The iron lintel over the door, and the warning band round the top, as on the building.
        if (doorTop <= plateRows) panel(poses, buffers, light, FRAME, -side - .5D, base + doorTop, inner, door.width(), 1, 1);
        for (int along = -OUT; along <= OUT; along++)
        {
            block(poses, buffers, light, band(along, -OUT), along, base + WALL_ROWS, -OUT);
            block(poses, buffers, light, band(along, OUT), along, base + WALL_ROWS, OUT);
            if (Math.abs(along) == OUT) continue;
            block(poses, buffers, light, band(-OUT, along), -OUT, base + WALL_ROWS, along);
            block(poses, buffers, light, band(OUT, along), OUT, base + WALL_ROWS, along);
        }
        panel(poses, buffers, light, ROOF, -edge, base + WALL_ROWS + 1, -edge, 2 * OUT + 1, 1, 2 * OUT + 1);
        // Behind the bay the pod is closed off, as the building's core closes the bay.
        panel(poses, buffers, bayLight, WALL, -inner, base + 1, OUT - 6.5D, 2 * OUT - 1, WALL_ROWS, 1);
        if (open < .999F) slats(poses, buffers, light, base + door.bottom(), door, open);
    }

    private static BlockState band(int x, int z)
    {
        return ((x + z) & 1) != 0 ? YELLOW : BLACK;
    }

    /** A plain door of slats going up into the lintel, where the client has not seen the real one. */
    private static void slats(PoseStack poses, MultiBufferSource buffers, int light, double bottom,
            ArmamentTowerLogicR64.Door door, float open)
    {
        int side = door.width() / 2;
        double shift = open * door.height();
        for (int row = 0; row < door.height(); row++)
        {
            if (row + shift > door.height() - 1) break;
            panel(poses, buffers, light, (row & 1) == 0 ? SLAT_A : SLAT_B, -side - .5D, bottom + row + shift, OUT - .5D, door.width(), 1, 1);
        }
    }

    /** The rifle upright in the bay, its side to the door, at the size it has in an EVA's hands. */
    private static void rifle(PoseStack poses, MultiBufferSource buffers, int light, double floor)
    {
        poses.pushPose();
        poses.translate(RIFLE_CENTRE, floor, RIFLE_BACK);
        poses.mulPose(Axis.YP.rotationDegrees(90F));
        poses.scale(EvaScale.RENDER_SCALE, EvaScale.RENDER_SCALE, EvaScale.RENDER_SCALE);
        LocalTriangleMeshLayer.renderStandalone(poses, buffers, RIFLE_MESH, RIFLE_TEXTURE, light, OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    /**
     * What stands on the roof at height {@code top}: the three locks, lifted by {@code lock}, and the corner
     * lamps. On the pod the guides are drawn too; on the standing building guides and lit lamps are blocks, and
     * only a dark cap is drawn over a lamp while it is off.
     */
    private static void roof(PoseStack poses, MultiBufferSource buffers, int light, double top, float lock, boolean lit, boolean pod)
    {
        for (int across = -2; across <= 2; across += 2)
        {
            // The building keeps a lamp block at the centre of its roof, an old builder's mark: the middle lock
            // stands on it, one block higher than its neighbours, and drops into it when the locks go down.
            double step = !pod && across == 0 ? 1.0D : 0.0D;
            block(poses, buffers, light, PIN, across, top - 2.0D + 2.0D * lock + step, 0);
            block(poses, buffers, light, PIN, across, top - 1.0D + 2.0D * lock + step, 0);
        }
        for (int x : new int[]{-OUT, OUT})
            for (int z : new int[]{-OUT, OUT})
            {
                if (pod) block(poses, buffers, lit ? FULL_BRIGHT : light, lit ? LAMP : ROOF, x, top, z);
                else if (!lit) panel(poses, buffers, light, ROOF, x - .51D, top - .01D, z - .51D, 1.02F, 1.02F, 1.02F);
            }
        if (!pod) return;
        for (int x : new int[]{-OUT + 2, OUT - 2})
            for (int z : new int[]{-OUT + 2, OUT - 2})
            {
                block(poses, buffers, light, GUIDE, x, top, z);
                block(poses, buffers, light, GUIDE, x, top + 1.0D, z);
            }
    }

    /** One block, its middle at x and z. */
    private static void block(PoseStack poses, MultiBufferSource buffers, int light, BlockState state, double x, double y, double z)
    {
        poses.pushPose();
        poses.translate(x - .5D, y, z - .5D);
        Minecraft.getInstance().getBlockRenderer().renderSingleBlock(state, poses, buffers, light, OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    /** One block stretched into a plate from the corner x, y, z. */
    private static void panel(PoseStack poses, MultiBufferSource buffers, int light, BlockState state,
            double x, double y, double z, float sizeX, float sizeY, float sizeZ)
    {
        poses.pushPose();
        poses.translate(x, y, z);
        poses.scale(sizeX, sizeY, sizeZ);
        Minecraft.getInstance().getBlockRenderer().renderSingleBlock(state, poses, buffers, light, OverlayTexture.NO_OVERLAY);
        poses.popPose();
    }

    private ArmamentTowerRenderR64() {}
}
