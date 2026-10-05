package com.projectseele.physics;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.CombatFeelR31;
import com.projectseele.entity.ShamshelEntity;
import com.projectseele.util.WeakIdentityMap;
import com.projectseele.physics.MeshContactMathR48.Hit;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Actual shipped weighted triangles, refitted to the existing shared motion and ground lift. */
public final class ShamshelPosedContactsR48
{
    private record Bone(String name, int parent, Vector3f pivot, Vector3f idle) {}
    private record Vertex(Vector3f point, int[] joints, float[] weights) {}
    private record Topology(int start, int end, Topology left, Topology right) {}
    private record Model(Bone[] bones, int[] skinBones, Vertex[] vertices, int[][] triangles, int[] order, Topology topology) {}
    private record Node(AABB bounds, int start, int end, Node left, Node right) {}
    private record Frame(Vec3[] points, Node root, Vec3 origin, float yaw, Vector3f[] angles, boolean grounded) {}
    private static final class State
    {
        Frame frame;
        Vector3f[] beforeReaction, held;
        long beat = Long.MIN_VALUE;
    }
    private static volatile Model model;
    private static volatile boolean loadAttempted;
    private static volatile String resourceStatus = "NOT_LOADED";
    private static final WeakIdentityMap<ShamshelEntity, State> STATES = new WeakIdentityMap<>();
    private static final boolean DOMINANT = Boolean.getBoolean("projectseele.r44DominantSkinReview");
    private static final boolean RUNNING = Boolean.getBoolean("projectseele.r44RunningSkinReview");
    private ShamshelPosedContactsR48() {}

    public static boolean supports(LivingEntity entity)
    {
        return entity instanceof ShamshelEntity && !CombatBodyDynamics.active(entity) && model() != null;
    }

    /** Public placeholder spawns remain valid; R48 private-release checks require READY. */
    public static String resourceStatus() { model(); return resourceStatus; }

