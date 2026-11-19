package com.projectseele.item;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/** Builds an original three-bay NERV underground sortie complex. */
public class NervConstructionKitItem extends Item
{
    public NervConstructionKitItem(Properties properties)
    {
        super(properties);
    }

    @Override
    public InteractionResult useOn(UseOnContext context)
    {
        if (!(context.getLevel() instanceof ServerLevel level))
        {
            return InteractionResult.SUCCESS;
        }
        BlockPos origin = context.getClickedPos().above();
        if (origin.getY() - 46 < level.getMinBuildHeight()
                || origin.getY() + 72 >= level.getMaxBuildHeight())
        {
            if (context.getPlayer() != null)
            {
                context.getPlayer().displayClientMessage(Component.translatable("message.projectseele.construction.height"), true);
            }
            return InteractionResult.FAIL;
        }
        AABB buildArea = new AABB(origin).inflate(80.0D, 64.0D, 80.0D);
        boolean existingComplex = !level.getEntitiesOfClass(EvaUnit01Entity.class, buildArea,
                unit -> unit.isAlive() && unit.findLaunchBed() != null).isEmpty();
        if (existingComplex)
        {
            if (context.getPlayer() != null)
            {
                context.getPlayer().displayClientMessage(Component.translatable("message.projectseele.construction.occupied"), true);
            }
            return InteractionResult.FAIL;
        }
        buildComplex(level, origin);
        if (context.getPlayer() != null)
        {
            context.getPlayer().displayClientMessage(Component.translatable("message.projectseele.nerv_built"), false);
        }
        return InteractionResult.CONSUME;
    }

    /** Shared builder used by the creative item and the deterministic silo command. */
    public static void buildComplex(ServerLevel level, BlockPos origin)
    {
        BlockState floor = Blocks.SMOOTH_STONE.defaultBlockState();
        BlockState armor = Blocks.GRAY_CONCRETE.defaultBlockState();
        BlockState nerv = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState glass = Blocks.TINTED_GLASS.defaultBlockState();

        // Armoured surface apron. The shafts are cut through it afterwards.
        for (int x = -64; x <= 64; x++)
        {
            for (int z = -45; z <= 55; z++)
            {
                BlockState surface = (Math.abs(x) % 12 == 0 || Math.abs(z) % 12 == 0)
                        ? armor : floor;
                level.setBlock(origin.offset(x, 0, z), surface, 3);
            }
        }
        BlockPos unit00Bay = origin.offset(-42, 0, 0);
        BlockPos unit01Bay = origin;
        BlockPos unit02Bay = origin.offset(42, 0, 0);
        buildLaunchShaft(level, unit00Bay, Blocks.ORANGE_CONCRETE.defaultBlockState());
        buildLaunchShaft(level, unit01Bay, Blocks.PURPLE_CONCRETE.defaultBlockState());
        buildLaunchShaft(level, unit02Bay, Blocks.RED_CONCRETE.defaultBlockState());

        // Underground transverse access gallery joining all three cages.
        for (int x = -50; x <= 50; x++)
        {
            for (int y = -41; y <= -35; y++)
            {
                for (int z = 16; z <= 24; z++)
                {
                    boolean shell = y == -41 || y == -35
                            || z == 16 || z == 24;
                    level.setBlock(origin.offset(x, y, z), shell ? armor : Blocks.AIR.defaultBlockState(), 3);
                    if (shell && y == -21 && x % 6 == 0)
                    {
                        level.setBlock(origin.offset(x, y, z), Blocks.SEA_LANTERN.defaultBlockState(), 3);
                    }
                }
            }
        }
        // Build the lift columns after the transverse gallery so its shell
        // cannot overwrite the ladder openings.
        buildEntryGantry(level, unit00Bay, Blocks.ORANGE_CONCRETE.defaultBlockState());
        buildEntryGantry(level, unit01Bay, Blocks.PURPLE_CONCRETE.defaultBlockState());
        buildEntryGantry(level, unit02Bay, Blocks.RED_CONCRETE.defaultBlockState());

        buildCommandBunker(level, origin.offset(0, 1, 40), armor, nerv, glass);
        for (int[] tower : new int[][] {{-56,-36},{-56,42},{56,-36},{56,42}})
        {
            buildRetractableTower(level, origin.offset(tower[0], 1, tower[1]), armor, glass);
        }
        deployUnit(level, unit00Bay, ModEntities.EVA_UNIT00.get().create(level));
        deployUnit(level, unit01Bay, ModEntities.EVA_UNIT01.get().create(level));
        deployUnit(level, unit02Bay, ModEntities.EVA_UNIT02.get().create(level));
    }

