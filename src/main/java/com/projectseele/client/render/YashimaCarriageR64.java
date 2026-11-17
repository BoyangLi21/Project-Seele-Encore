package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.entity.YashimaCannonEntityR52;
import com.projectseele.entity.YashimaCannonGeometryR52.Geometry;
import com.projectseele.util.WeakIdentityMap;
import com.projectseele.world.FixedCannonCradleR52;
import com.projectseele.world.YashimaCarriageLayoutR64;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import static com.projectseele.world.YashimaCarriageLayoutR64.*;

/**
 * R64: the emplaced Yashima gun's field carriage, drawn. YashimaCarriageLayoutR64 says what it is and where its
 * parts stand; here they are built once for a gun, of plain coloured boxes and round bars in the gun's own frame,
 * and drawn each frame in five groups: what does not move, the pads and connector shoes (down once the gun is
 * ready), the upper carriage (turned to the gun's bearing), the barrel's saddle (which rises and falls in it with
 * the elevation), and what is on the gun itself (turned with its whole aim). The four cable links between the mast
 * and the gun's plug are laid from end to end each frame.
 */
final class YashimaCarriageR64
{
    private static final int OLIVE = 0x5B6552, OLIVE_DARK = 0x444C3E, OLIVE_LIGHT = 0x6C7762, STEEL = 0x8F979B, STEEL_DARK = 0x54595D, HAZARD = 0xD6A21C, RUBBER = 0x1D1E21,
            CABLE = 0x26272B, BAND = 0xC4621E, JACKET = 0xB4BABD, RING = 0x4B5054, COOLANT = 0x426E9E, CABINET = 0x80888C, WARNING = 0xA83228;
    private static final double[][] LINK_AT = {{-.42, -.42}, {.42, -.42}, {-.42, .42}, {.42, .42}};

    private record Parts(YashimaCarriageLayoutR64 layout, RigidMachineryPartR44 lower, RigidMachineryPartR44 feet, RigidMachineryPartR44 upper,
                         RigidMachineryPartR44 saddle, RigidMachineryPartR44 onGun, RigidMachineryPartR44 tube, RigidMachineryPartR44 rod)
    {
        java.util.List<RigidMachineryPartR44> all() { return java.util.List.of(lower, feet, upper, saddle, onGun, tube, rod); }
    }

    /**
     * Built once for a gun's measured frame, by its values: the gun met again in another world has the same frame
     * and the same parts. (The cache on the GPU keeps whatever was drawn until it is told to let go, so parts are
     * never simply dropped.) Read and written on the render thread alone.
     */
    private static final java.util.Map<Geometry, Parts> PARTS = new java.util.HashMap<>();
    /** For each gun: how far its jacks are down (0..1) and the time that was reckoned at. */
    private static final WeakIdentityMap<YashimaCannonEntityR52, float[]> JACKS = new WeakIdentityMap<>();

