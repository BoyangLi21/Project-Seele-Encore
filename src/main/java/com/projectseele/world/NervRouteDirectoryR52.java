package com.projectseele.world;

import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Root-authored immutable routes. No world access, default coordinates or installation hook. */
public final class NervRouteDirectoryR52
{
    public static final String SCHEMA="projectseele.r52.route-directory.v1";
    public static final String EXPLICIT_BANK_SCHEMA="projectseele.r52.route-directory.v2";
    public record BankRole(int bank,String intent)
    {
        public BankRole{require(bank>=1&&bank<=3&&Set.of("geofront","surface","hakone").contains(intent),"Explicit bank1..3 and known departure intent required");}
        public Region region(){return intent.equals("geofront")?Region.GEOFRONT:Region.SURFACE;}
        public List<Motion> legacyLaunchSequence(){return intent.equals("geofront")?List.of(Motion.VERTICAL):List.of(Motion.VERTICAL,Motion.LAUNCH_INCLINE,Motion.VERTICAL);}
    }
    public enum Region { SURFACE,GEOFRONT }
    public enum Role { BAY,BANK,PATH,EXIT }
    public enum ResourceKind { RAIL,DOOR,SUPPORT,SPACE }
    public enum Motion { ORIGINAL_UPRIGHT_TRANSFER,TRACKED_BANK_TRANSFER,VERTICAL,FOOT_BEARING_TURN,LAUNCH_INCLINE }
    public record Unit(int variant,int lane,UUID eva,UUID plug)
    {public Unit{checkVariant(variant);require(lane>=0&&lane<=2,"Explicit physical lane0..2 binding required");Objects.requireNonNull(eva);Objects.requireNonNull(plug);require(!eva.equals(plug),"EVA and plug identities must differ");}}
    public record Rotation(float x,float y,float z,float w)
    {
        public Rotation{double n=(double)x*x+(double)y*y+(double)z*z+(double)w*w;require(Double.isFinite(n)&&Math.abs(n-1)<1e-5,"Measured unit quaternion required");}
        public Quaternionf quaternion(){return new Quaternionf(x,y,z,w);}
    }
    public record Node(String id,String dimension,Role role,int bank,int lane,int variant,RigidTransform footFrame)
    {
        public Node
        {
            id=identifier(id);dimension=identifier(dimension);Objects.requireNonNull(role);finite(footFrame.translation());
            if(role==Role.BANK){require(bank>=1&&bank<=3&&lane>=0&&lane<=2,"Explicit bank/lane required");}
            if(role==Role.BAY)checkVariant(variant);
        }
    }
    public record Resource(String id,ResourceKind kind,String component)
    {public Resource{id=identifier(id);Objects.requireNonNull(kind);component=identifier(component);}}
    public record Leg(String id,String from,String to,Motion motion,int ticks,Rotation evaFrom,Rotation evaTo,
                      List<String> rails,List<String> doors,String support,Set<String> occupancy,NervRampProfileR52 rampProfile,NervCentrelineCurveR52 centreCurve)
    {
        public Leg(String id,String from,String to,Motion motion,int ticks,Rotation evaFrom,Rotation evaTo,List<String> rails,List<String> doors,String support,Set<String> occupancy)
        {this(id,from,to,motion,ticks,evaFrom,evaTo,rails,doors,support,occupancy,null,null);}
        public Leg(String id,String from,String to,Motion motion,int ticks,Rotation evaFrom,Rotation evaTo,List<String> rails,List<String> doors,String support,Set<String> occupancy,NervRampProfileR52 rampProfile)
        {this(id,from,to,motion,ticks,evaFrom,evaTo,rails,doors,support,occupancy,rampProfile,null);}
        public Leg
        {
            id=identifier(id);from=identifier(from);to=identifier(to);Objects.requireNonNull(motion);require(ticks>0,"Explicit positive travel duration required");
            Objects.requireNonNull(evaFrom);Objects.requireNonNull(evaTo);rails=List.copyOf(rails);doors=List.copyOf(doors);support=identifier(support);occupancy=Set.copyOf(occupancy);
            require(!rails.isEmpty()&&!occupancy.isEmpty(),"Real track and occupied-space declarations required");
            require(rampProfile==null||centreCurve==null,"Original ramp and explicit centre curve cannot overwrite one another");
        }
        public Set<String> resources(){var all=new HashSet<>(occupancy);all.addAll(rails);all.addAll(doors);all.add(support);return Set.copyOf(all);}
    }
    public record SpeedProfile(double cruiseMps,double accelerationMps2,double decelerationMps2)
    {
        public SpeedProfile{require(Double.isFinite(cruiseMps)&&Double.isFinite(accelerationMps2)&&Double.isFinite(decelerationMps2)&&cruiseMps>0&&accelerationMps2>0&&decelerationMps2>0,"Explicit positive cruise/acceleration/deceleration required");}
    }
    public record MotionProfile(String type,double cruiseMps,double accelerationMps2,double decelerationMps2,String readyNode,int phaseVersion,SpeedProfile prelaunch)
    {
        public MotionProfile(String type,double cruise,double acceleration,double deceleration,String ready){this(type,cruise,acceleration,deceleration,ready,0,null);}
        public MotionProfile
        {
            require("continuous_upright".equals(type),"Explicit continuous_upright profile required");
            new SpeedProfile(cruiseMps,accelerationMps2,decelerationMps2);readyNode=identifier(readyNode);
            require(phaseVersion==0&&prelaunch==null||phaseVersion==1&&prelaunch!=null,"Explicit supported phase version and prelaunch profile required");
            if(prelaunch!=null)require(prelaunch.cruiseMps()<cruiseMps,"Prelaunch speed must be lower than launch speed");
        }
        public SpeedProfile launch(){return new SpeedProfile(cruiseMps,accelerationMps2,decelerationMps2);}
    }
    public record LegSpan(String id,double from,double to)
    {public LegSpan {id=identifier(id);require(Double.isFinite(from)&&Double.isFinite(to)&&from>=0&&to<=1&&to>=from,"Bounded monotone actual leg span required");}}
    public record RoutePosition(int legIndex,double fraction){}
    public record Route(String id,int variant,int bank,int lane,Region region,String port,String reverseOf,List<String> legs,MotionProfile motionProfile)
    {
        public Route(String id,int variant,int bank,int lane,Region region,String port,String reverseOf,List<String> legs){this(id,variant,bank,lane,region,port,reverseOf,legs,null);}
        public Route{id=identifier(id);checkVariant(variant);require(bank>=1&&bank<=3&&lane>=0&&lane<=2,"Route bank/lane required");Objects.requireNonNull(region);port=identifier(port);reverseOf=reverseOf==null?"":reverseOf;legs=List.copyOf(legs);require(!legs.isEmpty(),"Empty route");}
        public boolean recovery(){return !reverseOf.isEmpty();}
        public boolean continuousUpright(){return motionProfile!=null;}
        private MotionProfile profile(){require(motionProfile!=null,"Legacy route has no continuous speed authority");return motionProfile;}
        public double cruiseMps(){return profile().cruiseMps();}
        public double accelerationMps2(){return profile().accelerationMps2();}
        public double decelerationMps2(){return profile().decelerationMps2();}
        public String readyNode(){return profile().readyNode();}
        public boolean phased(){return motionProfile!=null&&motionProfile.phaseVersion()==1;}
    }
    public record Port(String id,Region region,String node,Map<Integer,String> reverseRoutes)
    {public Port{id=identifier(id);Objects.requireNonNull(region);node=identifier(node);reverseRoutes=Map.copyOf(reverseRoutes);}}
    /** Must inspect actual approach/track/door/collision availability, not a distance-only shortcut. */
    public interface RecoveryAccess { boolean reachable(Port port,Route reverseRoute); }

