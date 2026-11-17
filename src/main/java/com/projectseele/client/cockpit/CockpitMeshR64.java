package com.projectseele.client.cockpit;

import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * The inside of the entry plug as the pilot sees it: the two control yokes with the pilot's gloved hands on them,
 * the side consoles, the knees and the seat's front, and the LCL the plug is filled with.
 * <p>
 * Everything is built here from boxes, in the pilot's own space (the eye at the origin, looking down -Z, +Y up,
 * blocks), with no game classes: the game draws the vertices as they come, and tools/cockpit_preview draws the same
 * vertices without the game. Nothing is read from a model or a texture; the shapes and colours are this file.
 */
public final class CockpitMeshR64
{
    /** What the cockpit shows this frame. All eased by the caller; angles in radians. */
    public static final class State
    {
        /** 0 Unit-00, 1 Unit-01, 2 Unit-02, 3 a UN unit. */
        public int unit = 1;
        /** Seconds, for ripples and bubbles. */
        public float time;
        /** The yokes: pushed forward (+) or pulled back (-) and tilted to the right (+), each -1..1, left and right. */
        public float leftPush, leftTilt, rightPush, rightTilt;
        /** Trigger fingers, 0..1. */
        public float leftTrigger, rightTrigger;
        /** How far the cockpit is turned up into the view (the pilot looking down at it), and its sway. */
        public float pitch, swayX, swayY, roll;
        /** LCL: the surface's height against the eye (blocks; under -1.2 there is none), and how much of it shows, 0..1. */
        public float lclLevel = -9, lclAlpha;
        /** Bubbles in the LCL, 0..1 of the most. */
        public float bubbles;
        /** The plug's own light: 1 lit by the picture on the wall, 0 dark (before the wall is on). */
        public float light = 1;
        /** The seat, yokes, hands and knees; without them only the LCL is built (running out after the seat is left). */
        public boolean parts = true;
        /** How far the cockpit has sunk out of the view (blocks): behind a sight the hands are not in the picture. */
        public float drop;
        /**
         * The positron cannon's sight: how far it has swung down before the pilot's face (0 up out of the view, 1
         * down), the half width and half height of its window as tangents of the angle from the view's axis, and
         * the kick a shot gives it (radians).
         */
        public float visor, visorWide, visorHigh, visorJolt;
        /** The cannon's charge, 0..1, and whether the shot is on: the sight's housing shows both as a row of lamps. */
        public float visorCharge;
        public boolean visorLock;
    }

    /** Opaque and see-through vertices, seven floats each (x y z r g b a), four to a quad. */
    public float[] solid = new float[7 * 4 * 512], clear = new float[7 * 4 * 512];
    public int solidCount, clearCount;

    private final Matrix4f frame = new Matrix4f();
    private final Matrix4f part = new Matrix4f();
    private final Vector3f a = new Vector3f(), b = new Vector3f(), c = new Vector3f(), d = new Vector3f(), n = new Vector3f();
    private float light = 1;
    /** Where the light of the picture on the wall comes from: ahead and above. */
    private static final Vector3f SUN = new Vector3f(.25F, .8F, -.55F).normalize();

    private static final float[][] SUIT = {{.90F, .92F, .94F}, {.17F, .30F, .62F}, {.74F, .11F, .12F}, {.20F, .21F, .23F}};
    private static final float[][] CUFF = {{.16F, .36F, .40F}, {.86F, .88F, .92F}, {.96F, .47F, .10F}, {.86F, .70F, .12F}};
    private static final float[][] TRIM = {{.88F, .58F, .14F}, {.45F, .26F, .66F}, {.80F, .14F, .14F}, {.80F, .66F, .14F}};
    private static final float[] DARK = {.085F, .09F, .105F}, METAL = {.20F, .215F, .24F}, PALE = {.40F, .43F, .46F},
            RUBBER = {.05F, .05F, .055F}, TRIGGER = {.82F, .16F, .10F}, AMBER = {1F, .62F, .18F};

    /** The colour of the LCL. */
    public static final float[] LCL = {1F, .50F, .09F};

