package com.projectseele.world;

/** World-routing policy only; no invented encounter completion or native gameplay claim. */
public final class SurfaceAngelRoutingR52Test
{
    private static int checks;
    private static void check(boolean condition,String why){checks++;if(!condition)throw new AssertionError(why);}
    public static void main(String[] args)
    {
        for(String chapter:new String[]{"sachiel","shamshel"})
        {
            check(SurfaceAngelPlanR52.routingR52(chapter,false,false,false)==SurfaceAngelPlanR52.RoutingR52.LEGACY,"An unclaimed original world retains its original campaign");
            check(SurfaceAngelPlanR52.routingR52(chapter,false,false,true)==SurfaceAngelPlanR52.RoutingR52.LEGACY,"A readiness signal alone cannot migrate another world");
            check(SurfaceAngelPlanR52.routingR52(chapter,true,false,false)==SurfaceAngelPlanR52.RoutingR52.HOLD,"Declared but uninstalled world cannot spawn at old coordinates");
            check(SurfaceAngelPlanR52.routingR52(chapter,true,false,true)==SurfaceAngelPlanR52.RoutingR52.HOLD,"A declaration requires its own claim before becoming playable");
            check(SurfaceAngelPlanR52.routingR52(chapter,false,true,false)==SurfaceAngelPlanR52.RoutingR52.HOLD,"Claimed world with missing route document remains held");
            check(SurfaceAngelPlanR52.routingR52(chapter,true,true,false)==SurfaceAngelPlanR52.RoutingR52.HOLD,"Cold pending installation must not fall back");
            check(SurfaceAngelPlanR52.routingR52(chapter,true,true,true)==SurfaceAngelPlanR52.RoutingR52.SURFACE,"Ready declared world uses installed surface routes");
            check(SurfaceAngelPlanR52.routingR52(chapter,false,true,true)==SurfaceAngelPlanR52.RoutingR52.SURFACE,"Claimed authority still intercepts a missing plan for startBlocker");
        }
        for(String chapter:new String[]{"ramiel","gaghiel","",null})
            check(SurfaceAngelPlanR52.routingR52(chapter,true,true,true)==SurfaceAngelPlanR52.RoutingR52.LEGACY,"Other chapters are not captured by the first-two-Angels policy");
        check(SurfaceAngelPlanR52.declarationMatchesR52("projectseele:geofront","projectseele:geofront",true),"Matching dimension declaration");
        check(!SurfaceAngelPlanR52.declarationMatchesR52("projectseele:geofront","minecraft:overworld",false),"Shared world-root file does not claim another dimension");
        check(!SurfaceAngelPlanR52.declarationMatchesR52("other:dimension","projectseele:geofront",true),"Explicit foreign dimension is not inferred from generator type");
        check(SurfaceAngelPlanR52.declarationMatchesR52("","projectseele:geofront",true),"Damaged declaration holds its GeoFront instead of old-site fallback");
        check(!SurfaceAngelPlanR52.declarationMatchesR52("","minecraft:overworld",false),"Damaged GeoFront declaration does not select the overworld");
        var owner=java.util.UUID.fromString("00000000-0000-0000-0000-000000000001");
        var target=java.util.UUID.fromString("00000000-0000-0000-0000-000000000002");
        var foreign=java.util.UUID.fromString("00000000-0000-0000-0000-000000000003");
        for(String chapter:new String[]{"sachiel","shamshel"})for(double distance:new double[]{48,80,160})
        {
            var data=new TvCampaignSavedData();data.active=chapter;data.owner=owner;data.angel=target;data.phase="approach";data.generationR43=6;
            check(!data.canFinish(chapter,owner,target),"Merely approaching does not satisfy combat completion");
            check(SurfaceAngelAssaultR52.beginsCombatR53(data.phase,distance*distance,160),"Accepted ranged engagement uses the declared range, including its boundary");
            data.phase="combat";
            check(!data.canFinish(chapter,foreign,target)&&!data.canFinish(chapter,owner,foreign),"Ranged engagement cannot change accepted owner or target identity");
            check(!data.canFinish(chapter.equals("sachiel")?"shamshel":"sachiel",owner,target),"Another chapter cannot claim this kill");
            check(data.finish(chapter,owner,target)&&data.targetDeathConfirmedR45&&data.phase.equals("combat_victory"),"The ordinary death callback can finish the accepted ranged encounter");
            check(!data.archiveEpisode(chapter,owner,6),"Victory still requires original recovery and equipment handover before archive");
        }
        check(!SurfaceAngelAssaultR52.beginsCombatR53("approach",160.001*160.001,160),"Outside the declared engagement range remains approaching");
        for(String phase:new String[]{"alert","combat","cancel","failure","combat_victory","episode_archived","idle"})
            check(!SurfaceAngelAssaultR52.beginsCombatR53(phase,80*80,160),"An engagement cannot bypass alert or reopen another phase: "+phase);
        System.out.println("Surface Angel routing/ranged engagement PASS checks="+checks+"; state contract only, no native encounter completion");
    }
}
