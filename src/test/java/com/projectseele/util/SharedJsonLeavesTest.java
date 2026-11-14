package com.projectseele.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/** The shared copy must read exactly like the parsed tree: same text, same order, same values bit for bit. */
public final class SharedJsonLeavesTest
{
    public static void main(String[] args)
    {
        // The spellings that must stay apart, the way the motion files write them, and enough repeats to share.
        String[] spellings = {"-0.0", "0.0", "0", "1.0", "1", "1e0", "0.00591977", "-0.19080900047742777", "0.9816271824561528",
                "16777217", "0.1", "0.10000000000000001", "3.4028235e38", "1.17549435E-38", "-7"};
        Random random = new Random(64);
        StringBuilder text = new StringBuilder("{\"schema\":2,\"rig_key\":1,\"flag\":true,\"none\":null,\"bones\":[\"root\",\"hip\",\"root\"],\"clips\":{");
        for (int clip = 0; clip < 40; clip++)
        {
            text.append(clip == 0 ? "" : ",").append("\"clip").append(clip % 7).append('_').append(clip).append("\":{\"name\":\"clip")
                    .append(clip % 3).append("\",\"rotation\":[");
            for (int frame = 0; frame < 30; frame++)
            {
                text.append(frame == 0 ? "" : ",").append('[');
                for (int k = 0; k < 4; k++)
                    text.append(k == 0 ? "" : ",").append(random.nextInt(3) == 0 ? Float.toString(random.nextFloat()) : spellings[random.nextInt(spellings.length)]);
                text.append(']');
            }
            text.append("],\"empty\":[],\"pair\":[-0.0,0.0]}");
        }
        text.append("}}");
        JsonObject parsed = JsonParser.parseString(text.toString()).getAsJsonObject();
        String before = parsed.toString();
        JsonObject shared = SharedJsonLeaves.share(parsed);
        if (!parsed.toString().equals(before)) throw new AssertionError("The parsed tree was changed");
        if (!shared.toString().equals(before)) throw new AssertionError("The shared copy does not serialise to the same text");

        List<JsonElement> originalLeaves = new ArrayList<>(), sharedLeaves = new ArrayList<>();
        List<JsonArray> sharedArrays = new ArrayList<>();
        leaves(parsed, originalLeaves, new ArrayList<>());
        leaves(shared, sharedLeaves, sharedArrays);
        if (originalLeaves.size() != sharedLeaves.size()) throw new AssertionError("Leaf count changed");
        Map<JsonElement, String> textOf = new IdentityHashMap<>();
        Map<String, JsonElement> instanceOf = new java.util.HashMap<>();
        int numbers = 0;
        for (int i = 0; i < sharedLeaves.size(); i++)
        {
            JsonElement was = originalLeaves.get(i), now = sharedLeaves.get(i);
            if (!was.isJsonPrimitive() || !was.getAsJsonPrimitive().isNumber()) continue;
            numbers++;
            String written = was.getAsString();
            if (!now.getAsString().equals(written)) throw new AssertionError("Number text changed: " + written);
            if (Float.floatToRawIntBits(now.getAsFloat()) != Float.floatToRawIntBits(was.getAsFloat())
                    || Double.doubleToRawLongBits(now.getAsDouble()) != Double.doubleToRawLongBits(was.getAsDouble()))
                throw new AssertionError("Number value changed: " + written);
            // One instance per spelling, and never one instance for two spellings.
            String earlier = textOf.putIfAbsent(now, written);
            if (earlier != null && !earlier.equals(written)) throw new AssertionError("Two spellings share an instance: " + earlier + " and " + written);
            JsonElement first = instanceOf.putIfAbsent(written, now);
            if (first != null && first != now) throw new AssertionError("A spelling has two instances: " + written);
        }
        if (instanceOf.size() >= numbers) throw new AssertionError("Nothing was shared");
        Map<JsonArray, Boolean> distinctArrays = new IdentityHashMap<>();
        for (JsonArray array : sharedArrays) if (distinctArrays.put(array, Boolean.TRUE) != null) throw new AssertionError("An array is shared");
        System.out.println("Shared JSON leaves read like the parsed tree: " + numbers + " numbers on " + instanceOf.size() + " instances, "
                + sharedArrays.size() + " arrays each their own");
    }

    private static void leaves(JsonElement element, List<JsonElement> leaves, List<JsonArray> arrays)
    {
        if (element.isJsonArray())
        {
            arrays.add(element.getAsJsonArray());
            for (JsonElement item : element.getAsJsonArray()) leaves(item, leaves, arrays);
        }
        else if (element.isJsonObject())
        {
            for (Map.Entry<String, JsonElement> entry : element.getAsJsonObject().entrySet()) leaves(entry.getValue(), leaves, arrays);
        }
        else leaves.add(element);
    }
}
