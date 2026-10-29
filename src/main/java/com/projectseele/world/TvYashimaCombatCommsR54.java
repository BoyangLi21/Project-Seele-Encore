package com.projectseele.world;

import com.projectseele.entity.RamielEntity;
import com.projectseele.event.TvEncounterDirectorR45;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.Holder;
import net.minecraft.network.protocol.game.ClientboundSoundPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;

import java.util.LinkedHashSet;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Reports real Ramiel attack events. This class never schedules or advances an attack. */
public final class TvYashimaCombatCommsR54
{
    private static final Map<RamielEntity, Pulse> PULSES = new WeakHashMap<>();

    static final class Pulse
    {
        private int remaining;
        private boolean charging, fired, ended;

        boolean charge(int ticks)
        {
            if (charging || ticks <= 0) return false;
            remaining = ticks;
            charging = true;
            fired = ended = false;
            return true;
        }

        int countdown(int ticks)
        {
            if (!charging || ticks <= 0 || ticks >= remaining) return 0;
            int previous = remaining;
            remaining = ticks;
            // Crossing, rather than equality, also handles a delayed update.
            if (previous > 20 && ticks <= 20) return 1;
            if (previous > 60 && ticks <= 60) return 3;
            return 0;
        }

        boolean fire()
        {
            if (fired) return false;
            charging = false;
            fired = true;
            ended = false;
            return true;
        }

        boolean end()
        {
            if (!fired || ended) return false;
            ended = true;
            return true;
        }

        boolean cancel()
        {
            if (!charging || fired) return false;
            charging = false;
            return true;
        }
    }

    private static TvCampaignSavedData mission(RamielEntity boss)
    {
        if (!(boss.level() instanceof ServerLevel level)) return null;
        var data = TvCampaignSavedData.get(level);
        if (!boss.isAlive() || !data.active.equals("ramiel") || !boss.getUUID().equals(data.angel)
                || data.targetDeathConfirmedR45 || data.phase.equals("cancel") || data.phase.equals("failure")
                || !TvEncounterDirectorR45.owned(boss, data))
        {
            PULSES.remove(boss);
            return null;
        }
        return data;
    }

    private static void report(RamielEntity boss, TvCampaignSavedData data, String speaker, String line, boolean alarm)
    {
        var level = (ServerLevel) boss.level();
        var recipients = new LinkedHashSet<UUID>();
        if (data.owner != null) recipients.add(data.owner);
        for (var sortie : data.sorties.values())
        {
            if (sortie.commander != null) recipients.add(sortie.commander);
            if (!sortie.npc && sortie.pilotR45 != null) recipients.add(sortie.pilotR45);
        }
        var cannon = alarm ? TvYashimaStationR52.operatorPositionR52(level) : null;
        for (var id : recipients)
        {
            var player = level.getServer().getPlayerList().getPlayer(id);
            if (player == null || player.level() != level) continue;
            NervStaffDialogue.say(player, speaker + " · 指挥通信", line);
            // Deliver the emplacement warning into each nearby participant's
            // headset; an EVA cockpit sits beyond a ground sound's audible radius.
            if (cannon != null && player.position().distanceToSqr(cannon) <= 128 * 128)
            {
                var ear = player.getEyePosition();
                player.connection.send(new ClientboundSoundPacket(
                        Holder.direct(ModSounds.FACILITY.get("facility_siren").get()), SoundSource.BLOCKS,
                        ear.x, ear.y, ear.z, .55F, 1, level.getRandom().nextLong()));
            }
        }
    }

    /** Call after the attack goal actually starts charging, using its chosen duration. */
    public static void onCharge(RamielEntity boss, int totalTicks)
    {
        var data = mission(boss);
        if (data == null || !PULSES.computeIfAbsent(boss, key -> new Pulse()).charge(totalTicks)) return;
        report(boss, data, "伊吹摩耶", "高能反应上升！预计" + seconds(totalTicks) + "秒后开火，各机准备！", true);
    }

    /** Pass the effective remaining charge, including any real-time minimum. */
    public static void onChargeTick(RamielEntity boss, int remainingTicks)
    {
        var pulse = PULSES.get(boss);
        if (pulse == null) return;
        int cue = pulse.countdown(remainingTicks);
        if (cue == 0) return;
        var data = mission(boss);
        if (data == null) return;
        report(boss, data, "葛城美里", cue == 3
                ? "还有约3秒！零号机保持掩护。初号机瞄准核心，等它开火！"
                : "距离开火约1秒！初号机，准备射击！", false);
    }

    /** Call only after the actual beam state has been committed. */
    public static void onFire(RamielEntity boss)
    {
        var data = mission(boss);
        if (data == null || boss.getBeamTicks() <= 0
                || !PULSES.computeIfAbsent(boss, key -> new Pulse()).fire()) return;
        report(boss, data, "葛城美里", "光束来了！核心暴露，初号机开火！", false);
    }

    /** Call when the actual beam changes from one remaining tick to zero. */
    public static void onBeamEnded(RamielEntity boss, int cooldownTicks)
    {
        var pulse = PULSES.get(boss);
        if (pulse == null || boss.getBeamTicks() != 0) return;
        var data = mission(boss);
        if (data == null || !pulse.end()) return;
        String recovery = cooldownTicks > 0 ? "目标还需约" + seconds(cooldownTicks) + "秒恢复。" : "";
        report(boss, data, "赤木律子", "核心闭合，射击窗口结束。" + recovery + "重新充能，等待下一次光束。", false);
    }

    /** A stopped goal without a committed shot must not announce firing or cooling. */
    public static void onChargeCancelled(RamielEntity boss)
    {
        var pulse = PULSES.get(boss);
        if (pulse == null) return;
        var data = mission(boss);
        if (data == null || !pulse.cancel()) return;
        report(boss, data, "伊吹摩耶", "目标中止蓄力。保持警戒，等待下一次高能反应。", false);
    }

    private static int seconds(int ticks) { return Math.max(1, (int) Math.ceil(ticks / 20.0)); }
    private TvYashimaCombatCommsR54() {}
}
