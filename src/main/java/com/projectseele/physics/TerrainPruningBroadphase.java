package com.projectseele.physics;

import com.bulletphysics.collision.broadphase.BroadphasePair;
import com.bulletphysics.collision.broadphase.BroadphaseProxy;
import com.bulletphysics.collision.broadphase.Dbvt;
import com.bulletphysics.collision.broadphase.DbvtAabbMm;
import com.bulletphysics.collision.broadphase.DbvtBroadphase;
import com.bulletphysics.collision.broadphase.DbvtProxy;
import com.bulletphysics.collision.broadphase.DbvtTreeCollider;
import com.bulletphysics.collision.broadphase.Dispatcher;
import com.bulletphysics.collision.broadphase.HashedOverlappingPairCache;
import com.bulletphysics.util.ObjectArrayList;
import com.projectseele.ProjectSeele;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * JBullet's tree broadphase, finding the same pairs in the same order with far less walking.
 *
 * Terrain boxes are static, but JBullet refreshes every body's bounds on every substep, and that keeps them all in
 * the tree of moving bodies. The tree is then tested against itself, so thousands of touching terrain boxes are
 * paired with each other twelve times a tick, only for the group and mask filter to refuse each pair. This walk
 * leaves out a pair of subtrees when that filter would refuse every pair of bodies under them. The pairs that are
 * accepted, and the order they reach the pair cache in, are unchanged, so the solver gets the same input.
 *
 * Everything outside the self test repeats {@link DbvtBroadphase#collide} of jbullet 1.0.3 statement for statement.
 */
final class TerrainPruningBroadphase extends DbvtBroadphase
{
    private static final int UNTESTED=0,TRUSTED=1,REJECTED=2;
    /**
     * Collisions compared against the stock walk before this one works alone, and accepted pairs they must show.
     * A compared collision walks the tree twice more, so only one in {@link #COMPARED_EVERY} is compared: the first
     * knockdown of a session, when this is on trial, must not stutter more than it did before.
     */
    private static final int COMPARED_COLLISIONS=60,COMPARED_PAIRS=1000,COMPARED_EVERY=4;
    /** Unchanged terrain refreshes that must be seen to leave the tree alone before {@link #keepMoving} replaces them. */
    private static final int COMPARED_REFRESHES=10000;
    private static volatile int state=UNTESTED;
    private static final AtomicInteger compared=new AtomicInteger(),untested=new AtomicInteger();
    private static final AtomicLong comparedPairs=new AtomicLong(),comparedRefreshes=new AtomicLong();

    /** Whether the shortened walk has replaced the stock one. */
    static boolean trusted(){return state==TRUSTED;}
    /** Whether a settled terrain box may skip its bounds refresh, see {@link TerrainSteadyWorld}. */
    static boolean refreshTrusted(){return state==TRUSTED&&comparedRefreshes.get()>=COMPARED_REFRESHES;}
    static boolean rejected(){return state==REJECTED;}
    static void refreshMatched(){comparedRefreshes.incrementAndGet();}
    static void reject(String why)
    {
        if(state!=REJECTED){state=REJECTED;ProjectSeele.LOGGER.warn("Terrain broadphase shortcuts disabled: {}",why);}
    }

    /**
     * What {@code setAabb} does to a body of the moving tree whose bounds are the ones it already has and lie inside
     * its leaf: the tree stays as it is, and the body moves to the head of the current stage list, which is what
     * keeps it out of the fixed tree. False for a body of the fixed tree, which needs the full call.
     */
    boolean keepMoving(DbvtProxy proxy)
    {
        if(proxy.stage==STAGECOUNT)return false;
        stageRoots[proxy.stage]=unlink(proxy,stageRoots[proxy.stage]);
        proxy.stage=stageCurrent;
        stageRoots[stageCurrent]=link(proxy,stageRoots[stageCurrent]);
        return true;
    }

    // The moving tree in arrays for one collision: children by index (-1 at a leaf), and for each subtree every
    // group bit of its bodies in the low half and every mask bit in the high half.
    private Dbvt.Node[] nodes=new Dbvt.Node[256];
    private int[] first=new int[256],second=new int[256],filter=new int[256],work=new int[256],left=new int[256],right=new int[256];
    private int size;

    @Override public void collide(Dispatcher dispatcher)
    {
        if(state==REJECTED||!(paircache instanceof HashedOverlappingPairCache cache)||cache.getOverlapFilterCallback()!=null)
        {
            super.collide(dispatcher);return;
        }
        sets[0].optimizeIncremental(1+sets[0].leaves*dupdates/100);
        sets[1].optimizeIncremental(1+sets[1].leaves*fupdates/100);
        stageCurrent=(stageCurrent+1)%STAGECOUNT;
        DbvtProxy current=stageRoots[stageCurrent];
        if(current!=null)
        {
            DbvtTreeCollider collider=new DbvtTreeCollider(this);
            do
            {
                DbvtProxy next=current.links[1];
                stageRoots[current.stage]=unlink(current,stageRoots[current.stage]);
                stageRoots[STAGECOUNT]=link(current,stageRoots[STAGECOUNT]);
                Dbvt.collideTT(sets[1].root,current.leaf,collider);
                sets[0].remove(current.leaf);
                current.leaf=sets[1].insert(current.aabb,current);
                current.stage=STAGECOUNT;
                current=next;
            }
            while(current!=null);
        }
        DbvtTreeCollider collider=new DbvtTreeCollider(this);
        Dbvt.collideTT(sets[0].root,sets[1].root,collider);
        selfTest(cache,collider);
        ObjectArrayList<BroadphasePair> pairs=paircache.getOverlappingPairArray();
        if(pairs.size()>0)
        {
            for(int i=0,count=pairs.size();i<count;i++)
            {
                BroadphasePair pair=pairs.getQuick(i);
                DbvtProxy a=(DbvtProxy)pair.pProxy0,b=(DbvtProxy)pair.pProxy1;
                if(!DbvtAabbMm.Intersect(a.aabb,b.aabb))
                {
                    if(a.hashCode()>b.hashCode()){DbvtProxy swap=a;a=b;b=swap;}
                    paircache.removeOverlappingPair(a,b,dispatcher);
                    count--;i--;
                }
            }
        }
        pid++;
    }

    private void selfTest(HashedOverlappingPairCache cache,DbvtTreeCollider collider)
    {
        Dbvt.Node root=sets[0].root;
        if(root==null)return;
        if(state==TRUSTED){mirror(root);walk(collider);return;}
        // Until trusted the stock walk does the work, and now and then both walks are recorded and compared.
        if(untested.getAndIncrement()%COMPARED_EVERY!=0){Dbvt.collideTT(root,root,collider);return;}
        Recorder stock=new Recorder(cache),pruned=new Recorder(cache);
        Dbvt.collideTT(root,root,stock);
        mirror(root);walk(pruned);
        Dbvt.collideTT(root,root,collider);
        if(!stock.found.equals(pruned.found))
        {
            reject(pruned.found.size()/2+" accepted pairs against "+stock.found.size()/2+" from the stock walk");
            return;
        }
        long pairs=comparedPairs.addAndGet(stock.found.size()/2);
        if(compared.incrementAndGet()>=COMPARED_COLLISIONS&&pairs>=COMPARED_PAIRS&&state==UNTESTED)
        {
            state=TRUSTED;
            ProjectSeele.LOGGER.info("Terrain broadphase walk verified over {} collisions and {} accepted pairs",compared.get(),pairs);
        }
    }

    /** What a walk hands to the pair cache: the pairs whose bounds meet and which the filter accepts, in order. */
    private static final class Recorder extends Dbvt.ICollide
    {
        final HashedOverlappingPairCache cache;final ArrayList<DbvtProxy> found=new ArrayList<>();
        Recorder(HashedOverlappingPairCache cache){this.cache=cache;}
        @Override public void Process(Dbvt.Node a,Dbvt.Node b)
        {
            DbvtProxy pa=(DbvtProxy)a.data,pb=(DbvtProxy)b.data;
            if(DbvtAabbMm.Intersect(pa.aabb,pb.aabb)&&cache.needsBroadphaseCollision(pa,pb)){found.add(pa);found.add(pb);}
        }
    }

    private void mirror(Dbvt.Node root)
    {
        int count=1,top=0,before=size;
        nodes[0]=root;work[top++]=0;
        while(top>0)
        {
            int index=work[--top];Dbvt.Node node=nodes[index];
            if(node.isinternal())
            {
                if(count+2>nodes.length)
                {
                    int capacity=nodes.length*2;
                    nodes=Arrays.copyOf(nodes,capacity);first=Arrays.copyOf(first,capacity);second=Arrays.copyOf(second,capacity);filter=Arrays.copyOf(filter,capacity);
                }
                if(top+2>work.length)work=Arrays.copyOf(work,work.length*2);
                first[index]=count;second[index]=count+1;
                nodes[count]=node.childs[0];nodes[count+1]=node.childs[1];
                work[top++]=count;work[top++]=count+1;count+=2;
            }
            else
            {
                BroadphaseProxy proxy=(BroadphaseProxy)node.data;
                first[index]=-1;second[index]=-1;filter[index]=proxy.collisionFilterGroup&0xFFFF|(proxy.collisionFilterMask&0xFFFF)<<16;
            }
        }
        // Children are numbered after their parent, so going backwards meets them first.
        for(int index=count-1;index>=0;index--)if(first[index]>=0)filter[index]=filter[first[index]]|filter[second[index]];
        if(before>count)Arrays.fill(nodes,count,before,null);
        size=count;
    }

    /** {@code Dbvt.collideTT(root,root,policy)} entry for entry, without the pairs of subtrees the filter refuses whole. */
    private void walk(Dbvt.ICollide policy)
    {
        int top=1;
        left[0]=0;right[0]=0;
        do
        {
            int a=left[--top],b=right[top],fa=filter[a],fb=filter[b];
            // needsBroadphaseCollision wants (group of one & mask of the other) non-zero both ways.
            if((fa&0xFFFF&fb>>>16)==0||(fb&0xFFFF&fa>>>16)==0)continue;
            if(top+4>left.length){left=Arrays.copyOf(left,left.length*2);right=Arrays.copyOf(right,right.length*2);}
            if(a==b)
            {
                if(first[a]>=0)
                {
                    left[top]=first[a];right[top++]=first[a];
                    left[top]=second[a];right[top++]=second[a];
                    left[top]=first[a];right[top++]=second[a];
                }
            }
            else if(DbvtAabbMm.Intersect(nodes[a].volume,nodes[b].volume))
            {
                if(first[a]>=0)
                {
                    if(first[b]>=0)
                    {
                        left[top]=first[a];right[top++]=first[b];
                        left[top]=second[a];right[top++]=first[b];
                        left[top]=first[a];right[top++]=second[b];
                        left[top]=second[a];right[top++]=second[b];
                    }
                    else
                    {
                        left[top]=first[a];right[top++]=b;
                        left[top]=second[a];right[top++]=b;
                    }
                }
                else if(first[b]>=0)
                {
                    left[top]=a;right[top++]=first[b];
                    left[top]=a;right[top++]=second[b];
                }
                else policy.Process(nodes[a],nodes[b]);
            }
        }
        while(top>0);
    }

    private static DbvtProxy link(DbvtProxy item,DbvtProxy list)
    {
        item.links[0]=null;item.links[1]=list;
        if(list!=null)list.links[0]=item;
        return item;
    }

    private static DbvtProxy unlink(DbvtProxy item,DbvtProxy list)
    {
        if(item.links[0]!=null)item.links[0].links[1]=item.links[1];else list=item.links[1];
        if(item.links[1]!=null)item.links[1].links[0]=item.links[0];
        return list;
    }
}
