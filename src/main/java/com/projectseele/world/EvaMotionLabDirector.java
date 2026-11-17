package com.projectseele.world;

import java.util.List;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/** Deterministic, disposable arena used only by SEELE_EVA_MOTION_LAB. */
public final class EvaMotionLabDirector
{
    public static final String LEVEL_NAME = "Project SEELE - EVA Motion Lab";
    public static final String ENTITY_TAG = "seele_motion_lab";
    private static final int FLOOR_Y = -61;
    private static final BlockPos MARKER = new BlockPos(0, FLOOR_Y - 1, 0);
    private static final int[] UNIT_X = {-80, 0, 80};
    private static final int UNIT_Z = -105;
    private static final DemoMode[] DEMO_MODES = {
            DemoMode.STOP, DemoMode.STOP, DemoMode.STOP
    };
    private static final int[] DEMO_DIRECTIONS = {1, 1, 1};
    private static final int[] DEMO_TICKS = {0, 0, 0};
    private static final AABB ARENA = new AABB(
            -190, FLOOR_Y - 12, -190, 191, 100, 191);

    private EvaMotionLabDirector() {}

    public static boolean isMotionLab(ServerLevel level)
    {
        return LEVEL_NAME.equals(level.getServer().getWorldData()
                .getLevelName());
    }

    public static boolean setup(ServerLevel level, boolean force)
    {
        if (!isMotionLab(level))
        {
            return false;
        }
        level.setDayTime(6000L);
        level.setWeatherParameters(12000, 0, false, false);
        level.getGameRules().getRule(GameRules.RULE_DAYLIGHT)
                .set(false, level.getServer());
        level.getGameRules().getRule(GameRules.RULE_WEATHER_CYCLE)
                .set(false, level.getServer());
        level.getGameRules().getRule(GameRules.RULE_DOMOBSPAWNING)
                .set(false, level.getServer());

        boolean built = level.getBlockState(MARKER).is(Blocks.LODESTONE);
        if (force || !built)
        {
            buildArena(level);
        }
        if (force)
        {
            for (int index = 0; index < DEMO_MODES.length; index++)
            {
                DEMO_MODES[index] = DemoMode.STOP;
                DEMO_DIRECTIONS[index] = 1;
                DEMO_TICKS[index] = 0;
            }
        }
        ensureUnits(level, force);
        return true;
    }

