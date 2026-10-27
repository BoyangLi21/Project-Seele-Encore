package com.projectseele.world;

import java.util.*;
import java.util.function.*;
import net.minecraft.world.phys.AABB;

/** Bounded broadphase grouping only. Each clearance call still reads live
 * native/Forge shapes and supplies every obstacle to the original source
 * narrow phase. Neither plans nor bounds confer movement admission. */
public final class BoundedNativeCollisionGroupsR52 {
    public static final int MAX_CANDIDATES_PER_PIECE=24;
    private static final int BUCKET_WINDOW=12;
    private static final double CELL=32,EPS=1e-7;
    private record Cell(long x,long y,long z) {}
    public record Group(AABB bounds,List<Integer> pieces) {
        public Group { Objects.requireNonNull(bounds);pieces=List.copyOf(pieces); }
    }
    public static final class Plan {
        private final List<AABB> pieces;
        private final List<Group> groups;
        private final int[] groupOf;
        private final long originalEstimate,groupedEstimate;
        private final int candidateChecks,maximumChecksForPiece;
        private Plan(List<AABB> pieces,List<Group> groups,int[] groupOf,long original,long grouped,int checks,int maximum) {
            this.pieces=List.copyOf(pieces);this.groups=List.copyOf(groups);this.groupOf=groupOf.clone();
            originalEstimate=original;groupedEstimate=grouped;candidateChecks=checks;maximumChecksForPiece=maximum;
        }
        public List<AABB> pieces(){return pieces;}
        public List<Group> groups(){return groups;}
        public int groupOf(int piece){return groupOf[piece];}
        public long originalCellEstimate(){return originalEstimate;}
        public long groupedCellEstimate(){return groupedEstimate;}
        public int candidateChecks(){return candidateChecks;}
        public int maximumChecksForPiece(){return maximumChecksForPiece;}
    }
    private static final class BuildingGroup {
        AABB bounds;Cell cell;final ArrayList<Integer> pieces=new ArrayList<>();
        BuildingGroup(AABB bounds,int piece){this.bounds=bounds;cell=cell(bounds);pieces.add(piece);}
    }
    /** Matches the MC 1.20.1 BlockCollisions cursor's 1e-7 expansion and
     * one-cell neighbour halo. Counts all cursor positions conservatively,
     * including boundary positions which native code can subsequently skip. */
    public static long voxelEstimate(AABB b) {
        requireFinite(b);
        long x=extent(b.minX,b.maxX),y=extent(b.minY,b.maxY),z=extent(b.minZ,b.maxZ);
        return multiply(multiply(x,y),z);
    }
    private static long extent(double min,double max){return (long)Math.floor(max+EPS)-(long)Math.floor(min-EPS)+3;}
    private static long add(long a,long b){return a>Long.MAX_VALUE-b?Long.MAX_VALUE:a+b;}
    private static long multiply(long a,long b){return a>Long.MAX_VALUE/b?Long.MAX_VALUE:a*b;}
    private static void requireFinite(AABB b) {
        Objects.requireNonNull(b);
        for(double v:new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ})
            if(!Double.isFinite(v)||Math.abs(v)>Integer.MAX_VALUE-4D)throw new IllegalArgumentException("Finite native block coordinates required");
    }
    private static Cell cell(AABB b) {
        return new Cell((long)Math.floor((b.minX+(b.maxX-b.minX)*.5)/CELL),
                        (long)Math.floor((b.minY+(b.maxY-b.minY)*.5)/CELL),
                        (long)Math.floor((b.minZ+(b.maxZ-b.minZ)*.5)/CELL));
    }
    private static void index(Map<Cell,ArrayDeque<Integer>> buckets,Cell cell,int id) {
        var row=buckets.computeIfAbsent(cell,unused->new ArrayDeque<>());
        row.addLast(id);if(row.size()>BUCKET_WINDOW)row.removeFirst();
    }
    public static Plan plan(List<AABB> input) {
        var pieces=List.copyOf(input);var groups=new ArrayList<BuildingGroup>();
        var buckets=new HashMap<Cell,ArrayDeque<Integer>>();int[] groupOf=new int[pieces.size()];
        long original=0;int totalChecks=0,maximumChecks=0;
        for(int piece=0;piece<pieces.size();piece++) {
            var box=pieces.get(piece);long cost=voxelEstimate(box);original=add(original,cost);Cell near=cell(box);
            int best=-1,checks=0;long bestSaving=0;AABB bestBounds=null;
            search:for(int dx=-1;dx<=1;dx++)for(int dy=-1;dy<=1;dy++)for(int dz=-1;dz<=1;dz++) {
                var key=new Cell(near.x+dx,near.y+dy,near.z+dz);var row=buckets.get(key);if(row==null)continue;
                for(var iterator=row.descendingIterator();iterator.hasNext();) {
                    if(checks>=MAX_CANDIDATES_PER_PIECE)break search;
                    int id=iterator.next();var group=groups.get(id);checks++;
                    var union=group.bounds.minmax(box);long prior=voxelEstimate(group.bounds),merged=voxelEstimate(union),sum=add(prior,cost);
                    // A saturated estimate cannot justify a measured saving.
                    if(sum==Long.MAX_VALUE||merged>=sum)continue;
                    long saving=sum-merged;
                    if(saving>bestSaving){best=id;bestSaving=saving;bestBounds=union;}
                }
            }
            totalChecks+=checks;maximumChecks=Math.max(maximumChecks,checks);
            if(best<0){best=groups.size();groups.add(new BuildingGroup(box,piece));index(buckets,near,best);}
            else {
                var group=groups.get(best);Cell old=group.cell;group.bounds=bestBounds;group.pieces.add(piece);group.cell=cell(bestBounds);
                if(!old.equals(group.cell)) {
                    var row=buckets.get(old);if(row!=null){row.remove(best);if(row.isEmpty())buckets.remove(old);}
                    index(buckets,group.cell,best);
                }
            }
            groupOf[piece]=best;
        }
        var result=new ArrayList<Group>();long grouped=0;
        for(var group:groups){result.add(new Group(group.bounds,group.pieces));grouped=add(grouped,voxelEstimate(group.bounds));}
        return new Plan(pieces,result,groupOf,original,grouped,totalChecks,maximumChecks);
    }
    public record Result(boolean clear,Plan plan,int nativeReads,int groupedReads,int originalFallbackReads,
                         long readCellEstimate,long obstaclesPassedToNarrowPhase) {}
    private static final Comparator<AABB> EXACT_BOX_ORDER=Comparator.comparingDouble((AABB b)->b.minX)
            .thenComparingDouble(b->b.minY).thenComparingDouble(b->b.minZ)
            .thenComparingDouble(b->b.maxX).thenComparingDouble(b->b.maxY).thenComparingDouble(b->b.maxZ);
    /** The predicate checks the complete source spatial index, not one piece.
     * Visit each group's native shapes once. Exact cross-group deduplication
     * is invocation-local; Double.compare preserves AABB's signed-zero and
     * equality semantics without its grid-coordinate hash distribution. */
    public static Result clearWholeSource(List<AABB> pieces,Predicate<AABB> readableGroup,
            Function<AABB,List<AABB>> liveNativeShapes,Predicate<AABB> wholeSourceIntersects) {
        Objects.requireNonNull(readableGroup);Objects.requireNonNull(liveNativeShapes);Objects.requireNonNull(wholeSourceIntersects);
        Plan plan=plan(pieces);var seen=new TreeSet<AABB>(EXACT_BOX_ORDER);
        int reads=0,groupReads=0,fallbackReads=0;long cells=0,obstacles=0;
        for(var group:plan.groups) {
            boolean grouped=readableGroup.test(group.bounds);
            int count=grouped?1:group.pieces.size();
            for(int i=0;i<count;i++) {
                var query=grouped?group.bounds:plan.pieces.get(group.pieces.get(i));
                if(!grouped&&!readableGroup.test(query))return new Result(false,plan,reads,groupReads,fallbackReads,cells,obstacles);
                var shapes=liveNativeShapes.apply(query);reads++;if(grouped)groupReads++;else fallbackReads++;
                cells=add(cells,voxelEstimate(query));
                for(var obstacle:shapes) {
                    if(!seen.add(obstacle))continue;
                    obstacles++;
                    if(wholeSourceIntersects.test(obstacle))return new Result(false,plan,reads,groupReads,fallbackReads,cells,obstacles);
                }
            }
        }
        return new Result(true,plan,reads,groupReads,fallbackReads,cells,obstacles);
    }
    /** All fetched shapes are local to this invocation. The readable predicate
     * lets the caller retain original reads if a merged gap would touch an
     * unloaded region. It must not be an air/material shortcut. The reader
     * must call the same live native API with the same actor CollisionContext.
     * The callback must perform the complete original source narrow phase;
     * a merged bounds intersection never substitutes for that predicate. */
    public static Result clear(List<AABB> pieces,Predicate<AABB> readableGroup,
            Function<AABB,List<AABB>> liveNativeShapes,BiPredicate<Integer,AABB> originalSourceIntersects) {
        Objects.requireNonNull(readableGroup);Objects.requireNonNull(liveNativeShapes);Objects.requireNonNull(originalSourceIntersects);
        Plan plan=plan(pieces);var fetched=new ArrayList<List<AABB>>(Collections.nCopies(plan.groups.size(),null));
        boolean[] fallback=new boolean[plan.groups.size()],decided=new boolean[plan.groups.size()];
        int reads=0,groupReads=0,fallbackReads=0;long cells=0,obstacles=0;
        for(int piece=0;piece<plan.pieces.size();piece++) {
            int id=plan.groupOf(piece);var group=plan.groups.get(id);
            if(!decided[id]){fallback[id]=!readableGroup.test(group.bounds);decided[id]=true;}
            List<AABB> shapes;
            if(fallback[id]) {
                var box=plan.pieces.get(piece);
                if(!readableGroup.test(box))return new Result(false,plan,reads,groupReads,fallbackReads,cells,obstacles);
                shapes=List.copyOf(liveNativeShapes.apply(box));reads++;fallbackReads++;cells=add(cells,voxelEstimate(box));
            } else {
                shapes=fetched.get(id);
                if(shapes==null){shapes=List.copyOf(liveNativeShapes.apply(group.bounds));fetched.set(id,shapes);reads++;groupReads++;cells=add(cells,voxelEstimate(group.bounds));}
            }
            for(var obstacle:shapes) {
                obstacles++;
                if(originalSourceIntersects.test(piece,obstacle))return new Result(false,plan,reads,groupReads,fallbackReads,cells,obstacles);
            }
        }
        return new Result(true,plan,reads,groupReads,fallbackReads,cells,obstacles);
    }
    private BoundedNativeCollisionGroupsR52() {}
}
