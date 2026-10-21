package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/** Old packs retain their sockets; new sockets must belong to the loaded mesh. */
public final class EvaRifleGeometryR53Test
{
    public static void main(String[] args) throws Exception
    {
        JsonObject legacy;
        try (var input = EvaRifleGeometryR53Test.class.getResourceAsStream(
                "/assets/projectseele/motion/rifle_clearance_r10.json"))
        {
            legacy = JsonParser.parseReader(new InputStreamReader(input, StandardCharsets.UTF_8)).getAsJsonObject();
        }
        var old = EvaRifleClearance.parse(legacy, null);
        check(old.points().length > 0, "Public pack has no support hull");
        check(old.legacyGripFit(), "Old hand fit lost its translation");
        check(Math.abs(old.muzzle().y - 14.616765) < 1e-8, "Legacy muzzle changed");
        var withoutSchema = legacy.deepCopy();
        withoutSchema.remove("schema");
        check(EvaRifleClearance.parse(withoutSchema, null).muzzle().equals(old.muzzle()),
                "Unversioned legacy pack changed");

        var replacement = JsonParser.parseString("""
                {"schema":"projectseele.rifle-geometry.r53.v1","mesh_sha256":"mesh-A",
                 "points":[[0,1,-1],[0,-1,2]],"muzzle":[0,13,3],"stock":[0,-12,2],
                 "dominant_pad":[0.5,-1.5,-0.3],"supporting_pad":[0,4.5,1.5]}
                """).getAsJsonObject();
        var newer = EvaRifleClearance.parse(replacement, "mesh-A");
        check(!newer.legacyGripFit(), "Old hand offset applied to a replacement palm target");
        check(newer.muzzle().z == 3 && newer.supporting().z == 1.5,
                "New mesh sockets fell back to old geometry");
        reject(replacement, "mesh-B");
        reject(replacement, null);
        var unknown = replacement.deepCopy();
        unknown.addProperty("schema", "unsupported");
        reject(unknown, "mesh-A");
        var invalid = replacement.deepCopy();
        invalid.add("points", JsonParser.parseString("[]"));
        reject(invalid, "mesh-A");
        invalid = replacement.deepCopy();
        invalid.add("dominant_pad", JsonParser.parseString("[0,0,1000]"));
        reject(invalid, "mesh-A");
        System.out.println("Rifle geometry: legacy packs and bound replacement sockets verified");
    }

    private static void reject(JsonObject data, String hash)
    {
        try { EvaRifleClearance.parse(data, hash); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Mismatched or invalid rifle geometry accepted");
    }

    private static void check(boolean valid, String message)
    {
        if (!valid) throw new AssertionError(message);
    }
}
