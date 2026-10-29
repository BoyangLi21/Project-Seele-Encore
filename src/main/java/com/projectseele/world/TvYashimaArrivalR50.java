package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.Files;
import java.util.*;
import net.minecraft.server.level.*;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** One original far landing, then separate real walks. No fallback flight or old hero pullback. */
@net.minecraftforge.fml.common.Mod.EventBusSubscriber(modid="projectseele")
public final class TvYashimaArrivalR50
{
    public record Next(Vec3 point,boolean hold){}
    private record Plan(List<Vec3> access,List<Vec3> cover,Vec3 equipment,Vec3 side,double radius){}
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    private static final Map<EvaUnit01Entity,Vec3> GUARD_POSITIONS_R54=new WeakHashMap<>();
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
    public static Vec3 shieldSide(ServerLevel level)
    {
        var p=plan(level);if(p==null)return null;
        var data=TvCampaignSavedData.get(level);var shooter=TvSortiesR32.assignedUnit(level,data,1);
        var boss=data.angel==null?null:level.getEntity(data.angel);
        if(shooter==null||boss==null)return p.side();
        Vec3 eye=EvaBodyPose.opticalEye(shooter,1),target=boss.getBoundingBox().getCenter();
        var gun=TvYashimaStationR52.gun(level);Vec3 muzzle=gun==null?eye:gun.muzzleR52();if(muzzle==null)muzzle=eye;
        Vec3 best=p.side();double widest=-1;
        for(int i=p.cover().size()-1;i>=0;i--)
        {
            Vec3 point=p.cover().get(i);
            double clear=Math.min(laneDistanceR54(point,eye,target),laneDistanceR54(point,muzzle,target));
            if(clear>widest){widest=clear;best=point;}if(clear>=64)return point;
        }
        return best;
    }
    static double laneDistanceR54(Vec3 point,Vec3 from,Vec3 to)
    {
        Vec3 line=to.subtract(from).multiply(1,0,1).normalize(),offset=point.subtract(from);
        return Math.abs(offset.x*line.z-offset.z*line.x);
    }
    static boolean enterCoverR54(boolean charging,int remaining,int beamTicks)
    {return beamTicks>0||charging&&remaining>0&&remaining<=20;}
    static Vec3 guardStepR54(Vec3 current,Vec3 goal)
    {Vec3 delta=goal.subtract(current);return delta.lengthSqr()<=64?goal:current.add(delta.normalize().scale(8));}

    @net.minecraftforge.eventbus.api.SubscribeEvent
    public static void guardTickR54(net.minecraftforge.event.TickEvent.ServerTickEvent event)
    {
        if(event.phase!=net.minecraftforge.event.TickEvent.Phase.END)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var data=TvCampaignSavedData.get(level);var assignment=data.sorties.get(0);
        if(!data.active.equals("ramiel")||!Set.of("approach","combat").contains(data.phase)||assignment==null||!assignment.npc)return;
        var eva=TvSortiesR32.assignedUnit(level,data,0);var shooter=TvSortiesR32.assignedUnit(level,data,1);
        var site=TvEncounterSitesR45.site(level,"ramiel").orElse(null);var side=shieldSide(level);
        if(eva==null||shooter==null||site==null||side==null||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()
                ||eva.hasActiveCarrierMotion()||EvaAirTransportR31.active(eva)||NervAirTransportRuntimeR52.ownsMotion(eva)
                ||StaffRecoveryR47.pending(level,0)||!EvaLogisticsDirector.status(level,0).phase().equals("DEPLOYED"))return;
        boolean wreck=EvaShutdownR30.wreck(eva);
        if(!wreck&&!TvMissionEquipmentR45.shieldAuthorized(eva))return;
        var boss=data.angel==null?null:level.getEntity(data.angel);
        boolean incoming=!wreck&&boss instanceof RamielEntity ramiel&&enterCoverR54(ramiel.isCharging(),
                TvYashimaCombatCommsR54.chargeRemainingR54(ramiel),ramiel.getBeamTicks());
        // This finite tactical slide owns only the original NPC defender.
        // Keep its real health/plate; a wreck must clear the gun lane too.
        eva.stopAutonomousR30();
        if(!wreck&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot)
        {
            eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_SHIELD_R45);
            eva.autonomousDriveR30(pilot,Vec3.ZERO,boss==null?site.angel():boss.getBoundingBox().getCenter(),false);
            eva.autonomousShieldBraceR47(pilot,incoming);
        }
        if(incoming)GUARD_POSITIONS_R54.computeIfAbsent(eva,key->defensivePositionR54(eva,shooter,boss,side,site.cover().y));
        else GUARD_POSITIONS_R54.remove(eva);
        Vec3 goal=incoming?GUARD_POSITIONS_R54.getOrDefault(eva,side):side;
        if(eva.position().subtract(goal).horizontalDistanceSqr()<.0025)return;
        if(wreck&&com.projectseele.physics.CombatBodyDynamics.active(eva))
        {
            EvaShutdownR30.physicalRest(eva,EvaBodyPose.sample(eva,0),eva.getBoundingBox());
            com.projectseele.physics.CombatBodyDynamics.cancel(eva);
        }
        if(!wreck&&eva.getPilotEntity() instanceof TrainingPilotEntity pilot)
            eva.autonomousDriveR30(pilot,Vec3.ZERO,boss==null?site.angel():boss.getBoundingBox().getCenter(),true);
        eva.setPos(guardStepR54(eva.position(),goal));eva.setDeltaMovement(Vec3.ZERO);eva.resetFallDistance();
    }
    private static Vec3 defensivePositionR54(EvaUnit01Entity eva,EvaUnit01Entity shooter,net.minecraft.world.entity.Entity boss,Vec3 side,double y)
    {
        var plate=EvaShieldRigR47.guardPlaneR54(eva);var gun=TvYashimaStationR52.gun((ServerLevel)eva.level());
        if(plate==null||gun==null||gun.muzzleR52()==null)return side;
        Vec3 target=boss.getBoundingBox().getCenter(),body=shooter.getEyePosition(),eye=EvaBodyPose.opticalEye(shooter,1),muzzle=gun.muzzleR52();
        Vec3 solved=guardPositionR54(plate,eva.position(),body,eye,muzzle,target,y);
        return solved==null?side:solved;
    }
    static Vec3 guardPositionR54(EvaShieldRigR47.GuardPlaneR54 plate,Vec3 root,Vec3 body,Vec3 eye,Vec3 muzzle,Vec3 target,double y)
    {
        Vec3 forward=target.subtract(body).multiply(1,0,1).normalize(),right=new Vec3(forward.z,0,-forward.x);
        // Solve translation from the actual plate centre, so shield size and
        // attachment offset do not turn a grid of EVA root guesses into misses.
        for(double along:new double[]{3,8,16})for(double edge:new double[]{0,.5,-.5})
        {
            Vec3 desired=body.add(forward.scale(along)).add(right.scale(edge*Math.max(0,plate.halfWidth()-2)));
            Vec3 shift=desired.subtract(plate.centre());shift=new Vec3(shift.x,y-root.y,shift.z);
            Vec3 point=root.add(shift);
            if(!plate.intersects(shift,target,body,1)||plate.intersects(shift,eye,target,-4)||plate.intersects(shift,muzzle,target,-2))continue;
            var hull=new net.minecraft.world.phys.AABB(point.add(-8.5,0,-8.5),point.add(8.5,60,8.5));
            if(hull.contains(eye)||hull.clip(eye,target).isPresent()||hull.contains(muzzle)||hull.clip(muzzle,target).isPresent())continue;
            return point;
        }
        return null;
    }
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
