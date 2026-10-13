package com.projectseele.world;
import java.nio.file.*;

/** Actual missing/appearing/changing file hot path, without a world/server. */
public final class NervManifestPollR52Test
{
    public static void main(String[] args)throws Exception
    {
        var directory=Files.createTempDirectory("r52-manifest-negative-cache-");var file=directory.resolve("Root-explicit-only.json");int checks=0;var cache=new NervManifestPollR52();var absent=cache.probe(file,0);if(absent.available()||!absent.changed())throw new AssertionError("Missing manifest acquired readiness");checks++;
        int warnings=0;for(int tick=0;tick<1200;tick++)for(int call=0;call<12;call++){var value=cache.probe(file,tick);if(value.available())throw new AssertionError("Negative cache invented a manifest");if(cache.warningDue(value.fault(),tick))warnings++;checks++;}if(warnings!=1)throw new AssertionError("Same missing cause warned "+warnings+" times");checks++;
        Files.writeString(file,"first actual explicit manifest");if(cache.probe(file,1200).available()==false)throw new AssertionError("Created file never re-read");checks++;
        Files.writeString(file,"changed actual explicit manifest size");if(cache.probe(file,1201).changed())throw new AssertionError("Same-tick metadata hot path re-probed");checks++;cache.invalidate();if(!cache.probe(file,1201).changed())throw new AssertionError("Explicit install/file invalidation did not wake immediately");checks++;
        Files.delete(file);cache.invalidate();var deleted=cache.probe(file,1201);if(deleted.available()||!deleted.changed())throw new AssertionError("Deleted file retained readiness");checks++;if(!cache.warningDue(deleted.fault(),1201))throw new AssertionError("Elapsed bounded warning period was not honored");checks++;cache.invalidate();if(cache.warningDue(deleted.fault(),1201))throw new AssertionError("Explicit invalidate reset the same-cause warning throttle");checks++;
        if(!cache.warningDue(deleted.fault(),2401))throw new AssertionError("Stable fault never allowed bounded diagnostic refresh");checks++;Files.delete(directory);System.out.println("R52 actual manifest negative-cache/invalidate PASS checks="+checks+" hot_calls=14400 warnings=1; no legacy/geometry readiness granted");
    }
}
