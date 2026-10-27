package com.projectseele.world;

import java.util.*;
import java.util.function.BooleanSupplier;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Explicit shared load datum. Constructing a state never activates or moves an entity. */
public final class CarrierMountProfileR53
{
    public static final double LOAD_ELEVATION = 4.25;
    public static final double BAY_STROKE = 1;
    public static final double SUBMERGED_BAY_STROKE = 12;
    public static final double TRANSVERSE_TRAVEL = .65;
    public static final String BAY_RECEIVER_REVISION = "independent-upper-receiver-slotted-sleeve-r54";
    public static final State LEGACY = new State(false, 0, 0);
    public static final String CHANNEL = "MountProfileR53";
    private static final String SCHEMA = "projectseele.carrier-mount.r53.v1";

    public static State read(NervCarrierPlatformEntity machine, float partial)
    {
        var tag = machine.carrierMountProfileR53();
        if (tag.isEmpty()) return LEGACY;
        validateTag(tag);
        var current = decode(tag.getCompound("Current"));
        if (!machine.level().isClientSide) return current;
        double t = machine.mechanicalVisualFractionR54("mount", tag.getLong("At"), partial);
        return decode(tag.getCompound("Previous")).interpolate(current, t);
    }

    private static CompoundTag encode(State state)
    {
        var tag = new CompoundTag();tag.putBoolean("AboveFloor", state.aboveFloor());tag.putBoolean("ShallowBay", state.shallowBay());tag.putBoolean("SupportOnly", state.supportOnly());tag.putDouble("Elevation", state.elevation());tag.putDouble("Transverse", state.transverse());return tag;
    }

    private static State decode(CompoundTag tag)
    {
        if (!tag.contains("AboveFloor", 1) || !tag.contains("Elevation", 6) || !tag.contains("Transverse", 6)) throw new IllegalStateException("Complete explicit mounting revision required");
        return new State(tag.getBoolean("AboveFloor"), tag.getDouble("Elevation"), tag.getDouble("Transverse"), tag.getBoolean("ShallowBay"), tag.getBoolean("SupportOnly"));
    }

    private static void validateTag(CompoundTag tag)
    {
        if (!SCHEMA.equals(tag.getString("Schema")) || !tag.getString("Source").matches("[0-9a-f]{64}")
                || tag.getLong("Epoch") <= 0 || !tag.contains("At", 4)) throw new IllegalStateException("Source-bound carrier mounting required");
        decode(tag.getCompound("Previous"));decode(tag.getCompound("Current"));
    }

    /** Only the world owner may construct this after a source-bound geometry proof.
     * The proof callback is rechecked at submission; this token changes no root or travel clock. */
    public static final class PreparedUpdate
    {
        private final UUID actor;private final long at;private final CompoundTag before, after;
        private final BooleanSupplier geometryCurrent;
        PreparedUpdate(NervCarrierPlatformEntity machine, String source, long epoch, State from, State to, BooleanSupplier geometryCurrent)
        { this(machine, source, epoch, from, to, geometryCurrent, false); }

        PreparedUpdate(NervCarrierPlatformEntity machine, String source, long epoch, State from, State to,
                       BooleanSupplier geometryCurrent, boolean parkedInstallation)
        {
            if (machine.level().isClientSide || !source.matches("[0-9a-f]{64}") || epoch <= 0
                    || !read(machine, 1).equals(from) || geometryCurrent == null || !geometryCurrent.getAsBoolean())
                throw new IllegalArgumentException("Current owner geometry proof required");
            var binding = machine.carrierMountProfileR53();
            if (binding.isEmpty() && (to.elevation() != 0 || to.transverse() != 0))
                throw new IllegalArgumentException("Source commissioning cannot jump the load calibration");
            if (!binding.isEmpty() && from.aboveFloor() != to.aboveFloor())
                throw new IllegalArgumentException("Lateral-only and load refit are separate source revisions");
            if (from.shallowBay() != to.shallowBay() && (from.shallowBay() || !to.shallowBay()
                    || NervOriginalCarrierR52.progress(machine, 1) != 1
                        && !(parkedInstallation && CarrierBayTrayR53.parkedInstallationCurrent(machine))))
                throw new IllegalArgumentException("Shallow bay commissioning requires the unchanged raised source pose");
            actor = machine.getUUID();at = machine.level().getGameTime();before = machine.carrierMountProfileR53();
            if (!before.isEmpty() && (!before.getString("Source").equals(source) || before.getLong("Epoch") != epoch))
                throw new IllegalArgumentException("Existing mounting source cannot be silently replaced");
            after = new CompoundTag();after.putString("Schema", SCHEMA);after.putString("Source", source);after.putLong("Epoch", epoch);
            after.putLong("At", at);after.put("Previous", encode(before.isEmpty() || from.shallowBay() != to.shallowBay() || from.supportOnly() != to.supportOnly() ? to : from));after.put("Current", encode(to));
            this.geometryCurrent = geometryCurrent;
        }
        public boolean current(NervCarrierPlatformEntity machine)
        { return !machine.level().isClientSide && actor.equals(machine.getUUID()) && at == machine.level().getGameTime()
                && before.equals(machine.carrierMountProfileR53()) && geometryCurrent.getAsBoolean(); }
        public CompoundTag next() { return after.copy(); }
    }

