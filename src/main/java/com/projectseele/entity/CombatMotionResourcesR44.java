package com.projectseele.entity;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

/** A private combat bundle is resolved identically on both sides. */
public final class CombatMotionResourcesR44
{
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
            if(contract.has("bundle_id"))bundle=contract.get("bundle_id").getAsString();
        }
        ProjectSeele.LOGGER.info("Combat motion resource resolved: role={} bundle={} file={} sha256={}",
                role,bundle,file.toAbsolutePath().normalize(),hash);
        return bytes;
    }

    private CombatMotionResourcesR44(){}
}
