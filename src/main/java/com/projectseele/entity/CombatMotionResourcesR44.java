package com.projectseele.entity;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.TreeMap;

/** A private combat bundle is resolved and fingerprinted identically on both sides. */
public final class CombatMotionResourcesR44
{
    private static volatile Map<String,String> fingerprints;
    public static Path instancePath(String value)
    {
        Path path=Path.of(value);
        return path.isAbsolute()?path:net.minecraftforge.fml.loading.FMLPaths.GAMEDIR.get().resolve(path).normalize();
    }
    public static Path resolve(String reviewProperty,String... names)
    {
        String review=System.getProperty(reviewProperty,"");
        String bundle=System.getProperty("projectseele.combatBundleDirectory","");
        Path directory=instancePath(!review.isEmpty()?review:!bundle.isEmpty()?bundle:"projectseele-local-maps");
        for(String name:names)
        {
            Path file=directory.resolve(name);
            if(Files.isRegularFile(file))return file;
        }
        if(!review.isEmpty()||!bundle.isEmpty())
            throw new IllegalStateException("Requested combat bundle has no compatible file: "+directory+" / "+String.join(",",names));
        return directory.resolve(names[0]);
    }

    public static byte[] read(Path file,String role)throws Exception
    {
        byte[] bytes=Files.readAllBytes(file);
        String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        Path manifest=file.resolveSibling("combat_bundle_r44.json");
        String bundle="legacy";
        if(Files.isRegularFile(manifest))
        {
            var contract=JsonParser.parseString(Files.readString(manifest)).getAsJsonObject();
            var files=contract.getAsJsonObject("files");String name=file.getFileName().toString();
            if(contract.get("revision").getAsInt()!=44||!files.has(name)||!hash.equals(files.get(name).getAsString()))
                throw new IllegalStateException("Combat bundle resource identity mismatch: "+file);
            bundle=contract.get("bundle_id").getAsString();
        }
        ProjectSeele.LOGGER.info("Combat motion resource resolved: role={} bundle={} file={} sha256={}",
                role,bundle,file.toAbsolutePath().normalize(),hash);
        return bytes;
    }

    public static synchronized void resetFingerprints(){fingerprints=null;}

    public static synchronized Map<String,String> fingerprints()
    {
        if(fingerprints!=null)return fingerprints;
        try
        {
            Map<String,String> values=new TreeMap<>();
            values.put("pose-signals-contract","r44-captured-state-phase-displacement-v2:owners="+com.projectseele.config.PortableRuntimeOwnersR45.fingerprint());
            String explicit=System.getProperty("projectseele.bodyPoseReview","");
            Path body=explicit.isEmpty()?resolve("projectseele.bodyPoseReviewDirectory",
                    "eva_body_r44.json","eva_body_r43.json","eva_body_r42.json","eva_body_r41.json","eva_body_r25.json"):Path.of(explicit);
            if(!Files.isRegularFile(body))for(String name:new String[]{"eva_body_r11.json","eva_body_r06.json","eva_body_r05.json"})
            {Path legacy=Path.of("projectseele-local-maps").resolve(name);if(Files.isRegularFile(legacy)){body=legacy;break;}}
            values.put("body",Files.isRegularFile(body)?digest(read(body,"login-body")):bundled("motion/eva_connected_locomotion_v1.json")+":"+bundled("eva/eva_rig_schema.json"));
            for(int key=0;key<5;key++)
            {
                Path file=resolve("projectseele.gameplayReviewDirectory","eva_gameplay_r44_"+key+".json",
                        "eva_gameplay_r43_"+key+".json","eva_gameplay_r42_"+key+".json","eva_gameplay_r32_"+key+".json");
                values.put("eva-profile-"+key,Files.isRegularFile(file)?digest(read(file,"login-gameplay-"+key)):"ABSENT");
            }
            String captured=com.projectseele.config.PortableRuntimeOwnersR45.capturedDirectory();
            if(!captured.isEmpty())for(int key=0;key<5;key++)
            {
                Path file=Path.of(captured,"eva_locomotion_capture_r44_"+key+".json");
                values.put("captured-locomotion-"+key,Files.isRegularFile(file)?digest(read(file,"login-captured-locomotion-"+key)):"ABSENT");
            }
            Path angel=resolve("projectseele.gameplayReviewDirectory","sachiel_gameplay_r44.json","sachiel_gameplay_r32.json");
            values.put("sachiel-profile",Files.isRegularFile(angel)?digest(read(angel,"login-sachiel")):"ABSENT");
            FirstBattleClip.ready();String finisher=FirstBattleClip.fingerprint();
            values.put("first-battle",finisher.isEmpty()?bundled("motion/first_battle_r10.json"):finisher);
            values.put("physical-body-profiles",com.projectseele.physics.CombatBodyProfiles.fingerprint());
            var hands=new StringBuilder();
            for(int key=0;key<3;key++)hands.append(key).append(':').append(EvaAnatomicalHandsR45.contractFingerprintR45(key)).append(';');
            values.put("anatomical-hand-rigs",digest(hands.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            fingerprints=Map.copyOf(values);
            ProjectSeele.LOGGER.info("Combat required resource fingerprints: {}",values);
            return fingerprints;
        }
        catch(Exception failure){throw new IllegalStateException("Required combat resource identity could not be read",failure);}
    }
    private static String digest(byte[] bytes)throws Exception
    {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static String bundled(String name)throws Exception
    {
        try(var stream=CombatMotionResourcesR44.class.getResourceAsStream("/assets/projectseele/"+name))
        {if(stream==null)throw new IllegalStateException("Missing required combat resource: "+name);return digest(stream.readAllBytes());}
    }

    private CombatMotionResourcesR44(){}
}
