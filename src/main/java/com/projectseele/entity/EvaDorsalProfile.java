package com.projectseele.entity;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Geometry measured at each model's paired rear markings, shared by lid and capsule. */
public final class EvaDorsalProfile
{
    public record Profile(Vec3 centreModel,Vec3 outwardModel,Vec3 hingeModel,Vec3 hingeAxisModel,float openAngle)
    {
        public Vec3 centreBlocks(){return centreModel.scale(EvaScale.RENDER_SCALE/16D);}
    }
    private static final String[] MODELS={"eva_unit00","eva_unit01","eva_unit02","eva_prototype","eva_un01"};
    private static final Map<String,Profile> PROFILES=load();
    private static Vec3 vector(JsonArray a)
    {
        if(a.size()!=3)throw new IllegalArgumentException("Dorsal vector length");
        Vec3 p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z))throw new IllegalArgumentException("Dorsal vector is not finite");return p;
    }
    private static Map<String,Profile> load()
    {
        java.nio.file.Path privateProfile=CombatMotionResourcesR44.instancePath(System.getProperty("projectseele.dorsalPoseReview","projectseele-local-maps/eva_dorsal_r30.json"));
        try(var stream=java.nio.file.Files.isRegularFile(privateProfile)?java.nio.file.Files.newInputStream(privateProfile):EvaDorsalProfile.class.getResourceAsStream("/assets/projectseele/motion/eva_dorsal_r13.json"))
        {
            if(stream==null)throw new IllegalStateException("Dorsal profiles missing");
            var data=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("profiles");Map<String,Profile> result=new HashMap<>();
            for(String name:MODELS)
            {
                var p=data.getAsJsonObject(name);Vec3 axis=vector(p.getAsJsonArray("outward")),hingeAxis=vector(p.getAsJsonArray("hinge_axis"));
                if(Math.abs(axis.length()-1)>.001||Math.abs(hingeAxis.length()-1)>.001||Math.abs(axis.dot(hingeAxis))>.001)throw new IllegalArgumentException("Dorsal frame is not orthonormal");
                result.put(name,new Profile(vector(p.getAsJsonArray("centre")),axis.normalize(),vector(p.getAsJsonArray("hinge")),hingeAxis.normalize(),p.get("open_angle_degrees").getAsFloat()));
            }
            ProjectSeele.LOGGER.info("TV dorsal profiles loaded: {} measured models",result.size());return Map.copyOf(result);
        }
        catch(Exception e){throw new IllegalStateException("Invalid TV dorsal profiles",e);}
    }
    public static Profile byVariant(int variant){return PROFILES.get(MODELS[Math.max(0,Math.min(4,variant))]);}
    public static Profile of(EvaUnit01Entity unit){return byVariant(unit instanceof EvaPrototypeEntity un?3+un.getUNSerial():unit.getUnitVariant());}
    private EvaDorsalProfile() {}
}
