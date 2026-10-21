package com.projectseele.entity;
import com.google.gson.JsonParser;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
/** Support hull from the actual weapon, shared by rendered attachment and ballistics. */
public final class EvaRifleClearance
{
    record Hull(Vec3[] points,Vec3 muzzle,Vec3 stock,Vec3 dominant,Vec3 supporting,boolean legacyGripFit) {}
    private static final Hull HULL=load();
    private static Vec3 vector(com.google.gson.JsonArray array)
    {
        if(array==null||array.size()!=3)throw new IllegalArgumentException("Rifle geometry requires three coordinates");
        var point=new Vec3(array.get(0).getAsDouble(),array.get(1).getAsDouble(),array.get(2).getAsDouble());
        if(!Double.isFinite(point.lengthSqr())||point.lengthSqr()>10000)
            throw new IllegalArgumentException("Invalid rifle geometry coordinate");
        return point;
    }
    private static Hull legacy(Vec3[] points)
    {
        return new Hull(points,new Vec3(-.0014665D*.72,20.3010625D*.72,-.1561192D*.72),
                new Vec3(0,-49.700046D/16*EvaScale.RENDER_SCALE*.72,7.656318D/16*EvaScale.RENDER_SCALE*.72),
                new Vec3(.573097,-1.584,-.324),new Vec3(0,4.536,.170421),true);
    }
    private static Hull load()
    {
        try(var in=EvaRifleClearance.class.getResourceAsStream("/assets/projectseele/motion/rifle_clearance_r10.json"))
        {
            var root=JsonParser.parseReader(new InputStreamReader(in,StandardCharsets.UTF_8)).getAsJsonObject();
            if(!root.has("schema")||root.get("schema").getAsString().equals("1"))return parse(root,null);
            try(var mesh=EvaRifleClearance.class.getResourceAsStream("/assets/projectseele/mesh/eva_pallet_smg.mesh.json"))
            {
                String hash=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(mesh.readAllBytes()));
                return parse(root,hash);
            }
        }
        catch(Exception failure){throw new IllegalStateException("Rifle geometry unavailable or mismatched",failure);}
    }
    static Hull parse(com.google.gson.JsonObject root,String meshHash)
    {
        var a=root.getAsJsonArray("points");Vec3[] result=new Vec3[a.size()];
        if(result.length==0)throw new IllegalArgumentException("Empty rifle support surface");
        for(int i=0;i<result.length;i++)result[i]=vector(a.get(i).getAsJsonArray());
        if(!root.has("schema")||root.get("schema").getAsString().equals("1"))return legacy(result);
        if(!root.get("schema").getAsString().equals("projectseele.rifle-geometry.r53.v1"))
            throw new IllegalArgumentException("Unknown rifle geometry schema");
        if(meshHash==null||!meshHash.equals(root.get("mesh_sha256").getAsString()))
            throw new IllegalArgumentException("Rifle contact geometry and mesh differ");
        return new Hull(result,vector(root.getAsJsonArray("muzzle")),vector(root.getAsJsonArray("stock")),
                vector(root.getAsJsonArray("dominant_pad")),vector(root.getAsJsonArray("supporting_pad")),false);
    }
    /** Coordinates in weapon right / forward / up, shared by both sides. */
    public static Vec3 muzzle(){return HULL.muzzle();}
    public static Vec3 stock(){return HULL.stock();}
    public static Vec3 dominantPad(){return HULL.dominant();}
    public static Vec3 supportingPad(){return HULL.supporting();}
    public static boolean usesLegacyGripFit(){return HULL.legacyGripFit();}
    public static double lift(Vec3 grip,Vec3 right,Vec3 forward,Vec3 up,double floor)
    {
        double minimum=Double.POSITIVE_INFINITY;
        for(Vec3 p:HULL.points())minimum=Math.min(minimum,grip.y+right.y*p.x+forward.y*p.y+up.y*p.z);
        return Math.max(0,floor+.12-minimum);
    }
    private EvaRifleClearance() {}
}
