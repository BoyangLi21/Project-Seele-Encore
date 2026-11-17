import com.projectseele.client.cockpit.CockpitMeshR64;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Draws the pilot's cockpit (CockpitMeshR64) without the game, over a plain picture of a city under a sky, so that
 * its layout can be judged in seconds. See tools/cockpit_preview/README.md for how to run it.
 * <p>
 * The same vertices the game draws go through a small software rasteriser here: the vertical field of view is the
 * one the game uses for the cockpit (PilotCockpitR64.FOV), the near plane the same.
 */
public final class CockpitPreview
{
    private static final int W = 1280, H = 720, SS = 2;
    private static final float FOV = 70, NEAR = .05F;

    public static void main(String[] args) throws Exception
    {
        File out = new File(args.length > 0 ? args[0] : "cockpit_preview");
        out.mkdirs();
        // name, unit, cockpit pitch, left push, right push, tilt, right trigger, LCL level, LCL alpha, bubbles, light
        Object[][] shots = {
                {"01_level", 1, .10F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"02_forward", 1, .10F, 1F, 1F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"03_strike", 1, .10F, .3F, 1F, .4F, 1F, -9F, 0F, 0F, 1F},
                {"04_look_down", 1, .46F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"05_look_up", 1, -.20F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"06_unit00", 0, .2F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"07_unit02", 2, .2F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 1F},
                {"08_dark", 1, .2F, 0F, 0F, 0F, 0F, -9F, 0F, 0F, 0F},
                {"10_lcl_knees", 1, .2F, 0F, 0F, 0F, 0F, -.78F, .62F, 1F, .4F},
                {"11_lcl_chest", 1, .2F, 0F, 0F, 0F, 0F, -.35F, .62F, 1F, .4F},
                {"12_lcl_chin", 1, .1F, 0F, 0F, 0F, 0F, -.08F, .62F, 1F, .4F},
                {"13_lcl_under", 1, .1F, 0F, 0F, 0F, 0F, .12F, .62F, 1F, .4F},
                {"14_lcl_full", 1, .1F, 0F, 0F, 0F, 0F, .7F, .62F, 1F, .6F},
                {"15_lcl_settled", 1, .1F, 0F, 0F, 0F, 0F, .7F, .10F, .08F, 1F},
        };
        CockpitMeshR64 mesh = new CockpitMeshR64();
        for (Object[] shot : shots)
        {
            CockpitMeshR64.State s = new CockpitMeshR64.State();
            s.unit = (Integer) shot[1]; s.pitch = (Float) shot[2]; s.leftPush = (Float) shot[3]; s.rightPush = (Float) shot[4];
            s.leftTilt = s.rightTilt = (Float) shot[5]; s.rightTrigger = (Float) shot[6];
            s.lclLevel = (Float) shot[7]; s.lclAlpha = (Float) shot[8]; s.bubbles = (Float) shot[9]; s.light = (Float) shot[10];
            s.time = 3.7F;
            mesh.build(s);
            // Under the surface the whole view is in the liquid: the game lays that tint over the picture.
            float under = s.lclAlpha <= 0 ? 0 : clamp((s.lclLevel + .04F) / .10F, 0, 1) * s.lclAlpha * .68F;
            BufferedImage image = draw(mesh, s.light, under);
            ImageIO.write(image, "png", new File(out, shot[0] + ".png"));
            System.out.println(shot[0] + ": " + mesh.solidCount / 28 + " solid quads, " + mesh.clearCount / 28 + " clear quads");
        }
    }

    private static BufferedImage draw(CockpitMeshR64 mesh, float light, float under)
    {
        int w = W * SS, h = H * SS;
        float[] colour = new float[w * h * 3], depth = new float[w * h];
        java.util.Arrays.fill(depth, Float.MAX_VALUE);
        background(colour, w, h, light);
        if (under > 0)
            for (int i = 0; i < w * h; i++)
                for (int k = 0; k < 3; k++) colour[i * 3 + k] += (CockpitMeshR64.LCL[k] - colour[i * 3 + k]) * under;
        float f = (float) (1 / Math.tan(Math.toRadians(FOV) / 2)), aspect = (float) W / H;
        for (int q = 0; q < mesh.solidCount; q += 28) polygon(mesh.solid, q, colour, depth, w, h, f, aspect, true);
        // See-through quads from the farthest to the nearest.
        List<Integer> order = new ArrayList<>();
        for (int q = 0; q < mesh.clearCount; q += 28) order.add(q);
        order.sort((x, y) -> Float.compare(distance(mesh.clear, y), distance(mesh.clear, x)));
        for (int q : order) polygon(mesh.clear, q, colour, depth, w, h, f, aspect, false);
        BufferedImage image = new BufferedImage(W, H, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++)
            {
                float r = 0, g = 0, b = 0;
                for (int sy = 0; sy < SS; sy++)
                    for (int sx = 0; sx < SS; sx++)
                    {
                        int i = ((y * SS + sy) * w + x * SS + sx) * 3;
                        r += colour[i]; g += colour[i + 1]; b += colour[i + 2];
                    }
                int n = SS * SS;
                image.setRGB(x, y, (to8(r / n) << 16) | (to8(g / n) << 8) | to8(b / n));
            }
        return image;
    }

