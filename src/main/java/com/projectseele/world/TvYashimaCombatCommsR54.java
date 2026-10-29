package com.projectseele.world;

import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.event.TvEncounterDirectorR45;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.Holder;
import net.minecraft.network.protocol.game.ClientboundSoundPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.Entity;

import java.util.LinkedHashSet;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Reports real attack and cannon results without scheduling or advancing attacks. */
public final class TvYashimaCombatCommsR54
{
    private static final Map<RamielEntity, Pulse> PULSES = new WeakHashMap<>();

    enum ShotResult
    {
        UNCONFIRMED("弹道前方地形尚未加载，未确认命中。保持瞄准，重新充能。"),
        MISS("炮击未命中拉米尔。修正瞄准，等待下一次核心暴露。"),
        CORE_CLOSED("命中外壳，但核心尚未开放，未造成核心损伤。等它开火后再射击。"),
        AT_BLOCKED("命中外壳，核心尚未开放，A.T. 力场仍在，炮击未造成核心损伤。"),
        CORE_MISSED("击中外壳，弹道偏离了暴露的核心。调整瞄准，准备下一发。"),
        NO_DAMAGE("弹道触及核心，但未确认有效损伤。重新充能，继续观察核心。"),
        CORE_HIT("确认核心命中，目标受到有效损伤！重新充能，保持瞄准。"),
        CORE_DESTROYED("确认核心命中，目标生命反应归零。保持警戒，等待战果确认。");

        final String line;
        ShotResult(String line){this.line=line;}
    }

    static ShotResult shotResult(boolean hitBoss,boolean exposed,boolean atField,boolean coreShot,
                                 boolean accepted,float healthBefore,float healthAfter)
    {
        if(!hitBoss)return ShotResult.MISS;
        if(!exposed)return atField?ShotResult.AT_BLOCKED:ShotResult.CORE_CLOSED;
        if(!coreShot)return ShotResult.CORE_MISSED;
        if(!accepted||!Float.isFinite(healthBefore)||!Float.isFinite(healthAfter)||healthBefore<=healthAfter)
            return ShotResult.NO_DAMAGE;
        return healthAfter<=0?ShotResult.CORE_DESTROYED:ShotResult.CORE_HIT;
    }

    /** Called once after the actual cannon ray and direct damage have resolved. */
    public static void onCannonShot(EvaUnit01Entity shooter,Entity hit,boolean exposed,boolean atField,
                                    boolean coreShot,boolean accepted,float healthBefore,float healthAfter,boolean traceComplete)
    {
        if(!(shooter.level() instanceof ServerLevel level))return;
        var data=TvCampaignSavedData.get(level);
        var state=TvYashimaSavedDataR50.get(level);
        if(!data.active.equals("ramiel")||data.angel==null||!state.matches(data)
                ||TvSortiesR32.assignedUnit(level,data,1)!=shooter
                ||!(level.getEntity(data.angel) instanceof RamielEntity boss)
                ||!TvEncounterDirectorR45.owned(boss,data))return;
        // The lethal shot can already have changed the mission to victory.
        // Keep its real result even though the boss is no longer alive.
        var result=!traceComplete?ShotResult.UNCONFIRMED:shotResult(hit==boss,exposed,atField,coreShot,accepted,healthBefore,healthAfter);
        report(boss,data,result==ShotResult.MISS||result==ShotResult.CORE_MISSED?"葛城美里":"赤木律子",result.line,false);
    }

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

    public static int chargeRemainingR54(RamielEntity boss)
    {var pulse=PULSES.get(boss);return pulse!=null&&pulse.charging?pulse.remaining:0;}

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
        report(boss, data, "葛城美里", "光束来了！核心暴露约"+seconds(boss.getBeamDurationR54())+"秒，初号机开火！", false);
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