    private static JsonObject resource(String name) throws Exception
    {
        try (InputStream stream = ShamshelPosedContactsR48.class.getResourceAsStream("/assets/projectseele/" + name))
        {
            if (stream == null) throw new IllegalStateException("Missing actual contact resource " + name);
            return JsonParser.parseString(new String(stream.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
        }
    }

    private static synchronized Model model()
    {
        if (loadAttempted) return model;
        loadAttempted = true;
        for (String name : new String[]{"mesh/shamshel.mesh.json", "geo/shamshel.geo.json",
                "animations/shamshel.animation.json", "textures/entity/shamshel.png"})
            if (ShamshelPosedContactsR48.class.getResource("/assets/projectseele/" + name) == null)
            {
                resourceStatus = "PUBLIC_PLACEHOLDER_MISSING_DETAILED_RESOURCES";
                ProjectSeele.LOGGER.info("Shamshel contact mode: public placeholder; {} absent, original public collider retained; no posed-contact pass", name);
                return null;
            }
        try
        {
            if (DOMINANT && RUNNING) throw new IllegalStateException("Select one actual DQS hemisphere owner");
            JsonObject mesh = resource("mesh/shamshel.mesh.json"), geo = resource("geo/shamshel.geo.json");
            var animations = resource("animations/shamshel.animation.json").getAsJsonObject("animations");
            for (var clip : animations.entrySet()) for (var bone : clip.getValue().getAsJsonObject().getAsJsonObject("bones").entrySet())
                for (var channel : bone.getValue().getAsJsonObject().entrySet())
                {
                    if (!channel.getValue().isJsonArray()) throw new IllegalStateException("Unsupported actual animation track; shared sampler required");
                    float neutral = channel.getKey().equals("scale") ? 1 : 0;
                    for (var component : channel.getValue().getAsJsonArray())
                        if (component.getAsFloat() != neutral) throw new IllegalStateException("Actual animation adds motion not owned by the shared pose sampler");
                }
            if (mesh.get("stride").getAsInt() != 8) throw new IllegalStateException("Actual weighted stride changed");
            var rows = geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones");
            Map<String, Integer> indices = new LinkedHashMap<>();
            for (var raw : rows) indices.put(raw.getAsJsonObject().get("name").getAsString(), indices.size());
            if (rows.isEmpty() || indices.size() != rows.size()) throw new IllegalStateException("Empty or duplicate actual rig bones");
            Bone[] bones = new Bone[rows.size()]; int index = 0;
            for (var raw : rows)
            {
                var row = raw.getAsJsonObject(); String name = row.get("name").getAsString();
                Vector3f pivot = CombatBodyProfiles.vector(row.getAsJsonArray("pivot")).mul(-1, 1, 1).div(16);
                Vector3f idle = row.has("rotation") ? CombatBodyProfiles.vector(row.getAsJsonArray("rotation"))
                        .mul(-(float) Math.PI / 180, -(float) Math.PI / 180, (float) Math.PI / 180) : new Vector3f();
                if (!Float.isFinite(pivot.x + pivot.y + pivot.z + idle.x + idle.y + idle.z))
                    throw new IllegalStateException("Non-finite actual rig bone");
                bones[index++] = new Bone(name, row.has("parent") ? indices.get(row.get("parent").getAsString()) : -1, pivot, idle);
            }
            byte[] visits = new byte[bones.length];
            for (int i = 0; i < bones.length; i++) validateBone(bones, i, visits);
            var names = mesh.getAsJsonObject("skin").getAsJsonArray("bones"); int[] skinBones = new int[names.size()];
            for (int i = 0; i < names.size(); i++) skinBones[i] = indices.get(names.get(i).getAsString());
            var root = mesh.getAsJsonObject("parts").getAsJsonObject("root");
            Vector3f pivot = CombatBodyProfiles.vector(root.getAsJsonArray("pivot"));
            if (pivot.lengthSquared() != 0) throw new IllegalStateException("Actual root mesh pivot contract changed");
            var values = root.getAsJsonArray("vertices");
            var ji = mesh.getAsJsonObject("skin").getAsJsonArray("indices");
            var jw = mesh.getAsJsonObject("skin").getAsJsonArray("weights");
            if (values.isEmpty() || values.size() % 24 != 0 || ji.size() != values.size() / 2 || ji.size() != jw.size())
                throw new IllegalStateException("Incomplete actual skin triangles");
            Map<String, Integer> unique = new HashMap<>(); List<Vertex> vertices = new ArrayList<>();
            int[] welded = new int[values.size() / 8];
            for (int i = 0; i < welded.length; i++)
            {
                Vector3f point = new Vector3f(-values.get(i * 8).getAsFloat() / 16,
                        values.get(i * 8 + 1).getAsFloat() / 16, values.get(i * 8 + 2).getAsFloat() / 16);
                int[] joints = new int[4]; float[] weights = new float[4]; float sum = 0;
                StringBuilder key = new StringBuilder().append(point.x).append('/').append(point.y).append('/').append(point.z);
                for (int k = 0; k < 4; k++)
                {
                    joints[k] = ji.get(i * 4 + k).getAsInt(); weights[k] = jw.get(i * 4 + k).getAsFloat(); sum += weights[k];
                    if (joints[k] < 0 || joints[k] >= skinBones.length || !Float.isFinite(weights[k]) || weights[k] < 0)
                        throw new IllegalStateException("Invalid actual skin influence");
                    key.append('/').append(joints[k]).append(':').append(weights[k]);
                }
                if (Math.abs(sum - 1) > 1e-4 || !Float.isFinite(point.x + point.y + point.z))
                    throw new IllegalStateException("Invalid actual skin vertex");
                String encoded = key.toString(); Integer existing = unique.get(encoded);
                if (existing == null) { existing = vertices.size(); unique.put(encoded, existing); vertices.add(new Vertex(point, joints, weights)); }
                welded[i] = existing;
            }
            int[][] triangles = new int[welded.length / 3][3]; Integer[] order = new Integer[triangles.length];
            for (int i = 0; i < triangles.length; i++) { triangles[i] = new int[]{welded[i * 3], welded[i * 3 + 1], welded[i * 3 + 2]}; order[i] = i; }
            Vertex[] points = vertices.toArray(Vertex[]::new);
            Topology topology = topology(points, triangles, order, 0, order.length);
            model = new Model(bones, skinBones, points, triangles, Arrays.stream(order).mapToInt(Integer::intValue).toArray(), topology);
            resourceStatus = "READY";
            return model;
        }
        catch (Exception error)
        {
            resourceStatus = "INVALID_DETAILED_RESOURCES_UNVERIFIED";
            ProjectSeele.LOGGER.error("Shamshel posed contact resource rejected; original public collider retained to keep server available; private release not verified", error);
            return null;
        }
    }

    private static void validateBone(Bone[] bones, int bone, byte[] visits)
    {
        if (visits[bone] == 2) return;
        if (visits[bone] == 1) throw new IllegalStateException("Cyclic actual rig hierarchy");
        visits[bone] = 1;
        if (bones[bone].parent() >= 0) validateBone(bones, bones[bone].parent(), visits);
        visits[bone] = 2;
    }

    private static Topology topology(Vertex[] points, int[][] triangles, Integer[] order, int start, int end)
    {
        if (end - start <= 24) return new Topology(start, end, null, null);
        float[] minimum = {Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY};
        float[] maximum = {Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY};
        for (int i = start; i < end; i++) for (int v : triangles[order[i]])
            for (int axis = 0; axis < 3; axis++) { float value = points[v].point().get(axis); minimum[axis] = Math.min(minimum[axis], value); maximum[axis] = Math.max(maximum[axis], value); }
        int axis = maximum[1] - minimum[1] > maximum[0] - minimum[0] ? 1 : 0;
        if (maximum[2] - minimum[2] > maximum[axis] - minimum[axis]) axis = 2;
        final int sortAxis = axis;
        Arrays.sort(order, start, end, Comparator.comparingDouble((Integer tri) -> Arrays.stream(triangles[tri]).mapToDouble(v -> points[v].point().get(sortAxis)).sum()));
        int middle = (start + end) / 2;
        return new Topology(start, end, topology(points, triangles, order, start, middle), topology(points, triangles, order, middle, end));
    }

    private static Vector3f[] angles(ShamshelEntity actor, Model mesh)
    {
        Vector3f[] values = new Vector3f[mesh.bones().length];
        for (int i = 0; i < values.length; i++)
        {
            Bone bone = mesh.bones()[i]; Vector3f value = ShamshelContactPoseR48.base(actor, bone.name(), bone.idle(), 0);
            value = ShamshelContactPoseR48.impact(actor, bone.name(), value, 0);
            values[i] = ShamshelContactPoseR48.reaction(actor, bone.name(), value, 0);
        }
        return values;
    }

    /** Root calls before BEATS.put in both receive/begin; reads existing motion only. */
    public static void captureBeforeReaction(LivingEntity actor)
    {
        if (actor instanceof ShamshelEntity shamshel && supports(actor))
            STATES.computeIfAbsent(shamshel, ignored -> new State()).beforeReaction = frame(shamshel).angles();
    }

    private static Matrix4f matrix(Model mesh, Vector3f[] angles, int bone, Matrix4f[] cache)
    {
        if (cache[bone] != null) return cache[bone];
        Bone definition = mesh.bones()[bone]; Vector3f pivot = definition.pivot(), rotation = angles[bone];
        Matrix4f local = new Matrix4f().translate(pivot).rotateZYX(rotation.z, rotation.y, rotation.x).translate(-pivot.x, -pivot.y, -pivot.z);
        return cache[bone] = definition.parent() < 0 ? local : new Matrix4f(matrix(mesh, angles, definition.parent(), cache)).mul(local);
    }

    private static Vector3f skin(Vertex vertex, Quaternionf[] real, Quaternionf[] dual)
    {
        int reference = vertex.joints()[0];
        if (DOMINANT)
        {
            float largest = 0; reference = -1;
            for (int k = 0; k < 4; k++) if (vertex.weights()[k] > largest || vertex.weights()[k] == largest && largest > 0
                    && (reference < 0 || vertex.joints()[k] < reference)) { largest = vertex.weights()[k]; reference = vertex.joints()[k]; }
        }
        Quaternionf q = new Quaternionf(0, 0, 0, 0), d = new Quaternionf(0, 0, 0, 0);
        for (int k = 0; k < 4; k++)
        {
            int bone = vertex.joints()[k]; float weight = vertex.weights()[k]; if (weight == 0) continue;
            if ((RUNNING ? q : real[reference]).dot(real[bone]) < 0) weight = -weight;
            q.x += real[bone].x * weight; q.y += real[bone].y * weight; q.z += real[bone].z * weight; q.w += real[bone].w * weight;
            d.x += dual[bone].x * weight; d.y += dual[bone].y * weight; d.z += dual[bone].z * weight; d.w += dual[bone].w * weight;
        }
        float length = (float) Math.sqrt(q.lengthSquared()); if (length < 1e-8) throw new IllegalStateException("Degenerate actual DQS pose");
        q.mul(1 / length); d.mul(1 / length); float dot = q.dot(d);
        d.x -= q.x * dot; d.y -= q.y * dot; d.z -= q.z * dot; d.w -= q.w * dot;
        Quaternionf translation = d.mul(new Quaternionf(q).conjugate());
        return q.transform(new Vector3f(vertex.point())).add(2 * translation.x, 2 * translation.y, 2 * translation.z);
    }

    private static Frame frame(ShamshelEntity actor)
    {
        Model mesh = model(); State state = STATES.computeIfAbsent(actor, ignored -> new State());
        var beat = CombatFeelR31.beat(actor); Vector3f[] pose;
        if (beat != null && CombatFeelR31.hitPaused(actor))
        {
            if (state.beat != beat.start())
            {
                state.beat = beat.start(); state.held = state.beforeReaction != null ? state.beforeReaction
                        : state.frame != null ? state.frame.angles() : angles(actor, mesh);
            }
            pose = state.held;
        }
        else pose = angles(actor, mesh);
        boolean grounded = ShamshelContactPoseR48.groundSupport(actor);
        Frame old = state.frame;
        if (old != null && old.origin().equals(actor.position()) && old.yaw() == actor.yBodyRot
                && old.grounded() == grounded && Arrays.equals(old.angles(), pose)) return old;
        Matrix4f[] matrices = new Matrix4f[mesh.bones().length];
        Quaternionf[] real = new Quaternionf[mesh.skinBones().length], dual = new Quaternionf[real.length];
        for (int i = 0; i < real.length; i++)
        {
            Matrix4f transform = matrix(mesh, pose, mesh.skinBones()[i], matrices);
            real[i] = transform.getUnnormalizedRotation(new Quaternionf()).normalize(); Vector3f at = transform.getTranslation(new Vector3f());
            dual[i] = new Quaternionf(at.x, at.y, at.z, 0).mul(real[i]).mul(.5F);
        }
        Vector3f[] local = new Vector3f[mesh.vertices().length]; float minimum = Float.POSITIVE_INFINITY;
        for (int i = 0; i < local.length; i++) { local[i] = skin(mesh.vertices()[i], real, dual); minimum = Math.min(minimum, local[i].y); }
        float lift = grounded ? .016F - minimum : 0;
        float yaw = (float) Math.toRadians(180 - actor.yBodyRot); Vec3[] world = new Vec3[local.length];
        for (int i = 0; i < local.length; i++) { Vector3f point = local[i].add(0, lift, 0).mul(5).rotateY(yaw); world[i] = actor.position().add(point.x, point.y, point.z); }
        Frame result = new Frame(world, refit(mesh, world, mesh.topology()), actor.position(), actor.yBodyRot, pose, grounded);
        state.frame = result; return result;
    }

    private static Node refit(Model mesh, Vec3[] points, Topology topology)
    {
        if (topology.left() != null)
        {
            Node left = refit(mesh, points, topology.left()), right = refit(mesh, points, topology.right());
            return new Node(left.bounds().minmax(right.bounds()), topology.start(), topology.end(), left, right);
        }
        double minX = Double.POSITIVE_INFINITY, minY = minX, minZ = minX;
        double maxX = Double.NEGATIVE_INFINITY, maxY = maxX, maxZ = maxX;
        for (int i = topology.start(); i < topology.end(); i++) for (int vertex : mesh.triangles()[mesh.order()[i]])
        {
            Vec3 point = points[vertex]; minX = Math.min(minX, point.x); minY = Math.min(minY, point.y); minZ = Math.min(minZ, point.z);
            maxX = Math.max(maxX, point.x); maxY = Math.max(maxY, point.y); maxZ = Math.max(maxZ, point.z);
        }
        return new Node(new AABB(minX - 1e-6, minY - 1e-6, minZ - 1e-6, maxX + 1e-6, maxY + 1e-6, maxZ + 1e-6),
                topology.start(), topology.end(), null, null);
    }

    public static AABB bounds(LivingEntity actor)
    { return model() == null ? actor.getBoundingBox() : frame((ShamshelEntity) actor).root().bounds(); }

    public static Optional<Vec3> clip(LivingEntity actor, Vec3 from, Vec3 to, double radius)
    {
        if (model() == null)
        {
            AABB box = actor.getBoundingBox().inflate(radius);
            return box.contains(from) ? Optional.of(from) : box.clip(from, to);
        }
        Frame frame = frame((ShamshelEntity) actor);
        if (inside(frame, from)) return Optional.of(from);
        Hit hit = ray(frame, frame.root(), from, to, Math.max(0, radius), null);
        return hit == null ? Optional.empty() : Optional.of(hit.point());
    }

    private static Hit ray(Frame frame, Node node, Vec3 from, Vec3 to, double radius, Hit nearest)
    {
        AABB bounds = node.bounds().inflate(radius);
        if (!bounds.contains(from) && bounds.clip(from, to).isEmpty()) return nearest;
        if (node.left() != null) return ray(frame, node.right(), from, to, radius, ray(frame, node.left(), from, to, radius, nearest));
        Model mesh = model();
        for (int i = node.start(); i < node.end(); i++)
        {
            int[] triangle = mesh.triangles()[mesh.order()[i]];
            Hit hit = MeshContactMathR48.sweepTriangle(from, to, frame.points()[triangle[0]], frame.points()[triangle[1]], frame.points()[triangle[2]], radius);
            if (hit != null && (nearest == null || hit.time() < nearest.time())) nearest = hit;
        }
        return nearest;
    }

    public static boolean overlap(LivingEntity actor, AABB area)
    {
        if (model() == null) return actor.getBoundingBox().intersects(area);
        Frame frame = frame((ShamshelEntity) actor);
        return overlap(frame, frame.root(), area) || inside(frame, area.getCenter());
    }

    private static boolean overlap(Frame frame, Node node, AABB area)
    {
        if (!node.bounds().intersects(area)) return false;
        if (node.left() != null) return overlap(frame, node.left(), area) || overlap(frame, node.right(), area);
        Model mesh = model();
        for (int i = node.start(); i < node.end(); i++)
        {
            int[] tri = mesh.triangles()[mesh.order()[i]];
            if (MeshContactMathR48.triangleBox(frame.points()[tri[0]], frame.points()[tri[1]], frame.points()[tri[2]], area)) return true;
        }
        return false;
    }

    public static Vec3 nearestSurfacePoint(LivingEntity actor, Vec3 origin)
    {
        if (model() == null)
        {
            AABB box = actor.getBoundingBox();
            return new Vec3(Math.max(box.minX, Math.min(box.maxX, origin.x)), Math.max(box.minY, Math.min(box.maxY, origin.y)),
                    Math.max(box.minZ, Math.min(box.maxZ, origin.z)));
        }
        Frame frame = frame((ShamshelEntity) actor);
        return nearest(frame, frame.root(), origin, null);
    }

    private static Vec3 nearest(Frame frame, Node node, Vec3 origin, Vec3 best)
    {
        if (best != null && MeshContactMathR48.boxDistance(node.bounds(), origin) > best.distanceToSqr(origin)) return best;
        if (node.left() != null)
        {
            Node a = node.left(), b = node.right();
            if (MeshContactMathR48.boxDistance(a.bounds(), origin) > MeshContactMathR48.boxDistance(b.bounds(), origin)) { Node swap = a; a = b; b = swap; }
            return nearest(frame, b, origin, nearest(frame, a, origin, best));
        }
        Model mesh = model();
        for (int i = node.start(); i < node.end(); i++)
        {
            int[] tri = mesh.triangles()[mesh.order()[i]];
            Vec3 point = MeshContactMathR48.closestTriangle(origin, frame.points()[tri[0]], frame.points()[tri[1]], frame.points()[tri[2]]);
            if (best == null || point.distanceToSqr(origin) < best.distanceToSqr(origin)) best = point;
        }
        return best;
    }

    public static Optional<Vec3> clipBladeSweep(LivingEntity actor, Vec3 a, Vec3 b, Vec3 c, Vec3 d, double radius)
    {
        if (model() == null) return CombatBodyContacts.clipBladeBoxR45(actor.getBoundingBox().inflate(radius), a, b, c, d);
        Frame frame = frame((ShamshelEntity) actor); AABB area = new AABB(a, b).minmax(new AABB(c, d)).inflate(radius);
        Vec3 hit = blade(frame, frame.root(), area, a, b, c, d, Math.max(0, radius));
        if (hit == null) for (Vec3 point : new Vec3[]{a, b, c, d}) if (inside(frame, point)) { hit = point; break; }
        return Optional.ofNullable(hit);
    }

    private static Vec3 blade(Frame frame, Node node, AABB area, Vec3 a, Vec3 b, Vec3 c, Vec3 d, double radius)
    {
        if (!node.bounds().intersects(area)) return null;
        if (node.left() != null)
        {
            Vec3 point = blade(frame, node.left(), area, a, b, c, d, radius);
            return point != null ? point : blade(frame, node.right(), area, a, b, c, d, radius);
        }
        Model mesh = model();
        for (int i = node.start(); i < node.end(); i++)
        {
            int[] tri = mesh.triangles()[mesh.order()[i]]; Vec3 x = frame.points()[tri[0]], y = frame.points()[tri[1]], z = frame.points()[tri[2]];
            Vec3 point = MeshContactMathR48.triangles(a, b, c, x, y, z, radius);
            if (point == null) point = MeshContactMathR48.triangles(a, c, d, x, y, z, radius);
            if (point != null) return point;
        }
        return null;
    }

    private static boolean inside(Frame frame, Vec3 point)
    {
        if (!frame.root().bounds().contains(point)) return false;
        double winding = 0; Model mesh = model();
        for (int[] triangle : mesh.triangles())
            winding += MeshContactMathR48.solidAngle(point, frame.points()[triangle[0]], frame.points()[triangle[1]], frame.points()[triangle[2]]);
        return Math.abs(winding) > Math.PI * 2;
    }
}
