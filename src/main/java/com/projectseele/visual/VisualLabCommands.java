package com.projectseele.visual;

import java.util.UUID;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.MassProductionEvaEntity;
import com.projectseele.event.ThirdImpactDirector;
import com.projectseele.fx.TreeOfLifeLayout;
import com.projectseele.network.ClientboundVisualCapturePacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.EvaMotionLabDirector;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/** Deterministic development arena and pose controls for visual regression. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class VisualLabCommands
{
    private static final String[] POSES = {
            "normal", "idle", "walk_contact", "run_contact", "jump", "fall",
            "crouch", "crouch_walk", "prone", "crawl", "prone_cannon",
            "knife_ready", "knife_windup", "knife_contact", "knife_recovery",
            "lance_ready", "lance_windup", "lance_contact", "lance_recovery", "cannon", "rifle",
            "live_melee", "live_knife", "live_knife_heavy", "live_lance",
            "live_rifle", "live_jump"
    };
    private static final String[] MASS_POSES = {
            "normal", "idle", "move", "attack", "revive", "ritual"
    };
    private static final SuggestionProvider<CommandSourceStack> POSE_SUGGESTIONS =
            (context, builder) -> SharedSuggestionProvider.suggest(POSES, builder);
    private static final SuggestionProvider<CommandSourceStack> MASS_POSE_SUGGESTIONS =
            (context, builder) -> SharedSuggestionProvider.suggest(MASS_POSES, builder);

    private VisualLabCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher = event.getDispatcher();
        dispatcher.register(Commands.literal("seele")
                .requires(source -> source.hasPermission(2))
                .then(Commands.literal("visual")
                        .then(Commands.literal("setup").executes(context -> setup(context.getSource())))
                        .then(Commands.literal("spawn")
                                .then(Commands.literal("unit01")
                                        .executes(context -> spawn(context.getSource(), "unit01")))
                                .then(Commands.literal("unit00")
                                        .executes(context -> spawn(context.getSource(), "unit00")))
                                .then(Commands.literal("unit02")
                                        .executes(context -> spawn(context.getSource(), "unit02")))
                                .then(Commands.literal("mass")
                                        .executes(context -> spawnMass(context.getSource()))))
                        .then(Commands.literal("impact")
                                .executes(context -> impact(context.getSource())))
                        .then(Commands.literal("pose")
                                .then(Commands.argument("name", StringArgumentType.word())
                                        .suggests(POSE_SUGGESTIONS)
                                        .executes(context -> pose(context.getSource(),
                                                StringArgumentType.getString(context, "name"))))
                                .then(Commands.literal("mass")
                                        .then(Commands.argument("state", StringArgumentType.word())
                                                .suggests(MASS_POSE_SUGGESTIONS)
                                                .executes(context -> poseMass(context.getSource(),
                                                        StringArgumentType.getString(
                                                                context, "state"))))))
                        .then(Commands.literal("capture")
                                .then(Commands.literal("all")
                                        .executes(context -> capture(context.getSource())))
                                .then(Commands.literal("mass")
                                        .executes(context -> captureMass(context.getSource()))))));
    }

    static int setup(CommandSourceStack source) throws CommandSyntaxException
    {
        return setup(source, "unit01");
    }

    static int setup(CommandSourceStack source, String unitName) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.serverLevel();
        // Persistent Visual Lab saves can reopen with the player still riding
        // a subject from the previous matrix. Detach before cleanup/teleport so
        // that old vehicle cannot follow the player into the new capture.
        player.stopRiding();
        // This command is for the dedicated Visual Lab world. A fixed isolated
        // origin keeps captures independent from the player's previous
        // position, old high-altitude lab platforms, terrain and cloud height.
        BlockPos centre = new BlockPos(4096, 64, 4096);
        level.setDayTime(6000L);
        level.setWeatherParameters(6000, 0, false, false);

        boolean foundationVideo = Boolean.getBoolean(
                "projectseele.foundationVideoCapture");
        int minimumX = foundationVideo ? -60 : -45;
        int maximumX = foundationVideo ? 180 : 45;
        int minimumZ = foundationVideo ? -300 : -45;
        int maximumZ = foundationVideo ? 60 : 45;
        for (int x = minimumX; x <= maximumX; x++)
        {
            for (int z = minimumZ; z <= maximumZ; z++)
            {
                boolean major = x % 10 == 0 || z % 10 == 0;
                level.setBlock(centre.offset(x, 0, z),
                        major ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                                : Blocks.GRAY_CONCRETE.defaultBlockState(), 3);
            }
        }
        // Purge the old foreground fixtures from persistent Visual Lab saves.
        // Their orange/white blocks could line up with an EVA limb or head in
        // the close cameras and masquerade as weapon-dependent body texture.
        for (int y = 1; y <= 30; y++)
        {
            level.setBlock(centre.offset(-32, y, -30), Blocks.AIR.defaultBlockState(), 3);
            level.setBlock(centre.offset(32, y, -30), Blocks.AIR.defaultBlockState(), 3);
        }
        for (int y = 1; y <= 22; y++)
        {
            level.setBlock(centre.offset(26, y, 18), Blocks.AIR.defaultBlockState(), 3);
            level.setBlock(centre.offset(26, y, 34), Blocks.AIR.defaultBlockState(), 3);
        }
        for (int z = -8; z <= 8; z++)
        {
            level.setBlock(centre.offset(26, 22, 26 + z), Blocks.AIR.defaultBlockState(), 3);
        }
        for (int step = 0; step < 5; step++)
        {
            for (int x = 0; x <= step; x++)
            {
                level.setBlock(centre.offset(-28 + x, 1 + step, 24),
                        Blocks.AIR.defaultBlockState(), 3);
            }
        }
        // Keep the centre marker flush with the floor. The old lodestone lived
        // in the subject's feet volume, pushed every EVA up by one block and
        // also masqueraded as a launch-silo bed during manual interaction.
        level.setBlock(centre, Blocks.YELLOW_CONCRETE.defaultBlockState(), 3);
        level.setBlock(centre.above(), Blocks.AIR.defaultBlockState(), 3);
        removeLabEntities(level, centre);
        Entity subject = "mass".equals(unitName)
                ? createMass(level, centre.above())
                : createUnit(level, centre.above(), unitName);
        // Do not place a visible ArmorStand in a regression arena. Close
        // cameras magnify a two-block wooden target until its orange limbs
        // cover the 24-block EVA and look like weapon-dependent body paint.
        // The concrete height rulers and door frame provide scale without a
        // foreground entity that can contaminate screenshots.
        player.teleportTo(level, centre.getX() + 0.5D, centre.getY() + 2.0D,
                centre.getZ() + 42.5D, 180.0F, 5.0F);
        source.sendSuccess(() -> Component.literal(
                "Visual Lab ready; " + unitName + " id=" + subject.getId()), false);
        return 1;
    }

    private static int spawn(CommandSourceStack source, String unitName) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        BlockPos centre = player.blockPosition();
        EvaUnit01Entity unit = createUnit(player.serverLevel(), centre, unitName);
        source.sendSuccess(() -> Component.literal(
                "Visual " + unitName + " spawned: " + unit.getId()), false);
        return 1;
    }

    private static int spawnMass(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        MassProductionEvaEntity mass = createMass(player.serverLevel(), player.blockPosition());
        source.sendSuccess(() -> Component.literal(
                "Visual mass-production EVA spawned: " + mass.getId()), false);
        return 1;
    }

    private static EvaUnit01Entity createUnit(ServerLevel level, BlockPos position, String unitName)
    {
        EvaUnit01Entity unit = switch (unitName)
        {
            case "unit00" -> ModEntities.EVA_UNIT00.get().create(level);
            case "unit02" -> ModEntities.EVA_UNIT02.get().create(level);
            case "unit01" -> ModEntities.EVA_UNIT01.get().create(level);
            default -> throw new IllegalArgumentException("Unknown visual EVA: " + unitName);
        };
        if (unit == null)
        {
            throw new IllegalStateException("Unit-01 entity creation failed");
        }
        unit.moveTo(position.getX() + 0.5D, position.getY(), position.getZ() + 0.5D, 0.0F, 0.0F);
        unit.setNoAi(true);
        // The lab is a render fixture, not a combat encounter. Ambient mobs
        // repeatedly hitting the subject leave Minecraft's orange damage
        // overlay on selected materials and make texture/pose review useless.
        unit.setInvulnerable(true);
        unit.clearFire();
        unit.setDeltaMovement(Vec3.ZERO);
        unit.setPersistenceRequired();
        unit.addTag(EvaMotionLabDirector.ENTITY_TAG);
        unit.prepareForMotionLab();
        unit.setVisualPose(EvaUnit01Entity.VISUAL_IDLE);
        level.addFreshEntity(unit);
        return unit;
    }

    private static MassProductionEvaEntity createMass(ServerLevel level, BlockPos position)
    {
        MassProductionEvaEntity mass = ModEntities.MASS_PRODUCTION_EVA.get().create(level);
        if (mass == null)
        {
            throw new IllegalStateException("Mass Production EVA entity creation failed");
        }
        mass.moveTo(position.getX() + 0.5D, position.getY(), position.getZ() + 0.5D,
                0.0F, 0.0F);
        mass.setNoAi(true);
        mass.setNoGravity(true);
        mass.setInvulnerable(true);
        mass.clearFire();
        mass.setDeltaMovement(Vec3.ZERO);
        mass.setVisualPose(MassProductionEvaEntity.VISUAL_IDLE);
        mass.setPersistenceRequired();
        level.addFreshEntity(mass);
        return mass;
    }

    /** Instantly stages the full inverted Tree for a repeatable front capture. */
    static int impact(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        ServerLevel level = player.serverLevel();
        EvaUnit01Entity unit = nearestUnit(player);
        player.stopRiding();
        // A dark, clear sky is the deterministic contrast plate for the red
        // glyph; the story event itself still respects the world's live time.
        level.setDayTime(18000L);
        level.setWeatherParameters(6000, 0, false, false);

        Vec3 unitBase = unit.position();
        Vec3 origin = new Vec3(unitBase.x, unitBase.y + 32.0D, unitBase.z);
        Vec3 toViewer = player.position().subtract(origin).multiply(1.0D, 0.0D, 1.0D);
        if (toViewer.lengthSqr() < 1.0E-4D)
        {
            toViewer = new Vec3(0.0D, 0.0D, 1.0D);
        }
        Vec3 front = toViewer.normalize();
        float treeYaw = (float) Mth.atan2(front.x, front.z);
        float evaYaw = TreeOfLifeLayout.frontFacingYawDegrees(treeYaw);
        Vec3 tiferet = TreeOfLifeLayout.worldNode(origin, treeYaw, TreeOfLifeLayout.TIFERET);

        unit.teleportTo(tiferet.x, tiferet.y - unit.getBbHeight() * 0.5D, tiferet.z);
        unit.setYRot(evaYaw);
        unit.setXRot(0.0F);
        unit.yRotO = evaYaw;
        unit.xRotO = 0.0F;
        unit.yBodyRot = evaYaw;
        unit.yBodyRotO = evaYaw;
        unit.yHeadRot = evaYaw;
        unit.yHeadRotO = evaYaw;
        unit.setCrucified(true);
        unit.setNoAi(true);

        AABB ritualArea = new AABB(origin, origin).inflate(230.0D);
        level.getEntitiesOfClass(MassProductionEvaEntity.class, ritualArea,
                MassProductionEvaEntity::isRitualFormation).forEach(Entity::discard);
        ThirdImpactDirector.startVisualPreview(level, origin, treeYaw, true);

        // Keep the real player inside the view-distance square so all nine
        // vessel chunks remain tracked. The client uses its own farther
        // screenshot camera and does not need the server player at that point.
        Vec3 camera = origin.add(front.scale(300.0D))
                .add(0.0D, TreeOfLifeLayout.localY(TreeOfLifeLayout.TIFERET), 0.0D);
        Vec3 sight = tiferet.subtract(camera);
        float cameraYaw = (float) (Mth.atan2(sight.z, sight.x) * Mth.RAD_TO_DEG) - 90.0F;
        float cameraPitch = (float) -(Mth.atan2(sight.y, sight.horizontalDistance()) * Mth.RAD_TO_DEG);
        player.teleportTo(level, camera.x, camera.y, camera.z, cameraYaw, cameraPitch);
        source.sendSuccess(() -> Component.literal(
                "Third Impact visual ready: inverted tree, nine vessels, Unit-01 at Tiferet"), false);
        return 1;
    }

    static int pose(CommandSourceStack source, String name) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        return pose(source, name, nearestUnit(player));
    }

    static int pose(CommandSourceStack source, String name, UUID subjectId,
                    String expectedUnit) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        return pose(source, name, pinnedUnit(player, subjectId, expectedUnit));
    }

    private static int pose(CommandSourceStack source, String name, EvaUnit01Entity unit)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        removeVisualTargets(player.serverLevel(), unit.blockPosition());
        // End-to-end poses must use the same server-authoritative pilot path
        // as gameplay.  The old matrix sent control packets while the tester
        // stood forty blocks away, so damage/animation/jump requests were
        // correctly rejected and screenshots merely captured weapon-ready
        // idles. Force-mount only the explicit development live_* catalogue.
        if (name.startsWith("live_") && player.getVehicle() != unit)
        {
            if (!player.startRiding(unit, true))
            {
                throw new IllegalStateException(
                        "Visual live pose could not mount its pinned EVA subject");
            }
            ProjectSeele.LOGGER.info(
                    "Visual Lab mounted {} for authoritative {} input",
                    player.getGameProfile().getName(), name);
        }
        int visualPose = switch (name)
        {
            case "normal" -> EvaUnit01Entity.VISUAL_NORMAL;
            case "idle" -> EvaUnit01Entity.VISUAL_IDLE;
            case "walk_contact" -> EvaUnit01Entity.VISUAL_WALK_CONTACT;
            case "run_contact" -> EvaUnit01Entity.VISUAL_RUN_CONTACT;
            case "jump" -> EvaUnit01Entity.VISUAL_JUMP;
            case "fall" -> EvaUnit01Entity.VISUAL_FALL;
            case "knife_windup" -> EvaUnit01Entity.VISUAL_KNIFE_WINDUP;
            case "knife_contact" -> EvaUnit01Entity.VISUAL_KNIFE_CONTACT;
            case "knife_recovery" -> EvaUnit01Entity.VISUAL_KNIFE_RECOVERY;
            case "knife_ready" -> EvaUnit01Entity.VISUAL_KNIFE_READY;
            case "crouch" -> EvaUnit01Entity.VISUAL_CROUCH;
            case "crouch_walk" -> EvaUnit01Entity.VISUAL_CROUCH_WALK;
            case "prone" -> EvaUnit01Entity.VISUAL_PRONE;
            case "crawl" -> EvaUnit01Entity.VISUAL_CRAWL;
            case "prone_cannon" -> EvaUnit01Entity.VISUAL_PRONE_CANNON;
            case "lance_ready" -> EvaUnit01Entity.VISUAL_LANCE_READY;
            case "lance_windup" -> EvaUnit01Entity.VISUAL_LANCE_WINDUP;
            case "lance_contact" -> EvaUnit01Entity.VISUAL_LANCE_CONTACT;
            case "lance_recovery" -> EvaUnit01Entity.VISUAL_LANCE_RECOVERY;
            case "cannon" -> EvaUnit01Entity.VISUAL_CANNON;
            case "rifle" -> EvaUnit01Entity.VISUAL_RIFLE;
            case "crouch_knife_contact" -> EvaUnit01Entity.VISUAL_CROUCH_KNIFE_CONTACT;
            case "prone_knife_contact" -> EvaUnit01Entity.VISUAL_PRONE_KNIFE_CONTACT;
            case "crouch_lance_contact" -> EvaUnit01Entity.VISUAL_CROUCH_LANCE_CONTACT;
            case "prone_lance_contact" -> EvaUnit01Entity.VISUAL_PRONE_LANCE_CONTACT;
            case "n2_ready" -> EvaUnit01Entity.VISUAL_N2_READY;
            case "rifle_walk_contact" -> EvaUnit01Entity.VISUAL_RIFLE_WALK_CONTACT;
            case "crouch_rifle_contact" -> EvaUnit01Entity.VISUAL_CROUCH_RIFLE_CONTACT;
            case "prone_rifle" -> EvaUnit01Entity.VISUAL_PRONE_RIFLE;
            case "live_melee" -> EvaUnit01Entity.VISUAL_LIVE_MELEE;
            case "live_knife" -> EvaUnit01Entity.VISUAL_LIVE_KNIFE;
            case "live_lance" -> EvaUnit01Entity.VISUAL_LIVE_LANCE;
            case "live_rifle" -> EvaUnit01Entity.VISUAL_LIVE_RIFLE;
            case "live_knife_heavy" -> EvaUnit01Entity.VISUAL_LIVE_KNIFE_HEAVY;
            case "live_jump" -> EvaUnit01Entity.VISUAL_LIVE_JUMP;
            default -> throw new IllegalArgumentException("Unknown visual pose: " + name);
        };
        unit.setVisualPose(visualPose);
        unit.setYRot(0.0F);
        unit.setYBodyRot(0.0F);
        unit.setYHeadRot(0.0F);
        unit.setXRot(0.0F);
        unit.yRotO = 0.0F;
        unit.xRotO = 0.0F;
        unit.yBodyRotO = 0.0F;
        unit.yHeadRotO = 0.0F;
        source.sendSuccess(() -> Component.literal("Visual pose: " + name), false);
        return 1;
    }

    static int capture(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        return capture(source, nearestUnit(player));
    }

    static int capture(CommandSourceStack source, UUID subjectId,
                       String expectedUnit) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        return capture(source, pinnedUnit(player, subjectId, expectedUnit));
    }

    private static int capture(CommandSourceStack source, EvaUnit01Entity unit)
            throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        removeVisualTargets(player.serverLevel(), unit.blockPosition());
        if (player.getVehicle() != unit)
        {
            player.startRiding(unit, true);
        }
        player.setYRot(0.0F);
        player.setYHeadRot(0.0F);
        player.setXRot(0.0F);
        int requestedPose = unit.getVisualPose();
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundVisualCapturePacket(unit.getId(), requestedPose));
        if (Boolean.getBoolean("projectseele.foundationVideoCapture")
                && (requestedPose == EvaUnit01Entity.VISUAL_IDLE
                    || requestedPose == EvaUnit01Entity.VISUAL_WALK_CONTACT
                    || requestedPose == EvaUnit01Entity.VISUAL_RUN_CONTACT
                    || requestedPose == EvaUnit01Entity.VISUAL_LIVE_MELEE
                    || requestedPose == EvaUnit01Entity.VISUAL_LIVE_KNIFE
                    || requestedPose == EvaUnit01Entity.VISUAL_LIVE_JUMP))
        {
            unit.selectMotionLabWeapon(
                    requestedPose == EvaUnit01Entity.VISUAL_LIVE_KNIFE
                            ? EvaUnit01Entity.WEAPON_KNIFE
                            : EvaUnit01Entity.WEAPON_FISTS);
            // The packet retains the requested review label, while the actual
            // entity returns to normal gameplay authority before input fires.
            unit.setVisualPose(EvaUnit01Entity.VISUAL_NORMAL);
        }
        source.sendSuccess(() -> Component.literal(
                "Visual capture queued for " + unitName(unit)), false);
        return 1;
    }

    static int captureMass(CommandSourceStack source) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        MassProductionEvaEntity mass = nearestMass(player);
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player),
                new ClientboundVisualCapturePacket(mass.getId(), mass.getVisualPose()));
        source.sendSuccess(() -> Component.literal(
                "Visual capture queued for Mass Production EVA: "
                        + MassProductionEvaEntity.visualPoseName(mass.getVisualPose())), false);
        return 1;
    }

    static int poseMass(CommandSourceStack source, String name) throws CommandSyntaxException
    {
        ServerPlayer player = source.getPlayerOrException();
        MassProductionEvaEntity mass = nearestMass(player);
        int visualPose = switch (name)
        {
            case "normal" -> MassProductionEvaEntity.VISUAL_NORMAL;
            case "idle" -> MassProductionEvaEntity.VISUAL_IDLE;
            case "move" -> MassProductionEvaEntity.VISUAL_MOVE;
            case "attack" -> MassProductionEvaEntity.VISUAL_ATTACK;
            case "revive" -> MassProductionEvaEntity.VISUAL_REVIVE;
            case "ritual" -> MassProductionEvaEntity.VISUAL_RITUAL;
            default -> throw new IllegalArgumentException("Unknown mass-production pose: " + name);
        };
        mass.setVisualPose(visualPose);
        mass.setDeltaMovement(Vec3.ZERO);
        mass.setYRot(0.0F);
        mass.setYBodyRot(0.0F);
        mass.setYHeadRot(0.0F);
        mass.setXRot(0.0F);
        mass.yRotO = 0.0F;
        mass.xRotO = 0.0F;
        source.sendSuccess(() -> Component.literal(
                "Mass Production EVA visual pose: " + name), false);
        return 1;
    }

    private static EvaUnit01Entity nearestUnit(ServerPlayer player)
    {
        return player.serverLevel().getEntitiesOfClass(EvaUnit01Entity.class,
                        player.getBoundingBox().inflate(192.0D), Entity::isAlive).stream()
                .min((left, right) -> Double.compare(left.distanceToSqr(player), right.distanceToSqr(player)))
                .orElseThrow(() -> new IllegalStateException("No EVA within 192 blocks"));
    }

    static UUID findUnitId(ServerPlayer player, String expectedUnit)
    {
        return player.serverLevel().getEntitiesOfClass(EvaUnit01Entity.class,
                        player.getBoundingBox().inflate(192.0D), Entity::isAlive).stream()
                .filter(unit -> expectedUnit.equals(unitName(unit)))
                .min((left, right) -> Double.compare(
                        left.distanceToSqr(player), right.distanceToSqr(player)))
                .map(Entity::getUUID)
                .orElseThrow(() -> new IllegalStateException(
                        "No " + expectedUnit + " within 192 blocks"));
    }

    private static EvaUnit01Entity pinnedUnit(ServerPlayer player, UUID subjectId,
                                              String expectedUnit)
    {
        Entity entity = player.serverLevel().getEntity(subjectId);
        if (!(entity instanceof EvaUnit01Entity unit) || !unit.isAlive())
        {
            throw new IllegalStateException(
                    "Pinned Visual Lab EVA is missing: " + subjectId);
        }
        String actualUnit = unitName(unit);
        if (!expectedUnit.equals(actualUnit))
        {
            throw new IllegalStateException("Pinned Visual Lab EVA changed from "
                    + expectedUnit + " to " + actualUnit + ": " + subjectId);
        }
        return unit;
    }

    private static String unitName(EvaUnit01Entity unit)
    {
        return switch (unit.getUnitVariant())
        {
            case EvaUnit01Entity.UNIT_00 -> "unit00";
            case EvaUnit01Entity.UNIT_02 -> "unit02";
            default -> "unit01";
        };
    }

    private static MassProductionEvaEntity nearestMass(ServerPlayer player)
    {
        return player.serverLevel().getEntitiesOfClass(MassProductionEvaEntity.class,
                        player.getBoundingBox().inflate(192.0D), Entity::isAlive).stream()
                .min((left, right) -> Double.compare(left.distanceToSqr(player),
                        right.distanceToSqr(player)))
                .orElseThrow(() -> new IllegalStateException(
                        "No Mass Production EVA within 192 blocks"));
    }

    private static void removeLabEntities(ServerLevel level, BlockPos centre)
    {
        // Third-Impact vessels occupy the same X/Z lab cell but can reach
        // almost 190 blocks above the floor. A short cleanup box left their
        // upper Sephirot hanging over later cannon/first-person captures.
        AABB area = new AABB(centre).inflate(240.0D, 240.0D, 240.0D);
        level.getEntitiesOfClass(EvaUnit01Entity.class, area).forEach(Entity::discard);
        level.getEntitiesOfClass(MassProductionEvaEntity.class, area).forEach(Entity::discard);
        removeVisualTargets(level, centre);
    }

    /** Remove targets left in older Visual Lab saves before any new capture. */
    private static void removeVisualTargets(ServerLevel level, BlockPos centre)
    {
        AABB area = new AABB(centre).inflate(240.0D, 240.0D, 240.0D);
        level.getEntitiesOfClass(ArmorStand.class, area,
                stand -> stand.hasCustomName()
                        && "VISUAL TARGET".equals(stand.getCustomName().getString()))
                .forEach(Entity::discard);
    }
}
