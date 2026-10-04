package com.projectseele.world;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import java.util.Map;
import java.util.WeakHashMap;

/** NPC speech observes the real occupant and machinery; it never drives either. */
public final class PilotRadioR28
{
    private static final Map<TrainingPilotEntity, Voice> VOICES = new WeakHashMap<>();
    private static final Map<ServerPlayer, Long> LAST_HEARD = new WeakHashMap<>();
    private static final class Voice
    {
        String topic = "", pending = "";
        long next, expires, lastSpoken = -1000;
        float health = -1;
        boolean low;
        int variation;
    }

    public static String profile(int variant)
    { return switch (variant) { case 0 -> "rei"; case 2 -> "asuka"; default -> "shinji"; }; }

    public static EvaUnit01Entity occupiedUnit(TrainingPilotEntity pilot)
    {
        var vehicle = pilot.getVehicle();
        var eva = vehicle instanceof EntryPlugCarrierEntity plug ? plug.getLinkedEva()
                : vehicle instanceof EvaUnit01Entity unit ? unit : null;
        return eva != null && eva.getPilotEntity() == pilot ? eva : null;
    }

    public static String topic(TrainingPilotEntity pilot)
    {
        var eva = occupiedUnit(pilot);
        if (eva == null && pilot.getVehicle() instanceof EntryPlugCarrierEntity && pilot.level() instanceof ServerLevel level
                && java.util.Set.of("DESCENDING","TO_HANGAR","FILLING").contains(EvaLogisticsDirector.status(level,pilot.getAssignedVariant()).phase())) return "return";
        if(eva==null&&pilot.getPersistentData().getString("SeelePilotRouteR30").equals("hold"))return "route_blocked";
        if (eva == null) return switch (pilot.getTrainingStage())
        {
            case TrainingPilotEntity.STAGE_WALKING -> pilot.getPersistentData().getString("SeelePilotRouteR30").equals("return") ? "disembark" : "boarding";
            case TrainingPilotEntity.STAGE_IN_PLUG -> "plug";
            default -> "standby";
        };
        if (eva.isFirstBattleActive()) return "silent";
        if (EvaAirTransportR31.active(eva)) return "air_transport";
        if (PilotReturnR39.controls(eva) && EvaLogisticsDirector.status((ServerLevel) pilot.level(),pilot.getAssignedVariant()).phase().equals("DEPLOYED")) return "returning";
        var phase = EvaLogisticsDirector.status((ServerLevel) pilot.level(), pilot.getAssignedVariant()).phase();
        return phaseTopic(phase, eva.isLaunchSequenceActive());
    }

    public static String phaseTopic(String phase, boolean launching)
    {
        return switch (phase)
        {
            case "PLUG_INSERTING", "PLUG_LOCKING", "BRIDGE_RETRACTING" -> "link";
            case "DRAINING", "TO_SILO" -> "transfer";
            case "SILO_READY" -> "ready";
            case "DEPLOYED" -> launching ? "launch" : "field";
            case "DESCENDING", "TO_HANGAR", "FILLING" -> "return";
            case "PLUG_FAULT", "PLUG_ABORT_RETURNING", "PLUG_ABORT_DOCKED" -> "fault";
            default -> "plug";
        };
    }

    public static String response(ServerPlayer player, TrainingPilotEntity pilot, boolean rotate)
    {
        String topic = topic(pilot);
        if (topic.equals("silent")) return "……";
        return rotate ? StaffDialogueCatalogR24.next(player, profile(pilot.getAssignedVariant()), "technician", topic)
                : StaffDialogueCatalogR24.line(profile(pilot.getAssignedVariant()), "technician", topic, player.tickCount / 600);
    }

    public static void tick(TrainingPilotEntity pilot)
    {
        if (!(pilot.level() instanceof ServerLevel level) || pilot.tickCount % 20 != 0) return;
        long now = level.getGameTime();
        var voice = VOICES.computeIfAbsent(pilot, key -> new Voice());
        String topic = topic(pilot);
        var eva = occupiedUnit(pilot);
        boolean low = topic.equals("field") && eva != null && !eva.isUmbilicalConnected() && eva.getPowerTicks() < 1200;
        boolean hit = eva != null && voice.health >= 0 && eva.getHealth() < voice.health - .1F;
        voice.health = eva == null ? -1 : eva.getHealth();
        // Never replay an old phase report after a cooldown or over the directed scene.
        if (topic.equals("silent")) { voice.pending = ""; voice.topic = topic; return; }
        if (!topic.equals(voice.topic))
        {
            boolean initialIdle = voice.topic.isEmpty() && topic.equals("standby");
            voice.topic = topic;
            voice.pending = initialIdle ? "" : topic;
            voice.expires = now + 160;
            voice.next = Math.min(voice.next, voice.lastSpoken + 120);
        }
        if (hit || low && !voice.low)
        { voice.pending = hit ? "hit" : "low_power"; voice.expires = now + 160; voice.next = Math.min(voice.next, voice.lastSpoken + 120); }
        voice.low = low;
        if (now < voice.next) return;
        if (now > voice.expires) voice.pending = "";
        if (voice.pending.isEmpty() && eva != null && topic.equals("field")) voice.pending = "field";
        if (voice.pending.isEmpty()) return;
        // Early TV missions have no Rei/Asuka co-pilot radio. Their physical
        // standby NPCs remain available for free-play interactions.
        var campaign = TvCampaignSavedData.get(level);
        if (FirstBattleSavedData.get(level).active != null) { voice.pending = ""; return; }
        if (!campaign.active.isEmpty() && campaign.chapter < 2 && pilot.getAssignedVariant() != 1)
        { voice.pending = ""; return; }
        String line = StaffDialogueCatalogR24.line(profile(pilot.getAssignedVariant()), "technician", voice.pending, voice.variation++);
        boolean heard = false;
        for (var player : level.players())
        {
            if (now - LAST_HEARD.getOrDefault(player, -1000L) < 180) continue;
            if (player.distanceToSqr(pilot) > 96 * 96 && !StaffConversationR24.radioAllowed(player)) continue;
            NervStaffDialogue.say(player, TrainingPilotEntity.pilotName(pilot.getAssignedVariant()) + " · 通信", line);
            LAST_HEARD.put(player, now); heard = true;
        }
        if (heard)
        {
            if (System.getProperty("projectseele.regionalBuild", "").startsWith("r28-"))
                com.projectseele.ProjectSeele.LOGGER.info("R28 PILOT RADIO variant={} topic={}", pilot.getAssignedVariant(), voice.pending);
            voice.pending = "";
            voice.lastSpoken = now;
            voice.next = now + (topic.equals("field") ? 1400 + 200 * pilot.getAssignedVariant() : 120);
        }
    }
    private PilotRadioR28() {}
}
