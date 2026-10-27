package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Real frozen skin contacts, rather than six arbitrary bone-pivot offsets.
 * Each closed 12-sided jaw has a source vertex edge on that skin point. */
public final class NervAirCradleContactsR52
{
    public record Contact(String bone,Vec3 skin,Vec3 centre,Vec3 axis){}
    private static final List<String> BONES=List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r");
    private record Candidate(Vec3 skin,Vec3 normal,double distance){}
    public static List<Contact> evaluate(EvaOriginalMeshGeometryR52.Geometry geometry,List<Vec3> desired)
    {
        var candidates=candidates(geometry,desired);
        var result=new ArrayList<Contact>();var floors=new HashMap<String,Double>();
        for(var part:geometry.parts())floors.merge(part.bone(),part.bounds().minY,Math::min);
        for(int pair=0;pair<3;pair++)
        {
            var left=candidates.get(pair*2);var right=candidates.get(pair*2+1);
            var selected=pair(pair,left.get(0),right.get(0));
            if(!aboveFloor(selected,floors,0))
            {
                // A prone limb's nearest skin point can put the real tilted
                // jaw below that limb. Search nearby actual skin triangles;
                // reserve the existing deployment sweep enclosure too. The
                // complete world sweep still decides whether it fits.
                double best=Double.POSITIVE_INFINITY;
                for(int a=0;a<Math.min(64,left.size());a++)
                    for(int b=0;b<Math.min(64,right.size());b++)
                    {
                        double cost=left.get(a).distance()+right.get(b).distance();if(cost>=best)continue;
                        var option=pair(pair,left.get(a),right.get(b));
                        if(aboveFloor(option,floors,NervAirframeGeometryR52.CRADLE_RADIAL_ENCLOSURE_R53)){selected=option;best=cost;}
                    }
            }
            if(selected.size()!=2)throw new IllegalStateException("Actual cradle side contacts coincide");
            result.addAll(selected);
        }
        return List.copyOf(result);
    }
    private static List<List<Candidate>> candidates(EvaOriginalMeshGeometryR52.Geometry geometry,List<Vec3> desired)
    {
        if(desired.size()!=6)throw new IllegalArgumentException("Six actual frozen body contact references required");
        var candidates=new ArrayList<List<Candidate>>();
        for(int i=0;i<6;i++)
        {
            var choices=new ArrayList<Candidate>();String bone=BONES.get(i);
            for(var part:geometry.parts())if(part.bone().equals(bone))
            {
                double[] xyz=part.triangles();
                for(int n=0;n<xyz.length;n+=9)
                {
                    var a=point(xyz,n);var b=point(xyz,n+3);var c=point(xyz,n+6);var q=b.subtract(a).cross(c.subtract(a));
                    if(q.lengthSqr()<1e-20)continue;
                    var at=closest(desired.get(i),a,b,c);var normal=q.normalize();
                    if(normal.dot(desired.get(i).subtract(at))<0)normal=normal.scale(-1);
                    choices.add(new Candidate(at,normal,at.distanceToSqr(desired.get(i))));
                }
            }
            if(choices.isEmpty())throw new IllegalStateException("Actual frozen contact surface absent: "+bone);
            choices.sort(Comparator.comparingDouble(Candidate::distance));candidates.add(choices);
        }
        return candidates;
    }
    private record PairOption(List<Contact> contacts,double cost){}
    private record Choice(int a,int b,int c,double cost){}
    /** Bounded alternatives for a fully retracted rig. The caller checks actual
     * obstacles using captured source geometry; this selector never reads a world. */
    public static List<Contact> evaluate(EvaOriginalMeshGeometryR52.Geometry geometry,List<Vec3> desired,
            java.util.function.Predicate<List<Contact>> accepted)
    {
        Objects.requireNonNull(accepted);
        var original=evaluate(geometry,desired);
        if(accepted.test(original))return original;
        var candidates=candidates(geometry,desired);var floors=new HashMap<String,Double>();
        // Export tessellation density must not consume the entire search on
        // one skin patch. Keep the nearest point, then cover the actual skin.
        for(int i=0;i<candidates.size();i++)
            candidates.set(i,diverse(candidates.get(i),(a,b)->a.skin().distanceToSqr(b.skin())));
        for(var part:geometry.parts())floors.merge(part.bone(),part.bounds().minY,Math::min);
        var options=new ArrayList<List<PairOption>>();
        for(int pair=0;pair<3;pair++)
        {
            var left=candidates.get(pair*2);var right=candidates.get(pair*2+1);
            var unique=new HashMap<List<Contact>,Double>();
            for(int a=0;a<Math.min(64,left.size());a++)
            {
                NervGeometryWorkR53.check();
                for(int b=0;b<Math.min(64,right.size());b++)
                {
                    var contacts=pair(pair,left.get(a),right.get(b));
                    if(aboveFloor(contacts,floors,0))
                        unique.merge(contacts,left.get(a).distance()+right.get(b).distance(),Math::min);
                }
            }
            // Stable ties follow the actual skin coordinates, not hash iteration.
            var ordered=new ArrayList<PairOption>();unique.forEach((contacts,cost)->ordered.add(new PairOption(contacts,cost)));
            Comparator<PairOption> byCost=Comparator.comparingDouble(PairOption::cost)
                    .thenComparing(o->o.contacts().toString());
            ordered.sort(byCost);
            if(ordered.isEmpty())return List.of();
            var spread=new ArrayList<>(diverse(ordered,(a,b)->
                    a.contacts().get(0).skin().distanceToSqr(b.contacts().get(0).skin())
                    +a.contacts().get(1).skin().distanceToSqr(b.contacts().get(1).skin())));
            // Best-first Cartesian enumeration requires each axis cost-sorted.
            spread.sort(byCost);options.add(List.copyOf(spread));
        }
        var queue=new PriorityQueue<Choice>(Comparator.comparingDouble(Choice::cost)
                .thenComparingInt(Choice::a).thenComparingInt(Choice::b).thenComparingInt(Choice::c));
        var seen=new HashSet<Integer>();enqueue(queue,seen,options,0,0,0);
        // Search combined changes: a greedy single-pair replacement would fail
        // when the original collar and spine are both obstructed.
        for(int tried=1;tried<256&&!queue.isEmpty();tried++)
        {
            NervGeometryWorkR53.check();var choice=queue.remove();var contacts=new ArrayList<Contact>(6);
            contacts.addAll(options.get(0).get(choice.a()).contacts());
            contacts.addAll(options.get(1).get(choice.b()).contacts());
            contacts.addAll(options.get(2).get(choice.c()).contacts());
            var frozen=List.copyOf(contacts);
            if(!frozen.equals(original)&&accepted.test(frozen))return frozen;
            enqueue(queue,seen,options,choice.a()+1,choice.b(),choice.c());
            enqueue(queue,seen,options,choice.a(),choice.b()+1,choice.c());
            enqueue(queue,seen,options,choice.a(),choice.b(),choice.c()+1);
        }
        return List.of();
    }
    private static <T> List<T> diverse(List<T> sorted,java.util.function.ToDoubleBiFunction<T,T> distance)
    {
        if(sorted.size()<=64)return sorted;
        var selected=new ArrayList<T>(64);boolean[] used=new boolean[sorted.size()];
        double[] nearest=new double[sorted.size()];Arrays.fill(nearest,Double.POSITIVE_INFINITY);
        int next=0;
        for(int count=0;count<64;count++)
        {
            NervGeometryWorkR53.check();T chosen=sorted.get(next);selected.add(chosen);used[next]=true;
            int farthest=-1;double greatest=-1;
            for(int i=0;i<sorted.size();i++)if(!used[i])
            {
                nearest[i]=Math.min(nearest[i],distance.applyAsDouble(sorted.get(i),chosen));
                if(nearest[i]>greatest){greatest=nearest[i];farthest=i;}
            }
            if(farthest<0)break;next=farthest;
        }
        return selected;
    }
    private static void enqueue(PriorityQueue<Choice> queue,Set<Integer> seen,List<List<PairOption>> options,int a,int b,int c)
    {
        if(a>=options.get(0).size()||b>=options.get(1).size()||c>=options.get(2).size())return;
        int key=(a*64+b)*64+c;if(!seen.add(key))return;
        queue.add(new Choice(a,b,c,options.get(0).get(a).cost()+options.get(1).get(b).cost()+options.get(2).get(c).cost()));
    }
    /** Validate persisted contacts against the selected original skin and the
     * actual jaw vertices. Obstacle clearance remains the caller's live proof. */
    public static boolean valid(EvaOriginalMeshGeometryR52.Geometry geometry,List<Contact> contacts)
    {
        if(contacts==null||contacts.size()!=6)return false;
        for(int pair=0;pair<3;pair++)
        {
            var left=contacts.get(pair*2);var right=contacts.get(pair*2+1);
            if(left==null||right==null||!finite(left.skin())||!finite(right.skin()))return false;
            var axis=right.skin().subtract(left.skin()).normalize();if(axis.lengthSqr()<.99)return false;
            var x=axis.cross(Math.abs(axis.y)<.95?new Vec3(0,1,0):new Vec3(1,0,0)).normalize();var y=axis.cross(x).normalize();
            for(int side=0;side<2;side++)
            {
                var contact=contacts.get(pair*2+side);
                if(!BONES.get(pair*2+side).equals(contact.bone())||!finite(contact.centre())||!finite(contact.axis())
                        ||contact.axis().distanceToSqr(axis)>1e-12)return false;
                boolean radial=false;
                for(int n=0;n<12;n++)
                {
                    var point=contact.skin().subtract(x.scale(Math.cos(n*Math.PI/6)).add(y.scale(Math.sin(n*Math.PI/6))).scale(.85));
                    if(contact.centre().distanceToSqr(point)<=1e-12){radial=true;break;}
                }
                if(!radial)return false;
                boolean skin=false;
                for(var part:geometry.parts())if(part.bone().equals(contact.bone()))
                {
                    double[] xyz=part.triangles();
                    for(int n=0;n<xyz.length;n+=9)
                    {
                        var a=point(xyz,n);var b=point(xyz,n+3);var c=point(xyz,n+6);
                        if(b.subtract(a).cross(c.subtract(a)).lengthSqr()<1e-20)continue;
                        if(closest(contact.skin(),a,b,c).distanceToSqr(contact.skin())<=1e-12){skin=true;break;}
                    }
                    if(skin)break;
                }
                if(!skin)return false;
            }
        }
        return true;
    }
    private static boolean finite(Vec3 v)
    {return v!=null&&Double.isFinite(v.x)&&Double.isFinite(v.y)&&Double.isFinite(v.z);}
    private static List<Contact> pair(int pair,Candidate left,Candidate right)
    {
        var axis=right.skin().subtract(left.skin()).normalize();
        if(axis.lengthSqr()<.99)return List.of();
        var x=axis.cross(Math.abs(axis.y)<.95?new Vec3(0,1,0):new Vec3(1,0,0)).normalize();var y=axis.cross(x).normalize();
        var result=new ArrayList<Contact>();
        for(int side=0;side<2;side++)
        {
            var candidate=side==0?left:right;Vec3 radial=null;double best=Double.NEGATIVE_INFINITY;
            for(int n=0;n<12;n++)
            {
                var r=x.scale(Math.cos(n*Math.PI/6)).add(y.scale(Math.sin(n*Math.PI/6)));
                double d=r.dot(candidate.normal().scale(-1));if(d>best){best=d;radial=r;}
            }
            result.add(new Contact(BONES.get(pair*2+side),candidate.skin(),candidate.skin().subtract(radial.scale(.85)),axis));
        }
        return List.copyOf(result);
    }
    private static boolean aboveFloor(List<Contact> pair,Map<String,Double> floors,double clearance)
    {
        if(pair.size()!=2)return false;
        for(var contact:pair)
        {
            var axis=contact.axis();var x=axis.cross(Math.abs(axis.y)<.95?new Vec3(0,1,0):new Vec3(1,0,0)).normalize();var y=axis.cross(x).normalize();
            for(int n=0;n<12;n++)
                if(contact.centre().y-Math.abs(axis.y)*1.6+.85*(x.y*Math.cos(n*Math.PI/6)+y.y*Math.sin(n*Math.PI/6))<floors.get(contact.bone())+clearance)return false;
        }
        return true;
    }

    private static Vec3 point(double[] a,int n){return new Vec3(a[n],a[n+1],a[n+2]);}
    public static Vec3 closest(Vec3 p,Vec3 a,Vec3 b,Vec3 c)
    {
        var ab=b.subtract(a);var ac=c.subtract(a);var ap=p.subtract(a);double d1=ab.dot(ap),d2=ac.dot(ap);if(d1<=0&&d2<=0)return a;
        var bp=p.subtract(b);double d3=ab.dot(bp),d4=ac.dot(bp);if(d3>=0&&d4<=d3)return b;
        double vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0)return a.add(ab.scale(d1/(d1-d3)));
        var cp=p.subtract(c);double d5=ab.dot(cp),d6=ac.dot(cp);if(d6>=0&&d5<=d6)return c;
        double vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0)return a.add(ac.scale(d2/(d2-d6)));
        double va=d3*d6-d5*d4;if(va<=0&&d4-d3>=0&&d5-d6>=0)return b.add(c.subtract(b).scale((d4-d3)/((d4-d3)+(d5-d6))));
        double denominator=1/(va+vb+vc);return a.add(ab.scale(vb*denominator)).add(ac.scale(vc*denominator));
    }
    private NervAirCradleContactsR52(){}
}