    private static void buildLaunchShaft(ServerLevel level, BlockPos centre, BlockState accent)
    {
        BlockState wall = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        BlockState frame = Blocks.IRON_BLOCK.defaultBlockState();
        BlockState dark = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState light = Blocks.SEA_LANTERN.defaultBlockState();
        for (int y = -46; y <= 22; y++)
        {
            for (int x = -17; x <= 17; x++)
            {
                for (int z = -17; z <= 17; z++)
                {
                    int edge = Math.max(Math.abs(x), Math.abs(z));
                    level.setBlock(centre.offset(x, y, z),
                            edge == 17 ? wall : Blocks.AIR.defaultBlockState(), 3);
                }
            }
            for (int sx : new int[] {-16, 16})
            {
                for (int sz : new int[] {-16, 16})
                {
                    level.setBlock(centre.offset(sx, y, sz), y % 5 == 0 ? light : frame, 3);
                }
            }
            if (y >= -44 && y <= 4 && y % 6 == 0)
            {
                for (int x = -15; x <= 15; x++)
                {
                    level.setBlock(centre.offset(x, y, -16), dark, 3);
                    level.setBlock(centre.offset(x, y, 16), dark, 3);
                }
            }
        }
        // Luminous carrier platform and colour-coded depth markings.
        for (int x = -14; x <= 14; x++)
        {
            for (int z = -14; z <= 14; z++)
            {
                boolean rim = Math.abs(x) == 14 || Math.abs(z) == 14;
                level.setBlock(centre.offset(x, -45, z), rim ? light : dark, 3);
            }
            for (int y = -43; y <= 17; y += 5)
            {
                level.setBlock(centre.offset(x, y, 17), accent, 3);
            }
        }
        level.setBlock(centre.offset(0, -45, 0), Blocks.LODESTONE.defaultBlockState(), 3);
        // Split surface shutter, left open along the centreline for sorties.
        for (int i = -17; i <= 17; i++)
        {
            level.setBlock(centre.offset(i, 1, -18), accent, 3);
            level.setBlock(centre.offset(i, 1, 18), accent, 3);
            level.setBlock(centre.offset(-18, 1, i), frame, 3);
            level.setBlock(centre.offset(18, 1, i), frame, 3);
        }
    }

