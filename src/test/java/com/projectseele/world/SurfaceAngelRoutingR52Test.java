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
        System.out.println("Surface Angel per-world routing PASS checks="+checks+"; no World/game or campaign completion");
    }
}
