package com.projectseele.client;

import com.projectseele.network.ClientboundEncounterObserverPacket;
import com.projectseele.world.FacilitySchemaV2;
import java.lang.ref.WeakReference;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.dimension.DimensionType;

/** Saved mission presentation only; the server/world clock is never changed. */
public final class TvYashimaNightClientR54
{
    private static WeakReference<ClientLevel> bound = new WeakReference<>(null);
    private static long receivedTick = Long.MIN_VALUE;
    private static boolean night;

    public static void receive(ClientboundEncounterObserverPacket packet)
    {
        var level = Minecraft.getInstance().level;
        if (level == null || !level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || !level.dimension().location().equals(packet.dimension())) return;
        if (bound.get() == level && packet.serverTick() < receivedTick) return;
        bound = new WeakReference<>(level);receivedTick = packet.serverTick();
        night = packet.kind() == ClientboundEncounterObserverPacket.Kind.NIGHT;
    }

    public static boolean surfaceNight(Level level)
    {
        var minecraft = Minecraft.getInstance();
        return minecraft.isSameThread() && night && level != null && level == minecraft.level
                && bound.get() == level && level.dimension().equals(FacilitySchemaV2.DIMENSION)
                && minecraft.gameRenderer.getMainCamera().getPosition().y >= -128;
    }

    public static boolean surfaceNight(DimensionType type)
    {
        var level = Minecraft.getInstance().level;
        return level != null && level.dimensionType() == type && surfaceNight(level);
    }

    private TvYashimaNightClientR54() {}
}
