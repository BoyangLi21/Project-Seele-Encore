package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.network.*;
import com.projectseele.registry.ModItems;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import java.util.*;

/** UN authority is carried by the UN handset or the actual UN pilot, not NERV staff roles. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class UNCommandR29
{
    private static final Map<ServerPlayer,Integer> LAST=new WeakHashMap<>();
    private static final Map<ServerPlayer,Integer> LAST_QUERY=new WeakHashMap<>();
    private static final TicketType<ChunkPos> RADIO=TicketType.create("seele_un_radio",Comparator.comparingLong(ChunkPos::toLong),100);
    public static boolean authorized(ServerPlayer p)
    {
        return p.hasPermissions(2)||EvaPilotResolver.controlTarget(p) instanceof EvaPrototypeEntity
                ||p.getInventory().items.stream().anyMatch(s->s.is(ModItems.UN_SATELLITE_PHONE.get()))||p.getOffhandItem().is(ModItems.UN_SATELLITE_PHONE.get());
    }
    private static EvaPrototypeEntity unit(ServerLevel l,int serial)
    {
        UUID id=UNRecoveryR22.identity(l,serial);if(id==null)return null;
        BlockPos pos=UNRecoveryR22.lastKnownPosition(l,id);if(pos==null)pos=BlockPos.containing(UNRecoveryR22.home(l,serial));
        var chunk=new ChunkPos(pos);l.getChunkSource().addRegionTicket(RADIO,chunk,3,chunk);l.getChunkSource().getChunkFuture(chunk.x,chunk.z,ChunkStatus.FULL,true);
        if(l.getEntity(id) instanceof EvaPrototypeEntity eva)
        {
            var t=eva.getPersistentData();if(t.hasUUID("UNPlug")){var pp=UNRecoveryR22.lastKnownPosition(l,t.getUUID("UNPlug"));if(pp!=null){var c=new ChunkPos(pp);l.getChunkSource().addRegionTicket(RADIO,c,3,c);l.getChunkSource().getChunkFuture(c.x,c.z,ChunkStatus.FULL,true);}}
            return eva;
        }
        return null;
    }
    public static String status(ServerLevel l,int serial)
    {
        var eva=unit(l,serial);
        return Unit03SourceRigR53.displayName(serial)+" · 核能 · "+(eva==null?"远端信号接入中":eva.isUNFlying()?(eva.isUNLanding()?"自动降落":"飞行中"):eva.getPilotEntity()==null?"无人驾驶":"驾驶员已接入")+"\n"+UNAirLiftR29.status(l,serial);
    }
    private static String board(ServerPlayer p,int serial)
    {
        var l=p.serverLevel();var eva=unit(l,serial);if(eva==null)return "正在加载原机体，请稍后重试。";
        if(p.isPassenger())return "你已经在载具内，请先离开当前座舱。";
        if(UNAirLiftR29.ownsMotion(l,serial)||eva.isUNFlying()||eva.isNervLogisticsLocked())return "请等机体落地、夹具释放，并确认舱门已开启后再接入。";
        if(p.distanceToSqr(eva)>90*90)return "请先走到这台 UN EVA 附近，再请求接入。";
        var plug=UNPlugDirector.capsule(eva);if(plug==null)return "原插入栓仍在加载，没有生成替代插入栓。";
        if(plug.isVehicle()||eva.getPilotEntity()!=null)return "驾驶舱已有乘员。";
        if(plug.isLockedToEva())
        {
            if(!p.startRiding(plug,true)||!eva.bindEntryPlug(plug,70)){p.stopRiding();return "驾驶连接未被接受。";}
            plug.syncPilotPositionNow();l.getChunkSource().move(p);return "已接入原插入栓，正在完成同步。";
        }
        return plug.boardPassenger(p)?"已进入原插入栓，等待正常吊机接入。":"插入栓当前不可登机。";
    }
    public static void receive(ServerPlayer p,String action,int serial,int x,int z)
    {
        if(serial<0||serial>1||!authorized(p))return;
        if(!p.serverLevel().dimension().equals(FacilitySchemaV2.DIMENSION)){p.sendSystemMessage(Component.literal("请进入第三新东京市所在的项目世界后使用 UN 通信。"));return;}
        int tick=p.server.getTickCount();
        if(action.equals("status"))
        {
            if(tick-LAST_QUERY.getOrDefault(p,-100)<10)return;
            LAST_QUERY.put(p,tick);
        }
        if(!action.equals("status")&&!action.equals("open"))
        {
            if(tick-LAST.getOrDefault(p,-100)<4)return;
            LAST.put(p,tick);
        }
        var l=p.serverLevel();String reply="";
        switch(action)
        {
            case "open" -> reply="选择机体并填写投放 X、Z。运输机会寻找该位置附近可承载机体的地面。";
            case "status" -> {}
            case "deliver" -> reply=UNAirLiftR29.request(p,serial,false,x,z);
            case "recover" -> reply=UNAirLiftR29.request(p,serial,true,x,z);
            case "dock" -> reply=UNAirLiftR29.requestDock(p,serial);
            case "cancel" -> reply=UNAirLiftR29.cancel(p,serial);
            case "board" -> reply=board(p,serial);
            case "drain","door","fill" ->
            {
                unit(l,serial);
                reply=UNAirLiftR29.active(l,serial)?"运输任务正在使用机库，请先完成或取消运输。":serial==0?MilitaryR07Director.request(l,action,null):UNAnnexR20.request(l,action,null);
            }
            default -> {return;}
        }
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(()->p),new ClientboundUNStatusPacket(action.equals("open"),status(l,0),status(l,1),reply));
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        var root=Commands.literal("un").requires(s->s.getEntity() instanceof ServerPlayer p&&authorized(p));
        root.then(Commands.literal("phone").executes(c->{receive(c.getSource().getPlayerOrException(),"open",0,0,0);return 1;}));
        root.then(Commands.literal("status").executes(c->{var p=c.getSource().getPlayerOrException();p.sendSystemMessage(Component.literal(status(p.serverLevel(),0)+"\n"+status(p.serverLevel(),1)));return 1;}));
        var deliver=Commands.literal("deliver");
        for(int i=0;i<2;i++)
        {
            int serial=i;
            deliver.then(Commands.literal("0"+i).then(Commands.argument("x",IntegerArgumentType.integer(-29999000,29999000)).then(Commands.argument("z",IntegerArgumentType.integer(-29999000,29999000)).executes(c->{receive(c.getSource().getPlayerOrException(),"deliver",serial,IntegerArgumentType.getInteger(c,"x"),IntegerArgumentType.getInteger(c,"z"));return 1;}))));
            for(String action:new String[]{"recover","dock","cancel","board","drain","door","fill"})root.then(Commands.literal(action).then(Commands.literal("0"+i).executes(c->{receive(c.getSource().getPlayerOrException(),action,serial,0,0);return 1;})));
        }
        root.then(deliver);event.getDispatcher().register(root);
    }
    private UNCommandR29() {}
}
