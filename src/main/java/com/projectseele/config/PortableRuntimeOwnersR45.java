package com.projectseele.config;

import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Properties;
import java.util.Set;
import net.minecraftforge.fml.loading.FMLPaths;

/** Explicit identical portable owner selection; absence preserves the existing opt-in defaults. */
public final class PortableRuntimeOwnersR45
{
    public static final String RELATIVE_FILE="config/projectseele-runtime-r45.properties";
    private static final Set<String> KEYS=Set.of("schema","weapon_handling","cannon_contact",
            "captured_support","captured_locomotion_directory",
            "city.union.client.enabled","city.union.client.required","city.union.client.create_class_sha256","city.union.client.proof_sha256",
            "city.union.server.enabled","city.union.server.required","city.union.server.create_class_sha256","city.union.server.proof_sha256");
    private static final Set<String> FACILITY_KEYS=Set.of("tv_cage","personnel_platforms");
    private static Properties values;private static String hash="ABSENT";
    private static synchronized Properties values()
    {
        if(values!=null)return values;
        Properties parsed=new Properties();Path file=FMLPaths.GAMEDIR.get().resolve(RELATIVE_FILE);
        try
        {
            if(Files.isRegularFile(file))
            {
                byte[] bytes=Files.readAllBytes(file);String text=new String(bytes,StandardCharsets.UTF_8);
                var seen=new java.util.HashSet<String>();
                for(String line:text.split("\\r?\\n"))
                {
                    line=line.strip();if(line.isEmpty()||line.startsWith("#")||line.startsWith("!"))continue;
                    int equals=line.indexOf('=');if(equals<1||line.contains("\\\\")||!seen.add(line.substring(0,equals).strip()))
                        throw new IllegalStateException("Duplicate/escaped/malformed portable owner setting");
                }
                parsed.load(new StringReader(text));
                if(!"projectseele.runtime-owners.r45.v1".equals(parsed.getProperty("schema")))
                    throw new IllegalStateException("Unknown portable runtime owner schema");
                var allowed=new java.util.HashSet<>(KEYS);allowed.addAll(FACILITY_KEYS);
                if(!parsed.stringPropertyNames().containsAll(KEYS)||!allowed.containsAll(parsed.stringPropertyNames()))
                    throw new IllegalStateException("Incomplete/unknown portable runtime owner keys");
                for(String name:FACILITY_KEYS)
                    if(!Set.of("true","false").contains(parsed.getProperty(name,"false")))
                        throw new IllegalStateException("Invalid explicit facility Boolean: "+name);
                if(!parsed.getProperty("tv_cage","false").equals(parsed.getProperty("personnel_platforms","false")))
                    throw new IllegalStateException("TV cage render, collision and personnel interlock must deploy together");
                for(String name:new String[]{"weapon_handling","cannon_contact","captured_support","city.union.client.enabled","city.union.client.required","city.union.server.enabled","city.union.server.required"})
                    if(!Set.of("true","false").contains(parsed.getProperty(name)))throw new IllegalStateException("Invalid explicit owner Boolean: "+name);
                portableDirectory(parsed.getProperty("captured_locomotion_directory"));
                hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
                System.getLogger("Project SEELE runtime owners").log(System.Logger.Level.INFO,
                        "Explicit portable owner configuration loaded: sha256="+hash);
            }
            values=parsed;return values;
        }
        catch(Exception error){throw new IllegalStateException("Rejected portable runtime owner configuration "+RELATIVE_FILE,error);}
    }
    private static String portableDirectory(String value)
    {
        if(value==null||value.isEmpty())return "";
        if(value.startsWith("/")||value.contains("\\")||value.contains(":")||Path.of(value).isAbsolute())
            throw new IllegalStateException("Portable owner directory must be relative");
        for(String part:value.split("/",-1))if(part.isEmpty()||part.equals(".")||part.equals(".."))
            throw new IllegalStateException("Portable owner directory escapes its instance");
        if(!value.startsWith("projectseele-local-maps/"))throw new IllegalStateException("Portable owner directory must stay under projectseele-local-maps");
        return value;
    }
    private static boolean enabled(String key,String legacyProperty)
    {
        String explicit=System.getProperty(legacyProperty);
        return explicit!=null?Boolean.parseBoolean(explicit):Boolean.parseBoolean(values().getProperty(key,"false"));
    }
    public static boolean tvCage(){return enabled("tv_cage","projectseele.r44TvCageReview");}
    public static boolean personnelPlatforms(){return enabled("personnel_platforms","projectseele.r44TvPersonnelPlatformsReview");}
    public static boolean weaponHandling(){return enabled("weapon_handling","projectseele.weaponHandlingReviewR45");}
    public static boolean cannonContact(){return enabled("cannon_contact","projectseele.r45CannonContactCandidate");}
    public static boolean capturedSupport(){return enabled("captured_support","projectseele.r44CapturedSupportOwnership");}
    public static String capturedDirectory()
    {
        String explicit=System.getProperty("projectseele.capturedLocomotionDirectory");
        if(explicit!=null)return explicit;
        String relative=portableDirectory(values().getProperty("captured_locomotion_directory",""));
        return relative.isEmpty()?"":FMLPaths.GAMEDIR.get().resolve(relative).normalize().toString();
    }
    public static synchronized String fingerprint()
    {
        values();String effective=hash+":"+weaponHandling()+":"+cannonContact()+":"+capturedSupport()+":"+!capturedDirectory().isEmpty()+":"+tvCage()+":"+personnelPlatforms();
        try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(effective.getBytes(StandardCharsets.UTF_8)));}
        catch(Exception error){throw new IllegalStateException("Cannot fingerprint actual runtime owners",error);}
    }
    private PortableRuntimeOwnersR45() {}
}
