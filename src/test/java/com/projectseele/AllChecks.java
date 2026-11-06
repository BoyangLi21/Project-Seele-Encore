package com.projectseele;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Runs every check in the test classes in one JVM, each on its own main method. */
public final class AllChecks
{
    /** Forge's registries lock once, so these boot it in a JVM of their own: see build.gradle. */
    private static final java.util.Set<String> OWN_JVM=java.util.Set.of("GeoFrontHeightR52Test","HakoneSurfaceFieldTest","NervBallisticLandingProfileR53Test","NervCarrierBlockReadsR53Test","SurfaceRepairReplayTest");
    public static void main(String[] args) throws Exception
    {
        var root=Path.of(AllChecks.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        List<String> names;
        try(var files=Files.walk(root))
        {
            names=files.map(p->root.relativize(p).toString().replace(java.io.File.separatorChar,'.'))
                    .filter(n->n.endsWith("Test.class")&&!n.contains("$"))
                    .map(n->n.substring(0,n.length()-".class".length()))
                    .filter(n->!OWN_JVM.contains(n.substring(n.lastIndexOf('.')+1)))
                    .filter(n->args.length==0||java.util.Arrays.stream(args).anyMatch(n::contains)).sorted().toList();
        }
        List<String> failed=new ArrayList<>();
        for(String name:names)
        {
            long start=System.nanoTime();
            try
            {
                Class.forName(name).getMethod("main",String[].class).invoke(null,(Object)new String[0]);
                System.out.printf("[ok] %s %.2fs%n",name,(System.nanoTime()-start)/1e9);
            }
            catch(ReflectiveOperationException|LinkageError e)
            {
                Throwable cause=e.getCause()==null?e:e.getCause();
                failed.add(name+": "+cause);
                System.out.printf("[FAILED] %s: %s%n",name,cause);
            }
        }
        System.out.println(names.size()-failed.size()+" of "+names.size()+" checks passed");
        if(!failed.isEmpty())throw new AssertionError(String.join("\n",failed));
    }
}
