package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import java.nio.file.Files;
import java.util.Map;
import java.util.HashMap;
import java.util.WeakHashMap;
import java.util.Optional;

/** Installed measured encounter sites; neither terrain nor story-progress writer. */
public final class TvEncounterSitesR45
{
    public record Landing(Vec3 point,String receiver){}
    public record Site(String id,Vec3 hero,Vec3 angel,Vec3 cover,float yaw,
            boolean cityInterlock,boolean geometryValidated,boolean modelReady,
            String visibility,double attackRange,int primaryUnit,Vec3 support,boolean supportValidated,float modelScale,Map<Integer,Landing> landings)
    {
        public Site{landings=Map.copyOf(landings);}
        public Site(String id,Vec3 hero,Vec3 angel,Vec3 cover,float yaw,
                boolean cityInterlock,boolean geometryValidated,boolean modelReady,
                String visibility,double attackRange,int primaryUnit)
        {this(id,hero,angel,cover,yaw,cityInterlock,geometryValidated,modelReady,visibility,attackRange,primaryUnit,null,false,1,Map.of());}
        public Site(String id,Vec3 hero,Vec3 angel,Vec3 cover,float yaw,boolean cityInterlock,boolean geometryValidated,boolean modelReady,
                String visibility,double attackRange,int primaryUnit,Vec3 support,boolean supportValidated)
        {this(id,hero,angel,cover,yaw,cityInterlock,geometryValidated,modelReady,visibility,attackRange,primaryUnit,support,supportValidated,1,Map.of());}
        public Site(String id,Vec3 hero,Vec3 angel,Vec3 cover,float yaw,boolean cityInterlock,boolean geometryValidated,boolean modelReady,
                String visibility,double attackRange,int primaryUnit,Vec3 support,boolean supportValidated,float modelScale)
        {this(id,hero,angel,cover,yaw,cityInterlock,geometryValidated,modelReady,visibility,attackRange,primaryUnit,support,supportValidated,modelScale,Map.of());}
        public double separation(){return hero.distanceTo(angel);}
        public boolean supportReady()
        {return supportValidated&&support!=null&&finite(support)&&support.distanceTo(hero)>=30&&support.distanceTo(cover)>=30;}
        public String fingerprint()
        {
            String value=id+"|"+hero+"|"+angel+"|"+cover+"|"+yaw+"|"+cityInterlock+"|"+visibility+"|"+attackRange+"|"+primaryUnit+"|scale="+modelScale;
            if(support!=null)value+="|support="+support;
            for(int unit:new int[]{0,1})if(landings.containsKey(unit))value+="|landing"+unit+"="+landings.get(unit);
            try{return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)));}
            catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
        }
    }
    private static final Map<ServerLevel,Map<String,Site>> CACHE=new WeakHashMap<>();
    private static Vec3 vec(com.google.gson.JsonArray row)
    {return new Vec3(row.get(0).getAsDouble(),row.get(1).getAsDouble(),row.get(2).getAsDouble());}
    public static Map<Integer,Landing> readLandingsR52(com.google.gson.JsonObject row)
    {
        var values=row.getAsJsonObject("landings");if(values==null||values.size()!=2)throw new IllegalArgumentException("Two original independent Yashima landing roots required");
        var result=new HashMap<Integer,Landing>();for(int unit:new int[]{0,1})
        {var r=values.getAsJsonObject(Integer.toString(unit));var point=vec(r.getAsJsonArray("point"));String receiver=r.get("receiver_id").getAsString();
            if(!finite(point)||!receiver.matches("[a-z0-9_./-]{1,128}"))throw new IllegalArgumentException("Explicit upright landing root/receiver rejected");result.put(unit,new Landing(point,receiver));}
        if(result.get(0).receiver().equals(result.get(1).receiver())||result.get(0).point().distanceTo(result.get(1).point())<48)
            throw new IllegalArgumentException("Original two EVA deliveries must use independent real ports");return Map.copyOf(result);
    }
    public static Optional<Site> site(ServerLevel level,String chapter)
    {
        return Optional.ofNullable(CACHE.computeIfAbsent(level,l ->
        {
            var path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_encounter_sites_r45.json");
            if(!Files.isRegularFile(path))return Map.of();
            try
            {
                var json=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
                if(json.get("schema").getAsInt()!=45||!json.get("dimension").getAsString().equals(l.dimension().location().toString()))
                    throw new IllegalArgumentException("Encounter site identity");
                Map<String,Site> result=new HashMap<>();
                for(var entry:json.getAsJsonObject("sites").entrySet())
                {
                    if(!entry.getKey().equals("ramiel")&&!entry.getKey().equals("gaghiel"))continue;
                    var r=entry.getValue().getAsJsonObject();
                    var site=new Site(r.get("id").getAsString(),vec(r.getAsJsonArray("hero")),vec(r.getAsJsonArray("angel")),
                            vec(r.getAsJsonArray("cover")),r.get("yaw").getAsFloat(),r.get("requires_retracted_city").getAsBoolean(),
                            r.get("geometry_validated").getAsBoolean(),r.get("model_ready").getAsBoolean(),r.get("visibility").getAsString(),
                            r.get("attack_range").getAsDouble(),r.get("primary_unit").getAsInt(),
                            r.has("support_port")?vec(r.getAsJsonArray("support_port")):null,
                            r.has("support_port_validated")&&r.get("support_port_validated").getAsBoolean(),
                            r.has("model_scale")?r.get("model_scale").getAsFloat():1F,entry.getKey().equals("ramiel")?readLandingsR52(r):Map.of());
                    if(!finite(site.hero())||!finite(site.angel())||!finite(site.cover())||!Float.isFinite(site.yaw())
                            ||!Float.isFinite(site.modelScale())||site.modelScale()<(entry.getKey().equals("ramiel")?4:1)||site.modelScale()>16
                            ||!Double.isFinite(site.separation())||site.separation()<30||site.separation()>4096
                            ||!Double.isFinite(site.attackRange())||site.attackRange()<8||site.attackRange()>4096
                            ||site.primaryUnit()!=(entry.getKey().equals("ramiel")?1:2)
                            ||site.support()!=null&&(!finite(site.support())||site.support().distanceTo(site.hero())<30
                            ||site.support().distanceTo(site.cover())<30||site.support().distanceTo(site.hero())>512)
                            ||!(site.visibility().equals("native_tracking")||site.visibility().equals("remote_actual_entity_v1")))
                        throw new IllegalArgumentException("Encounter site range/unit");
                    result.put(entry.getKey(),site);
                }
                return Map.copyOf(result);
            }
            catch(Exception failure)
            {ProjectSeele.LOGGER.error("Measured TV encounter sites rejected; no fallback terrain/targets generated",failure);return Map.of();}
        }).get(chapter));
    }
    private static boolean finite(Vec3 v)
    {return Double.isFinite(v.x)&&Double.isFinite(v.y)&&Double.isFinite(v.z);}
    public static String startBlocker(ServerLevel level,String chapter)
    {
        var site=site(level,chapter).orElse(null);
        if(site==null)return "作战区域仍在准备中。";
        if(!site.geometryValidated())return "作战阵地仍在整备中。";
        if(!site.modelReady())return "目标确认仍在准备中。";
        return "";
    }
    private TvEncounterSitesR45(){}
}
