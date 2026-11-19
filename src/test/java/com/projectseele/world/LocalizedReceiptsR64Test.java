package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.contents.TranslatableContents;

import java.nio.file.Files;
import java.nio.file.Path;

public final class LocalizedReceiptsR64Test
{
    private static void check(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
    }

    private static String key(Component component)
    {
        return ((TranslatableContents) component.getContents()).getKey();
    }

    public static void main(String[] args) throws Exception
    {
        Path resources = Path.of("src/main/resources");
        Path lang = resources.resolve("assets/projectseele/lang");
        JsonObject english = JsonParser.parseString(Files.readString(lang.resolve("en_us.json"))).getAsJsonObject();
        JsonObject chinese = JsonParser.parseString(Files.readString(lang.resolve("zh_cn.json"))).getAsJsonObject();
        check(english.keySet().equals(chinese.keySet()), "English and Chinese key sets differ");

        var profiles = JsonParser.parseString(Files.readString(resources.resolve(
                "data/projectseele/nerv_dialogue/profiles.json"))).getAsJsonObject().getAsJsonObject("profiles");
        int variants = 0;
        for (var profile : profiles.entrySet())
            for (var topic : profile.getValue().getAsJsonObject().entrySet())
                for (var line : topic.getValue().getAsJsonArray())
                {
                    String id = line.getAsString();
                    check(english.has(id) && chinese.has(id), "Untranslated profile line " + id);
                    check(key(StaffDialogueCatalogR24.component(id)).equals(id), "Built-in line lost its key");
                    variants++;
                }
        check(StaffDialogueCatalogR24.component("A custom data pack line").getString().equals("A custom data pack line"),
                "Custom prose must survive intact");
        String aircraft = "ops.projectseele.airlift.aircraft_standby";
        check(key(OperationText.read("运输机待命")).equals(aircraft), "R63 saved note was not recognized");
        check(key(OperationText.read(aircraft)).equals(aircraft), "R64 saved key was not recognized");
        String literal = "Pilot 7 — 100%";
        check(OperationText.read(literal).getString().equals(literal), "Custom job note was modified");
        var result = (TranslatableContents) OperationText.read(OperationText.format(
                "ops.projectseele.un.unit_reply", literal, OperationText.read(aircraft))).getContents();
        check(result.getKey().equals("ops.projectseele.un.unit_reply"), "Receipt lost its key");
        check(result.getArgs()[0].equals(literal), "Receipt lost literal argument");
        check(key((Component) result.getArgs()[1]).equals(aircraft), "Receipt lost nested translation");
        var briefing = new TvBriefingText("ramiel", "combat", true, new int[]{-1, 1, -3, 3, 4}, "100 / 25 / -7",
                "运输机待命", "Pilot 7 — 100%");
        String encoded = briefing.encode();
        check(encoded.getBytes(java.nio.charset.StandardCharsets.UTF_8).length < 1400, "Briefing exceeds staff reply field");
        String displayed = Component.Serializer.toJson(TvBriefingText.read(encoded));
        check(displayed.contains("mission.projectseele.ramiel.objective") && displayed.contains("100 / 25 / -7")
                && displayed.contains(aircraft) && displayed.contains("Pilot 7 — 100%"), "Briefing lost its fields");
        String legacy = "屋岛作战 · GeoFront入口已贯穿；总部与终端尚未失守 · 装甲贯穿 3 层 · 炮位就绪，确认核心后炮击。";
        var oldBriefing = new TvBriefingText("ramiel", "combat", true, new int[0], "", "", legacy);
        String oldDisplay = Component.Serializer.toJson(TvBriefingText.read(oldBriefing.encode()));
        check(oldDisplay.contains("ops.projectseele.yashima.status") && oldDisplay.contains("ops.projectseele.yashima.entrance_breached")
                && oldDisplay.contains("ops.projectseele.yashima.gun_ready") && oldDisplay.contains("3"), "Legacy Yashima receipt lost status fields");
        System.out.println("Locale parity, " + variants + " dialogue variants and saved/packet receipt round trips passed");
    }
}
