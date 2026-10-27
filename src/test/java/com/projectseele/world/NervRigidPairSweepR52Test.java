package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

public final class NervRigidPairSweepR52Test
{
    private static int checks;
    private static void check(boolean b,String text){checks++;if(!b)throw new AssertionError(text);}
    private static void boundedWorkingSetReuse()throws Exception
    {
        var source=new double[4096*9];
        for(int i=0;i<4096;i++){double x=i*.01;double[] triangle={x,0,0,x+.004,0,0,x,1,0};System.arraycopy(triangle,0,source,i*9,9);}
        var mesh=new NervRigidMeshSweepR52(source);var frame=RigidTransform.identity();var query=new NervRigidMeshSweepR52.PairQuery();
        var motion=NervRigidMeshSweepR52.PairQuery.class.getDeclaredMethod("motion",NervRigidMeshSweepR52.class,RigidTransform.class,RigidTransform.class,Vec3.class);motion.setAccessible(true);
        var cached=motion.invoke(query,mesh,frame,frame,Vec3.ZERO);var chord=cached.getClass().getDeclaredMethod("chord",int.class,int.class,int.class);chord.setAccessible(true);
        for(int i=0;i<2048;i++)chord.invoke(cached,i,1,0);
        var late=chord.invoke(cached,3000,1,0);
        check(late==chord.invoke(cached,3000,1,0),"A full bounded chord cache must still reuse the newly reached source page");
        var root=NervRigidMeshSweepR52.class.getDeclaredField("root");root.setAccessible(true);Object node=root.get(mesh);
        var left=node.getClass().getDeclaredField("left");var right=node.getClass().getDeclaredField("right");left.setAccessible(true);right.setAccessible(true);
        var hull=cached.getClass().getDeclaredMethod("leafHull",node.getClass());hull.setAccessible(true);var queue=new ArrayDeque<Object>();queue.add(node);Object lastLeaf=null;int leaves=0;
        while(!queue.isEmpty()){node=queue.removeFirst();if(left.get(node)!=null){queue.add(left.get(node));queue.add(right.get(node));}else{hull.invoke(cached,node);lastLeaf=node;leaves++;}}
        check(leaves>256,"Fixture must move beyond the original frozen leaf cache");
        check(hull.invoke(cached,lastLeaf)==hull.invoke(cached,lastLeaf),"Newly reached actual leaf projections remain reusable after capacity");
        var count=cached.getClass().getDeclaredField("cachedChords");count.setAccessible(true);
        var pages=cached.getClass().getDeclaredField("boundedChords");pages.setAccessible(true);
        check(count.getInt(cached)<=2048&&((Map<?,?>)pages.get(cached)).size()<=16,"Eviction must retain the original geometry memory bounds");
        for(int i=0;i<18;i++)motion.invoke(query,new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0}),frame,frame,Vec3.ZERO);
        check(cached==motion.invoke(query,mesh,frame,frame,Vec3.ZERO),"One full actor's 18 groups cannot evict every preceding fixed source projection");
    }
    private static boolean exhaustiveSeparated(Vec3[] a,Vec3[] b,Vec3 error,Vec3 axis)
    {
        if(axis.lengthSqr()<1e-28)return false;
        double al=Double.POSITIVE_INFINITY,ah=Double.NEGATIVE_INFINITY,bl=al,bh=ah;
        for(var p:a){double v=p.dot(axis);al=Math.min(al,v);ah=Math.max(ah,v);}
        for(var p:b){double v=p.dot(axis);bl=Math.min(bl,v);bh=Math.max(bh,v);}
        double pad=error.x*Math.abs(axis.x)+error.y*Math.abs(axis.y)+error.z*Math.abs(axis.z);
        return ah+pad<=bl||al-pad>=bh;
    }
    private static boolean exhaustivePair(Vec3[] a,Vec3[] b,Vec3 error)
    {
        for(var axis:new Vec3[]{new Vec3(1,0,0),new Vec3(0,1,0),new Vec3(0,0,1)})if(exhaustiveSeparated(a,b,error,axis))return false;
        for(var hull:new Vec3[][]{a,b})for(int i=0;i<6;i++)for(int j=i+1;j<6;j++)for(int k=j+1;k<6;k++)if(exhaustiveSeparated(a,b,error,hull[j].subtract(hull[i]).cross(hull[k].subtract(hull[i]))))return false;
        for(int i=0;i<6;i++)for(int j=i+1;j<6;j++)for(int k=0;k<6;k++)for(int m=k+1;m<6;m++)if(exhaustiveSeparated(a,b,error,a[j].subtract(a[i]).cross(b[m].subtract(b[k]))))return false;
        return true;
    }
    private static void stationaryEndpointAxes()
    {
        var random=new Random(530026);int hit=0,clear=0;
        for(int trial=0;trial<5000;trial++)
        {
            var a=new Vec3[6];var b=new Vec3[6];
            for(int i=0;i<3;i++)
            {
                a[i]=new Vec3(random.nextDouble()*2,random.nextDouble()*2,random.nextDouble()*2);
                b[i]=new Vec3(random.nextDouble()*2,random.nextDouble()*2,random.nextDouble()*2);
                a[i+3]=trial%3==0?a[i]:a[i].add(.1,-.2,.3);
                b[i+3]=b[i];
            }
            if(trial%4==0)for(int i=0;i<6;i++)b[i]=new Vec3(b[i].x,b[i].y,trial%8==0?0:2);
            if(trial%4==0)for(int i=0;i<6;i++)a[i]=new Vec3(a[i].x,a[i].y,0);
            var pad=trial%5==0?Vec3.ZERO:new Vec3(.00002,.00001,.00003);
            boolean expected=exhaustivePair(a,b,pad);
            check(TriangleSweepMeshR52.convexSweepPair(a,b,pad)==expected,"Stationary duplicate removal must preserve all original axes, including coplanar and padded contact");
            check(TriangleSweepMeshR52.convexSweepPair(b,a,pad)==exhaustivePair(b,a,pad),"Either side can be the stationary source");
            if(expected)hit++;else clear++;
        }
        check(hit>0&&clear>0,"Endpoint-axis regression requires both outcomes");
    }
    private static void transformedBounds()
    {
        var random=new Random(530024);
        for(int i=0;i<1200;i++)
        {
            var a=new Vec3(random.nextDouble()*500-250,random.nextDouble()*500-250,random.nextDouble()*500-250);
            var b=new AABB(a,a.add(random.nextDouble()*100,random.nextDouble()*100,random.nextDouble()*100));
            var frame=RigidTransform.of(new Vec3(72.5,-1062,301.5),new Quaternionf().rotationXYZ(random.nextFloat()*6,random.nextFloat()*6,random.nextFloat()*6));
            AABB expected=null;
            for(double x:new double[]{b.minX,b.maxX})for(double y:new double[]{b.minY,b.maxY})for(double z:new double[]{b.minZ,b.maxZ})
            {
                var p=frame.transformPoint(new Vec3(x,y,z));expected=expected==null?new AABB(p,p):expected.minmax(new AABB(p,p));
            }
            check(NervRigidMeshSweepR52.transformed(b,frame).equals(expected),"Transformed bounds must match all original source corners exactly");
        }
    }
    private static void leafCacheInputs()
    {
        var random=new Random(530030);var source=new double[90*9];
        for(int i=0;i<source.length;i++)source[i]=random.nextDouble()*20-10;
        var cached=new NervRigidMeshSweepR52(source);
        for(int i=0;i<60;i++)
        {
            var from=RigidTransform.of(new Vec3(i%3,-1062,i%7),new Quaternionf().rotationXYZ(i*.01F,0,0));
            var to=RigidTransform.of(from.translation().add(0,.01,0),new Quaternionf().rotationY(i*.02F));
            var fresh=new NervRigidMeshSweepR52(source).leafEnvelopes(from,to);
            var result=cached.leafEnvelopes(from,to);
            check(result.equals(fresh),"Changed start, end and rotation must retain exact freshly computed leaf bounds");
            check(cached.leafEnvelopes(from,to)==result,"Identical immutable source frames reuse the established bounds");
            cached.leafEnvelopes(to,from);
            check(cached.leafEnvelopes(from,to).equals(fresh),"Interleaved reverse queries cannot poison the original motion envelope");
        }
    }
    private static void separatedSourceMembers()
    {
        var source=new double[700*9];
        for(int i=0;i<700;i++)
        {
            double x=i*.3;double[] triangle={x,0,0,x+.1,0,0,x,100,0};
            System.arraycopy(triangle,0,source,i*9,9);
        }
        var mesh=new NervRigidMeshSweepR52(source);var first=RigidTransform.identity();
        var last=new RigidTransform(new Vec3(0,0,2),0,0,0,1);
        for(int index:new int[]{0,127,255,256,511,512,699})
        {
            double x=index*.3;
            var hit=new NervRigidMeshSweepR52(new double[]{x+.01,1,1,x+.02,1,1,x+.01,2,1});
            var gap=new NervRigidMeshSweepR52(new double[]{x+.15,1,1,x+.16,1,1,x+.15,2,1});
            check(mesh.intersects(first,last,hit,first,first,.003,Vec3.ZERO),"Every original long member must remain in the BVH across cache page boundaries");
            check(!mesh.intersects(first,last,gap,first,first,.003,Vec3.ZERO),"Empty space between long source members must remain empty");
            check(!mesh.intersects(first,first,hit,first,first,.003,Vec3.ZERO)&&!mesh.intersects(last,last,hit,first,first,.003,Vec3.ZERO),"An obstruction between endpoint poses cannot be dropped by spatial partitioning");
        }
    }
    private static void sparseAndRotatingSweeps()
    {
        var random=new Random(530025);
        int hit=0,clear=0;
        for(int trial=0;trial<160;trial++)
        {
            double[] a={0,0,0,2,0,0,0,2,0},b={0,0,0,1,0,0,0,1,0};
            var am=new NervRigidMeshSweepR52(a);var bm=new NervRigidMeshSweepR52(b);
            var af=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationXYZ(.1F,.2F,.3F));
            var at=RigidTransform.of(new Vec3(.2,0,.4),new Quaternionf().rotationXYZ(.2F,.3F,.5F));
            var bf=RigidTransform.of(new Vec3(random.nextDouble()*3-.5,random.nextDouble()*3-.5,random.nextDouble()-.5),new Quaternionf().rotationXYZ(.3F,.1F,0));
            var bt=RigidTransform.of(bf.translation().add(-.1,.1,-.2),new Quaternionf().rotationXYZ(.4F,.1F,.1F));
            double ar=NervRigidMeshSweepR52.radius(am.bounds()),br=NervRigidMeshSweepR52.radius(bm.bounds());
            double aa=NervRigidMeshSweepR52.angular(af,at),ba=NervRigidMeshSweepR52.angular(bf,bt);
            int n=Math.max(NervRigidMeshSweepR52.divisions(ar,aa,.003),NervRigidMeshSweepR52.divisions(br,ba,.003));
            double ae=NervRigidMeshSweepR52.error(ar,aa,n),be=NervRigidMeshSweepR52.error(br,ba,n);
            var extra=new Vec3(.00002,.00001,.00003);var pad=extra.add(ae+be,ae+be,ae+be);boolean brute=false;
            for(int s=0;s<n&&!brute;s++)
            {
                var ac=new Vec3[6];var bc=new Vec3[6];
                for(int c=0;c<3;c++)
                {
                    var ap=new Vec3(a[c*3],a[c*3+1],a[c*3+2]);var bp=new Vec3(b[c*3],b[c*3+1],b[c*3+2]);
                    ac[c]=af.interpolate(at,(double)s/n).transformPoint(ap);ac[c+3]=af.interpolate(at,(double)(s+1)/n).transformPoint(ap);
                    bc[c]=bf.interpolate(bt,(double)s/n).transformPoint(bp);bc[c+3]=bf.interpolate(bt,(double)(s+1)/n).transformPoint(bp);
                    // Independent point-level reference in the same moving
                    // frame; world swept hulls also admit different times.
                    var shift0=bf.translation().lerp(bt.translation(),(double)s/n);
                    var shift1=bf.translation().lerp(bt.translation(),(double)(s+1)/n);
                    ac[c]=ac[c].subtract(shift0);bc[c]=bc[c].subtract(shift0);
                    ac[c+3]=ac[c+3].subtract(shift1);bc[c+3]=bc[c+3].subtract(shift1);
                }
                brute=TriangleSweepMeshR52.convexSweepPair(ac,bc,pad);
            }
            check(am.intersects(af,at,bm,bf,bt,.003,extra)==brute,"Cached chord bounds must preserve same-time rotating triangle SAT with certified padding");
            if(brute)hit++;else clear++;
        }
        check(hit>0&&clear>0,"Rotating triangle comparison must exercise separated and intersecting surfaces");
    }
    private static void compoundTranslationSweeps()
    {
        var random=new Random(530015);
        int blocked=0,clear=0;
        for(int trial=0;trial<80;trial++)
        {
            double[] a=new double[25*9],b=new double[29*9];
            for(int i=0;i<a.length;i++)a[i]=random.nextDouble()*2-1;
            for(int i=0;i<b.length;i++)b[i]=random.nextDouble()*2-1;
            var af=RigidTransform.identity();var at=new RigidTransform(new Vec3(.2,.1,-.3),0,0,0,1);
            var bf=new RigidTransform(new Vec3(trial%3==0?4:random.nextDouble(),0,0),0,0,0,1);
            var bt=new RigidTransform(bf.translation().add(-.1,.2,.3),0,0,0,1);
            var padding=new Vec3(.00002,.00001,.00002);boolean brute=false;
            for(int i=0;i<a.length&&!brute;i+=9)for(int j=0;j<b.length&&!brute;j+=9)
            {
                var ac=new Vec3[6];var bc=new Vec3[6];
                for(int c=0;c<3;c++)
                {
                    var ap=new Vec3(a[i+c*3],a[i+c*3+1],a[i+c*3+2]);var bp=new Vec3(b[j+c*3],b[j+c*3+1],b[j+c*3+2]);
                    ac[c]=af.transformPoint(ap);ac[c+3]=at.transformPoint(ap).subtract(bt.translation().subtract(bf.translation()));
                    bc[c]=bf.transformPoint(bp);bc[c+3]=bc[c];
                }
                brute=TriangleSweepMeshR52.convexSweepPair(ac,bc,padding);
            }
            boolean actual=new NervRigidMeshSweepR52(a).intersects(af,at,new NervRigidMeshSweepR52(b),bf,bt,.003,padding);
            check(actual==brute,"Compound BVH motion must match every simultaneous relative triangle pair, including repeated nodes");
            if(actual)blocked++;else clear++;
        }
        check(blocked>0&&clear>0,"Compound translation comparison requires both collision outcomes");
    }
    private static void simultaneousTranslations()
    {
        var mesh=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});
        var a=RigidTransform.identity();var b=new RigidTransform(new Vec3(0,0,.01),0,0,0,1);var pad=new Vec3(.000001,.000001,.000001);
        for(int i=1;i<=200;i++)
        {
            var movement=new Vec3(i*.01,-i*.007,i*.1);var endA=new RigidTransform(movement,0,0,0,1);var endB=new RigidTransform(b.translation().add(movement),0,0,0,1);
            check(!mesh.intersects(a,endA,mesh,b,endB,.003,pad),"Parallel moving faces separated by one centimetre never collide, even when their swept volumes overlap");
            check(!mesh.intersects(b,endB,mesh,a,endA,.003,pad),"Simultaneous separation is independent of which moving member is queried first");
            var crossing=new RigidTransform(endB.translation().add(0,0,-.02),0,0,0,1);
            check(mesh.intersects(a,endA,mesh,b,crossing,.003,pad),"A peer that crosses through the moving face must still collide");
        }
    }
    private static void farSourceTranslations()
    {
        var moving=new NervRigidMeshSweepR52(new double[]{1000,-1062,328,1002,-1062,328,1000,-1060,328});
        var fixed=new NervRigidMeshSweepR52(new double[]{1000,-1062,329,1002,-1062,329,1000,-1060,329});
        var id=RigidTransform.identity();var end=new RigidTransform(new Vec3(0,0,2),0,0,0,1);
        double radius=NervRigidMeshSweepR52.radius(moving.bounds());
        check(radius>375&&NervRigidMeshSweepR52.divisions(radius,0,.003)==1,"Far source coordinates cannot invent angular error in static or affine motion");
        check(!moving.intersects(id,id,fixed,id,id,.003,Vec3.ZERO),"Separated far-coordinate static steel must remain clear");
        check(moving.intersects(id,end,fixed,id,id,.003,Vec3.ZERO),"Pure translation must retain the actual crossing between separated endpoint poses");
        boolean rotatedRejected=false;try{NervRigidMeshSweepR52.divisions(radius,.001,.003);}catch(IllegalArgumentException expected){rotatedRejected=true;}
        check(rotatedRejected,"Nonzero rotation must retain the original radius-based precision threshold");
        for(double[] values:new double[][]{{Double.NaN,0,.003},{radius,Double.NaN,.003},{radius,0,0},{radius,0,Double.POSITIVE_INFINITY}})
        {
            boolean rejected=false;try{NervRigidMeshSweepR52.divisions(values[0],values[1],values[2]);}catch(IllegalArgumentException expected){rejected=true;}
            check(rejected,"Zero-angle shortcut must not admit invalid inputs or nonpositive budgets");
        }
    }
    private static void inclinedLeafSeparation()
    {
        // Two source facets per leaf, inclined almost parallel steel with
        // overlapping world boxes, at both local and actual hangar heights.
        double[] source={-1,-1,0,1,-1,0,1,1,0,-1,-1,0,1,1,0,-1,1,0};
        var mesh=new NervRigidMeshSweepR52(source);var rotation=new Quaternionf().rotationX(.6F);
        var pad=new Vec3(.00004,.00004,.00004);var query=new NervRigidMeshSweepR52.PairQuery();
        for(double y:new double[]{0,-1062})for(double gap:new double[]{.00001,.0002,.02})for(boolean crossing:new boolean[]{false,true})
        {
            var from=RigidTransform.of(new Vec3(30.5,y,328.5),rotation);
            var normal=from.transformVector(new Vec3(0,0,1));
            var to=RigidTransform.of(from.translation().add(.1,0,0).add(normal.scale(crossing?gap*2:0)),rotation);
            var fixed=RigidTransform.of(from.translation().add(normal.scale(gap)),rotation);boolean expected=false;
            for(int a=0;a<2&&!expected;a++)for(int b=0;b<2&&!expected;b++)
            {
                var ac=new Vec3[6];var bc=new Vec3[6];
                for(int c=0;c<3;c++)
                {
                    int i=a*9+c*3,j=b*9+c*3;var p=new Vec3(source[i],source[i+1],source[i+2]);var q=new Vec3(source[j],source[j+1],source[j+2]);
                    ac[c]=from.interpolate(to,0).transformPoint(p);ac[c+3]=from.interpolate(to,1).transformPoint(p);
                    bc[c]=fixed.interpolate(fixed,0).transformPoint(q);bc[c+3]=bc[c];
                }
                expected=exhaustivePair(ac,bc,pad);
            }
            query.nextInterval();
            check(mesh.intersects(from,to,mesh,fixed,fixed,.003,pad,query)==expected,"Inclined leaf rejection must retain padded contact and crossings at the original hangar root");
        }
    }
    private static void affineStaticReuse()throws Exception
    {
        var moving=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});
        var stationary=new NervRigidMeshSweepR52(new double[]{5,.1,-1,5,.1,1,5,.9,0});
        var id=RigidTransform.identity();var end=new RigidTransform(new Vec3(10,0,0),0,0,0,1);
        var high=new RigidTransform(new Vec3(0,0,5),0,0,0,1);var highEnd=new RigidTransform(new Vec3(10,0,5),0,0,0,1);
        var role=NervOriginalCarrierR52.Role.STRUCTURE;
        var first=List.of(new NervOriginalCarrierR52.Part("same_name",role,moving,id),new NervOriginalCarrierR52.Part("same_name",role,moving,high));
        var last=List.of(new NervOriginalCarrierR52.Part("same_name",role,moving,end),new NervOriginalCarrierR52.Part("same_name",role,moving,highEnd));
        var type=Class.forName("com.projectseele.world.NervOriginalCarrierR52$AffineStaticChecksR53");
        var constructor=type.getDeclaredConstructor(List.class,List.class);constructor.setAccessible(true);var proof=constructor.newInstance(first,last);
        var method=type.getDeclaredMethod("hits",NervOriginalCarrierR52.Part.class,NervOriginalCarrierR52.Part.class,int.class,NervFlightProofR52.ObstacleMesh.class,double.class);method.setAccessible(true);
        var obstacle=new NervFlightProofR52.ObstacleMesh(stationary,id);
        check(!(Boolean)method.invoke(proof,first.get(1),last.get(1),1,obstacle,.00002),"Complete translated assembly clears a separated surface");
        check(!(Boolean)method.invoke(proof,first.get(1),last.get(1),1,new NervFlightProofR52.ObstacleMesh(stationary,id),.00002),"Equivalent current static surface can reuse its whole-interval proof");
        var early=new NervOriginalCarrierR52.Part("same_name",role,moving,id.interpolate(end,.1));
        check((Boolean)method.invoke(proof,first.get(0),early,0,obstacle,.00002),"A different member with the same name must detect a later collision in the complete translation");
        check((Boolean)method.invoke(proof,first.get(1),last.get(1),1,new NervFlightProofR52.ObstacleMesh(stationary,high),.00002),"Changing the obstacle frame invalidates a previous clearance");
    }
    private static void indexedSweeps()
    {
        var random=new Random(53);
        var mesh=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});
        var obstacles=new ArrayList<NervFlightProofR52.ObstacleMesh>();
        for(int i=0;i<24;i++)
        {
            var first=RigidTransform.of(new Vec3(random.nextDouble()*4-2,random.nextDouble()*4-2,random.nextDouble()-.5),new Quaternionf().rotationXYZ(.1F,.2F,.3F));
            var last=RigidTransform.of(first.translation().add(.05,0,-.08),new Quaternionf().rotationXYZ(.12F,.18F,.32F));
            obstacles.add(new NervFlightProofR52.ObstacleMesh(mesh,first,last));
        }
        var index=new NervStaticSpatialIndexR52<>(obstacles,m->m.mesh().envelope(m.frame(),m.endFrame()));
        int collisions=0,clear=0;
        for(int i=0;i<60;i++)
        {
            var from=RigidTransform.of(new Vec3(random.nextDouble()*4-2,random.nextDouble()*4-2,random.nextDouble()-.5),new Quaternionf().rotationY(.15F));
            var to=RigidTransform.of(from.translation().add(.25,-.08,.15),new Quaternionf().rotationXYZ(.01F,.18F,0));
            double error=i%2==0?.00002:.01;var allowance=new Vec3(error,error,error);
            var expected=obstacles.stream().filter(m->mesh.intersects(from,to,m.mesh(),m.frame(),m.endFrame(),.003,allowance)).toList();
            var actual=index.query(mesh.envelope(from,to).inflate(error)).stream().filter(m->mesh.intersects(from,to,m.mesh(),m.frame(),m.endFrame(),.003,allowance)).toList();
            check(actual.equals(expected),"Indexed moving meshes must retain every exact collision and source order");
            if(expected.isEmpty())clear++;else collisions++;
        }
        check(collisions>0&&clear>0,"Indexed comparison must exercise both blocked and clear physical sweeps");
    }
    private static void rotatingCommonTranslation()
    {
        var a=new NervRigidMeshSweepR52(new double[]{0,0,0,2,0,0,0,2,0});
        var b=new NervRigidMeshSweepR52(new double[]{0,.2,-1,0,.2,1,0,1.8,0});
        var a0=RigidTransform.identity();
        var a1=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationY(.15F));
        var b0=RigidTransform.of(new Vec3(4,0,0),new Quaternionf());
        var b1=RigidTransform.of(new Vec3(4,0,0),new Quaternionf().rotationZ(-.1F));
        var crossing=RigidTransform.of(new Vec3(-1,0,0),new Quaternionf().rotationZ(-.1F));
        check(!a.intersects(a0,a1,b,b0,b1,.005,Vec3.ZERO),"Rotating separated members stay clear in their common moving frame");
        check(a.intersects(a0,a1,b,b0,crossing,.005,Vec3.ZERO),"A real relative crossing is retained while both members rotate");
        var query=new NervRigidMeshSweepR52.PairQuery();
        for(var origin:List.of(new Vec3(72,-930,28),new Vec3(-1200,175,-1500)))
            for(var travel:List.of(new Vec3(32,7,-25),new Vec3(0,84,0)))
            {
                var A0=offset(a0,origin);var A1=offset(a1,origin.add(travel));
                var B0=offset(b0,origin);var B1=offset(b1,origin.add(travel));
                var C1=offset(crossing,origin.add(travel));
                check(!a.intersects(A0,A1,b,B0,B1,.005,Vec3.ZERO,query),"Common carrier travel cannot create an asynchronous rotation collision");
                check(a.intersects(A0,A1,b,B0,C1,.005,Vec3.ZERO,query),"Common carrier travel cannot hide a real rotating contact");
                query.nextInterval();
            }
    }
    private static RigidTransform offset(RigidTransform frame,Vec3 displacement)
    {return new RigidTransform(frame.translation().add(displacement),frame.qx(),frame.qy(),frame.qz(),frame.qw());}
    public static void main(String[] args)throws Exception
    {
        var a=new NervRigidMeshSweepR52(new double[]{0,0,0,10,0,0,0,10,0});var b=new NervRigidMeshSweepR52(new double[]{9,9,-1,9.1,9,1,9,9.1,1});var id=RigidTransform.identity();
        check(a.bounds().intersects(b.bounds()),"Empty triangle corner is inside both broad BVH boxes");check(!a.intersects(id,id,b,id,id,.005,Vec3.ZERO),"Actual paired triangle SAT permits that empty corner");
        a=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});b=new NervRigidMeshSweepR52(new double[]{5,.1,-1,5,.1,1,5,.9,0});var end=new RigidTransform(new Vec3(10,0,0),0,0,0,1);
        check(!a.intersects(id,id,b,id,id,.005,Vec3.ZERO)&&!a.intersects(end,end,b,id,id,.005,Vec3.ZERO),"Both actual stopped mesh pairs are separated");check(a.intersects(id,end,b,id,id,.005,Vec3.ZERO),"Same-time continuous real triangle chord detects the collision between stopped endpoints");
        Vec3[] stopped={new Vec3(5,.1,-1),new Vec3(5,.1,1),new Vec3(5,.9,0),new Vec3(5,.1,-1),new Vec3(5,.1,1),new Vec3(5,.9,0)};check(!a.intersectsChord(stopped,Vec3.ZERO,id)&&!a.intersectsChord(stopped,Vec3.ZERO,end),"A moving external source mesh is clear at both endpoint samples");check(a.intersectsChord(stopped,Vec3.ZERO,id,end),"Moving external source cannot disappear between two clear endpoint samples");
        indexedSweeps();
        transformedBounds();
        leafCacheInputs();
        sparseAndRotatingSweeps();
        compoundTranslationSweeps();
        simultaneousTranslations();
        farSourceTranslations();
        inclinedLeafSeparation();
        stationaryEndpointAxes();
        separatedSourceMembers();
        affineStaticReuse();
        boundedWorkingSetReuse();
        rotatingCommonTranslation();
        System.out.println("PASS R52 paired actual triangle BVH/chord checks: "+checks);
    }
}
