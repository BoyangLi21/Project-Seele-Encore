package com.projectseele.world;

import com.projectseele.entity.NervArmamentStationEntity;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Run with AllChecks: the rules of the spare-weapon towers. */
public final class ArmamentTowerLogicR64Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    private static final int STOWED = NervArmamentStationEntity.STOWED, OPENING = NervArmamentStationEntity.OPENING,
            RISING = NervArmamentStationEntity.RISING, READY = NervArmamentStationEntity.READY, EMPTY = NervArmamentStationEntity.EMPTY,
            LOWERING = NervArmamentStationEntity.LOWERING, CLOSING = NervArmamentStationEntity.CLOSING,
            DOOR_OPENING = NervArmamentStationEntity.DOOR_OPENING, DOOR_CLOSING = NervArmamentStationEntity.DOOR_CLOSING;
    private static final int NONE = ArmamentTowerLogicR64.NONE, LOWERED = ArmamentTowerLogicR64.LOWERED, RAISED = ArmamentTowerLogicR64.RAISED;

    public static void main(String[] args)
    {
        // Which end the city rests at, from the lift's own words.
        check(ArmamentTowerLogicR64.cityMode("RIGID_IDLE", 0, 312) == RAISED, "At rest with depth 0 the city is raised");
        check(ArmamentTowerLogicR64.cityMode("RIGID_IDLE", 312, 312) == LOWERED, "At rest at full depth the city is lowered");
        check(ArmamentTowerLogicR64.cityMode("RIGID_DISABLED", 312, 312) == LOWERED, "A lift that is switched off stays where it was saved");
        check(ArmamentTowerLogicR64.cityMode("RIGID_IDLE", 100, 312) == NONE, "A depth between the ends is neither");
        for (String phase : List.of("RIGID_QUEUED", "RIGID_QUEUED_OCCUPIED", "RIGID_PREPARE", "RIGID_MOVE", "RIGID_PLACE", "RIGID_FLUSH",
                "RIGID_LOADING", "RIGID_FAULT", "FAULT", "REVERSAL_QUEUED_ASCENT"))
            check(ArmamentTowerLogicR64.cityMode(phase, 0, 312) == NONE && ArmamentTowerLogicR64.cityMode(phase, 312, 312) == NONE,
                    "No tower starts while the lift says " + phase);
        check(ArmamentTowerLogicR64.cityMode(null, 0, 312) == NONE, "No status, no run");
        check(ArmamentTowerLogicR64.tripWaiting("RIGID_QUEUED") && ArmamentTowerLogicR64.tripWaiting("RIGID_QUEUED_BLOCKED")
                && !ArmamentTowerLogicR64.tripWaiting("RIGID_MOVE") && !ArmamentTowerLogicR64.tripWaiting("RIGID_IDLE"),
                "A trip waits only between being asked for and beginning");

        // The two runs.
        check(ArmamentTowerLogicR64.afterOpening(LOWERED) == RISING && ArmamentTowerLogicR64.afterDoorClosing(LOWERED) == LOWERING,
                "City lowered: hatch, lift, door, and back the same way");
        check(ArmamentTowerLogicR64.afterOpening(RAISED) == DOOR_OPENING && ArmamentTowerLogicR64.afterDoorClosing(RAISED) == CLOSING,
                "City raised: the locks lead straight to the door, there is no pod");
        check(ArmamentTowerLogicR64.deployTicks(LOWERED, 24, 100, 30, 24, 30) == 154, "Lowered, call to ready: 154 ticks as the lift stations");
        check(ArmamentTowerLogicR64.retractTicks(LOWERED, 30, 24, 80, 30, 24, 30) == 164, "Lowered, taken to stowed: 164 ticks");
        check(ArmamentTowerLogicR64.deployTicks(RAISED, 24, 100, 30, 24, 30) == 54, "Raised, call to ready: 54 ticks");
        check(ArmamentTowerLogicR64.retractTicks(RAISED, 30, 24, 80, 30, 24, 30) == 84, "Raised, taken to stowed: 84 ticks");

        // When the blocks are out.
        for (int state : new int[]{OPENING, RISING, DOOR_OPENING, READY, EMPTY, DOOR_CLOSING, LOWERING, CLOSING})
            check(ArmamentTowerLogicR64.cellsOut(LOWERED, state), "Lowered: the hatch is out for the whole run");
        check(!ArmamentTowerLogicR64.cellsOut(LOWERED, STOWED), "Lowered and stowed: the hatch is in");
        for (int state : new int[]{DOOR_OPENING, READY, EMPTY, DOOR_CLOSING})
            check(ArmamentTowerLogicR64.cellsOut(RAISED, state), "Raised: the door is out from its first move to its last");
        for (int state : new int[]{STOWED, OPENING, CLOSING})
            check(!ArmamentTowerLogicR64.cellsOut(RAISED, state), "Raised: while only the locks move the door is blocks");
        check(!ArmamentTowerLogicR64.cellsOut(NONE, READY), "No run takes nothing out");

        // Turning a phase round.
        check(ArmamentTowerLogicR64.reversedTicks(0, 30, 30) == 30, "A door that has not moved is shut at once");
        check(ArmamentTowerLogicR64.reversedTicks(30, 30, 30) == 0, "A door fully up comes all the way down");
        check(ArmamentTowerLogicR64.reversedTicks(10, 30, 30) == 20, "A door a third up has a third to come down");
        check(ArmamentTowerLogicR64.reversedTicks(50, 100, 80) == 40, "A pod halfway up is halfway through the shorter way down");
        check(24 + 80 + 30 == 134, "From ready, a tower is in after 134 ticks at most");

        // Coming in by itself.
        check(!ArmamentTowerLogicR64.idleRecall(3599, 3600, false) && ArmamentTowerLogicR64.idleRecall(3600, 3600, false),
                "A ready tower nobody uses comes in at the limit");
        check(!ArmamentTowerLogicR64.idleRecall(99999, 3600, true), "Not during combat");
        check(!ArmamentTowerLogicR64.idleRecall(99999, 0, false), "A limit of zero never recalls");

        // The door and the hatch of tower 28, centre (-10, 80, 140).
        var lot = new ArmamentTowerLogicR64.Lot(-10, 80, 140);
        var door = new ArmamentTowerLogicR64.Door(15, 38, 1);
        List<int[]> south = ArmamentTowerLogicR64.doorCells(lot, 0, door);
        check(south.size() == 15 * 38, "The door is 15 by 38");
        int minX = 999, maxX = -999, minY = 999, maxY = -999;
        Set<Long> seen = new HashSet<>();
        for (int[] cell : south)
        {
            check(cell[2] == 148, "A south door is on the wall one in from the lot's south edge");
            minX = Math.min(minX, cell[0]); maxX = Math.max(maxX, cell[0]);
            minY = Math.min(minY, cell[1]); maxY = Math.max(maxY, cell[1]);
            seen.add(((long)cell[0] << 40) ^ ((long)cell[1] << 20) ^ cell[2]);
        }
        check(minX == -17 && maxX == -3 && minY == 81 && maxY == 118, "It spans the building's inner width, from the first row above the floor");
        check(seen.size() == south.size(), "No cell twice");
        check(south.get(0)[1] == 81 && south.get(15)[1] == 82 && south.get(1)[0] == south.get(0)[0] + 1, "Cells run across, row by row from the bottom");
        for (int[] cell : ArmamentTowerLogicR64.doorCells(lot, 1, door)) check(cell[0] == -18 && cell[2] >= 133 && cell[2] <= 147, "West door");
        for (int[] cell : ArmamentTowerLogicR64.doorCells(lot, 2, door)) check(cell[2] == 132 && cell[0] >= -17 && cell[0] <= -3, "North door");
        for (int[] cell : ArmamentTowerLogicR64.doorCells(lot, 3, door)) check(cell[0] == -2 && cell[2] >= 133 && cell[2] <= 147, "East door");

        List<int[]> bay = ArmamentTowerLogicR64.bayCells(lot, 0, door, 5);
        check(bay.size() == 15 * 5 * 40, "The bay is the door's width, five deep and forty high");
        for (int[] cell : bay) check(cell[2] >= 143 && cell[2] <= 147 && cell[1] >= 81 && cell[1] <= 120 && cell[0] >= -17 && cell[0] <= -3, "The bay is right behind the door");

        List<int[]> hatch = ArmamentTowerLogicR64.hatchCells(lot);
        check(hatch.size() == 17 * 17, "The pod comes up through the hatch without its outer ring");
        for (int[] cell : hatch) check(cell[1] == 80 && Math.abs(cell[0] + 10) <= 8 && Math.abs(cell[2] - 140) <= 8, "The hatch is the lot's own layer");
        check(ArmamentTowerLogicR64.cells(RAISED, lot, 0, door).size() == 570 && ArmamentTowerLogicR64.cells(LOWERED, lot, 0, door).size() == 289
                && ArmamentTowerLogicR64.cells(NONE, lot, 0, door).isEmpty(), "Each run has its own cells");
        boolean refused = false;
        try { new ArmamentTowerLogicR64.Door(14, 38, 1); } catch (IllegalArgumentException expected) { refused = true; }
        check(refused, "A door of even width cannot be centred");
        check(ArmamentTowerLogicR64.POD_TRAVEL >= ArmamentTowerLogicR64.POD_HEIGHT + 3, "Stowed, the pod and the guides on its roof are under the sunk hatch");

        // Picking a tower: the four lots.
        double[][] lots = {{-49.5, 260.5}, {-9.5, 140.5}, {70.5, 340.5}, {110.5, 180.5}};
        boolean[] all = {true, true, true, true};
        check(ArmamentTowerLogicR64.nearest(30.5, 12.5, lots, all) == 1, "From the city's north edge tower 28 is nearest");
        check(ArmamentTowerLogicR64.nearest(60, 330, lots, all) == 2, "Near tower 40");
        check(ArmamentTowerLogicR64.nearest(30.5, 12.5, lots, new boolean[]{true, false, true, true}) == 3, "The next one if the nearest cannot be used");
        check(ArmamentTowerLogicR64.nearest(0, 0, lots, new boolean[4]) == -1, "None if none can be used");

        // The line on the command room's wall.
        check(ArmamentTowerLogicR64.summary(new int[]{STOWED, STOWED, STOWED, STOWED}, 0).equals("STOWED"), "All in");
        check(ArmamentTowerLogicR64.summary(new int[]{READY, READY, RISING, STOWED}, 0).equals("READY 2/4"), "Ready ones are counted first");
        check(ArmamentTowerLogicR64.summary(new int[]{OPENING, LOWERING, STOWED, STOWED}, 0).equals("MOVING 2/4"), "Then the moving ones");
        check(ArmamentTowerLogicR64.summary(new int[]{STOWED, STOWED, STOWED, STOWED}, 4).equals("WAIT CITY"), "Called while the city moves");
        check(ArmamentTowerLogicR64.summary(new int[]{READY, READY, READY, READY}, 0).length() <= 12, "It fits the wall's column");
        System.out.println("Armament tower checks passed: " + checks);
    }
}
