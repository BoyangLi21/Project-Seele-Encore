package com.projectseele.world;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import java.util.UUID;
import net.minecraft.server.level.ServerLevel;

/** Opt-in control evidence; no dialogue, world state, identity or task mutation. */
public final class StaffOperationsTraceR45
{
    public static void event(ServerLevel level, String stage, UUID operator,
                             UUID officer, int unit, String operation, String reason)
    {
        if (!Boolean.getBoolean("projectseele.r45StaffControlTrace")) return;
        JsonObject row = new JsonObject();
        row.addProperty("server_tick", level.getServer().getTickCount());
        row.addProperty("game_time", level.getGameTime());
        row.addProperty("dimension", level.dimension().location().toString());
        row.addProperty("stage", stage);
        row.addProperty("operator_uuid", operator == null ? "" : operator.toString());
        row.addProperty("officer_uuid", officer == null ? "" : officer.toString());
        row.addProperty("unit", unit);
        row.addProperty("operation", operation);
        row.addProperty("reason", reason);
        var entry = unit < 0 || unit > 2 ? null : EvaFleetSavedData.get(level.getServer()).entry(unit).orElse(null);
        if (entry != null)
        {
            row.addProperty("fleet_phase", entry.phase().name());
        }
        var actor = officer == null ? null : level.getEntity(officer);
        if (actor instanceof com.projectseele.entity.NervStaffEntity npc)
        {
            row.addProperty("staff_id", npc.memberId());
            row.addProperty("role", npc.staffRole());
            row.addProperty("busy", npc.busy());
            row.addProperty("press_count", npc.pressCount());
            row.addProperty("position", npc.position().toString());
        }
        ProjectSeele.LOGGER.info("STAFF R45 CONTROL {}", row);
    }

    private StaffOperationsTraceR45() {}
}
