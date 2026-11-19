package com.projectseele.visual;

import com.projectseele.world.OperationText;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
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
import java.util.List;

/** Fixed, measured arrivals in the current commissioned world (/seele tp, /seele enter). Never builds terrain. */
public final class SeeleTravelCommandsR43
{
    public record Destination(String key,String label,Vec3 point,float yaw) {}
    public static final List<Destination> DESTINATIONS=List.of(
        new Destination("entrance","ops.projectseele.travel.entrance",new Vec3(-360.5,81,730.5),0),
        new Destination("command","ops.projectseele.travel.command",new Vec3(28.5,-406,269.5),0),
        new Destination("dogma","ops.projectseele.travel.dogma",new Vec3(31.5,-566,280.5),0),
        new Destination("observation","ops.projectseele.travel.observation",new Vec3(90.5,-367,-221.5),90),
        new Destination("station","ops.projectseele.travel.station",new Vec3(30.5,-466,451.5),0),
        new Destination("hanger_station","ops.projectseele.travel.hanger_station",new Vec3(150.5,-442,-28.5),180),
        new Destination("tokyo3","ops.projectseele.travel.tokyo3",new Vec3(32.5,81,217.5),180),
        new Destination("hakone","ops.projectseele.travel.hakone",new Vec3(-1484.5,131,649.5),180),
        new Destination("port","ops.projectseele.travel.port",new Vec3(1471.5,65,582.5),180),
        new Destination("airport","ops.projectseele.travel.airport",new Vec3(420.5,73,75.5),180),
        new Destination("geofront_airport","ops.projectseele.travel.geofront_airport",new Vec3(-353.5,-475,-299.5),90),
        new Destination("un","ops.projectseele.travel.un",new Vec3(6560.5,75,-5968.5),180),
        new Destination("un_hangar","ops.projectseele.travel.un_hangar",new Vec3(6394.5,77,-6192.5),90),
        new Destination("rei","ops.projectseele.travel.rei",new Vec3(-193.5,103,519.5),-90),
        new Destination("misato","ops.projectseele.travel.misato",new Vec3(-44.0,133,765.5),0),
        new Destination("school","ops.projectseele.travel.school",new Vec3(253.5,73,-679.5),180));

    public static LiteralArgumentBuilder<CommandSourceStack> enterCommand()
    {
        return Commands.literal("enter").executes(c->teleport(c.getSource(),"entrance"));
    }
    public static LiteralArgumentBuilder<CommandSourceStack> tpCommand()
    {
        return Commands.literal("tp").executes(c->list(c.getSource()))
                .then(Commands.argument("destination",StringArgumentType.word())
                        .suggests((context,builder)->SharedSuggestionProvider.suggest(destinations(context.getSource()).stream().map(Destination::key),builder))
                        .executes(c->teleport(c.getSource(),StringArgumentType.getString(c,"destination"))));
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
        result.add(new Destination("hangar","ops.projectseele.travel.hangar",Vec3.ZERO,0));
        return List.copyOf(result);
    }
    private static int list(CommandSourceStack source)
    {
        var destinations=destinations(source);
        if(destinations.isEmpty())return unavailable(source);
        source.sendSuccess(()->Component.translatable("message.projectseele.travel.list"),false);
        for(var destination:destinations)source.sendSuccess(()->link(destination.key(),destination.label()),false);
        return 1;
    }
    private static Component link(String key,String label)
    {
        return Component.literal("/seele tp "+key+"  — ").append(OperationText.read(label))
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
            source.sendFailure(Component.translatable("message.projectseele.travel.no_facility"));return 0;
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
        {source.sendFailure(Component.translatable("message.projectseele.travel.no_gate"));return 0;}
        return arrive(source,player,level,destination);
    }
    private static int unavailable(CommandSourceStack source)
    {source.sendFailure(Component.translatable("message.projectseele.travel.directory"));return 0;}
    private static int arrive(CommandSourceStack source,net.minecraft.server.level.ServerPlayer player,
            net.minecraft.server.level.ServerLevel level,Destination destination)
    {
        Vec3 p=destination.point();BlockPos cell=BlockPos.containing(p);
        if(cell.getY()<=level.getMinBuildHeight()||cell.getY()+2>=level.getMaxBuildHeight()
                ||!level.getWorldBorder().isWithinBounds(cell))
        {source.sendFailure(Component.translatable("message.projectseele.travel.out_of_bounds"));return 0;}
        for(int x=(cell.getX()-1)>>4;x<=(cell.getX()+1)>>4;x++)
            for(int z=(cell.getZ()-1)>>4;z<=(cell.getZ()+1)>>4;z++)level.getChunk(x,z);
        AABB body=new AABB(p.x-.30,p.y+.01,p.z-.30,p.x+.30,p.y+1.80,p.z+.30);
        AABB sole=new AABB(p.x-.28,p.y-.16,p.z-.28,p.x+.28,p.y+.005,p.z+.28);
        if(!level.noCollision(player,body)||!level.getBlockCollisions(player,sole).iterator().hasNext()||!level.getFluidState(cell).isEmpty())
        {
            source.sendFailure(Component.translatable("message.projectseele.travel.unsafe", OperationText.read(destination.label())));return 0;
        }
        player.stopRiding();
        // The facility keeps a pilot in an entry plug that has no safe place to step out (inserted in a unit that
        // stands deployed, for one). Teleported while still seated, the pilot's client lost the ground under the
        // unit it drives, and the unit fell through its closed hatch and down the launch shaft.
        if(player.isPassenger())
        {
            source.sendFailure(Component.translatable("message.projectseele.travel.cannot_dismount"));return 0;
        }
        player.teleportTo(level,p.x,p.y,p.z,destination.yaw(),0);player.fallDistance=0;player.setDeltaMovement(Vec3.ZERO);
        source.sendSuccess(()->Component.translatable("message.projectseele.travel.arrived", OperationText.read(destination.label())),false);return 1;
    }
    private SeeleTravelCommandsR43() {}
}