    /**
     * Runs the disposable autonomous gait lane and suppresses campaign map
     * writers while this dedicated save is open.
     */
    public static boolean tick(MinecraftServer server)
    {
        ServerLevel level = server.overworld();
        if (!isMotionLab(level))
        {
            return false;
        }
        for (int variant = 0; variant < 3; variant++)
        {
            EvaUnit01Entity eva = unit(level, variant);
            if (eva == null)
            {
                continue;
            }
            DemoMode mode = DEMO_MODES[variant];
            int motionPreview = switch (mode)
            {
                case PHYSICS_WALK -> 1;
                case PHYSICS_RECOVERY -> 2;
                case PHYSICS_LIVE -> 3;
                case GROUNDED_WALK -> 4;
                case GROUNDED_RUN -> 5;
                case ORDINARY_ATTACK_CROSS_RIGHT -> 6;
                case ORDINARY_ATTACK_JAB_LEFT -> 7;
                case ORDINARY_ATTACK_HOOK_RIGHT -> 8;
                case ORDINARY_ATTACK_COMBO -> 9;
                default -> 0;
            };
            eva.setMotionLabPhysicsPreview(motionPreview);
            if (motionPreview > 0)
            {
                eva.setMotionLabDemoGait(false);
                int frame = Math.floorMod(DEMO_TICKS[variant]++, 160);
                double speed = switch (mode)
                {
                    case PHYSICS_WALK -> frame >= 20 && frame < 100
                            ? 0.525D : 0.0D;
                    // Exact 60-block-scale travel rates measured from the
                    // exported full-body cycles. They keep planted feet
                    // stationary instead of previewing the clip in place.
                    case GROUNDED_WALK -> 1.33D;
                    case GROUNDED_RUN -> 2.49D;
                    default -> 0.0D;
                };
                int direction = DEMO_DIRECTIONS[variant];
                if (eva.getZ() > 142.0D)
                {
                    direction = -1;
                }
                else if (eva.getZ() < -142.0D)
                {
                    direction = 1;
                }
                DEMO_DIRECTIONS[variant] = direction;
                float yaw = direction > 0 ? 0.0F : 180.0F;
                eva.setYRot(yaw);
                eva.yRotO = eva.yBodyRot = eva.yHeadRot = yaw;
                eva.move(MoverType.SELF,
                        new net.minecraft.world.phys.Vec3(
                                0.0D, 0.0D, speed * direction));
                eva.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
                continue;
            }
            if (mode == DemoMode.JUMP)
            {
                eva.setMotionLabDemoGait(false);
                if (eva.onGround())
                {
                    eva.triggerMotionLabDemoJump(1.45D);
                    DEMO_MODES[variant] = DemoMode.STOP;
                }
                continue;
            }
            if (mode == DemoMode.STOP)
            {
                // Manual pilots own sprint/crouch/prone while the autonomous
                // demo is stopped. Reasserting the demo state every server
                // tick used to erase a real stance one tick after its packet.
                if (eva.getControllingPassenger() == null)
                {
                    eva.setMotionLabDemoGait(false);
                }
                continue;
            }
            double speed = switch (mode)
            {
                case WALK -> 0.22D;
                case RUN -> 0.62D;
                default -> 0.0D;
            };
            int direction = DEMO_DIRECTIONS[variant];
            if (eva.getZ() > 142.0D)
            {
                direction = -1;
            }
            else if (eva.getZ() < -142.0D)
            {
                direction = 1;
            }
            DEMO_DIRECTIONS[variant] = direction;
            float yaw = direction > 0 ? 0.0F : 180.0F;
            eva.setYRot(yaw);
            eva.yRotO = eva.yBodyRot = eva.yHeadRot = yaw;
            eva.setMotionLabDemoGait(mode == DemoMode.RUN);
            eva.move(MoverType.SELF,
                    new net.minecraft.world.phys.Vec3(
                            0.0D, 0.0D, speed * direction));
            eva.setDeltaMovement(net.minecraft.world.phys.Vec3.ZERO);
        }
        return true;
    }

    public static boolean setDemo(ServerLevel level, int variant,
                                  String rawMode)
    {
        if (!isMotionLab(level) || variant < 0 || variant >= 3)
        {
            return false;
        }
        DemoMode mode = switch (rawMode.toLowerCase())
        {
            case "stop", "idle" -> DemoMode.STOP;
            case "walk" -> DemoMode.WALK;
            case "run", "sprint" -> DemoMode.RUN;
            case "jump" -> DemoMode.JUMP;
            case "physics", "physics_walk", "preview" ->
                    DemoMode.PHYSICS_WALK;
            case "physics_recovery", "recovery" ->
                    DemoMode.PHYSICS_RECOVERY;
            case "live", "physics_live", "policy", "livereset",
                    "livepush" ->
                    DemoMode.PHYSICS_LIVE;
            case "attack_b", "attack_cross", "attack_right",
                    "ordinary_attack_cross_right", "ordinary_attack_right",
                    "batter_right", "ordinary_batter_right" ->
                    DemoMode.ORDINARY_ATTACK_CROSS_RIGHT;
            case "attack_a", "attack_jab", "jab_left",
                    "ordinary_attack_jab_left" ->
                    DemoMode.ORDINARY_ATTACK_JAB_LEFT;
            case "attack_c", "attack_hook", "hook_right",
                    "ordinary_attack_hook_right" ->
                    DemoMode.ORDINARY_ATTACK_HOOK_RIGHT;
            case "attack_combo", "combo" -> DemoMode.ORDINARY_ATTACK_COMBO;
            default -> null;
        };
        if (mode == null)
        {
            return false;
        }
        DEMO_MODES[variant] = mode;
        DEMO_TICKS[variant] = 0;
        if (rawMode.equalsIgnoreCase("live")
                || rawMode.equalsIgnoreCase("physics_live")
                || rawMode.equalsIgnoreCase("policy")
                || rawMode.equalsIgnoreCase("livereset"))
        {
            EvaLivePhysicsControl.reset(variant);
        }
        else if (rawMode.equalsIgnoreCase("livepush"))
        {
            EvaLivePhysicsControl.lateralImpulse(variant, -0.5F);
        }
        return true;
    }

