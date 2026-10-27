import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.physics.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.ZipFile;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** The two known Unit01 standing-to-crouch failures, using saved native assets.
 * No world, entities, dense phase grid or resource digest comparison. */
public final class AuditStandingKneeMarginR53
{
    private static final int VARIANT=1;
    private static final List<String> LEGS=List.of("leg_l","shin_l","foot_l","leg_r","shin_r","foot_r");
    private final Object data;
    private final Method sample;
    private final CombatBodyProfiles.Profile profile;
    private final float idleDuration;
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static JsonObject read(Path p)throws Exception{return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static double angle(Quaternionf a,Quaternionf b)
    {
        double dot=(double)a.x*b.x+(double)a.y*b.y+(double)a.z*b.z+(double)a.w*b.w;
        double aa=(double)a.x*a.x+(double)a.y*a.y+(double)a.z*a.z+(double)a.w*a.w;
        double bb=(double)b.x*b.x+(double)b.y*b.y+(double)b.z*b.z+(double)b.w*b.w;
        return Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(dot)/Math.sqrt(aa*bb))));
    }
    @SuppressWarnings("unchecked")
    private AuditStandingKneeMarginR53(Path client)throws Exception
    {
        Path directory=client.resolve("projectseele-local-maps");
        var all=read(directory.resolve("eva_body_r44.json"));var physics=read(directory.resolve("articulated_bodies_r35.json"));
        var motion=all.getAsJsonObject("motion");String[] names=new Gson().fromJson(motion.get("bones"),String[].class);
        var reader=EvaBodyPose.class.getDeclaredMethod("readCombatClipsR31",JsonObject.class,String[].class);reader.setAccessible(true);
        var clips=(Map<String,Object>)reader.invoke(null,motion,names);var rig=new LinkedHashMap<String,EvaBodyPose.Bone>();
        for(var element:all.getAsJsonObject("rigs").getAsJsonArray(""+VARIANT))
        {
            var row=element.getAsJsonObject();String name=row.get("name").getAsString();
            String parent=row.has("parent")&&!row.get("parent").isJsonNull()?row.get("parent").getAsString():null;
            var bind=row.has("rotation")?vector(row.getAsJsonArray("rotation")):row.has("bindRotationDegrees")?vector(row.getAsJsonArray("bindRotationDegrees")):new Vector3f();bind.mul((float)Math.PI/180);
            rig.put(name,new EvaBodyPose.Bone(name,parent,vector(row.getAsJsonArray("pivot")).mul(-1,1,1).div(16),new Quaternionf().rotationZYX(bind.z,-bind.y,-bind.x)));
        }
        var overrides=new HashMap<String,Object>();
        for(String file:List.of("eva_combat_capture_r31.json","eva_gameplay_r44_"+VARIANT+".json"))
            if(Files.isRegularFile(directory.resolve(file)))overrides.putAll((Map<String,Object>)reader.invoke(null,read(directory.resolve(file)),names));
        overrides.putAll((Map<String,Object>)reader.invoke(null,all.getAsJsonObject("stance_clips_by_rig").getAsJsonObject(""+VARIANT),names));
        var idle=overrides.getOrDefault("idle",clips.get("idle"));var duration=idle.getClass().getDeclaredMethod("duration");duration.setAccessible(true);idleDuration=(Float)duration.invoke(idle);
        profile=new CombatBodyProfiles.Profile("standing-knee-margin",physics.getAsJsonObject("models").getAsJsonObject(""+VARIANT),rig,null);
        Class<?> type=Class.forName("com.projectseele.entity.EvaBodyPose$Data");var constructor=type.getDeclaredConstructors()[0];constructor.setAccessible(true);
        data=constructor.newInstance(names,Map.of(),clips,Map.of(VARIANT,rig),Map.of(),new JsonObject(),new JsonObject(),new JsonObject(),Map.of(),Map.of(),Map.of(),Map.of(VARIANT,overrides),all.getAsJsonObject("locomotion_contract_r43"));
        sample=EvaBodyPose.class.getDeclaredMethod("ordinaryClipBaseR52",type,int.class,float.class,float.class,float.class,float.class,float.class,float.class,float.class,float.class,boolean.class);sample.setAccessible(true);
        // Read the installed shoe vertices directly, without loading the
        // production resource-admission/digest path into this numerical fixture.
        JsonObject shoes;
        try(var jar=new ZipFile(client.resolve("mods/projectseele-0.1.0-all.jar").toFile());var stream=jar.getInputStream(jar.getEntry("assets/projectseele/eva/ordinary_standing_support_hulls_r52.json")))
        {shoes=JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();}
        var parts=new HashMap<String,Vector3f[]>();var row=shoes.getAsJsonObject("rigs").getAsJsonObject(""+VARIANT).getAsJsonObject("parts");
        for(String side:List.of("l","r")){String name="foot_"+side;var points=new ArrayList<Vector3f>();for(var p:row.getAsJsonArray(name))points.add(vector(p.getAsJsonArray()));parts.put(name,points.toArray(Vector3f[]::new));}
        var field=EvaOrdinaryStandingSupportR52.class.getDeclaredField("SOURCES");field.setAccessible(true);((Map<Integer,Map<String,Vector3f[]>>)field.get(null)).put(VARIANT,Map.copyOf(parts));
    }
    private EvaBodyPose.Sample sample(boolean rifle,float stance,double tick)throws Exception
    {
        float idle=(float)((tick/20/idleDuration)%1);
        var pose=(EvaBodyPose.Sample)sample.invoke(null,data,VARIANT,0F,idle,0F,0F,Math.min(1,stance),Math.max(0,(stance-1)/2),stance,0F,rifle);
        EvaBodyPose.preserveJointCentres(pose);AnatomicalLimbConstraints.apply(pose,profile);return pose;
    }
    private Map<String,Object> sequence(boolean rifle)throws Exception
    {
        var phases=new ArrayList<Float>();float phase=0,velocity=0;phases.add(phase);
        for(int tick=0;tick<80&&(phase!=1||velocity!=0);tick++)
        {var next=EvaStanceTimingR53.advance(phase,1,velocity);phase=next.phase();velocity=next.velocity();phases.add(phase);}
        if(phase!=1||velocity!=0)throw new AssertionError("Unsettled stance clock");
        EvaBodyPose.Sample prior=null;double maximum=0,soleError=0,drop=0,knownWindow=0;float worstFrom=0,worstTo=0,priorPhase=0;String bone="";int frames=0;
        var byBone=new LinkedHashMap<String,Double>();double knownPhase=rifle?.301:.388;
        for(double time=0;time<=(phases.size()-1)/20D;time+=.029292199999872537)
        {
            double tick=time*20;int i=(int)tick;phase=phases.get(i)+(phases.get(Math.min(i+1,phases.size()-1))-phases.get(i))*(float)(tick-i);
            var pose=sample(rifle,phase,6454627+tick);float before=pose.positions.get("root").y;
            EvaOrdinaryStandingSupportR52.apply(VARIANT,pose,1,new float[]{0,0},profile);
            drop=Math.max(drop,(before-pose.positions.get("root").y)*EvaScale.RENDER_SCALE);
            for(String side:List.of("l","r"))soleError=Math.max(soleError,Math.abs(EvaOrdinaryStandingSupportR52.lowest(VARIANT,pose,side).y-.006F)*EvaScale.RENDER_SCALE);
            if(prior!=null)for(String name:LEGS)
            {
                double step=angle(prior.rotations.get(name),pose.rotations.get(name));byBone.merge(name,step,Math::max);
                if(name.startsWith("shin_")&&phase>=knownPhase-.03&&priorPhase<=knownPhase+.03)knownWindow=Math.max(knownWindow,step);
                if(step>maximum){maximum=step;bone=name;worstFrom=priorPhase;worstTo=phase;}
            }
            prior=pose;priorPhase=phase;frames++;
        }
        var result=new LinkedHashMap<String,Object>();result.put("rifle",rifle);result.put("frames",frames);result.put("maximum_leg_step_degrees",maximum);
        result.put("worst",Map.of("bone",bone,"from_phase",worstFrom,"to_phase",worstTo));result.put("maximum_sole_error_blocks",soleError);result.put("maximum_local_pelvis_drop_blocks",drop);
        result.put("maximum_step_by_bone_degrees",byBone);result.put("known_singularity_window_shin_step_degrees",knownWindow);
        return result;
    }
    public static void main(String[] args)throws Exception
    {
        var audit=new AuditStandingKneeMarginR53(Path.of(args[0]));
        if(args.length>2&&args[2].equals("rifle-foot")){audit.rifleFootWindow(Path.of(args[1]));return;}
        var rows=List.of(audit.sequence(false),audit.sequence(true));
        var result=Map.of("variant",VARIANT,"frame_interval_ms",29.292199999872537,"sequences",rows,
                "limits","Two known flat-floor Unit01 0-to-1 sequences only; excludes native client signal clock, terrain, combat layers and visual acceptance.");
        String json=new GsonBuilder().setPrettyPrinting().create().toJson(result);Files.writeString(Path.of(args[1]),json);System.out.println(json);
    }
    private void rifleFootWindow(Path output)throws Exception
    {
        var phases=new ArrayList<Float>();float phase=0,velocity=0;phases.add(phase);
        for(int tick=0;tick<80&&(phase!=1||velocity!=0);tick++)
        {var next=EvaStanceTimingR53.advance(phase,1,velocity);phase=next.phase();velocity=next.velocity();phases.add(phase);}
        var rows=new ArrayList<Object>();var prior=new HashMap<String,Quaternionf>();
        var support=new EvaOrdinaryStandingSupportR52.MotionMemory(0);
        var tracker=new EvaOrdinaryStandingSupportR52.FootOrientation();Quaternionf lastDesired=null,lastShown=null;double lastTick=0,repeatedStep=0;
        for(int frame=0;frame<60;frame++)
        {
            double tick=frame*.029292199999872537*20;int i=(int)tick;if(i>=phases.size()-1)break;
            phase=phases.get(i)+(phases.get(i+1)-phases.get(i))*(float)(tick-i);
            if(phase<.48F||phase>.60F)continue;
            var row=new LinkedHashMap<String,Object>();row.put("phase",phase);row.put("frame",frame);
            float idle=(float)(((6454627+tick)/20/idleDuration)%1);
            var pose=(EvaBodyPose.Sample)sample.invoke(null,data,VARIANT,0F,idle,0F,0F,phase,0F,phase,0F,true);
            trace(row,prior,"source",pose);EvaBodyPose.preserveJointCentres(pose);AnatomicalLimbConstraints.apply(pose,profile);
            var euler=pose.matrix("foot_r").getUnnormalizedRotation(new Quaternionf()).normalize().getEulerAnglesXYZ(new Vector3f()).mul(180F/(float)Math.PI);row.put("authored_right_shoe_euler_degrees",List.of(euler.x,euler.y,euler.z));
            lastDesired=pose.matrix("foot_r").getUnnormalizedRotation(new Quaternionf()).normalize();lastShown=tracker.follow(lastDesired,tick);lastTick=tick;
            repeatedStep=Math.max(repeatedStep,angle(lastShown,tracker.follow(lastDesired,tick)));
            trace(row,prior,"anatomical",pose);float before=pose.positions.get("root").y;
            support.orientFeet(pose,tick,1);
            EvaOrdinaryStandingSupportR52.apply(VARIANT,pose,1,new float[]{0,0},profile);trace(row,prior,"supported",pose);
            row.put("pelvis_drop_blocks",(before-pose.positions.get("root").y)*EvaScale.RENDER_SCALE);
            for(String side:List.of("l","r"))row.put("sole_error_"+side,Math.abs(EvaOrdinaryStandingSupportR52.lowest(VARIANT,pose,side).y-.006F)*EvaScale.RENDER_SCALE);
            rows.add(row);
        }
        double lag=angle(lastShown,lastDesired);for(int i=1;i<=20;i++)lastShown=tracker.follow(lastDesired,lastTick+i);
        double heldError=angle(lastShown,lastDesired);if(repeatedStep>1e-4||heldError>.01)throw new AssertionError("Foot orientation clock/convergence failed");
        String json=new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("frame_interval_ms",29.292199999872537,"frames",rows,
                "same_clock_extra_rotation_degrees",repeatedStep,"last_frame_following_error_degrees",lag,"held_target_error_after_one_second_degrees",heldError,
                "limits","Only the known Unit01 rifle .48-.60 flat-floor interval plus the last target held for one second; no native/render or other action coverage."));
        Files.writeString(output,json);System.out.println(json);
    }
    private static void trace(Map<String,Object> row,Map<String,Quaternionf> prior,String stage,EvaBodyPose.Sample pose)
    {
        var steps=new LinkedHashMap<String,Double>();
        for(String name:LEGS)for(boolean world:new boolean[]{false,true})
        {
            String key=name+(world?"_world":"_local"),id=stage+key;
            var q=world?pose.matrix(name).getUnnormalizedRotation(new Quaternionf()).normalize():new Quaternionf(pose.rotations.get(name));
            var previous=prior.put(id,q);if(previous!=null)steps.put(key,angle(previous,q));
        }
        row.put(stage,steps);
    }
}
