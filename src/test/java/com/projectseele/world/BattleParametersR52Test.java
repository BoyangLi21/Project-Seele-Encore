package com.projectseele.world;

import com.google.gson.*;

/** Synthetic contract rejection tests only; these do not certify routes, motion or a native campaign. */
public final class BattleParametersR52Test
{
    private static int checks;
    private static void check(boolean ok,String reason){checks++;if(!ok)throw new AssertionError(reason);}
    private static void rejects(Runnable operation,String reason)
    {boolean rejected=false;try{operation.run();}catch(RuntimeException expected){rejected=true;}check(rejected,reason);}
    private static JsonObject fixture()
    {
        return JsonParser.parseString("""
            {"schema":52,"dimension":"synthetic:surface","id":"synthetic","armor_column":"synthetic_plate",
             "installed":true,"geometry_validated":true,"sites":{
               "sachiel":{"spawn":[0,10,0],"route":[[0,10,0],[50,10,0],[100,10,0],[150,10,0],[200,10,0]],
                 "intercept":[180,10,30],"yaw":0,"speed":0.2,"arrival_radius":1,"engagement_range":96,"attack_period_ticks":100,"armor_damage":20},
               "shamshel":{"spawn":[0,10,0],"route":[[0,10,0],[50,10,0],[100,10,0],[150,10,0],[200,10,0]],
                 "intercept":[180,10,30],"yaw":0,"speed":0.2,"arrival_radius":1,"engagement_range":96,"attack_period_ticks":100,"armor_damage":20}}}
            """).getAsJsonObject();
    }
    public static void main(String[] args)
    {
        var root=fixture();var plan=SurfaceAngelPlanR52.parse(root,"synthetic:surface");
        check(plan.sites().size()==2,"both surface encounters present");check(plan.fingerprint().length()==64,"configuration continuity fingerprint");
        rejects(()->SurfaceAngelPlanR52.parse(fixture(),"synthetic:other"),"foreign dimension");
        var absent=fixture();absent.remove("sites");rejects(()->SurfaceAngelPlanR52.parse(absent,"synthetic:surface"),"no old-site fallback");
        var draft=fixture();draft.addProperty("installed",false);rejects(()->SurfaceAngelPlanR52.parse(draft,"synthetic:surface"),"unbuilt design cannot start");
        var unmeasured=fixture();unmeasured.addProperty("geometry_validated",false);rejects(()->SurfaceAngelPlanR52.parse(unmeasured,"synthetic:surface"),"unmeasured route cannot start");
        var broken=fixture();broken.getAsJsonObject("sites").getAsJsonObject("sachiel").getAsJsonArray("route").remove(1);
        rejects(()->SurfaceAngelPlanR52.parse(broken,"synthetic:surface"),"route gap");
        var underground=fixture();underground.getAsJsonObject("sites").getAsJsonObject("sachiel").getAsJsonArray("route").get(1).getAsJsonArray().set(1,new JsonPrimitive(-100));
        rejects(()->SurfaceAngelPlanR52.parse(underground,"synthetic:surface"),"vertical discontinuity");
        var near=fixture();var site=near.getAsJsonObject("sites").getAsJsonObject("sachiel");site.add("spawn",site.getAsJsonArray("route").get(4).deepCopy());
        rejects(()->SurfaceAngelPlanR52.parse(near,"synthetic:surface"),"near-port substitution");
        var marine=JsonParser.parseString("""
             {"original_cannon_UUIDs":["00000000-0000-0000-0000-000000000001","00000000-0000-0000-0000-000000000002"],
              "original_cannon_positions":[[1,2,3],[4,5,6]]}
             """).getAsJsonObject();
        check(TvMarineSiteR50.readCannons(marine).get(1).position().x==4,"declared original position consumed");
        var noSeats=marine.deepCopy();noSeats.remove("original_cannon_positions");rejects(()->TvMarineSiteR50.readCannons(noSeats),"no old cannon coordinates");
        var duplicate=marine.deepCopy();duplicate.getAsJsonArray("original_cannon_UUIDs").set(1,duplicate.getAsJsonArray("original_cannon_UUIDs").get(0));
        rejects(()->TvMarineSiteR50.readCannons(duplicate),"duplicate original cannon");
        var landings=JsonParser.parseString("""
            {"landings":{"0":{"point":[0,10,0],"receiver_id":"synthetic_shield"},
                         "1":{"point":[60,10,0],"receiver_id":"synthetic_shooter"}}}
            """).getAsJsonObject();
        check(TvEncounterSitesR45.readLandingsR52(landings).get(1).point().x==60,"explicit original upright landing root");
        rejects(()->TvEncounterSitesR45.readLandingsR52(new JsonObject()),"no old hero as landing fallback");
        var duplicateReceiver=landings.deepCopy();duplicateReceiver.getAsJsonObject("landings").getAsJsonObject("1").addProperty("receiver_id","synthetic_shield");
        rejects(()->TvEncounterSitesR45.readLandingsR52(duplicateReceiver),"two original deliveries cannot alias one receiver");
        var duplicateLanding=landings.deepCopy();duplicateLanding.getAsJsonObject("landings").getAsJsonObject("1").add("point",JsonParser.parseString("[0,10,0]"));
        rejects(()->TvEncounterSitesR45.readLandingsR52(duplicateLanding),"two EVA landing hulls require independent ports");
        var gun=JsonParser.parseString("""
            {"mesh_frame":{"translation":[3,4,5],"quaternion_xyzw":[0,0,0,1],"scale":5},"bounds_local":[[-1,0,-1],[1,10,1]],
             "aim_pivot_local":[0,0,0],"bore_local":[0,1,0],"muzzle_local":[0,10,0],"grip_left_local":[-1,2,0],"grip_right_local":[1,2,0]}
            """).getAsJsonObject();
        var geometry=com.projectseele.entity.YashimaCannonGeometryR52.parse(gun);var origin=new net.minecraft.world.phys.Vec3(100,20,200);var identity=new org.joml.Quaternionf();
        check(geometry.point(origin,identity,geometry.muzzle()).distanceTo(new net.minecraft.world.phys.Vec3(103,74,205))<1e-6,"same model frame gives actual world muzzle");
        var rotated=new org.joml.Quaternionf().rotationX((float)(Math.PI/2));
        check(geometry.boreWorld(rotated).distanceTo(new net.minecraft.world.phys.Vec3(0,0,1))<1e-6,"mounted barrel shares aim rotation");
        check(geometry.worldBounds(origin,rotated).inflate(.001).contains(geometry.point(origin,rotated,geometry.left())),"full hull contains transformed original grip");
        var restored=com.projectseele.entity.YashimaCannonGeometryR52.decode(com.projectseele.entity.YashimaCannonGeometryR52.encode(geometry));
        check(restored.point(origin,rotated,restored.muzzle()).distanceTo(geometry.point(origin,rotated,geometry.muzzle()))<1e-6,"complete gun frame NBT roundtrip");
        var wrongBore=gun.deepCopy();wrongBore.add("bore_local",JsonParser.parseString("[0,3,0]"));rejects(()->com.projectseele.entity.YashimaCannonGeometryR52.parse(wrongBore),"unmeasured non-unit barrel axis");
        var markerOutside=gun.deepCopy();markerOutside.add("muzzle_local",JsonParser.parseString("[0,20,0]"));rejects(()->com.projectseele.entity.YashimaCannonGeometryR52.parse(markerOutside),"muzzle cannot come from a different invisible cannon");
        System.out.println("R52 battle parameter synthetic checks: "+checks+" passed; no native/world acceptance claim.");
    }
}