    static void draw(YashimaCannonEntityR52 gun, Geometry g, FixedCannonCradleR52.Spec spec, Quaternionf aim, float partial, PoseStack poses, MultiBufferSource buffers, int light)
    {
        Parts parts = PARTS.get(g);
        if (parts == null)
        {
            // There is one such gun; should frames ever pile up, the old ones' parts are given back first.
            if (PARTS.size() >= 4)
            {
                for (Parts old : PARTS.values()) old.all().forEach(RigidMachineryGpuR44::releaseR52);
                PARTS.clear();
            }
            PARTS.put(g, parts = build(g, spec));
        }
        var layout = parts.layout;
        Vec3 pivot = layout.pivot(), rest = g.boreWorld(new Quaternionf()), now = g.boreWorld(aim);
        float yaw = (float)(Math.atan2(now.x, now.z) - Math.atan2(rest.x, rest.z));

        parts.lower.draw(poses, buffers, light);
        poses.pushPose();
        poses.translate(0, JACK_STROKE * (1 - jacks(gun, partial)), 0);
        parts.feet.draw(poses, buffers, light);
        poses.popPose();

        poses.pushPose();
        poses.translate(pivot.x, 0, pivot.z);
        poses.mulPose(new Quaternionf().rotationY(yaw));
        poses.translate(-pivot.x, 0, -pivot.z);
        parts.upper.draw(poses, buffers, light);
        poses.translate(0, aimed(layout, aim, layout.saddle()).y - layout.saddle().y, 0);
        parts.saddle.draw(poses, buffers, light);
        poses.popPose();

        poses.pushPose();
        poses.translate(pivot.x, pivot.y, pivot.z);
        poses.mulPose(aim);
        poses.translate(-pivot.x, -pivot.y, -pivot.z);
        parts.onGun.draw(poses, buffers, light);
        poses.popPose();

        Vec3 box = layout.mastBox(), plug = layout.plug();
        for (double[] at : LINK_AT)
        {
            Vec3 from = box.add(layout.ahead().scale(at[0])).add(0, at[1], 0);
            Vec3 to = aimed(layout, aim, plug.add(layout.ahead().scale(at[0])).add(0, at[1], 0)), axis = to.subtract(from);
            double length = axis.length();
            if (length < 1e-6) continue;
            axis = axis.scale(1 / length);
            var turn = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), axis.toVector3f());
            Vec3 rod = to.subtract(axis.scale(LINK));
            poses.pushPose(); poses.translate(from.x, from.y, from.z); poses.mulPose(turn); parts.tube.draw(poses, buffers, light); poses.popPose();
            poses.pushPose(); poses.translate(rod.x, rod.y, rod.z); poses.mulPose(turn); parts.rod.draw(poses, buffers, light); poses.popPose();
        }
    }

    /** A point of the gun, given at rest, as the gun is aimed. */
    private static Vec3 aimed(YashimaCarriageLayoutR64 layout, Quaternionf aim, Vec3 point)
    {
        return layout.pivot().add(new Vec3(aim.transform(point.subtract(layout.pivot()).toVector3f())));
    }

    /** The jacks come down in a second and a half once the gun is up and its hatch shut, and go up twice as fast. */
    private static float jacks(YashimaCannonEntityR52 gun, float partial)
    {
        float time = gun.tickCount + partial;
        float[] state = JACKS.computeIfAbsent(gun, key -> new float[]{key.readyR52() ? 1 : 0, time});
        float passed = Math.max(0, Math.min(40, time - state[1]));
        state[1] = time;
        state[0] = gun.readyR52() ? Math.min(1, state[0] + passed / 30) : Math.max(0, state[0] - passed / 15);
        return state[0] * state[0] * (3 - 2 * state[0]);
    }

    private static Parts build(Geometry g, FixedCannonCradleR52.Spec spec)
    {
        var rest = new Quaternionf();
        var layout = YashimaCarriageLayoutR64.of(g.point(Vec3.ZERO, rest, g.pivot()), g.boreWorld(rest), g.point(Vec3.ZERO, rest, g.muzzle()));
        // The two lifting columns, where the gun's own cradle stands them.
        var columns = new java.util.ArrayList<Vec3>();
        for (var piece : FixedCannonCradleR52.pieces(g, spec, Vec3.ZERO, rest))
            if (piece.part().name().equals("crosshead")) columns.add(piece.frame().translation());
        return new Parts(layout, lower(layout, columns), feet(layout), upper(layout), saddle(layout), onGun(layout), link(.28, CABLE, true), link(.19, STEEL_DARK, false));
    }

    // ---------------------------------------------------------------------------------------------- the parts

    private static RigidMachineryPartR44 lower(YashimaCarriageLayoutR64 l, java.util.List<Vec3> columns)
    {
        var s = new Shape(l);
        double inner = BEAM_ASIDE - BEAM_HALF, outer = BEAM_ASIDE + BEAM_HALF, arm = (ARM_LOW + BEAM_HIGH) / 2;
        s.block(FAR_FROM, BEAM_TO, BEAM_LOW, BEAM_HIGH, -outer, -inner, OLIVE);
        s.block(NEAR_FROM, BEAM_TO, BEAM_LOW, BEAM_HIGH, inner, outer, OLIVE);
        // Their top flanges, a shade lighter, and the cross beams between them.
        s.block(FAR_FROM - .1, BEAM_TO + .1, BEAM_HIGH - .14, BEAM_HIGH, -outer - .12, -inner + .12, OLIVE_LIGHT);
        s.block(NEAR_FROM - .1, BEAM_TO + .1, BEAM_HIGH - .14, BEAM_HIGH, inner - .12, outer + .12, OLIVE_LIGHT);
        for (double along : new double[]{NEAR_FROM + .5, GUIDE_ALONG, BEAM_TO - .5})
            s.block(along - .5, along + .5, BEAM_LOW + .15, BEAM_HIGH - .15, -inner, inner, OLIVE_DARK);
        // Each lifting column carries the carriage in a collar, tied to the beams.
        for (Vec3 column : columns)
        {
            double along = l.along(column), across = l.across(column);
            for (int i = 0; i < 8; i++)
            {
                double a = i * Math.PI / 4, b = (i + 1) * Math.PI / 4;
                s.bar(l.at(along + Math.cos(a) * 1.3, arm, across + Math.sin(a) * 1.3), l.at(along + Math.cos(b) * 1.3, arm, across + Math.sin(b) * 1.3), .28, .42, STEEL_DARK);
            }
            s.block(along - .4, along + .4, ARM_LOW + .1, BEAM_HIGH - .1, -inner, across - 1.5, OLIVE_DARK);
            if (along >= NEAR_FROM) s.block(along - .4, along + .4, ARM_LOW + .1, BEAM_HIGH - .1, across + 1.5, inner, OLIVE_DARK);
        }
        // The outriggers: an arm, the jack's housing with its warning band and cap, a strut down to the beam.
        for (double[] leg : LEGS)
        {
            double side = Math.signum(leg[1]), reach = Math.abs(leg[1]);
            s.block(leg[0] - .55, leg[0] + .55, ARM_LOW + .04, BEAM_HIGH - .04, Math.min(side * outer, side * (reach - HOUSING)), Math.max(side * outer, side * (reach - HOUSING)), OLIVE);
            s.block(leg[0] - HOUSING, leg[0] + HOUSING, ARM_LOW + .02, 5.6, leg[1] - HOUSING, leg[1] + HOUSING, OLIVE_DARK);
            s.block(leg[0] - HOUSING - .06, leg[0] + HOUSING + .06, ARM_LOW + .3, ARM_LOW + .75, leg[1] - HOUSING - .06, leg[1] + HOUSING + .06, HAZARD);
            s.block(leg[0] - HOUSING - .06, leg[0] + HOUSING + .06, 5.6, 5.8, leg[1] - HOUSING - .06, leg[1] + HOUSING + .06, STEEL_DARK);
            s.bar(l.at(leg[0], BEAM_HIGH, side * BEAM_ASIDE), l.at(leg[0], 5.3, side * (reach - HOUSING)), .24, .24, OLIVE_DARK);
        }
        // The two rails, a knee under each end that overhangs the beams, and a stop at each end.
        for (Rail rail : new Rail[]{cheekRail(), guideRail()})
        {
            int pieces = (int)Math.ceil((rail.to() - rail.from()) / 3);
            for (int i = 0; i < pieces; i++)
            {
                double a = rail.from() + (rail.to() - rail.from()) * i / pieces, b = rail.from() + (rail.to() - rail.from()) * (i + 1) / pieces;
                s.bar(l.onRail(rail, a, 0).add(0, .125, 0), l.onRail(rail, b, 0).add(0, .125, 0), RAIL_HALF, .125, STEEL);
            }
            double crossing = Math.toDegrees(Math.asin(outer / rail.radius()));
            for (double end : new double[]{rail.from(), rail.to()})
            {
                double from = Math.signum(end) * crossing;
                if (Math.abs(end) > crossing + 1) s.bar(l.onRail(rail, from, 0).add(0, -.42, 0), l.onRail(rail, end, 0).add(0, -.42, 0), .4, .4, OLIVE_DARK);
                Vec3 stop = l.onRail(rail, end, 0).add(0, .5, 0), along = l.onRail(rail, end + Math.signum(end) * .8, 0).subtract(l.onRail(rail, end, 0)).normalize();
                s.box(stop, along.scale(.18), new Vec3(0, .25, 0), new Vec3(-along.z, 0, along.x).scale(RAIL_HALF), HAZARD);
            }
        }
        // Behind on the far side: a deck beside the beam's tail with the cable mast, two condensers and a switch box.
        s.block(FAR_FROM, -.6, BEAM_HIGH - .25, BEAM_HIGH, -8.0, -outer, OLIVE_DARK);
        Vec3 box = l.mastBox();
        s.block(MAST_ALONG - .4, MAST_ALONG + .4, BEAM_HIGH, box.y + 1.0, MAST_ACROSS - .4, MAST_ACROSS + .4, OLIVE);
        s.bar(l.at(MAST_ALONG + 1.6, BEAM_HIGH, -BEAM_ASIDE), l.at(MAST_ALONG + .3, 7.4, MAST_ACROSS + .3), .2, .22, OLIVE_DARK);
        s.bar(l.at(MAST_ALONG - 1.6, BEAM_HIGH, -BEAM_ASIDE), l.at(MAST_ALONG - .3, 7.4, MAST_ACROSS + .3), .2, .22, OLIVE_DARK);
        s.block(MAST_ALONG - .85, MAST_ALONG + .85, box.y - .85, box.y + .85, MAST_ACROSS - .9, MAST_ACROSS + MAST_FACE, CABINET);
        s.block(MAST_ALONG - .9, MAST_ALONG + .9, box.y + .5, box.y + .68, MAST_ACROSS - .95, MAST_ACROSS + MAST_FACE + .05, BAND);
        for (double along : new double[]{-7.1, -5.5})
        {
            s.tube(l.at(along, BEAM_HIGH, -6.8), l.at(along, 6.9, -6.8), .75, 12, CABINET);
            s.tube(l.at(along, 6.9, -6.8), l.at(along, 7.2, -6.8), .5, 12, RING);
            s.tube(l.at(along, 5.7, -6.8), l.at(along, 5.95, -6.8), .8, 12, BAND);
            s.tube(l.at(along, BEAM_HIGH, -6.8), l.at(along, BEAM_HIGH + .2, -6.8), .85, 12, RING);
        }
        s.block(-2.7, -1.0, BEAM_HIGH, 6.0, -7.8, -6.0, CABINET);
        s.block(-2.74, -.96, 5.55, 5.75, -7.84, -5.96, WARNING);
        // The junction cabinet inside the well's west edge, held from the deck and the beam's tail, with the
        // housings its connector shoes slide in, and the mast's four cables hanging over to it.
        double x = (CABINET_WEST + CABINET_EAST) / 2, z = (CABINET_SOUTH + CABINET_NORTH) / 2, low = FLOOR + .1;
        s.box(new Vec3(x, (low + CABINET_TOP) / 2, z), new Vec3((CABINET_EAST - CABINET_WEST) / 2, 0, 0), new Vec3(0, (CABINET_TOP - low) / 2, 0), new Vec3(0, 0, (CABINET_NORTH - CABINET_SOUTH) / 2), CABINET);
        s.box(new Vec3(x, CABINET_TOP - .5, z), new Vec3((CABINET_EAST - CABINET_WEST) / 2 + .04, 0, 0), new Vec3(0, .14, 0), new Vec3(0, 0, (CABINET_NORTH - CABINET_SOUTH) / 2 + .04), WARNING);
        s.box(new Vec3(x, CABINET_TOP + .08, z), new Vec3((CABINET_EAST - CABINET_WEST) / 2 + .08, 0, 0), new Vec3(0, .08, 0), new Vec3(0, 0, (CABINET_NORTH - CABINET_SOUTH) / 2 + .08), STEEL_DARK);
        for (int door = 0; door < 4; door++)
            s.box(new Vec3(CABINET_EAST + .03, (low + CABINET_TOP) / 2 - .3, CABINET_SOUTH + 1.05 + door * 2.03), new Vec3(.03, 0, 0), new Vec3(0, 1.2, 0), new Vec3(0, 0, .8), STEEL_DARK);
        s.bar(l.at(FAR_FROM + .5, BEAM_HIGH - .6, -BEAM_ASIDE), new Vec3(CABINET_EAST, BEAM_HIGH - .6, CABINET_NORTH - 2.4), .4, .4, OLIVE_DARK);
        s.bar(l.at(FAR_FROM + .3, BEAM_HIGH - .12, -7.6), new Vec3(CABINET_EAST, BEAM_HIGH - .12, CABINET_NORTH - .5), .3, .12, OLIVE_DARK);
        for (int i = 0; i < 4; i++)
        {
            s.box(new Vec3(SHOE_LINE + .05, 4.8, SHOE_AT[i]), new Vec3(.35, 0, 0), new Vec3(0, .9, 0), new Vec3(0, 0, .42), OLIVE_DARK);
            Vec3 socket = new Vec3(x, CABINET_TOP + .16, SHOE_AT[i]), from = l.at(MAST_ALONG - .85, box.y - .45 + .3 * i, MAST_ACROSS - .2);
            s.tube(socket, socket.add(0, .4, 0), .42, 8, BAND);
            Vec3 last = from;
            for (int piece = 1; piece <= 7; piece++)
            {
                double t = piece / 7D;
                Vec3 next = from.lerp(socket.add(0, .4, 0), t).add(0, -1.3 * 4 * t * (1 - t), 0);
                s.tube(last, next, .3, 8, CABLE);
                last = next;
            }
        }
        return s.out.finish();
    }

    /** What the jacks bring down: the four pads with their rams, and the four connector shoes with their plungers. */
    private static RigidMachineryPartR44 feet(YashimaCarriageLayoutR64 l)
    {
        var s = new Shape(l);
        for (double[] leg : LEGS)
        {
            s.block(leg[0] - PAD, leg[0] + PAD, GROUND, GROUND + PAD_THICK, leg[1] - PAD, leg[1] + PAD, STEEL_DARK);
            s.block(leg[0] - PAD + .25, leg[0] + PAD - .25, GROUND + PAD_THICK, GROUND + PAD_THICK + .04, leg[1] - PAD + .25, leg[1] + PAD - .25, HAZARD);
            s.tube(l.at(leg[0], GROUND + PAD_THICK, leg[1]), l.at(leg[0], GROUND + PAD_THICK + JACK_STROKE + .6, leg[1]), .32, 10, STEEL);
        }
        for (int i = 0; i < 4; i++)
        {
            Vec3 shoe = l.shoe(i);
            s.box(shoe.add(0, .12, 0), new Vec3(.4, 0, 0), new Vec3(0, .12, 0), new Vec3(0, 0, .5), RUBBER);
            s.box(shoe.add(0, .45, 0), new Vec3(.34, 0, 0), new Vec3(0, .21, 0), new Vec3(0, 0, .42), BAND);
            s.tube(shoe.add(0, .66, 0), shoe.add(0, .66 + JACK_STROKE + .9, 0), .16, 8, STEEL);
        }
        return s.out.finish();
    }

    /** How far aside the upper carriage's side members are so far along: they run from the trunnion frames' feet to the posts'. */
    private static double member(boolean near, double along)
    {
        double t = (along - CHEEK_ALONG) / (GUIDE_ALONG - CHEEK_ALONG);
        return near ? CHEEK_NEAR + t * (GUIDE_NEAR - CHEEK_NEAR) : CHEEK_FAR + t * (GUIDE_FAR - CHEEK_FAR);
    }

    private static RigidMachineryPartR44 upper(YashimaCarriageLayoutR64 l)
    {
        var s = new Shape(l);
        double middle = (FRAME_LOW + FRAME_HIGH) / 2, half = (FRAME_HIGH - FRAME_LOW) / 2;
        for (boolean near : new boolean[]{false, true})
        {
            double cheek = near ? CHEEK_NEAR : CHEEK_FAR, post = near ? GUIDE_NEAR : GUIDE_FAR, out = near ? 1 : -1;
            // The trucks on the rails and the member between them.
            s.block(CHEEK_ALONG - 1.1, CHEEK_ALONG + 1.1, FRAME_LOW, FRAME_HIGH, cheek - TRUCK, cheek + TRUCK, STEEL_DARK);
            s.block(GUIDE_ALONG - .9, GUIDE_ALONG + .9, FRAME_LOW, FRAME_HIGH, post - TRUCK, post + TRUCK, STEEL_DARK);
            s.bar(l.at(CHEEK_ALONG + 1.1, middle, member(near, CHEEK_ALONG + 1.1)), l.at(GUIDE_ALONG - .9, middle, member(near, GUIDE_ALONG - .9)), .42, half, OLIVE);
            // The trunnion frame: two uprights with the slot between them, closed above and below, strutted forward.
            s.block(CHEEK_ALONG - 1.0, CHEEK_ALONG - .45, FRAME_HIGH, SLOT_HIGH + .5, cheek - CHEEK_HALF, cheek + CHEEK_HALF, OLIVE);
            s.block(CHEEK_ALONG + .45, CHEEK_ALONG + 1.0, FRAME_HIGH, SLOT_HIGH + .5, cheek - CHEEK_HALF, cheek + CHEEK_HALF, OLIVE);
            s.block(CHEEK_ALONG - .45, CHEEK_ALONG + .45, SLOT_HIGH, SLOT_HIGH + .5, cheek - CHEEK_HALF, cheek + CHEEK_HALF, OLIVE);
            s.block(CHEEK_ALONG - .45, CHEEK_ALONG + .45, FRAME_HIGH, SLOT_LOW, cheek - CHEEK_HALF, cheek + CHEEK_HALF, OLIVE);
            s.block(CHEEK_ALONG - 1.08, CHEEK_ALONG + 1.08, SLOT_HIGH + .5, SLOT_HIGH + .68, cheek - CHEEK_HALF - .07, cheek + CHEEK_HALF + .07, STEEL_DARK);
            s.bar(l.at(CHEEK_ALONG + 4.4, FRAME_HIGH, member(near, CHEEK_ALONG + 4.4)), l.at(CHEEK_ALONG + 1.0, SLOT_HIGH - 1.2, cheek), .3, .3, OLIVE_DARK);
            // Marks of the elevation beside the slot, on the frame's outer face.
            for (int mark = 0; mark <= 4; mark++)
                s.block(CHEEK_ALONG + .45, CHEEK_ALONG + 1.0, SLOT_LOW + .6 + mark * .9, SLOT_LOW + .72 + mark * .9,
                        Math.min(cheek + out * CHEEK_HALF, cheek + out * (CHEEK_HALF + .03)), Math.max(cheek + out * CHEEK_HALF, cheek + out * (CHEEK_HALF + .03)), HAZARD);
            // The support's post: two flanges with the screw between them, capped, strutted back.
            s.block(GUIDE_ALONG - .6, GUIDE_ALONG - .3, FRAME_HIGH, POST_TOP, post - POST_HALF, post + POST_HALF, OLIVE);
            s.block(GUIDE_ALONG + .3, GUIDE_ALONG + .6, FRAME_HIGH, POST_TOP, post - POST_HALF, post + POST_HALF, OLIVE);
            s.block(GUIDE_ALONG - .68, GUIDE_ALONG + .68, POST_TOP, POST_TOP + .4, post - POST_HALF - .08, post + POST_HALF + .08, STEEL_DARK);
            s.tube(l.at(GUIDE_ALONG, FRAME_HIGH, post), l.at(GUIDE_ALONG, POST_TOP, post), .18, 8, STEEL);
            s.bar(l.at(GUIDE_ALONG - 4.2, FRAME_HIGH, member(near, GUIDE_ALONG - 4.2)), l.at(GUIDE_ALONG - .6, 11.6, post), .26, .28, OLIVE_DARK);
        }
        // Two ties across, where the gun leaves them room at its lowest.
        s.bar(l.at(16.8, middle, member(false, 16.8)), l.at(16.8, middle, member(true, 16.8)), .4, half, OLIVE_DARK);
        s.bar(l.at(GUIDE_ALONG, middle, GUIDE_FAR + TRUCK), l.at(GUIDE_ALONG, middle, GUIDE_NEAR - TRUCK), .4, half, OLIVE_DARK);
        return s.out.finish();
    }

    /** The saddle the gun's fore-end lies on: a bar between the posts with its two nuts, a pad and two lips. */
    private static RigidMachineryPartR44 saddle(YashimaCarriageLayoutR64 l)
    {
        var s = new Shape(l);
        s.block(GUIDE_ALONG - .28, GUIDE_ALONG + .28, SADDLE - SADDLE_THICK, SADDLE, GUIDE_FAR - .3, GUIDE_NEAR + .3, STEEL_DARK);
        for (double post : new double[]{GUIDE_FAR, GUIDE_NEAR})
            s.block(GUIDE_ALONG - .3, GUIDE_ALONG + .3, SADDLE - SADDLE_THICK - .2, SADDLE + .2, post - POST_HALF + .05, post + POST_HALF - .05, HAZARD);
        s.block(GUIDE_ALONG - .7, GUIDE_ALONG + .7, SADDLE - .16, SADDLE, -1.4, .95, STEEL_DARK);
        s.block(GUIDE_ALONG - .7, GUIDE_ALONG + .7, SADDLE, SADDLE + .08, -1.25, .8, RUBBER);
        s.block(GUIDE_ALONG - .7, GUIDE_ALONG + .7, SADDLE, SADDLE + .85, -1.6, -1.28, STEEL_DARK);
        s.block(GUIDE_ALONG - .7, GUIDE_ALONG + .7, SADDLE, SADDLE + .85, .83, 1.15, STEEL_DARK);
        return s.out.finish();
    }

    /** On the gun: the cross shaft, the cooling jacket with its cooler and pipes, and the cable plug on the butt. */
    private static RigidMachineryPartR44 onGun(YashimaCarriageLayoutR64 l)
    {
        var s = new Shape(l);
        // The cross shaft through the body, a block on it in each frame's slot and a collar outside.
        s.tube(l.at(CHEEK_ALONG, SHAFT_HEIGHT, CHEEK_FAR - .7), l.at(CHEEK_ALONG, SHAFT_HEIGHT, -1.6), .32, 10, STEEL);
        s.tube(l.at(CHEEK_ALONG, SHAFT_HEIGHT, 2.2), l.at(CHEEK_ALONG, SHAFT_HEIGHT, CHEEK_NEAR + .7), .32, 10, STEEL);
        for (double cheek : new double[]{CHEEK_FAR, CHEEK_NEAR})
        {
            double out = Math.signum(cheek);
            s.tube(l.at(CHEEK_ALONG, SHAFT_HEIGHT, cheek - CHEEK_HALF - .04), l.at(CHEEK_ALONG, SHAFT_HEIGHT, cheek + CHEEK_HALF + .04), .43, 10, HAZARD);
            s.tube(l.at(CHEEK_ALONG, SHAFT_HEIGHT, cheek + out * (CHEEK_HALF + .04)), l.at(CHEEK_ALONG, SHAFT_HEIGHT, cheek + out * (CHEEK_HALF + .24)), .75, 12, STEEL_DARK);
        }
        // The jacket round the barrel, ringed; the pipe back along its underside.
        s.tube(l.axis(JACKET_FROM), l.axis(JACKET_TO), JACKET_RADIUS, 12, JACKET);
        for (int ring = 0; ring <= 4; ring++)
        {
            double along = JACKET_FROM + .25 + (JACKET_TO - JACKET_FROM - .5) * ring / 4;
            s.tube(l.axis(along - .25), l.axis(along + .25), JACKET_RADIUS + .22, 12, RING);
        }
        s.tube(l.axis(JACKET_FROM + .1).add(0, -JACKET_RADIUS - .2, 0), l.axis(JACKET_TO - .1).add(0, -JACKET_RADIUS - .2, 0), .2, 8, COOLANT);
        // The cooler slung under the sight on the far side, and its two pipes forward to the jacket.
        s.block(18, 23, 10.3, 12.1, -3.1, -1.1, CABINET);
        for (int fin = 0; fin < 4; fin++) s.block(18.45 + fin * 1.1, 18.95 + fin * 1.1, 10.5, 11.9, -3.16, -3.1, RING);
        s.block(17.9, 23.1, 12.1, 12.22, -3.2, -1.0, STEEL_DARK);
        Vec3 back = l.axis(JACKET_FROM + .2);
        double flank = l.across(back) - JACKET_RADIUS + .1;
        s.tube(l.at(23, 11.6, -2.0), l.at(JACKET_FROM + .2, back.y - .35, flank), .22, 8, COOLANT);
        s.tube(l.at(23, 10.95, -2.0), l.at(JACKET_FROM + .2, back.y - .95, flank + .2), .22, 8, COOLANT);
        s.block(30.2, 30.7, 11.0, 12.2, -2.15, -.95, RING);
        // The plug on the butt's far flank: a clamp over the butt (open below, where the rear column holds the
        // gun), the drum, and its face, which the four links come to.
        s.block(PLUG_ALONG - .8, PLUG_ALONG + .8, 10.5, 10.8, -.35, 2.0, RING);
        s.block(PLUG_ALONG - .8, PLUG_ALONG + .8, 8.7, 10.5, -.35, .02, RING);
        s.block(PLUG_ALONG - .8, PLUG_ALONG + .8, 9.3, 10.5, 1.72, 2.0, RING);
        s.tube(l.at(PLUG_ALONG, PLUG_HEIGHT, -.35), l.at(PLUG_ALONG, PLUG_HEIGHT, PLUG_ACROSS + .12), .95, 12, BAND);
        s.tube(l.at(PLUG_ALONG, PLUG_HEIGHT, PLUG_ACROSS + .12), l.at(PLUG_ALONG, PLUG_HEIGHT, PLUG_ACROSS - .08), 1.08, 12, RING);
        return s.out.finish();
    }

    /** One member of a cable link: a round bar of the link's length, upward from its foot; the outer one is banded. */
    private static RigidMachineryPartR44 link(double radius, int colour, boolean banded)
    {
        var s = new Shape(null);
        s.tube(Vec3.ZERO, new Vec3(0, LINK, 0), radius, 8, colour);
        if (banded)
        {
            s.tube(new Vec3(0, .05, 0), new Vec3(0, .35, 0), radius + .08, 8, BAND);
            s.tube(new Vec3(0, LINK - .3, 0), new Vec3(0, LINK, 0), radius + .08, 8, RING);
        }
        else s.tube(new Vec3(0, LINK - .35, 0), new Vec3(0, LINK - .05, 0), radius + .1, 8, BAND);
        return s.out.finish();
    }

    // ---------------------------------------------------------------------------------------------- the shapes

    /** Boxes and round bars, every face turned outward whichever way its corners were given. */
    private static final class Shape
    {
        final RigidMachineryPartR44.Builder out = new RigidMachineryPartR44.Builder();
        private final YashimaCarriageLayoutR64 layout;

        Shape(YashimaCarriageLayoutR64 layout) { this.layout = layout; }

        private void face(Vec3 a, Vec3 b, Vec3 c, Vec3 d, Vec3 inside, int colour)
        {
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.dot(a.add(b).add(c).add(d).scale(.25).subtract(inside)) < 0) out.quad(a, d, c, b, colour);
            else out.quad(a, b, c, d, colour);
        }

        /** A triangle, as a quad with its last corner twice (the builder takes its normal from the first three). */
        private void triangle(Vec3 a, Vec3 b, Vec3 c, Vec3 inside, int colour)
        {
            Vec3 normal = b.subtract(a).cross(c.subtract(a));
            if (normal.dot(a.add(b).add(c).scale(1 / 3D).subtract(inside)) < 0) out.quad(a, c, b, b, colour);
            else out.quad(a, b, c, c, colour);
        }

        /** A box by its middle and its three half edges. */
        void box(Vec3 middle, Vec3 u, Vec3 v, Vec3 w, int colour)
        {
            for (int sign = -1; sign <= 1; sign += 2)
            {
                side(middle, u.scale(sign), v, w, colour);
                side(middle, v.scale(sign), w, u, colour);
                side(middle, w.scale(sign), u, v, colour);
            }
        }

        private void side(Vec3 middle, Vec3 n, Vec3 s, Vec3 t, int colour)
        {
            Vec3 c = middle.add(n);
            face(c.subtract(s).subtract(t), c.add(s).subtract(t), c.add(s).add(t), c.subtract(s).add(t), middle, colour);
        }

        /** A box square to the carriage: from where to where along, in height and across. */
        void block(double along0, double along1, double low, double high, double across0, double across1, int colour)
        {
            box(layout.at((along0 + along1) / 2, (low + high) / 2, (across0 + across1) / 2), layout.ahead().scale((along1 - along0) / 2),
                    new Vec3(0, (high - low) / 2, 0), layout.aside().scale((across1 - across0) / 2), colour);
        }

        /** A square bar from one point to another: its half width (level, across it) and half depth. */
        void bar(Vec3 from, Vec3 to, double wide, double deep, int colour)
        {
            Vec3 half = to.subtract(from).scale(.5), level = new Vec3(-half.z, 0, half.x);
            level = level.lengthSqr() < 1e-9 ? new Vec3(1, 0, 0) : level.normalize();
            box(from.add(half), half, level.scale(wide), half.cross(level).normalize().scale(deep), colour);
        }

        /** A round bar from one point to another, closed at both ends. */
        void tube(Vec3 from, Vec3 to, double radius, int sides, int colour)
        {
            Vec3 axis = to.subtract(from).normalize(), u = Math.abs(axis.y) > .9 ? new Vec3(1, 0, 0) : new Vec3(0, 1, 0);
            u = u.subtract(axis.scale(u.dot(axis))).normalize();
            Vec3 v = axis.cross(u), middle = from.add(to).scale(.5);
            for (int i = 0; i < sides; i++)
            {
                double a = i * 2 * Math.PI / sides, b = (i + 1) * 2 * Math.PI / sides;
                Vec3 p = u.scale(Math.cos(a) * radius).add(v.scale(Math.sin(a) * radius)), q = u.scale(Math.cos(b) * radius).add(v.scale(Math.sin(b) * radius));
                face(from.add(p), from.add(q), to.add(q), to.add(p), middle, colour);
                triangle(from, from.add(q), from.add(p), middle, colour);
                triangle(to, to.add(p), to.add(q), middle, colour);
            }
        }
    }

    private YashimaCarriageR64() {}
}
