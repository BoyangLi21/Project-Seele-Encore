package com.projectseele.visual;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.RegionalGatewayDirector;
import com.projectseele.world.NervTravelDirectoryR52;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.ClickEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.List;

/** Fixed, measured arrivals in the current commissioned world. Never builds terrain. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SeeleTravelCommandsR43
{
    public record Destination(String key,String label,Vec3 point,float yaw) {}
    public static final List<Destination> DESTINATIONS=List.of(
        new Destination("entrance","NERV 地面入口",new Vec3(-360.5,81,730.5),0),
        new Destination("command","指挥室入口",new Vec3(28.5,-406,269.5),0),
        new Destination("dogma","终极教条前厅",new Vec3(31.5,-566,280.5),0),
        new Destination("observation","机库上层观察廊",new Vec3(90.5,-367,-221.5),90),
        new Destination("station","NERV 总部车站",new Vec3(30.5,-466,451.5),0),
        new Destination("hanger_station","EVA 机库车站",new Vec3(150.5,-442,-28.5),180),
        new Destination("tokyo3","第三新东京中央区域",new Vec3(32.5,81,217.5),180),
        new Destination("hakone","新箱根中央车站",new Vec3(-1484.5,131,649.5),180),
        new Destination("port","港口登舰栈桥",new Vec3(1471.5,65,582.5),180),
        new Destination("airport","NERV 航空基地航站楼",new Vec3(420.5,73,75.5),180),
        new Destination("geofront_airport","地下运输机场控制区",new Vec3(-353.5,-475,-299.5),90),
        new Destination("un","联合国军事基地",new Vec3(6560.5,75,-5968.5),180),
        new Destination("un_hangar","联合国试验机库人员走廊",new Vec3(6394.5,77,-6192.5),90),
        new Destination("rei","绫波丽公寓门外",new Vec3(-2848.5,86,-1108.5),0),
        new Destination("misato","美里家公寓入口",new Vec3(196.5,81,527.5),0),
        new Destination("school","第三新东京第一中学校门外",new Vec3(253.5,73,-679.5),180));

    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        var root=Commands.literal("seele").requires(s->s.hasPermission(2));
        root.then(Commands.literal("enter").executes(c->teleport(c.getSource(),"entrance")));
        var travel=Commands.literal("tp").executes(c->list(c.getSource()));
        travel.then(Commands.argument("destination",StringArgumentType.word())
                .suggests((context,builder)->SharedSuggestionProvider.suggest(destinations(context.getSource()).stream().map(Destination::key),builder))
                .executes(c->teleport(c.getSource(),StringArgumentType.getString(c,"destination"))));
        root.then(travel);event.getDispatcher().register(root);
    }
    private static List<Destination> destinations(CommandSourceStack source)
    {
        var level=source.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(NervTravelDirectoryR52.applies(level))
        {
            var directory=NervTravelDirectoryR52.installed(level);
            return directory==null?List.of():directory.arrivals().stream()
                    .map(a->new Destination(a.key(),a.label(),a.position(),a.yaw())).toList();
        }
        var result=new java.util.ArrayList<>(DESTINATIONS);
        result.add(new Destination("hangar","EVA 机库登机廊",Vec3.ZERO,0));
        return List.copyOf(result);
    }
    private static int list(CommandSourceStack source)
    {
        var destinations=destinations(source);
        if(destinations.isEmpty())return unavailable(source);
        source.sendSuccess(()->Component.literal("SEELE 传送地点（可点击）："),false);
        for(var destination:destinations)source.sendSuccess(()->link(destination.key(),destination.label()),false);
        return 1;
    }
    private static Component link(String key,String label)
    {
        return Component.literal("/seele tp "+key+"  — "+label)
                .withStyle(s->s.withColor(0xA9D9AE).withClickEvent(new ClickEvent(ClickEvent.Action.RUN_COMMAND,"/seele tp "+key)));
    }
    public static int teleport(CommandSourceStack source,Destination destination)throws CommandSyntaxException
    {
        return teleport(source,destination.key());
    }
    public static int teleport(CommandSourceStack source,String key)throws CommandSyntaxException
    {
        key=NervTravelDirectoryR52.canonicalKey(key);
        var player=source.getPlayerOrException();var level=source.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null||!RegionalGatewayDirector.active(level))
        {
            source.sendFailure(Component.literal("当前存档尚未安装这套 NERV 设施，请先导入配套 SEELE 存档。"));return 0;
        }
        Destination destination=null;
        if(NervTravelDirectoryR52.applies(level))
        {
            var directory=NervTravelDirectoryR52.installed(level);
            if(directory==null)return unavailable(source);
            var arrival=directory.arrival(key);
            if(arrival!=null)destination=new Destination(arrival.key(),arrival.label(),arrival.position(),arrival.yaw());
        }
        else
        {
            if(key.equals("hangar"))return EvaLogisticsCommands.enterHangar(source);
            for(var arrival:DESTINATIONS)if(arrival.key().equals(key)){destination=arrival;break;}
        }
        if(destination==null)
        {source.sendFailure(Component.literal("当前地图没有这个到达入口，请用 /seele tp 查看已安装地点。"));return 0;}
        return arrive(source,player,level,destination);
    }
    private static int unavailable(CommandSourceStack source)
    {source.sendFailure(Component.literal("新地图的到达目录尚未安装或与当前地图不一致，请完成配套地图安装。"));return 0;}
    private static int arrive(CommandSourceStack source,net.minecraft.server.level.ServerPlayer player,
            net.minecraft.server.level.ServerLevel level,Destination destination)
    {
        Vec3 p=destination.point();BlockPos cell=BlockPos.containing(p);
        if(cell.getY()<=level.getMinBuildHeight()||cell.getY()+2>=level.getMaxBuildHeight()
                ||!level.getWorldBorder().isWithinBounds(cell))
        {source.sendFailure(Component.literal("到达入口超出当前地图范围，未执行传送。"));return 0;}
        for(int x=(cell.getX()-1)>>4;x<=(cell.getX()+1)>>4;x++)
            for(int z=(cell.getZ()-1)>>4;z<=(cell.getZ()+1)>>4;z++)level.getChunk(x,z);
        AABB body=new AABB(p.x-.30,p.y+.01,p.z-.30,p.x+.30,p.y+1.80,p.z+.30);
        AABB sole=new AABB(p.x-.28,p.y-.16,p.z-.28,p.x+.28,p.y+.005,p.z+.28);
        if(!level.noCollision(player,body)||!level.getBlockCollisions(player,sole).iterator().hasNext()||!level.getFluidState(cell).isEmpty())
        {
            source.sendFailure(Component.literal("“"+destination.label()+"”的落脚点暂时不安全，未执行传送。"));return 0;
        }
        player.stopRiding();player.teleportTo(level,p.x,p.y,p.z,destination.yaw(),0);player.fallDistance=0;player.setDeltaMovement(Vec3.ZERO);
        source.sendSuccess(()->Component.literal("已到达："+destination.label()),false);return 1;
    }
    private SeeleTravelCommandsR43() {}
}
