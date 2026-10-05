package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.Optional;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Destruction is an explicit authority event, never inferred from an unloaded UUID. */
public final class EntryPlugDisposalR31
{
    public static final class Ledger extends SavedData
    {
        private final Map<UUID,CompoundTag> destroyed=new HashMap<>();
        static Ledger load(CompoundTag tag)
        {
            Ledger ledger=new Ledger();
            for(String key:tag.getAllKeys())try{ledger.destroyed.put(UUID.fromString(key),tag.getCompound(key).copy());}catch(IllegalArgumentException ignored){}
            return ledger;
        }
        @Override public CompoundTag save(CompoundTag tag){destroyed.forEach((id,entry)->tag.put(id.toString(),entry.copy()));return tag;}
    }
    private static Ledger ledger(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(Ledger::load,Ledger::new,"projectseele_destroyed_entry_plugs_r31");}

    public static boolean destroyed(ServerLevel level,UUID id)
    {return id!=null&&ledger(level).destroyed.containsKey(id);}

    public static boolean replacementAuthorized(EvaPrototypeEntity eva)
    {
        var data=eva.getPersistentData();
        if(!(eva.level() instanceof ServerLevel level)||!data.hasUUID("UNPlug"))return false;
        CompoundTag entry=ledger(level).destroyed.get(data.getUUID("UNPlug"));
        return entry!=null&&entry.getBoolean("IndependentUN")
                &&(!entry.hasUUID("Owner")||entry.getUUID("Owner").equals(eva.getUUID()));
    }

    public static Optional<Vec3> hit(Player player,EntryPlugCarrierEntity plug)
    {
        if(plug.laboratorySlotR47()>=0||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_FIELD_LANDED||plug.isVehicle()||plug.isPassenger()||plug.isRemoved())return Optional.empty();
        Vec3 start=player.getEyePosition(),end=start.add(player.getLookAngle().scale(player.isCreative()?5:3));
        var pose=plug.getCanonicalTransform();var inverse=pose.inverse();
        var centre=EntryPlugKinematics.BODY_OBB_CENTRE_P;var half=EntryPlugKinematics.BODY_OBB_HALF_EXTENTS;
        var box=new AABB(centre.subtract(half),centre.add(half));
        var local=box.clip(inverse.transformPoint(start),inverse.transformPoint(end));
        if(local.isEmpty())return Optional.empty();
        Vec3 point=pose.transformPoint(local.get());
        var block=player.level().clip(new ClipContext(start,point,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,player));
        if(block.getLocation().distanceToSqr(start)+.0025<point.distanceToSqr(start))return Optional.empty();
        return Optional.of(point);
    }

    public static boolean destroyLanded(EntryPlugCarrierEntity plug)
    {
        if(plug.laboratorySlotR47()>=0||!(plug.level() instanceof ServerLevel level)||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_FIELD_LANDED
                ||plug.isVehicle()||plug.isPassenger()||plug.isRemoved())return false;
        var ledger=ledger(level);CompoundTag receipt=new CompoundTag();
        receipt.putBoolean("IndependentUN",plug.isIndependentUNPlug());receipt.putInt("Variant",plug.getAssignedVariant());
        receipt.putLong("DestroyedAt",level.getGameTime());receipt.putLong("Position",plug.blockPosition().asLong());
        UUID host=plug.getHostEvaUuid();if(host!=null)receipt.putUUID("Owner",host);
        ledger.destroyed.put(plug.getUUID(),receipt);ledger.setDirty();
        EvaUnit01Entity linked=plug.getLinkedEva();if(linked!=null)linked.clearEntryPlugLink(plug);
        if(!plug.isIndependentUNPlug())
        {
            var fleet=EvaFleetSavedData.get(level.getServer());var entry=fleet.entry(plug.getAssignedVariant()).orElse(null);
            if(entry!=null&&plug.getUUID().equals(entry.entryPlugId()))fleet.put(plug.getAssignedVariant(),entry.withEntryPlug(null));
        }
        var p=plug.getCanonicalTransform().translation();
        level.sendParticles(ParticleTypes.SMOKE,p.x,p.y+1,p.z,16,1.2,.4,1.2,.025);
        level.sendParticles(ParticleTypes.ELECTRIC_SPARK,p.x,p.y+1,p.z,12,.8,.4,.8,.05);
        level.playSound(null,p.x,p.y,p.z,SoundEvents.IRON_GOLEM_DAMAGE,SoundSource.BLOCKS,1.5F,.7F);
        ProjectSeele.LOGGER.info("Landed entry plug destroyed: plug={} independentUN={} owner={}",plug.getUUID(),plug.isIndependentUNPlug(),host);
        plug.discard();return true;
    }
    private EntryPlugDisposalR31() {}
}