    public static EvaUnit01Entity unit(ServerLevel level, int variant)
    {
        return level.getEntitiesOfClass(EvaUnit01Entity.class, ARENA,
                        eva -> eva.isAlive()
                                && eva.getTags().contains(ENTITY_TAG)
                                && !eva.isExperimentalUnit()
                                && eva.getUnitVariant() == variant)
                .stream().findFirst().orElse(null);
    }

    /** The UN unit put on the lab's fourth pad by {@link #enterUnR63}, if there is one. */
    public static EvaUnit01Entity unUnitR63(ServerLevel level)
    {
        return level.getEntitiesOfClass(EvaUnit01Entity.class, ARENA,
                        eva -> eva.isAlive()
                                && eva.getTags().contains(ENTITY_TAG)
                                && eva.isExperimentalUnit())
                .stream().findFirst().orElse(null);
    }

    /**
     * Review only: a UN unit (serial 0 or 1) on a pad of its own between Unit-01 and Unit-02,
     * with the player aboard. The three lab units stay where they are; a UN unit left by an
     * earlier run is replaced, and a lab reset removes it like every other unit in the arena.
     */
    public static boolean enterUnR63(ServerPlayer player, int serial)
    {
        ServerLevel level = player.serverLevel();
        if (!setup(level, false))
        {
            return false;
        }
        level.getEntitiesOfClass(EvaUnit01Entity.class, ARENA,
                EvaUnit01Entity::isExperimentalUnit).forEach(EvaUnit01Entity::discard);
        var eva = ModEntities.EVA_PROTOTYPE.get().create(level);
        if (eva == null)
        {
            return false;
        }
        eva.setUNSerial(serial);
        eva.addTag(ENTITY_TAG);
        eva.prepareForMotionLab();
        eva.moveTo((UNIT_X[1] + UNIT_X[2]) / 2 + 0.5D, FLOOR_Y + 1.0D,
                UNIT_Z + 0.5D, 0.0F, 0.0F);
        eva.yRotO = eva.yBodyRot = eva.yHeadRot = 0.0F;
        level.addFreshEntity(eva);
        if (player.isPassenger())
        {
            player.stopRiding();
        }
        player.teleportTo(level, eva.getX(), eva.getY() + 2, eva.getZ() + 20,
                eva.getYRot(), 0);
        return eva.boardFromExternalPlug(player, 100);
    }

    public static boolean enter(ServerPlayer player, int variant)
    {
        ServerLevel level = player.serverLevel();
        if (!setup(level, false))
        {
            return false;
        }
        EvaUnit01Entity eva = unit(level, variant);
        if (eva == null)
        {
            return false;
        }
        // Manual piloting and the autonomous lane must never own the same
        // chassis. A previously selected RUN demo otherwise keeps translating
        // the EVA and overwriting gait data after the player boards it.
        DEMO_MODES[variant] = DemoMode.STOP;
        DEMO_TICKS[variant] = 0;
        eva.setMotionLabPhysicsPreview(0);
        eva.setMotionLabDemoGait(false);
        if (player.isPassenger())
        {
            player.stopRiding();
        }
        eva.ejectPassengers();
        eva.prepareForMotionLab();
        // A remote mount can leave both rider and vehicle outside ticking range:
        // the EVA cannot move the rider until its new chunk starts ticking.
        // This command is restricted to the disposable lab; bring the player
        // into that chunk before establishing the ordinary passenger relation.
        player.teleportTo(level, eva.getX(), eva.getY()+2, eva.getZ()+20,
                eva.getYRot(), 0);
        return eva.boardFromExternalPlug(player, 100);
    }

    public static boolean selectWeapon(ServerLevel level, int variant,
                                       int weapon)
    {
        EvaUnit01Entity eva = unit(level, variant);
        return eva != null && eva.selectMotionLabWeapon(weapon);
    }

    public static void teleportCamera(ServerPlayer player)
    {
        player.teleportTo(player.serverLevel(), 154.5D, -25.0D, 0.5D,
                90.0F, 12.0F);
    }

