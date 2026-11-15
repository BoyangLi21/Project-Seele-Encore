package com.projectseele.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.Map;
import java.util.Set;

/**
 * A motion profile keeps its clips as parsed JSON for the whole session, and nine tenths of that tree is each
 * frame's per-bone channels, which are read once to build the pose clips and never again.
 *
 * without() gives a profile that reads the same except that the named keys are gone from every frame of every
 * clip. The given profile is not changed: the result is a new root, new clips and new frames around the same
 * values, so a thread still reading the old profile is not disturbed.
 */
public final class JsonClipFrames
{
    public static JsonObject without(JsonObject profile, String... frameKeys)
    {
        if (!profile.has("clips") || !profile.get("clips").isJsonObject()) return profile;
        Set<String> dropped = Set.of(frameKeys);
        JsonObject clips = new JsonObject();
        for (Map.Entry<String, JsonElement> clip : profile.getAsJsonObject("clips").entrySet())
            clips.add(clip.getKey(), clip.getValue().isJsonObject() ? clip(clip.getValue().getAsJsonObject(), dropped) : clip.getValue());
        JsonObject result = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : profile.entrySet())
            result.add(entry.getKey(), entry.getKey().equals("clips") ? clips : entry.getValue());
        return result;
    }

    private static JsonObject clip(JsonObject clip, Set<String> dropped)
    {
        if (!clip.has("frames") || !clip.get("frames").isJsonArray()) return clip;
        JsonArray source = clip.getAsJsonArray("frames");
        JsonArray frames = new JsonArray(source.size());
        for (JsonElement frame : source)
        {
            if (!frame.isJsonObject())
            {
                frames.add(frame);
                continue;
            }
            JsonObject kept = new JsonObject();
            for (Map.Entry<String, JsonElement> entry : frame.getAsJsonObject().entrySet())
                if (!dropped.contains(entry.getKey())) kept.add(entry.getKey(), entry.getValue());
            frames.add(kept);
        }
        JsonObject result = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : clip.entrySet())
            result.add(entry.getKey(), entry.getKey().equals("frames") ? frames : entry.getValue());
        return result;
    }

    private JsonClipFrames()
    {
    }
}