    public void build(State s)
    {
        solidCount = clearCount = 0;
        light = .30F + .70F * s.light;
        // The pilot's head turns down a share of the way the view does: looking at the ground brings the yokes
        // and knees up into the view, looking at the sky leaves it clear. The sway is the seat under the pilot.
        frame.identity().translate(s.swayX, s.swayY - s.drop, 0).rotateZ(s.roll).rotateX(s.pitch);
        int u = Math.max(0, Math.min(3, s.unit));
        if (s.parts)
        {
            seat(u);
            for (int side = -1; side <= 1; side += 2)
            {
                boolean left = side < 0;
                yoke(u, side, left ? s.leftPush : s.rightPush, left ? s.leftTilt : s.rightTilt, left ? s.leftTrigger : s.rightTrigger);
                leg(u, side);
            }
        }
        if (s.visor > 0) visor(s);
        if (s.lclAlpha > 0 && s.lclLevel > -1.2F)
        {
            // The liquid is level in the plug whether or not the hands have sunk out of the picture.
            frame.identity().translate(s.swayX, s.swayY, 0).rotateZ(s.roll).rotateX(s.pitch);
            if (s.bubbles > 0) bubbles(s);
            surface(s);
        }
    }

    // ----- the parts -----

    private void seat(int u)
    {
        // The seat's front between the knees, with the strip of light every console in the base has.
        part.set(frame).translate(0, -.80F, -.62F).rotateX(-.30F);
        box(0, 0, 0, .15F, .045F, .20F, DARK, 1);
        box(0, .05F, -.06F, .11F, .008F, .10F, METAL, 1);
        box(0, .062F, -.10F, .085F, .003F, .012F, AMBER, 3);
        box(0, .062F, -.02F, .05F, .003F, .008F, TRIM[u], 2);
        for (int side = -1; side <= 1; side += 2)
        {
            // The side consoles the yokes stand on.
            part.set(frame).translate(side * .56F, -.66F, -.46F).rotateZ(side * -.20F).rotateX(-.10F);
            box(0, 0, 0, .085F, .06F, .40F, DARK, 1);
            box(side * -.02F, .062F, -.05F, .05F, .006F, .30F, METAL, 1);
            box(side * -.02F, .070F, -.33F, .035F, .003F, .010F, AMBER, 3);
            box(side * .05F, .068F, -.02F, .012F, .004F, .26F, TRIM[u], 1);
        }
    }

    private static final float[] SHELL = {.27F, .29F, .32F}, BEZEL = {.34F, .36F, .40F}, LENS = {.10F, .34F, .30F}, READY = {.49F, .94F, .54F};

