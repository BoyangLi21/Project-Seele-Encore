package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** Installed personnel arrivals share the machinery directory's world identity.
 * A missing or stale migrated directory never falls back to retired coordinates. */
public final class NervTravelDirectoryR52
{
    public static final String FILE = "r52/travel.json";
    public static final String SCHEMA = "projectseele.r52.travel-directory.v1";
    public record Arrival(String key,String label,String component,String entryId,Vec3 position,float yaw) {}
    public record Document(long epoch,String directoryFingerprint,List<Arrival> arrivals)
    {
        public Arrival arrival(String key)
        {return arrivals.stream().filter(a->a.key().equals(canonicalKey(key))).findFirst().orElse(null);}
    }
    private static final class State
    {
        final NervManifestPollR52 poll = new NervManifestPollR52();
        long epoch;
        String fingerprint = "";
        Document document;
    }
    private static final Map<ServerLevel,State> STATES = new WeakHashMap<>();

    public static String canonicalKey(String key)
    {return "hanger".equals(key)?"hangar":key;}

    public static boolean applies(ServerLevel level)
    {
        return level!=null&&level.dimension().equals(FacilitySchemaV2.DIMENSION)
                &&(NervRouteRuntimeR52.claimed(level)||FacilityWorldPolicy.markerPresent(level.getServer(),FILE));
    }

    public static Document installed(ServerLevel level)
    {
        if(!applies(level))return null;
        State state=STATES.computeIfAbsent(level,ignored->new State());
        long epoch=NervRouteRuntimeR52.commissioningEpoch(level);
        String fingerprint=NervRouteRuntimeR52.directoryFingerprint(level);
        if(state.epoch!=epoch||!state.fingerprint.equals(fingerprint))
        {
            state.epoch=epoch;state.fingerprint=fingerprint;
            state.document=null;state.poll.invalidate();
        }
        if(!NervRouteRuntimeR52.claimed(level)||epoch<=0||!fingerprint.matches("[0-9a-f]{64}"))
        {state.document=null;return null;}
        int tick=level.getServer().getTickCount();
        try
        {
            var world=level.getServer().getWorldPath(LevelResource.ROOT).toRealPath();
            var file=world.resolve(FILE);
            var probe=state.poll.probe(file,tick);
            if(!probe.available()){state.document=null;return null;}
            if(probe.changed())
            {
                state.document=null;
                if(probe.size()>262144||!file.toRealPath().startsWith(world))
                    throw new IllegalArgumentException("Bounded arrival directory inside this actual world required");
                String text=Files.readString(file);
                state.document=parse(JsonParser.parseString(text).getAsJsonObject(),epoch,fingerprint);
            }
            return state.document;
        }
        catch(Exception failure)
        {
            state.document=null;
            if(state.poll.warningDue(failure.toString(),tick))
                ProjectSeele.LOGGER.warn("Migrated personnel arrivals held; retired coordinates remain disabled: {}",failure.toString());
            return null;
        }
    }

    public static Document parse(JsonObject root,long epoch,String fingerprint)
    {
        require(SCHEMA.equals(root.get("schema").getAsString())
                &&"projectseele:geofront".equals(root.get("dimension").getAsString())
                &&root.get("installed").getAsBoolean()&&root.get("complete_replacement").getAsBoolean(),
                "Installed complete arrival directory required");
        require(epoch>0&&fingerprint.matches("[0-9a-f]{64}")
                &&root.get("epoch").getAsBigDecimal().longValueExact()==epoch
                &&fingerprint.equals(root.get("directory_fingerprint").getAsString()),
                "Arrival directory belongs to a different world installation");
        Map<String,Arrival> arrivals=new LinkedHashMap<>();
        var rows=root.getAsJsonArray("destinations");
        require(rows!=null&&!rows.isEmpty()&&rows.size()<=128,"Bounded explicit arrival list required");
        for(var value:rows)
        {
            var row=value.getAsJsonObject();String key=row.get("key").getAsString();
            String label=row.get("label").getAsString(),component=row.get("component").getAsString(),entry=row.get("entry_id").getAsString();
            require(key.matches("[a-z][a-z0-9_]{0,63}")&&key.equals(canonicalKey(key)),"Unique canonical arrival key required");
            require(!label.isBlank()&&label.length()<=100&&!label.contains("\n")&&!label.contains("\r")
                    &&component.matches("[a-z][a-z0-9_./-]{0,95}")&&entry.matches("[A-Za-z0-9_./-]{1,128}"),
                    "Arrival must name its actual component and entrance");
            var point=row.getAsJsonArray("position");require(point!=null&&point.size()==3,"Explicit three-axis arrival required");
            Vec3 position=new Vec3(point.get(0).getAsDouble(),point.get(1).getAsDouble(),point.get(2).getAsDouble());
            double yaw=row.get("yaw").getAsDouble();
            require(Double.isFinite(position.lengthSqr())&&Math.abs(position.x)<29999984&&Math.abs(position.z)<29999984
                    &&Math.abs(position.y)<4096&&Double.isFinite(yaw)&&Math.abs(yaw)<=360,"Finite in-world arrival and heading required");
            require(arrivals.putIfAbsent(key,new Arrival(key,label,component,entry,position,(float)yaw))==null,"Duplicate arrival key");
        }
        require(arrivals.keySet().containsAll(List.of("entrance","command","hangar","station","dogma","observation")),
                "Installed headquarters, hangar, Terminal and station entrances required");
        return new Document(epoch,fingerprint,List.copyOf(arrivals.values()));
    }
    private static void require(boolean value,String reason)
    {if(!value)throw new IllegalArgumentException(reason);}
    private NervTravelDirectoryR52() {}
}
