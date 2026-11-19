package com.projectseele.world;

import com.google.gson.JsonParser;
import net.minecraft.network.chat.Component;

import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Localizable operational receipts in the existing UTF-8 packet fields and saved job notes. */
public final class OperationText
{
    private static final String PREFIX = "ops.projectseele.";
    private static final String COMPONENT = "\u001e";

    private OperationText() {}

    public static Component unit(int slot)
    {
        return slot < 3 ? Component.translatable("entity.projectseele.eva_unit0" + slot)
                : Component.literal("EVA-UN-0" + (slot - 3));
    }

    public static String format(String key, Object... arguments)
    {
        return encode(Component.translatable(key, arguments));
    }

    public static String encode(Component component)
    {
        return COMPONENT + Component.Serializer.toJson(component);
    }

    public static Component read(String value)
    {
        if (value == null) return Component.empty();
        if (value.startsWith(PREFIX)) return Component.translatable(value);
        if (value.startsWith(COMPONENT))
        {
            try
            {
                Component decoded = Component.Serializer.fromJson(value.substring(COMPONENT.length()));
                if (decoded != null) return decoded;
            }
            catch (com.google.gson.JsonParseException ignored) {}
        }
        String oldKey = SavedNotes.KEYS.get(value);
        return oldKey == null ? Component.literal(value) : Component.translatable(oldKey);
    }

    /** R63 saves may contain the shipped Chinese note itself. Never reinterpret typed player chat. */
    private static final class SavedNotes
    {
        static final Map<String, String> KEYS = load();

        private static Map<String, String> load()
        {
            var keys = new HashMap<String, String>();
            try (var stream = OperationText.class.getResourceAsStream("/assets/projectseele/lang/zh_cn.json"))
            {
                if (stream == null) return Map.of();
                var json = JsonParser.parseReader(new InputStreamReader(stream, StandardCharsets.UTF_8)).getAsJsonObject();
                for (var entry : json.entrySet())
                    if (entry.getKey().startsWith(PREFIX)) keys.putIfAbsent(entry.getValue().getAsString(), entry.getKey());
            }
            catch (java.io.IOException error) { throw new java.io.UncheckedIOException(error); }
            return Map.copyOf(keys);
        }
    }
}
