package com.projectseele.network;

import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/**
 * R64: the Yashima emplacement's gunnery as the server has it, for the shooter's own sight: the power that reaches
 * the gun, the service after a shot, whether a charge is admitted now, and the target's own charge and core. The
 * sight draws these numbers and guesses none of them.
 *
 * @param entity       the shooting Unit
 * @param phase        the operation: 1 alert, 2 approach, 3 combat, 0 anything else
 * @param grid         how many of the position's three grid switches are closed
 * @param pylons       the position's power sockets are all there
 * @param umbilical    the Unit's cable is on one of them
 * @param permitted    the server admits a charge now
 * @param shots        shots fired in this operation
 * @param service      the service since the last shot, in ticks (the fuse is in at 100, the barrel cooled at 120)
 * @param targetCharge ticks until the target fires, 0 when it is not charging
 * @param exposed      the target's core is open
 * @param beam         ticks its beam still lasts, of {@code beamTotal}
 * @param notice       the last clause of the operation's notice (what holds the gun, or that it is clear)
 */
public record ClientboundCannonServiceR64(int entity, int phase, int grid, boolean pylons, boolean umbilical, boolean permitted,
        int shots, int service, boolean reload, boolean coolant, int targetCharge, int targetChargeTotal, boolean exposed, int beam, int beamTotal,
        double coreX, double coreY, double coreZ, float coreRadius, String notice)
{
    public ClientboundCannonServiceR64
    {
        if (phase < 0 || phase > 3 || grid < 0 || grid > 3 || service < 0 || service > 120 || targetCharge < 0 || targetChargeTotal < 0 || beam < 0 || beamTotal < 0
                || !Double.isFinite(coreX) || !Double.isFinite(coreY) || !Double.isFinite(coreZ) || !Float.isFinite(coreRadius) || coreRadius < 0)
            throw new IllegalArgumentException("Bounded gunnery state required");
        notice = notice == null ? "" : notice.length() > 96 ? notice.substring(0, 96) : notice;
    }

    public ClientboundCannonServiceR64(FriendlyByteBuf buffer)
    {
        this(buffer.readVarInt(), buffer.readByte(), buffer.readByte(), buffer.readBoolean(), buffer.readBoolean(), buffer.readBoolean(),
                buffer.readVarInt(), buffer.readVarInt(), buffer.readBoolean(), buffer.readBoolean(), buffer.readVarInt(), buffer.readVarInt(), buffer.readBoolean(),
                buffer.readVarInt(), buffer.readVarInt(), buffer.readDouble(), buffer.readDouble(), buffer.readDouble(), buffer.readFloat(), buffer.readUtf(96));
    }

    public void encode(FriendlyByteBuf buffer)
    {
        buffer.writeVarInt(entity); buffer.writeByte(phase); buffer.writeByte(grid); buffer.writeBoolean(pylons); buffer.writeBoolean(umbilical); buffer.writeBoolean(permitted);
        buffer.writeVarInt(shots); buffer.writeVarInt(service); buffer.writeBoolean(reload); buffer.writeBoolean(coolant); buffer.writeVarInt(targetCharge);
        buffer.writeVarInt(targetChargeTotal); buffer.writeBoolean(exposed); buffer.writeVarInt(beam); buffer.writeVarInt(beamTotal);
        buffer.writeDouble(coreX); buffer.writeDouble(coreY); buffer.writeDouble(coreZ); buffer.writeFloat(coreRadius); buffer.writeUtf(notice, 96);
    }

    public void handle(Supplier<NetworkEvent.Context> context)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> () -> com.projectseele.client.cockpit.PlugCannonSightR64.receive(this));
        context.get().setPacketHandled(true);
    }
}
