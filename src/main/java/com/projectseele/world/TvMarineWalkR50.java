package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;

/** Finite real ramp waypoints; movement remains EVA's ordinary collision-authoritative travel. */
public final class TvMarineWalkR50
{
    private record Route(String id,List<Vec3> points,double width) {}
    private static final Map<ServerLevel,Optional<Route>> CACHE=new WeakHashMap<>();
    private static Route route(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,l->{
            try
            {
                var path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_marine_site_r50.json");
                var root=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(!root.has("installed")||!root.get("installed").getAsBoolean()||!root.has("eva_underwater_route"))return Optional.empty();
                var row=root.getAsJsonObject("eva_underwater_route");if(!row.get("installed").getAsBoolean())return Optional.empty();
                var points=new java.util.ArrayList<Vec3>();
                for(var raw:row.getAsJsonArray("waypoints"))
                {
                    var a=raw.getAsJsonArray();var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
                    if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z)||p.y<16||p.y>80)throw new IllegalArgumentException("Marine walking waypoint");
                    points.add(p);
                }
                double width=row.get("width").getAsDouble();
                if(!Double.isFinite(width)||width<17||width>48||points.size()<2||points.size()>128)throw new IllegalArgumentException("Marine walking route width/count");
                var site=TvMarineSiteR50.site(level).orElse(null);
                if(site==null||points.stream().anyMatch(p->p.distanceTo(site.center())>256))throw new IllegalArgumentException("Marine walking route leaves installed encounter volume");
                return Optional.of(new Route(root.get("id").getAsString(),List.copyOf(points),width));
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Finite installed marine walking route unavailable",failure);return Optional.empty();}
        }).orElse(null);
    }
    /** A goal is returned only after the actual full route feet have reached preceding points. */
    public static Vec3 approachGoal(ServerLevel level,TvCampaignSavedData campaign,EvaUnit01Entity eva,Vec3 intercept)
    {
        var route=route(level);if(route==null)return null;
        var tag=eva.getPersistentData();
        if(tag.getLong("MarineWalkGenerationR50")!=campaign.generationR43||!tag.getString("MarineWalkSiteR50").equals(route.id()))
        {
            tag.putLong("MarineWalkGenerationR50",campaign.generationR43);tag.putString("MarineWalkSiteR50",route.id());tag.putInt("MarineWalkIndexR50",0);
        }
        int index=Math.max(0,Math.min(route.points().size(),tag.getInt("MarineWalkIndexR50")));
        if(index<route.points().size())
        {
            Vec3 point=route.points().get(index);
            if(!registeredBearing(level,point))return null;
            if(eva.position().subtract(point).horizontalDistance()<=5&&Math.abs(eva.getY()-point.y)<=3
                    &&AirCradleClearanceR31.touchdownContact(eva)!=null)
            {index++;tag.putInt("MarineWalkIndexR50",index);}
            if(index<route.points().size())return route.points().get(index);
        }
        return intercept;
    }
    /** Verify a declared floor using blocks and collision shapes, never a nearby empty space. */
    private static boolean registeredBearing(ServerLevel level,Vec3 point)
    {
        int measured=0;
        for(int dx:new int[]{-6,0,6})for(int dz:new int[]{-6,0,6})
        {
            boolean supported=false;
            for(int y=(int)Math.floor(point.y+7);y>=(int)Math.floor(point.y-9);y--)
            {
                var pos=BlockPos.containing(point.x+dx,y,point.z+dz);if(!level.hasChunkAt(pos))return false;
                var shape=level.getBlockState(pos).getCollisionShape(level,pos);
                if(!shape.isEmpty()&&y+shape.max(Direction.Axis.Y)<=point.y+8){supported=true;break;}
            }
            if(supported)measured++;
        }
        return measured==9;
    }
    public static void clear(ServerLevel level){CACHE.remove(level);}
    private TvMarineWalkR50(){}
}
