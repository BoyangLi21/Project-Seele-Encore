package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervLiftDoorEntity;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Objects;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** Smooth visual overlay for every S20 lift landing door. */
public final class LiftSlidingDoorDirector
{
    public static final String MARKER =
            ".projectseele_lift_sliding_doors_r01.json";
    private static final int DOOR_DISTANCE = 4;
    private static final int WIDTH = 5;
    private static final int HEIGHT = 3;
    private static final Map<MinecraftServer, Boolean> ENABLED =
            new WeakHashMap<>();

    private LiftSlidingDoorDirector() {}

    public static boolean enabled(ServerLevel level)
    {
        MinecraftServer server = level.getServer();
        synchronized (ENABLED)
        {
            return ENABLED.computeIfAbsent(server, ignored ->
            {
                Path marker = server.getWorldPath(LevelResource.ROOT)
                        .resolve(MARKER);
                boolean present = Files.isRegularFile(marker);
                if (present)
                {
                    ProjectSeele.LOGGER.info(
                            "NERV smooth lift landing doors enabled");
                }
                return present;
            });
        }
    }

    /** Returns true when the smooth adapter owns this landing. */
    public static boolean setLandingDoor(ServerLevel level,
            S20PhysicalElevatorDirector.LiftSpec lift,
            S20PhysicalElevatorDirector.Landing landing, boolean open)
    {
        if (!enabled(level))
        {
            return false;
        }
        Direction lateral = landing.exit().getClockWise();
        BlockPos plane = landing.cabinCentre().relative(
                landing.exit(), DOOR_DISTANCE);
        int doorId = Objects.hash(lift.id(),
                landing.walkY(), landing.cabinCentre().getX(),
                landing.cabinCentre().getZ());
        NervLiftDoorEntity door = NervLiftDoorEntity.reconcile(
                level, doorId, lateral.getAxis() == Direction.Axis.X,
                WIDTH, HEIGHT,
                new Vec3(plane.getX() + 0.5D, plane.getY(),
                        plane.getZ() + 0.5D));
        if (door != null)
        {
            door.setOpen(open);
        }
        return true;
    }

    public static void resetRuntime()
    {
        synchronized (ENABLED)
        {
            ENABLED.clear();
        }
    }
}
