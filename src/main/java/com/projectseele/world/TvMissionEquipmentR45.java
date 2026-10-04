package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Finite physical Yashima cargo, including two explicitly commissioned new items. */
public final class TvMissionEquipmentR45
{
    public static final String CARGO="TvMissionCargoStackR45",CARGO_ID="TvMissionCargoIdR45";
    public static final String RACK_UNIT="TvMissionRackUnitR45";
    public static final String SUPPLY_RECEIPT="TvMissionSupplyReceiptR45";
    private static final String EPISODE="TV05-06";
    private static final ResourceLocation CANNON=new ResourceLocation("projectseele:eva_positron_cannon");
    private static final ResourceLocation SHIELD=new ResourceLocation("projectseele:yashima_shield");
    private static final String LOANED="loaned",RETURN_PENDING="return_pending",STORED="stored";
    private static final UUID[] SUPPLY_CARGO={UUID.fromString("3ea20e4d-37bf-5c8c-90b6-26316d2b4911"),UUID.fromString("58eab304-0fb0-5f44-b500-4fed8824db08")};
    private static final UUID[] SUPPLY_RACK={UUID.fromString("e9fd32e9-b3a3-5dc6-8d9f-21ce267a848e"),UUID.fromString("749cf141-0e2f-59ef-9e9b-d08346d5ea8d")};
    private static final class PhysicalStock
    {UUID cargo,rack,carrier;net.minecraft.core.BlockPos position;CompoundTag item=new CompoundTag();}
    private static final class Loan
    {
        UUID cargo,source,eva,owner,pilot;long generation;int unit;
        String episode=EPISODE,chapter="ramiel",dimension,status=LOANED;
        CompoundTag item=new CompoundTag();
    }
    public static final class State extends SavedData
    {
        private final Map<UUID,Loan> loans=new LinkedHashMap<>();
        private final Map<UUID,PhysicalStock> physical=new LinkedHashMap<>();
        private final Map<UUID,CompoundTag> commissioned=new LinkedHashMap<>();
        private final ListTag quarantined=new ListTag();
        private static State load(CompoundTag tag)
        {
            var state=new State();
            for(var raw:tag.getList("Loans",Tag.TAG_COMPOUND))
            {
                var n=(CompoundTag)raw;
                if(!n.hasUUID("Cargo")||!n.hasUUID("Source")||!n.hasUUID("Eva")||!n.hasUUID("Owner"))
                {state.quarantined.add(n.copy());continue;}
                var loan=new Loan();loan.cargo=n.getUUID("Cargo");loan.source=n.getUUID("Source");
                loan.eva=n.getUUID("Eva");loan.owner=n.getUUID("Owner");loan.generation=n.getLong("Generation");
                if(n.hasUUID("ActualPilotR45"))loan.pilot=n.getUUID("ActualPilotR45");
                loan.unit=n.getInt("Unit");loan.chapter=n.getString("Chapter");loan.episode=n.getString("Episode");
                loan.dimension=n.getString("Dimension");loan.status=n.getString("Status");loan.item=n.getCompound("Item").copy();
                if(state.loans.putIfAbsent(loan.cargo,loan)!=null)state.quarantined.add(n.copy());
            }
            for(var raw:tag.getList("Quarantined",Tag.TAG_COMPOUND))state.quarantined.add(raw.copy());
            for(var raw:tag.getList("PhysicalStockR45",Tag.TAG_COMPOUND))
            {
                var n=(CompoundTag)raw;
                if(!n.hasUUID("Cargo")||!n.contains("Item",Tag.TAG_COMPOUND)||n.hasUUID("Rack")&&n.hasUUID("Carrier"))
                {state.quarantined.add(n.copy());continue;}
                var stock=new PhysicalStock();stock.cargo=n.getUUID("Cargo");stock.item=n.getCompound("Item").copy();
                stock.rack=n.hasUUID("Rack")?n.getUUID("Rack"):null;stock.carrier=n.hasUUID("Carrier")?n.getUUID("Carrier"):null;
                if(n.contains("RackPosition",Tag.TAG_LONG))stock.position=net.minecraft.core.BlockPos.of(n.getLong("RackPosition"));
                if(state.physical.putIfAbsent(stock.cargo,stock)!=null)state.quarantined.add(n.copy());
            }
            for(var raw:tag.getList("CommissionedSupplyR45",Tag.TAG_COMPOUND))
            {
                var n=(CompoundTag)raw;
                if(!n.hasUUID("Cargo")||state.commissioned.putIfAbsent(n.getUUID("Cargo"),n.copy())!=null)state.quarantined.add(n.copy());
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            var list=new ListTag();
            for(var l:loans.values())
            {
                var n=new CompoundTag();n.putUUID("Cargo",l.cargo);n.putUUID("Source",l.source);
                n.putUUID("Eva",l.eva);n.putUUID("Owner",l.owner);n.putLong("Generation",l.generation);
                n.putInt("Unit",l.unit);n.putString("Chapter",l.chapter);n.putString("Episode",l.episode);
                n.putString("Dimension",l.dimension);n.putString("Status",l.status);n.put("Item",l.item.copy());
                if(l.pilot!=null)n.putUUID("ActualPilotR45",l.pilot);list.add(n);
            }
            tag.put("Loans",list);tag.put("Quarantined",quarantined.copy());
            var physicalList=new ListTag();
            for(var stock:physical.values())
            {
                var n=new CompoundTag();n.putUUID("Cargo",stock.cargo);n.put("Item",stock.item.copy());
                if(stock.rack!=null)n.putUUID("Rack",stock.rack);if(stock.carrier!=null)n.putUUID("Carrier",stock.carrier);physicalList.add(n);
                if(stock.position!=null)n.putLong("RackPosition",stock.position.asLong());
            }
            if(!physicalList.isEmpty())tag.put("PhysicalStockR45",physicalList);
            var initial=new ListTag();for(var n:commissioned.values())initial.add(n.copy());
            if(!initial.isEmpty())tag.put("CommissionedSupplyR45",initial);return tag;
        }
    }
    private static State state(ServerLevel l)
    {return l.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_tv_mission_equipment_r45");}
    private static int cargoUnit(ItemStack stack)
    {
        if(stack.isEmpty()||stack.getCount()!=1)return -1;
        var id=BuiltInRegistries.ITEM.getKey(stack.getItem());
        // Unregistered shield resolves to AIR, which is empty and rejected.
        return id.equals(CANNON)?1:id.equals(SHIELD)&&BuiltInRegistries.ITEM.containsKey(SHIELD)?0:-1;
    }
    /** Root calls once after its reversible civil/fixture receipt is committed; never a tick refill. */
    public static boolean commissionNewSupply(NervArmamentStationEntity station,int unit,String committedReceipt)
    {
        if(!(station.level() instanceof ServerLevel l)||!l.dimension().location().toString().equals("projectseele:geofront")
                ||unit<0||unit>1||!station.getUUID().equals(SUPPLY_RACK[unit])
                ||committedReceipt==null||!committedReceipt.matches("[0-9a-f]{64}")
                ||!committedReceipt.equals(station.getPersistentData().getString(SUPPLY_RECEIPT)))return false;
        var registry=BuiltInRegistries.ITEM;var id=unit==0?SHIELD:CANNON;
        if(!registry.containsKey(id))return false;
        var state=state(l);var cargo=SUPPLY_CARGO[unit];var slot=station.getPersistentData();
        if(state.commissioned.containsKey(cargo)||state.physical.containsKey(cargo)||state.loans.containsKey(cargo)
                ||slot.contains(CARGO)||slot.hasUUID(CARGO_ID)||slot.contains(RACK_UNIT,Tag.TAG_INT)&&slot.getInt(RACK_UNIT)!=unit)return false;
        var item=new ItemStack(registry.get(id),1);if(cargoUnit(item)!=unit)return false;
        item.getOrCreateTag().putUUID(CARGO_ID,cargo);var exact=item.save(new CompoundTag());
        var stock=new PhysicalStock();stock.cargo=cargo;stock.rack=station.getUUID();stock.position=station.blockPosition();stock.item=exact.copy();
        var receipt=new CompoundTag();receipt.putUUID("Cargo",cargo);receipt.putUUID("Source",station.getUUID());
        receipt.putInt("Unit",unit);receipt.put("Item",exact.copy());receipt.putString("Receipt",committedReceipt);
        state.commissioned.put(cargo,receipt);state.physical.put(cargo,stock);
        slot.putInt(RACK_UNIT,unit);slot.putUUID(CARGO_ID,cargo);slot.put(CARGO,exact);state.setDirty();return true;
    }
    private static boolean rackOwns(State state,NervArmamentStationEntity station,UUID cargo,CompoundTag item)
    {
        var physical=state.physical.get(cargo);
        if(physical!=null)return station.getUUID().equals(physical.rack)&&physical.carrier==null&&physical.item.equals(item);
        var loan=state.loans.get(cargo);
        return loan==null||loan.status.equals(STORED)&&loan.source.equals(station.getUUID())&&loan.item.equals(item);
    }
    private static boolean context(ServerLevel l,EvaUnit01Entity eva)
    {
        var d=TvCampaignSavedData.get(l);int unit=eva.getUnitVariant();
        if(eva.level()!=l||eva.isExperimentalUnit()||eva.getTags().contains("seele_motion_lab")||unit<0||unit>1||!d.active.equals("ramiel")
                ||d.owner==null||d.generationR43<=0||d.phase.equals("cancel")||d.targetDeathConfirmedR45)return false;
        var s=d.sorties.get(unit);var fleet=EvaFleetSavedData.get(l.getServer()).entry(unit).orElse(null);
        return s!=null&&s.eva!=null&&s.eva.equals(eva.getUUID())&&fleet!=null&&fleet.canonicalId().equals(eva.getUUID());
    }
    private static boolean live(Loan loan,ServerLevel l,EvaUnit01Entity eva)
    {
        if(!context(l,eva)||!loan.status.equals(LOANED))return false;
        var d=TvCampaignSavedData.get(l);
        var sortie=d.sorties.get(eva.getUnitVariant());
        return loan.chapter.equals("ramiel")&&loan.episode.equals(EPISODE)&&loan.dimension.equals(l.dimension().location().toString())
                &&loan.generation==d.generationR43&&loan.owner.equals(d.owner)&&loan.eva.equals(eva.getUUID())
                &&loan.unit==eva.getUnitVariant()&&loan.pilot!=null&&sortie!=null&&loan.pilot.equals(sortie.pilotR45)
                &&cargoUnit(ItemStack.of(loan.item))==loan.unit;
    }
    private static Loan loanFor(State state,EvaUnit01Entity eva)
    {
        for(var loan:state.loans.values())if(loan.eva.equals(eva.getUUID())&&!loan.status.equals(STORED))return loan;
        return null;
    }
    /** Read during real Entity NBT load; requires original persisted fleet UUID. */
    public static boolean cannonAuthorized(EvaUnit01Entity eva)
    {return authorized(eva,1);}
    public static boolean shieldAuthorized(EvaUnit01Entity eva)
    {return authorized(eva,0);}
    private static boolean authorized(EvaUnit01Entity eva,int unit)
    {
        if(!(eva.level() instanceof ServerLevel l)||eva.getUnitVariant()!=unit)return false;
        var loan=loanFor(state(l),eva);return loan!=null&&live(loan,l,eva);
    }
    public static boolean operational(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l)||!context(l,eva)||TvCampaignSavedData.get(l).phase.equals("failure"))return false;
        var sortie=TvCampaignSavedData.get(l).sorties.get(eva.getUnitVariant());var pilot=eva.getPilotEntity();
        return sortie!=null&&sortie.pilotR45!=null&&pilot!=null&&pilot.isAlive()&&sortie.pilotR45.equals(pilot.getUUID());
    }
    public static int restoreCannonMask(EvaUnit01Entity eva,int ordinaryMask)
    {return cannonAuthorized(eva)?ordinaryMask|(1<<EvaUnit01Entity.WEAPON_CANNON):ordinaryMask&~(1<<EvaUnit01Entity.WEAPON_CANNON);}