    /**
     * The positron cannon's sight: a housing on two arms hinged above the pilot's head, which swings down before
     * the eyes. It is fixed to the pilot's head, not to the seat: it neither sways nor tips with the view. Nearest
     * the eye is the bezel round its window, deep enough for its inner faces to be seen; behind the yokes (so that
     * the hands stay in the picture, on the trigger) is the shell that shuts out everything but the window.
     */
    private void visor(State s)
    {
        float t = s.visor * s.visor * (3 - 2 * s.visor);
        // Up, it stands a little over a right angle back from its place; it settles with the least over-travel.
        float swing = (1 - t) * 1.9F - (s.visor > .82F ? (float) Math.sin((s.visor - .82F) / .18F * Math.PI) * .018F : 0) + s.visorJolt;
        float hingeY = .62F, hingeZ = .14F, far = .40F, near = .30F, plate = 1.25F;
        float wide = s.visorWide * far, high = s.visorHigh * far, rim = .036F, mid = -(near + far) * .5F - hingeZ, deep = (far - near) * .5F;
        Matrix4f hinge = new Matrix4f().translate(0, hingeY, hingeZ).rotateX(swing);
        // The bezel: a deep brow and two deep cheeks round the window, and a slim lip under it (a deep one so near
        // the eye would hide the pilot's hands). Its far inner edges are the window's edges on the picture.
        part.set(hinge);
        float lip = .012F, shallow = .02F, back = -far - hingeZ + shallow;
        box(0, -hingeY + high + rim, mid, wide + 2 * rim, rim, deep, BEZEL, 1);
        box(0, -hingeY - high - lip, back, wide + 2 * rim, lip, shallow, BEZEL, 1);
        box(-wide - rim, -hingeY, mid, rim, high, deep, BEZEL, 1);
        box(wide + rim, -hingeY, mid, rim, high, deep, BEZEL, 1);
        // On the bezel's face: a strip of light along the brow, a lamp at each lower corner, the lens housings at its sides.
        float face = mid + deep + .001F;
        box(0, -hingeY + high + rim, face, wide * .46F, .0035F, .0015F, AMBER, 3);
        for (int side = -1; side <= 1; side += 2)
        {
            box(side * (wide - .02F), -hingeY - high - lip, back + shallow + .001F, .005F, .004F, .0015F, TRIGGER, 3);
            box(side * (wide + 2 * rim + .028F), -hingeY + high * .25F, mid - .01F, .028F, high * .42F, deep * 1.25F, METAL, 1);
            box(side * (wide + 2 * rim + .028F), -hingeY + high * .25F, mid + deep * 1.25F - .009F, .017F, high * .30F, .0015F, LENS, 2);
            box(side * (wide + 2 * rim + .028F), -hingeY - high * .55F, mid, .020F, high * .16F, deep, PALE, 1);
        }
        // The lip carries the charge as a row of seven lamps: one more for each seventh, all green when the shot is on.
        int lamps = Math.round(Math.max(0, Math.min(1, s.visorCharge)) * 7);
        for (int lamp = 0; lamp < 7; lamp++)
            box((lamp - 3) * wide * .105F, -hingeY - high - lip, back + shallow + .001F, wide * .036F, .0045F, .0015F,
                    lamp < lamps ? s.visorLock ? READY : AMBER : DARK, lamp < lamps ? 3 : 1);
        // The shell behind the hands: four plates that leave the window open.
        float px = s.visorWide * plate * 1.07F, py = s.visorHigh * plate * 1.09F, pz = -plate - hingeZ;
        box(0, -hingeY + py + 1.2F, pz, 3.2F, 1.2F, .01F, SHELL, 1);
        box(0, -hingeY - py - 1.2F, pz, 3.2F, 1.2F, .01F, SHELL, 1);
        box(-px - 1.4F, -hingeY, pz, 1.4F, py, .01F, SHELL, 1);
        box(px + 1.4F, -hingeY, pz, 1.4F, py, .01F, SHELL, 1);
        // Seams and a darker band on the shell, so that it reads as plates and not as a hole in the picture.
        for (int side = -1; side <= 1; side += 2)
        {
            box(side * (px + .62F), -hingeY, pz + .012F, .012F, py + 1.1F, .002F, DARK, 1);
            box(side * (px + 1.5F), -hingeY + py * .45F, pz + .012F, .86F, .010F, .002F, DARK, 1);
            box(side * (px + 1.5F), -hingeY - py * .45F, pz + .012F, .86F, .010F, .002F, DARK, 1);
        }
        box(0, -hingeY + py + .22F, pz + .012F, px + .5F, .012F, .002F, DARK, 1);
        box(0, -hingeY - py - .22F, pz + .012F, px + .5F, .012F, .002F, DARK, 1);
        // The two arms, from the bezel's upper corners to the hinge.
        for (int side = -1; side <= 1; side += 2)
        {
            Vector3f foot = hinge.transformPosition(new Vector3f(side * (wide + rim), -hingeY + high + 2 * rim, mid));
            Vector3f top = hinge.transformPosition(new Vector3f(side * (wide + rim), 0, 0));
            limb(foot, top, .020F, .026F, METAL, PALE, .18F);
        }
    }

