package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/** Old packs retain their sockets; new sockets load whatever mesh is installed. */
public final class EvaRifleGeometryR53Test
{
    public static void main(String[] args) throws Exception
    {
        // The installed resource may already use the mesh-bound replacement schema.
        var legacy = JsonParser.parseString("""
                {"schema":1,"points":[[0,1,-1],[0,-1,2]]}
                """).getAsJsonObject();
        var old = EvaRifleClearance.parse(legacy);
        check(old.points().length > 0, "Legacy fixture has no support hull");
        check(old.legacyGripFit(), "Old hand fit lost its translation");
        check(Math.abs(old.muzzle().y - 14.616765) < 1e-8, "Legacy muzzle changed");
        var withoutSchema = legacy.deepCopy();
        withoutSchema.remove("schema");
        check(EvaRifleClearance.parse(withoutSchema).muzzle().equals(old.muzzle()),
                "Unversioned legacy pack changed");

        var replacement = JsonParser.parseString("""
                {"schema":"projectseele.rifle-geometry.r53.v1","mesh_sha256":"mesh-A",
                 "points":[[0,1,-1],[0,-1,2]],"muzzle":[0,13,3],"stock":[0,-12,2],
                 "dominant_pad":[0.5,-1.5,-0.3],"supporting_pad":[0,4.5,1.5]}
                """).getAsJsonObject();
        var newer = EvaRifleClearance.parse(replacement);
        check(!newer.legacyGripFit(), "Old hand offset applied to a replacement palm target");
        check(newer.muzzle().z == 3 && newer.supporting().z == 1.5,
                "New mesh sockets fell back to old geometry");
        // A recorded mesh digest from an older pack is inert: an edited rifle mesh still loads.
        var edited = replacement.deepCopy();
        edited.addProperty("mesh_sha256", "mesh-B");
        check(EvaRifleClearance.parse(edited).muzzle().equals(newer.muzzle()),
                "Stale mesh digest rejected the replacement sockets");
        var unknown = replacement.deepCopy();
        unknown.addProperty("schema", "unsupported");
        reject(unknown);
        var invalid = replacement.deepCopy();
        invalid.add("points", JsonParser.parseString("[]"));
        reject(invalid);
        invalid = replacement.deepCopy();
        invalid.add("dominant_pad", JsonParser.parseString("[0,0,1000]"));
        reject(invalid);
        System.out.println("Rifle geometry: legacy packs and replacement sockets verified");
    }

    private static void reject(JsonObject data)
    {
        try { EvaRifleClearance.parse(data); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Invalid rifle geometry accepted");
    }

    private static void check(boolean valid, String message)
    {
        if (!valid) throw new AssertionError(message);
    }
}