    /**
     * Dorsal entry-plug access. The lift starts in the transverse gallery and
     * ends beside the Unit's upper back, so a pilot cannot board a caged EVA
     * from ground level. The catwalk stays outside the 17-block carrier
     * envelope and therefore cannot snag the frame during launch.
     */
    private static void buildEntryGantry(ServerLevel level, BlockPos centre, BlockState accent)
    {
        // The 2x Tiger plug socket resolves around bed+43. A floor at bed+48
        // puts the pilot at the high dorsal interaction envelope.
        int gantryY = 3;
        BlockState frame = Blocks.IRON_BLOCK.defaultBlockState();
        BlockState dark = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState light = Blocks.SEA_LANTERN.defaultBlockState();
        BlockState ladder = Blocks.LADDER.defaultBlockState().setValue(LadderBlock.FACING, Direction.NORTH);

        // Vertical service lift from the existing low access gallery.
        for (int y = -40; y <= 4; y++)
        {
            level.setBlock(centre.offset(0, y, 31), frame, 3);
            level.setBlock(centre.offset(0, y, 30), ladder, 3);
            if (y % 4 == 0)
            {
                level.setBlock(centre.offset(1, y, 31), light, 3);
            }
        }

        // Enclosed high catwalk. Its inner lip is beyond the +/-14 moving
        // carrier while remaining inside the scaled plug interaction reach.
        for (int z = 16; z <= 31; z++)
        {
            for (int x = -5; x <= 5; x++)
            {
                // Keep a real climb-through hatch at the top of the service
                // ladder. Filling this cell with the deck made the gantry look
                // complete while leaving the upper platform unreachable.
                BlockState deck = x == 0 && z == 30
                        ? ladder
                        : (x == 0 && z % 3 == 0 ? accent : dark);
                level.setBlock(centre.offset(x, gantryY, z), deck, 3);
                if (Math.abs(x) == 5)
                {
                    level.setBlock(centre.offset(x, gantryY + 1, z), Blocks.IRON_BARS.defaultBlockState(), 3);
                    level.setBlock(centre.offset(x, gantryY + 3, z), frame, 3);
                }
            }
            level.setBlock(centre.offset(0, gantryY + 4, z), z % 3 == 0 ? light : frame, 3);
        }

        // Cut a personnel doorway through the shaft shell at upper-back height.
        for (int x = -3; x <= 3; x++)
        {
            for (int y = gantryY + 1; y <= gantryY + 3; y++)
            {
                level.setBlock(centre.offset(x, y, 17), Blocks.AIR.defaultBlockState(), 3);
            }
        }
        level.setBlock(centre.offset(-5, gantryY + 2, 17), accent, 3);
        level.setBlock(centre.offset(5, gantryY + 2, 17), accent, 3);
    }

    private static void deployUnit(ServerLevel level, BlockPos bay, EvaUnit01Entity unit)
    {
        if (unit == null)
        {
            return;
        }
        // Face away from the +Z service gallery, placing the gantry at the
        // dorsal/rear side of every Unit rather than in front of its face.
        float launchYaw = 180.0F;
        unit.moveTo(bay.getX() + 0.5D, bay.getY() - 44.0D, bay.getZ() + 0.5D,
                launchYaw, 0.0F);
        // moveTo updates the entity look direction, but a LivingEntity keeps
        // separate body/head interpolation fields. Leaving those at zero made
        // the parked mesh face the rear gantry until launch lock synchronized
        // it several seconds later, while interaction already used 180 deg.
        unit.setYRot(launchYaw);
        unit.setYBodyRot(launchYaw);
        unit.setYHeadRot(launchYaw);
        unit.yRotO = launchYaw;
        unit.yBodyRotO = launchYaw;
        unit.yHeadRotO = launchYaw;
        unit.setPersistenceRequired();
        level.addFreshEntity(unit);
    }

    private static void buildCommandBunker(ServerLevel level, BlockPos centre, BlockState armor,
                                           BlockState nerv, BlockState glass)
    {
        for (int y = 0; y <= 9; y++)
        {
            int rx = 15 - y;
            int rz = 8 - Math.min(y, 6);
            for (int x = -rx; x <= rx; x++)
            {
                for (int z = -rz; z <= rz; z++)
                {
                    boolean shell = Math.abs(x) == rx || Math.abs(z) == rz || y == 0;
                    if (shell)
                    {
                        level.setBlock(centre.offset(x, y, z), y >= 5 && Math.abs(z) == rz ? glass : armor, 3);
                    }
                }
            }
        }
        for (int x = -10; x <= 10; x++)
        {
            level.setBlock(centre.offset(x, 1, -8), x % 4 == 0 ? Blocks.REDSTONE_LAMP.defaultBlockState() : nerv, 3);
        }
    }

    private static void buildRetractableTower(ServerLevel level, BlockPos base,
                                              BlockState armor, BlockState glass)
    {
        for (int y = 0; y <= 22; y++)
        {
            int half = y > 17 ? 2 : 3;
            for (int x = -half; x <= half; x++)
            {
                for (int z = -half; z <= half; z++)
                {
                    if (Math.abs(x) == half || Math.abs(z) == half)
                    {
                        level.setBlock(base.offset(x, y, z), y % 5 == 2 ? glass : armor, 3);
                    }
                }
            }
        }
    }
}
