package com.projectseele.physics;

import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.CombatFeelR31;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.ShamshelEntity;
import com.projectseele.world.TvCampaignSavedData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.event.entity.living.LivingDamageEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.event.entity.living.LivingHurtEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Read-only observation of one supplied original UUID; never enables or alters an attack. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class ShamshelDamageWitnessR48
{
    private static final String TARGET = System.getProperty("projectseele.r48ShamshelDamageWitness", "");
    private static int rows;
    private ShamshelDamageWitnessR48() { }

    public static boolean enabled() { return !TARGET.isEmpty() && rows < 64; }

    public static boolean selected(Entity entity)
    {
        return !TARGET.isEmpty() && entity instanceof ShamshelEntity
                && !entity.level().isClientSide && TARGET.equalsIgnoreCase(entity.getStringUUID());
    }

    /** An empty candidate result can observe the supplied original by UUID, with no scan/load. */
    public static void producerGate(String gate, Entity attacker, Entity candidate, float amount, String detail)
    {
        if (!enabled()) return;
        Entity observed = candidate;
        if (observed == null && attacker != null && attacker.level() instanceof ServerLevel level)
        {
            try { observed = level.getEntity(java.util.UUID.fromString(TARGET)); }
            catch (IllegalArgumentException invalidTarget) { return; }
        }
        record(gate, attacker, observed, null, amount, detail);
    }

    public static void record(String gate, Entity attacker, Entity target, DamageSource source, float amount, String detail)
    {
        if (!selected(target) || rows >= 64) return;
        try { snapshot(gate, attacker, target, source, amount, detail); }
        catch (RuntimeException failure)
        {
            rows++;
            ProjectSeele.LOGGER.warn("R48 SHAMSHEL DAMAGE observation unavailable; gameplay retained: gate={} target={}",
                    gate, target.getUUID(), failure);
        }
    }

    private static void snapshot(String gate, Entity attacker, Entity target, DamageSource source, float amount, String detail)
    {
        if (!selected(target) || rows >= 64 || !(target.level() instanceof ServerLevel level)) return;
        ShamshelEntity angel = (ShamshelEntity) target;
        JsonObject row = new JsonObject();
        row.addProperty("row", ++rows); row.addProperty("gate", gate); row.addProperty("detail", detail);
        row.addProperty("amount", amount);
        row.addProperty("world_tick", level.getGameTime()); row.addProperty("dimension", level.dimension().location().toString());
        row.addProperty("target_uuid", target.getStringUUID()); row.addProperty("health", angel.getHealth());
        row.addProperty("max_health", angel.getMaxHealth()); row.addProperty("at_field", angel.getAtField());
        row.addProperty("armor", angel.getArmorValue()); row.addProperty("invulnerable_time", angel.invulnerableTime);
        row.addProperty("hurt_time", angel.hurtTime); row.addProperty("death_time", angel.deathTime);
        row.addProperty("alive", angel.isAlive()); row.addProperty("dead_or_dying", angel.isDeadOrDying());
        row.addProperty("invulnerable", angel.isInvulnerable()); row.addProperty("no_ai", angel.isNoAi());
        row.addProperty("standing_bounds", target.getBoundingBox().toString()); row.addProperty("position", target.position().toString());
        row.addProperty("effects", angel.getActiveEffects().toString());
        var beat = CombatFeelR31.beat(angel);
        row.addProperty("reaction", beat == null ? "none" : beat.toString());
        row.addProperty("hit_paused", CombatFeelR31.hitPaused(angel));
        row.addProperty("dynamics_active", CombatBodyDynamics.active(angel));
        boolean posed = ShamshelPosedContactsR48.supports(angel);
        row.addProperty("posed_contact", posed); row.addProperty("posed_resources", ShamshelPosedContactsR48.resourceStatus());
        if (posed) row.addProperty("posed_bounds", ShamshelPosedContactsR48.bounds(angel).toString());
        if (source != null)
        {
            row.addProperty("damage_type", source.getMsgId());
            row.addProperty("bypasses_cooldown", source.is(DamageTypeTags.BYPASSES_COOLDOWN));
            row.addProperty("bypasses_invulnerability", source.is(DamageTypeTags.BYPASSES_INVULNERABILITY));
            row.addProperty("at_bypass", com.projectseele.combat.AtFieldRules.bypassesAtField(source));
            if (source.getDirectEntity() != null) row.addProperty("direct_uuid", source.getDirectEntity().getStringUUID());
            if (source.getEntity() != null) row.addProperty("causing_uuid", source.getEntity().getStringUUID());
        }
        if (attacker != null) row.addProperty("attacker_uuid", attacker.getStringUUID());
        if (attacker instanceof EvaUnit01Entity eva)
        {
            row.addProperty("weapon", eva.getWeapon());
            row.addProperty("ordinary_stage", eva.getOrdinaryAttackStage()); row.addProperty("heavy", eva.isHeavyMotionActive());
            if (eva.getPilotEntity() != null) row.addProperty("pilot_uuid", eva.getPilotEntity().getStringUUID());
        }
        var mission = TvCampaignSavedData.get(level);
        row.addProperty("mission", mission.active); row.addProperty("mission_phase", mission.phase);
        row.addProperty("mission_generation", mission.generationR43);
        row.addProperty("mission_owner", mission.owner == null ? "none" : mission.owner.toString());
        row.addProperty("mission_target", mission.angel == null ? "none" : mission.angel.toString());
        row.addProperty("target_death_confirmed", mission.targetDeathConfirmedR45);
        row.addProperty("tv03_tag", angel.getTags().contains("seele_tv_shamshel_r24"));
        row.addProperty("tv03_can_finish", mission.canFinish("shamshel", mission.owner, angel.getUUID()));
        row.addProperty("scope", "Server gate snapshot; LivingDamage is before health update. No visual/kill pass inferred.");
        ProjectSeele.LOGGER.info("R48 SHAMSHEL DAMAGE {}", row);
    }

    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void attacked(LivingAttackEvent event)
    { record("forge_attack", event.getSource().getEntity(), event.getEntity(), event.getSource(), event.getAmount(), "canceled=" + event.isCanceled()); }
    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void hurt(LivingHurtEvent event)
    { record("forge_hurt", event.getSource().getEntity(), event.getEntity(), event.getSource(), event.getAmount(), "canceled=" + event.isCanceled()); }
    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void damaged(LivingDamageEvent event)
    { record("forge_damage_before_health_update", event.getSource().getEntity(), event.getEntity(), event.getSource(), event.getAmount(), "canceled=" + event.isCanceled()); }
    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void died(LivingDeathEvent event)
    { record("forge_death", event.getSource().getEntity(), event.getEntity(), event.getSource(), 0, "canceled=" + event.isCanceled()); }
}
