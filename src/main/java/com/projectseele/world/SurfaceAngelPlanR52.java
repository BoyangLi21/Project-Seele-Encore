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
    private static final Map<ServerLevel,Optional<Plan>> CACHE=new WeakHashMap<>();
    public static boolean handles(String chapter)
    {
        return NervRouteRuntimeR52.mapRebuildEnabledR52()
                && (chapter.equals("sachiel") || chapter.equals("shamshel"));
    }
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
    public static Optional<Plan> plan(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);if(!Files.isRegularFile(file))return Optional.empty();
            try{return Optional.of(parse(JsonParser.parseString(Files.readString(file)).getAsJsonObject(),l.dimension().location().toString()));}
            catch(Exception failure){ProjectSeele.LOGGER.error("Installed R52 surface assault rejected",failure);return Optional.empty();}
        });
    }
    public static Optional<Site> site(ServerLevel level,String chapter){return plan(level).map(p->p.sites().get(chapter));}
    public static String startBlocker(ServerLevel level,String chapter)
    {
        if(!handles(chapter))return "";
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
