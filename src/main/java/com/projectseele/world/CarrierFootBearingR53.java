package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Finite fitted pads fill the measured gap between intact source deck and intact source soles. */
public final class CarrierFootBearingR53
{
    public static final String SELECTION = "eva/carrier_sole_bearings_r53_sources.json";
    public static final String SOURCE = "mesh/carrier_sole_bearings_r53.json";
    public record Pad(int variant, String bone, String name, NervRigidMeshSweepR52 mesh, double[] rgb,
                      List<List<Vec3>> contacts, double bottom) { }
    public record Source(List<Pad> pads, String fingerprint, String carrierSource)
    {
        public List<Pad> variant(int variant) { return pads.stream().filter(p -> p.variant() == variant).toList(); }
    }
    private static boolean checked;private static Source installed;
    private record BearingKey(Source source,EvaOriginalMeshGeometryR52.Geometry body,
            CarrierAssemblyR53.Surface deck,RigidTransform relative)
    {
        @Override public boolean equals(Object other)
        {return other instanceof BearingKey key&&source==key.source&&body==key.body&&deck==key.deck&&relative.equals(key.relative);}
        @Override public int hashCode()
        {return ((System.identityHashCode(source)*31+System.identityHashCode(body))*31+System.identityHashCode(deck))*31+relative.hashCode();}
    }
    // Same bounded immutable-result pattern as NervRigidPairMemoR53. No level,
    // entity, support blocks or world-clearance decision is retained here.
    private static final Map<BearingKey,Boolean> BEARINGS=new LinkedHashMap<>(32,.75F,true);


