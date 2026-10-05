package com.projectseele.entity;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Measured red back-port frame, independent of the higher entry-plug socket. */
public final class EvaPowerPortsR48
{
    public record Profile(Vec3 mountPixels,Vec3 cableTailPixels,Vec3 cableDirection) { }
    private static final Map<Integer,Profile> PROFILES=load();
    private static Vec3 vector(JsonArray a)
    {
        if(a.size()!=3)throw new IllegalArgumentException("Three power-frame coordinates required");
        Vec3 p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(p.lengthSqr()))throw new IllegalArgumentException("Non-finite power-frame coordinate");
        return p;
    }
    private static Map<Integer,Profile> load()
    {
        try(var stream=EvaPowerPortsR48.class.getResourceAsStream("/assets/projectseele/motion/eva_power_ports_r48.json"))
        {
            if(stream==null)return Map.of();
            var data=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();
            if(data.get("schema").getAsInt()!=48)throw new IllegalArgumentException("Power-port profile version");
            var result=new HashMap<Integer,Profile>();
            for(int variant=0;variant<3;variant++)
            {
                var p=data.getAsJsonObject("profiles").getAsJsonObject(Integer.toString(variant));
                Vec3 mount=vector(p.getAsJsonArray("origin_native_model_pixels"));
                Vec3 tail=vector(p.getAsJsonArray("cable_tail_native_model_pixels"));
                Vec3 direction=vector(p.getAsJsonArray("cable_tangent_native"));
                if(Math.abs(direction.length()-1)>.001||p.getAsJsonArray("ports_native_model_pixels").size()!=3)
                    throw new IllegalArgumentException("Incomplete three-contact connector");
                result.put(variant,new Profile(mount,tail,direction));
            }
            return Map.copyOf(result);
        }
        catch(Exception failure)
        {ProjectSeele.LOGGER.error("R48 measured charging connector profile rejected",failure);return Map.of();}
    }
    public static Profile of(EvaUnit01Entity eva)
    {return eva.isExperimentalUnit()?null:PROFILES.get(eva.getUnitVariant());}
    private EvaPowerPortsR48() { }
}
