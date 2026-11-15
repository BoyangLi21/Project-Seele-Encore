package com.projectseele.util;

import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.util.IdentityHashMap;
import java.util.Map;
import java.util.Random;

/** After sharing, every clip entry must hold the bits it held before, and equal entries one instance. */
public final class SharedPoseValuesTest
{
    public static void main(String[] args)
    {
        Random random = new Random(64);
        int frames = 60, bones = 40;
        Quaternionf[][] rotations = new Quaternionf[frames][bones];
        Vector3f[][] positions = new Vector3f[frames][bones];
        int[][][] rotationBits = new int[frames][bones][];
        int[][][] positionBits = new int[frames][bones][];
        for (int f = 0; f < frames; f++)
        {
            for (int b = 0; b < bones; b++)
            {
                // A third of the bones rest; the rest move. Offsets are zero except on the first bone,
                // and a zero offset is written both as 0.0 and as -0.0 (what mul(-1,1,1) leaves behind).
                rotations[f][b] = b % 3 == 0 ? new Quaternionf(.1F * b, 0, 0, 1).normalize()
                        : new Quaternionf(random.nextFloat(), random.nextFloat(), random.nextFloat(), random.nextFloat()).normalize();
                positions[f][b] = b == 0 ? new Vector3f(random.nextFloat(), 1, 2) : new Vector3f(f % 2 == 0 ? 0F : -0F, 0, 0);
                rotationBits[f][b] = bits(rotations[f][b]);
                positionBits[f][b] = bits(positions[f][b]);
            }
        }
        // A second clip that shares a row array with the first, the way an overlay clip does.
        Quaternionf[][] overlay = rotations.clone();
        overlay[5] = overlay[5].clone();
        overlay[5][1] = new Quaternionf(rotations[5][1]);

        SharedPoseValues shared = new SharedPoseValues();
        shared.share(rotations);
        shared.share(positions);
        shared.share(overlay);

        Map<Quaternionf, Boolean> rotationInstances = new IdentityHashMap<>();
        Map<Vector3f, Boolean> positionInstances = new IdentityHashMap<>();
        Map<String, Quaternionf> rotationOf = new java.util.HashMap<>();
        Map<String, Vector3f> positionOf = new java.util.HashMap<>();
        for (int f = 0; f < frames; f++)
        {
            for (int b = 0; b < bones; b++)
            {
                if (!java.util.Arrays.equals(bits(rotations[f][b]), rotationBits[f][b])) throw new AssertionError("A rotation changed at frame " + f + " bone " + b);
                if (!java.util.Arrays.equals(bits(positions[f][b]), positionBits[f][b])) throw new AssertionError("A position changed at frame " + f + " bone " + b);
                rotationInstances.put(rotations[f][b], Boolean.TRUE);
                positionInstances.put(positions[f][b], Boolean.TRUE);
                Quaternionf firstRotation = rotationOf.putIfAbsent(java.util.Arrays.toString(rotationBits[f][b]), rotations[f][b]);
                if (firstRotation != null && firstRotation != rotations[f][b]) throw new AssertionError("Equal rotations kept two instances");
                Vector3f firstPosition = positionOf.putIfAbsent(java.util.Arrays.toString(positionBits[f][b]), positions[f][b]);
                if (firstPosition != null && firstPosition != positions[f][b]) throw new AssertionError("Equal positions kept two instances");
            }
        }
        if (rotationInstances.size() != rotationOf.size() || positionInstances.size() != positionOf.size()) throw new AssertionError("Two values share an instance");
        if (rotationInstances.size() >= frames * bones || positionInstances.size() >= frames * bones) throw new AssertionError("Nothing was shared");
        // 0.0 and -0.0 are different offsets and must not have been merged.
        if (positions[0][1] == positions[1][1] || Float.floatToRawIntBits(positions[1][1].x) != Float.floatToRawIntBits(-0F)) throw new AssertionError("0.0 and -0.0 were merged");
        if (overlay[5][1] != rotations[5][1]) throw new AssertionError("The overlay's own copy was not shared with its equal");
        System.out.println("Shared pose values read as before: " + frames * bones + " rotations on " + rotationInstances.size()
                + " instances, " + frames * bones + " positions on " + positionInstances.size());
    }

    private static int[] bits(Quaternionf q)
    {
        return new int[] {Float.floatToRawIntBits(q.x), Float.floatToRawIntBits(q.y), Float.floatToRawIntBits(q.z), Float.floatToRawIntBits(q.w)};
    }

    private static int[] bits(Vector3f v)
    {
        return new int[] {Float.floatToRawIntBits(v.x), Float.floatToRawIntBits(v.y), Float.floatToRawIntBits(v.z)};
    }
}
