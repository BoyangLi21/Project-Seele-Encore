package com.projectseele.world;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;

import com.mojang.datafixers.util.Pair;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.LilithEntity;
import com.projectseele.event.ThirdImpactSavedData;
import com.projectseele.visual.GeoFrontCommands;
import it.unimi.dsi.fastutil.longs.LongSet;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.world.ForgeChunkManager;

/**
 * Bounded migration for debris produced by early procedural NERV revisions.
 *
 * <p>This is intentionally not another permanent world auditor. It runs once
 * after a player enters GeoFront, touches only already-loaded entities, and
 * then leaves the normal server tick completely idle.</p>
 */
public final class NervRuntimeMaintenance
{
    private static final Set<MinecraftServer> SWEPT_SERVERS =
            Collections.newSetFromMap(new WeakHashMap<>());
    private static final Set<Item> CONSTRUCTION_DEBRIS = Set.of(
            Items.RAIL, Items.POWERED_RAIL, Items.TORCH,
            Items.STONE_BUTTON, Items.LADDER);

    private NervRuntimeMaintenance() {}

    /**
     * Removes persistent Project SEELE chunk tickets whose owning operation no
     * longer exists.  Forge invokes this before reinstating tickets, which is
     * the only safe point to prevent a stale legacy UUID from making a route
     * chunk tick forever.
     */
    public static void validateForcedChunkTickets(
            ServerLevel level, ForgeChunkManager.TicketHelper helper)
    {
        Set<UUID> validOwners = new HashSet<>();
        for (ThirdImpactSavedData.StoredImpact impact
                : ThirdImpactSavedData.get(level).impacts())
        {
            validOwners.add(impact.id());
        }
        for (AngelSiegeSavedData.StoredSiege siege
                : AngelSiegeSavedData.get(level).sieges())
        {
            validOwners.add(siege.eventId());
        }
        if (level.dimension().equals(GeoFrontCommands.GEOFRONT)
                && level.getServer().getLevel(
                        net.minecraft.world.level.Level.OVERWORLD) != null)
        {
            EvaFleetSavedData fleet =
                    EvaFleetSavedData.get(level.getServer());
            for (int variant = 0; variant < 3; variant++)
            {
                fleet.entry(variant)
                        .filter(entry -> entry.phase()
                                != EvaFleetSavedData.Phase.PARKED
                                && entry.phase()
                                != EvaFleetSavedData.Phase.DEPLOYED)
                        .map(EvaFleetSavedData.FleetEntry::canonicalId)
                        .ifPresent(validOwners::add);
            }
        }

        int removedOwners = 0;
        int removedChunkLinks = 0;
        int retainedChunkLinks = 0;
        /*
         * removeAllTickets mutates the same fastutil map exposed by
         * getEntityTickets().  Iterate a stable snapshot: Forge may restore
         * several stale owners in one save and the live iterator is not safe
         * to mutate.
         */
        ArrayList<Map.Entry<UUID, Pair<LongSet, LongSet>>> tickets =
                new ArrayList<>(helper.getEntityTickets().entrySet());
        for (Map.Entry<UUID, Pair<LongSet, LongSet>> ticket : tickets)
        {
            if (validOwners.contains(ticket.getKey()))
            {
                retainedChunkLinks += ticket.getValue().getFirst().size()
                        + ticket.getValue().getSecond().size();
                continue;
            }
            removedChunkLinks += ticket.getValue().getFirst().size()
                    + ticket.getValue().getSecond().size();
            helper.removeAllTickets(ticket.getKey());
            removedOwners++;
        }
        if (level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
        }
        if (removedOwners > 0)
        {
            ProjectSeele.LOGGER.warn(
                    "NERV stale forced-chunk migration: dimension={} owners={} chunkLinks={} validOwners={}",
                    level.dimension().location(), removedOwners,
                    removedChunkLinks, validOwners.size());
        }
    }

    public static void tick(MinecraftServer server)
    {
        if (server.getTickCount() % 20 != 0
                || SWEPT_SERVERS.contains(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null || level.players().isEmpty())
        {
            return;
        }
        SWEPT_SERVERS.add(server);
        SweepResult result = sweepLoaded(level);
        if (result.total() > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV legacy entity migration: debris={} ambientMobs={} duplicateLilith={} loadedEntities={}",
                    result.debris(), result.ambientMobs(),
                    result.duplicateLilith(),
                    result.loadedEntities());
        }
    }

