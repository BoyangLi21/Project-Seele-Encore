package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

/**
 * The emplaced Yashima gun's field carriage, laid out for the gun as it is installed (the numbers below are the
 * installed station's and its gun's own, measured from its root): it stays inside the room the well leaves it,
 * nothing that does not move hangs under the well's floor when the gun is down, it keeps clear of the gun's two
 * lifting columns, of the gun itself and of the side the Unit lies on, its moving parts have the travel the gun's
 * whole sector asks of them, and its connector shoes come down on the stretch where the position's own cables arrive.
 */
public final class YashimaCarriageLayoutR64Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    public static void main(String[] args)
    {
        final double yaw = YashimaCarriageLayoutR64.SECTOR_YAW, pitch = YashimaCarriageLayoutR64.SECTOR_PITCH;
        // yashima_cannon_station_r52.json, root_hakone_fixed_cannon_r53: the gun at rest, from its root.
        Vec3 pivot = new Vec3(-22.36, 9.69, -15.17), bore = new Vec3(.5919, -.0198, .8057), muzzle = new Vec3(9.06, 12.33, 28.56);
        // The two lifting columns stand under these two points of the gun; a crosshead of 4 by 4 on each (2.83 to its corner).
        Vec3 rear = new Vec3(-23.2, 9.18, -18.41), front = new Vec3(-4.21, 12.47, 10.5);
        var layout = YashimaCarriageLayoutR64.of(pivot, bore, muzzle);
        that(Math.abs(layout.along(muzzle) - 53.85) < .05 && Math.abs(layout.across(muzzle) + .57) < .05, "the muzzle is 53.85 along: " + layout.along(muzzle));

        // The room: the well is world x -1279..-1223, z -1429..-1365, and the root stands at -1242.5, -1400.5.
        double west = -1279 + 1242.5, east = -1223 + 1242.5, south = -1429 + 1400.5, north = -1365 + 1400.5;
        for (Vec3 point : layout.footprint())
            that(point.x >= west && point.x <= east && point.z >= south && point.z <= north, "outside the well's room: " + point);
        that(muzzle.x <= east && muzzle.z <= north, "the gun itself is inside it");

        // Down in the well the floor is 2.5 above the root: only the pads and the shoes go lower, and only once the gun is up.
        for (Vec3 point : layout.footprint())
            that(point.y >= YashimaCarriageLayoutR64.FLOOR || point.y == YashimaCarriageLayoutR64.GROUND, "a fixed part under the well's floor: " + point);
        that(YashimaCarriageLayoutR64.BEAM_LOW >= YashimaCarriageLayoutR64.FLOOR, "the beams clear the floor");
        that(YashimaCarriageLayoutR64.GROUND + YashimaCarriageLayoutR64.JACK_STROKE >= YashimaCarriageLayoutR64.FLOOR, "the pads, drawn up, clear the floor");
        that(YashimaCarriageLayoutR64.GROUND + YashimaCarriageLayoutR64.JACK_STROKE + YashimaCarriageLayoutR64.PAD_THICK <= YashimaCarriageLayoutR64.ARM_LOW + .01,
                "the pads, drawn up, are under the outriggers' arms");
        for (double[] leg : YashimaCarriageLayoutR64.LEGS)
            that(Math.abs(leg[1]) - YashimaCarriageLayoutR64.PAD > YashimaCarriageLayoutR64.BEAM_ASIDE + YashimaCarriageLayoutR64.BEAM_HALF, "a pad under a beam: " + leg[1]);

        // The lifting columns.
        double rearAlong = layout.along(rear), rearAcross = layout.across(rear), frontAlong = layout.along(front), frontAcross = layout.across(front);
        var guideRail = YashimaCarriageLayoutR64.guideRail();
        var cheekRail = YashimaCarriageLayoutR64.cheekRail();
        that(Math.abs(frontAcross) + 2.83 < YashimaCarriageLayoutR64.BEAM_ASIDE - YashimaCarriageLayoutR64.BEAM_HALF, "the front column stands between the beams: " + frontAcross);
        that(guideRail.radius() + YashimaCarriageLayoutR64.RAIL_HALF + .5 < frontAlong - 2.83, "the support and its rail keep behind the front column's crosshead: " + frontAlong);
        that(rearAcross - 2.83 > -YashimaCarriageLayoutR64.BEAM_ASIDE + YashimaCarriageLayoutR64.BEAM_HALF, "the rear column stands clear of the far beam: " + rearAcross);
        that(Math.hypot(rearAlong, rearAcross) + 2.83 < cheekRail.radius() - YashimaCarriageLayoutR64.RAIL_HALF, "the rear column stands inside the trunnion frames' rail");
        that(YashimaCarriageLayoutR64.MAST_ACROSS + .9 < rearAcross - 2.83, "the mast stands clear of the rear column");

        // The Unit's side: behind GUNNER_CLEAR nothing stands on the positive side (its hands reach to 8.25 along).
        that(YashimaCarriageLayoutR64.NEAR_FROM >= YashimaCarriageLayoutR64.GUNNER_CLEAR, "the near beam begins ahead of the Unit");
        for (double[] leg : YashimaCarriageLayoutR64.LEGS)
            that(leg[1] < 0 || leg[0] - YashimaCarriageLayoutR64.PAD >= YashimaCarriageLayoutR64.GUNNER_CLEAR, "an outrigger on the Unit's side: " + leg[0]);
        that(layout.along(layout.onRail(cheekRail, cheekRail.to(), -YashimaCarriageLayoutR64.RAIL_HALF)) >= YashimaCarriageLayoutR64.GUNNER_CLEAR,
                "the trunnion frames' rail ends ahead of the Unit: " + layout.along(layout.onRail(cheekRail, cheekRail.to(), -YashimaCarriageLayoutR64.RAIL_HALF)));
        for (double turn = -yaw; turn <= yaw; turn += 4)
            that(layout.along(layout.turned(layout.shaft(true), turn)) - .8 >= YashimaCarriageLayoutR64.GUNNER_CLEAR, "the near trunnion frame swings back to the Unit at " + turn);
        that(YashimaCarriageLayoutR64.MAST_ACROSS < -3 && YashimaCarriageLayoutR64.PLUG_ACROSS < 0, "the cables are on the far side");

        // The gun itself, cut at the stations (its mesh, at rest): the frames stand outside it and the saddle under it.
        double gunFarAtCheek = -5.92, gunNearAtCheek = 2.84, foreEndLow = 10.74, foreEndFar = -1.15, foreEndNear = .59;
        that(YashimaCarriageLayoutR64.CHEEK_FAR + YashimaCarriageLayoutR64.CHEEK_HALF < gunFarAtCheek - .3
                && YashimaCarriageLayoutR64.CHEEK_NEAR - YashimaCarriageLayoutR64.CHEEK_HALF > gunNearAtCheek + .2, "the trunnion frames stand outside the gun's body");
        that(YashimaCarriageLayoutR64.SADDLE <= foreEndLow - .1 && YashimaCarriageLayoutR64.SADDLE >= foreEndLow - .4, "the saddle's top is just under the fore-end");
        that(YashimaCarriageLayoutR64.GUIDE_FAR + YashimaCarriageLayoutR64.POST_HALF < foreEndFar - .5
                && YashimaCarriageLayoutR64.GUIDE_NEAR - YashimaCarriageLayoutR64.POST_HALF > foreEndNear + .5, "the fore-end passes between the posts");
        that(Math.abs((YashimaCarriageLayoutR64.GUIDE_FAR + YashimaCarriageLayoutR64.GUIDE_NEAR) / 2 - layout.across(muzzle)) < .05, "the support stands under the barrel's axis");

        // Through the whole sector: the cross shaft stays in its slots, the saddle between its posts and over the
        // frame, and each cable link within what a tube and a rod sliding in each other can do.
        Vec3 box = layout.mastBox();
        double least = Double.MAX_VALUE, most = 0, shaftLow = Double.MAX_VALUE, shaftHigh = 0, saddleLow = Double.MAX_VALUE, saddleHigh = 0;
        for (double turn = -yaw; turn <= yaw; turn += 4)
            for (double raise = -pitch; raise <= pitch; raise += 4)
            {
                double length = layout.aimed(layout.plug(), turn, raise).distanceTo(box);
                least = Math.min(least, length); most = Math.max(most, length);
                double shaft = layout.aimed(layout.shaft(false), turn, raise).y, saddle = layout.aimed(layout.saddle(), turn, raise).y;
                shaftLow = Math.min(shaftLow, shaft); shaftHigh = Math.max(shaftHigh, shaft);
                saddleLow = Math.min(saddleLow, saddle); saddleHigh = Math.max(saddleHigh, saddle);
            }
        that(least >= YashimaCarriageLayoutR64.LINK + .15 && most <= 2 * YashimaCarriageLayoutR64.LINK - .15, "the cable links slide from " + least + " to " + most);
        that(shaftLow - .35 >= YashimaCarriageLayoutR64.SLOT_LOW && shaftHigh + .35 <= YashimaCarriageLayoutR64.SLOT_HIGH, "the cross shaft travels " + shaftLow + " to " + shaftHigh);
        that(saddleHigh + .3 <= YashimaCarriageLayoutR64.POST_TOP && saddleLow - YashimaCarriageLayoutR64.SADDLE_THICK >= YashimaCarriageLayoutR64.FRAME_HIGH + .3,
                "the saddle travels " + saddleLow + " to " + saddleHigh);

        // The rails: every foot stays on its rail through the sector, and the middle outrigger's housing stands outside the inner one.
        for (double turn = -yaw; turn <= yaw; turn += 4)
        {
            for (boolean near : new boolean[]{false, true})
            {
                Vec3 foot = layout.turned(layout.shaft(near), turn);
                double bearing = Math.toDegrees(Math.atan2(layout.across(foot), layout.along(foot))), out = Math.hypot(layout.across(foot), layout.along(foot));
                that(bearing > cheekRail.from() + 1 && bearing < cheekRail.to() - 1 && Math.abs(out - cheekRail.radius()) < YashimaCarriageLayoutR64.RAIL_HALF, "a trunnion frame's foot off its rail at " + turn);
                Vec3 post = layout.turned(layout.at(YashimaCarriageLayoutR64.GUIDE_ALONG, 0, near ? YashimaCarriageLayoutR64.GUIDE_NEAR : YashimaCarriageLayoutR64.GUIDE_FAR), turn);
                bearing = Math.toDegrees(Math.atan2(layout.across(post), layout.along(post))); out = Math.hypot(layout.across(post), layout.along(post));
                that(bearing > guideRail.from() + 1 && bearing < guideRail.to() - 1 && Math.abs(out - guideRail.radius()) < YashimaCarriageLayoutR64.RAIL_HALF, "a post's foot off its rail at " + turn);
            }
        }
        double[] middle = YashimaCarriageLayoutR64.LEGS[1];
        that(Math.hypot(middle[0] - YashimaCarriageLayoutR64.HOUSING - .05, Math.abs(middle[1]) - YashimaCarriageLayoutR64.HOUSING - .05)
                        > Math.hypot(YashimaCarriageLayoutR64.CHEEK_ALONG, YashimaCarriageLayoutR64.CHEEK_FAR) + YashimaCarriageLayoutR64.TRUCK + .1,
                "the far trunnion frame's truck passes inside the middle outrigger's jack");

        // The jacket is on the thin barrel only: ahead of the fore-end's lug (to 37.2 along) and behind the muzzle's block (from 51.4).
        that(YashimaCarriageLayoutR64.JACKET_FROM >= 37.6 && YashimaCarriageLayoutR64.JACKET_TO <= 51.2, "the jacket lies on the barrel alone");
        that(Math.abs(layout.axis(layout.along(muzzle)).distanceTo(muzzle)) < 1e-6 && Math.abs(layout.along(layout.axis(40)) - 40) < 1e-6, "the barrel's axis is the bore through the muzzle");
        that(Math.abs(layout.axis(44).y - 12.53) < .05, "the barrel is 12.53 high at 44 along: " + layout.axis(44).y);

        // The connector shoes: just inside the well's west edge, each before a block of the stretch where the
        // position's cables end (world z -1420..-1414, one block each), and each one's tongue, slid out, reaches the
        // cable's end one block outside the edge (world x -1280) and is inside the edge while it is in.
        for (int shoe = 0; shoe < 4; shoe++)
        {
            Vec3 at = layout.shoe(shoe);
            that(at.x - west <= 1.2 && at.x - .4 >= west && at.z > -1420 + 1400.5 && at.z < -1413 + 1400.5, "a shoe off the cables' stretch: " + at);
            // (The root stands at a half block, so the middle of a block is a whole number from it.)
            that(Math.abs(at.z - Math.rint(at.z)) < 1e-9, "a shoe not before the middle of a block: " + at);
        }
        that(YashimaCarriageLayoutR64.TONGUE_HEAD >= west, "a tongue's head outside the well while it is in");
        that(Math.abs(YashimaCarriageLayoutR64.TONGUE_HEAD - YashimaCarriageLayoutR64.TONGUE - (west - 1)) < 1e-9, "the tongues do not reach the cables' ends");
        // The cabinet is clear of the rear pad beside it and stands on the far side.
        Vec3 pad = layout.pad(0);
        that(pad.x - YashimaCarriageLayoutR64.PAD * 1.42 > YashimaCarriageLayoutR64.CABINET_EAST + .5, "the cabinet stands west of the rear pad: " + pad);
        that(layout.across(new Vec3(YashimaCarriageLayoutR64.CABINET_EAST, 0, YashimaCarriageLayoutR64.CABINET_SOUTH)) < -3
                && layout.across(new Vec3(YashimaCarriageLayoutR64.CABINET_EAST, 0, YashimaCarriageLayoutR64.CABINET_NORTH)) < -3, "the cabinet is on the far side");

        System.out.println("YashimaCarriageLayoutR64Test: " + checked + " checks passed.");
    }
}
