package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaUnit01Entity;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** Actual foot contacts advance the installed approach route; no position or identity writes. */
public final class TvYashimaArrivalR50
{
    public record Next(Vec3 point,boolean hold) {}
    private record Plan(List<Vec3> access,List<Vec3> cover,List<Vec3> cannon,Map<Integer,Vec3> equipment,Vec3 side,double radius) {}
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    private static Vec3 vec(com.google.gson.JsonArray a)
    {return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static List<Vec3> points(com.google.gson.JsonArray a)
    {var out=new java.util.ArrayList<Vec3>();if(a!=null)for(var row:a)out.add(vec(row.getAsJsonArray()));return List.copyOf(out);}
    private static Plan plan(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,key->{
            try
            {
                var path=key.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_encounter_sites_r45.json");
                var row=JsonParser.parseString(Files.readString(path)).getAsJsonObject().getAsJsonObject("sites").getAsJsonObject("ramiel");
                var access=points(row.getAsJsonArray(row.has("eva_supply_access_route")?"eva_supply_access_route":"eva_access_ramp"));
                var cover=points(row.getAsJsonArray(row.has("cover_after_supply_route")?"cover_after_supply_route":"cover_access_ramp"));
                var cannon=points(row.getAsJsonArray("cannon_after_supply_route"));
                var equipment=new java.util.HashMap<Integer,Vec3>();
                if(row.has("equipment_approach"))for(var entry:row.getAsJsonObject("equipment_approach").entrySet())equipment.put(Integer.parseInt(entry.getKey()),vec(entry.getValue().getAsJsonArray()));
                Vec3 side=row.has("shield_wait_port")?vec(row.getAsJsonArray("shield_wait_port")):null;
                double radius=row.has("route_arrival_radius")?row.get("route_arrival_radius").getAsDouble():.9;
                if(access.size()<2||access.size()>256||radius<.5||radius>2||equipment.size()!=2||side==null
                        ||java.util.stream.Stream.concat(access.stream(),cover.stream()).anyMatch(v->!Double.isFinite(v.lengthSqr())))return Optional.empty();
                for(int n=1;n<access.size();n++)if(access.get(n).distanceTo(access.get(n-1))>8||Math.abs(access.get(n).y-access.get(n-1).y)>1.6)return Optional.empty();
                for(int n=1;n<cover.size();n++)if(cover.get(n).distanceTo(cover.get(n-1))>8||Math.abs(cover.get(n).y-cover.get(n-1).y)>1.6)return Optional.empty();
                for(int n=1;n<cannon.size();n++)if(cannon.get(n).distanceTo(cannon.get(n-1))>8||Math.abs(cannon.get(n).y-cannon.get(n-1).y)>1.6)return Optional.empty();
                return Optional.of(new Plan(access,cover,cannon,Map.copyOf(equipment),side,radius));
            }
            catch(Exception error){com.projectseele.ProjectSeele.LOGGER.error("Installed Yashima approach route unavailable",error);return Optional.empty();}
        }).orElse(null);
    }
    public static Vec3 shieldSide(ServerLevel level)
    {var p=plan(level);return p==null?null:p.side();}
    private static boolean at(EvaUnit01Entity eva,Vec3 point,double radius)
    {return eva.position().subtract(point).horizontalDistance()<=radius&&Math.abs(eva.getY()-point.y)<=1.35
            &&!EvaAirTransportR31.active(eva)&&!NervAirLiftR30.ownsMotion(eva)&&AirCradleClearanceR31.touchdownContact(eva)!=null;}
    /** Read the same current route and physical arrival required before NPC cannon tactics. */
    public static boolean npcCannonEmplacementReadyR50(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva)
    {
        var p=plan(level);var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);
        if(p==null||site==null||eva==null||eva.getUnitVariant()!=1||!p.equipment().containsKey(1))return false;
        var tag=eva.getPersistentData();
        return tag.getLong("R50YashimaRouteGeneration")==data.generationR43
                &&tag.getString("R50YashimaRouteLayout").equals(data.encounterLayoutR45)
                &&tag.getBoolean("R50YashimaRampDone")&&at(eva,site.hero(),1.5);
    }
    private static Next flight(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner,Vec3 point,Vec3 port)
    {
        if(at(eva,port,7))return new Next(null,false);
        String blocked=NervAirLiftR30.yieldBlockedPrepareToGroundR50(level,eva,owner.getUUID(),false);
        if(!blocked.isEmpty())
        {
            var tag=eva.getPersistentData();tag.putInt("R50YashimaRouteStall",0);
            tag.putDouble("R50YashimaRouteClosest",Double.MAX_VALUE);tag.putLong("R50YashimaFlightNext",level.getGameTime()+100);
            data.notice="原机起吊通道受阻、尚未挂载；保持原节点，驾驶员重新沿实际坡路前进。 "+blocked;data.setDirty();
            return new Next(point,false);
        }
        eva.stopAutonomousR30();
        if(EvaAirTransportR31.active(eva)||NervAirLiftR30.deliveryPendingR50(level,eva,owner.getUUID()))
        {data.notice="原机进山通路受阻，现有原运输机执行实际冠面交付 · "+NervAirLiftR30.status(level);return new Next(null,true);}
        if(NervAirLiftR30.busy(level)){data.notice="等待原运输机完成当前任务，原机保持地表接应。";return new Next(null,true);}
        var tag=eva.getPersistentData();long next=tag.getLong("R50YashimaFlightNext");
        if(level.getGameTime()<next&&next-level.getGameTime()<=100)return new Next(null,true);
        tag.putLong("R50YashimaFlightNext",level.getGameTime()+100);
        data.notice=NervAirLiftR30.request(owner,eva.getUnitVariant(),false,(int)Math.floor(port.x),(int)Math.floor(port.z));data.setDirty();return new Next(null,true);
    }
    public static Next next(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner,boolean equipped)
    {
        var p=plan(level);var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);
        if(p==null||site==null||owner==null){data.notice="原机进山坡路与盾侧接口尚未确认，原机保持原位。";return new Next(null,true);}
        var tag=eva.getPersistentData();
        if(tag.getLong("R50YashimaRouteGeneration")!=data.generationR43||!tag.getString("R50YashimaRouteLayout").equals(data.encounterLayoutR45))
        {
            tag.putLong("R50YashimaRouteGeneration",data.generationR43);tag.putString("R50YashimaRouteLayout",data.encounterLayoutR45);
            tag.putInt("R50YashimaRouteCursor",0);tag.putDouble("R50YashimaRouteClosest",Double.MAX_VALUE);tag.putInt("R50YashimaRouteStall",0);
            tag.putInt("R50YashimaCoverCursor",0);
            tag.putInt("R50YashimaCannonCursor",0);
            tag.putBoolean("R50YashimaRampDone",false);tag.putBoolean("R50YashimaCoverDone",false);
        }
        Vec3 equipment=p.equipment().get(eva.getUnitVariant());
        if(equipment==null)return new Next(null,true);
        var defender=TvSortiesR32.assignedUnit(level,data,0);
        if(eva.getUnitVariant()==1&&defender!=null&&!defenderReady(defender,data,p,site)
                &&eva.position().subtract(site.hero()).horizontalDistance()<65)
        {data.notice="零号机先沿原坡路到盾侧待命，射手在山脚安全接应段等候。";return new Next(null,true);}
        if(!tag.getBoolean("R50YashimaRampDone"))
        {
            if(at(eva,equipment,1.5)){tag.putBoolean("R50YashimaRampDone",true);tag.putInt("R50YashimaRouteCursor",0);}
            else
            {
                int cursor=Math.max(0,Math.min(tag.getInt("R50YashimaRouteCursor"),p.access().size()));
                while(cursor<p.access().size()&&at(eva,p.access().get(cursor),p.radius()))cursor++;
                tag.putInt("R50YashimaRouteCursor",cursor);
                if(cursor<p.access().size())return progress(level,data,eva,owner,p.access().get(cursor),equipment);
                if(at(eva,equipment,1.5)){tag.putBoolean("R50YashimaRampDone",true);tag.putInt("R50YashimaRouteCursor",0);}
                else return progress(level,data,eva,owner,equipment,equipment);
            }
        }
        if(!equipped)return new Next(null,false); // The real depot handoff now owns the stock.
        if(eva.getUnitVariant()==1)
        {
            var cover=TvSortiesR32.assignedUnit(level,data,0);
            if(cover!=null&&!defenderReady(cover,data,p,site))
            {data.notice="按原编成先让零号机完成盾侧待命，射手在实际领用区等候。";return new Next(null,true);}
            if(at(eva,site.hero(),1.5))return new Next(null,false);
            if(p.cannon().isEmpty()){data.notice="原供货区至炮冠的反向下降坡路尚未确认；不直下山体。";return new Next(null,true);}
            int cursor=Math.max(0,Math.min(tag.getInt("R50YashimaCannonCursor"),p.cannon().size()));
            while(cursor<p.cannon().size()&&at(eva,p.cannon().get(cursor),p.radius()))cursor++;
            tag.putInt("R50YashimaCannonCursor",cursor);
            if(cursor<p.cannon().size())return progress(level,data,eva,owner,p.cannon().get(cursor),site.hero());
            return at(eva,site.hero(),1.5)?new Next(null,false):progress(level,data,eva,owner,site.hero(),site.hero());
        }
        if(eva.getUnitVariant()!=0)return new Next(null,false);
        if(!tag.getBoolean("R50YashimaCoverDone"))
        {
            if(at(eva,p.side(),1.5))
            {tag.putBoolean("R50YashimaCoverDone",true);tag.putLong("R50YashimaCoverReadyGeneration",data.generationR43);return new Next(null,false);}
            int cursor=Math.max(0,Math.min(tag.getInt("R50YashimaCoverCursor"),p.cover().size()));
            while(cursor<p.cover().size()&&at(eva,p.cover().get(cursor),p.radius()))cursor++;
            tag.putInt("R50YashimaCoverCursor",cursor);
            if(cursor<p.cover().size())return progress(level,data,eva,owner,p.cover().get(cursor),p.side(),false);
            if(!at(eva,p.side(),1.5))
            {
                if(p.cover().isEmpty()){data.notice="原盾冠没有已验证步行接口，也不是空运冠；原机保持炮冠接应。";return new Next(null,true);}
                return progress(level,data,eva,owner,p.side(),p.side(),false);
            }
            tag.putBoolean("R50YashimaCoverDone",true);tag.putLong("R50YashimaCoverReadyGeneration",data.generationR43);
        }
        return new Next(null,false);
    }
    private static boolean defenderReady(EvaUnit01Entity cover,TvCampaignSavedData data,Plan plan,TvEncounterSitesR45.Site site)
    {
        if(cover.getPersistentData().getLong("R50YashimaCoverReadyGeneration")==data.generationR43)return true;
        if(ShieldCoverR48.authorized(cover)&&(at(cover,plan.side(),1.5)||at(cover,site.cover(),1.5)))
        {cover.getPersistentData().putLong("R50YashimaCoverReadyGeneration",data.generationR43);return true;}
        return false;
    }
    private static Next progress(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner,Vec3 point,Vec3 landing)
    {return progress(level,data,eva,owner,point,landing,true);}
    private static Next progress(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,ServerPlayer owner,Vec3 point,Vec3 landing,boolean flightAllowed)
    {
        var tag=eva.getPersistentData();double distance=eva.position().distanceTo(point);double closest=tag.getDouble("R50YashimaRouteClosest");
        String key=point.toString();
        if(!key.equals(tag.getString("R50YashimaRoutePoint"))||distance<closest-.2)
        {tag.putString("R50YashimaRoutePoint",key);tag.putDouble("R50YashimaRouteClosest",distance);tag.putInt("R50YashimaRouteStall",0);}
        else tag.putInt("R50YashimaRouteStall",tag.getInt("R50YashimaRouteStall")+1);
        if(tag.getInt("R50YashimaRouteStall")>240)
        {
            if(flightAllowed)return flight(level,data,eva,owner,point,landing);
            data.notice="原17宽盾机在已施工侧坡节点受阻；小盾冠没有空投许可，保持原机与原路线待检查。";return new Next(null,true);
        }
        return new Next(point,false);
    }
    public static void clear(ServerLevel level){CACHE.remove(level);}
    public static void recovered(EvaUnit01Entity eva)
    {
        var tag=eva.getPersistentData();
        for(String key:List.of("R50YashimaRouteGeneration","R50YashimaRouteLayout","R50YashimaRouteCursor","R50YashimaCoverCursor","R50YashimaCannonCursor",
                "R50YashimaRampDone","R50YashimaCoverDone","R50YashimaCoverReadyGeneration","R50YashimaRouteClosest","R50YashimaRouteStall","R50YashimaRoutePoint"))tag.remove(key);
    }
    private TvYashimaArrivalR50(){}
}
