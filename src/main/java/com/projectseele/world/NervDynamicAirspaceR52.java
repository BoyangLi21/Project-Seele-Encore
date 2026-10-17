package com.projectseele.world;
import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.AABB;

/** Root's bounded permission to instantiate existing32m grid identities.
 * No region is enumerated. Only actual source envelopes produce cell claims. */
public final class NervDynamicAirspaceR52 {
 public record Domain(String id,String dimension,AABB bounds,int maximumStepCells) {}
 private final List<Domain> domains;
 private NervDynamicAirspaceR52(List<Domain> domains){this.domains=List.copyOf(domains);}
 public static NervDynamicAirspaceR52 parse(JsonObject root){
  var domains=new ArrayList<Domain>();var ids=new HashSet<String>();
  if(root.has("space_domains")){
   if(!root.get("space_domains").isJsonArray())throw new IllegalArgumentException("Root dynamic space domains must be an array");
   for(var raw:root.getAsJsonArray("space_domains")){
    if(!raw.isJsonObject())throw new IllegalArgumentException("Explicit Root dynamic domain object required");var o=raw.getAsJsonObject();
    if(!o.keySet().equals(Set.of("id","dimension","bounds","grid_metres","max_step_cells")))throw new IllegalArgumentException("Explicit Root dynamic space-domain fields required");
    String id=text(o,"id"),dimension=text(o,"dimension");
    if(!o.get("bounds").isJsonArray())throw new IllegalArgumentException("Measured Root dynamic bounds required");var a=o.getAsJsonArray("bounds");
    if(a.size()!=6||!ids.add(id)||!id.matches("[A-Za-z0-9_./:-]{1,160}")||!dimension.matches("[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+")||whole(o,"grid_metres")!=32)throw new IllegalArgumentException("Unique Root dynamic32m domain required");
    double[] p=new double[6];for(int i=0;i<6;i++){if(!a.get(i).isJsonPrimitive()||!a.get(i).getAsJsonPrimitive().isNumber())throw new IllegalArgumentException("Measured numeric Root dynamic bounds required");p[i]=a.get(i).getAsDouble();}
    // AABB normalizes reversed endpoints. Validate the authored coordinates
    // before constructing it so a malformed Root authority cannot expand.
    if(!(p[0]<p[3]&&p[1]<p[4]&&p[2]<p[5]))throw new IllegalArgumentException("Strict positive Root dynamic bounds required");
    var b=new AABB(p[0],p[1],p[2],p[3],p[4],p[5]);int max=whole(o,"max_step_cells");
    if(!finite(b)||max<1||max>32768)throw new IllegalArgumentException("Finite bounded Root dynamic SPACE authority required");domains.add(new Domain(id,dimension,b,max));
   }
  }
  return new NervDynamicAirspaceR52(domains);
 }
 private static String text(JsonObject o,String key){var v=o.get(key);if(!v.isJsonPrimitive()||!v.getAsJsonPrimitive().isString())throw new IllegalArgumentException("Explicit Root domain string required: "+key);return v.getAsString();}
 private static int whole(JsonObject o,String key){var v=o.get(key);if(!v.isJsonPrimitive()||!v.getAsJsonPrimitive().isNumber())throw new IllegalArgumentException("Exact Root domain integer required: "+key);try{return v.getAsBigDecimal().intValueExact();}catch(ArithmeticException malformed){throw new IllegalArgumentException("Exact Root domain integer required: "+key,malformed);}}
 private static boolean finite(AABB b){return Double.isFinite(b.minX+b.minY+b.minZ+b.maxX+b.maxY+b.maxZ)&&b.maxX>b.minX&&b.maxY>b.minY&&b.maxZ>b.minZ&&Math.max(Math.abs(b.minX),Math.abs(b.maxX))<=30000000&&Math.max(Math.abs(b.minZ),Math.abs(b.maxZ))<=30000000&&Math.max(Math.abs(b.minY),Math.abs(b.maxY))<=30000000;}
 public List<Domain> domains(){return domains;}
 public int maximumStepCells(){return domains.stream().mapToInt(Domain::maximumStepCells).max().orElse(0);}
 public static String key(int x,int y,int z){return "space/c"+x+"_"+y+"_"+z;}
 public static AABB canonicalBox(String id){if(id==null||!id.matches("space/c-?[0-9]{1,8}_-?[0-9]{1,8}_-?[0-9]{1,8}"))return null;try{var pieces=id.substring(7).split("_");int x=Integer.parseInt(pieces[0]),y=Integer.parseInt(pieces[1]),z=Integer.parseInt(pieces[2]);if(!key(x,y,z).equals(id)||Math.max(Math.max(Math.abs((long)x),Math.abs((long)y)),Math.abs((long)z))>937500)return null;return new AABB(x*32D,y*32D,z*32D,(x+1D)*32,(y+1D)*32,(z+1D)*32);}catch(NumberFormatException invalid){return null;}}
 public NervRouteDirectoryR52.Resource resource(String id){var b=canonicalBox(id);return b!=null&&domains.stream().anyMatch(d->d.bounds().intersects(b))?new NervRouteDirectoryR52.Resource(id,NervRouteDirectoryR52.ResourceKind.SPACE,id):null;}
 public NervRouteNativeR52.Binding binding(String id){var r=resource(id);return r==null?null:new NervRouteNativeR52.Binding(id,id,null,"",List.of(),List.of(canonicalBox(id)),0);}
 /** Static authority may cover shafts between the Root domains. New cells
  * are only legal where each source envelope is fully covered by Root bounds
  * and/or actual already-declared static SPACE, without bridging a gap. */
 public Set<String> required(String dimension,List<AABB> envelopes,Map<String,NervRouteNativeR52.Binding> statics){
  var permitted=new ArrayList<AABB>();int maximum=0;for(var d:domains)if(d.dimension().equals(dimension)){permitted.add(d.bounds());maximum=Math.max(maximum,d.maximumStepCells());}if(permitted.isEmpty())throw new IllegalArgumentException("Root dynamic SPACE domain missing for actual dimension");boolean staticAdded=false;var ids=new HashSet<String>();
  for(var b:envelopes){boolean inside=domains.stream().anyMatch(d->d.dimension().equals(dimension)&&contains(d.bounds(),b));if(!inside&&!staticAdded){for(var binding:statics.values())permitted.addAll(binding.spaces());staticAdded=true;}if(!finite(b)||!inside&&!NervAirspaceCoverageR52.covered(b,permitted))throw new IllegalArgumentException("Actual source sweep exceeds explicit Root dynamic/static SPACE authority: "+b);int x=(int)Math.floor(b.minX/32),X=(int)Math.floor(Math.nextDown(b.maxX)/32),y=(int)Math.floor(b.minY/32),Y=(int)Math.floor(Math.nextDown(b.maxY)/32),z=(int)Math.floor(b.minZ/32),Z=(int)Math.floor(Math.nextDown(b.maxZ)/32);long count=(long)(X-x+1)*(Y-y+1)*(Z-z+1);if(count>maximum)throw new IllegalArgumentException("Dynamic source interval must be segmented; Root step-cell bound exceeded");for(int i=x;i<=X;i++)for(int j=y;j<=Y;j++)for(int k=z;k<=Z;k++){String id=key(i,j,k);if(statics.containsKey(id)||resource(id)!=null)ids.add(id);else throw new IllegalArgumentException("Source requires an unapproved dynamic SPACE cell");if(ids.size()>maximum)throw new IllegalArgumentException("Root dynamic source-step cell bound exceeded");}}
  return Set.copyOf(ids);
 }
 private static boolean contains(AABB a,AABB b){return b.minX>=a.minX&&b.minY>=a.minY&&b.minZ>=a.minZ&&b.maxX<=a.maxX&&b.maxY<=a.maxY&&b.maxZ<=a.maxZ;}
 private static final class ResolvedBindings extends AbstractMap<String,NervRouteNativeR52.Binding>{private final NervDynamicAirspaceR52 authority;private final Map<String,NervRouteNativeR52.Binding> statics;private ResolvedBindings(NervDynamicAirspaceR52 a,Map<String,NervRouteNativeR52.Binding> s){authority=a;statics=Map.copyOf(s);}@Override public NervRouteNativeR52.Binding get(Object key){var b=statics.get(key);return b!=null?b:key instanceof String s?authority.binding(s):null;}@Override public boolean containsKey(Object key){return get(key)!=null;}@Override public Set<Entry<String,NervRouteNativeR52.Binding>> entrySet(){return statics.entrySet();}}
 public Map<String,NervRouteNativeR52.Binding> bindings(Map<String,NervRouteNativeR52.Binding> statics){return new ResolvedBindings(this,statics);}
 public static Map<String,NervRouteNativeR52.Binding> immutableBindings(Map<String,NervRouteNativeR52.Binding> bindings){return bindings instanceof ResolvedBindings?bindings:Map.copyOf(bindings);}
}