    private void yoke(int u, int side, float push, float tilt, float trigger)
    {
        // The yoke turns about its foot on the console: pushed forward to go, tilted to step aside.
        part.set(frame).translate(side * .47F, -.585F, -.50F)
                .rotateX(-.42F - push * .22F).rotateZ(-tilt * .20F + side * .10F);
        box(0, 0, 0, .030F, .022F, .030F, METAL, 1);
        box(0, .075F, 0, .013F, .075F, .013F, PALE, 1);
        // The grip, leaning back in the hand, and the guard before the fingers.
        part.translate(0, .165F, 0).rotateX(.34F);
        box(0, .045F, 0, .021F, .070F, .024F, RUBBER, 1);
        box(0, .121F, 0, .026F, .008F, .029F, TRIM[u], 1);
        box(0, .050F, -.060F, .006F, .060F, .006F, METAL, 1);
        box(0, .112F, -.032F, .006F, .006F, .032F, METAL, 1);
        box(0, -.012F, -.032F, .006F, .006F, .032F, METAL, 1);
        box(0, .078F - trigger * .004F, -.030F + trigger * .010F, .008F, .013F, .008F, TRIGGER, 2);
        // The glove: the palm behind the grip, the fingers round its front, the thumb over the top.
        float[] suit = SUIT[u], cuff = CUFF[u];
        box(side * .004F, .050F, .034F, .034F, .050F, .020F, suit, 1);
        // Three fingers round the grip, one above the other, and the first on the trigger.
        for (int finger = 0; finger < 3; finger++)
            box(side * .002F, .008F + finger * .0215F, -.024F, .033F, .0092F, .013F, suit, 1);
        box(side * .002F, .0745F, -.024F - trigger * .006F, .031F, .0092F, .012F + trigger * .003F, suit, 1);
        box(side * -.030F, .096F, .008F, .012F, .012F, .030F, suit, 1);
        box(side * .004F, .050F, .056F, .020F, .030F, .004F, cuff, 1);
        // The forearm, from the wrist back to an elbow outside the view.
        part.translate(side * .006F, .005F, .050F);
        Vector3f wrist = part.transformPosition(new Vector3f());
        Vector3f elbow = frame.transformPosition(new Vector3f(side * .60F, -.86F, .10F));
        limb(wrist, elbow, .040F, .046F, suit, cuff, .16F);
    }

    private void leg(int u, int side)
    {
        float[] suit = SUIT[u], cuff = CUFF[u];
        Vector3f hip = frame.transformPosition(new Vector3f(side * .12F, -.92F, .12F));
        Vector3f knee = frame.transformPosition(new Vector3f(side * .15F, -.70F, -.46F));
        Vector3f foot = frame.transformPosition(new Vector3f(side * .15F, -1.08F, -.86F));
        limb(knee, hip, .070F, .082F, suit, cuff, 0);
        limb(knee, foot, .064F, .056F, suit, cuff, 0);
        part.set(frame).translate(side * .15F, -.685F, -.47F).rotateX(-.55F);
        box(0, 0, 0, .078F, .050F, .078F, suit, 1);
        box(0, .052F, -.006F, .050F, .006F, .046F, cuff, 1);
    }

    /** A limb from one point to another: a box along it, thicker at the far end, with a band of the cuff's colour. */
    private void limb(Vector3f from, Vector3f to, float near, float far, float[] colour, float[] band, float bandAt)
    {
        Vector3f axis = new Vector3f(to).sub(from);
        float length = axis.length();
        if (length < 1e-4F) return;
        axis.div(length);
        Quaternionf turn = new Quaternionf().rotationTo(new Vector3f(0, 1, 0), axis);
        part.identity().translate(from).rotate(turn);
        float mid = (near + far) * .5F;
        if (bandAt > 0)
        {
            box(0, bandAt * .5F * length, 0, near, bandAt * .5F * length, near, colour, 1);
            box(0, bandAt * length + .012F, 0, near + .006F, .012F, near + .006F, band, 1);
            box(0, (1 + bandAt) * .5F * length + .012F, 0, mid, (1 - bandAt) * .5F * length - .012F, mid, colour, 1);
        }
        else box(0, length * .5F, 0, mid, length * .5F, mid, colour, 1);
    }

    // ----- the LCL -----

