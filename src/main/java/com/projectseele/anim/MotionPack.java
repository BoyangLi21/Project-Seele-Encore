package com.projectseele.anim;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.CombatMotionResourcesR44;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * Baked motion produced by tools/motion3 (Blender is the source of truth).
 *
 * Every clip stores model-space data that the runtime samples directly:
 * per-frame bone quaternions (w,x,y,z) for the animated bones, the root
 * translation in model blocks and two foot-contact flags.  Loop cycles are
 * stored in place; {@code stride} is the model-space distance one cycle covers.
 */
public final class MotionPack
{
    public static final String FILE = "seele_motion_pack.json";

    public static final class Clip
    {
        public final String name;
        public final String[] bones;
        public final int frames;
        public final float rate;
        public final boolean loop;
        public final float duration;
        public final float stride;
        private final float[] rot;
        private final float[] root;
        private final byte[] contact;

        Clip(String name, JsonObject json)
        {
            this.name = name;
            JsonArray names = json.getAsJsonArray("bones");
            this.bones = new String[names.size()];
            for (int i = 0; i < bones.length; i++)
            {
                bones[i] = names.get(i).getAsString();
            }
            this.frames = json.get("frames").getAsInt();
            this.rate = json.get("rate").getAsFloat();
            this.loop = json.get("loop").getAsBoolean();
            this.duration = json.get("duration").getAsFloat();
            this.stride = json.get("stride").getAsFloat();
            this.rot = floats(json.getAsJsonArray("rot"));
            this.root = floats(json.getAsJsonArray("root"));
            JsonArray c = json.getAsJsonArray("contact");
            this.contact = new byte[c.size()];
            for (int i = 0; i < contact.length; i++)
            {
                contact[i] = (byte) c.get(i).getAsInt();
            }
            if (rot.length != frames * bones.length * 4 || root.length != frames * 3
                    || contact.length != frames * 2 || frames < 2)
            {
                throw new IllegalArgumentException("Malformed motion clip " + name);
            }
        }

        /** Seconds of a non-loop clip, or one full cycle of a loop. */
        public float length()
        {
            return loop ? frames / rate : (frames - 1) / rate;
        }

        /** Frame position for a cycle phase (loops) or clamped normalised time. */
        public float framePosition(float phase)
        {
            if (loop)
            {
                float p = phase - (float) Math.floor(phase);
                return p * frames;
            }
            float p = Math.max(0, Math.min(1, phase));
            return p * (frames - 1);
        }

        /**
         * Adds this clip, weighted, into the accumulators.  Quaternions are
         * summed hemisphere-aligned (normalised later), which matches slerp
         * for the small angular differences between neighbouring blend inputs.
         */
        public void accumulate(float framePos, float weight, Map<String, Quaternionf> rotAcc,
                               Vector3f rootAcc)
        {
            int f0 = (int) Math.floor(framePos);
            float t = framePos - f0;
            int f1;
            if (loop)
            {
                f0 = Math.floorMod(f0, frames);
                f1 = (f0 + 1) % frames;
            }
            else
            {
                f0 = Math.max(0, Math.min(frames - 1, f0));
                f1 = Math.min(frames - 1, f0 + 1);
            }
            Quaternionf a = new Quaternionf();
            Quaternionf b = new Quaternionf();
            for (int i = 0; i < bones.length; i++)
            {
                read(f0, i, a);
                read(f1, i, b);
                a.slerp(b, t);
                Quaternionf acc = rotAcc.get(bones[i]);
                if (acc == null)
                {
                    rotAcc.put(bones[i], new Quaternionf(a.x * weight, a.y * weight, a.z * weight, a.w * weight));
                }
                else
                {
                    float s = acc.dot(a) < 0 ? -weight : weight;
                    acc.x += a.x * s;
                    acc.y += a.y * s;
                    acc.z += a.z * s;
                    acc.w += a.w * s;
                }
            }
            int r0 = f0 * 3;
            int r1 = f1 * 3;
            rootAcc.x += weight * (root[r0] + (root[r1] - root[r0]) * t);
            rootAcc.y += weight * (root[r0 + 1] + (root[r1 + 1] - root[r0 + 1]) * t);
            rootAcc.z += weight * (root[r0 + 2] + (root[r1 + 2] - root[r0 + 2]) * t);
        }

        private void read(int frame, int bone, Quaternionf out)
        {
            int o = (frame * bones.length + bone) * 4;
            out.set(rot[o + 1], rot[o + 2], rot[o + 3], rot[o]);
        }

