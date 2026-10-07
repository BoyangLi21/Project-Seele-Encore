package com.projectseele.event;

import com.projectseele.entity.Angel;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.world.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.world.entity.Mob;
import net.minecraft.network.chat.Component;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** One real owned boss per TV mission, with bounded preload and recoverable failure. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class TvEncounterDirectorR45
{
    public static String tag(String chapter){return "seele_tv_r45_"+chapter;}
    public static String startBlocker(ServerLevel l,String chapter)
    {
        String reason=TvEncounterSitesR45.startBlocker(l,chapter);if(!reason.isEmpty())return reason;
        if(chapter.equals("gaghiel")&&!BuiltInRegistries.ENTITY_TYPE.containsKey(new ResourceLocation("projectseele:gaghiel")))
            return "海上迎击仍在准备中。";
        if(!Tokyo3RamielBattleSavedData.get(l).battles().isEmpty())return "已有行动占用战区，请先结束该行动。";
        if(chapter.equals("ramiel"))return TvYashimaDirectorR50.startBlocker(l);
        if(chapter.equals("gaghiel"))return TvMarineDirectorR50.startBlocker(l);
        return "";
    }

    /** Setup needs a ready defender; live combat retains its originals even when that defender is damaged. */
    public static String combatEquipmentBlockerR48(ServerLevel level, TvCampaignSavedData data)
    {
        if (!data.active.equals("ramiel") || !java.util.Set.of("approach","combat").contains(data.phase))
            return "屋岛作战尚未进入已授权交战阶段。";
        var site = TvEncounterSitesR45.site(level, data.active).orElse(null);
        if (data.owner == null || data.generationR43 <= 0 || data.targetDeathConfirmedR45
                || data.angel == null || !(level.getEntity(data.angel) instanceof RamielEntity boss) || !owned(boss, data))
            return "原作战目标或授权凭证尚未确认，行动暂停。";
        if (site == null || !site.geometryValidated() || !site.modelReady()
                || !site.id().equals(data.encounterSiteR45) || !site.fingerprint().equals(data.encounterLayoutR45))
            return "原作战阵地正在重新确认，行动暂停。";
        if (data.sorties.containsKey(2) && !site.supportReady())
            return "二号机支援阵地仍在整备中。";
        var defender = data.sorties.get(0); var shooterSortie = data.sorties.get(1);
        if (shooterSortie == null || shooterSortie.eva == null || shooterSortie.pilotR45 == null)
            return "等待初号机原射手完成编成、登栓与出击。";
        // The original defender's identity remains mandatory. Its current HP,
        // pilot boarding, brace and shield loan are battle/recovery outcomes.
        var originalDefender = EvaFleetSavedData.get(level.getServer()).entry(0).orElse(null);
        if (defender != null && defender.eva != null && (originalDefender == null || !defender.eva.equals(originalDefender.canonicalId())))
            return "零号机原出战身份不一致，行动暂停。";
        var shooter = TvSortiesR32.assignedUnit(level, data, 1);
        if (shooter == null || !shooter.isAlive() || shooter.isExperimentalUnit() || shooter.getUnitVariant() != 1
                || !TvSortiesR32.readyAssigned(level, shooterSortie)
                || !TvMissionEquipmentR45.operational(shooter))
            return "等待原初号机与原驾驶员恢复有效炮击状态。";
        var cannon = TvEncounterEquipmentControlR45.serverCargoAndCannonR45();
        if (!TvMissionEquipmentR45.cannonAuthorized(shooter) || !cannon.cannonReady(shooter))
            return "原初号机真实阳离子炮或任务借用凭证尚未确认。";
        if (!cannon.rangesReady(shooter, Math.max(site.separation(), site.attackRange())))
            return "原初号机远程火控仍在校准中。";
        if (shooter.position().distanceTo(site.hero()) > 12)
            return "初号机请保持原炮击阵地。";
        if (boss.effectiveBeamRangeR45() < boss.getBoundingBox().getCenter().distanceTo(shooter.getEyePosition()))
            return "原目标火控仍在校准中。";
        return "";
    }

    private static String phaseEquipmentBlockerR48(ServerLevel level, TvCampaignSavedData data)
    {
        return data.active.equals("ramiel") && data.phase.equals("combat")
                ? combatEquipmentBlockerR48(level, data) : TvEncounterRulesR45.equipmentBlocker(level, data);
    }
    public static void tick(ServerLevel l,TvCampaignSavedData d,ServerPlayer commander,ServerBossEvent bar)
    {
        if(d.active.equals("ramiel"))TvYashimaDirectorR50.tick(l,d,commander,bar);
        else if(d.active.equals("gaghiel"))TvMarineDirectorR50.tick(l,d,commander,bar);
    }
    public static boolean owned(Mob boss,TvCampaignSavedData d)
    {return boss.getTags().contains(tag(d.active))&&boss.getPersistentData().getLong("TvGenerationR45")==d.generationR43
            &&d.owner!=null&&boss.getPersistentData().hasUUID("TvOwnerR45")&&d.owner.equals(boss.getPersistentData().getUUID("TvOwnerR45"));}
    @SubscribeEvent public static void death(LivingDeathEvent e)
    {
        if(!(e.getEntity()instanceof Mob boss)||!(boss.level()instanceof ServerLevel l))return;
        var d=TvCampaignSavedData.get(l);
        if(d.active.equals("gaghiel"))return; // Marine controller owns its actual cannon/contact receipts.
        if(!TvEncounterRulesR45.handles(d.active)||!boss.getUUID().equals(d.angel)||!owned(boss,d))return;
        var owner=d.owner==null?null:l.getServer().getPlayerList().getPlayer(d.owner);
        var shooter=TvSortiesR32.assignedUnit(l,d,1);
        boolean valid=d.phase.equals("combat")&&owner!=null&&owner.level()==l
                &&shooter!=null&&shooter.getPilotEntity()!=null&&e.getSource().getEntity()==shooter.getPilotEntity()
                &&TvEncounterRulesR45.targetFrameReady(l,d,owner)
                &&TvEncounterRulesR45.obstruction(l,d).isEmpty()&&phaseEquipmentBlockerR48(l,d).isEmpty();
        // Evaluate live mission permission before the terminal fact revokes it.
        if(valid){d.targetDeathConfirmedR45=true;d.setDirty();TvCampaignDirector.encounterCompleteR45(l,d.active,d.owner,boss.getUUID());}
        else if(!d.phase.equals("cancel"))
        {TvYashimaDirectorR50.fail(l,d,"目标死亡已确认，但未满足本行动的真实炮击与观测条件。");d.targetDeathConfirmedR45=true;d.setDirty();}

    }
    @SubscribeEvent public static void logout(net.minecraftforge.event.entity.player.PlayerEvent.PlayerLoggedOutEvent e)
    {if(e.getEntity() instanceof ServerPlayer p)TvEncounterRulesR45.logout(p);}
    @SubscribeEvent public static void unloaded(net.minecraftforge.event.level.LevelEvent.Unload e)
    {if(e.getLevel() instanceof ServerLevel l){TvEncounterRulesR45.clearSession(l);TvYashimaDirectorR50.clearSession(l);}}
    private TvEncounterDirectorR45(){}
}
