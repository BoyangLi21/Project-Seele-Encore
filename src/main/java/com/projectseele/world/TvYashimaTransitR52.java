package com.projectseele.world;

import com.projectseele.entity.*;
import net.minecraft.server.level.ServerLevel;
import java.util.*;

/** Bank2 original departure, typed original far flight, and one accepted landing per mission generation. */
public final class TvYashimaTransitR52
{
    private static final String GENERATION="YashimaLandingGenerationR52",LAYOUT="YashimaLandingLayoutR52",RECEIVER="YashimaLandingReceiverR52";
    public static boolean landed(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva)
    {
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);if(site==null||eva==null)return false;
        var landing=site.landings().get(eva.getUnitVariant());if(landing==null)return false;var tag=eva.getPersistentData();
        return tag.getLong(GENERATION)==data.generationR43&&tag.getString(LAYOUT).equals(data.encounterLayoutR45)&&tag.getString(RECEIVER).equals(landing.receiver());
    }
    private static boolean physicalLanding(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,TvEncounterSitesR45.Landing landing)
    {
        if(EvaAirTransportR31.active(eva)||NervAirTransportRuntimeR52.pending(level,eva)||eva.isNervLogisticsLocked()
                ||eva.position().distanceTo(landing.point())>2||AirCradleClearanceR31.touchdownContact(eva)==null)return false;
        var assignment=data.sorties.get(eva.getUnitVariant());String mission=AutoSortieR32.missionToken(level);var state=NervAirTransportRuntimeR52.state(level);
        return state.jobs().stream().anyMatch(j->j.payloadTransferred()&&!j.carrying()&&!j.cancelRequested()
                &&j.receiver().equals(landing.receiver())&&j.original().eva().equals(eva.getUUID())&&j.original().variant()==eva.getUnitVariant()
                &&j.original().owner().equals(assignment.commander)&&j.original().pilot().equals(assignment.pilotR45)
                &&j.original().mission().equals(mission)&&j.manifestFingerprint().equals(state.manifestFingerprint()));
    }
    public static boolean automatic(ServerLevel level,int unit)
    {
        var data=TvCampaignSavedData.get(level);var sortie=data.sorties.get(unit);
        if(!data.active.equals("ramiel")||unit<0||unit>1||sortie==null||!sortie.npc)return false;
        if(AutoSortieR32.missionToken(level).isEmpty())return true;var eva=TvSortiesR32.assignedUnit(level,sortie);if(eva==null)return true;
        if(landed(level,data,eva))return true;
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);var landing=site==null?null:site.landings().get(unit);
        if(landing==null||!NervRouteRuntimeR52.claimed(level)||!NervRouteRuntimeR52.ready(level))
        {data.notice="屋岛原bank2地下出动与两独立远山落点尚未接通；不改走地表。";return true;}
        var tag=eva.getPersistentData();String mission=AutoSortieR32.missionToken(level);
        if(StaffRecoveryR47.pending(level,unit)||AutoSortieR32.cancellationCurrentR45(tag.getBoolean("R32AutoCancelled"),tag.getString("R43AutoMission"),mission))return true;
        var plug=EntryPlugDirector.canonical(level,unit);var pilot=plug==null?null:plug.getFirstPassenger();
        if(!AutoSortieR32.assignedPilotR45(level,unit,pilot)||!plug.isHatchFullySealed())return true;
        if(physicalLanding(level,data,eva,landing))
        {
            tag.putLong(GENERATION,data.generationR43);tag.putString(LAYOUT,data.encounterLayoutR45);tag.putString(RECEIVER,landing.receiver());
            data.notice=NervStaffDialogue.unitName(unit)+"已由原飞机完成原落点交付，继续步行到本机实际战位。";data.setDirty();return true;
        }
        if(NervAirTransportRuntimeR52.pending(level,eva)||EvaAirTransportR31.active(eva))return true;
        if(!NervRouteRuntimeR52.status(level,unit).phase().equals("DEPLOYED"))
        {NervRouteRuntimeR52.automatic(level,unit);return true;}
        var ground=NervRouteRuntimeR52.flightContext(level);var saved=level.getDataStorage().get(NervRouteRuntimeStateR52::load,NervRouteRuntimeStateR52.NAME);
        var departed=saved==null?null:saved.job(unit);var route=ground==null||departed==null?null:ground.directory().route(departed.snapshot().route());
        if(route==null||route.bank()!=2||!departed.snapshot().original().mission().equals(mission))
        {data.notice="本场原机尚无bank2地下出动凭证；保持原位，不由旧地表出击转送。";return true;}
        if(level.getGameTime()<tag.getLong("YashimaFlightRetryR52"))return true;
        tag.putLong("YashimaFlightRetryR52",level.getGameTime()+40);
        data.notice=NervAirTransportRuntimeR52.requestReceiver(level,unit,sortie.commander,landing.receiver());data.setDirty();return true;
    }
    private TvYashimaTransitR52(){}
}