    public record State(boolean aboveFloor, double elevation, double transverse, boolean shallowBay, boolean supportOnly)
    {
        public State(boolean aboveFloor, double elevation, double transverse, boolean shallowBay)
        { this(aboveFloor, elevation, transverse, shallowBay, false); }
        public State(boolean aboveFloor, double elevation, double transverse)
        { this(aboveFloor, elevation, transverse, false); }

        public State
        {
            if (!Double.isFinite(elevation + transverse) || elevation < 0 || elevation > LOAD_ELEVATION
                    || transverse < 0 || transverse > 1 || !aboveFloor && elevation != 0 || shallowBay && aboveFloor || supportOnly && (aboveFloor || shallowBay))
                throw new IllegalArgumentException("Bounded explicit carrier calibration required");
        }

        public RigidTransform payloadFrame(RigidTransform controller)
        { return controller.compose(translation(elevation)); }

        public RigidTransform controllerFrame(RigidTransform payload)
        { return payload.compose(translation(-elevation)); }

        public double bodyDrop(float rise)
        {
            if (!Float.isFinite(rise) || rise < 0 || rise > 1)
                throw new IllegalArgumentException("Bounded original rise required");
            return -(shallowBay ? SUBMERGED_BAY_STROKE : aboveFloor ? BAY_STROKE : 64)
                    * Math.max(0, 1 - rise / (double)CarrierAssemblyR53.RISE_END);
        }

        public RigidTransform bodyFrame(RigidTransform controller, float rise)
        { return controller.compose(translation(elevation + bodyDrop(rise))); }

        public RigidTransform headLiftFrame(RigidTransform controller, float rise, double lift)
        {
            if (!Double.isFinite(lift) || lift < 0 || lift > CarrierRearGuideR53.STOW_LIFT)
                throw new IllegalArgumentException("Bounded physical rear lift required");
            // A shallow bay's independently stowed receiver stays above the
            // personnel edge while the mast slides through its long sleeves.
            // At the raised stop this is the unchanged route mating frame.
            return controller.compose(translation((shallowBay ? 0 : bodyDrop(rise)) + lift));
        }

        public RigidTransform carrierLocalFrame(CarrierAssemblyR53.Profile source, String part,
                                                float rise, float release, double deckTravel)
        {
            var original = source.frame(part, rise, release, deckTravel);
            if (shallowBay)
            {
                // The deck bears the EVA while the mast rises from its rear
                // service slot. Jaws close only after the mast reaches height.
                boolean deck = part.equals("deck") || part.startsWith("toe_");
                double opening = Math.max(Math.min(1, (1D - rise) / (1D - CarrierAssemblyR53.RISE_END)), release);
                boolean rod = part.startsWith("clamp_") || part.startsWith("jaw_rod_");
                boolean carriage = part.startsWith("jaw_carriage_");
                double x = rod ? (part.endsWith("_l") ? -1 : 1) * 1.5 * Math.min(1, opening * 2) : 0;
                double z = rod || carriage ? 2 * Math.max(0, opening * 2 - 1) : 0;
                return new RigidTransform(new Vec3(x, deck ? 0 : bodyDrop(rise), z), 0, 0, 0, 1);
            }
            if (!aboveFloor && !shallowBay) return original;
            boolean deck = part.equals("deck") || part.startsWith("toe_");
            var p = original.translation();
            return new RigidTransform(new Vec3(p.x, elevation + (deck ? p.y : bodyDrop(rise)), p.z), 0, 0, 0, 1);
        }

