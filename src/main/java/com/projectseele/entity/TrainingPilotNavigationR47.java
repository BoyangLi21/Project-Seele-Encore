package com.projectseele.entity;

import com.projectseele.world.FacilityEdgeRailR41;
import com.projectseele.world.CityPersonnelDoorR44;
import com.projectseele.world.EntryPlugBridgeDeckR48;
import com.projectseele.world.TrainingPilotDirector;
import com.projectseele.world.TvPersonnelDeckR44;
import com.projectseele.world.TvPersonnelGuardR44;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.navigation.GroundPathNavigation;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.pathfinder.BlockPathTypes;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.level.pathfinder.PathFinder;
import net.minecraft.world.level.pathfinder.WalkNodeEvaluator;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Original pilots may stand beside a partial rail, but never path through it. */
public final class TrainingPilotNavigationR47 extends GroundPathNavigation
{
    private record DeclaredDomainR47(int minX,int minY,int minZ,int maxX,int maxY,int maxZ)
    {
        boolean contains(int x,int y,int z)
        {return x>=minX&&x<=maxX&&y>=minY&&y<=maxY&&z>=minZ&&z<=maxZ;}
    }
    private DeclaredDomainR47 declaredDomainR47;
    private PathFinder ownedFinderR47;
    private int configuredNodeBudgetR47,expandedNodesR47,domainRejectedR47,unsupportedRejectedR47,sweepRejectedR47,maxWalkRejectedR47;
    private float queryMaxWalkR47;
    private float queryVisitedMultiplierR47=Float.NaN;
    private String firstMaxWalkRejectionR47="none",lastSearchR47="not_searched";

    public TrainingPilotNavigationR47(Mob mob,Level level) { super(mob,level); }

    @Override protected PathFinder createPathFinder(int range)
    {
        // This is the actual constructor input, not a guessed historical limit.
        this.configuredNodeBudgetR47=range;
        this.nodeEvaluator=new WalkNodeEvaluator()
        {
            @Override public Node getStart()
            {
                Node original=super.getStart();
                if(TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,
                        new BlockPos(original.x,original.y,original.z))!=null)return original;
                Mob actor=TrainingPilotNavigationR47.this.mob;
                BlockPos pos=new BlockPos(Mth.floor(actor.getX()),Mth.ceil(actor.getY()-1.0E-7),Mth.floor(actor.getZ()));
                if(TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,pos)==null)return original;
                Node exact=getNode(pos);
                exact.type=getBlockPathType(TrainingPilotNavigationR47.this.level,pos.getX(),pos.getY(),pos.getZ(),actor);
                exact.costMalus=actor.getPathfindingMalus(exact.type);
                return exact;
            }

