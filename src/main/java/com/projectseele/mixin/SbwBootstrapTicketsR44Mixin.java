package com.projectseele.mixin;

import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.FacilityWorldPolicy;
import net.minecraft.server.level.ServerChunkCache;
import net.minecraft.server.level.TicketType;
import net.minecraft.util.Unit;
import net.minecraft.world.level.ChunkPos;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Candidate: startup restoration is temporary; active vehicles retain their own live tickets. */
@Pseudo
@Mixin(targets="com.atsuishio.superbwarfare.world.saveddata.ChunkPosSavedData$Companion",remap=false)
public abstract class SbwBootstrapTicketsR44Mixin
{
    @Unique
    private static final TicketType<Unit> projectseele$bootstrap=TicketType.create(
            "projectseele_sbw_bootstrap_r44",(a,b)->0,600);

    @Redirect(method="posSavedDataOnServerStarted",
            at=@At(value="INVOKE",target="Lnet/minecraft/server/level/ServerChunkCache;addRegionTicket(Lnet/minecraft/server/level/TicketType;Lnet/minecraft/world/level/ChunkPos;ILjava/lang/Object;)V",remap=true),
            remap=false)
    private <T> void projectseele$boundedProjectBootstrap(ServerChunkCache source,TicketType<T> type,ChunkPos pos,int radius,T value)
    {
        if(Boolean.getBoolean("projectseele.r44ExpiringVehicleBootstrap") && type==TicketType.START && radius==3 && value==Unit.INSTANCE
                && source.level.dimension().equals(FacilitySchemaV2.DIMENSION)
                && FacilityWorldPolicy.isS20Rebuild(source.level.getServer()))
            source.addRegionTicket(projectseele$bootstrap,pos,radius,Unit.INSTANCE);
        else source.addRegionTicket(type,pos,radius,value);
    }
}