    private void surface(State s)
    {
        // A sheet at the height of the liquid, as wide as the plug and running on ahead; it lies level in the
        // plug, so it is turned and swayed with the seat. Seen from above while it rises, from below once over the eye.
        int across = 16, along = 18;
        float z0 = .6F, z1 = -26F;
        for (int i = 0; i < across; i++)
            for (int k = 0; k < along; k++)
            {
                // Rows are closer together near the pilot, where the ripples show, and the sheet widens with distance.
                float ta = (float) k / along, tb = (float) (k + 1) / along;
                float za = z0 + (z1 - z0) * ta * ta * ta, zb = z0 + (z1 - z0) * tb * tb * tb;
                float wa = 2.4F - za * 2.6F, wb = 2.4F - zb * 2.6F;
                float ua = (float) i / across * 2 - 1, ub = (float) (i + 1) / across * 2 - 1;
                wave(a, ua * wa, za, s); wave(b, ub * wa, za, s); wave(c, ub * wb, zb, s); wave(d, ua * wb, zb, s);
                sheet(a, s); sheet(b, s); sheet(c, s); sheet(d, s);
            }
    }

    private void wave(Vector3f out, float x, float z, State s)
    {
        float near = 1 / (1 + z * z * .08F);
        float ripple = (.012F * (float) Math.sin(x * 5.3F + s.time * 3.1F) + .010F * (float) Math.sin(z * 4.1F - s.time * 2.3F + x * 1.7F)) * near;
        out.set(x, s.lclLevel + ripple, z);
    }

    /** One corner of the sheet: lit by its own ripple, and thinner with distance so that it has no far edge. */
    private void sheet(Vector3f p, State s)
    {
        float glint = .5F + .5F * (float) Math.sin(p.x * 3.1F + p.z * 2.3F + s.time * 2.2F);
        float shade = .88F + .12F * glint;
        float fade = 1 / (1 + p.z * p.z * .012F);
        float alpha = s.lclAlpha * (.35F + .65F * fade);
        frame.transformPosition(p);
        if (clearCount + 7 > clear.length) clear = java.util.Arrays.copyOf(clear, clear.length * 2);
        clearCount = put(clear, clearCount, p, LCL[0] * shade, Math.min(1, LCL[1] * shade + .08F * glint), LCL[2] * shade + .06F * glint, alpha);
    }

    private void bubbles(State s)
    {
        int most = Math.round(46 * Math.min(1, s.bubbles));
        for (int i = 0; i < most; i++)
        {
            // Each bubble has its own column, speed and size; it rises from the floor and starts again.
            float seed = i * 12.9898F;
            float x = (hash(seed) - .5F) * 1.7F, z = -.18F - hash(seed + 3.1F) * 1.9F;
            float speed = .45F + .55F * hash(seed + 7.7F), size = .006F + .016F * hash(seed + 5.3F);
            float span = 1.75F, phase = (s.time * speed + hash(seed + 1.3F) * span) % span;
            float y = -1.0F + phase;
            if (y > s.lclLevel - size) continue;
            x += .02F * (float) Math.sin(s.time * 3.0F + seed);
            Vector3f at = frame.transformPosition(new Vector3f(x, y, z));
            float fade = Math.min(1, (s.lclLevel - y) * 6) * s.lclAlpha;
            disc(at, size, 1F, .86F, .62F, .30F * fade, 1F, .95F, .82F, .80F * fade);
        }
    }

    /** A bubble facing the eye: a pale disc with a bright rim. */
    private void disc(Vector3f at, float radius, float r, float g, float bl, float alpha, float rr, float rg, float rb, float rim)
    {
        Vector3f toEye = new Vector3f(at).negate().normalize();
        Vector3f right = new Vector3f(0, 1, 0).cross(toEye).normalize(), up = new Vector3f(toEye).cross(right);
        int sides = 8;
        for (int i = 0; i < sides; i++)
        {
            float t0 = (float) (Math.PI * 2 * i / sides), t1 = (float) (Math.PI * 2 * (i + 1) / sides);
            ring(a, at, right, up, radius * .72F, t0); ring(b, at, right, up, radius * .72F, t1);
            c.set(at); d.set(at);
            quad(false, a, b, c, d, r, g, bl, alpha);
            ring(c, at, right, up, radius, t1); ring(d, at, right, up, radius, t0);
            quad(false, a, b, c, d, rr, rg, rb, rim);
        }
    }