    private static void ensureUnits(ServerLevel level, boolean force)
    {
        List<EvaUnit01Entity> all = level.getEntitiesOfClass(
                EvaUnit01Entity.class, ARENA, EvaUnit01Entity::isAlive);
        List<EvaUnit01Entity> existing = new java.util.ArrayList<>();
        if (force)
        {
            all.forEach(EvaUnit01Entity::discard);
        }
        else
        {
            for (EvaUnit01Entity eva : all)
            {
                if (eva.getTags().contains(ENTITY_TAG))
                {
                    existing.add(eva);
                }
                else
                {
                    // The flat template historically contained one untagged
                    // trio. In this disposable world those are not campaign
                    // assets; keeping them made every reviewed motion appear
                    // three times and collision-launched the tagged unit.
                    eva.discard();
                }
            }
        }
        for (int variant = 0; variant < 3; variant++)
        {
            int wanted = variant;
            List<EvaUnit01Entity> matches = existing.stream()
                    .filter(candidate -> !candidate.isExperimentalUnit()
                            && candidate.getUnitVariant() == wanted)
                    .toList();
            EvaUnit01Entity eva = matches.isEmpty() ? null : matches.get(0);
            matches.stream().skip(1).forEach(EvaUnit01Entity::discard);
            if (eva == null)
            {
                eva = create(level, variant);
            }
            if (eva == null)
            {
                continue;
            }
            eva.addTag(ENTITY_TAG);
            eva.prepareForMotionLab();
            eva.moveTo(UNIT_X[variant] + 0.5D, FLOOR_Y + 1.0D,
                    UNIT_Z + 0.5D, 0.0F, 0.0F);
            eva.yRotO = eva.yBodyRot = eva.yHeadRot = 0.0F;
            if (!eva.isAddedToWorld())
            {
                level.addFreshEntity(eva);
            }
        }
    }

