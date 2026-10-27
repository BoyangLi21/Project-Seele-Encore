package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;
import java.util.function.Consumer;
import java.util.function.Supplier;

/** Explicit operator recovery of named personnel; ordinary ticks never replace NPCs. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervNpcResetR53
{
    public record Target(UUID uuid,String id,EntityType<? extends PathfinderMob> type,Vec3 home,float yaw,
                         Supplier<String> busy,Consumer<PathfinderMob> restore) { }
    private static final class Batch
    {
        final boolean all; int remaining,success;
        Batch(boolean all){this.all=all;}
    }
    private static final class Pending
    {
        final ServerLevel level; final Target target; final CommandSourceStack source; final Batch batch;
        long started=-1;
        Pending(ServerLevel level,Target target,CommandSourceStack source,Batch batch)
        {this.level=level;this.target=target;this.source=source;this.batch=batch;}
        ServerLevel level(){return level;} Target target(){return target;} CommandSourceStack source(){return source;}
        long started(){return started;}
    }
    private static final Map<UUID,Pending> PENDING=new LinkedHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_npc_reset",Comparator.comparingLong(ChunkPos::toLong),100);

    @SubscribeEvent public static void stopped(ServerStoppedEvent event)
    {PENDING.values().removeIf(p->p.level().getServer()==event.getServer());}

    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("npc").requires(s->s.hasPermission(2))
                .then(Commands.literal("reset").then(Commands.argument("target",StringArgumentType.word())
                        .suggests((c,b)->net.minecraft.commands.SharedSuggestionProvider.suggest(List.of("all","fuyutsuki","misato","ritsuko","rei","shinji","asuka"),b))
                        .executes(c->request(c.getSource(),StringArgumentType.getString(c,"target")))))));
    }
    private static int request(CommandSourceStack source,String id)
    {
        int count=0;var batch=new Batch(id.equals("all"));
        for(var level:source.getServer().getAllLevels())
        {
            if(!(NervRouteRuntimeR52.originalActorAccess(level) instanceof NervAssemblyOwnerR52 owner))continue;
            for(var target:owner.npcResetTargetsR53(level))
            {
                if(!id.equals("all")&&!target.id().equals(id))continue;
                if(PENDING.containsKey(target.uuid()))continue;
                PENDING.put(target.uuid(),new Pending(level,target,source,batch));count++;
            }
        }
        batch.remaining=count;final int queued=count;
        if(count==0)source.sendFailure(Component.literal("没有匹配的已登记 NPC，或重置已经在进行。"));
        else source.sendSuccess(()->Component.literal("正在恢复 "+queued+" 个已登记 NPC；分批恢复岗位区块，完成后汇总。"),false);
        return count;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||PENDING.isEmpty())return;
        int budget=4;
        for(var iterator=PENDING.values().iterator();iterator.hasNext()&&budget>0;)
        {
            var pending=iterator.next();var level=pending.level();
            if(level.getServer()!=event.getServer())continue;
            budget--;
            var target=pending.target();var chunk=new ChunkPos(BlockPos.containing(target.home()));
            if(pending.started<0)
            {
                pending.started=level.getGameTime();
                level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);
            }
            if(!level.areEntitiesLoaded(chunk.toLong()))
            {
                if(level.getGameTime()-pending.started()<80)continue;
                pending.source().sendFailure(Component.literal(target.id()+"：岗位区块尚未加载，未生成替身，请稍后重试。"));
            }
            else
            {
                String busy=target.busy().get();
                if(!busy.isEmpty())pending.source().sendFailure(Component.literal(target.id()+"："+busy));
                else
                {
                    var existing=level.getEntity(target.uuid());
                    if(existing!=null&&existing.getType()!=target.type())
                        pending.source().sendFailure(Component.literal(target.id()+"：登记身份对应了其他实体类型，未覆盖。"));
                    else
                    {
                        PathfinderMob npc=existing instanceof PathfinderMob mob?mob:target.type().create(level);
                        if(npc!=null)
                        {
                            if(existing==null)npc.setUUID(target.uuid());
                            npc.stopRiding();npc.getNavigation().stop();npc.setTarget(null);npc.setNoAi(false);
                            npc.setHealth(npc.getMaxHealth());npc.deathTime=0;npc.hurtTime=0;npc.clearFire();npc.removeAllEffects();
                            npc.setInvulnerable(true);npc.setPersistenceRequired();npc.setDeltaMovement(Vec3.ZERO);
                            npc.moveTo(target.home().x,target.home().y,target.home().z,target.yaw(),0);
                            npc.yBodyRot=target.yaw();npc.setYHeadRot(target.yaw());target.restore().accept(npc);
                            boolean success=existing!=null||level.addFreshEntity(npc);
                            if(success)
                            {
                                pending.batch.success++;
                                if(!pending.batch.all)pending.source().sendSuccess(()->Component.literal(target.id()+"：已恢复原身份、生命和岗位。"),false);
                            }
                            else pending.source().sendFailure(Component.literal(target.id()+"：实体添加失败，未报告成功。"));
                        }
                        else pending.source().sendFailure(Component.literal(target.id()+"：实体类型创建失败，未报告成功。"));
                    }
                }
            }
            level.getChunkSource().removeRegionTicket(TICKET,chunk,2,chunk);iterator.remove();
            if(--pending.batch.remaining==0&&pending.batch.all)
                pending.source().sendSuccess(()->Component.literal("NPC 批量复位结束：已恢复 "+pending.batch.success+" 个；未恢复的原因已单独显示。"),false);
        }
    }
    private NervNpcResetR53() { }
}
