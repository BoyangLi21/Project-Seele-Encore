package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** Root-installed surface routes. Missing construction never selects the retired battle site. */
public final class SurfaceAngelPlanR52
{
    public static final String FILE="surface_angel_assault_r52.json";
    public record Site(String chapter,Vec3 spawn,List<Vec3> route,Vec3 intercept,float yaw,
            double speed,double arrivalRadius,double engagementRange,int attackPeriod,float armorDamage) {}
    public record Plan(String id,String armorColumn,String fingerprint,Map<String,Site> sites) {}
    public enum RoutingR52 { LEGACY,HOLD,SURFACE }
    private record DeclarationR52(String dimension,Optional<Plan> plan){}
    private static final Map<ServerLevel,DeclarationR52> CACHE=new WeakHashMap<>();
    static RoutingR52 routingR52(String chapter,boolean declared,boolean claimed,boolean ready)
    {
        if(!"sachiel".equals(chapter)&&!"shamshel".equals(chapter)||!declared&&!claimed)return RoutingR52.LEGACY;
        return claimed&&ready?RoutingR52.SURFACE:RoutingR52.HOLD;
    }
    static boolean declarationMatchesR52(String declaredDimension,String actualDimension,boolean geofrontGenerator)
    {return declaredDimension.equals(actualDimension)||declaredDimension.isEmpty()&&geofrontGenerator;}
    private static boolean claimedForRoutingR52(ServerLevel level)
    {
        if(NervRouteRuntimeR52.claimed(level))return true;
        // Read an existing claim even while the global installation switch
        // is disabled; that switch cannot send a migrated save to old spawns.
        var saved=level.getDataStorage().get(NervRouteRuntimeStateR52::load,NervRouteRuntimeStateR52.NAME);
        return saved!=null&&saved.claimed();
    }
    public static boolean declared(ServerLevel level)
    {
        if(claimedForRoutingR52(level))return true;
        var declaration=declarationR52(level);
        return declaration!=null&&declarationMatchesR52(declaration.dimension(),level.dimension().location().toString(),level.getChunkSource().getGenerator() instanceof GeoFrontBoundedChunkGenerator);
    }
    public static RoutingR52 routingR52(ServerLevel level,String chapter)
    {boolean claimed=claimedForRoutingR52(level);return routingR52(chapter,claimed||declared(level),claimed,NervRouteRuntimeR52.ready(level));}
    public static boolean handles(ServerLevel level,String chapter){return routingR52(level,chapter)!=RoutingR52.LEGACY;}
    private static Vec3 vec(com.google.gson.JsonArray a)
    {
        if(a==null||a.size()!=3)throw new IllegalArgumentException("Explicit three-coordinate point required");
        var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z)||Math.abs(p.x)>29_000_000||Math.abs(p.z)>29_000_000)
            throw new IllegalArgumentException("Non-finite surface route point");
        return p;
    }
    /** Pure contract validation; it makes no construction or native-clearance claim. */
    public static Plan parse(JsonObject root,String dimension)
    {
        if(root.get("schema").getAsInt()!=52||!root.get("dimension").getAsString().equals(dimension)
                ||!root.get("installed").getAsBoolean()||!root.get("geometry_validated").getAsBoolean())
            throw new IllegalArgumentException("Surface assault must be explicitly installed and measured in this dimension");
        String id=root.get("id").getAsString(),armor=root.get("armor_column").getAsString();
        if(id.isBlank()||armor.isBlank())throw new IllegalArgumentException("Surface route and armor identities required");
        var sites=new LinkedHashMap<String,Site>();
        for(String chapter:List.of("sachiel","shamshel"))
        {
            var o=root.getAsJsonObject("sites").getAsJsonObject(chapter);if(o==null)throw new IllegalArgumentException("Both original surface encounters required");
            Vec3 spawn=vec(o.getAsJsonArray("spawn")),intercept=vec(o.getAsJsonArray("intercept"));
            var route=new ArrayList<Vec3>();for(var p:o.getAsJsonArray("route"))route.add(vec(p.getAsJsonArray()));
            double speed=o.get("speed").getAsDouble(),radius=o.get("arrival_radius").getAsDouble(),range=o.get("engagement_range").getAsDouble();
            float yaw=o.get("yaw").getAsFloat(),damage=o.get("armor_damage").getAsFloat();int period=o.get("attack_period_ticks").getAsInt();
            if(route.size()<2||route.size()>512||spawn.distanceTo(route.get(0))>2||spawn.distanceTo(route.get(route.size()-1))<160
                    ||!Double.isFinite(speed)||speed<.05||speed>1.2||!Double.isFinite(radius)||radius<.3||radius>6
                    ||!Double.isFinite(range)||range<48||range>512||!Float.isFinite(yaw)||!Float.isFinite(damage)||damage<=0||damage>1000||period<60||period>1200)
                throw new IllegalArgumentException("Invalid bounded remote spawn, route or attack parameters");
            for(int i=1;i<route.size();i++)if(route.get(i).distanceTo(route.get(i-1))>64
                    ||chapter.equals("sachiel")&&Math.abs(route.get(i).y-route.get(i-1).y)>2)
                throw new IllegalArgumentException("Surface route is not continuous");
            sites.put(chapter,new Site(chapter,spawn,List.copyOf(route),intercept,yaw,speed,radius,range,period,damage));
        }
        try
        {
            String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(root.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            return new Plan(id,armor,hash,Map.copyOf(sites));
        }
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    private static DeclarationR52 declarationR52(ServerLevel level)
    {
        var cached=CACHE.get(level);if(cached!=null)return cached;
        var file=level.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);if(!Files.isRegularFile(file))return null;
        String dimension="";Optional<Plan> plan=Optional.empty();
        try
        {
            var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();dimension=root.get("dimension").getAsString();
            if(dimension.equals(level.dimension().location().toString()))plan=Optional.of(parse(root,dimension));
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("Declared R52 surface assault is held; no legacy-site fallback",failure);}
        var declaration=new DeclarationR52(dimension,plan);CACHE.put(level,declaration);return declaration;
    }
    public static Optional<Plan> plan(ServerLevel level){var declaration=declarationR52(level);return declaration==null?Optional.empty():declaration.plan();}
    public static Optional<Site> site(ServerLevel level,String chapter){return plan(level).map(p->p.sites().get(chapter));}
    public static String startBlocker(ServerLevel level,String chapter)
    {
        var routing=routingR52(level,chapter);if(routing==RoutingR52.LEGACY)return "";
        if(routing==RoutingR52.HOLD)return "新地图已声明，机库、发射通道与原编队的运行安装尚未就绪；作战保持等待。";
        var plan=plan(level).orElse(null);var armor=NervArmorColumnR50.plan(level).orElse(null);
        if(plan==null)return "远端使徒与地表进攻路线尚未完成实际施工和安装。";
        if(armor==null||!armor.installed()||!armor.id().equals(plan.armorColumn()))return "本场原地表装甲井尚未安装或身份不符。";
        int surface=armor.layers().get(0).maxY();
        if(plan.sites().get(chapter).route().stream().anyMatch(p->p.y<surface-2))return "前两使徒路线必须保持地表，不能进入地下装甲柱。";
        return "";
    }
    public static void clear(ServerLevel level){CACHE.remove(level);}
    private SurfaceAngelPlanR52(){}
}