    private final long epoch;
    private final boolean installed;
    private final String fingerprint;
    private final Map<Integer,Unit> units;
    private final Map<String,Node> nodes;
    private final Map<String,Resource> resources;
    private final Map<String,Leg> legs;
    private final Map<String,Route> routes;
    private final Map<String,Port> ports;
    private final NervDynamicAirspaceR52 dynamicSpaces;
    private final Map<String,RampArc> rampArcs=new HashMap<>();
    private final Set<String> continuousLegs;
    private final int schemaVersion;
    private final Map<Integer,BankRole> bankRoles;
    private NervRouteDirectoryR52(long epoch,boolean installed,String fingerprint,Map<Integer,Unit> units,Map<String,Node> nodes,
                                 Map<String,Resource> resources,Map<String,Leg> legs,Map<String,Route> routes,Map<String,Port> ports,NervDynamicAirspaceR52 dynamicSpaces,int schemaVersion,Map<Integer,BankRole> bankRoles)
    {
        require(epoch>0,"Root commissioning epoch required");this.epoch=epoch;this.installed=installed;this.fingerprint=fingerprint;
        this.schemaVersion=schemaVersion;this.bankRoles=Map.copyOf(bankRoles);
        this.units=Map.copyOf(units);this.nodes=Map.copyOf(nodes);this.resources=Map.copyOf(resources);this.legs=Map.copyOf(legs);this.routes=Map.copyOf(routes);this.ports=Map.copyOf(ports);this.continuousLegs=routes.values().stream().filter(Route::continuousUpright).flatMap(r->r.legs().stream()).collect(java.util.stream.Collectors.toUnmodifiableSet());this.dynamicSpaces=Objects.requireNonNull(dynamicSpaces);validate();for(var domain:dynamicSpaces.domains())require(knowsDimension(domain.dimension()),"Dynamic SPACE domain must use an actual Root directory dimension");
        if(!dynamicSpaces.domains().isEmpty())for(var resource:resources.values())if(resource.kind()==ResourceKind.SPACE)require(NervDynamicAirspaceR52.canonicalBox(resource.id())!=null&&resource.component().equals(resource.id()),"Ground and dynamic air SPACE must use the same canonical32m identity");
    }
    public long epoch(){return epoch;}
    public boolean installed(){return installed;}
    public String fingerprint(){return fingerprint;}
    public int schemaVersionR52(){return schemaVersion;}
    public BankRole bankRoleR52(int bank){var role=bankRoles.get(bank);require(role!=null,"Undeclared launch bank");return role;}
    public int bankForIntentR52(String intent){return bankRoles.values().stream().filter(r->r.intent().equals(intent)).findFirst().orElseThrow(()->new IllegalArgumentException("Undeclared departure intent")).bank();}
    public void validateCompactLaunchContractR52()
    {
        require(schemaVersion==2&&bankForIntentR52("geofront")==1&&bankForIntentR52("surface")==2&&bankForIntentR52("hakone")==3,"Current compact launch contract requires explicit bank1=geofront, bank2=surface, bank3=hakone");
        require(routes.values().stream().allMatch(Route::phased),"Current compact launch contract requires explicit stopped prelaunch/launch phases");
    }
    public Unit unit(int variant){return units.get(variant);}
    public Node node(String id){return nodes.get(id);}
    public Leg leg(String id){return legs.get(id);}
    public Route route(String id){return routes.get(id);}
    public Map<String,Port> ports(){return ports;}
    public Resource resource(String id){var declared=resources.get(id);return declared!=null?declared:dynamicSpaces.resource(id);}
    public NervDynamicAirspaceR52 dynamicSpacesR52(){return dynamicSpaces;}
    public Map<String,Resource> declaredResources(){return resources;}
    public Map<String,Route> routes(){return routes;}
    public boolean knowsDimension(String dimension){return nodes.values().stream().anyMatch(node->node.dimension().equals(dimension));}
    public Set<String> resources(Route route)
    {var result=new HashSet<String>();for(String id:route.legs())result.addAll(leg(id).resources());return Set.copyOf(result);}

