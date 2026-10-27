package com.projectseele.world;

import java.util.Arrays;
import java.util.List;
import net.minecraft.world.phys.Vec3;

/** Pure path interval tests; no Level, actors, geometry evaluation or clearance. */
public final class NervRailSourceCoverageR53Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }
    private static DirectoryTrajectoryR52 path(NervRouteDirectoryR52 directory,
            FootSupportFrameR52.Binding binding, String leg, double from, double to)
    {
        return new DirectoryTrajectoryR52(directory, directory.leg(leg), binding, from, to);
    }
    public static void main(String[] args)
    {
        var json = NervRouteCoreR52Test.rootFixtureForNativeBindingTest();
        var directory = NervRouteDirectoryR52.parse(json);
        var otherDirectory = NervRouteDirectoryR52.parse(json.deepCopy());
        var binding = new FootSupportFrameR52.Binding(new Vec3(-1, 0, 0), new Vec3(1, 0, 0), RigidTransform.identity());
        var equalBinding = new FootSupportFrameR52.Binding(new Vec3(-1, 0, 0), new Vec3(1, 0, 0), RigidTransform.identity());
        var otherBinding = new FootSupportFrameR52.Binding(new Vec3(-2, 0, 0), new Vec3(2, 0, 0), RigidTransform.identity());
        var whole = path(directory, binding, "original1", 0, 1);
        var middle = path(directory, binding, "original1", .2, .8);
        check(NervRailSourceCoverageR53.covers(List.of(whole), List.of(middle)), "Subset rejected");
        check(!NervRailSourceCoverageR53.covers(List.of(middle), List.of(whole)), "Superset accepted");
        var joined = List.of(path(directory, binding, "original1", .4, .8),
                path(directory, binding, "original1", 0, .4), path(directory, binding, "original1", .3, .5));
        check(NervRailSourceCoverageR53.covers(joined, List.of(middle)), "Unordered overlapping/touching union rejected");
        var gap = List.of(path(directory, binding, "original1", 0, .4),
                path(directory, binding, "original1", Math.nextUp(.4), 1));
        check(!NervRailSourceCoverageR53.covers(gap, List.of(whole)), "One-ULP gap silently bridged");
        check(NervRailSourceCoverageR53.covers(gap, gap), "Separate requested windows need not fill an unrequested gap");
        check(NervRailSourceCoverageR53.covers(joined, List.of(path(directory, binding, "original1", .4, .4))), "Validated point rejected");
        check(!NervRailSourceCoverageR53.covers(List.of(middle), List.of(path(directory, binding, "original1", .1, .1))), "Unvalidated point accepted");
        check(NervRailSourceCoverageR53.covers(List.of(whole), List.of(path(directory, equalBinding, "original1", .2, .8))), "Value-equal binding rejected");
        check(!NervRailSourceCoverageR53.covers(List.of(whole), List.of(path(directory, otherBinding, "original1", .2, .8))), "Different binding accepted");
        check(!NervRailSourceCoverageR53.covers(List.of(whole), List.of(path(otherDirectory, binding, "original1", .2, .8))), "Equivalent but distinct directory accepted");
        var reverse = path(directory, binding, "reverse_original1", 0, 1);
        check(!NervRailSourceCoverageR53.covers(List.of(whole), List.of(reverse)), "Different/reverse leg accepted");
        check(NervRailSourceCoverageR53.covers(List.of(whole, reverse), List.of(middle, reverse)), "Independent validated curves rejected");
        check(!NervRailSourceCoverageR53.covers(List.of(whole), List.of(middle, reverse)), "Only first requested segment was checked");
        check(!NervRailSourceCoverageR53.covers(List.of(), List.of(middle)), "Missing validation accepted");
        check(NervRailSourceCoverageR53.covers(List.of(), List.of()), "Empty requested set must be vacuously covered");
        check(!NervRailSourceCoverageR53.covers(null, List.of()), "Null validation accepted");
        check(!NervRailSourceCoverageR53.covers(List.of(whole), null), "Null request accepted");
        check(!NervRailSourceCoverageR53.covers(Arrays.asList((DirectoryTrajectoryR52)null), List.of()), "Null validated element accepted");
        check(!NervRailSourceCoverageR53.covers(List.of(whole), Arrays.asList((DirectoryTrajectoryR52)null)), "Null requested element accepted");
        boolean backwardsRejected = false;
        try { path(directory, binding, "original1", .8, .2); }
        catch (IllegalArgumentException expected) { backwardsRejected = true; }
        check(backwardsRejected, "Trajectory constructor admitted reverse fractions");
        System.out.println("PASS exact immutable rail-source coverage checks=" + checks);
    }
}