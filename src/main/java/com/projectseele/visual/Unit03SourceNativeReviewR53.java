package com.projectseele.visual;

import com.mojang.brigadier.arguments.StringArgumentType;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.coordinates.Vec3Argument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;

/** Explicit isolated-world actor; no player teleport, original actor lookup or world construction. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class Unit03SourceNativeReviewR53
{
    private static final String TAG="seele_unit03_fixed_review_r53";
    private static Unit03ReviewContractR53.Contract safe(MinecraftServer server)
    {
        var c=Unit03ReviewContractR53.current();
        if(c==null||!server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize().equals(c.world()))
            throw new IllegalStateException("Unit03 review refuses every world except its isolated review path");
        return c;
    }
    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        if(!Unit03ReviewContractR53.requested())return;
        Unit03ReviewContractR53.current();
        event.getDispatcher().register(Commands.literal("seele").then(Commands.literal("unit03_review").requires(s->s.hasPermission(4))
                .then(Commands.literal("spawn").then(Commands.argument("pose",StringArgumentType.word())
                        .then(Commands.argument("position",Vec3Argument.vec3()).executes(c->spawn(c.getSource().getLevel(),
                                StringArgumentType.getString(c,"pose"),Vec3Argument.getVec3(c,"position"))))))
                .then(Commands.literal("pose").then(Commands.argument("pose",StringArgumentType.word())
                        .executes(c->pose(c.getSource().getLevel(),StringArgumentType.getString(c,"pose")))))
                .then(Commands.literal("finish").executes(c->finish(c.getSource().getLevel())))));
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.EntityInteract event)
    {
        if(Unit03ReviewContractR53.actor(event.getTarget().getUUID()))
        {event.setCanceled(true);event.setCancellationResult(net.minecraft.world.InteractionResult.FAIL);}
    }
    private static EvaPrototypeEntity actor(ServerLevel level)
    {
        var c=safe(level.getServer());var e=level.getEntity(c.actor());
        if(!(e instanceof EvaPrototypeEntity un)||un.getUNSerial()!=1||!e.getTags().contains(TAG))
            throw new IllegalStateException("No owned Unit03 review actor; original actors are never substituted");
        return un;
    }
    private static int spawn(ServerLevel level,String name,Vec3 position)
    {
        var c=safe(level.getServer());
        if(!level.dimension().equals(net.minecraft.world.level.Level.OVERWORLD))
            throw new IllegalStateException("Review actor is restricted to the isolated overworld, outside facility directors");
        if(!c.poses().has(name))throw new IllegalArgumentException("Unadmitted keypose "+name);
        for(var other:level.getServer().getAllLevels())if(other.getEntity(c.actor())!=null)
            throw new IllegalStateException("Review actor already exists; use pose or finish");
        if(!level.hasChunkAt(net.minecraft.core.BlockPos.containing(position)))
            throw new IllegalStateException("Review position must already be loaded");
        var e=ModEntities.EVA_PROTOTYPE.get().create(level);
        if(e==null)throw new IllegalStateException("Review actor factory");
        e.setUUID(c.actor());e.setUNSerial(1);e.addTag(TAG);e.setNoAi(true);e.setNoGravity(true);e.setInvulnerable(true);
        e.setPersistenceRequired();e.setCustomName(Component.literal("UNIT-03 / FIXED KEYPOSE REVIEW"));
        e.moveTo(position.x,position.y,position.z,0,0);freeze(e,name);
        if(!level.addFreshEntity(e))throw new IllegalStateException("Review actor rejected");
        receipt(c,"spawn",name);return 1;
    }
    private static int pose(ServerLevel level,String name)
    {var e=actor(level);freeze(e,name);receipt(safe(level.getServer()),"pose",name);return 1;}
    private static void freeze(EvaPrototypeEntity e,String name)
    {
        var c=safe(e.getServer());var row=c.poses().getAsJsonObject(name);
        if(row==null)throw new IllegalArgumentException("Unadmitted keypose "+name);
        if(!e.getPassengers().isEmpty())throw new IllegalStateException("Fixed review actor cannot carry passengers");
        var sample=EvaBodyPose.neutralForTransportR32(e);
        if(!sample.rig.keySet().equals(row.keySet()))throw new IllegalStateException("Loaded review rig differs from contract");
        for(var entry:row.entrySet())
        {
            var p=entry.getValue().getAsJsonObject();var q=p.getAsJsonArray("rotation_xyzw");var v=p.getAsJsonArray("position");
            sample.rotations.put(entry.getKey(),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()));
            sample.positions.put(entry.getKey(),new Vector3f(v.get(0).getAsFloat(),v.get(1).getAsFloat(),v.get(2).getAsFloat()));
        }
        var frozen=EvaShutdownR30.encode(sample);if(!EvaShutdownR30.valid(frozen))throw new IllegalStateException("Review pose codec rejected");
        var tag=new CompoundTag();tag.putInt("R30Shutdown",EvaShutdownR30.EMPTY);tag.putLong("R30ShutdownSince",e.level().getGameTime());
        tag.put("R30FrozenPose",frozen);tag.put("R30ShutdownOrigin",frozen.copy());EvaShutdownR30.load(e,tag);
        e.getPersistentData().putBoolean("R30FrozenPoseConfirmed",true);e.setDeltaMovement(Vec3.ZERO);e.setTarget(null);e.getNavigation().stop();
    }
    private static int finish(ServerLevel level)
    {var e=actor(level);if(!e.getPassengers().isEmpty())throw new IllegalStateException("Passenger present; refusing removal");e.discard();receipt(safe(level.getServer()),"finish","");return 1;}
    private static void receipt(Unit03ReviewContractR53.Contract c,String action,String pose)
    {
        var row=new com.google.gson.JsonObject();row.addProperty("action",action);row.addProperty("pose",pose);
        row.addProperty("actor",c.actor().toString());row.addProperty("review_contract",c.fingerprint());row.addProperty("gameplay_admitted",false);
        try{Files.writeString(c.directory().resolve("native-command-receipts.jsonl"),row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        catch(Exception failure){throw new IllegalStateException("Cannot preserve Unit03 review receipt",failure);}
    }
    private Unit03SourceNativeReviewR53(){}
}
