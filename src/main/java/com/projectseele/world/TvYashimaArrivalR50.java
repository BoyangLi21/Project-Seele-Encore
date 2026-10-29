package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.Files;
import java.util.*;
import net.minecraft.server.level.*;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** One original far landing, then separate real walks. No fallback flight or old hero pullback. */
public final class TvYashimaArrivalR50
{
    public record Next(Vec3 point,boolean hold){}
    private record Plan(List<Vec3> access,List<Vec3> cover,Vec3 equipment,Vec3 side,double radius){}
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    private static List<Vec3> points(JsonArray rows)
    {var out=new ArrayList<Vec3>();if(rows!=null)for(var row:rows)out.add(YashimaCannonGeometryR52.vector(row.getAsJsonArray()));return List.copyOf(out);}
    private static void route(List<Vec3> points)
    {if(points.size()<2||points.size()>512)throw new IllegalArgumentException("Explicit continuous shield walk required");for(int n=1;n<points.size();n++)if(points.get(n).distanceTo(points.get(n-1))>8||Math.abs(points.get(n).y-points.get(n-1).y)>1.6)throw new IllegalArgumentException("Shield walk continuity rejected");}
    private static Plan plan(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,key->{try{
            var path=key.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_encounter_sites_r45.json");var row=JsonParser.parseString(Files.readString(path)).getAsJsonObject().getAsJsonObject("sites").getAsJsonObject("ramiel");
            var site=TvEncounterSitesR45.site(level,"ramiel").orElseThrow();var access=points(row.getAsJsonObject("eva_access_routes").getAsJsonArray("0"));var cover=points(row.getAsJsonArray("cover_after_supply_route"));route(access);route(cover);
            var equipment=YashimaCannonGeometryR52.vector(row.getAsJsonObject("equipment_approach").getAsJsonArray("0"));var side=YashimaCannonGeometryR52.vector(row.getAsJsonArray("shield_wait_port"));double radius=row.get("route_arrival_radius").getAsDouble();
            if(!Double.isFinite(radius)||radius<.5||radius>2||access.get(0).distanceTo(site.landings().get(0).point())>2
                    ||access.get(access.size()-1).distanceTo(equipment)>2||cover.get(0).distanceTo(equipment)>2||cover.get(cover.size()-1).distanceTo(side)>2)throw new IllegalArgumentException("Original shield landing/supply/side endpoints rejected");
            // The old waiting point left the full-size upright shield beside
            // the optical/fire line. Stop earlier on the same authored walk,
            // far enough to keep both the airframe and its plate in the flank.
            Vec3 line=site.angel().subtract(site.hero()).multiply(1,0,1).normalize();
            int flank=cover.size()-1;double widest=-1;
            for(int i=cover.size()-1;i>=0;i--)
            {
                Vec3 offset=cover.get(i).subtract(site.hero());
                double clearance=Math.abs(offset.x*line.z-offset.z*line.x);
                if(clearance>widest){widest=clearance;flank=i;}
                if(clearance>=64){flank=i;break;}
            }
            side=cover.get(flank);cover=List.copyOf(cover.subList(0,flank+1));
            return Optional.of(new Plan(access,cover,equipment,side,radius));
        }catch(Exception error){com.projectseele.ProjectSeele.LOGGER.error("Installed separate far shield walk unavailable",error);return Optional.empty();}}).orElse(null);
    }
    public static Vec3 shieldSide(ServerLevel level){var p=plan(level);return p==null?null:p.side();}
    public static String startBlockerR52(ServerLevel level)
    {return plan(level)==null?"零号机独立落点、原盾架与实际盾位的步行接口尚未接通。":"";}
    private static boolean at(EvaUnit01Entity eva,Vec3 point,double radius)
    {return eva.position().subtract(point).horizontalDistance()<=radius&&Math.abs(eva.getY()-point.y)<=1.35&&!EvaAirTransportR31.active(eva)&&!NervAirTransportRuntimeR52.ownsMotion(eva)&&AirCradleClearanceR31.touchdownContact(eva)!=null;}
    public static boolean npcCannonEmplacementReadyR50(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva)
    {return eva!=null&&eva.getUnitVariant()==1&&TvYashimaTransitR52.landed(level,data,eva)&&TvYashimaStationR52.fireBlocker(eva).isEmpty();}
    public static Next next(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner,boolean equipped)
    {
        if(!TvYashimaTransitR52.landed(level,data,eva))return new Next(null,true);
        if(eva.getUnitVariant()==1)return TvYashimaStationR52.npcArrival(level,data,eva,owner);
        var p=plan(level);if(p==null||owner==null||eva.getUnitVariant()!=0){data.notice="零号机独立落点至原盾架和盾位的实际通路尚未接通。";return new Next(null,true);}
        var tag=eva.getPersistentData();
        if(tag.getLong("R50YashimaRouteGeneration")!=data.generationR43||!tag.getString("R50YashimaRouteLayout").equals(data.encounterLayoutR45))
        {tag.putLong("R50YashimaRouteGeneration",data.generationR43);tag.putString("R50YashimaRouteLayout",data.encounterLayoutR45);tag.putInt("R50YashimaRouteCursor",0);tag.putInt("R50YashimaCoverCursor",0);tag.putBoolean("R50YashimaRampDone",false);tag.putBoolean("R50YashimaCoverDone",false);}
        // A shield issued in the hangar already arrived with this same pilot.
        // Walk from its landing straight along the flank to standby instead of
        // visiting the now-empty supply rack and walking the entire loop again.
        if(equipped&&!tag.getBoolean("R50YashimaRampDone"))
        {tag.putBoolean("R50YashimaRampDone",true);tag.putInt("R50YashimaCoverCursor",p.cover().size()-1);}
        if(!tag.getBoolean("R50YashimaRampDone"))
        {if(at(eva,p.equipment(),1.5))tag.putBoolean("R50YashimaRampDone",true);else return follow(eva,p.access(),"R50YashimaRouteCursor",p.radius());}
        if(!equipped)return new Next(null,false); // The actual finite original shield rack owns its handoff.
        if(!tag.getBoolean("R50YashimaCoverDone"))
        {if(at(eva,p.side(),1.5)){tag.putBoolean("R50YashimaCoverDone",true);tag.putLong("R50YashimaCoverReadyGeneration",data.generationR43);}else return follow(eva,p.cover(),"R50YashimaCoverCursor",p.radius());}
        return new Next(null,false);
    }
    private static Next follow(EvaUnit01Entity eva,List<Vec3> points,String key,double radius)
    {var tag=eva.getPersistentData();int cursor=Math.max(0,Math.min(tag.getInt(key),points.size()-1));while(cursor<points.size()-1&&at(eva,points.get(cursor),radius))cursor++;tag.putInt(key,cursor);return new Next(points.get(cursor),false);}
    public static void recovered(EvaUnit01Entity eva)
    {for(String key:List.of("R50YashimaRouteGeneration","R50YashimaRouteLayout","R50YashimaRouteCursor","R50YashimaCoverCursor","R50YashimaRampDone","R50YashimaCoverDone","R50YashimaCoverReadyGeneration"))eva.getPersistentData().remove(key);}
    public static void clear(ServerLevel level){CACHE.remove(level);}
    private TvYashimaArrivalR50(){}
}
