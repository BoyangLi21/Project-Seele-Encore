package com.projectseele.world;

import com.projectseele.entity.NervArmamentStationEntity;
import java.util.ArrayList;
import java.util.List;

/**
 * The rules of a spare-weapon tower (the A-1 armament buildings of Tokyo-3) that need no world.
 *
 * <p>A tower hands out its weapon in one of two runs. With the city raised the building stands on its lot: the
 * roof locks lift, the door goes up and the weapon stands behind it. With the city lowered the lot is flat: a pod
 * dressed like the building's top rises through the lot's hatch, as the armament lift stations do.</p>
 */
public final class ArmamentTowerLogicR64
{
    /** A run, or the city's settled state. NONE: no run, or the city is not at rest at either end. */
    public static final int NONE = 0, LOWERED = 1, RAISED = 2;
    /** The lot of a lifting tower: 19 by 19, the building one block inside it. */
    public static final int HALF = 9;
    /** The pod of the lowered run: floor, forty rows of wall, roof slab. */
    public static final int POD_HEIGHT = 42;
    /** Deep enough that the guides on the pod's roof stay under the hatch while it is stowed. */
    public static final int POD_TRAVEL = 45;

    /** A lot by its centre block: the hatch layer is at {@code baseY}, the standing building's rows start above it. */
    public record Lot(int cx, int baseY, int cz) {}
    /** The door: {@code width} cells centred on the wall, {@code height} rows from {@code bottom} above the base. */
    public record Door(int width, int height, int bottom)
    {
        public Door
        {
            if (width < 1 || width > 2 * HALF - 3 || width % 2 == 0 || height < 1 || bottom < 1)
                throw new IllegalArgumentException("A tower door is an odd width inside the wall, at least one row above the floor");
        }
    }

    /**
     * The city's settled state from the lift's status. A trip that is queued, under way, being reloaded or faulted
     * is none of the two: a tower starts nothing then.
     */
    public static int cityMode(String phase, int depth, int maximum)
    {
        if (phase == null) return NONE;
        boolean settled = phase.equals("IDLE") || phase.equals("RIGID_DISABLED") || phase.startsWith("RIGID_IDLE");
        if (!settled) return NONE;
        return depth == 0 ? RAISED : depth == maximum ? LOWERED : NONE;
    }

    /** A trip that has been asked for and has not begun: towers that are out may still finish coming in. */
    public static boolean tripWaiting(String phase)
    {
        return phase != null && (phase.startsWith("RIGID_QUEUED") || phase.startsWith("REVERSAL_QUEUED"));
    }

    /**
     * Whether the blocks a run takes out are out in this state: the lot's hatch for the whole lowered run, the
     * door from the moment it starts to rise until it is down again.
     */
    public static boolean cellsOut(int run, int state)
    {
        if (run == LOWERED) return state != NervArmamentStationEntity.STOWED;
        if (run == RAISED)
            return state == NervArmamentStationEntity.DOOR_OPENING || state == NervArmamentStationEntity.READY
                    || state == NervArmamentStationEntity.EMPTY || state == NervArmamentStationEntity.DOOR_CLOSING;
        return false;
    }

    /** After the first phase: the raised run has no pod to lift, its locks lead straight to the door. */
    public static int afterOpening(int run)
    {
        return run == RAISED ? NervArmamentStationEntity.DOOR_OPENING : NervArmamentStationEntity.RISING;
    }

    /** After the door is down: the raised run has no pod to lower. */
    public static int afterDoorClosing(int run)
    {
        return run == RAISED ? NervArmamentStationEntity.CLOSING : NervArmamentStationEntity.LOWERING;
    }

    /** Ticks from the call to READY. */
    public static int deployTicks(int run, int hatch, int rise, int door, int lock, int raisedDoor)
    {
        return run == RAISED ? lock + raisedDoor : hatch + rise + door;
    }

    /** Ticks from the weapon being taken to STOWED. */
    public static int retractTicks(int run, int hold, int hatch, int lower, int door, int lock, int raisedDoor)
    {
        return run == RAISED ? hold + raisedDoor + lock : hold + door + lower + hatch;
    }

    /**
     * Where a phase of {@code ticks} stands when it is turned round after {@code elapsed} ticks into a phase of
     * {@code reverseTicks}: the eased progress carries on from where it was instead of jumping to the far end.
     */
    public static int reversedTicks(int elapsed, int ticks, int reverseTicks)
    {
        double done = Math.max(0, Math.min(1, elapsed / (double)Math.max(1, ticks)));
        return (int)Math.round((1 - done) * reverseTicks);
    }

