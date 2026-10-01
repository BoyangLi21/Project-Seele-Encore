package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.event.entity.living.LivingDamageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.fml.common.Mod;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.*;

/** Observe real backend events; visual contact is reported by a separate draw witness. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SharedCombatHitWitnessR44
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44SharedContactWitness");
    private static int count;
    @SubscribeEvent(priority=EventPriority.LOWEST,receiveCanceled=true)
    public static void attempted(LivingAttackEvent event)
    {record(event.getEntity(),event.getSource(),event.getAmount(),event.isCanceled(),"actual_living_attack_event");}
    @SubscribeEvent(priority=EventPriority.LOWEST,receiveCanceled=true)
    public static void damaged(LivingDamageEvent event)
    {record(event.getEntity(),event.getSource(),event.getAmount(),event.isCanceled(),"actual_living_damage_event_final_amount");}
    private static void record(net.minecraft.world.entity.LivingEntity entity,net.minecraft.world.damagesource.DamageSource source,float amount,boolean canceled,String kind)
    {
        if(!ENABLED||!CombatR31Review.ENABLED||entity.level().isClientSide||count>=2048
                ||entity.getId()!=CombatR31Review.evaId&&entity.getId()!=CombatR31Review.angelId)return;
        JsonObject row=new JsonObject();row.addProperty("kind",kind);row.addProperty("world_tick",entity.level().getGameTime());row.addProperty("review_stage",CombatR31Review.stageName);row.addProperty("review_tick",CombatR31Review.stageTicks);
        row.addProperty("target_uuid",entity.getStringUUID());row.addProperty("target_entity_id",entity.getId());row.addProperty("target_world_yaw",entity.getYRot());row.addProperty("damage_type",source.getMsgId());row.addProperty("amount",amount);row.addProperty("canceled",canceled);row.addProperty("health_at_event",entity.getHealth());
        var direct=source.getDirectEntity();var causing=source.getEntity();if(direct!=null)row.addProperty("direct_entity_uuid",direct.getStringUUID());if(causing!=null)row.addProperty("causing_entity_uuid",causing.getStringUUID());
        row.addProperty("scope","Actual Forge backend event and source; final LivingDamage amount is observed before health update. No visible hand/surface contact or exact hit location inferred.");
        try{Path file=entity.getServer().getWorldPath(LevelResource.ROOT).resolve("shared_backend_hits_r44.jsonl");Files.writeString(file,row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);count++;}
        catch(Exception error){throw new IllegalStateException("Shared backend contact witness write failed",error);}
    }
    private SharedCombatHitWitnessR44(){}
}
