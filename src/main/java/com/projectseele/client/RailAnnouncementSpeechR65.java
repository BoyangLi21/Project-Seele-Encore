package com.projectseele.client;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Native MTR gives each announcement clause to mergeStations before it flattens the languages. */
public final class RailAnnouncementSpeechR65
{
    public record Speech(List<String> clips, String chinese, String english) {}

    private static final Map<String, String> STATIONS = table("stations");
    private static final Map<String, String> PHRASES = phrases();
    private static final List<String> TOKENS = PHRASES.keySet().stream()
            .sorted(Comparator.comparingInt(String::length).reversed()).toList();

    private static Map<String, String> table(String name)
    {
        Map<String, String> result = new HashMap<>();
        try (var in = Objects.requireNonNull(RailAnnouncementSpeechR65.class.getResourceAsStream(
                "/assets/projectseele_rail/" + name + ".tsv"));
             var reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8)))
        {
            reader.lines().forEach(line -> {
                String[] row = line.split("\\t", 2);
                result.put(row[0], row[1]);
            });
        }
        catch (IOException ex) { throw new IllegalStateException("Rail voice table " + name, ex); }
        return Map.copyOf(result);
    }

    private static Map<String, String> phrases()
    {
        var result = new HashMap<>(table("phrases"));
        STATIONS.forEach((name, clip) -> result.put("次は、" + name + "です。", clip));
        return Map.copyOf(result);
    }

    static String[] languages(String name)
    {
        String[] parts = name.split("\\|\\|", 2)[0].split("\\|", -1);
        if (parts.length != 3) return null;
        parts[0] = parts[0].replace("NERV", "ネルフ");
        return parts;
    }

    public static String interchangeNames(List<?> routes)
    {
        List<String> jp = new ArrayList<>(), zh = new ArrayList<>(), en = new ArrayList<>();
        for (Object route : routes)
        {
            String[] parts = languages((String)route);
            if (parts == null || !PHRASES.containsKey(parts[0])) return null;
            jp.add(parts[0]); zh.add(parts[1]); en.add(parts[2]);
        }
        return jp.isEmpty() ? null : String.join("、", jp) + "|" + String.join("、", zh) + "|" + String.join(" and ", en);
    }

    static String translated(String label, String[] args, boolean terminal)
    {
        if (args.length == 0) return null;
        String[] a = languages(args[0]);
        if (a == null) return null;
        String[] b = args.length > 1 ? languages(args[1]) : null;
        return switch (label)
        {
            case "gui.mtr.next_station_announcement_cjk" -> !STATIONS.containsKey(a[0]) ? null : terminal
                    ? "次は、終点、"+a[0]+"です。|下一站是终点站"+a[1]+"。|Next and final station: "+a[2]+"."
                    : "次は、"+a[0]+"です。|下一站是"+a[1]+"。|Next station: "+a[2]+".";
            case "gui.mtr.interchange_announcement_cjk" ->
                    a[0]+"にお乗り換えいただけます。|可换乘"+a[1]+"。|Interchange for "+a[2]+".";
            case "gui.mtr.connecting_station_announcement_cjk" ->
                    a[0]+"でお乗り換えです。|可在"+a[1]+"换乘。|Change at "+a[2]+".";
            case "gui.mtr.connecting_station_interchange_announcement_part_cjk" -> b == null ? null :
                    b[0]+"では、"+a[0]+"にお乗り換えいただけます。|在"+b[1]+"可换乘"+a[1]+"。|Change at "+b[2]+" for "+a[2]+".";
            case "gui.mtr.connecting_station_part_cjk" -> String.join("|", a);
            case "gui.mtr.next_route_train_announcement_cjk" -> b == null ? null :
                    "この列車は"+a[0]+"に直通し、"+b[0]+"行きです。|本次列车直通"+a[1]+"，开往"+b[1]+"。|This train continues on "+a[2]+" to "+b[2]+".";
            case "gui.mtr.next_station_cjk" -> "次は"+a[0]+"です。|下一站："+a[1]+"。|Next: "+a[2]+".";
            case "gui.mtr.this_station_cjk" -> "ただいま、"+a[0]+"です。|本站："+a[1]+"。|This station: "+a[2]+".";
            case "gui.mtr.last_train_station_cjk" -> "この列車は"+a[0]+"行きです。|本次列车开往"+a[1]+"。|This train is bound for "+a[2]+".";
            default -> null;
        };
    }

    public static Speech plan(List<String> clauses)
    {
        var clips = new ArrayList<String>();
        var chinese = new LinkedHashSet<String>();
        var english = new LinkedHashSet<String>();
        for (String clause : new LinkedHashSet<>(clauses))
        {
            String[] row = languages(clause);
            if (row == null) return null;
            String sentence = row[0];
            int at = 0;
            while (at < sentence.length())
            {
                if (sentence.charAt(at) == '、' || sentence.charAt(at) == ' ') { at++; continue; }
                String token = null;
                for (String key : TOKENS)
                    if (sentence.startsWith(key, at)) { token = key; break; }
                if (token == null) return null;
                clips.add(PHRASES.get(token));
                at += token.length();
            }
            chinese.add(row[1]); english.add(row[2]);
        }
        return clips.isEmpty() ? null : new Speech(List.copyOf(clips), String.join(" ", chinese), String.join(" ", english));
    }

    private RailAnnouncementSpeechR65() {}
}
