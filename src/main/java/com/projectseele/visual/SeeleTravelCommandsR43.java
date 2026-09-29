package com.projectseele.visual;

import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.RegionalGatewayDirector;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
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
        new Destination("un","联合国军事基地",new Vec3(6560.5,75,-5968.5),180),
        new Destination("un_hangar","联合国试验机库人员走廊",new Vec3(6394.5,77,-6192.5),90),
        new Destination("rei","绫波丽公寓门外",new Vec3(-2848.5,86,-1108.5),0));

    @SubscribeEvent public static void register(RegisterCommandsEvent event)
    {
        var root=Commands.literal("seele").requires(s->s.hasPermission(2));
        root.then(Commands.literal("enter").executes(c->teleport(c.getSource(),DESTINATIONS.get(0))));
        var travel=Commands.literal("tp").executes(c->list(c.getSource()));
        travel.then(Commands.literal("hanger").executes(c->EvaLogisticsCommands.enterHangar(c.getSource())));
        for(var destination:DESTINATIONS)travel.then(Commands.literal(destination.key()).executes(c->teleport(c.getSource(),destination)));
        root.then(travel);event.getDispatcher().register(root);
    }
    private static int list(CommandSourceStack source)
    {
        source.sendSuccess(()->Component.literal("SEELE 传送地点（可点击）："),false);
        source.sendSuccess(()->link("hanger","EVA 机库登机廊"),false);
        for(var destination:DESTINATIONS)source.sendSuccess(()->link(destination.key(),destination.label()),false);
        return 1;
    }
    private static Component link(String key,String label)
    {
        return Component.literal("/seele tp "+key+"  — "+label)
                .withStyle(s->s.withColor(0xA9D9AE).withClickEvent(new ClickEvent(ClickEvent.Action.RUN_COMMAND,"/seele tp "+key)));
    }
    public static int teleport(CommandSourceStack source,Destination destination)throws CommandSyntaxException
    {
        var player=source.getPlayerOrException();var level=source.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null||!RegionalGatewayDirector.active(level))
        {
            source.sendFailure(Component.literal("当前存档尚未安装这套 NERV 设施，请先导入配套 SEELE 存档。"));return 0;
        }
        Vec3 p=destination.point();BlockPos cell=BlockPos.containing(p);
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
