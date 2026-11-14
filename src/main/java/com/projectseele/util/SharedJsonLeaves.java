package com.projectseele.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;

import java.util.HashMap;
import java.util.Map;

/**
 * For a parsed JSON tree that stays in memory for the whole session. Gson gives every number its own
 * object, its own lazily parsed wrapper and its own copy of the text, about 88 bytes each, and every
 * array a ten-slot list. The gameplay motion files hold 6.6 million numbers of which 1.0 million are
 * distinct (a third of them are "-0.0"), so the five profiles cost about 700 MB as parsed.
 *
 * The copy returned here shares one primitive per distinct number text and per distinct string, and
 * sizes every array exactly. Primitives are immutable and are still the ones Gson parsed, so every
 * getAsFloat and getAsDouble gives the value it gave before. Arrays and objects are not shared.
 */
public final class SharedJsonLeaves
{
    private final Map<String, JsonPrimitive> numbers = new HashMap<>();
    private final Map<String, JsonPrimitive> strings = new HashMap<>();
    private final Map<String, String> names = new HashMap<>();

    /** A tree equal to the given one; the given one is not changed and can be dropped. */
    public static JsonObject share(JsonObject root)
    {
        return new SharedJsonLeaves().object(root);
    }

    private JsonElement element(JsonElement element)
    {
        if (element.isJsonPrimitive())
        {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            // The key is the text exactly as written: "0.0" and "-0.0" and "0" stay three different numbers.
            if (primitive.isNumber()) return this.numbers.computeIfAbsent(primitive.getAsString(), text -> primitive);
            if (primitive.isString()) return this.strings.computeIfAbsent(primitive.getAsString(), text -> primitive);
            return primitive;
        }
        if (element.isJsonArray())
        {
            JsonArray array = element.getAsJsonArray();
            JsonArray exact = new JsonArray(array.size());
            for (JsonElement item : array) exact.add(element(item));
            return exact;
        }
        if (element.isJsonObject()) return object(element.getAsJsonObject());
        return element;
    }

    private JsonObject object(JsonObject object)
    {
        JsonObject copy = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : object.entrySet())
            copy.add(this.names.computeIfAbsent(entry.getKey(), name -> name), element(entry.getValue()));
        return copy;
    }

    private SharedJsonLeaves()
    {
    }
}
