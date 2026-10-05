package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.living.LivingDamageEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;

/** Brief written command reports from committed combat and actual server state. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CombatCommandBriefR47
{
    private static final Map<EvaUnit01Entity, Pulse> PULSES = new WeakHashMap<>();
    private static final Map<LivingEntity, Boolean> DEATHS = new WeakHashMap<>();
    private static final class Pulse
    {
        long attackAfter, hurtAfter, lineAfter;
        boolean observed, berserk, critical;
    }

    private static void say(ServerLevel level, EvaUnit01Entity eva, String speaker, String line)
    {
        Set<UUID> recipients = new HashSet<>();
        if (eva != null)
        {
            if (eva.getPilotEntity() instanceof ServerPlayer pilot) recipients.add(pilot.getUUID());
            var tag = eva.getPersistentData();
            if (tag.hasUUID("R32SortieCommander")) recipients.add(tag.getUUID("R32SortieCommander"));
        }
        var campaign = TvCampaignSavedData.get(level);
        boolean assigned = eva == null || campaign.sorties.values().stream()
                .anyMatch(sortie -> eva.getUUID().equals(sortie.eva));
        if (assigned && !campaign.active.isEmpty())
        {
            if (campaign.owner != null) recipients.add(campaign.owner);
            for (var sortie : campaign.sorties.values()) recipients.add(sortie.commander);
        }
        for (var id : recipients)
        {
            var player = level.getServer().getPlayerList().getPlayer(id);
            if (player != null && player.level() == level) NervStaffDialogue.say(player, speaker, line);
        }
    }

    /** Root calls this only after accepting the actual attack, including a shot that misses. */
    public static void attackCommitted(EvaUnit01Entity eva, String kind)
    {
        if (!(eva.level() instanceof ServerLevel level) || !eva.isAlive()) return;
        var pulse = PULSES.computeIfAbsent(eva, key -> new Pulse());
        long now = level.getGameTime();
        if (now < pulse.attackAfter || now < pulse.lineAfter) return;
        String action = switch (kind)
        {
            case "rifle", "cannon" -> "射击确认。注意目标的反击。";
            case "knife", "sword" -> "近战攻击确认。保持退路。";
            case "smash", "punch" -> "攻击确认。别停在目标正面。";
            default -> null;
        };
        if (action == null) return;
        pulse.attackAfter = now + 160; pulse.lineAfter = now + 50;
        say(level, eva, "葛城美里 · 作战通信", TvSortiesR32.name(TvSortiesR32.slot(eva)) + "，" + action);
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void damage(LivingDamageEvent event)
    {
        if (event.isCanceled() || event.getAmount() <= 0 || !(event.getEntity().level() instanceof ServerLevel level)) return;
        if (event.getEntity() instanceof EvaUnit01Entity eva)
        {
            var pulse = PULSES.computeIfAbsent(eva, key -> new Pulse());
            long now = level.getGameTime();
            boolean critical = eva.getHealth() - event.getAmount() <= eva.getMaxHealth() * .25F;
            if (now < pulse.hurtAfter || (!critical && now < pulse.lineAfter)) return;
            pulse.hurtAfter = now + 140; pulse.lineAfter = now + 50; pulse.critical = critical;
            say(level, eva, "赤木律子 · 机体监视", TvSortiesR32.name(TvSortiesR32.slot(eva))
                    + (critical ? "损伤较重。请确认驾驶员状态，建议回收检查。" : "受到冲击。驾驶员，请报告操纵反馈。"));
        }
        else if (event.getSource().getEntity() instanceof EvaUnit01Entity eva)
        {
            var pulse = PULSES.computeIfAbsent(eva, key -> new Pulse());
            long now = level.getGameTime();
            if (now < pulse.attackAfter || now < pulse.lineAfter) return;
            pulse.attackAfter = now + 160; pulse.lineAfter = now + 50;
            say(level, eva, "葛城美里 · 作战通信", TvSortiesR32.name(TvSortiesR32.slot(eva)) + "有效命中。继续观察目标。" );
        }
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void death(LivingDeathEvent event)
    {
        if (event.isCanceled() || !(event.getEntity().level() instanceof ServerLevel level)) return;
        var target = event.getEntity();
        var campaign = TvCampaignSavedData.get(level);
        if (campaign.angel == null || !campaign.angel.equals(target.getUUID()) || DEATHS.put(target, true) != null) return;
        say(level, null, "葛城美里 · 作战通信", "目标生命反应消失。各机保持警戒，按原流程回收。");
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 5 != 0) return;
        for (var level : event.getServer().getAllLevels())
            for (var entity : level.getAllEntities())
            {
                if (!(entity instanceof EvaUnit01Entity eva) || !eva.isAlive()) continue;
                var pulse = PULSES.computeIfAbsent(eva, key -> new Pulse());
                boolean berserk = eva.isBerserk();
                if ((!pulse.observed && berserk) || (pulse.observed && pulse.berserk != berserk))
                {
                    say(level, eva, "赤木律子 · 机体监视", TvSortiesR32.name(TvSortiesR32.slot(eva))
                            + (berserk ? "出现自律反应，制御状态异常。先确认驾驶员安全。" : "自律反应减弱。继续确认驾驶员和操纵系统。"));
                    pulse.lineAfter = level.getGameTime() + 60;
                }
                pulse.berserk = berserk; pulse.observed = true;
            }
    }

    private CombatCommandBriefR47() {}
}
