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
    private static boolean night, powered;

    public static void receive(ClientboundEncounterObserverPacket packet)
    {
        var level = Minecraft.getInstance().level;
        if (level == null || !level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || !level.dimension().location().equals(packet.dimension())) return;
        if (bound.get() == level && packet.serverTick() < receivedTick) return;
        if (bound.get() != level && packet.kind() == ClientboundEncounterObserverPacket.Kind.BLACKOUT
                && com.projectseele.config.SeeleConfig.YASHIMA_BLACKOUT.get()
                && !YashimaBlackoutR64.held) CityLightWavesR65.joinDark(level);
        bound = new WeakReference<>(level);receivedTick = packet.serverTick();
        // R64: BLACKOUT is the same night with the power switched to the gun.
        powered = packet.kind() == ClientboundEncounterObserverPacket.Kind.BLACKOUT;
        night = powered || packet.kind() == ClientboundEncounterObserverPacket.Kind.NIGHT;
    }

    /** The mission's night is on in this world, wherever the camera is (the client thread's). */
    public static boolean night(ClientLevel level)
    {
        return night && level != null && bound.get() == level && level.dimension().equals(FacilitySchemaV2.DIMENSION);
    }

    /** The mission's night is on in this world and the power has been switched to the gun (R64). */
    public static boolean blackout(ClientLevel level)
    {
        return powered && night(level);
    }

    public static boolean surfaceNight(Level level)
    {
        var minecraft = Minecraft.getInstance();
        return minecraft.isSameThread() && (night || CityLightWavesR65.restoring(minecraft.level)) && level != null && level == minecraft.level
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
