package com.projectseele.client.cockpit;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Whatever the positron cannon's sight says through a language key is in both language files, and each of its sounds
 * has its entry in the sound table, its subtitle in both languages and its file. Read from the sources themselves:
 * a key mistyped in the sight would otherwise show as the key on the pilot's screen.
 */
public final class CannonSightTextsR64Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    public static void main(String[] args) throws Exception
    {
        Path assets = Path.of("src/main/resources/assets/projectseele");
        String sight = Files.readString(Path.of("src/main/java/com/projectseele/client/cockpit/PlugCannonSightR64.java"), StandardCharsets.UTF_8);
        var keys = new TreeSet<String>();
        Matcher whole = Pattern.compile("\"(hud\\.projectseele\\.sight\\.[a-z_]+)\"").matcher(sight);
        while (whole.find()) keys.add(whole.group(1));
        // The figures' rows are named in a table and their keys put together from the names.
        that(sight.contains("\"hud.projectseele.sight.\" + row[0]"), "the figures' rows are no longer keyed by their names: this check must follow");
        Matcher row = Pattern.compile("\\{\"([a-z]+)\", ").matcher(sight);
        while (row.find()) keys.add("hud.projectseele.sight." + row.group(1));
        that(keys.size() >= 25, "the sight's keys were not found in its source: " + keys.size());
        String[] sounds = {"cannon_visor", "cannon_sight_tick", "cannon_sight_lock", "cannon_vent", "cannon_fuse"};
        for (String language : new String[]{"zh_cn", "en_us"})
        {
            String file = Files.readString(assets.resolve("lang/" + language + ".json"), StandardCharsets.UTF_8);
            for (String key : keys) that(file.contains("\"" + key + "\":"), language + ".json has no " + key);
            for (String sound : sounds) that(file.contains("\"subtitles.projectseele." + sound + "\":"), language + ".json has no subtitle for " + sound);
            // And no key of the sight's in the file that the sight does not say.
            Matcher has = Pattern.compile("\"(hud\\.projectseele\\.sight\\.[a-z_]+)\":").matcher(file);
            while (has.find()) that(keys.contains(has.group(1)), language + ".json has " + has.group(1) + ", which the sight does not say");
        }
        String table = Files.readString(assets.resolve("sounds.json"), StandardCharsets.UTF_8);
        String registry = Files.readString(Path.of("src/main/java/com/projectseele/registry/ModSounds.java"), StandardCharsets.UTF_8);
        for (String sound : sounds)
        {
            that(table.contains("\"" + sound + "\": {") && table.contains("\"projectseele:" + sound + "\""), "sounds.json has no " + sound);
            that(Files.size(assets.resolve("sounds/" + sound + ".ogg")) > 1000, sound + ".ogg is missing or empty");
            that(registry.contains("register(\"" + sound + "\")"), "ModSounds does not register " + sound);
            that(sight.contains("ModSounds." + sound.toUpperCase(java.util.Locale.ROOT) + ".get()"), "the sight never plays " + sound);
        }
        System.out.println("CannonSightTextsR64Test: " + checked + " checks passed.");
    }
}
