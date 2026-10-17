package com.projectseele.world;

import com.google.gson.*;
import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import com.supermartijn642.movingelevators.elevator.ElevatorGroupCapability;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** The same native cabin changes shaft axis beneath the original basement. */
public final class NervPersonnelTransferR53
{
    public static final String TAG="SeeleHorizontalTransferR53";
    public record PathSpec(String id,int upperX,int upperZ,int lowerX,int lowerZ,int transferY)
    {
        public PathSpec
        {
            if(id.isBlank()||upperX==lowerX&&upperZ==lowerZ)throw new IllegalArgumentException("Two declared personnel lift axes required");
        }
        public boolean axis(int x,int z){return x==upperX&&z==upperZ||x==lowerX&&z==lowerZ;}
        public BlockPos controller(int y){return new BlockPos(y>=transferY?upperX:lowerX,y,y>=transferY?upperZ:lowerZ);}
        public Vec3 offset(double lowerFraction){return new Vec3((upperX-lowerX)*(1-lowerFraction),0,(upperZ-lowerZ)*(1-lowerFraction));}
        public int duration(double peakSpeed){return Math.max(1,(int)Math.ceil(1.5*Math.hypot(upperX-lowerX,upperZ-lowerZ)/Math.max(.01,peakSpeed)));}
        public CompoundTag encode()
        {
            var t=new CompoundTag();t.putString("Id",id);t.putInt("UpperX",upperX);t.putInt("UpperZ",upperZ);t.putInt("LowerX",lowerX);t.putInt("LowerZ",lowerZ);t.putInt("TransferY",transferY);return t;
        }
        public static PathSpec decode(CompoundTag t)
        {return t.isEmpty()?null:new PathSpec(t.getString("Id"),t.getInt("UpperX"),t.getInt("UpperZ"),t.getInt("LowerX"),t.getInt("LowerZ"),t.getInt("TransferY"));}
    }
    public interface NativeState
    {
        PathSpec seele$transferPath();
    }
    private static final class Cached
    {
        long checked=Long.MIN_VALUE,modified=Long.MIN_VALUE;String reference="";List<PathSpec> paths=List.of();
    }
    private static final Map<ServerLevel,Cached> CACHE=new WeakHashMap<>();
    private NervPersonnelTransferR53() {}

    public static PathSpec parse(String id,JsonObject raw)
    {
        if(!raw.has("horizontal_transfer"))return null;
        var t=raw.getAsJsonObject("horizontal_transfer");var a=t.getAsJsonArray("upper_controller_axis");var b=t.getAsJsonArray("lower_controller_axis");
        return new PathSpec(id,a.get(0).getAsInt(),a.get(1).getAsInt(),b.get(0).getAsInt(),b.get(1).getAsInt(),t.get("transfer_y").getAsInt());
    }
    public static List<PathSpec> paths(Level level)
    {
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return List.of();
        if(!(level instanceof ServerLevel server))
        {
            var paths=new ArrayList<PathSpec>();
            for(var group:ElevatorGroupCapability.get(level).getGroups())
                if(group instanceof NativeState state&&state.seele$transferPath()!=null)paths.add(state.seele$transferPath());
            return paths;
        }
        if(!NervRouteRuntimeR52.claimed(server))return List.of();
        var cache=CACHE.computeIfAbsent(server,s->new Cached());String reference=NervRouteRuntimeR52.personnelLiftManifest(server);
        long now=server.getGameTime();if(reference.equals(cache.reference)&&now>=cache.checked&&now-cache.checked<100)return cache.paths;
        cache.checked=now;
        if(reference.isBlank())return List.of();
        try
        {
            var file=server.getServer().getWorldPath(LevelResource.ROOT).resolve(reference);long modified=Files.getLastModifiedTime(file).toMillis();
            if(reference.equals(cache.reference)&&modified==cache.modified)return cache.paths;
            var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if(root.get("epoch").getAsLong()!=NervRouteRuntimeR52.commissioningEpoch(server)||!root.get("directory_fingerprint").getAsString().equals(NervRouteRuntimeR52.directoryFingerprint(server)))return List.of();
            var paths=new ArrayList<PathSpec>();for(var raw:root.getAsJsonArray("lifts")){var lift=raw.getAsJsonObject();var path=parse(lift.get("id").getAsString(),lift);if(path!=null)paths.add(path);}
            cache.reference=reference;cache.modified=modified;cache.paths=List.copyOf(paths);return cache.paths;
        }
        catch(java.io.IOException failure){return List.of();}
    }
    public static BlockPos canonicalController(Level level,BlockPos original)
    {
        for(var path:paths(level))if(path.axis(original.getX(),original.getZ()))return new BlockPos(path.lowerX(),original.getY(),path.lowerZ());
        return original;
    }
    public static PathSpec forGroup(ElevatorGroup group)
    {
        for(var path:paths(group.level))if(group.x==path.lowerX()&&group.z==path.lowerZ())return path;
        return null;
    }
}