        public boolean contact(float framePos, int side)
        {
            int f = loop ? Math.floorMod(Math.round(framePos), frames)
                    : Math.max(0, Math.min(frames - 1, Math.round(framePos)));
            return contact[f * 2 + side] != 0;
        }
    }

    public static final class Variant
    {
        public final Map<String, Clip> clips;

        Variant(Map<String, Clip> clips)
        {
            this.clips = Map.copyOf(clips);
        }

        public Clip clip(String name)
        {
            return clips.get(name);
        }
    }

    private static volatile MotionPack loaded;
    private static volatile boolean attempted;

    public final Map<Integer, Variant> variants;
    public final String source;
    private final Map<Integer, JsonObject> handPoses;

    private MotionPack(Map<Integer, Variant> variants, Map<Integer, JsonObject> handPoses, String source)
    {
        this.variants = Map.copyOf(variants);
        this.handPoses = Map.copyOf(handPoses);
        this.source = source;
    }

    /** Fitted anatomical hand poses for a rig key ({pose: {bone_angles}}), or null. */
    public static JsonObject handPoses(int rigKey)
    {
        MotionPack pack = get();
        return pack == null ? null : pack.handPoses.get(rigKey);
    }

    /** The active pack, or null when no pack is installed. */
    public static MotionPack get()
    {
        if (!attempted)
        {
            synchronized (MotionPack.class)
            {
                if (!attempted)
                {
                    loaded = load();
                    attempted = true;
                }
            }
        }
        return loaded;
    }

    public static synchronized void reload()
    {
        attempted = false;
        loaded = null;
    }

    public Variant variant(int rigKey)
    {
        return variants.get(rigKey);
    }

    private static MotionPack load()
    {
        try
        {
            Path file;
            try
            {
                file = CombatMotionResourcesR44.resolve("projectseele.motionPackDirectory", FILE);
            }
            catch (IllegalStateException missingFromBundle)
            {
                file = null;
            }
            JsonObject json = null;
            String source;
            if (file != null && Files.isRegularFile(file))
            {
                try (var reader = Files.newBufferedReader(file, StandardCharsets.UTF_8))
                {
                    json = JsonParser.parseReader(reader).getAsJsonObject();
                }
                source = file.toAbsolutePath().normalize().toString();
            }
            else
            {
                InputStream stream = MotionPack.class.getResourceAsStream("/assets/projectseele/motion/" + FILE);
                if (stream == null)
                {
                    ProjectSeele.LOGGER.info("SEELE motion pack not installed; legacy EVA pose path stays active");
                    return null;
                }
                try (var reader = new InputStreamReader(stream, StandardCharsets.UTF_8))
                {
                    json = JsonParser.parseReader(reader).getAsJsonObject();
                }
                source = "classpath:" + FILE;
            }
            if (!"seele-motion-pack".equals(json.get("format").getAsString()) || json.get("version").getAsInt() != 1)
            {
                throw new IllegalArgumentException("Unsupported motion pack format");
            }
            Map<Integer, Variant> variants = new HashMap<>();
            for (var entry : json.getAsJsonObject("variants").entrySet())
            {
                Map<String, Clip> clips = new HashMap<>();
                for (var clip : entry.getValue().getAsJsonObject().getAsJsonObject("clips").entrySet())
                {
                    clips.put(clip.getKey(), new Clip(clip.getKey(), clip.getValue().getAsJsonObject()));
                }
                variants.put(Integer.parseInt(entry.getKey()), new Variant(clips));
            }
            Map<Integer, JsonObject> handPoses = new HashMap<>();
            if (json.has("hand_poses"))
            {
                for (var entry : json.getAsJsonObject("hand_poses").entrySet())
                {
                    handPoses.put(Integer.parseInt(entry.getKey()), entry.getValue().getAsJsonObject());
                }
            }
            ProjectSeele.LOGGER.info("SEELE motion pack loaded: source={} variants={} clips={} handPoses={}", source,
                    variants.keySet(), variants.values().stream().mapToInt(v -> v.clips.size()).sum(), handPoses.keySet());
            return new MotionPack(variants, handPoses, source);
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("SEELE motion pack failed to load; legacy EVA pose path stays active", failure);
            return null;
        }
    }

    private static float[] floats(JsonArray array)
    {
        float[] out = new float[array.size()];
        for (int i = 0; i < out.length; i++)
        {
            out[i] = array.get(i).getAsFloat();
        }
        return out;
    }
}