    private static EvaUnit01Entity create(ServerLevel level, int variant)
    {
        EntityType<EvaUnit01Entity> type = switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> ModEntities.EVA_UNIT00.get();
            case EvaUnit01Entity.UNIT_02 -> ModEntities.EVA_UNIT02.get();
            default -> ModEntities.EVA_UNIT01.get();
        };
        return type.create(level);
    }

    private static void buildArena(ServerLevel level)
    {
        BlockState floor = Blocks.GRAY_CONCRETE.defaultBlockState();
        BlockState road = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        BlockState white = Blocks.WHITE_CONCRETE.defaultBlockState();
        BlockState orange = Blocks.ORANGE_CONCRETE.defaultBlockState();
        BlockState red = Blocks.RED_CONCRETE.defaultBlockState();

        fill(level, -170, FLOOR_Y, -170, 170, FLOOR_Y, 170, floor);
        fill(level, -18, FLOOR_Y, -160, 18, FLOOR_Y, 160, road);
        fill(level, -160, FLOOR_Y, -18, 160, FLOOR_Y, 18, road);

        // Distance and centre-line marks remain readable beneath a 60-block EVA.
        for (int z = -152; z <= 152; z += 16)
        {
            fill(level, -1, FLOOR_Y + 1, z, 1, FLOOR_Y + 1, z, Blocks.AIR.defaultBlockState());
            fill(level, -1, FLOOR_Y, z, 1, FLOOR_Y, z, white);
        }
        for (int x = -152; x <= 152; x += 16)
        {
            fill(level, x, FLOOR_Y + 1, -1, x, FLOOR_Y + 1, 1, Blocks.AIR.defaultBlockState());
            fill(level, x, FLOOR_Y, -1, x, FLOOR_Y, 1, white);
        }
        for (int variant = 0; variant < 3; variant++)
        {
            int x = UNIT_X[variant];
            BlockState accent = switch (variant)
            {
                case 0 -> orange;
                case 2 -> red;
                default -> Blocks.PURPLE_CONCRETE.defaultBlockState();
            };
            fill(level, x - 21, FLOOR_Y + 1, UNIT_Z - 21,
                    x + 21, FLOOR_Y + 2, UNIT_Z + 21, Blocks.AIR.defaultBlockState());
            fill(level, x - 21, FLOOR_Y, UNIT_Z - 21,
                    x + 21, FLOOR_Y, UNIT_Z + 21, road);
            for (int d = -21; d <= 21; d++)
            {
                set(level, new BlockPos(x - 21, FLOOR_Y, UNIT_Z + d), accent);
                set(level, new BlockPos(x + 21, FLOOR_Y, UNIT_Z + d), accent);
                set(level, new BlockPos(x + d, FLOOR_Y, UNIT_Z - 21), accent);
                set(level, new BlockPos(x + d, FLOOR_Y, UNIT_Z + 21), accent);
            }
        }

        // Broad banked-turn reference ring. It is visual, not a collision rail.
        for (int x = -110; x <= 110; x++)
        {
            for (int z = -110; z <= 110; z++)
            {
                double radius = Math.sqrt(x * x + z * z);
                if (radius >= 86.0D && radius <= 96.0D)
                {
                    set(level, new BlockPos(x, FLOOR_Y + 1, z), Blocks.AIR.defaultBlockState());
                    set(level, new BlockPos(x, FLOOR_Y + 2, z), Blocks.AIR.defaultBlockState());
                    set(level, new BlockPos(x, FLOOR_Y, z), road);
                }
                if (radius >= 90.5D && radius <= 91.5D)
                {
                    set(level, new BlockPos(x, FLOOR_Y, z), white);
                }
            }
        }

        // Four wide terraces expose step-up, knee compression and foot plant.
        for (int step = 0; step < 5; step++)
        {
            int z0 = -72 + step * 18;
            fill(level, 112, FLOOR_Y + 1, z0,
                    154, FLOOR_Y + 1 + step, z0 + 17, road);
        }

        // Three 40-block firing panels at the far end of the main runway.
        for (int x : UNIT_X)
        {
            fill(level, x - 15, FLOOR_Y + 1, 158,
                    x + 15, FLOOR_Y + 42, 160,
                    Blocks.BLACK_CONCRETE.defaultBlockState());
            fill(level, x - 11, FLOOR_Y + 7, 157,
                    x + 11, FLOOR_Y + 35, 157, white);
            fill(level, x - 3, FLOOR_Y + 17, 156,
                    x + 3, FLOOR_Y + 25, 156, red);
        }

        // Elevated clear-glass observer booth outside the turn ring.
        fill(level, 145, -31, -12, 164, -31, 12, road);
        fill(level, 145, -30, -12, 145, -18, 12,
                ModBlocks.CLEAR_GLASS.get().defaultBlockState());
        fill(level, 164, -30, -12, 164, -18, 12,
                Blocks.BLACK_CONCRETE.defaultBlockState());
        fill(level, 145, -30, -12, 164, -18, -12,
                ModBlocks.CLEAR_GLASS.get().defaultBlockState());
        fill(level, 145, -30, 12, 164, -18, 12,
                ModBlocks.CLEAR_GLASS.get().defaultBlockState());
        fill(level, 145, -17, -12, 164, -17, 12,
                Blocks.BLACK_CONCRETE.defaultBlockState());

        set(level, MARKER, Blocks.LODESTONE.defaultBlockState());
    }

    private static void fill(ServerLevel level, int x0, int y0, int z0,
                             int x1, int y1, int z1, BlockState state)
    {
        BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        for (int y = Math.min(y0, y1); y <= Math.max(y0, y1); y++)
        {
            for (int z = Math.min(z0, z1); z <= Math.max(z0, z1); z++)
            {
                for (int x = Math.min(x0, x1); x <= Math.max(x0, x1); x++)
                {
                    cursor.set(x, y, z);
                    level.setBlock(cursor, state, Block.UPDATE_CLIENTS);
                }
            }
        }
    }

    private static void set(ServerLevel level, BlockPos position,
                            BlockState state)
    {
        level.setBlock(position, state, Block.UPDATE_CLIENTS);
    }

    private enum DemoMode
    {
        STOP,
        WALK,
        RUN,
        JUMP,
        PHYSICS_WALK,
        PHYSICS_RECOVERY,
        PHYSICS_LIVE,
        GROUNDED_WALK,
        GROUNDED_RUN,
        ORDINARY_ATTACK_CROSS_RIGHT,
        ORDINARY_ATTACK_JAB_LEFT,
        ORDINARY_ATTACK_HOOK_RIGHT,
        ORDINARY_ATTACK_COMBO
    }
}