    private void validate()
    {
        require(units.keySet().equals(Set.of(0,1,2)),"Original three-unit roster required");var actors=new HashSet<UUID>();var unitLanes=new HashSet<Integer>();
        for(var unit:units.values())require(actors.add(unit.eva())&&actors.add(unit.plug()),"Duplicate original actor identity");
        for(var unit:units.values())require(unitLanes.add(unit.lane()),"Root unit-to-physical-lane binding must be bijective");
        var laneKeys=new HashSet<String>();
        for(var node:nodes.values())if(node.role()==Role.BANK)require(laneKeys.add(node.bank()+"/"+node.lane()),"Duplicate bank/lane dock");
        require(laneKeys.size()==9,"Exactly three banks with three explicit lane docks required");
        var physical=new HashSet<String>();for(var resource:resources.values())require(physical.add(resource.component()),"Physical component aliased by multiple reservation IDs");
        for(var leg:legs.values())
        {
            Node from=node(leg.from()),to=node(leg.to());require(from!=null&&to!=null&&from.dimension().equals(to.dimension()),"Missing endpoint or cross-dimension route gap");
            if(leg.rampProfile()!=null)
            {require(leg.motion()==Motion.ORIGINAL_UPRIGHT_TRANSFER,"Rounded original grade belongs only to the original upright transfer");leg.rampProfile().checkLength(from.footFrame().translation().subtract(to.footFrame().translation()).horizontalDistance());}
            if(leg.centreCurve()!=null)
            {require(leg.motion()!=Motion.FOOT_BEARING_TURN,"A centre curve cannot masquerade as a stationary turn");require(leg.centreCurve().point(0).equals(from.footFrame().translation())&&leg.centreCurve().point(1).equals(to.footFrame().translation()),"Curve controls do not meet actual node foot centres");require(fixed(from.footFrame().rotation(),to.footFrame().rotation())&&fixed(leg.evaFrom().quaternion(),leg.evaTo().quaternion()),"Explicit centre curves keep the EVA/bearing orientation fixed");}
            for(String rail:leg.rails())resource(rail,ResourceKind.RAIL);for(String door:leg.doors())resource(door,ResourceKind.DOOR);resource(leg.support(),ResourceKind.SUPPORT);
            for(String occupied:leg.occupancy())resource(occupied,ResourceKind.SPACE);
            if(leg.motion()==Motion.FOOT_BEARING_TURN)
                require(from.footFrame().translation().equals(to.footFrame().translation()),"Bearing turn must retain the same physical support centre");
            else require(from.footFrame().translation().distanceToSqr(to.footFrame().translation())>0,"Zero-length placeholder travel leg");
            if(leg.centreCurve()==null&&leg.motion()==Motion.VERTICAL)require(from.footFrame().translation().x==to.footFrame().translation().x&&from.footFrame().translation().z==to.footFrame().translation().z,"Vertical leg has lateral gap");
            if(leg.motion()==Motion.ORIGINAL_UPRIGHT_TRANSFER||leg.motion()==Motion.TRACKED_BANK_TRANSFER)
            {
                require(upright(from,leg.evaFrom())&&upright(to,leg.evaTo()),"Original/bank transfer must preserve an upright EVA");
                require(same(worldRotation(from,leg.evaFrom()),worldRotation(to,leg.evaTo())),"Original transfer body orientation changed along the ramp");
            }
            if(leg.motion()==Motion.TRACKED_BANK_TRANSFER)require(!leg.doors().isEmpty(),"Serial bank transfer needs an explicit rear pressure gate");
        }
        var departures=new HashSet<String>();
        for(var route:routes.values())
        {
            require(units.containsKey(route.variant())&&ports.containsKey(route.port()),"Unknown route unit/intake");
            require(units.get(route.variant()).lane()==route.lane(),"Route cannot replace original unit identity with an x/lane index");
            var port=ports.get(route.port());require(port.region()==route.region(),"Port/route region mismatch");
            Leg prior=null;
            for(String id:route.legs())
            {
                Leg leg=leg(id);require(leg!=null,"Undeclared route leg");
                if(prior!=null)require(prior.to().equals(leg.from())&&same(prior.evaTo().quaternion(),leg.evaFrom().quaternion()),"Disconnected endpoint or instantaneous body turn");
                prior=leg;
            }
            if(schemaVersion==2)require(route.phased(),"Current v2 directory requires explicit phase_version=1 and slow prelaunch");
            if(route.continuousUpright())validateContinuous(route);
            if(route.recovery())validateReverse(route);
            else
            {
                require(departures.add(route.variant()+"/"+route.bank()+"/"+route.lane()),"Duplicate unit/bank/lane departure");
                validateDeparture(route);require(prior.to().equals(port.node()),"Departure is not bound to the physical intake endpoint");
            }
        }
        if(schemaVersion==2)
        {
            require(departures.size()==9&&routes.size()==18,"Explicit bank roles require all nine original-unit departures and nine complete recoveries");
            for(var out:routes.values())if(!out.recovery())require(routes.values().stream().filter(back->back.reverseOf().equals(out.id())).count()==1,"Each departure requires exactly one original-unit reverse route");
        }
        for(var port:ports.values())
        {
            require(node(port.node())!=null&&node(port.node()).role()==Role.EXIT,"Explicit intake node required");
            require(!port.reverseRoutes().isEmpty(),"Intake has no real reverse route");
            for(var binding:port.reverseRoutes().entrySet())
            {
                Route route=route(binding.getValue());require(route!=null&&route.recovery()&&route.variant()==binding.getKey()&&route.port().equals(port.id())&&route.region()==port.region(),"Wrong actor/entrance reverse binding");
            }
        }
    }
    private void validateDeparture(Route route)
    {
        Leg first=leg(route.legs().get(0));Node bay=node(first.from()),dock=node(first.to());
        require(first.motion()==Motion.ORIGINAL_UPRIGHT_TRANSFER&&bay.role()==Role.BAY&&bay.variant()==route.variant()
                &&dock.role()==Role.BANK&&dock.bank()==1&&dock.lane()==route.lane(),"Bay must use original upright ramp into bank1");
        Vec3 ramp=dock.footFrame().translation().subtract(bay.footFrame().translation());require(ramp.y>0&&ramp.horizontalDistanceSqr()>0,"Original transfer must use the actual rising inclined path");
        int current=1,index=1;
        while(index<route.legs().size()&&leg(route.legs().get(index)).motion()==Motion.TRACKED_BANK_TRANSFER)
        {
            Leg next=leg(route.legs().get(index++));Node a=node(next.from()),b=node(next.to());
            require(a.role()==Role.BANK&&b.role()==Role.BANK&&a.bank()==current&&b.bank()==current+1&&a.lane()==route.lane()&&b.lane()==route.lane(),"Banks must transfer serially 1->2->3 on explicit same-lane rails");current++;
        }
        require(current==route.bank(),"Departure skipped a serial bank");
        var bankRole=bankRoleR52(route.bank());require(route.region()==bankRole.region(),"Route region differs from its explicit bank role");
        if(route.continuousUpright()) {require(index<route.legs().size(),"Actual bank-to-port launch curve required");require(node(leg(route.legs().get(route.legs().size()-1)).to()).footFrame().translation().y>node(leg(route.legs().get(index)).from()).footFrame().translation().y,"Continuous launch must reach the actual higher port");return;}
        var sequence=new ArrayList<Motion>();
        for(;index<route.legs().size();index++)
        {
            Leg leg=leg(route.legs().get(index));Motion m=leg.motion();
            if(m!=Motion.FOOT_BEARING_TURN){require(node(leg.to()).footFrame().translation().y>node(leg.from()).footFrame().translation().y,"Departure launch travel must rise");sequence.add(m);}
            if(m==Motion.LAUNCH_INCLINE)require(node(leg.to()).footFrame().translation().subtract(node(leg.from()).footFrame().translation()).horizontalDistanceSqr()>0,"Inclined launch has no actual horizontal track");
        }
        require(sequence.equals(bankRole.legacyLaunchSequence()),"Launch sequence differs from the explicit bank role");
    }
    private void validateReverse(Route route)
    {
        Route original=route(route.reverseOf());require(original!=null&&!original.recovery()&&original.variant()==route.variant()&&original.bank()==route.bank()
                &&original.lane()==route.lane()&&original.region()==route.region()&&original.port().equals(route.port())&&original.legs().size()==route.legs().size(),"Recovery must bind the same unit/port and complete actual departure");
        require(Objects.equals(original.motionProfile(),route.motionProfile()),"Recovery must retain the same stopped bank and explicit speed profiles");
        for(int i=0;i<route.legs().size();i++)
        {
            Leg back=leg(route.legs().get(i)),out=leg(original.legs().get(original.legs().size()-1-i));
            require(back.from().equals(out.to())&&back.to().equals(out.from())&&back.motion()==out.motion()&&back.resources().equals(out.resources())
                    &&same(back.evaFrom().quaternion(),out.evaTo().quaternion())&&same(back.evaTo().quaternion(),out.evaFrom().quaternion()),"Reverse leg/path/resource/pose mismatch");
            double length=node(out.from()).footFrame().translation().subtract(node(out.to()).footFrame().translation()).horizontalDistance();
            require(out.rampProfile()==null?back.rampProfile()==null:out.rampProfile().reversed(length).sameGeometry(back.rampProfile()),"Reverse original rail elevation differs");
            require(out.centreCurve()==null?back.centreCurve()==null:out.centreCurve().isReverseOf(back.centreCurve()),"Reverse explicit centre curve differs");
        }
    }
    private void validateContinuous(Route route)
    {
        Leg first=leg(route.legs().get(0));var basis=node(first.from()).footFrame().rotation();var relative=first.evaFrom().quaternion();
        require(upright(node(first.from()),first.evaFrom()),"Continuous route must retain the prepared upright EVA");boolean ready=first.from().equals(route.readyNode());Leg prior=null;
        for(String id:route.legs()) {
            var current=leg(id);require(current.motion()!=Motion.FOOT_BEARING_TURN,"Continuous routes cannot contain stationary turn stations");
            require(fixed(basis,node(current.from()).footFrame().rotation())&&fixed(basis,node(current.to()).footFrame().rotation())&&fixed(relative,current.evaFrom().quaternion())&&fixed(relative,current.evaTo().quaternion()),"Continuous route changed prepared EVA/bearing orientation");
            if(prior!=null&&!(route.phased()&&current.from().equals(route.readyNode())))require(tangent(prior,1).distanceTo(tangent(current,0))<=1e-7,"Continuous route tangent is disconnected");
            ready|=current.to().equals(route.readyNode());prior=current;
        }
        require(ready,"Explicit ready_node is not on this actual route");
        if(route.phased())
        {
            var bank=node(route.readyNode());require(bank!=null&&bank.role()==Role.BANK&&bank.bank()==route.bank()&&bank.lane()==route.lane(),"READY must be the selected physical bank");
            require(readyDistanceR53(route)>0&&readyDistanceR53(route)<routeLength(route),"Both stopped motion phases require actual nonzero travel");
            if(!route.recovery())validateAscendingLaunchR53(route);
        }
    }
    public double readyDistanceR53(Route route)
    {
        double metres=0;for(String id:route.legs()){var leg=leg(id);if(leg.from().equals(route.readyNode()))return metres;metres+=legLength(leg);if(leg.to().equals(route.readyNode()))return metres;}
        throw new IllegalArgumentException("READY is not on actual route");
    }
    private void validateAscendingLaunchR53(Route route)
    {
        boolean launch=false,first=true;
        for(String id:route.legs())
        {
            var leg=leg(id);if(leg.from().equals(route.readyNode()))launch=true;if(!launch)continue;
            require(leg.rampProfile()==null&&(leg.motion()==Motion.VERTICAL||leg.motion()==Motion.LAUNCH_INCLINE),"Launch phase cannot contain bank transfer, original ramp or turn station");
            var segments=leg.centreCurve()==null?List.of(new NervCentrelineCurveR52.Segment(NervCentrelineCurveR52.Type.LINE,List.of(node(leg.from()).footFrame().translation(),node(leg.to()).footFrame().translation()))):leg.centreCurve().segments();
            for(var segment:segments)
            {
                var controls=segment.controls();
                for(int i=1;i<controls.size();i++)require(controls.get(i).y>controls.get(i-1).y,"Every launch control derivative must strictly rise; horizontal/descent segments are forbidden");
                boolean vertical=controls.stream().allMatch(v->v.x==controls.get(0).x&&v.z==controls.get(0).z);
                require(!first||vertical,"Launch starts with an actual nonzero pure vertical segment");
                require(!bankRoleR52(route.bank()).intent().equals("geofront")||vertical,"GeoFront launch must remain purely vertical");first=false;
            }
        }
        require(!first,"Actual ascending launch phase required");
    }
    private static boolean fixed(Quaternionf a,Quaternionf b)
    {return a.x==b.x&&a.y==b.y&&a.z==b.z&&a.w==b.w||a.x==-b.x&&a.y==-b.y&&a.z==-b.z&&a.w==-b.w;}
    private void resource(String id,ResourceKind expected)
    {Resource resource=resources.get(id);require(resource!=null&&resource.kind()==expected,"Undeclared/wrong physical rail, door, support or space resource: "+id);}
    public Optional<Route> nearestRecovery(int variant,Region region,String dimension,Vec3 actualFoot,RecoveryAccess access)
    {
        checkVariant(variant);finite(actualFoot);Objects.requireNonNull(access);if(!installed)return Optional.empty();
        return ports.values().stream().filter(p->p.region()==region&&node(p.node()).dimension().equals(dimension)&&p.reverseRoutes().containsKey(variant))
                .filter(p->access.reachable(p,route(p.reverseRoutes().get(variant))))
                .min(Comparator.comparingDouble((Port p)->node(p.node()).footFrame().translation().distanceToSqr(actualFoot)).thenComparing(Port::id))
                .map(p->route(p.reverseRoutes().get(variant)));
    }
    /** Caller supplies the original posed feet/plug, never a guessed entity-origin pivot. */
    public FootSupportFrameR52.Sample sample(Leg leg,double fraction,FootSupportFrameR52.Binding original)
    {
        require(leg!=null&&leg.equals(legs.get(leg.id())),"Sample must use an explicit leg from this Root directory");
        require(Double.isFinite(fraction)&&fraction>=0&&fraction<=1,"Fraction outside leg");
        var from=node(leg.from()).footFrame();var to=node(leg.to()).footFrame();
        RigidTransform bearing=from.interpolate(to,fraction);
        if(leg.rampProfile()!=null)
        {
            double length=from.translation().subtract(to.translation()).horizontalDistance();
            double h=leg.rampProfile().heightFraction(length,fraction);
            var q=bearing.rotation();var p=bearing.translation();
            bearing=new RigidTransform(new Vec3(p.x,from.translation().y+(to.translation().y-from.translation().y)*h,p.z),q.x,q.y,q.z,q.w);
        }
        if(leg.centreCurve()!=null)bearing=RigidTransform.of(leg.centreCurve().point(fraction),from.rotation());
        if(NervR50CarrierModeR53.enabled()&&continuousLegs.contains(leg.id()))
        {
            // These rails were authored against the original carrier's sole
            // reference. A recovered stance may change the measured feet, but
            // must not move the rail origin or the carried EVA root with it.
            for(var route:routes.values())if(route.continuousUpright()&&route.legs().contains(leg.id()))
            {
                try
                {
                    var reference=NervFootGuideRigR52.nominalBinding(route.variant());
                    var root=FootSupportFrameR52.sample(reference,bearing,leg.evaFrom().quaternion(),leg.evaTo().quaternion(),fraction).evaRoot();
                    return new FootSupportFrameR52.Sample(root,root.transformPoint(original.leftFoot()),
                            root.transformPoint(original.rightFoot()),root.compose(original.plugInEva()));
                }
                catch(java.io.IOException missing){throw new IllegalStateException("Original carrier route reference unavailable",missing);}
            }
        }
        return FootSupportFrameR52.sample(original,bearing,leg.evaFrom().quaternion(),leg.evaTo().quaternion(),fraction);
    }
    private void actual(Leg leg){require(leg!=null&&leg.equals(legs.get(leg.id())),"Actual directory leg required");}
    public Vec3 centrePoint(Leg leg,double fraction)
    {
        actual(leg);require(Double.isFinite(fraction)&&fraction>=0&&fraction<=1,"Bounded fraction required");if(leg.centreCurve()!=null)return leg.centreCurve().point(fraction);
        var a=node(leg.from()).footFrame();var b=node(leg.to()).footFrame();var p=a.interpolate(b,fraction).translation();if(leg.rampProfile()==null)return p;
        return new Vec3(p.x,a.translation().y+(b.translation().y-a.translation().y)*leg.rampProfile().heightFraction(a.translation().subtract(b.translation()).horizontalDistance(),fraction),p.z);
    }
    public Vec3 point(Leg leg,double fraction){return centrePoint(leg,fraction);}
    public Vec3 tangent(Leg leg,double fraction)
    {
        actual(leg);require(Double.isFinite(fraction)&&fraction>=0&&fraction<=1,"Bounded fraction required");if(leg.centreCurve()!=null)return leg.centreCurve().tangent(fraction);
        var delta=node(leg.to()).footFrame().translation().subtract(node(leg.from()).footFrame().translation());double dy=delta.y;
        if(leg.rampProfile()!=null){var r=leg.rampProfile();double h=delta.horizontalDistance(),d=h*fraction-r.flatBefore(),s=0;if(d>0&&d<r.slopeRun())s=d<r.blend()?(1-Math.cos(Math.PI*d/r.blend()))*.5:d>r.slopeRun()-r.blend()?(1-Math.cos(Math.PI*(r.slopeRun()-d)/r.blend()))*.5:1;dy*=h*s/(r.slopeRun()-r.blend());}
        var v=new Vec3(delta.x,dy,delta.z);require(v.lengthSqr()>0,"Stationary leg has no running tangent");return v.scale(1/v.length());
    }
    static final class RampArc {
        final int count=4096;final double[] cumulative=new double[count+1];final double error,pointError,curvature;
        RampArc(Vec3 a,Vec3 b,NervRampProfileR52 r){double h=b.subtract(a).horizontalDistance();Vec3 before=a;
            for(int i=1;i<=count;i++){double f=i/(double)count;var at=new Vec3(a.x+(b.x-a.x)*f,a.y+(b.y-a.y)*r.heightFraction(h,f),a.z+(b.z-a.z)*f);cumulative[i]=cumulative[i-1]+at.distanceTo(before);before=at;}
            double k=r.secondDerivativeBound(h,b.y-a.y,1);double active=0;for(int i=0;i<count;i++){double lo=h*i/count,hi=h*(i+1D)/count;if(hi>=r.flatBefore()&&lo<=r.flatBefore()+r.blend()||hi>=r.flatBefore()+r.slopeRun()-r.blend()&&lo<=r.flatBefore()+r.slopeRun())active++;}
            double scale=Math.max(Math.max(Math.abs(a.x),Math.abs(b.x)),Math.max(Math.max(Math.abs(a.y),Math.abs(b.y)),Math.max(Math.abs(a.z),Math.abs(b.z))));
            error=active*k*k/(8*h*(double)count*count*count)+Math.ulp(cumulative[count])*(count+4)+Math.ulp(Math.max(1,scale))*count*16;
            // Linear interpolation of the cumulative chord table additionally
            // differs from partial true arc by |S''| h^2/8, S'=|P'|.
            pointError=2*error+k/(8D*count*count)+h*Math.scalb(1D,-24)+Math.ulp(Math.max(1,scale))*64;curvature=k/(h*h);}
        double distance(double fraction){double t=fraction*count;int i=Math.min(count-1,(int)t);return cumulative[i]+(cumulative[i+1]-cumulative[i])*(t-i);}
        double fraction(double distance){int low=0,high=count;while(low+1<high){int mid=(low+high)>>>1;if(cumulative[mid]<=distance)low=mid;else high=mid;}return(low+(distance-cumulative[low])/(cumulative[low+1]-cumulative[low]))/count;}
    }
    private synchronized RampArc rampArc(Leg leg){actual(leg);return rampArcs.computeIfAbsent(leg.id(),id->new RampArc(node(leg.from()).footFrame().translation(),node(leg.to()).footFrame().translation(),leg.rampProfile()));}
    public double legLength(Leg leg){actual(leg);return leg.centreCurve()!=null?leg.centreCurve().length():leg.rampProfile()!=null?rampArc(leg).cumulative[4096]:node(leg.from()).footFrame().translation().distanceTo(node(leg.to()).footFrame().translation());}
    public double legLength(String id){return legLength(leg(id));}
    public double legLengthError(Leg leg){actual(leg);return leg.centreCurve()!=null?leg.centreCurve().lengthErrorBound():leg.rampProfile()!=null?rampArc(leg).error:0;}
    public double legDistance(Leg leg,double fraction){actual(leg);require(Double.isFinite(fraction)&&fraction>=0&&fraction<=1,"Bounded geometric fraction required");return leg.rampProfile()!=null?rampArc(leg).distance(fraction):legLength(leg)*fraction;}
    public double legFractionAtDistance(Leg leg,double metres){double length=legLength(leg);require(Double.isFinite(metres)&&metres>=0&&metres<=length,"Distance outside actual leg");return metres==0?0:metres==length?1:leg.rampProfile()!=null?rampArc(leg).fraction(metres):metres/length;}
    public double routeLength(Route route){require(route!=null&&route.equals(routes.get(route.id())),"Actual route required");double length=0;for(String id:route.legs())length+=legLength(leg(id));return length;}
    public double routeDistance(Route route,int legIndex,double fraction){require(legIndex>=0&&legIndex<route.legs().size(),"Actual route leg index required");routeLength(route);double distance=0;for(int i=0;i<legIndex;i++)distance+=legLength(leg(route.legs().get(i)));return distance+legDistance(leg(route.legs().get(legIndex)),fraction);}
    public RoutePosition locateDistance(Route route,double metres){double total=routeLength(route);require(Double.isFinite(metres)&&metres>=0&&metres<=total,"Distance outside actual route");if(metres==total)return new RoutePosition(route.legs().size()-1,1);if(metres==0)return new RoutePosition(0,0);double before=0;for(int i=0;i<route.legs().size();i++){var leg=leg(route.legs().get(i));double length=legLength(leg);if(metres<before+length||i==route.legs().size()-1)return new RoutePosition(i,legFractionAtDistance(leg,Math.max(0,Math.min(length,metres-before))));before+=length;}throw new IllegalStateException("Route length mismatch");}
    public List<LegSpan> routeSpans(Route route,double fromMetres,double toMetres){require(route.continuousUpright(),"Arc spans require explicit continuous route authority");var from=locateDistance(route,fromMetres);var to=locateDistance(route,toMetres);require(toMetres>=fromMetres,"Monotone route distance required; use the actual reverse route for recovery");var spans=new ArrayList<LegSpan>();for(int i=from.legIndex();i<=to.legIndex();i++){String id=route.legs().get(i);double a=i==from.legIndex()?from.fraction():0,b=i==to.legIndex()?to.fraction():1;if(b>a||fromMetres==toMetres)spans.add(new LegSpan(id,a,b));}return List.copyOf(spans);}
    public List<DirectoryTrajectoryR52> routeSlices(Route route,double fromMetres,double toMetres,FootSupportFrameR52.Binding binding){return routeSpans(route,fromMetres,toMetres).stream().map(s->new DirectoryTrajectoryR52(this,leg(s.id()),binding,s.from(),s.to())).toList();}
    public boolean usesArcLengthSampling(Leg leg){actual(leg);return leg.centreCurve()!=null||continuousLegs.contains(leg.id());}
    public double intervalFraction(Leg leg,double from,double to,double time){actual(leg);require(Double.isFinite(time)&&time>=0&&time<=1,"Bounded interval time required");if(time==0)return from;if(time==1)return to;if(leg.rampProfile()!=null&&usesArcLengthSampling(leg))return legFractionAtDistance(leg,legDistance(leg,from)+(legDistance(leg,to)-legDistance(leg,from))*time);return from+(to-from)*time;}
    public double translationSecondDerivativeBound(Leg leg,double from,double to){actual(leg);if(leg.centreCurve()!=null)return leg.centreCurve().secondDerivativeBound(from,to);if(leg.rampProfile()==null)return 0;if(usesArcLengthSampling(leg)){if(from==to)return 0;var metric=rampArc(leg);double distance=legDistance(leg,to)-legDistance(leg,from)+2*metric.pointError;return metric.curvature*distance*distance;}var a=node(leg.from()).footFrame().translation();var b=node(leg.to()).footFrame().translation();return leg.rampProfile().secondDerivativeBound(b.subtract(a).horizontalDistance(),b.y-a.y,to-from);}
    public double translationSamplingError(Leg leg){actual(leg);return leg.centreCurve()!=null?2*leg.centreCurve().pointErrorBound():leg.rampProfile()!=null&&usesArcLengthSampling(leg)?2*rampArc(leg).pointError:0;}
    private static Quaternionf worldRotation(Node node,Rotation relative){return node.footFrame().rotation().mul(relative.quaternion()).normalize();}
    private static boolean upright(Node node,Rotation rotation){return worldRotation(node,rotation).transform(new org.joml.Vector3f(0,1,0)).distance(new org.joml.Vector3f(0,1,0))<1e-5;}
    private static boolean same(Quaternionf a,Quaternionf b){return Math.abs(a.dot(b))>1-1e-6;}
    static void require(boolean condition,String reason){if(!condition)throw new IllegalArgumentException(reason);}
    private static void checkVariant(int value){require(value>=0&&value<=2,"Original variant0..2 required");}
    private static String identifier(String value){require(value!=null&&value.matches("[A-Za-z0-9_./:-]{1,160}"),"Explicit directory ID required");return value;}
    private static void finite(Vec3 p){require(p!=null&&Double.isFinite(p.x)&&Double.isFinite(p.y)&&Double.isFinite(p.z),"Finite Root-measured point required");}

