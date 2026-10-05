package com.projectseele.network;

import java.util.function.Supplier;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/**
 * Pilot telemetry for the lower orange tactical board in NERV operations.
 *
 * <p>The board cannot read this from the client level: an EVA parked in its
 * hangar is routinely outside the operator's entity tracking range, so a
 * client-side scan shows an empty screen exactly when the room is supposed to
 * be watching a launch. The server samples the canonical fleet instead and
 * pushes it to everyone in GeoFront.</p>
 */
public final class ClientboundPilotStatusPacket
{
    public static final int UNIT_COUNT = 3;

    /** One EVA row; {@code present} false means no canonical chassis. */
    public record Unit(boolean present, String pilot, String phase,
                       float sync, float atEnergy, float atCapacity,
                       float health, float maxHealth,
                       int powerTicks, int powerCapacity,
                       boolean externalPower, boolean berserk,
                       boolean liveFeed)
    {
        public static final Unit ABSENT = new Unit(false, "", "OFFLINE",
                0.0F, 0.0F, 0.0F, 0.0F, 0.0F, 0, 0, false, false, false);
    }

    private final Unit[] units;
    private final String cityPhase;
    private final int cityDepth;
    private final int cityTargetDepth;
    private final int cityMaximumDepth;
    private final float cityPhysicalRetractionFraction;
    private final String armamentState;
    private final boolean armamentStocked;
    private final int armamentLiftPercent;

    public ClientboundPilotStatusPacket(Unit[] units, String cityPhase,
                                        int cityDepth, int cityTargetDepth,
                                        int cityMaximumDepth,
                                        float cityPhysicalRetractionFraction,
                                        String armamentState,
                                        boolean armamentStocked,
                                        int armamentLiftPercent)
    {
        this.units = units;
        this.cityPhase = cityPhase;
        this.cityDepth = cityDepth;
        this.cityTargetDepth = cityTargetDepth;
        this.cityMaximumDepth = cityMaximumDepth;
        this.cityPhysicalRetractionFraction = cityPhysicalRetractionFraction;
        this.armamentState = armamentState;
        this.armamentStocked = armamentStocked;
        this.armamentLiftPercent = armamentLiftPercent;
    }

    public ClientboundPilotStatusPacket(FriendlyByteBuf buffer)
    {
        this.units = new Unit[UNIT_COUNT];
        for (int index = 0; index < UNIT_COUNT; index++)
        {
            if (!buffer.readBoolean())
            {
                this.units[index] = Unit.ABSENT;
                continue;
            }
            this.units[index] = new Unit(true,
                    buffer.readUtf(32), buffer.readUtf(32),
                    buffer.readFloat(), buffer.readFloat(),
                    buffer.readFloat(), buffer.readFloat(),
                    buffer.readFloat(), buffer.readVarInt(),
                    buffer.readVarInt(), buffer.readBoolean(),
                    buffer.readBoolean(), buffer.readBoolean());
        }
        this.cityPhase = buffer.readUtf(32);
        this.cityDepth = buffer.readVarInt();
        this.cityTargetDepth = buffer.readVarInt();
        this.cityMaximumDepth = buffer.readVarInt();
        this.cityPhysicalRetractionFraction = buffer.readFloat();
        this.armamentState = buffer.readUtf(32);
        this.armamentStocked = buffer.readBoolean();
        this.armamentLiftPercent = buffer.readVarInt();
    }

    public void encode(FriendlyByteBuf buffer)
    {
        for (int index = 0; index < UNIT_COUNT; index++)
        {
            Unit unit = this.units[index];
            buffer.writeBoolean(unit.present());
            if (!unit.present())
            {
                continue;
            }
            buffer.writeUtf(unit.pilot(), 32);
            buffer.writeUtf(unit.phase(), 32);
            buffer.writeFloat(unit.sync());
            buffer.writeFloat(unit.atEnergy());
            buffer.writeFloat(unit.atCapacity());
            buffer.writeFloat(unit.health());
            buffer.writeFloat(unit.maxHealth());
            buffer.writeVarInt(unit.powerTicks());
            buffer.writeVarInt(unit.powerCapacity());
            buffer.writeBoolean(unit.externalPower());
            buffer.writeBoolean(unit.berserk());
            buffer.writeBoolean(unit.liveFeed());
        }
        buffer.writeUtf(this.cityPhase, 32);
        buffer.writeVarInt(this.cityDepth);
        buffer.writeVarInt(this.cityTargetDepth);
        buffer.writeVarInt(this.cityMaximumDepth);
        buffer.writeFloat(this.cityPhysicalRetractionFraction);
        buffer.writeUtf(this.armamentState, 32);
        buffer.writeBoolean(this.armamentStocked);
        buffer.writeVarInt(this.armamentLiftPercent);
    }

    public void handle(Supplier<NetworkEvent.Context> contextSupplier)
    {
        NetworkEvent.Context context = contextSupplier.get();
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.projectseele.client.EvaCommandFeedClient
                        .setPilotStatus(this.units, this.cityPhase,
                                this.cityDepth, this.cityTargetDepth,
                                this.cityMaximumDepth,
                                this.cityPhysicalRetractionFraction,
                                this.armamentState, this.armamentStocked,
                                this.armamentLiftPercent));
        context.setPacketHandled(true);
    }
}
