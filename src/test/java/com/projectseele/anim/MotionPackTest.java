package com.projectseele.anim;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.entity.EvaBodyPose;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * Clip sampling kernel, plus (when the private data is supplied through
 * -Dseele.motionPack and -Dseele.bodyProfile) an end-to-end check that the
 * baked locomotion keeps planted feet on the ground through the runtime's
 * own pivot forward kinematics.
 */
public final class MotionPackTest
{
    public static void main(String[] args) throws Exception
    {
        kernel();
        String pack = System.getProperty("seele.motionPack", "");
        String body = System.getProperty("seele.bodyProfile", "");
        if (!pack.isEmpty() && !body.isEmpty() && Files.isRegularFile(Path.of(pack)) && Files.isRegularFile(Path.of(body)))
        {
            grounded(Path.of(pack), Path.of(body));
        }
        else
        {
            System.out.println("MotionPackTest: private pack/profile not supplied, kernel checks only");
        }
        System.out.println("MotionPackTest OK");
    }

    private static void kernel()
    {
        JsonObject json = new JsonObject();
        JsonArray bones = new JsonArray();
        bones.add("a");
        json.add("bones", bones);
        json.addProperty("frames", 4);
        json.addProperty("rate", 4);
        json.addProperty("loop", true);
        json.addProperty("duration", 1);
        json.addProperty("stride", 2);
        JsonArray rot = new JsonArray();
        JsonArray root = new JsonArray();
        JsonArray contact = new JsonArray();
        for (int f = 0; f < 4; f++)
        {
            Quaternionf q = new Quaternionf().rotationY((float) (f * Math.PI / 4));
            rot.add(q.w);
            rot.add(q.x);
            rot.add(q.y);
            rot.add(q.z);
            root.add(f);
            root.add(0);
            root.add(0);
            contact.add(f < 2 ? 1 : 0);
            contact.add(f < 2 ? 0 : 1);
        }
        json.add("rot", rot);
        json.add("root", root);
        json.add("contact", contact);
        MotionPack.Clip clip = new MotionPack.Clip("k", json);
        Map<String, Quaternionf> acc = new HashMap<>();
        Vector3f r = new Vector3f();
        clip.accumulate(clip.framePosition(0.125F), 1, acc, r);
        float angle = 2 * (float) Math.acos(Math.min(1, Math.abs(acc.get("a").normalize().w)));
        check(Math.abs(angle - Math.PI / 8) < 1e-3, "slerp half frame " + angle);
        check(Math.abs(r.x - 0.5F) < 1e-4, "root lerp " + r.x);
        acc.clear();
        r.zero();
        // last frame wraps back to frame 0 (in-place loop)
        clip.accumulate(clip.framePosition(0.875F), 1, acc, r);
        check(Math.abs(r.x - 1.5F) < 1e-4, "root wrap " + r.x);
        check(clip.contact(clip.framePosition(0.1F), 0) && !clip.contact(clip.framePosition(0.6F), 0), "contacts");
    }

    private static void grounded(Path packFile, Path bodyFile) throws Exception
    {
        JsonObject pack = JsonParser.parseString(Files.readString(packFile)).getAsJsonObject();
        JsonObject body = JsonParser.parseString(Files.readString(bodyFile)).getAsJsonObject();
        for (var entry : pack.getAsJsonObject("variants").entrySet())
        {
            Map<String, EvaBodyPose.Bone> rig = new HashMap<>();
            for (var e : body.getAsJsonObject("rigs").getAsJsonArray(entry.getKey()))
            {
                JsonObject b = e.getAsJsonObject();
                JsonArray p = b.getAsJsonArray("pivot");
                String parent = b.has("parent") && !b.get("parent").isJsonNull() ? b.get("parent").getAsString() : null;
                Vector3f pivot = new Vector3f(-p.get(0).getAsFloat(), p.get(1).getAsFloat(), p.get(2).getAsFloat()).div(16);
                rig.put(b.get("name").getAsString(), new EvaBodyPose.Bone(b.get("name").getAsString(), parent, pivot, new Quaternionf()));
            }
            float restAnkle = rig.get("ankle_l").pivot().y;
            for (var clipEntry : entry.getValue().getAsJsonObject().getAsJsonObject("clips").entrySet())
            {
                MotionPack.Clip clip = new MotionPack.Clip(clipEntry.getKey(), clipEntry.getValue().getAsJsonObject());
                float worst = 0;
                float lowest = Float.POSITIVE_INFINITY;
                for (int i = 0; i < 40; i++)
                {
                    float phase = i / 40F;
                    Map<String, Quaternionf> acc = new HashMap<>();
                    Vector3f root = new Vector3f();
                    float pos = clip.framePosition(phase);
                    clip.accumulate(pos, 1, acc, root);
                    EvaBodyPose.Sample s = new EvaBodyPose.Sample(rig);
                    acc.forEach((k, q) -> { if (rig.containsKey(k)) s.rotations.put(k, q.normalize()); });
                    s.positions.get("root").set(root);
                    s.dirty();
                    for (int side = 0; side < 2; side++)
                    {
                        String ankle = side == 0 ? "ankle_l" : "ankle_r";
                        Vector3f world = s.matrix(ankle).transformPosition(new Vector3f(rig.get(ankle).pivot()));
                        lowest = Math.min(lowest, world.y);
                        if (clip.contact(pos, side))
                        {
                            worst = Math.max(worst, Math.abs(world.y - restAnkle));
                        }
                    }
                }
                System.out.printf("variant %s %-10s planted ankle error %.3f, lowest ankle %.3f (rest %.3f)%n",
                        entry.getKey(), clip.name, worst, lowest, restAnkle);
                // attacks plant on the ball of the foot; loops must keep the whole sole down
                check(worst < (clip.loop ? 0.45F : 0.65F), "planted ankle leaves the ground: " + clip.name + " " + worst);
                check(lowest > restAnkle - 0.45F, "ankle sinks below ground: " + clip.name + " " + lowest);
            }
        }
    }

    private static void check(boolean ok, String message)
    {
        if (!ok)
        {
            throw new AssertionError(message);
        }
    }
}
