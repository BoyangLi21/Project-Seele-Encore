package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

/** Exact subset coverage of immutable source curves; no world clearance. */
public final class NervRailSourceCoverageR53
{
    private record Curve(NervRouteDirectoryR52.Leg leg, FootSupportFrameR52.Binding binding) {}
    private record Interval(double from, double to) {}

    public static boolean covers(List<DirectoryTrajectoryR52> validated,
                                 List<DirectoryTrajectoryR52> requested)
    {
        if (validated == null || requested == null) return false;
        var index = new IdentityHashMap<NervRouteDirectoryR52, Map<Curve, List<Interval>>>();
        for (var path : validated)
        {
            if (!valid(path)) return false;
            index.computeIfAbsent(path.directory(), ignored -> new HashMap<>())
                    .computeIfAbsent(new Curve(path.leg(), path.binding()), ignored -> new ArrayList<>())
                    .add(new Interval(path.fromFraction(), path.toFraction()));
        }
        for (var curves : index.values())
        {
            for (var entry : curves.entrySet())
            {
                var sorted = entry.getValue();
                sorted.sort(Comparator.comparingDouble(Interval::from).thenComparingDouble(Interval::to));
                var merged = new ArrayList<Interval>();
                for (var interval : sorted)
                {
                    if (merged.isEmpty() || interval.from() > merged.get(merged.size() - 1).to())
                        merged.add(interval);
                    else
                    {
                        var previous = merged.get(merged.size() - 1);
                        merged.set(merged.size() - 1, new Interval(previous.from(), Math.max(previous.to(), interval.to())));
                    }
                }
                entry.setValue(merged);
            }
        }
        for (var path : requested)
        {
            if (!valid(path)) return false;
            var curves = index.get(path.directory());
            var intervals = curves == null ? null : curves.get(new Curve(path.leg(), path.binding()));
            if (intervals == null) return false;
            int low = 0, high = intervals.size();
            while (low < high)
            {
                int middle = (low + high) >>> 1;
                if (intervals.get(middle).from() <= path.fromFraction()) low = middle + 1;
                else high = middle;
            }
            if (low == 0 || intervals.get(low - 1).to() < path.toFraction()) return false;
        }
        return true;
    }

    private static boolean valid(DirectoryTrajectoryR52 path)
    {
        return path != null && Double.isFinite(path.fromFraction()) && Double.isFinite(path.toFraction())
                && path.fromFraction() >= 0 && path.toFraction() <= 1
                && path.fromFraction() <= path.toFraction();
    }

    private NervRailSourceCoverageR53() {}
}