    /**
     * Cancels duplicate specimens while their entity chunk is entering the
     * level. The once-per-server sweep remains as a safety net for entities
     * that were already resident before the first player joined.
     */
    public static boolean rejectJoin(ServerLevel level, Entity entity)
    {
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return false;
        }
        // Old Tokyo-3 rail reconstruction dropped thousands of rail item
        // entities across many chunks.  The one-shot loaded-entity sweep
        // cannot see a cold chunk, so reject that exact railway debris as its
        // entity section is loaded later.  Other item drops are untouched.
        if (entity instanceof ItemEntity item && isEastRailDebris(item))
        {
            return true;
        }
        if (isWildGeoFrontArsMob(entity))
        {
            return true;
        }
        if (!(entity instanceof LilithEntity)
                || !specimenBounds().contains(entity.position()))
        {
            return false;
        }
        return level.getEntitiesOfClass(LilithEntity.class, specimenBounds(),
                existing -> existing.isAlive() && existing != entity)
                .stream().findAny().isPresent();
    }

    public static void reset()
    {
        SWEPT_SERVERS.clear();
    }

    private static SweepResult sweepLoaded(ServerLevel level)
    {
        int loaded = 0;
        int debris = 0;
        int ambientMobs = 0;
        ArrayList<LilithEntity> specimens = new ArrayList<>();
        // EntityLookup's linked iterator is invalidated by discard(). Gather a
        // stable server-thread snapshot first, then perform the one-shot
        // migration. The former mutate-while-iterating path could corrupt the
        // iterator and crash a rescue world during its first joined tick.
        ArrayList<Entity> snapshot = new ArrayList<>();
        level.getAllEntities().forEach(snapshot::add);
        for (Entity entity : snapshot)
        {
            loaded++;
            if (entity instanceof ItemEntity item
                    && isLegacyConstructionDebris(item))
            {
                item.discard();
                debris++;
            }
            else if (isWildGeoFrontArsMob(entity))
            {
                entity.discard();
                ambientMobs++;
            }
            else if (entity instanceof LilithEntity lilith
                    && specimenBounds().contains(lilith.position()))
            {
                specimens.add(lilith);
            }
        }

        BlockPos anchor = specimenAnchor();
        Vec3 centre = Vec3.atBottomCenterOf(anchor);
        specimens.sort(Comparator
                .comparingDouble((LilithEntity entity) ->
                        entity.position().distanceToSqr(centre))
                .thenComparing(Entity::getUUID));
        int duplicateLilith = 0;
        for (int index = 1; index < specimens.size(); index++)
        {
            specimens.get(index).discard();
            duplicateLilith++;
        }
        return new SweepResult(debris, ambientMobs, duplicateLilith, loaded);
    }

    private static boolean isLegacyConstructionDebris(ItemEntity entity)
    {
        if (!CONSTRUCTION_DEBRIS.contains(entity.getItem().getItem()))
        {
            return false;
        }
        Vec3 position = entity.position();
        BlockPos geo = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        boolean withinIntegratedMap =
                Math.abs(position.x - geo.getX()) <= 400.0D
                && Math.abs(position.z - geo.getZ()) <= 400.0D
                && position.y >= -640.0D && position.y <= 220.0D;
        if (!withinIntegratedMap)
        {
            return false;
        }

        // The largest leak is the old east railway: support reconstruction
        // detached 2,000+ rail entities along one exact civil-engineering lot.
        boolean eastRail = isEastRailDebris(entity);
        // Other debris is limited to the installed map and is removed only by
        // this one-shot migration. EVA weapons and all unrelated drops survive.
        return eastRail || entity.getItem().is(Items.TORCH)
                || entity.getItem().is(Items.STONE_BUTTON)
                || entity.getItem().is(Items.LADDER);
    }

    private static boolean isEastRailDebris(ItemEntity entity)
    {
        if (!entity.getItem().is(Items.RAIL)
                && !entity.getItem().is(Items.POWERED_RAIL))
        {
            return false;
        }
        Vec3 position = entity.position();
        BlockPos city = IntegratedNervMapBuilder.TOKYO3_ORIGIN;
        return Math.abs(position.x
                - (city.getX() + Tokyo3LandscapeBuilder.RAIL_X)) <= 12.0D
                && Math.abs(position.y
                - (city.getY() + Tokyo3LandscapeBuilder.RAIL_DECK_Y + 1))
                <= 4.0D;
    }

    /**
     * The custom cavern inherited Ars Nouveau biome population and accumulated
     * 239 pathfinding helper mobs in the legacy save.  Keep anything a player
     * named, made persistent, tamed, summoned or spawned from an egg; only the
     * untouched NATURAL/CHUNK_GENERATION population is facility debris.
     */
    private static boolean isWildGeoFrontArsMob(Entity entity)
    {
        if (!(entity instanceof Mob mob)
                || !"ars_nouveau".equals(BuiltInRegistries.ENTITY_TYPE
                        .getKey(entity.getType()).getNamespace())
                || entity.hasCustomName() || mob.isPersistenceRequired())
        {
            return false;
        }
        CompoundTag tag = entity.saveWithoutId(new CompoundTag());
        String spawnType = tag.getString("forge:spawn_type");
        boolean tamed = tag.getBoolean("tamed")
                || tag.hasUUID("Owner") || tag.hasUUID("OwnerUUID");
        return !tamed && ("CHUNK_GENERATION".equals(spawnType)
                || "NATURAL".equals(spawnType));
    }

    private static BlockPos specimenAnchor()
    {
        return IntegratedNervMapBuilder.GEOFRONT_ORIGIN.offset(
                0, TerminalDogmaBuilder.FACILITY_Y_OFFSET
                        + TerminalDogmaBuilder.LCL_SURFACE_Y, -22);
    }

    private static AABB specimenBounds()
    {
        BlockPos facility = IntegratedNervMapBuilder.GEOFRONT_ORIGIN.offset(
                0, TerminalDogmaBuilder.FACILITY_Y_OFFSET, 0);
        return AABB.ofSize(Vec3.atCenterOf(facility.offset(0, -59, 0)),
                64.0D, 48.0D, 96.0D);
    }

    private record SweepResult(int debris, int ambientMobs,
                               int duplicateLilith,
                               int loadedEntities)
    {
        int total()
        {
            return this.debris + this.ambientMobs + this.duplicateLilith;
        }
    }
}
