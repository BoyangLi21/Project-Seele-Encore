package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.*;
import net.minecraft.util.profiling.ProfilerFiller;
import net.minecraftforge.event.AddReloadListenerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Datapacks contain dialogue prose only; available actions remain server-owned. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StaffDialogueCatalogR24
{
    private static volatile Map<String, Map<String, List<String>>> profiles = Map.of();

    @SubscribeEvent
    public static void reload(AddReloadListenerEvent event)
    {
        event.addListener(new SimpleJsonResourceReloadListener(new Gson(), "nerv_dialogue")
        {
            @Override
            protected void apply(Map<ResourceLocation, JsonElement> resources, ResourceManager manager, ProfilerFiller profiler)
            {
                Map<String, Map<String, List<String>>> result = new LinkedHashMap<>();
                resources.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry ->
                {
                    JsonObject root = entry.getValue().getAsJsonObject();
                    for (var person : root.getAsJsonObject("profiles").entrySet())
                    {
                        if (!person.getKey().matches("[a-z0-9_]{1,40}")) throw new IllegalArgumentException("Invalid dialogue profile");
                        Map<String, List<String>> topics = new LinkedHashMap<>();
                        for (var topic : person.getValue().getAsJsonObject().entrySet())
                        {
                            List<String> lines = new ArrayList<>();
                            for (var line : topic.getValue().getAsJsonArray())
                            {
                                String value = line.getAsString();
                                if (value.length() > 240 || value.contains("\u00a7")) throw new IllegalArgumentException("Invalid dialogue line");
                                lines.add(value);
                            }
                            if (lines.isEmpty() || lines.size() > 16) throw new IllegalArgumentException("Invalid dialogue variants");
                            topics.put(topic.getKey(), List.copyOf(lines));
                        }
                        result.put(person.getKey(), Map.copyOf(topics));
                    }
                });
                profiles = Map.copyOf(result);
                ProjectSeele.LOGGER.info("R24 staff dialogue profiles loaded: {}", profiles.size());
            }
        });
    }

    public static String line(String skin, String role, String topic, int variation)
    {
        for (String key : List.of(skin, role, "technician"))
        {
            List<String> lines = profiles.getOrDefault(key, Map.of()).get(topic);
            if (lines != null && !lines.isEmpty()) return lines.get(Math.floorMod(variation, lines.size()));
        }
        return "请讲。";
    }

    public static String next(net.minecraft.server.level.ServerPlayer player, String skin, String role, String topic)
    {
        String key = "SeeleDialogueR28_" + skin + "_" + topic;
        int index = player.getPersistentData().getInt(key);
        player.getPersistentData().putInt(key, index == Integer.MAX_VALUE ? 0 : index + 1);
        return line(skin, role, topic, index);
    }

    public static String profile(com.projectseele.entity.NervStaffEntity npc)
    {
        // Named operators share a clothing skin, but retain their original jobs and identities.
        if (java.util.Set.of("hyuga", "aoba").contains(npc.memberId())) return npc.memberId();
        if (npc.memberId().startsWith("r47/restroom/security_")) return "restroom_security";
        if (npc.memberId().startsWith("r47/yashima/power_monitor_")) return "yashima_power";
        if (npc.staffRole().equals("scientist") && !npc.skin().equals("ritsuko")) return "scientist";
        return npc.skin();
    }

    private StaffDialogueCatalogR24() {}
}