        public Vec3 shoulderMovement(Vec3 original)
        { return original.add(0, elevation, 0); }

        public Quaternionf shoulderEndRotation(Vec3 normal, Quaternionf shaft)
        {
            return aboveFloor ? new Quaternionf().rotationTo(0, 0, 1, (float)normal.x, (float)normal.y, (float)normal.z)
                    : new Quaternionf(shaft);
        }

        public RigidTransform powerReelFrame(RigidTransform controller, float rise, Vec3 sourceReel)
        { return bodyFrame(controller, rise).compose(new RigidTransform(sourceReel, 0, 0, 0, 1)); }

        public State interpolate(State to, double fraction)
        {
            if (aboveFloor != to.aboveFloor || shallowBay != to.shallowBay || supportOnly != to.supportOnly || !Double.isFinite(fraction) || fraction < 0 || fraction > 1)
                throw new IllegalArgumentException("Source migration and continuous actuator motion are separate operations");
            return new State(aboveFloor, elevation + (to.elevation - elevation) * fraction,
                    transverse + (to.transverse - transverse) * fraction, shallowBay, supportOnly);
        }
    }

    private static final Map<CarrierRearGuideR53.Hardware, List<CarrierRearGuideR53.Template>> EXTENDED = new IdentityHashMap<>();
    private static final Map<CarrierRearGuideR53.Hardware, List<CarrierRearGuideR53.Template>> BAY_SLEEVES = new IdentityHashMap<>();

    /** Only the two newly engineered rods extend; supplied source head/body triangles are untouched. */
    public static synchronized List<CarrierRearGuideR53.Template> rearTemplates(CarrierRearGuideR53.Hardware hardware, State state)
    {
        if(state.shallowBay())
        {
            var known=BAY_SLEEVES.get(hardware);if(known!=null)return known;
            var result=new ArrayList<CarrierRearGuideR53.Template>();int faces=0;
            for(var p:hardware.parts())
            {
                boolean sleeve=p.name().contains("/lift_sleeve/"),tie=p.name().contains("/lift_tie/"),isRod=p.name().endsWith("/lift_rod");
                boolean bracket=p.name().contains("/lift_bracket/"),cross=p.name().endsWith("/mount/2");
                if(!sleeve&&!tie&&!isRod&&!bracket&&!cross){result.add(p);continue;}
                if(!CarrierRearLateralR53.rectangular(p.mesh()))throw new IllegalStateException("Complete original rectangular guide required");
                String prefix=p.name().substring(0,p.name().indexOf('/',5));
                var rod=hardware.parts().stream().filter(q->q.name().equals(prefix+"/lift_rod")).findFirst().orElseThrow();
                var box=p.mesh().bounds();double centre=(rod.mesh().bounds().minX+rod.mesh().bounds().maxX)/2;
                if(bracket)
                {result.add(bayGuideBoxR54(p,p.name(),box.move(centre>0?-.14:.14,0,0)));continue;}
                if(cross)
                {
                    var trimmed=centre>0?new net.minecraft.world.phys.AABB(box.minX,box.minY,box.minZ,centre-.205,box.maxY,box.maxZ)
                            :new net.minecraft.world.phys.AABB(centre+.205,box.minY,box.minZ,box.maxX,box.maxY,box.maxZ);
                    result.add(bayGuideBoxR54(p,p.name(),trimmed));continue;
                }
                double top=rod.mesh().bounds().minY+CarrierRearGuideR53.STOW_LIFT+SUBMERGED_BAY_STROKE+.35;
                if(isRod)
                {
                    result.add(bayGuideBoxR54(p,p.name(),new net.minecraft.world.phys.AABB(centre-.2,box.minY,box.minZ,centre+.2,box.maxY,box.maxZ)));continue;
                }
                int side=Integer.parseInt(p.name().substring(p.name().lastIndexOf('/')+1));
                double high=sleeve?top:box.maxY;
                if(side==3)
                {
                    // A real open front slot lets the unchanged 0.16m cross
                    // arm traverse the guide; two cheeks still bear the rod.
                    result.add(bayGuideBoxR54(p,p.name()+"/left",new net.minecraft.world.phys.AABB(centre-.2,box.minY,box.minZ,centre-.085,high,box.maxZ)));
                    result.add(bayGuideBoxR54(p,p.name()+"/right",new net.minecraft.world.phys.AABB(centre+.085,box.minY,box.minZ,centre+.2,high,box.maxZ)));
                }
                else
                {
                    double shift=side==0?.14:side==1?-.14:0;
                    result.add(bayGuideBoxR54(p,p.name(),new net.minecraft.world.phys.AABB(box.minX+shift,box.minY,box.minZ,box.maxX+shift,high,box.maxZ)));
                }
                if(sleeve)faces++;
            }
            if(faces!=hardware.mounts().size()*4)throw new IllegalStateException("Four finite sleeve faces per original receiver required");
            var complete=List.copyOf(result);BAY_SLEEVES.put(hardware,complete);return complete;
        }
        if (!state.aboveFloor()) return hardware.parts();
        var known = EXTENDED.get(hardware);
        if (known != null) return known;
        var result = new ArrayList<CarrierRearGuideR53.Template>();int rods = 0;
        for (var p : hardware.parts())
        {
            if (!p.name().endsWith("/lift_rod")) { result.add(p);continue; }
            double top = p.mesh().bounds().maxY;double[] rgb = p.rgb().clone();
            for (int i = 0; i < rgb.length; i += 6) if (Math.abs(rgb[i + 1] - top) < 1e-8) rgb[i + 1] += LOAD_ELEVATION;
            double[] xyz = new double[rgb.length / 2];
            for (int i = 0, j = 0; i < rgb.length; i += 6) for (int k = 0; k < 3; k++) xyz[j++] = rgb[i + k];
            result.add(new CarrierRearGuideR53.Template(p.name(), p.frame(), p.role(), new NervRigidMeshSweepR52(xyz), rgb));rods++;
        }
        if (rods != 2) throw new IllegalStateException("Both original engineered rear lift rods required");
        if (EXTENDED.size() >= 4) EXTENDED.clear();
        var immutable = List.copyOf(result);EXTENDED.put(hardware, immutable);return immutable;
    }

