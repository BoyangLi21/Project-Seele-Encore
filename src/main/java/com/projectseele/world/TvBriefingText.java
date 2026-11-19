package com.projectseele.world;

import com.google.gson.Gson;
import com.google.gson.JsonParseException;
import net.minecraft.network.chat.Component;

/** Compact campaign facts for the existing staff reply field. Clients choose the language. */
public record TvBriefingText(String chapter, String activity, boolean central, int[] crew,
                             String coordinates, String blocker, String notice)
{
    private static final Gson JSON = new Gson();
    private static final String PREFIX = "\u001dTV:";
    private static final String KEY = "ops.projectseele.briefing.";

    public String encode()
    {
        return PREFIX + JSON.toJson(this);
    }

    public static Component read(String text)
    {
        if (text.startsWith(PREFIX))
        {
            try
            {
                var briefing = JSON.fromJson(text.substring(PREFIX.length()), TvBriefingText.class);
                if (briefing != null && briefing.chapter != null && briefing.activity != null && briefing.crew != null
                        && briefing.coordinates != null && briefing.blocker != null && briefing.notice != null
                        && TvCampaignCatalog.find(briefing.chapter).isPresent())
                    return briefing.display();
            }
            catch (JsonParseException ignored) {}
        }
        return OperationText.read(text);
    }

    public static Component unit(int slot)
    {
        return slot < 3 ? Component.translatable("entity.projectseele.eva_unit0" + slot)
                : Component.literal("EVA-UN-0" + (slot - 3));
    }

    private Component display()
    {
        String mission = "mission.projectseele." + chapter + ".";
        var title = Component.translatable(mission + "title");
        var target = TvCampaignCatalog.find(chapter).orElseThrow().target().isEmpty()
                ? Component.empty() : Component.translatable(mission + "target");
        var result = Component.translatable(KEY + "target", title, target)
                .append("\n").append(Component.translatable(KEY + "phase." + activity));
        if (crew.length > 0)
        {
            var roster = Component.empty();
            for (int i = 0; i < crew.length; i++)
            {
                if (i > 0) roster.append(Component.translatable(KEY + "separator"));
                boolean npc = crew[i] < 0;
                int slot = npc ? -crew[i] - 1 : crew[i];
                Component pilot = npc ? StaffDialogueCatalogR24.pilotName(slot) : Component.translatable(KEY + "human");
                roster.append(Component.translatable(KEY + "crew", unit(slot), pilot));
            }
            result.append("\n").append(Component.translatable(KEY + "formation", roster));
        }
        Component zone = Component.translatable(central ? "ops.projectseele.battlefield.city" : "ops.projectseele.battlefield.avenue");
        result.append("\n\n").append(Component.translatable(KEY + "objective", Component.translatable(mission + "objective", zone)));
        if (!coordinates.isEmpty()) result.append("\n").append(Component.translatable(KEY + "cannon", coordinates));
        if (!blocker.isBlank()) result.append("\n\n").append(Component.translatable(KEY + "pending", OperationText.read(blocker)));
        if (!notice.isBlank()) result.append("\n\n").append(Component.translatable(KEY + "dispatch", OperationText.read(notice)));
        if (activity.equals("idle")) result.append("\n\n").append(Component.translatable(KEY + "replay"));
        else if (activity.equals("alert") || activity.equals("approach") || activity.equals("combat"))
            result.append("\n\n").append(Component.translatable(KEY + "reinforce"));
        return result;
    }
}
