package com.projectseele.entity;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/** Common resource admission; a missing physical binding keeps its slot unavailable. */
public final class EvaEquipmentResourcesR45
{
    private record Asset(boolean present, String sha256) {}
    private static final Map<String,Asset> ASSETS=new HashMap<>();
    private static final List<String> SWORD_CLIPS=List.of("sword_a","sword_b","sword_c",
            "sword_heavy","sword_guard");
    private static final List<String> SHIELD_CLIPS=List.of("shield_idle","shield_brace","shield_hit");

    public static boolean ready(EvaUnit01Entity e,int weapon)
    {
        if(!EvaEquipmentPolicyR45.allowed(weapon,e.getUnitVariant(),e.isExperimentalUnit()))return false;
        if(weapon<6)return true;
        if(weapon==EvaEquipmentPolicyR45.SWORD&&!EvaSwordActionsR45.dispatchReadyR45(e))return false;
        // The root-owned common attachment provider must check the actual admitted
        // grip/geometry. No review flag, client renderer or successful fixture can supply this.
        String method=weapon==EvaEquipmentPolicyR45.SWORD?"swordAttachmentReadyR45":"shieldAttachmentReadyR45";
        if(!bindingReady(e,method))return false;
        var profile=EvaGameplayMotionR32.profile(e.getUnitVariant());
        if(profile==null||!profile.has("clips"))return false;
        var clips=profile.getAsJsonObject("clips");
        for(String name:weapon==EvaEquipmentPolicyR45.SWORD?SWORD_CLIPS:SHIELD_CLIPS)
        {
            String key="r32_"+name;
            if(!clips.has(key)||!EvaBodyPose.combatCaptureReadyR31(e,key))return false;
            var clip=clips.getAsJsonObject(key);
            if(!clip.has("frames")||clip.getAsJsonArray("frames").size()<2
                    ||!clip.has("source_duration_seconds"))return false;
            float seconds=clip.get("source_duration_seconds").getAsFloat();
            if(!Float.isFinite(seconds)||seconds<=0)return false;
        }
        if(weapon==EvaEquipmentPolicyR45.SWORD)
            return asset("mesh/eva02_longsword.mesh.json","lance").present()
                    &&asset("textures/entity/eva02_longsword.png",null).present();
        // Shield resource/plane identity belongs to the root provider; no guessed mesh or plane.
        return true;
    }

    private static boolean bindingReady(EvaUnit01Entity e,String name)
    {
        try
        {
            var method=EvaAnatomicalHandsR45.class.getMethod(name,EvaUnit01Entity.class);
            if(method.getReturnType()!=boolean.class||!Modifier.isStatic(method.getModifiers()))
                throw new IllegalStateException("Invalid common equipment readiness signature: "+name);
            return (boolean)method.invoke(null,e);
        }
        catch(NoSuchMethodException absent){return false;}
        catch(ReflectiveOperationException bad){throw new IllegalStateException("Common equipment readiness failed: "+name,bad);}
    }

    private static synchronized Asset asset(String name,String part)
    {
        return ASSETS.computeIfAbsent(name,key->{
            try(var stream=EvaEquipmentResourcesR45.class.getResourceAsStream("/assets/projectseele/"+key))
            {
                if(stream==null)return new Asset(false,"ABSENT");
                byte[] bytes=stream.readAllBytes();
                if(part!=null)
                {
                    var root=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
                    if(!root.has("parts")||!root.getAsJsonObject("parts").has(part))
                        throw new IllegalStateException("Required equipment mesh part missing: "+key+"#"+part);
                }
                else if(bytes.length<8||bytes[0]!=(byte)137||bytes[1]!=80||bytes[2]!=78||bytes[3]!=71)
                    throw new IllegalStateException("Invalid common equipment PNG: "+key);
                String sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
                ProjectSeele.LOGGER.info("R45 equipment common resource resolved: resource={} sha256={}",key,sha);
                return new Asset(true,sha);
            }
            catch(Exception error){throw new IllegalStateException("Rejected common equipment resource: "+key,error);}
        });
    }

    private EvaEquipmentResourcesR45() {}
}
