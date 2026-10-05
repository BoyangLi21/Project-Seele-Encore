package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Versioned civil mask and original equipment UUIDs own the two new physical wells. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class EquipmentVaultsR47
{
    private record Vault(String id,int payload,double x,double y,double z,List<BlockPos> lids){}
    private static final Map<ServerLevel,List<Vault>> PLANS=new WeakHashMap<>();
    private static final Map<NervArmamentStationEntity,Integer> LID_PHASES=new WeakHashMap<>();
    private static List<Vault> plans(ServerLevel level)
    {
        return PLANS.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve("r47_equipment_vaults.json");
            if(!Files.isRegularFile(file))return List.of();
            try
            {
                var data=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(!"projectseele.r47.equipment-vaults.v1".equals(data.get("schema").getAsString()))throw new IllegalStateException("Unknown equipment well plan");
                List<Vault> result=new ArrayList<>();
                for(var value:data.getAsJsonArray("vaults"))
                {
                    var row=value.getAsJsonObject();JsonArray centre=row.getAsJsonArray("centre");List<BlockPos> lids=new ArrayList<>();
                    for(var item:row.getAsJsonArray("lidPositions"))
                    {var p=item.getAsJsonArray();lids.add(new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt()));}
                    int payload=row.get("payload").getAsInt();if(payload!=6&&payload!=7)throw new IllegalStateException("Invalid dedicated payload");
                    int span=row.get("lid_span").getAsInt();
                    if(span!=(payload==7?29:9)||lids.size()!=span*span)throw new IllegalStateException("Incomplete well lid");
                    result.add(new Vault(row.get("id").getAsString(),payload,centre.get(0).getAsDouble(),centre.get(1).getAsDouble(),centre.get(2).getAsDouble(),List.copyOf(lids)));
                }
                return List.copyOf(result);
            }
            catch(Exception error){throw new IllegalStateException("Equipment well deployment is incomplete",error);}
        });
    }
    public static final class State extends SavedData
    {
        final Map<String,UUID> ids=new HashMap<>();
        final Map<String,UUID> loans=new HashMap<>();
        public static State load(CompoundTag tag)
        {var state=new State();var names=tag.getCompound("Wells");for(String name:names.getAllKeys())if(names.hasUUID(name))state.ids.put(name,names.getUUID(name));
            var loans=tag.getCompound("Loans");for(String name:loans.getAllKeys())if(loans.hasUUID(name))state.loans.put(name,loans.getUUID(name));return state;}
        @Override public CompoundTag save(CompoundTag tag)
        {var names=new CompoundTag();ids.forEach(names::putUUID);tag.put("Wells",names);
            var borrowed=new CompoundTag();loans.forEach(borrowed::putUUID);tag.put("Loans",borrowed);return tag;}
    }
    public static Optional<BlockPos> knownVaultPositionR47(ServerLevel level,int payload)
    {
        State state=level.getDataStorage().get(State::load,"projectseele_equipment_vaults_r47");
        if(state==null)return Optional.empty();
        return plans(level).stream().filter(vault->vault.payload==payload&&state.ids.containsKey(vault.id))
                .map(vault->BlockPos.containing(vault.x,vault.y,vault.z)).findFirst();
    }
    /** A carried shield keeps its original saved loan while its distant well is unloaded. */
    public static boolean physicalShieldLoanAuthorizedR48(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level)||eva.isExperimentalUnit()||eva.getUnitVariant()!=0)return false;
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(0).orElse(null);
        if(fleet==null||!eva.getUUID().equals(fleet.canonicalId()))return false;
        State state=level.getDataStorage().get(State::load,"projectseele_equipment_vaults_r47");
        if(state==null)return false;
        for(var vault:plans(level))if(vault.payload==EvaUnit01Entity.WEAPON_SHIELD_R45)
        {
            UUID original=state.ids.get(vault.id);
            if(original==null||!eva.getUUID().equals(state.loans.get(vault.id)))continue;
            var loaded=level.getEntity(original);
            return loaded==null||loaded instanceof NervArmamentStationEntity station
                    &&station.payloadR47()==vault.payload
                    &&vault.id.equals(station.getPersistentData().getString("R47Vault"));
        }
        return false;
    }
    /** Commands resolve the commissioned physical object, never spawn a substitute. */
    public static NervArmamentStationEntity recordedStationR47(ServerLevel level,int payload)
    {
        State state=level.getDataStorage().get(State::load,"projectseele_equipment_vaults_r47");
        if(state==null)return null;
        for(var vault:plans(level))if(vault.payload==payload)
        {
            UUID id=state.ids.get(vault.id);if(id==null)return null;
            BlockPos position=BlockPos.containing(vault.x,vault.y,vault.z);
            NervArmamentStationEntity.keepCommandStationLoaded(level,position);level.getChunkAt(position);
            var entity=level.getEntity(id);
            return entity instanceof NervArmamentStationEntity station&&station.payloadR47()==payload?station:null;
        }
        return null;
    }
    public static boolean issueR47(NervArmamentStationEntity station,EvaUnit01Entity eva)
    {
        if(!(station.level() instanceof ServerLevel level)||eva.level()!=level)return false;
        String id=station.getPersistentData().getString("R47Vault");
        if(id.isEmpty())return eva.installExternalArmament(station.payloadR47());
        State state=level.getDataStorage().get(State::load,"projectseele_equipment_vaults_r47");
        if(state==null||!station.getUUID().equals(state.ids.get(id))||state.loans.containsKey(id))return false;
        if(!eva.installExternalArmament(station.payloadR47()))return false;
        state.loans.put(id,eva.getUUID());state.setDirty();return true;
    }
    /** The actual recorded airframe returns its loan during cold hangar storage. */
    public static void returnStoredR47(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel level))return;
        State state=level.getDataStorage().get(State::load,"projectseele_equipment_vaults_r47");if(state==null)return;
        for(var vault:plans(level))if(eva.getUUID().equals(state.loans.get(vault.id)))
        {
            var station=recordedStationR47(level,vault.payload);if(station==null)continue;
            station.returnStoredPayloadR47();state.loans.remove(vault.id);state.setDirty();
        }
    }
    @SubscribeEvent
    public static void tick(TickEvent.LevelTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||!(event.level instanceof ServerLevel level)
                ||!level.dimension().location().toString().equals("projectseele:geofront")||level.getGameTime()%20!=0)return;
        State state=level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_equipment_vaults_r47");
        for(var vault:plans(level))
        {
            BlockPos position=BlockPos.containing(vault.x,vault.y,vault.z);
            NervArmamentStationEntity.keepCommandStationLoaded(level,position);
            UUID id=state.ids.get(vault.id);var found=id==null?null:level.getEntity(id);
            if(found==null)
            {
                // Never replace an unloaded original object: loading its home
                // chunk precedes the UUID lookup and first creation.
                level.getChunkAt(position);found=id==null?null:level.getEntity(id);
                if(found==null&&id==null)
                {
                    var station=ModEntities.NERV_ARMAMENT_STATION.get().create(level);if(station==null)continue;
                    station.setPos(vault.x,vault.y,vault.z);station.setPayloadR47(vault.payload);
                    station.getPersistentData().putString("R47Vault",vault.id);
                    if(level.addFreshEntity(station)){state.ids.put(vault.id,station.getUUID());state.setDirty();found=station;}
                }
            }
            if(found instanceof NervArmamentStationEntity station)updateLid(level,station,vault);
        }
    }
    private static void updateLid(ServerLevel level,NervArmamentStationEntity station,Vault vault)
    {
        boolean closed=station.getStationState()==NervArmamentStationEntity.STOWED
                ||station.getStationState()==NervArmamentStationEntity.CLOSING;
        var desired=closed?Blocks.BARRIER.defaultBlockState():Blocks.AIR.defaultBlockState();
        for(var position:vault.lids)
        {
            var current=level.getBlockState(position);
            if(level.getBlockEntity(position)!=null||!current.isAir()&&!current.is(Blocks.BARRIER))return;
            if(closed&&!current.is(Blocks.BARRIER)&&!level.getEntities((net.minecraft.world.entity.Entity)null,
                    new net.minecraft.world.phys.AABB(position),e->e instanceof net.minecraft.world.entity.LivingEntity).isEmpty())return;
        }
        for(var position:vault.lids)if(!level.getBlockState(position).equals(desired))level.setBlock(position,desired,3);
        LID_PHASES.put(station,station.getStationState());
    }
    public static boolean beforeMechanicalTick(NervArmamentStationEntity station)
    {
        if(!(station.level() instanceof ServerLevel level))return true;
        String id=station.getPersistentData().getString("R47Vault");if(id.isEmpty())return true;
        for(var vault:plans(level))if(vault.id.equals(id))
        {
            int phase=station.getStationState();
            if(!Objects.equals(LID_PHASES.get(station),phase))updateLid(level,station,vault);
            // Pause physical closing while any part of an occupant still
            // crosses the lid. A visual cover never replaces native support.
            if(phase==NervArmamentStationEntity.CLOSING)
                for(var position:vault.lids)if(!level.getBlockState(position).is(Blocks.BARRIER))return false;
            return true;
        }
        return false;
    }
    private EquipmentVaultsR47(){}
}
