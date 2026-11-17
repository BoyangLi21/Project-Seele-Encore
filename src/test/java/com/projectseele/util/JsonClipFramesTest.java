package com.projectseele.util;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/** Dropping per-bone channels must leave everything else in a profile reading exactly as before, and the source untouched. */
public final class JsonClipFramesTest
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    public static void main(String[] args)
    {
        String text = "{\"schema\":2,\"rig_key\":1,\"bones\":[\"root\",\"hip\"],\"support_toes\":{\"l\":[1,2,3]},\"clips\":{"
                + "\"r32_jab\":{\"duration_seconds\":0.5,\"loop\":false,\"trajectory_m\":[[0,0,0],[0,0,1]],\"frames\":["
                + "{\"root_m\":[0,1,0],\"rotation_wxyz\":[[1,0,0,0],[0.7,0.7,0,0]],\"foot_contact\":[true,false],\"bone_position_xyz\":{\"hip\":[-0.0,0.0,0.0]}},"
                + "{\"root_m\":[0,1,0.5],\"rotation_wxyz\":[[1,0,0,0],[0.6,0.8,0,0]],\"foot_contact\":[false,true],\"bone_position_xyz\":{},\"handling_r45\":{\"grip\":1}}]},"
                + "\"r32_note\":{\"duration_seconds\":1.0},"
                + "\"odd\":7}}";
        JsonObject profile = JsonParser.parseString(text).getAsJsonObject();
        String before = profile.toString();
        JsonObject stripped = JsonClipFrames.without(profile, "rotation_wxyz", "bone_position_xyz");
        check(profile.toString().equals(before), "The given profile was changed");
        check(stripped != profile, "A new root is expected");

        String expected = "{\"schema\":2,\"rig_key\":1,\"bones\":[\"root\",\"hip\"],\"support_toes\":{\"l\":[1,2,3]},\"clips\":{"
                + "\"r32_jab\":{\"duration_seconds\":0.5,\"loop\":false,\"trajectory_m\":[[0,0,0],[0,0,1]],\"frames\":["
                + "{\"root_m\":[0,1,0],\"foot_contact\":[true,false]},"
                + "{\"root_m\":[0,1,0.5],\"foot_contact\":[false,true],\"handling_r45\":{\"grip\":1}}]},"
                + "\"r32_note\":{\"duration_seconds\":1.0},"
                + "\"odd\":7}}";
        check(stripped.toString().equals(expected), "Only the named frame keys may go, in the same order: " + stripped);

        // Everything kept is the very same element, not a copy.
        check(stripped.get("bones") == profile.get("bones") && stripped.get("support_toes") == profile.get("support_toes"), "Top-level values must be shared");
        JsonObject jab = stripped.getAsJsonObject("clips").getAsJsonObject("r32_jab"), sourceJab = profile.getAsJsonObject("clips").getAsJsonObject("r32_jab");
        check(jab.get("trajectory_m") == sourceJab.get("trajectory_m"), "Clip values must be shared");
        check(jab.getAsJsonArray("frames").get(0).getAsJsonObject().get("root_m") == sourceJab.getAsJsonArray("frames").get(0).getAsJsonObject().get("root_m"),
                "Frame values must be shared");
        check(stripped.getAsJsonObject("clips").get("r32_note") == profile.getAsJsonObject("clips").get("r32_note"), "A clip without frames is kept as it is");
        check(sourceJab.getAsJsonArray("frames").get(0).getAsJsonObject().has("rotation_wxyz"), "The source frames keep their channels");

        JsonObject plain = JsonParser.parseString("{\"schema\":2}").getAsJsonObject();
        check(JsonClipFrames.without(plain, "rotation_wxyz") == plain, "A profile without clips is returned as it is");
        System.out.println("Clip frame channel checks passed: " + checks);
    }
}