    /** A tower left ready with nobody taking the weapon comes in after the limit; the count does not run in combat. */
    public static boolean idleRecall(int readyTicks, int limitTicks, boolean combat)
    {
        return limitTicks > 0 && !combat && readyTicks >= limitTicks;
    }

    /** Facing as Minecraft counts it: 0 south (+z), 1 west (-x), 2 north (-z), 3 east (+x). */
    public static int stepX(int facing) { return facing == 1 ? -1 : facing == 3 ? 1 : 0; }
    public static int stepZ(int facing) { return facing == 0 ? 1 : facing == 2 ? -1 : 0; }

    /** The door's cells {x, y, z}, on the building's wall (one in from the lot's edge) on the facing side. */
    public static List<int[]> doorCells(Lot lot, int facing, Door door)
    {
        List<int[]> cells = new ArrayList<>(door.width() * door.height());
        int out = HALF - 1, side = door.width() / 2;
        for (int row = 0; row < door.height(); row++)
            for (int across = -side; across <= side; across++)
            {
                int x = lot.cx() + stepX(facing) * out + (stepX(facing) == 0 ? across : 0);
                int z = lot.cz() + stepZ(facing) * out + (stepZ(facing) == 0 ? across : 0);
                cells.add(new int[]{x, lot.baseY() + door.bottom() + row, z});
            }
        return cells;
    }

    /**
     * The weapon bay behind the door: the door's width, {@code depth} deep, from the door's first row to two rows
     * above its last. A building has a bay only if it was made for this, which is how one is told from the rest.
     */
    public static List<int[]> bayCells(Lot lot, int facing, Door door, int depth)
    {
        List<int[]> cells = new ArrayList<>(door.width() * depth * (door.height() + 2));
        int side = door.width() / 2;
        for (int row = 0; row < door.height() + 2; row++)
            for (int back = 1; back <= depth; back++)
                for (int across = -side; across <= side; across++)
                {
                    int out = HALF - 1 - back;
                    int x = lot.cx() + stepX(facing) * out + (stepX(facing) == 0 ? across : 0);
                    int z = lot.cz() + stepZ(facing) * out + (stepZ(facing) == 0 ? across : 0);
                    cells.add(new int[]{x, lot.baseY() + door.bottom() + row, z});
                }
        return cells;
    }

    /** The cells {x, y, z} of the lot's hatch that the pod comes up through: all but the outer ring. */
    public static List<int[]> hatchCells(Lot lot)
    {
        int out = HALF - 1;
        List<int[]> cells = new ArrayList<>((2 * out + 1) * (2 * out + 1));
        for (int x = -out; x <= out; x++)
            for (int z = -out; z <= out; z++)
                cells.add(new int[]{lot.cx() + x, lot.baseY(), lot.cz() + z});
        return cells;
    }

    /** The cells a run takes out. */
    public static List<int[]> cells(int run, Lot lot, int facing, Door door)
    {
        return run == RAISED ? doorCells(lot, facing, door) : run == LOWERED ? hatchCells(lot) : List.of();
    }

    /**
     * The nearest tower to a point among those that can be used; -1 if none can.
     * {@code positions} holds x and z per tower.
     */
    public static int nearest(double x, double z, double[][] positions, boolean[] usable)
    {
        int best = -1;
        double bestDistance = Double.POSITIVE_INFINITY;
        for (int i = 0; i < positions.length; i++)
        {
            if (!usable[i]) continue;
            double dx = positions[i][0] - x, dz = positions[i][1] - z, distance = dx * dx + dz * dz;
            if (distance < bestDistance) { bestDistance = distance; best = i; }
        }
        return best;
    }

    /** One line for the command room's wall: how many towers are ready, moving or waiting for the city. */
    public static String summary(int[] states, int waiting)
    {
        int ready = 0, moving = 0;
        for (int state : states)
        {
            if (state == NervArmamentStationEntity.READY) ready++;
            else if (state != NervArmamentStationEntity.STOWED) moving++;
        }
        if (ready > 0) return "READY " + ready + "/" + states.length;
        if (moving > 0) return "MOVING " + moving + "/" + states.length;
        if (waiting > 0) return "WAIT CITY";
        return "STOWED";
    }

    private ArmamentTowerLogicR64() {}
}
