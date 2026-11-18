package com.projectseele.network;

import com.projectseele.world.NervRouteDirectoryR52;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;
import net.minecraftforge.network.PacketDistributor;

/** Only the pilot receives the approaching section of their commissioned launch track. */
public record ClientboundLaunchRideR65(int eva, double exitY, List<Shutter> shutters)
{
    public record Shutter(Vec3 foot, Vec3 tangent) {}
    private static final int SPACING = 80;
    private static final int AHEAD = 3;

    public static void send(ServerPlayer pilot, int eva, NervRouteDirectoryR52 directory,
            NervRouteDirectoryR52.Route route, double travelled)
    {
        double bank = directory.readyDistanceR53(route);
        double end = directory.routeLength(route);
        var gates = new ArrayList<Shutter>(AHEAD);
        int first = Math.max(1, (int)Math.ceil((travelled - bank) / SPACING));
        for (int i = first; i < first + AHEAD; i++)
        {
            double at = bank + i * SPACING;
            if (at >= end - SPACING) break;
            var sample = directory.locateDistance(route, at);
            var leg = directory.leg(route.legs().get(sample.legIndex()));
            var axis = directory.tangent(leg, sample.fraction());
            if (axis.horizontalDistance() > .12)
                gates.add(new Shutter(directory.centrePoint(leg, sample.fraction()), axis));
        }
        var last = directory.leg(route.legs().get(route.legs().size() - 1));
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> pilot),
                new ClientboundLaunchRideR65(eva, directory.centrePoint(last, 1).y, List.copyOf(gates)));
    }

    public ClientboundLaunchRideR65(FriendlyByteBuf buf)
    {
        this(buf.readVarInt(), buf.readDouble(), readShutters(buf));
    }

    private static List<Shutter> readShutters(FriendlyByteBuf b)
    {
        int count = b.readVarInt();
        if (count < 0 || count > AHEAD) throw new IllegalArgumentException("Launch shutter count");
        var result = new ArrayList<Shutter>(count);
        for (int i = 0; i < count; i++)
            result.add(new Shutter(new Vec3(b.readDouble(), b.readDouble(), b.readDouble()),
                    new Vec3(b.readFloat(), b.readFloat(), b.readFloat())));
        return List.copyOf(result);
    }

    public void encode(FriendlyByteBuf buf)
    {
        buf.writeVarInt(eva);
        buf.writeDouble(exitY);
        buf.writeCollection(shutters, (b, gate) -> {
            Vec3 p = gate.foot(), n = gate.tangent();
            b.writeDouble(p.x).writeDouble(p.y).writeDouble(p.z);
            b.writeFloat((float)n.x).writeFloat((float)n.y).writeFloat((float)n.z);
        });
    }

    public void handle(Supplier<NetworkEvent.Context> context)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> () -> com.projectseele.client.LaunchTunnelViewR65.receive(this));
        context.get().setPacketHandled(true);
    }
}