    private static void ring(Vector3f out, Vector3f at, Vector3f right, Vector3f up, float radius, float angle)
    {
        float cos = (float) Math.cos(angle) * radius, sin = (float) Math.sin(angle) * radius;
        out.set(at.x + right.x * cos + up.x * sin, at.y + right.y * cos + up.y * sin, at.z + right.z * cos + up.z * sin);
    }

    private static float hash(float value)
    {
        float x = (float) Math.sin(value) * 43758.547F;
        return x - (float) Math.floor(x);
    }

    // ----- boxes -----

    private static final float[][] CORNER = {{-1, -1, -1}, {1, -1, -1}, {1, 1, -1}, {-1, 1, -1}, {-1, -1, 1}, {1, -1, 1}, {1, 1, 1}, {-1, 1, 1}};
    private static final int[][] FACE = {{0, 3, 2, 1}, {4, 5, 6, 7}, {0, 4, 7, 3}, {1, 2, 6, 5}, {3, 7, 6, 2}, {0, 1, 5, 4}};
    private static final float[][] NORMAL = {{0, 0, -1}, {0, 0, 1}, {-1, 0, 0}, {1, 0, 0}, {0, 1, 0}, {0, -1, 0}};
    private final Vector3f[] corner = {new Vector3f(), new Vector3f(), new Vector3f(), new Vector3f(), new Vector3f(), new Vector3f(), new Vector3f(), new Vector3f()};

    /** A box in the current part's space. glow: 1 lit by the wall, 2 half its own light, 3 its own light. */
    private void box(float x, float y, float z, float hx, float hy, float hz, float[] colour, int glow)
    {
        for (int i = 0; i < 8; i++)
            part.transformPosition(corner[i].set(x + CORNER[i][0] * hx, y + CORNER[i][1] * hy, z + CORNER[i][2] * hz));
        for (int f = 0; f < 6; f++)
        {
            part.transformDirection(n.set(NORMAL[f][0], NORMAL[f][1], NORMAL[f][2])).normalize();
            // A face turned away from the eye is never seen: the eye is the origin.
            Vector3f first = corner[FACE[f][0]];
            if (n.dot(first) >= 0) continue;
            float lit = Math.max(0, n.dot(SUN)), sky = .5F + .5F * n.y;
            float shade = glow == 3 ? 1F : (.20F + .22F * sky + .62F * lit) * light;
            if (glow == 2) shade = .55F + .45F * shade;
            quad(true, corner[FACE[f][0]], corner[FACE[f][1]], corner[FACE[f][2]], corner[FACE[f][3]],
                    Math.min(1, colour[0] * shade), Math.min(1, colour[1] * shade), Math.min(1, colour[2] * shade), 1);
        }
    }

    private void quad(boolean opaque, Vector3f p0, Vector3f p1, Vector3f p2, Vector3f p3, float r, float g, float bl, float alpha)
    {
        if (opaque)
        {
            if (solidCount + 28 > solid.length) solid = java.util.Arrays.copyOf(solid, solid.length * 2);
            solidCount = put(solid, solidCount, p0, r, g, bl, alpha);
            solidCount = put(solid, solidCount, p1, r, g, bl, alpha);
            solidCount = put(solid, solidCount, p2, r, g, bl, alpha);
            solidCount = put(solid, solidCount, p3, r, g, bl, alpha);
        }
        else
        {
            if (clearCount + 28 > clear.length) clear = java.util.Arrays.copyOf(clear, clear.length * 2);
            clearCount = put(clear, clearCount, p0, r, g, bl, alpha);
            clearCount = put(clear, clearCount, p1, r, g, bl, alpha);
            clearCount = put(clear, clearCount, p2, r, g, bl, alpha);
            clearCount = put(clear, clearCount, p3, r, g, bl, alpha);
        }
    }

    private static int put(float[] into, int at, Vector3f p, float r, float g, float bl, float alpha)
    {
        into[at] = p.x; into[at + 1] = p.y; into[at + 2] = p.z;
        into[at + 3] = r; into[at + 4] = g; into[at + 5] = bl; into[at + 6] = alpha;
        return at + 7;
    }
}
