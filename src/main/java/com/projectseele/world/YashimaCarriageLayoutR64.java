package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

/**
 * R64: where the parts of the emplaced Yashima gun's field carriage stand, kept apart from their drawing so that
 * it can be checked by itself (YashimaCarriageLayoutR64Test).
 * <p>
 * In the original the gun at Yashima is a prototype requisitioned from the army and set up on a field carriage:
 * a thick barrel lying on a support, heavy cables into its rear, cooling beside it. The gun here is the Unit's own
 * cannon enlarged, rising from a well on two lifting columns; this is a carriage of this mod's own design round
 * it, which rises with it. Nothing of the gun's calibration (pivot, bore, muzzle, grips) is touched and nothing
 * here collides: the carriage is only drawn.
 * <p>
 * Everything is measured from the gun's root, in blocks, with the gun at rest: {@code along} the barrel's
 * horizontal direction from the pivot (the muzzle ahead, the butt behind), {@code across} to the side (positive
 * is the gunner's side, the barrel's left) and the height above the root. The platform's surface is
 * {@link #GROUND} above the root when the gun is up; the well's floor is {@link #FLOOR} above it when the gun is
 * down, so nothing that does not move may hang lower.
 * <p>
 * It has three parts. The lower carriage hangs on the lift and does not turn: two beams, four outriggers whose
 * pads come down once the gun is up, two arcs of rail, and behind on the far side the cable mast and the junction
 * cabinet. The upper carriage turns on the rails with the gun's bearing: the trunnion frames beside the gun's
 * body, in whose slots its cross shaft rises and falls with the elevation, and ahead of them the barrel's support,
 * a saddle between two screw posts. On the gun itself are the shaft, the cooling jacket round the thin barrel
 * with its pipes, and the cable plug at its rear.
 * <p>
 * The Unit lies prone beside the gun on the positive side, its hands on the grips under the gun between the pivot
 * and about 9 ahead of it, its head a few blocks ahead of the pivot. So on that side the carriage stands only
 * ahead of {@link #GUNNER_CLEAR}; everything behind that is on the far side.
 */
public record YashimaCarriageLayoutR64(Vec3 pivot, Vec3 ahead, Vec3 aside, Vec3 bore, Vec3 muzzle)
{
    /** The platform's surface with the gun up, and the well's floor with the gun down, both above the gun's root. */
    public static final double GROUND = 1.0, FLOOR = 2.5;
    /** The gun's sector either way from its rest, in degrees (YashimaCannonGeometryR52.aimWithinSectorR54). */
    public static final double SECTOR_YAW = 12, SECTOR_PITCH = 8;
    /** On the gunner's side the carriage stands only ahead of this. */
    public static final double GUNNER_CLEAR = 12;

    /** The lower carriage's two beams: how far aside, their half width, underside and top, and from where to where each runs. */
    public static final double BEAM_ASIDE = 4.9, BEAM_HALF = .7, BEAM_LOW = 2.6, BEAM_HIGH = 4.0, FAR_FROM = -8, NEAR_FROM = 13, BEAM_TO = 36;
    /** The underside of the outriggers' arms: the pads, drawn up, lie under them. */
    public static final double ARM_LOW = 3.0;
    /** The four outriggers (along, across): three on the far side and one ahead on the gunner's. */
    public static final double[][] LEGS = {{0, -8.6}, {14, -10.0}, {34, -8.6}, {34, 8.6}};
    /** The pads' half width and thickness, the jack housings' half width, and how far the jacks bring the pads down once the gun is up. */
    public static final double PAD = 1.3, PAD_THICK = .45, HOUSING = .6, JACK_STROKE = FLOOR - GROUND + .05;
    /** The half width of a truck of the upper carriage on its rail. */
    public static final double TRUCK = .5;
    /** The rails lie on the beams; their half width, and how far beyond a foot's travel each runs, in degrees. */
    public static final double RAIL_TOP = BEAM_HIGH + .25, RAIL_HALF = .75, RAIL_OVER = 3;

    /**
     * The trunnion frames: so far ahead of the pivot, so far to either side (the gun's sight unit reaches 5.92 on
     * the far side there), their plates' half thickness; the cross shaft's height at rest and the slots' ends.
     */
    public static final double CHEEK_ALONG = 14, CHEEK_FAR = -6.8, CHEEK_NEAR = 3.5, CHEEK_HALF = .35, SHAFT_HEIGHT = 10.5, SLOT_LOW = 8.1, SLOT_HIGH = 12.9;
    /** The barrel's support: so far ahead, its posts so far to either side and their half width, the saddle's top at rest and its thickness, and the posts' top. */
    public static final double GUIDE_ALONG = 26, GUIDE_FAR = -2.77, GUIDE_NEAR = 1.63, POST_HALF = .45, SADDLE = 10.6, SADDLE_THICK = .6, POST_TOP = 14.9;
    /** The upper carriage's frame, from its underside (clear of the rails) to its top. */
    public static final double FRAME_LOW = RAIL_TOP + .05, FRAME_HIGH = 4.9;

