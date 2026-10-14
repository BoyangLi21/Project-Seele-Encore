import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.*;

/** Runs the installed MC DDA with an in-memory availability predicate; no Level or server is created. */
public final class SbwDefenseLosDdaChecksR56
{
    private static Method dda, x, y, z;
    private static Constructor<?> vector;
    private static final List<Map<String,Object>> rows = new ArrayList<>();
    private static Method method(Class<?> owner, String... names) throws Exception
    {
        for (String name : names) try { return owner.getMethod(name); } catch (NoSuchMethodException absent) { }
        throw new NoSuchMethodException(Arrays.toString(names));
    }
    private static final class Availability
    {
        final Set<String> loaded, probes = new LinkedHashSet<>();
        int outsideHeightCells, calls;
        Availability(Set<String> loaded) { this.loaded = loaded; }
    }
    private static void check(String name, double[] from, double[] to, Set<String> loaded,
            boolean expected, Set<String> expectedProbes, boolean expectedOutsideHeight) throws Exception
    {
        Availability context = new Availability(loaded);
        BiFunction<Availability,Object,Boolean> visit = (world, pos) ->
        {
            try
            {
                int px = ((Number)x.invoke(pos)).intValue(), py = ((Number)y.invoke(pos)).intValue(), pz = ((Number)z.invoke(pos)).intValue();
                if (py < -640 || py >= 2048) { world.outsideHeightCells++; return null; }
                world.calls++;
                String chunk = (px >> 4) + "," + (pz >> 4); world.probes.add(chunk);
                return world.loaded.contains(chunk) ? null : Boolean.FALSE;
            }
            catch (ReflectiveOperationException failure) { throw new RuntimeException(failure); }
        };
        boolean actual = (Boolean)dda.invoke(null, vector.newInstance(from[0],from[1],from[2]),
                vector.newInstance(to[0],to[1],to[2]), context, visit, (Function<Availability,Boolean>)world -> Boolean.TRUE);
        if (actual != expected || !context.probes.equals(expectedProbes)
                || (context.outsideHeightCells > 0) != expectedOutsideHeight)
            throw new AssertionError(name + ": result=" + actual + " probes=" + context.probes + " outside=" + context.outsideHeightCells);
        var row = new LinkedHashMap<String,Object>(); row.put("case",name); row.put("passed",true);
        row.put("from",from); row.put("to",to); row.put("available_chunks",loaded); row.put("result",actual);
        row.put("native_dda_probed_chunks",context.probes); row.put("native_dda_in_height_cells",context.calls);
        row.put("native_dda_outside_height_cells",context.outsideHeightCells); rows.add(row);
    }
    public static void main(String[] args) throws Exception
    {
        if (args.length != 1) throw new IllegalArgumentException("Fresh external report path required");
        Path output = Path.of(args[0]).toAbsolutePath().normalize();
        if (Files.exists(output)) throw new IllegalArgumentException("Fresh report required");
        for (Path p=output;p!=null;p=p.getParent()) if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock"))) throw new IllegalArgumentException("Output inside World");
        Class<?> v = Class.forName("net.minecraft.world.phys.Vec3"), p = Class.forName("net.minecraft.core.BlockPos");
        vector = v.getConstructor(double.class,double.class,double.class);
        x=method(p,"getX","m_123341_"); y=method(p,"getY","m_123342_"); z=method(p,"getZ","m_123343_");
        Class<?> getter=Class.forName("net.minecraft.world.level.BlockGetter");
        for(String name:List.of("traverseBlocks","m_151361_"))try{dda=getter.getMethod(name,v,v,Object.class,BiFunction.class,Function.class);break;}catch(NoSuchMethodException absent){}
        if(dda==null)throw new NoSuchMethodException("actual native DDA");
        check("middle_missing_stops_before_loaded_destination",new double[]{.5,64,.5},new double[]{48.5,64,.5},Set.of("0,0","1,0","3,0"),false,Set.of("0,0","1,0","2,0"),false);
        check("same_long_ray_all_loaded_continues_native_los",new double[]{.5,64,.5},new double[]{48.5,64,.5},Set.of("0,0","1,0","2,0","3,0"),true,Set.of("0,0","1,0","2,0","3,0"),false);
        check("negative_floor_and_three_chunks",new double[]{-.5,64,-.5},new double[]{-32.5,64,-.5},Set.of("-1,-1","-2,-1","-3,-1"),true,Set.of("-1,-1","-2,-1","-3,-1"),false);
        check("negative_exact_endpoint_epsilon_requires_next_chunk",new double[]{-.5,64,-.5},new double[]{-16,64,-.5},Set.of("-1,-1"),false,Set.of("-1,-1","-2,-1"),false);
        check("corner_native_tie_order_missing_side_chunk",new double[]{15.5,64,15.5},new double[]{16.5,64,16.5},Set.of("0,0","1,1"),false,Set.of("0,0","0,1"),false);
        check("corner_all_native_tie_order_chunks_loaded",new double[]{15.5,64,15.5},new double[]{16.5,64,16.5},Set.of("0,0","0,1","1,1"),true,Set.of("0,0","0,1","1,1"),false);
        check("exact_start_boundary_native_epsilon_requires_left_chunk",new double[]{16,64,.5},new double[]{16.5,64,.5},Set.of("1,0"),false,Set.of("0,0"),false);
        check("zero_length_native_miss_does_not_probe",new double[]{16,64,.5},new double[]{16,64,.5},Set.of(),true,Set.of(),false);
        check("above_build_height_known_air_without_chunk",new double[]{.5,2049,.5},new double[]{48.5,2049,.5},Set.of(),true,Set.of(),true);
        check("below_build_height_known_air_without_chunk",new double[]{.5,-641,.5},new double[]{48.5,-641,.5},Set.of(),true,Set.of(),true);
        check("height_boundary_rejects_first_in_height_missing_chunk",new double[]{.5,-640.5,.5},new double[]{.5,-639.5,.5},Set.of(),false,Set.of("0,0"),true);
        var report=new LinkedHashMap<String,Object>();report.put("passed",true);report.put("checks",rows.size());report.put("actual_native_method",dda.toString());
        report.put("minecraft_class_source",getter.getProtectionDomain().getCodeSource().getLocation().toString());
        report.put("scope","Actual MC DDA boundary checks with an in-memory availability predicate; no Level/server/World creation, no loaded-world or cold-restart PASS");report.put("cases",rows);
        Object gson=Class.forName("com.google.gson.Gson").getConstructor().newInstance();
        Files.createDirectories(output.getParent());Files.writeString(output,gson.getClass().getMethod("toJson",Object.class).invoke(gson,report)+"\n");
        System.out.println("PASS "+rows.size()+" actual native DDA cases; no World created");
    }
}