    private static CarrierRearGuideR53.Template bayGuideBoxR54(CarrierRearGuideR53.Template source,String name,net.minecraft.world.phys.AABB to)
    {
        var from=source.mesh().bounds();double[] lo={from.minX,from.minY,from.minZ},hi={from.maxX,from.maxY,from.maxZ};
        double[] low={to.minX,to.minY,to.minZ},high={to.maxX,to.maxY,to.maxZ};var rgb=source.rgb().clone();var xyz=new double[rgb.length/2];
        for(int i=0,n=0;i<rgb.length;i+=6)for(int k=0;k<3;k++)
        {rgb[i+k]=Math.abs(rgb[i+k]-lo[k])<1e-8?low[k]:high[k];xyz[n++]=rgb[i+k];}
        return new CarrierRearGuideR53.Template(name,source.frame(),source.role(),new NervRigidMeshSweepR52(xyz),rgb);
    }

    public static RigidTransform transverseFrame(RigidTransform controller, RigidTransform frame,
                                                 CarrierRearGuideR53.Template part, State state)
    {
        if (state.transverse() == 0) return frame;
        boolean moving = part.role().equals("ball") || part.role().equals("lateral_rod")
                || part.frame().equals("rear_l") || part.frame().equals("rear_r");
        if (!moving) return frame;
        int side = part.name().startsWith("rear/rear_l/") ? -1 : 1;
        var p = frame.translation().add(controller.transformVector(new Vec3(-side * TRANSVERSE_TRAVEL * state.transverse(), 0, 0)));
        return new RigidTransform(p, frame.qx(), frame.qy(), frame.qz(), frame.qw());
    }

    private static RigidTransform translation(double y)
    { return new RigidTransform(new Vec3(0, y, 0), 0, 0, 0, 1); }

    private CarrierMountProfileR53() { }
}