    public static synchronized Source selected()
    {
        if (checked) return installed;
        try (var stream = CarrierFootBearingR53.class.getResourceAsStream("/assets/projectseele/" + SELECTION))
        {
            if (stream != null)
            {
                var manifest = JsonParser.parseString(new String(stream.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
                byte[] bytes = EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
                if (!sha(bytes).equals(manifest.getAsJsonObject("resources").get(SOURCE).getAsString())) throw new IllegalStateException("Selected sole pad changed");
                installed = read(bytes);
                if (!CarrierAssemblyR53.retainsSourceSurface(installed.carrierSource())) throw new IllegalStateException("Sole bearing requires its exact supplied deck");
            }
            checked = true;return installed;
        }
        catch (IOException failure) { throw new IllegalStateException("Selected finite sole support unavailable", failure); }
    }

    public static Source read(byte[] bytes)
    {
        var root = JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject();
        if (!"projectseele.r53.carrier-sole-bearing.v1".equals(root.get("schema").getAsString()) || root.get("stride").getAsInt() != 6) throw new IllegalArgumentException("Finite source sole pad format required");
        var pads = new ArrayList<Pad>();var keys = new HashSet<String>();
        for (var raw : root.getAsJsonArray("parts"))
        {
            var row = raw.getAsJsonObject();int variant = row.get("variant").getAsInt();String bone = row.get("bone").getAsString();
            if (variant < 0 || variant > 2 || !Set.of("foot_l", "foot_r").contains(bone) || !keys.add(variant + "/" + bone)) throw new IllegalArgumentException("Six distinct original sole supports required");
            var a = row.getAsJsonArray("triangles_rgb");double[] rgb = new double[a.size()], xyz = new double[a.size() / 2];
            if (rgb.length == 0 || rgb.length % 18 != 0) throw new IllegalArgumentException("Complete pad source faces required");
            for (int i = 0, n = 0; i < rgb.length; i += 6) { for (int j = 0; j < 6; j++) { rgb[i + j] = a.get(i + j).getAsDouble();if (!Double.isFinite(rgb[i + j])) throw new IllegalArgumentException("Finite pad source required"); }for (int j = 0; j < 3; j++) xyz[n++] = rgb[i + j]; }
            var contacts = new ArrayList<List<Vec3>>();double area = 0;
            for (var f : row.getAsJsonArray("contact_facets"))
            {
                var points = new ArrayList<Vec3>();for (var p : f.getAsJsonArray()) { var v = p.getAsJsonArray();points.add(new Vec3(v.get(0).getAsDouble(), v.get(1).getAsDouble(), v.get(2).getAsDouble())); }
                if (points.size() != 3) throw new IllegalArgumentException("Finite source sole triangle required");
                area += Math.abs(points.get(1).subtract(points.get(0)).cross(points.get(2).subtract(points.get(0))).y) / 2;contacts.add(List.copyOf(points));
            }
            if (!(area > 1)) throw new IllegalArgumentException("Finite source sole area required");
            pads.add(new Pad(variant, bone, row.get("name").getAsString(), new NervRigidMeshSweepR52(xyz), rgb, List.copyOf(contacts), row.get("bottom").getAsDouble()));
        }
        if (pads.size() != 6) throw new IllegalArgumentException("All original soles required");
        return new Source(List.copyOf(pads), sha(bytes), root.get("carrier_source_sha256").getAsString());
    }

    public static List<NervOriginalCarrierR52.Part> partsAt(Source source, int variant, RigidTransform controller, CarrierMountProfileR53.State mounting)
    {
        var result = new ArrayList<NervOriginalCarrierR52.Part>();
        for (var p : source.variant(variant)) result.add(new NervOriginalCarrierR52.Part(p.name(), NervOriginalCarrierR52.Role.SOLE_BEARING, p.mesh(), mounting.payloadFrame(controller)));
        return List.copyOf(result);
    }

    public static boolean bears(Source source, EvaOriginalMeshGeometryR52.Geometry body, RigidTransform bodyFrame,
                                RigidTransform controller, CarrierMountProfileR53.State mounting, CarrierAssemblyR53.Profile carrier)
    {
        if (!mounting.aboveFloor() && !mounting.shallowBay() && !mounting.supportOnly()) return false;
        var local = mounting.payloadFrame(controller).inverse().compose(bodyFrame);
        var deck=carrier.parts().get("deck");var key=new BearingKey(source,body,deck,local);
        synchronized(BEARINGS){var cached=BEARINGS.get(key);if(cached!=null)return cached;}
        boolean result=sourceBears(source,body,local,deck);
        synchronized(BEARINGS)
        {
            BEARINGS.put(key,result);
            if(BEARINGS.size()>32)BEARINGS.remove(BEARINGS.keySet().iterator().next());
        }
        return result;
    }

    private static boolean sourceBears(Source source,EvaOriginalMeshGeometryR52.Geometry body,
            RigidTransform local,CarrierAssemblyR53.Surface deckSurface)
    {
        int supported=0;
        var deckSource=deckSurface.positions();
        for (var p : source.variant(body.variant()))
        {
            var skins = new ArrayList<double[]>();
            for (var skin : body.parts()) if (skin.bone().equals(p.bone()))
            {
                var xyz = skin.triangles();for (int i = 0; i < xyz.length; i += 3) { var q = point(xyz, i, local);xyz[i] = q.x;xyz[i + 1] = q.y;xyz[i + 2] = q.z; }skins.add(xyz);
            }
            if (skins.isEmpty()) return false;
            for (var f : p.contacts())
            {
                var probes = new ArrayList<>(f);probes.add(f.get(0).add(f.get(1)).add(f.get(2)).scale(1D / 3));
                for (var probe : probes)
                {
                    double nearest = Double.POSITIVE_INFINITY;
                    for (var xyz : skins) for (int i = 0; i < xyz.length; i += 9) nearest = Math.min(nearest, NervShoulderBearingR52.triangleDistanceR52(probe, vertex(xyz, i), vertex(xyz, i + 3), vertex(xyz, i + 6)));
                    double deck = NervMappedPlugMechanicsR52.surfaceHeight(deckSource, probe.x, probe.z);
                    if (nearest > .002 || !Double.isFinite(deck) || Math.abs(deck - p.bottom()) > .002) return false;
                }
            }
            supported++;
        }
        return supported == 2;
    }

    private static Vec3 point(double[] values, int offset, RigidTransform frame)
    { return frame.transformPoint(vertex(values, offset)); }
    private static Vec3 vertex(double[] values, int offset)
    { return new Vec3(values[offset], values[offset + 1], values[offset + 2]); }

    public static boolean permitsContact(Source source, EvaOriginalMeshGeometryR52.Geometry body, RigidTransform bodyFrame,
                                         RigidTransform controller, CarrierMountProfileR53.State mounting,
                                         CarrierAssemblyR53.Profile carrier, String bone, NervFlightProofR52.ObstacleMesh obstacle)
    {
        var pad = source.variant(body.variant()).stream().filter(p -> p.bone().equals(bone)).findFirst().orElse(null);
        if (pad == null || !bears(source, body, bodyFrame, controller, mounting, carrier)) return false;
        var expected = mounting.payloadFrame(controller);
        if (!NervAirTransportManifestR52.same(expected, obstacle.frame()) || !NervAirTransportManifestR52.same(expected, obstacle.endFrame())
                || !Arrays.equals(pad.mesh().triangles(), obstacle.mesh().triangles())) return false;
        var local = expected.inverse().compose(bodyFrame);boolean tested = false;
        for (var skin : body.parts()) if (skin.bone().equals(bone))
        {
            var xyz = skin.triangles();
            for (var face : pad.contacts())
            {
                var normal = face.get(1).subtract(face.get(0)).cross(face.get(2).subtract(face.get(0)));
                if (normal.y < 0) normal = normal.scale(-1);
                double plane = normal.dot(face.get(0));
                for (int i = 0; i < xyz.length; i += 9)
                {
                    List<Vec3> polygon = new ArrayList<>(List.of(point(xyz, i, local), point(xyz, i + 3, local), point(xyz, i + 6, local)));
                    for (int edge = 0; edge < 3 && !polygon.isEmpty(); edge++)
                    {
                        var origin = face.get(edge);var direction = face.get((edge + 1) % 3).subtract(origin);
                        var inward = new Vec3(-direction.z, 0, direction.x);
                        if (inward.dot(face.get((edge + 2) % 3).subtract(origin)) < 0) inward = inward.scale(-1);
                        polygon = clip(polygon, origin, inward);
                    }
                    for (var p : polygon) { tested = true;if ((normal.dot(p) - plane) / normal.length() < -.0002) return false; }
                }
            }
        }
        return tested;
    }

    private static List<Vec3> clip(List<Vec3> polygon, Vec3 origin, Vec3 inward)
    {
        var out = new ArrayList<Vec3>();var before = polygon.get(polygon.size() - 1);double old = before.subtract(origin).dot(inward);
        for (var now : polygon)
        {
            double value = now.subtract(origin).dot(inward);
            if ((old >= 0) != (value >= 0)) { double t = old / (old - value);out.add(before.add(now.subtract(before).scale(t))); }
            if (value >= 0) out.add(now);before = now;old = value;
        }
        return out;
    }

    private static String sha(byte[] bytes)
    { try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); } }
    private CarrierFootBearingR53() { }
}