    private static boolean withinReach(NervArmamentStationEntity station,EvaUnit01Entity eva)
    {
        return station.position().subtract(eva.position()).horizontalDistance()<=NervArmamentStationEntity.EVA_PICKUP_RANGE
                &&station.getBoundingBox().maxY>=eva.getBoundingBox().minY-4
                &&station.getBoundingBox().minY<=eva.getBoundingBox().maxY+4;
    }
    /** Rack purpose outlives its cargo: an empty mission rack cannot refill rifles. */
    public static boolean missionRack(NervArmamentStationEntity station)
    {return station.getPersistentData().contains(RACK_UNIT,Tag.TAG_INT)||station.getPersistentData().contains(CARGO,Tag.TAG_COMPOUND);}
    public static boolean physicalStockPresent(NervArmamentStationEntity station)
    {
        var slot=station.getPersistentData();
        int unit=cargoUnit(ItemStack.of(slot.getCompound(CARGO)));
        return station.level() instanceof ServerLevel l&&slot.hasUUID(CARGO_ID)&&slot.contains(CARGO,Tag.TAG_COMPOUND)&&unit>=0
                &&(!slot.contains(RACK_UNIT,Tag.TAG_INT)||slot.getInt(RACK_UNIT)==unit)
                &&rackOwns(state(l),station,slot.getUUID(CARGO_ID),slot.getCompound(CARGO));
    }
    public static NervArmamentStationEntity nearestPhysicalCargo(ServerLevel l,EvaUnit01Entity eva)
    {
        return l.getEntitiesOfClass(NervArmamentStationEntity.class,eva.getBoundingBox().inflate(256),s->stockedFor(s,eva)
                &&s.getBoundingBox().maxY>=eva.getBoundingBox().minY-4&&s.getBoundingBox().minY<=eva.getBoundingBox().maxY+4)
                .stream().min(java.util.Comparator.comparingDouble(s->s.distanceToSqr(eva))).orElse(null);
    }
    /** Real player's held item moves into an EMPTY physical rack, never copied. */
    public static boolean deliverHeldCargo(NervArmamentStationEntity station,ServerPlayer player,InteractionHand hand)
    {
        if(!(station.level() instanceof ServerLevel l)||player.level()!=l||!NervStaffDialogue.authorized(player)
                ||player.distanceToSqr(station)>36||station.isStocked()
                ||!(station.getStationState()==NervArmamentStationEntity.STOWED||station.getStationState()==NervArmamentStationEntity.EMPTY))return false;
        var slot=station.getPersistentData();if(slot.contains(CARGO)||slot.hasUUID(CARGO_ID))return false;
        var held=player.getItemInHand(hand);int unit=cargoUnit(held);if(unit<0)return false;
        if(slot.contains(RACK_UNIT,Tag.TAG_INT)&&slot.getInt(RACK_UNIT)!=unit)return false;
        var state=state(l);var carriedTag=held.getTag();
        UUID cargo=carriedTag!=null&&carriedTag.hasUUID(CARGO_ID)?carriedTag.getUUID(CARGO_ID):UUID.randomUUID();
        var prior=state.physical.get(cargo);var loan=state.loans.get(cargo);
        if(carriedTag!=null&&carriedTag.hasUUID(CARGO_ID)
                &&(prior==null||!player.getUUID().equals(prior.carrier)||prior.rack!=null||!prior.item.equals(held.save(new CompoundTag()))))return false;
        if(loan!=null&&!loan.status.equals(STORED))return false;
        var exact=held.copy();exact.setCount(1);exact.getOrCreateTag().putUUID(CARGO_ID,cargo);
        var physical=prior==null?new PhysicalStock():prior;physical.cargo=cargo;physical.rack=station.getUUID();physical.carrier=null;
        physical.position=station.blockPosition();
        physical.item=exact.save(new CompoundTag());state.physical.put(cargo,physical);
        if(loan!=null){loan.source=station.getUUID();loan.item=physical.item.copy();}
        slot.putInt(RACK_UNIT,unit);slot.putUUID(CARGO_ID,cargo);slot.put(CARGO,physical.item.copy());held.shrink(1);state.setDirty();return true;
    }
    /** Original stack goes into the ground crew's empty hand for physical travel between floors. */
    public static boolean collectStoredCargo(NervArmamentStationEntity station,ServerPlayer player,InteractionHand hand)
    {
        if(!(station.level() instanceof ServerLevel l)||player.level()!=l||!NervStaffDialogue.authorized(player)
                ||player.distanceToSqr(station)>36||!player.getItemInHand(hand).isEmpty()||!missionRack(station)
                ||!physicalStockPresent(station))return false;
        var slot=station.getPersistentData();var state=state(l);var cargo=slot.getUUID(CARGO_ID);var item=slot.getCompound(CARGO).copy();
        var loan=state.loans.get(cargo);if(loan!=null&&!loan.status.equals(STORED))return false;
        var stack=ItemStack.of(item);var identity=stack.getTag();
        if(identity==null||!identity.hasUUID(CARGO_ID)||!identity.getUUID(CARGO_ID).equals(cargo))return false;
        var stock=state.physical.get(cargo);if(stock==null)return false;
        stock.rack=null;stock.carrier=player.getUUID();stock.position=null;slot.remove(CARGO);slot.remove(CARGO_ID);
        player.setItemInHand(hand,stack);state.setDirty();return true;
    }
    private static boolean assignedPilot(ServerLevel l,EvaUnit01Entity eva,LivingEntity pilot)
    {
        if(pilot==null||pilot.level()!=l||eva.getPilotEntity()!=pilot)return false;
        var s=TvCampaignSavedData.get(l).sorties.get(eva.getUnitVariant());if(s==null)return false;
        return s.pilotR45!=null&&s.pilotR45.equals(pilot.getUUID())
                &&(pilot instanceof TrainingPilotEntity npc?s.npc&&npc.getAssignedVariant()==eva.getUnitVariant()
                :pilot instanceof ServerPlayer player&&!s.npc&&s.commander.equals(player.getUUID()));
    }
    /** Called only by root's physical station handoff, after the rack is READY. */
    public static boolean issueFromStation(NervArmamentStationEntity station,EvaUnit01Entity eva,LivingEntity pilot)
    {
        if(!(station.level() instanceof ServerLevel l)||!context(l,eva)||!operational(eva)||!assignedPilot(l,eva,pilot)
                ||!station.isReadyAndStocked()||!withinReach(station,eva))return false;
        var stock=station.getPersistentData();if(!stock.hasUUID(CARGO_ID)||!stock.contains(CARGO,Tag.TAG_COMPOUND))return false;
        var cargo=stock.getUUID(CARGO_ID);var item=stock.getCompound(CARGO).copy();if(cargoUnit(ItemStack.of(item))!=eva.getUnitVariant())return false;
        if(stock.contains(RACK_UNIT,Tag.TAG_INT)&&stock.getInt(RACK_UNIT)!=eva.getUnitVariant())return false;
        var state=state(l);var old=state.loans.get(cargo);
        // A stale duplicated rack snapshot cannot issue an already borrowed ID.
        if(!rackOwns(state,station,cargo,item)||old!=null&&(!old.status.equals(STORED)||!old.item.equals(item)))return false;
        if(loanFor(state,eva)!=null)return false;
        var d=TvCampaignSavedData.get(l);var loan=new Loan();loan.cargo=cargo;loan.source=station.getUUID();
        loan.eva=eva.getUUID();loan.owner=d.owner;loan.generation=d.generationR43;loan.unit=eva.getUnitVariant();
        loan.dimension=l.dimension().location().toString();loan.item=item;loan.pilot=pilot.getUUID();
        state.loans.put(cargo,loan);var physical=state.physical.get(cargo);
        if(physical!=null){physical.rack=null;physical.carrier=null;physical.position=null;}
        state.setDirty();stock.putInt(RACK_UNIT,loan.unit);stock.remove(CARGO);stock.remove(CARGO_ID);return true;
    }
    /** Existing physical cargo only; no fallback factory or default mission kit. */
    public static boolean stockedFor(NervArmamentStationEntity station,EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l)||station.level()!=l||!context(l,eva))return false;
        var tag=station.getPersistentData();return physicalStockPresent(station)
                &&(!tag.contains(RACK_UNIT,Tag.TAG_INT)||tag.getInt(RACK_UNIT)==eva.getUnitVariant())
                &&cargoUnit(ItemStack.of(tag.getCompound(CARGO)))==eva.getUnitVariant();
    }
    public static void revokeMission(ServerLevel l)
    {
        var d=TvCampaignSavedData.get(l);var state=state(l);
        for(var loan:state.loans.values())if(loan.status.equals(LOANED)&&loan.owner.equals(d.owner)
                &&loan.generation==d.generationR43&&loan.chapter.equals(d.active))loan.status=RETURN_PENDING;
        state.setDirty();
    }
    /** Reconciliation caller keeps complete original cargo pending while revoked. */
    public static void reconcile(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l))return;
        var state=state(l);var loan=loanFor(state,eva);if(loan==null||!loan.status.equals(LOANED))return;
        // Initial staging can be PARKED; only RETURNING transitions/recovery
        // revoke at root's explicit physical recovery-completed hook below.
        if(!live(loan,l,eva)){loan.status=RETURN_PENDING;state.setDirty();}
    }
    /** Root's actual completed original-airframe recovery calls this. */
    public static void recoveryCompleted(EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l))return;
        var fleet=EvaFleetSavedData.get(l.getServer()).entry(eva.getUnitVariant()).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(eva.getUUID())||fleet.phase()!=EvaFleetSavedData.Phase.PARKED)return;
        var state=state(l);var loan=loanFor(state,eva);if(loan!=null&&loan.status.equals(LOANED))
        {loan.status=RETURN_PENDING;state.setDirty();}
    }
    /** Original cargo returns to a real EMPTY rack exactly once after recovery. */
    public static boolean returnToStation(NervArmamentStationEntity station,EvaUnit01Entity eva)
    {
        if(!(eva.level() instanceof ServerLevel l)||station.level()!=l||station.isStocked()
                ||!withinReach(station,eva)
                ||!(station.getStationState()==NervArmamentStationEntity.STOWED
                ||station.getStationState()==NervArmamentStationEntity.EMPTY
                ||station.getStationState()==NervArmamentStationEntity.READY))return false;
        var fleet=EvaFleetSavedData.get(l.getServer()).entry(eva.getUnitVariant()).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(eva.getUUID())||fleet.phase()!=EvaFleetSavedData.Phase.PARKED)return false;
        var state=state(l);var loan=loanFor(state,eva);var slot=station.getPersistentData();
        if(loan==null||!loan.status.equals(RETURN_PENDING)||slot.contains(CARGO)||slot.hasUUID(CARGO_ID))return false;
        if(!slot.contains(RACK_UNIT,Tag.TAG_INT)||slot.getInt(RACK_UNIT)!=loan.unit)return false;
        // No item reconstruction, count change, generic replenishment or new ID.
        slot.put(CARGO,loan.item.copy());slot.putUUID(CARGO_ID,loan.cargo);loan.status=STORED;loan.source=station.getUUID();
        var stock=state.physical.get(loan.cargo);if(stock==null){stock=new PhysicalStock();stock.cargo=loan.cargo;state.physical.put(loan.cargo,stock);}
        stock.item=loan.item.copy();stock.rack=station.getUUID();stock.carrier=null;stock.position=station.blockPosition();state.setDirty();return true;
    }
    /** Recovered pilots are out of the plug; authorized ground crews can return the original cargo. */
    public static boolean returnNearbyCargo(NervArmamentStationEntity station,ServerPlayer player)
    {
        if(!(station.level() instanceof ServerLevel l)||player.level()!=l||!NervStaffDialogue.authorized(player)
                ||player.distanceToSqr(station)>36||!missionRack(station))return false;
        for(var loan:state(l).loans.values())
        {
            if(!loan.status.equals(RETURN_PENDING))continue;
            var eva=TvSortiesR32.unit(l,loan.unit);
            if(eva!=null&&eva.getUUID().equals(loan.eva)&&returnToStation(station,eva))return true;
        }
        return false;
    }
    /** Every original loan must be physically in its recorded real rack, never merely on a carrier or marked stored. */
    public static boolean missionEquipmentReturned(ServerLevel level,UUID commander,long generation,String chapter)
    {
        var state=state(level);
        for(var loan:state.loans.values())
        {
            if(!loan.owner.equals(commander)||loan.generation!=generation||!loan.chapter.equals(chapter))continue;
            if(!loan.status.equals(STORED))return false;
            var stock=state.physical.get(loan.cargo);
            if(stock==null||stock.rack==null||stock.carrier!=null||!stock.item.equals(loan.item))return false;
            if(stock.position!=null)NervArmamentStationEntity.keepCommandStationLoaded(level,stock.position);
            if(!(level.getEntity(stock.rack) instanceof NervArmamentStationEntity rack)||!physicalStockPresent(rack))return false;
            var slot=rack.getPersistentData();
            if(!slot.hasUUID(CARGO_ID)||!loan.cargo.equals(slot.getUUID(CARGO_ID))||!loan.item.equals(slot.getCompound(CARGO)))return false;
        }return true;
    }
    private TvMissionEquipmentR45(){}
}