    /** The cooling jacket round the barrel: from where to where along it, and its radius. */
    public static final double JACKET_FROM = 38, JACKET_TO = 50.8, JACKET_RADIUS = 1.3;
    /** The cable mast (along, across) and how far its head's face stands toward the gun, and the gun's plug at rest: where it stands out of the butt's far flank and how high. */
    public static final double MAST_ALONG = -4, MAST_ACROSS = -6.6, MAST_FACE = .5, PLUG_ALONG = -3, PLUG_ACROSS = -2.2, PLUG_HEIGHT = 9.6;
    /** Each of the four cable links is a tube and a rod of this length, sliding in each other. */
    public static final double LINK = 2.6;

    /**
     * The position's own cables end two blocks outside the well's west edge (world x -1281, z -1420..-1414, the
     * well's edge being x -1279 and the root standing at -1242.5, -1400.5: map-buildings, 2026-11-18). Nothing may
     * stand outside the edge while the gun rises. The carriage's junction cabinet hangs just inside that edge and
     * its four connector shoes come down beside it with the jacks. From the root: the cabinet's west and east
     * faces, its south and north ends, its top, and the line the shoes stand on.
     */
    public static final double CABINET_WEST = -35.5, CABINET_EAST = -33.9, CABINET_SOUTH = -20.2, CABINET_NORTH = -11.8, CABINET_TOP = 6.4, SHOE_LINE = -35.9;
    public static final double[] SHOE_AT = {-19.0, -17.0, -15.0, -13.0};
    /**
     * Out of each shoe, once it is down, a tongue slides west over the edge to the end of the cable before it: its
     * head's west face while it is in, and how far it slides.
     */
    public static final double TONGUE_HEAD = -36.45, TONGUE = 1.05;

    /**
     * @param pivot  the point the gun turns about, at rest
     * @param bore   the barrel's direction at rest
     * @param muzzle the muzzle at rest
     */
    public static YashimaCarriageLayoutR64 of(Vec3 pivot, Vec3 bore, Vec3 muzzle)
    {
        Vec3 ahead = new Vec3(bore.x, 0, bore.z).normalize();
        return new YashimaCarriageLayoutR64(pivot, ahead, new Vec3(ahead.z, 0, -ahead.x), bore.normalize(), muzzle);
    }

    /** The point so far along, so high above the root and so far aside. */
    public Vec3 at(double along, double height, double across)
    {
        return new Vec3(pivot.x + ahead.x * along + aside.x * across, height, pivot.z + ahead.z * along + aside.z * across);
    }

    /** How far along and how far aside a point is (its height is left out). */
    public double along(Vec3 point) { return (point.x - pivot.x) * ahead.x + (point.z - pivot.z) * ahead.z; }

    public double across(Vec3 point) { return (point.x - pivot.x) * aside.x + (point.z - pivot.z) * aside.z; }

    /** The barrel's axis so far along: the jacket lies round it. */
    public Vec3 axis(double along)
    {
        double back = (along(muzzle) - along) / Math.hypot(bore.x, bore.z);
        return muzzle.subtract(bore.scale(back));
    }

    /**
     * A point of the gun, given at rest, with the gun turned so many degrees to the side and raised so many: for
     * the checks, which go through the whole sector. (The game turns the gun by one rotation from its rest to its
     * aim; over this sector the two differ by less than a tenth of a block.)
     */
    public Vec3 aimed(Vec3 point, double yaw, double pitch)
    {
        double a = along(point), h = point.y - pivot.y, c = across(point), p = Math.toRadians(pitch), y = Math.toRadians(yaw);
        double raised = a * Math.cos(p) - h * Math.sin(p), high = a * Math.sin(p) + h * Math.cos(p);
        return at(raised * Math.cos(y) - c * Math.sin(y), pivot.y + high, raised * Math.sin(y) + c * Math.cos(y));
    }

    /** A point of the upper carriage, given at rest, turned with the gun's bearing. */
    public Vec3 turned(Vec3 point, double yaw)
    {
        double a = along(point), c = across(point), y = Math.toRadians(yaw);
        return at(a * Math.cos(y) - c * Math.sin(y), point.y, a * Math.sin(y) + c * Math.cos(y));
    }

    /** A rail: its radius about the pivot and the bearings it runs between, in degrees from straight ahead toward the positive side. */
    public record Rail(double radius, double from, double to) {}

