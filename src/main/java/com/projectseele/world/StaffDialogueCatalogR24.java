package com.projectseele.world;

import net.minecraft.network.chat.Component;
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
        return "dialogue.projectseele.fallback";
    }

    /** Data packs may supply either a translation key or their own literal prose. */
    public static Component component(String line)
    {
        if (line.startsWith("dialogue.projectseele."))
            return Component.translatable(line);
        return TvBriefingText.read(line);
    }

    public static Component speaker(String label)
    {
        int split = label.indexOf(" · ");
        String name = split < 0 ? label : label.substring(0, split);
        String key = switch (name)
        {
            case "碇源堂" -> "hud.projectseele.chat.name.gendo";
            case "加持良治" -> "hud.projectseele.chat.name.kaji";
            case "渚薰" -> "hud.projectseele.chat.name.kaworu";
            case "葛城美里" -> "hud.projectseele.chat.name.misato";
            case "赤木律子" -> "hud.projectseele.chat.name.ritsuko";
            case "伊吹摩耶" -> "hud.projectseele.chat.name.maya";
            case "冬月耕造" -> "hud.projectseele.chat.name.fuyutsuki";
            case "青叶茂" -> "hud.projectseele.chat.name.aoba";
            case "日向诚" -> "hud.projectseele.chat.name.hyuga";
            case "碇真嗣" -> "hud.projectseele.chat.name.shinji";
            case "绫波丽" -> "hud.projectseele.chat.name.rei";
            case "惣流·明日香·兰格雷" -> "hud.projectseele.chat.name.asuka";
            case "明日香" -> "hud.projectseele.chat.name.asuka";
            case "NERV 回收联络" -> "ops.projectseele.recovery.nerv_recovery_control";
            case "NERV 运输联络" -> "ops.projectseele.recovery.nerv_transport_control";
            case "地下回收联络" -> "ops.projectseele.recovery.underground_recovery_control";
            case "地下运输联络" -> "ops.projectseele.recovery.underground_transport_control";
            default -> null;
        };
        Component person = key == null ? Component.literal(name) : Component.translatable(key);
        if (split < 0) return person;
        String channel = label.substring(split + 3);
        String channelKey = switch (channel)
        {
            case "回收联络" -> "radio.projectseele.channel.recovery";
            case "作战通信" -> "radio.projectseele.channel.combat";
            case "指挥通信" -> "radio.projectseele.channel.command";
            case "驾驶员通信" -> "radio.projectseele.channel.pilot";
            case "通信" -> "radio.projectseele.channel.radio";
            case "机体监视" -> "radio.projectseele.channel.monitor";
            default -> null;
        };
        return Component.empty().append(person).append(" · ").append(channelKey == null
                ? Component.literal(channel) : Component.translatable(channelKey));
    }

    public static Component pilotName(int unit)
    {
        return Component.translatable(switch (unit)
        {
            case 0 -> "hud.projectseele.chat.name.rei";
            case 2 -> "hud.projectseele.chat.name.asuka";
            default -> "hud.projectseele.chat.name.shinji";
        });
    }

    /** Only composed pilot replies use this prefix on the existing UTF-8 reply field. */
    public static String pilotReply(int unit, String line)
    {
        return "pilot-reply:" + unit + ":" + line;
    }

    public static Component replyComponent(String reply)
    {
        String prefix = "pilot-reply:";
        if (reply.startsWith(prefix) && reply.length() > prefix.length() + 2)
        {
            int unit = reply.charAt(prefix.length()) - '0';
            if (unit >= 0 && unit <= 2 && reply.charAt(prefix.length() + 1) == ':')
                return Component.translatable("dialogue.projectseele.pilot_reply", pilotName(unit),
                        component(reply.substring(prefix.length() + 2)));
        }
        return component(reply);
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