            @Override public BlockPathTypes getBlockPathType(BlockGetter view,int x,int y,int z,Mob actor)
            {
                if(declaredDomainR47!=null&&!declaredDomainR47.contains(x,y,z))
                {domainRejectedR47++;return BlockPathTypes.BLOCKED;}
                BlockPathTypes original=super.getBlockPathType(view,x,y,z,actor);
                BlockPos pos=new BlockPos(x,y,z);
                if(!partialSurface(view,pos))return original;
                // Preserve native fluids, doors and hazards. Only custom partial
                // guard/deck cells get a more precise interpretation of FENCE.
                if(original!=BlockPathTypes.FENCE&&original!=BlockPathTypes.BLOCKED
                        &&original!=BlockPathTypes.OPEN&&original!=BlockPathTypes.WALKABLE)return original;
                Vec3 sole=TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,pos);
                return sole==null?original:BlockPathTypes.WALKABLE;
            }

            @Override protected double getFloorLevel(BlockPos pos)
            {
                Vec3 sole=TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,pos);
                return sole==null?super.getFloorLevel(pos):sole.y;
            }

            @Override public int getNeighbors(Node[] nodes,Node current)
            {
                if(declaredDomainR47!=null)
                {
                    // Native PathFinder overwrites a neighbor's walkedDistance
                    // before better-g decides whether to replace cameFrom.
                    // Restore this popped node's real accepted parent-chain
                    // metric before the unchanged native 96m range calculation.
                    var chain=new java.util.ArrayList<Node>();
                    var seen=new java.util.IdentityHashMap<Node,Boolean>();
                    Node cursor=current;String unknown=null;
                    while(cursor!=null)
                    {
                        if(seen.put(cursor,Boolean.TRUE)!=null){unknown="cameFrom_cycle";break;}
                        if(chain.size()>Math.max(1,configuredNodeBudgetR47)){unknown="cameFrom_chain_exceeds_constructor_budget";break;}
                        chain.add(cursor);cursor=cursor.cameFrom;
                    }
                    float acceptedDistance=0;
                    if(unknown==null)for(int i=chain.size()-1;i>0;i--)
                    {
                        float edge=chain.get(i).distanceTo(chain.get(i-1));
                        if(!Float.isFinite(edge)||edge<0){unknown="nonfinite_or_negative_native_edge";break;}
                        acceptedDistance+=edge;
                    }
                    var diagnostics=this.mob.getPersistentData();
                    float oldDistance=current.walkedDistance;
                    if(unknown==null&&(!Float.isFinite(acceptedDistance)||!Float.isFinite(oldDistance)||oldDistance<0))
                        unknown="nonfinite_or_negative_native_distance";
                    if(unknown!=null)
                    {
                        diagnostics.putString("SeelePilotWalkedCacheRepairUnknownR47",unknown+" node="
                                +new BlockPos(current.x,current.y,current.z));
                    }
                    else if(Float.compare(oldDistance,acceptedDistance)!=0)
                    {
                        current.walkedDistance=acceptedDistance;
                        long count=diagnostics.getLong("SeelePilotWalkedCacheRepairCountR47");
                        diagnostics.putLong("SeelePilotWalkedCacheRepairCountR47",count==Long.MAX_VALUE?count:count+1);
                        if(!diagnostics.contains("SeelePilotWalkedCacheFirstRepairR47"))
                        {
                            String first="node="+new BlockPos(current.x,current.y,current.z)+" old="+oldDistance
                                    +" acceptedCameFrom="+acceptedDistance+" chainNodes="+chain.size()
                                    +" metric=Node.distanceTo limit="+queryMaxWalkR47;
                            diagnostics.putString("SeelePilotWalkedCacheFirstRepairR47",first);
                            com.projectseele.ProjectSeele.LOGGER.info("NERV original pilot walked cache repaired: uuid={} {}",
                                    this.mob.getStringUUID(),first);
                        }
                    }
                }
                expandedNodesR47++;
                int count=super.getNeighbors(nodes,current),accepted=0;
                Vec3 from=TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,
                        new BlockPos(current.x,current.y,current.z));
                for(int i=0;i<count;i++)
                {
                    Node next=nodes[i];
                    Vec3 to=TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,
                            new BlockPos(next.x,next.y,next.z));
                    if(declaredDomainR47!=null&&!declaredDomainR47.contains(next.x,next.y,next.z))
                    {domainRejectedR47++;continue;}
                    if(from==null||to==null){unsupportedRejectedR47++;continue;}
                    if(!clearStep(from,to)){sweepRejectedR47++;continue;}
                    nodes[accepted++]=next;
                }
                // Vanilla's integer BLOCKED->jump/fall recursion can omit a
                // .25m tread whose sole and node have different Y coordinates.
                // Add only adjacent real, grounded step-height transitions;
                // the same body/sweep checks still prohibit rail shortcuts.
                if(from!=null)
                {
                    BlockPos here=new BlockPos(current.x,current.y,current.z);
                    for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++)
                    {
                        // Retain vanilla's diagonal corner/support rules;
                        // supplemental fractional transitions are cardinal.
                        if(Math.abs(dx)+Math.abs(dz)!=1)continue;
                        for(int dy=-1;dy<=1;dy++)
                        {
                            BlockPos at=here.offset(dx,dy,dz);
                            if(declaredDomainR47!=null&&!declaredDomainR47.contains(at.getX(),at.getY(),at.getZ()))
                            {domainRejectedR47++;continue;}
                            if(!partialSurface(TrainingPilotNavigationR47.this.level,here)
                                    &&!partialSurface(TrainingPilotNavigationR47.this.level,at))continue;
                            Vec3 to=TrainingPilotDirector.nativeNodeFeetR47(TrainingPilotNavigationR47.this.level,at);
                            if(to==null||Math.abs(to.y-from.y)>TrainingPilotNavigationR47.this.mob.getStepHeight()+1.0E-7
                                    ||!clearStep(from,to))continue;
                            BlockPathTypes type=getBlockPathType(TrainingPilotNavigationR47.this.level,
                                    at.getX(),at.getY(),at.getZ(),TrainingPilotNavigationR47.this.mob);
                            if(type!=BlockPathTypes.WALKABLE)continue;
                            Node next=getNode(at);
                            if(next.closed)continue;
                            boolean duplicate=false;
                            for(int i=0;i<accepted;i++)if(nodes[i]==next){duplicate=true;break;}
                            if(duplicate||accepted>=nodes.length)continue;
                            next.type=type;
                            next.costMalus=Math.max(next.costMalus,TrainingPilotNavigationR47.this.mob.getPathfindingMalus(type));
                            nodes[accepted++]=next;
                        }
                    }
                }
                // Read exactly the native PathFinder's next walkedDistance
                // calculation. Do not reject or modify that candidate here.
                for(int i=0;i<accepted;i++)
                {
                    Node next=nodes[i];float walked=current.walkedDistance+current.distanceTo(next);
                    if(walked>=queryMaxWalkR47)
                    {
                        maxWalkRejectedR47++;
                        if(firstMaxWalkRejectionR47.equals("none"))firstMaxWalkRejectionR47="from="
                                +new BlockPos(current.x,current.y,current.z)+" to="+new BlockPos(next.x,next.y,next.z)
                                +" currentWalked="+current.walkedDistance+" nextWalked="+walked+" limit="+queryMaxWalkR47;
                    }
                }
                return accepted;
            }
        };
        this.nodeEvaluator.setCanPassDoors(true);
        // Owned gate pairs are opened by the director's actual finite interlock.
        this.nodeEvaluator.setCanOpenDoors(false);
        this.ownedFinderR47=new PathFinder(this.nodeEvaluator,range);
        return this.ownedFinderR47;
    }

    @Override public Path createPath(BlockPos target,int accuracy)
    {
        boolean ordinary=declaredDomainR47==null;
        if(ordinary)beginSearchEvidenceR47();
        // GroundPathNavigation normally moves a solid target up above its
        // voxel. A thin guard shares the target's legal floor cell, so retain
        // that precise target through the original bounded native path finder.
        Path result=TrainingPilotDirector.nativeNodeFeetR47(level,target)!=null
                ?createPath(java.util.Set.of(target),8,false,accuracy):super.createPath(target,accuracy);
        if(ordinary)finishSearchEvidenceR47(result);
        return result;
    }

    /** Only the director's explicit original boarding/return course uses this domain. */
    public Path createDeclaredRoutePathR47(BlockPos target,java.util.List<BlockPos> declared)
    {
        if(declared.size()<3)return createPath(target,0);
        int minX=mob.blockPosition().getX(),maxX=minX,minZ=mob.blockPosition().getZ(),maxZ=minZ;
        int minY=Mth.ceil(mob.getY()-1.0E-7),maxY=minY;
        for(BlockPos node:declared)
        {
            minX=Math.min(minX,node.getX());maxX=Math.max(maxX,node.getX());
            minY=Math.min(minY,node.getY());maxY=Math.max(maxY,node.getY());
            minZ=Math.min(minZ,node.getZ());maxZ=Math.max(maxZ,node.getZ());
        }
        DeclaredDomainR47 previous=declaredDomainR47;
        // Five cells include the complete measured lower side aisle (unit00
        // X-31..-29), both ramp cells/guards and the rear approach through the dock.
        // The vertical node band is the declared real foot band, not a room
        // inferred from air. The 96 distance and constructor budget stay native.
        declaredDomainR47=new DeclaredDomainR47(minX-5,minY,minZ-5,maxX+5,maxY,maxZ+5);
        beginSearchEvidenceR47();
        Path active=path;boolean hideIncompatibleCache=false;
        if(active!=null)for(int i=0;i<active.getNodeCount();i++)
        {
            Node node=active.getNode(i);
            if(!declaredDomainR47.contains(node.x,node.y,node.z)){hideIncompatibleCache=true;break;}
        }
        // Native createPath caches by goal, not our scoped domain. A path
        // outside this domain must not bypass the single intended search.
        // Restore the active path before returning; no movement tick occurs here.
        if(hideIncompatibleCache)path=null;
        try
        {
            Path result=createPath(target,0);finishSearchEvidenceR47(result);return result;
        }
        finally{if(hideIncompatibleCache)path=active;declaredDomainR47=previous;}
    }

    private void beginSearchEvidenceR47()
    {
        expandedNodesR47=domainRejectedR47=unsupportedRejectedR47=sweepRejectedR47=maxWalkRejectedR47=0;
        queryMaxWalkR47=(float)mob.getAttributeValue(Attributes.FOLLOW_RANGE);
        queryVisitedMultiplierR47=readNativeVisitedMultiplierR47();
        firstMaxWalkRejectionR47="none";
    }

    private float readNativeVisitedMultiplierR47()
    {
        // Official and raw Forge names differ. The actual base ABI has one
        // private nonstatic float input; ambiguity/access failure is unknown,
        // never permission to change the native budget or deny movement.
        try
        {
            java.lang.reflect.Field input=null;
            for(var field:net.minecraft.world.entity.ai.navigation.PathNavigation.class.getDeclaredFields())
                if(field.getType()==float.class&&java.lang.reflect.Modifier.isPrivate(field.getModifiers())
                        &&!java.lang.reflect.Modifier.isStatic(field.getModifiers()))
                {if(input!=null)return Float.NaN;input=field;}
            return input!=null&&input.trySetAccessible()?input.getFloat(this):Float.NaN;
        }
        catch(ReflectiveOperationException|RuntimeException unavailable){return Float.NaN;}
    }

    private void finishSearchEvidenceR47(Path result)
    {
        String terminal=result!=null&&result.canReach()?"reached":"native_unreachable_reason_not_proven";
        Boolean pendingOpen=readNativePendingOpenR47();
        int actualBudget=Float.isFinite(queryVisitedMultiplierR47)&&queryVisitedMultiplierR47>=0
                ?(int)(configuredNodeBudgetR47*queryVisitedMultiplierR47):-1;
        if(result!=null&&!result.canReach()&&declaredDomainR47!=null)
        {
            var origin=mob.blockPosition();
            double x=Math.max(Math.abs(declaredDomainR47.minX-origin.getX()),Math.abs(declaredDomainR47.maxX-origin.getX()))+1;
            double y=Math.max(Math.abs(declaredDomainR47.minY-origin.getY()),Math.abs(declaredDomainR47.maxY-origin.getY()))+1;
            double z=Math.max(Math.abs(declaredDomainR47.minZ-origin.getZ()),Math.abs(declaredDomainR47.maxZ-origin.getZ()))+1;
            // Inside this bounded domain every popped node is below the
            // native radial distance bound, so each pop calls getNeighbors.
            if(x*x+y*y+z*z<queryMaxWalkR47*queryMaxWalkR47
                    &&actualBudget>0&&expandedNodesR47==actualBudget-1&&Boolean.TRUE.equals(pendingOpen))
                terminal="visited_budget_exhausted_in_declared_domain";
        }
        lastSearchR47="domain="+declaredDomainR47+" maxWalk="+queryMaxWalkR47+" constructorNodeBudget="+configuredNodeBudgetR47
                +" actualVisitedMultiplier="+(Float.isFinite(queryVisitedMultiplierR47)?Float.toString(queryVisitedMultiplierR47):"unknown")
                +" actualNodeBudget="+(actualBudget>=0?Integer.toString(actualBudget):"unknown")
                +" nativeOpenPending="+(pendingOpen==null?"unknown":pendingOpen.toString())
                +" expanded="+expandedNodesR47+" domainRejected="+domainRejectedR47+" unsupportedRejected="+unsupportedRejectedR47
                +" sweepRejected="+sweepRejectedR47+" nativeMaxWalkRejected="+maxWalkRejectedR47
                +" firstNativeMaxWalkRejection={"+firstMaxWalkRejectionR47+"} cachedOrNoExpansion="+(expandedNodesR47==0)
                +" terminal="+terminal;
    }

    private Boolean readNativePendingOpenR47()
    {
        try
        {
            java.lang.reflect.Field input=null;
            for(var field:PathFinder.class.getDeclaredFields())
                if(field.getType()==net.minecraft.world.level.pathfinder.BinaryHeap.class
                        &&!java.lang.reflect.Modifier.isStatic(field.getModifiers()))
                {if(input!=null)return null;input=field;}
            return input!=null&&input.trySetAccessible()&&ownedFinderR47!=null
                    ?!((net.minecraft.world.level.pathfinder.BinaryHeap)input.get(ownedFinderR47)).isEmpty():null;
        }
        catch(ReflectiveOperationException|RuntimeException unavailable){return null;}
    }

    public String lastSearchEvidenceR47(){return lastSearchR47;}

    private static boolean partialSurface(BlockGetter view,BlockPos pos)
    {
        for(int y=-1;y<=1;y++)
        {
            var block=view.getBlockState(pos.offset(0,y,0)).getBlock();
            String id=BuiltInRegistries.BLOCK.getKey(block).toString();
            if(block instanceof TvPersonnelGuardR44||block instanceof FacilityEdgeRailR41
                    ||block instanceof com.projectseele.world.NervRoomPartitionR47
                    ||block instanceof TvPersonnelDeckR44||block instanceof EntryPlugBridgeDeckR48
                    ||id.equals("mtr:escalator_step"))return true;
        }
        return false;
    }

    @Override protected double getGroundY(Vec3 nodePosition)
    {
        Vec3 sole=TrainingPilotDirector.nativeNodeFeetR47(level,
                new BlockPos(Mth.floor(nodePosition.x),Mth.floor(nodePosition.y),Mth.floor(nodePosition.z)));
        return sole==null?super.getGroundY(nodePosition):sole.y;
    }

    private Vec3 realPathNodeR47(int index)
    {
        if(path==null||index<0||index>=path.getNodeCount())return null;
        Node node=path.getNode(index);
        return TrainingPilotDirector.nativeNodeFeetR47(level,new BlockPos(node.x,node.y,node.z));
    }

    private boolean nearPersonnelDoorR47(BlockPos pos)
    {
        for(int dx=-1;dx<=1;dx++)for(int dz=-1;dz<=1;dz++)for(int dy=-1;dy<=1;dy++)
            if(level.getBlockState(pos.offset(dx,dy,dz)).getBlock() instanceof CityPersonnelDoorR44)return true;
        return false;
    }

    private boolean precisionPortR47()
    {
        if(path==null||path.isDone())return false;
        int index=path.getNextNodeIndex();
        return nearPersonnelDoorR47(mob.blockPosition())||nearPersonnelDoorR47(path.getNextNodePos())
                ||index+1<path.getNodeCount()&&nearPersonnelDoorR47(path.getNodePos(index+1));
    }

    @Override public boolean canCutCorner(BlockPathTypes type)
    {
        if(precisionPortR47()||partialSurface(level,mob.blockPosition())
                ||path!=null&&!path.isDone()&&partialSurface(level,path.getNextNodePos()))return false;
        return super.canCutCorner(type);
    }

    @Override protected void followThePath()
    {
        if(!precisionPortR47()){super.followThePath();return;}
        int index=path.getNextNodeIndex();Vec3 centre=realPathNodeR47(index),actual=mob.position();
        // Vanilla tests nodeX/Z + width/2 (.3), while its movement target and
        // our planner use +.5. Use the same real centre/sole at finite doors.
        this.maxDistanceToWaypoint=mob.getBbWidth()>.75F?mob.getBbWidth()/2:.75F-mob.getBbWidth()/2;
        boolean arrived=centre!=null&&Math.abs(actual.x-centre.x)<maxDistanceToWaypoint
                &&Math.abs(actual.z-centre.z)<maxDistanceToWaypoint&&Math.abs(actual.y-centre.y)<=.08;
        Vec3 following=realPathNodeR47(index+1);
        // Retain the current centre until the actual off-centre actor has a
        // safe continuous body route to the following centre. This prevents
        // an early advance cutting the open leaf/rail at the MTR threshold.
        if(arrived&&clearStep(actual,centre)
                &&(index+1>=path.getNodeCount()||following!=null&&clearStep(actual,following)))path.advance();
        doStuckDetection(getTempMobPos());
    }

    @Override public void tick()
    {
        super.tick();
        if(!mob.onGround()||!precisionPortR47())return;
        int index=path.getNextNodeIndex();Vec3 target=realPathNodeR47(index),actual=mob.position();
        if(target!=null&&clearStep(actual,target))return;
        // A native path consists of safe centre edges; an MTR drift is not
        // necessarily on that edge. Walk back to its previous proven centre
        // when that actual segment is safe, rather than drive into a leaf.
        Vec3 previous=realPathNodeR47(index-1);
        if(previous!=null&&actual.distanceToSqr(previous)<=4
                &&Math.abs(actual.y-previous.y)<=mob.getStepHeight()+1.0E-7&&clearStep(actual,previous))
        {
            path.setNextNodeIndex(index-1);
            mob.getMoveControl().setWantedPosition(previous.x,previous.y,previous.z,speedModifier);
        }
        else
        {
            // Preserve the real path and existing bounded stall failure;
            // issue no unsafe movement, teleport, velocity reset or arrival.
            mob.getMoveControl().setWantedPosition(actual.x,actual.y,actual.z,speedModifier);
            mob.getPersistentData().putString("SeelePilotPortSweepHoldR47","feet="+actual+" next="+target);
        }
    }

    private boolean clearStep(Vec3 from,Vec3 to)
    {
        // Vanilla supplies legal neighbor elevations. A step rises before its
        // horizontal motion and descends afterwards, including fractional treads.
        Vec3 raised=to.y>=from.y?new Vec3(from.x,to.y,from.z):new Vec3(to.x,from.y,to.z);
        return clearSegment(from,raised)&&clearSegment(raised,to);
    }

    private boolean clearSegment(Vec3 from,Vec3 to)
    {
        double half=mob.getBbWidth()/2.0,height=mob.getBbHeight();
        AABB broad=new AABB(Math.min(from.x,to.x)-half,Math.min(from.y,to.y)+.001,
                Math.min(from.z,to.z)-half,Math.max(from.x,to.x)+half,
                Math.max(from.y,to.y)+height,Math.max(from.z,to.z)+half);
        if(level.containsAnyLiquid(broad))return false;
        for(var shape:level.getBlockCollisions(mob,broad))for(AABB box:shape.toAabbs())
        {
            // Exact Minkowski expansion of every native collision box; no
            // sampled gaps and no straight shortcut across a partial edge rail.
            AABB expanded=new AABB(box.minX-half+1.0E-7,box.minY-height+1.0E-7,
                    box.minZ-half+1.0E-7,box.maxX+half-1.0E-7,
                    box.maxY-.001-1.0E-7,box.maxZ+half-1.0E-7);
            if(intersectsSegment(expanded,from,to))return false;
        }
        return true;
    }

    private static boolean intersectsSegment(AABB box,Vec3 from,Vec3 to)
    {
        double enter=0,exit=1;
        double[] start={from.x,from.y,from.z},delta={to.x-from.x,to.y-from.y,to.z-from.z};
        double[] low={box.minX,box.minY,box.minZ},high={box.maxX,box.maxY,box.maxZ};
        for(int axis=0;axis<3;axis++)
        {
            if(Math.abs(delta[axis])<1.0E-12)
            {
                if(start[axis]<=low[axis]||start[axis]>=high[axis])return false;
            }
            else
            {
                double a=(low[axis]-start[axis])/delta[axis],b=(high[axis]-start[axis])/delta[axis];
                enter=Math.max(enter,Math.min(a,b));exit=Math.min(exit,Math.max(a,b));
                if(enter>=exit)return false;
            }
        }
        return true;
    }
}
