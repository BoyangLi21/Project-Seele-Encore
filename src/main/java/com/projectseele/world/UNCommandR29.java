package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.network.*;
import com.projectseele.registry.ModItems;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraftforge.network.PacketDistributor;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.builder.RequiredArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.exceptions.SimpleCommandExceptionType;
import java.util.*;

/** UN authority is carried by the UN handset or the actual UN pilot, not NERV staff roles. */
public final class UNCommandR29
{
    private static final SimpleCommandExceptionType UNKNOWN_UNIT=new SimpleCommandExceptionType(Component.literal("UN 机体请用 un0 或 un1。"));
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
    /** UN handset holders and UN pilots; an operator-level console or command block may use the admin leaves too. */
    public static boolean canUse(CommandSourceStack source)
    {
        return source.hasPermission(2)||source.getEntity() instanceof ServerPlayer p&&authorized(p);
    }
    /** /seele un. The handset screen keeps receive(); commands answer in chat, because a typed command has no open screen. */
    public static LiteralArgumentBuilder<CommandSourceStack> command()
    {
        var un=Commands.literal("un");
        un.then(Commands.literal("phone").executes(c->{receive(c.getSource().getPlayerOrException(),"open",0,0,0);return 1;}));
        un.then(Commands.literal("status").executes(c->{var p=c.getSource().getPlayerOrException();p.sendSystemMessage(Component.literal(status(p.serverLevel(),0)+"\n"+status(p.serverLevel(),1)));return 1;}));
        un.then(Commands.literal("deliver").then(unitArgument().then(Commands.argument("x",IntegerArgumentType.integer(-29999000,29999000)).then(Commands.argument("z",IntegerArgumentType.integer(-29999000,29999000))
                .executes(c->transport(c,"deliver",IntegerArgumentType.getInteger(c,"x"),IntegerArgumentType.getInteger(c,"z")))))));
        // One recovery for everyone: it docks a unit already at the receiving apron and otherwise calls the aircraft.
        un.then(Commands.literal("recover").then(unitArgument().executes(c->UNRecoveryR22.request(c.getSource(),unit(c),false))));
        for(String action:new String[]{"dock","cancel","board"})un.then(Commands.literal(action).then(unitArgument().executes(c->transport(c,action,0,0))));
        var cells=Commands.literal("hangar");
        for(String action:new String[]{"status","drain","door","fill"})cells.then(Commands.literal(action).then(unitArgument().executes(c->hangar(c.getSource(),action,unit(c)))));
        un.then(cells);
        un.then(Commands.literal("reset").requires(s->s.hasPermission(2)).then(unitArgument().executes(c->UNRecoveryR22.request(c.getSource(),unit(c),true))));
        for(String toggle:new String[]{"defense","power"})un.then(Commands.literal(toggle).requires(s->s.hasPermission(2)).executes(c->{
            var l=c.getSource().getServer().getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return 0;
            String message=MilitaryR07Director.request(l,toggle,c.getSource().getPlayerOrException());c.getSource().sendSuccess(()->Component.literal(message),false);return 1;
        }));
        return un;
    }
    private static int transport(CommandContext<CommandSourceStack> c,String action,int x,int z)throws CommandSyntaxException
    {
        var p=c.getSource().getPlayerOrException();int serial=unit(c);
        if(!p.serverLevel().dimension().equals(FacilitySchemaV2.DIMENSION)){c.getSource().sendFailure(Component.literal("请进入第三新东京市所在的项目世界后再联络 UN 运输。"));return 0;}
        String reply=switch(action)
        {
            case "deliver" -> UNAirLiftR29.request(p,serial,false,x,z);
            case "dock" -> UNAirLiftR29.requestDock(p,serial);
            case "cancel" -> UNAirLiftR29.cancel(p,serial);
            default -> board(p,serial);
        };
        c.getSource().sendSuccess(()->Component.literal(Unit03SourceRigR53.displayName(serial)+"："+reply),false);return 1;
    }
    /** The wet cell of un0 or un1: the same interlock as the handset, answered in chat. */
    public static int hangar(CommandSourceStack source,String action,int serial)throws CommandSyntaxException
    {
        var p=source.getPlayerOrException();var l=p.serverLevel();
        if(!l.dimension().equals(FacilitySchemaV2.DIMENSION)){source.sendFailure(Component.literal("请进入第三新东京市所在的项目世界后再操作 UN 机库。"));return 0;}
        unit(l,serial);
        String reply=!action.equals("status")&&UNAirLiftR29.active(l,serial)?"运输任务正在使用机库，请先完成或取消运输。"
                :serial==0?MilitaryR07Director.request(l,action,null):UNAnnexR20.request(l,action,null);
        source.sendSuccess(()->Component.literal(reply),false);return 1;
    }
    private static RequiredArgumentBuilder<CommandSourceStack,String> unitArgument()
    {
        return Commands.argument("unit",StringArgumentType.word()).suggests((c,b)->SharedSuggestionProvider.suggest(new String[]{"un0","un1"},b));
    }
    /** un0 or un1; the 00/01 of the old /un and /seele military spellings still parses. */
    private static int unit(CommandContext<CommandSourceStack> c)throws CommandSyntaxException
    {
        return switch(StringArgumentType.getString(c,"unit").toLowerCase(Locale.ROOT))
        {
            case "un0","un00","00","0" -> 0;
            case "un1","un01","01","1" -> 1;
            default -> throw UNKNOWN_UNIT.create();
        };
    }
    private UNCommandR29() {}
}
