package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaShieldRigR47;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.physics.CombatDamageTargetsR44;
import com.projectseele.physics.CombatEntityQueryR44;
import java.util.HashSet;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.entity.projectile.ThrownEnderpearl;
import net.minecraft.world.entity.projectile.ThrownExperienceBottle;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.EntityJoinLevelEvent;
import net.minecraftforge.event.entity.ProjectileImpactEvent;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.event.level.ExplosionEvent;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Server physical occlusion, with no spectator/area immunity or surrogate shield plane. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class ShieldCoverR48
{
    public record Contact(EvaUnit01Entity holder, Vec3 point) {}
    private static final Map<ServerLevel, Set<UUID>> PROJECTILES = new WeakHashMap<>();
    private static final ThreadLocal<Boolean> EXACT_DAMAGE = new ThreadLocal<>();
    private ShieldCoverR48() {}

    private static boolean finite(Vec3 point)
    {
        return point != null && Double.isFinite(point.x) && Double.isFinite(point.y) && Double.isFinite(point.z);
    }

    public static boolean authorized(EvaUnit01Entity holder)
    {
        return holder.level() instanceof ServerLevel && holder.isAlive() && EvaShieldRigR47.equipped(holder)
                && (TvMissionEquipmentR45.shieldLoanAuthorizedR48(holder)
                    || EquipmentVaultsR47.physicalShieldLoanAuthorizedR48(holder));
    }

    /** The segment ends at the actual body/terrain contact, never the intended target's centre. */
    public static Optional<Contact> nearest(ServerLevel level, Vec3 from, Vec3 to, Entity attacker)
    {
        if (!finite(from) || !finite(to) || from.distanceToSqr(to) < 1e-12) return Optional.empty();
        Contact nearest = null; double distance = Double.POSITIVE_INFINITY;
        for (EvaUnit01Entity holder : level.getEntitiesOfClass(EvaUnit01Entity.class,
                CombatEntityQueryR44.originSearch(new AABB(from, to)), ShieldCoverR48::authorized))
        {
            if (attacker != null && holder.getRootVehicle() == attacker.getRootVehicle()) continue;
            Optional<Vec3> intersection = EvaShieldRigR47.intercept(holder, from, to);
            if (intersection.isEmpty()) continue;
            double current = from.distanceToSqr(intersection.get());
            if (current < distance) { nearest = new Contact(holder, intersection.get()); distance = current; }
        }
        return Optional.ofNullable(nearest);
    }

    /** Explicit weapon-contact admission for Root's shared damage entry point. */
    public static boolean blocksDirect(Entity victim, DamageSource source, Vec3 from, Vec3 actualContact)
    {
        if (!(victim.level() instanceof ServerLevel level) || !finite(from) || !finite(actualContact)) return false;
        // A contact returned by the float hand matrix can land a sub-mm past
        // its own closed triangle endpoint when clipped a second time.
        Vec3 inclusiveContact = actualContact.add(actualContact.subtract(from).normalize().scale(.001));
        return nearest(level, from, inclusiveContact, source.getDirectEntity() != null
                ? source.getDirectEntity() : source.getEntity()).isPresent();
    }

    /** Vanilla damage has no explicit weapon contact; Root calls this before EVA A.T. consumption. */
    public static boolean blocksFallback(Entity victim, DamageSource source)
    {
        if (Boolean.TRUE.equals(EXACT_DAMAGE.get()) || !(victim.level() instanceof ServerLevel)
                || source.getEntity() == null || !finite(source.getSourcePosition())) return false;
        Vec3 from = source.getSourcePosition();
        return blocksDirect(victim, source, from, CombatDamageTargetsR44.nearestSurface(victim, from));
    }

    /** A precise producer must not be reinterpreted as a centre/eye fallback in LivingAttackEvent. */
    public static boolean hurtDirect(Entity victim, DamageSource source, float amount, Vec3 from, Vec3 actualContact,
                                     java.util.function.BooleanSupplier acceptedDamage)
    {
        if (!finite(from) || !finite(actualContact)) return acceptedDamage.getAsBoolean();
        if (blocksDirect(victim, source, from, actualContact)) return false;
        Boolean previous = EXACT_DAMAGE.get(); EXACT_DAMAGE.set(true);
        try { return acceptedDamage.getAsBoolean(); }
        finally { if (previous == null) EXACT_DAMAGE.remove(); else EXACT_DAMAGE.set(previous); }
    }

    public static boolean yashima(RamielEntity boss)
    {
        if (!(boss.level() instanceof ServerLevel level)) return false;
        TvCampaignSavedData data = TvCampaignSavedData.get(level);
        var site = TvEncounterSitesR45.site(level, data.active).orElse(null);
        return data.active.equals("ramiel") && Set.of("alert","approach","combat").contains(data.phase) && data.generationR43 > 0
                && site != null && site.geometryValidated() && site.modelReady()
                && !data.targetDeathConfirmedR45 && boss.getUUID().equals(data.angel)
                && com.projectseele.event.TvEncounterDirectorR45.owned(boss, data)
                && TvEncounterRulesR45.missionRamielAnchor(boss) != null;
    }

    /** Keep all the original firing gates except a missing/mis-aimed shield after combat starts. */
    public static boolean missionBeamAllowed(RamielEntity boss)
    {
        return yashima(boss)&&TvEncounterRulesR45.missionBeamAllowed(boss);
    }

    /** Shared with the mission director's live-combat hold, never with setup or victory admission. */
    public static boolean shieldOnlyBlockerAfterCombat(ServerLevel level, TvCampaignSavedData data, String blocker)
    {
        if (!blocker.equals("零号机尚未装备防护盾。")
                && !blocker.equals("零号机请调整盾面，遮挡目标到初号机的射线。")) return false;
        if (data.angel == null || !(level.getEntity(data.angel) instanceof RamielEntity boss) || !yashima(boss)) return false;
        var owner = data.owner == null ? null : level.getServer().getPlayerList().getPlayer(data.owner);
        if (owner == null || owner.level() != level || !TvEncounterRulesR45.targetFrameReady(level, data, owner)) return false;
        // equipmentBlocker has already checked participants, ready states,
        // cannon/loadout/range before its shield clause. Recheck the later
        // clauses explicitly; removing that early return must not skip them.
        var site = TvEncounterSitesR45.site(level, data.active).orElse(null);
        var cover = TvSortiesR32.assignedUnit(level, data, 0);
        var shooter = TvSortiesR32.assignedUnit(level, data, 1);
        return site != null && cover != null && shooter != null
                && cover.position().distanceTo(site.cover()) <= 12
                && shooter.position().distanceTo(site.hero()) <= 12
                && boss.effectiveBeamRangeR45() >= boss.getBoundingBox().getCenter().distanceTo(shooter.getEyePosition());
    }

    /** Called once by fireBeam, never by the afterglow renderer or damage ticks. */
    public static void receiveYashima(Contact contact, RamielEntity boss, UUID shot, DamageSource source)
    {
        if (!yashima(boss) || !authorized(contact.holder()) || contact.holder().level() != boss.level()) return;
        EvaUnit01Entity holder = contact.holder();
        long generation = TvCampaignSavedData.get((ServerLevel) boss.level()).generationR43;
        CompoundTag hits = holder.getPersistentData().getCompound("R48YashimaShieldHits").copy();
        if (!hits.hasUUID("Boss") || !hits.getUUID("Boss").equals(boss.getUUID()) || hits.getLong("Generation") != generation)
        {
            hits = new CompoundTag(); hits.putUUID("Boss", boss.getUUID()); hits.putLong("Generation", generation);
        }
        ListTag shots = hits.getList("Shots", Tag.TAG_STRING);
        if (shots.stream().anyMatch(entry -> entry.getAsString().equals(shot.toString()))) return;
        int count = Math.min(2, hits.getInt("Hits") + 1);
        Boolean previous = EXACT_DAMAGE.get(); EXACT_DAMAGE.set(true);
        try
        {
            if (holder.receiveYashimaShieldHitR48(source, count >= 2))
            {
                shots.add(StringTag.valueOf(shot.toString())); hits.put("Shots", shots);
                while(shots.size()>16)shots.remove(0);
                hits.putUUID("LastShot", shot); hits.putInt("Hits", count);
                holder.getPersistentData().put("R48YashimaShieldHits", hits);
            }
        }
        finally { if (previous == null) EXACT_DAMAGE.remove(); else EXACT_DAMAGE.set(previous); }
    }

    @SubscribeEvent
    public static void joined(EntityJoinLevelEvent event)
    {
        if (event.getLevel() instanceof ServerLevel level && event.getEntity() instanceof Projectile projectile
                && !(projectile instanceof ThrownEnderpearl) && !(projectile instanceof ThrownExperienceBottle))
            PROJECTILES.computeIfAbsent(level, ignored -> new HashSet<>()).add(projectile.getUUID());
    }

    @SubscribeEvent
    public static void unloaded(LevelEvent.Unload event)
    {
        if (event.getLevel() instanceof ServerLevel level) PROJECTILES.remove(level);
    }

    private static void stopProjectile(Projectile projectile, Vec3 contact)
    {
        if (projectile instanceof AbstractArrow arrow)
        {
            // Keep the original arrow/trident identity, pickup and owner.
            Vec3 motion = arrow.getDeltaMovement();
            arrow.setPos(contact.subtract(motion.normalize().scale(.05)));
            arrow.setDeltaMovement(motion.scale(-.15)); arrow.setPierceLevel((byte) 0); arrow.hasImpulse = true;
        }
        else projectile.discard();
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void projectileTick(TickEvent.LevelTickEvent event)
    {
        if (event.phase != TickEvent.Phase.START || !(event.level instanceof ServerLevel level)) return;
        Set<UUID> tracked = PROJECTILES.get(level); if (tracked == null) return;
        tracked.removeIf(id -> !(level.getEntity(id) instanceof Projectile projectile) || !projectile.isAlive());
        for (UUID id : Set.copyOf(tracked))
        {
            if (!(level.getEntity(id) instanceof Projectile projectile)) continue;
            Vec3 from = projectile.position(), to = from.add(projectile.getDeltaMovement());
            if (!finite(from) || !finite(to) || from.distanceToSqr(to) < 1e-10) continue;
            Vec3 terrain = level.clip(new ClipContext(from, to, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, projectile)).getLocation();
            var body = CombatDamageTargetsR44.ray(level, from, terrain, 0, projectile, projectile.getOwner());
            Vec3 end = body == null ? terrain : body.getLocation();
            nearest(level, from, end, projectile.getOwner()).ifPresent(contact -> stopProjectile(projectile, contact.point()));
        }
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void projectileImpact(ProjectileImpactEvent event)
    {
        Projectile projectile = event.getProjectile();
        if (!(projectile.level() instanceof ServerLevel level) || projectile instanceof ThrownEnderpearl
                || projectile instanceof ThrownExperienceBottle) return;
        nearest(level, projectile.position(), event.getRayTraceResult().getLocation(), projectile.getOwner()).ifPresent(contact ->
        {
            event.setCanceled(true); stopProjectile(projectile, contact.point());
        });
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void explosion(ExplosionEvent.Detonate event)
    {
        if (!(event.getLevel() instanceof ServerLevel level)) return;
        Vec3 from = event.getExplosion().getPosition();
        Entity attacker = event.getExplosion().getDirectSourceEntity();
        event.getAffectedEntities().removeIf(victim -> CombatDamageTargetsR44.supported(CombatDamageTargetsR44.parent(victim))
                && nearest(level, from, CombatDamageTargetsR44.nearestSurface(CombatDamageTargetsR44.parent(victim), from), attacker).isPresent());
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void attacked(LivingAttackEvent event)
    {
        if (Boolean.TRUE.equals(EXACT_DAMAGE.get()) || !(event.getEntity().level() instanceof ServerLevel)) return;
        if (blocksFallback(event.getEntity(), event.getSource())) event.setCanceled(true);
    }
}