    private static float distance(float[] v, int q)
    {
        float x = 0, y = 0, z = 0;
        for (int i = 0; i < 4; i++) { x += v[q + i * 7]; y += v[q + i * 7 + 1]; z += v[q + i * 7 + 2]; }
        return x * x + y * y + z * z;
    }

    /** One quad: cut at the near plane, then filled as a fan of triangles. */
    private static void polygon(float[] v, int q, float[] colour, float[] depth, int w, int h, float f, float aspect, boolean opaque)
    {
        float[][] in = new float[4][];
        for (int i = 0; i < 4; i++) in[i] = java.util.Arrays.copyOfRange(v, q + i * 7, q + i * 7 + 7);
        List<float[]> cut = new ArrayList<>();
        for (int i = 0; i < 4; i++)
        {
            float[] p = in[i], n = in[(i + 1) % 4];
            boolean pin = p[2] <= -NEAR, nin = n[2] <= -NEAR;
            if (pin) cut.add(p);
            if (pin != nin)
            {
                float t = (-NEAR - p[2]) / (n[2] - p[2]);
                float[] m = new float[7];
                for (int k = 0; k < 7; k++) m[k] = p[k] + (n[k] - p[k]) * t;
                cut.add(m);
            }
        }
        if (cut.size() < 3) return;
        float[][] s = new float[cut.size()][];
        for (int i = 0; i < s.length; i++)
        {
            float[] p = cut.get(i);
            float iz = -1 / p[2];
            s[i] = new float[]{(p[0] * f / aspect * iz * .5F + .5F) * w, (.5F - p[1] * f * iz * .5F) * h, -p[2], p[3], p[4], p[5], p[6]};
        }
        for (int i = 1; i + 1 < s.length; i++) triangle(s[0], s[i], s[i + 1], colour, depth, w, h, opaque);
    }

    private static void triangle(float[] a, float[] b, float[] c, float[] colour, float[] depth, int w, int h, boolean opaque)
    {
        int x0 = (int) Math.max(0, Math.floor(Math.min(a[0], Math.min(b[0], c[0])))), x1 = (int) Math.min(w - 1, Math.ceil(Math.max(a[0], Math.max(b[0], c[0]))));
        int y0 = (int) Math.max(0, Math.floor(Math.min(a[1], Math.min(b[1], c[1])))), y1 = (int) Math.min(h - 1, Math.ceil(Math.max(a[1], Math.max(b[1], c[1]))));
        float area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
        if (Math.abs(area) < 1e-6F) return;
        for (int y = y0; y <= y1; y++)
            for (int x = x0; x <= x1; x++)
            {
                float px = x + .5F, py = y + .5F;
                float wa = ((b[0] - px) * (c[1] - py) - (b[1] - py) * (c[0] - px)) / area;
                float wb = ((c[0] - px) * (a[1] - py) - (c[1] - py) * (a[0] - px)) / area;
                float wc = 1 - wa - wb;
                if (wa < 0 || wb < 0 || wc < 0) continue;
                // Depth across the screen goes with one over the distance.
                float z = 1 / (wa / a[2] + wb / b[2] + wc / c[2]);
                int i = y * w + x;
                if (z >= depth[i]) continue;
                float alpha = wa * a[6] + wb * b[6] + wc * c[6];
                for (int k = 0; k < 3; k++)
                {
                    float value = wa * a[3 + k] + wb * b[3 + k] + wc * c[3 + k];
                    colour[i * 3 + k] = opaque ? value : colour[i * 3 + k] + (value - colour[i * 3 + k]) * alpha;
                }
                if (opaque) depth[i] = z;
            }
    }

    /** A sky, a ground and a row of towers: enough to judge the cockpit against a bright and a dark picture. */
    private static void background(float[] colour, int w, int h, float light)
    {
        java.util.Random random = new java.util.Random(7);
        int[] tower = new int[48];
        for (int i = 0; i < tower.length; i++) tower[i] = random.nextInt(100) < 55 ? 20 + random.nextInt(150) : 0;
        for (int y = 0; y < h; y++)
        {
            float v = (float) y / h;
            for (int x = 0; x < w; x++)
            {
                float r, g, b;
                if (v < .52F) { float t = v / .52F; r = .42F + .36F * t; g = .58F + .28F * t; b = .86F + .08F * t; }
                else { float t = (v - .52F) / .48F; r = .36F - .12F * t; g = .40F - .12F * t; b = .34F - .12F * t; }
                int column = x * tower.length / w;
                int top = (int) (.52F * h) - tower[column] * SS;
                if (tower[column] > 0 && y >= top && v < .56F) { r = .30F; g = .33F; b = .37F; if ((x / (6 * SS) + y / (8 * SS)) % 3 == 0) { r += .1F; g += .1F; b += .08F; } }
                float dim = .25F + .75F * light;
                int i = (y * w + x) * 3;
                colour[i] = r * dim; colour[i + 1] = g * dim; colour[i + 2] = b * dim;
            }
        }
    }

    private static float clamp(float v, float lo, float hi) { return Math.max(lo, Math.min(hi, v)); }
    private static int to8(float v) { return Math.max(0, Math.min(255, Math.round(v * 255))); }
}
