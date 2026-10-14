package com.projectseele.world;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.MinecraftServer;
/** Root's claimed map retires inherited facility generators even before commissioning.
 * Readiness never re-enables a legacy coordinate writer. */
public final class NervLegacyGenerationGuardR52 {
    public static boolean retired(ServerLevel level){return NervTravelDirectoryR52.applies(level);}
    public static boolean retired(MinecraftServer server){return server!=null&&retired(server.getLevel(FacilitySchemaV2.DIMENSION));}
    public static boolean evaZone(ServerLevel level,String zone){return retired(level)&&zone!=null&&zone.matches("UNIT0[012]_(CAGE|CARRIER|SWITCHYARD|SILO|SURFACE_HEAD)");}
    public static boolean evaPort(ServerLevel level,FacilitySchemaV2.PortSpec port){return retired(level)&&(port.clearProfile().startsWith("EVA2X_")||evaZone(level,port.zoneId())||evaZone(level,port.peerZoneId()));}
    private NervLegacyGenerationGuardR52(){}
}
