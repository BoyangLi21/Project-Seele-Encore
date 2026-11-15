package com.projectseele.util;

import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.util.HashMap;
import java.util.Map;

/**
 * For pose clips that stay in memory for the whole session. A clip holds one Quaternionf and one
 * Vector3f per bone per frame: 2.0 million of each across the body and gameplay clips, 130 MB, of
 * which only 320,000 rotations and 72,000 positions differ (most bones carry no offset, and a bone
 * at rest repeats its rotation frame after frame).
 *
 * share() replaces every entry of the frame rows by one instance per value. Values are compared
 * bit for bit, so 0.0 and -0.0 stay apart. The shared instances must only be read: changing a clip
 * entry in place would change every frame that holds the same value.
 */
public final class SharedPoseValues
{
    private record Rotation(int x, int y, int z, int w) { }
    private record Position(int x, int y, int z) { }
    private final Map<Rotation, Quaternionf> rotations = new HashMap<>();
    private final Map<Position, Vector3f> positions = new HashMap<>();

    public void share(Quaternionf[][] frames)
    {
        for (Quaternionf[] frame : frames)
        {
            if (frame == null) continue;
            for (int bone = 0; bone < frame.length; bone++)
            {
                Quaternionf value = frame[bone];
                if (value == null) continue;
                frame[bone] = this.rotations.computeIfAbsent(new Rotation(Float.floatToRawIntBits(value.x),
                        Float.floatToRawIntBits(value.y), Float.floatToRawIntBits(value.z), Float.floatToRawIntBits(value.w)), key -> value);
            }
        }
    }

    public void share(Vector3f[][] frames)
    {
        for (Vector3f[] frame : frames)
        {
            if (frame == null) continue;
            for (int bone = 0; bone < frame.length; bone++)
            {
                Vector3f value = frame[bone];
                if (value == null) continue;
                frame[bone] = this.positions.computeIfAbsent(new Position(Float.floatToRawIntBits(value.x),
                        Float.floatToRawIntBits(value.y), Float.floatToRawIntBits(value.z)), key -> value);
            }
        }
    }
}