    public static NervRouteDirectoryR52 parse(JsonObject root)
    {
        require(!root.has("air_transport")&&!root.has("directory_fingerprint")&&!root.has("fingerprint"),
                "Directory identity cannot contain its own fingerprint or dependent air manifest");
        String schema=text(root,"schema");int schemaVersion=EXPLICIT_BANK_SCHEMA.equals(schema)?2:SCHEMA.equals(schema)?1:0;
        require(schemaVersion!=0&&"root".equals(text(root,"map_author")),"Root runtime-directory schema required; spatial draft is not a runtime installation");
        var bankRoles=parseBankRolesR52(root,schemaVersion);
        String status=text(root,"status");require(status.equals("design")||status.equals("installed"),"Explicit design/installed status required");
        boolean installed=status.equals("installed");if(installed)require(text(root,"installation_receipt_sha256").matches("[0-9a-f]{64}"),"Explicit Root installation receipt required");
        long epoch=whole(root,"epoch");var units=new LinkedHashMap<Integer,Unit>();var nodes=new LinkedHashMap<String,Node>();var resources=new LinkedHashMap<String,Resource>();var legs=new LinkedHashMap<String,Leg>();var routes=new LinkedHashMap<String,Route>();var ports=new LinkedHashMap<String,Port>();
        for(var value:root.getAsJsonArray("units")){var o=value.getAsJsonObject();var u=new Unit(integer(o,"variant"),integer(o,"lane"),UUID.fromString(text(o,"eva")),UUID.fromString(text(o,"plug")));unique(units,u.variant(),u);}
        for(var value:root.getAsJsonArray("nodes"))
        {
            var o=value.getAsJsonObject();Role role=Role.valueOf(text(o,"role"));var frame=o.getAsJsonObject("foot_frame");var p=frame.getAsJsonArray("translation");require(p.size()==3,"Measured bearing point required");Rotation q=rotation(frame.getAsJsonArray("quaternion_xyzw"));
            var n=new Node(text(o,"id"),text(o,"dimension"),role,role==Role.BANK?integer(o,"bank"):0,role==Role.BANK?integer(o,"lane"):0,role==Role.BAY?integer(o,"variant"):-1,new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),q.x(),q.y(),q.z(),q.w()));unique(nodes,n.id(),n);
        }
        for(var value:root.getAsJsonArray("resources")){var o=value.getAsJsonObject();var v=new Resource(text(o,"id"),ResourceKind.valueOf(text(o,"kind")),text(o,"component"));unique(resources,v.id(),v);}
        for(var value:root.getAsJsonArray("legs"))
        {
            var o=value.getAsJsonObject();NervRampProfileR52 profile=null;
            if(o.has("ramp_profile")){var r=o.getAsJsonObject("ramp_profile");profile=new NervRampProfileR52(r.get("flat_before").getAsDouble(),r.get("slope_run").getAsDouble(),r.get("blend").getAsDouble());}
            var v=new Leg(text(o,"id"),text(o,"from"),text(o,"to"),Motion.valueOf(text(o,"motion")),integer(o,"ticks"),rotation(o.getAsJsonArray("eva_from_xyzw")),rotation(o.getAsJsonArray("eva_to_xyzw")),names(o,"rails"),names(o,"doors"),text(o,"support"),Set.copyOf(names(o,"occupancy")),profile,o.has("centre_curve")?NervCentrelineCurveR52.parse(o.getAsJsonObject("centre_curve")):null);unique(legs,v.id(),v);
        }
        for(var value:root.getAsJsonArray("routes")){var o=value.getAsJsonObject();var v=new Route(text(o,"id"),integer(o,"variant"),integer(o,"bank"),integer(o,"lane"),Region.valueOf(text(o,"region")),text(o,"port"),o.has("reverse_of")?text(o,"reverse_of"):"",names(o,"legs"),motionProfile(o));unique(routes,v.id(),v);}
        for(var value:root.getAsJsonArray("ports"))
        {
            var o=value.getAsJsonObject();var reverse=new LinkedHashMap<Integer,String>();for(var entry:o.getAsJsonObject("reverse_routes").entrySet()){int v=Integer.parseInt(entry.getKey());checkVariant(v);unique(reverse,v,entry.getValue().getAsString());}
            var p=new Port(text(o,"id"),Region.valueOf(text(o,"region")),text(o,"node"),reverse);unique(ports,p.id(),p);
        }
        try{return new NervRouteDirectoryR52(epoch,installed,HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(root.toString().getBytes(StandardCharsets.UTF_8))),units,nodes,resources,legs,routes,ports,NervDynamicAirspaceR52.parse(root),schemaVersion,bankRoles);}
        catch(java.security.NoSuchAlgorithmException failure){throw new IllegalStateException(failure);}
    }
    private static Map<Integer,BankRole> parseBankRolesR52(JsonObject root,int version)
    {
        if(version==1){require(!root.has("bank_roles")&&!root.has("bank_roles_version"),"Legacy v1 cannot silently reinterpret explicit bank roles");return Map.of(1,new BankRole(1,"surface"),2,new BankRole(2,"geofront"),3,new BankRole(3,"hakone"));}
        require(integer(root,"bank_roles_version")==1&&root.has("bank_roles")&&root.get("bank_roles").isJsonArray(),"Versioned explicit bank roles required");
        var roles=new LinkedHashMap<Integer,BankRole>();var intents=new HashSet<String>();
        for(var raw:root.getAsJsonArray("bank_roles")){require(raw.isJsonObject(),"Explicit bank role object required");var row=raw.getAsJsonObject();require(row.keySet().equals(Set.of("bank","intent")),"Exact bank role fields required");var role=new BankRole(integer(row,"bank"),text(row,"intent"));unique(roles,role.bank(),role);require(intents.add(role.intent()),"Each departure intent must name exactly one bank");}
        require(roles.keySet().equals(Set.of(1,2,3))&&intents.equals(Set.of("surface","geofront","hakone")),"Complete bijective bank role declaration required");return Map.copyOf(roles);
    }
    private static MotionProfile motionProfile(JsonObject route)
    {
        if(!route.has("motion_profile"))return null;require(route.get("motion_profile").isJsonObject(),"Explicit motion_profile object required");var o=route.getAsJsonObject("motion_profile");
        var fields=new HashSet<>(Set.of("type","cruise_mps","acceleration_mps2","deceleration_mps2","ready_node"));int version=0;SpeedProfile prelaunch=null;
        if(o.has("phase_version")){fields.add("phase_version");fields.add("prelaunch");version=integer(o,"phase_version");require(version==1&&o.has("prelaunch")&&o.get("prelaunch").isJsonObject(),"Explicit phase_version=1 and prelaunch required");var p=o.getAsJsonObject("prelaunch");require(p.keySet().equals(Set.of("cruise_mps","acceleration_mps2","deceleration_mps2")),"Exact prelaunch profile fields required");prelaunch=new SpeedProfile(p.get("cruise_mps").getAsDouble(),p.get("acceleration_mps2").getAsDouble(),p.get("deceleration_mps2").getAsDouble());}
        require(o.keySet().equals(fields),"Complete explicit continuous profile fields required");
        return new MotionProfile(text(o,"type"),o.get("cruise_mps").getAsDouble(),o.get("acceleration_mps2").getAsDouble(),o.get("deceleration_mps2").getAsDouble(),text(o,"ready_node"),version,prelaunch);
    }
    private static Rotation rotation(JsonArray a){require(a!=null&&a.size()==4,"Measured quaternion required");return new Rotation(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat(),a.get(3).getAsFloat());}
    private static String text(JsonObject o,String key){require(o.has(key)&&o.get(key).isJsonPrimitive()&&o.getAsJsonPrimitive(key).isString(),"Explicit string required: "+key);return o.get(key).getAsString();}
    private static long whole(JsonObject o,String key){require(o.has(key)&&o.getAsJsonPrimitive(key).isNumber(),"Explicit integer required: "+key);return o.get(key).getAsBigDecimal().longValueExact();}
    private static int integer(JsonObject o,String key){return Math.toIntExact(whole(o,key));}
    private static List<String> names(JsonObject o,String key){require(o.has(key)&&o.get(key).isJsonArray(),"Explicit resource/path array required: "+key);var result=new ArrayList<String>();var seen=new HashSet<String>();for(var value:o.getAsJsonArray(key)){String name=identifier(value.getAsString());require(seen.add(name),"Duplicate member: "+key);result.add(name);}return List.copyOf(result);}
    private static <K,V> void unique(Map<K,V> map,K key,V value){require(map.putIfAbsent(key,value)==null,"Duplicate directory member: "+key);}
}