    private static Rail rail(double along, double far, double near)
    {
        double low = Math.toDegrees(Math.atan2(far, along)), high = Math.toDegrees(Math.atan2(near, along));
        return new Rail((Math.hypot(along, far) + Math.hypot(along, near)) / 2, low - SECTOR_YAW - RAIL_OVER, high + SECTOR_YAW + RAIL_OVER);
    }

    /** The rail the trunnion frames' feet run on, and the one the support's feet run on. */
    public static Rail cheekRail() { return rail(CHEEK_ALONG, CHEEK_FAR, CHEEK_NEAR); }

    public static Rail guideRail() { return rail(GUIDE_ALONG, GUIDE_FAR, GUIDE_NEAR); }

    /** A point of a rail's middle line, on the beams. */
    public Vec3 onRail(Rail rail, double bearing, double out)
    {
        double b = Math.toRadians(bearing);
        return at((rail.radius + out) * Math.cos(b), BEAM_HIGH, (rail.radius + out) * Math.sin(b));
    }

    /** The cross shaft's ends in the two trunnion frames, at rest. */
    public Vec3 shaft(boolean near) { return at(CHEEK_ALONG, SHAFT_HEIGHT, near ? CHEEK_NEAR : CHEEK_FAR); }

    /** The middle of the saddle's top, at rest: the gun's fore-end lies on it. */
    public Vec3 saddle() { return at(GUIDE_ALONG, SADDLE, (GUIDE_FAR + GUIDE_NEAR) / 2); }

    /** The box at the mast's top and the gun's plug at rest: the four cable links run between their faces. */
    public Vec3 mastBox() { return at(MAST_ALONG, PLUG_HEIGHT + .3, MAST_ACROSS + MAST_FACE); }

    public Vec3 plug() { return at(PLUG_ALONG, PLUG_HEIGHT, PLUG_ACROSS); }

    /** One of the four pads, as it stands on the ground. */
    public Vec3 pad(int index) { return at(LEGS[index][0], GROUND, LEGS[index][1]); }

    /** One of the four connector shoes, as it stands on the ground. */
    public Vec3 shoe(int index) { return new Vec3(SHOE_LINE, GROUND, SHOE_AT[index]); }

    /**
     * The outline of the carriage from above, with the lowest height of each part: for the check of the well's
     * room. The upper carriage's feet are given at both ends of the sector.
     */
    public Vec3[] footprint()
    {
        var out = new java.util.ArrayList<Vec3>();
        for (int pad = 0; pad < 4; pad++)
            for (int corner = 0; corner < 4; corner++)
                out.add(pad(pad).add(ahead.scale(corner < 2 ? -PAD : PAD)).add(aside.scale(corner % 2 == 0 ? -PAD : PAD)));
        out.add(at(FAR_FROM, BEAM_LOW, -8.0)); out.add(at(BEAM_TO, BEAM_LOW, -BEAM_ASIDE - BEAM_HALF));
        out.add(at(NEAR_FROM, BEAM_LOW, BEAM_ASIDE + BEAM_HALF)); out.add(at(BEAM_TO, BEAM_LOW, BEAM_ASIDE + BEAM_HALF));
        Vec3 foot = at(MAST_ALONG, BEAM_HIGH, MAST_ACROSS);
        for (int corner = 0; corner < 4; corner++) out.add(foot.add(corner < 2 ? -.9 : .9, 0, corner % 2 == 0 ? -.9 : .9));
        out.add(new Vec3(CABINET_WEST, FLOOR + .1, CABINET_SOUTH)); out.add(new Vec3(CABINET_EAST, FLOOR + .1, CABINET_SOUTH));
        out.add(new Vec3(CABINET_WEST, FLOOR + .1, CABINET_NORTH)); out.add(new Vec3(CABINET_EAST, FLOOR + .1, CABINET_NORTH));
        for (int shoe = 0; shoe < 4; shoe++) out.add(shoe(shoe).add(-.4, 0, 0));
        for (Rail rail : new Rail[]{cheekRail(), guideRail()})
            for (double bearing : new double[]{rail.from, rail.to})
                out.add(onRail(rail, bearing, RAIL_HALF));
        for (double yaw : new double[]{-SECTOR_YAW, SECTOR_YAW})
        {
            out.add(turned(at(CHEEK_ALONG, FRAME_LOW, CHEEK_FAR - TRUCK - .2), yaw)); out.add(turned(at(CHEEK_ALONG, FRAME_LOW, CHEEK_NEAR + TRUCK + .2), yaw));
            out.add(turned(at(GUIDE_ALONG, FRAME_LOW, GUIDE_FAR - TRUCK - .2), yaw)); out.add(turned(at(GUIDE_ALONG, FRAME_LOW, GUIDE_NEAR + TRUCK + .2), yaw));
        }
        return out.toArray(Vec3[]::new);
    }
}
