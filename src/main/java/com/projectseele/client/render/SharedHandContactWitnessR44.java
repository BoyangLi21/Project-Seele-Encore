package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.visual.CombatR31Review;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import java.nio.file.*;
import java.util.*;

/** Review-only actual mesh submission, distinct from the backend damage sweep. */
public final class SharedHandContactWitnessR44
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r44SharedContactWitness");
    private static final JsonArray ROWS=new JsonArray();
    private static long frame=Long.MIN_VALUE,lastTick=Long.MIN_VALUE;
    private static int samples;
    private static EvaUnit01Entity actor;
    private static float partial;
    private static final Map<String,Hand> HANDS=new HashMap<>();
    private static final Map<Integer,Target> TARGETS=new HashMap<>();
    private static final Map<String,Vector3f> PREVIOUS=new HashMap<>();
    private static final class Hand
    {
        Vector3f reference,point;String part="",referenceSource="";int vertex=-1,vertices,parts;
        float error=Float.POSITIVE_INFINITY;Matrix4f world;
    }
    private static final class Target
    {
        LivingEntity entity;final List<float[]> triangles=new ArrayList<>();final Vector3f[] pending={new Vector3f(),new Vector3f(),new Vector3f()};
        int vertices,emittedTriangles,nearTriangles;Matrix4f world;String branch="";
    }
    private static boolean active()
    {return ENABLED&&CombatR31Review.ENABLED&&!CombatR31Review.done&&!ShaderShadowPassR44.active();}
    private static boolean select(EvaUnit01Entity eva,float value)
    {
        if(!active()||eva.getId()!=CombatR31Review.evaId||!EvaGameplayMotionR32.sharedBody(eva,value))return false;
        long current=FirstBattleSignals.clientFrameTime();
        if(current!=frame)
        {
            finishFrame();frame=current;actor=eva;partial=value;HANDS.clear();TARGETS.clear();
        }
        if(actor==null){actor=eva;partial=value;}
        int gap=Math.max(1,Integer.getInteger("projectseele.r44SharedContactTickGap",2));
        return samples<Integer.getInteger("projectseele.r44SharedContactFrames",180)
                &&(lastTick==Long.MIN_VALUE||eva.level().getGameTime()-lastTick>=gap);
    }
    public static void submitted(EvaUnit01Entity eva,GeoBone bone,float[] values,int stride,float px,float py,float pz,Matrix4f world,float value)
    {
        String name=bone.getName();
        if(!(name.startsWith("hand_")||name.startsWith("finger_"))||!select(eva,value))return;
        String side=name.endsWith("_l")?"l":"r";Hand hand=HANDS.computeIfAbsent(side,key->new Hand());
        if(name.equals("hand_"+side))
        {
            var profile=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(eva));String clip=EvaGameplayMotionR32.resolvedGroundClipR44(eva,value);
            var c=profile==null?null:profile.getAsJsonObject("clips").getAsJsonObject("r32_"+clip);
            if(c!=null&&c.has("contact_bone")&&c.get("contact_bone").getAsString().equals(name)&&c.has("contact_point_model"))
            {
                var p=c.getAsJsonArray("contact_point_model");hand.reference=world.transformPosition(new Vector3f(-p.get(0).getAsFloat()/16,p.get(1).getAsFloat()/16,p.get(2).getAsFloat()/16));
                hand.referenceSource="declared current action contact point through actual submitted hand matrix";
            }
            hand.world=new Matrix4f(world);
        }
        if(hand.reference==null&&PREVIOUS.get(side)!=null){hand.reference=new Vector3f(PREVIOUS.get(side));hand.referenceSource="previous sampled actual vertex used as ROI only; current matching vertex is actual but its knuckle identity is unverified";}
        if(hand.reference==null)return;
        hand.parts++;hand.vertices+=values.length/stride;
        for(int at=0;at+stride<=values.length;at+=stride)
        {
            Vector3f point=world.transformPosition(new Vector3f(-(values[at]+px)/16,(values[at+1]+py)/16,(values[at+2]+pz)/16));
            float error=point.distanceSquared(hand.reference);
            if(error<hand.error){hand.error=error;hand.point=point;hand.part=name;hand.vertex=at/stride;}
        }
    }
    public static void targetVertex(LivingEntity entity,Vector3f submitted,Matrix4f world,String branch)
    {
        if(!active()||world==null||entity.getId()!=CombatR31Review.angelId||samples>=Integer.getInteger("projectseele.r44SharedContactFrames",180))return;
        long current=FirstBattleSignals.clientFrameTime();
        if(current!=frame){finishFrame();frame=current;actor=null;HANDS.clear();TARGETS.clear();}
        Target target=TARGETS.computeIfAbsent(entity.getId(),key->new Target());target.entity=entity;target.world=new Matrix4f(world);target.branch=branch;
        world.transformPosition(new Vector3f(submitted),target.pending[target.vertices%3]);target.vertices++;
        if(target.vertices%3!=0)return;target.emittedTriangles++;
        boolean near=false;float radius=Math.max(2,Float.parseFloat(System.getProperty("projectseele.r44SharedContactRadius","12")));
        for(Hand hand:HANDS.values())if(hand.reference!=null)for(Vector3f point:target.pending)near|=point.distanceSquared(hand.reference)<=radius*radius;
        if(!near)for(Vector3f previous:PREVIOUS.values())for(Vector3f point:target.pending)near|=point.distanceSquared(previous)<=radius*radius;
        if(!near)return;target.nearTriangles++;
        int cap=Math.max(16,Integer.getInteger("projectseele.r44SharedTargetTriangleCap",512));
        if(target.triangles.size()>=cap)return;
        float[] triangle=new float[9];for(int i=0;i<3;i++){triangle[i*3]=target.pending[i].x;triangle[i*3+1]=target.pending[i].y;triangle[i*3+2]=target.pending[i].z;}target.triangles.add(triangle);
    }
    private static Vector3f closest(Vector3f p,float[] t)
    {
        Vector3f a=new Vector3f(t[0],t[1],t[2]),b=new Vector3f(t[3],t[4],t[5]),c=new Vector3f(t[6],t[7],t[8]);
        Vector3f ab=new Vector3f(b).sub(a),ac=new Vector3f(c).sub(a),ap=new Vector3f(p).sub(a);
        float d1=ab.dot(ap),d2=ac.dot(ap);if(d1<=0&&d2<=0)return a;
        Vector3f bp=new Vector3f(p).sub(b);float d3=ab.dot(bp),d4=ac.dot(bp);if(d3>=0&&d4<=d3)return b;
        float vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0)return a.fma(d1/(d1-d3),ab);
        Vector3f cp=new Vector3f(p).sub(c);float d5=ab.dot(cp),d6=ac.dot(cp);if(d6>=0&&d5<=d6)return c;
        float vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0)return a.fma(d2/(d2-d6),ac);
        float va=d3*d6-d5*d4;if(va<=0&&d4-d3>=0&&d5-d6>=0)return b.fma((d4-d3)/((d4-d3)+(d5-d6)),new Vector3f(c).sub(b));
        float sum=va+vb+vc;if(Math.abs(sum)<1e-12F)return a;
        return a.fma(vb/sum,ab).fma(vc/sum,ac);
    }
    public static void finishFrame()
    {
        if(actor==null||HANDS.isEmpty())return;
        JsonObject row=new JsonObject();row.addProperty("frame_ns",frame);row.addProperty("world_tick",actor.level().getGameTime());
        row.addProperty("review_stage",CombatR31Review.stageName);row.addProperty("review_tick",CombatR31Review.stageTicks);
        row.addProperty("actor_uuid",actor.getStringUUID());row.addProperty("entity_world_yaw",actor.getYRot());row.addProperty("body_world_yaw",actor.yBodyRot);
        row.addProperty("clip",EvaGameplayMotionR32.resolvedGroundClipR44(actor,partial));row.addProperty("phase",EvaGameplayMotionR32.activeGroundPhase(actor,partial));row.addProperty("stance",actor.rifleStanceLevel(partial));
        var actualChoice=EvaGameplayMotionR32.actualPoseChoiceReviewR44(actor,partial);
        row.addProperty("actual_pose_choice_available",actualChoice!=null);if(actualChoice!=null)row.add("actual_pose_choice",actualChoice);
        row.add("entity_world_position",vector(actor.position().toVector3f()));JsonArray hands=new JsonArray();
        for(var entry:HANDS.entrySet())
        {
            Hand h=entry.getValue();if(h.point==null)continue;JsonObject record=new JsonObject();record.addProperty("side",entry.getKey());record.addProperty("actual_submitted_part",h.part);record.addProperty("actual_vertex_index",h.vertex);
            record.add("actual_knuckle_nearest_mesh_vertex_world",vector(h.point));record.add("declared_contact_reference_world",vector(h.reference));record.addProperty("reference_to_actual_vertex_distance",Math.sqrt(h.error));
            record.addProperty("reference_source",h.referenceSource);
            record.addProperty("inspected_hand_vertices",h.vertices);record.addProperty("inspected_hand_parts",h.parts);if(h.world!=null)record.add("actual_hand_mesh_to_world_column_major",matrix(h.world));
            Vector3f nearest=null;Target chosen=null;double distance=Double.POSITIVE_INFINITY;float[] surface=null;
            for(Target target:TARGETS.values())for(float[] triangle:target.triangles)
            {Vector3f point=closest(h.point,triangle);double delta=point.distanceSquared(h.point);if(delta<distance){distance=delta;nearest=point;chosen=target;surface=triangle;}}
            record.addProperty("same_frame_actual_target_surface_sampled",chosen!=null);
            if(chosen!=null)
            {
                record.addProperty("target_uuid",chosen.entity.getStringUUID());record.addProperty("target_entity_id",chosen.entity.getId());record.addProperty("target_world_yaw",chosen.entity.getYRot());record.addProperty("target_branch",chosen.branch);
                record.add("actual_target_surface_world",vector(nearest));record.addProperty("actual_mesh_surface_distance",Math.sqrt(distance));record.addProperty("emitted_target_triangles",chosen.emittedTriangles);record.addProperty("near_region_target_triangles",chosen.nearTriangles);record.addProperty("retained_target_triangles",chosen.triangles.size());
                record.addProperty("target_triangle_sampling_capped",chosen.nearTriangles>chosen.triangles.size());JsonArray tri=new JsonArray();for(float value:surface)tri.add(value);record.add("nearest_actual_target_triangle_world_xyz",tri);record.add("actual_target_emit_to_world_column_major",matrix(chosen.world));
            }
            record.addProperty("scope","Actual same-frame submitted hand vertex and limited nearby target draw triangles. Visual proximity is distinct from server hit/damage. Missing/capped/unretained triangles cannot prove no intersection.");hands.add(record);PREVIOUS.put(entry.getKey(),new Vector3f(h.point));
        }
        if(hands.size()>0){row.add("hands",hands);ROWS.add(row);samples++;lastTick=actor.level().getGameTime();}
        actor=null;HANDS.clear();TARGETS.clear();
    }
    public static void write(Path folder)throws java.io.IOException
    {
        if(!ENABLED)return;finishFrame();JsonObject report=new JsonObject();report.addProperty("review_only",true);report.addProperty("sampled_frames",samples);report.addProperty("damage_inferred_from_visual_distance",false);report.add("frames",ROWS);
        Files.writeString(folder.resolve("shared_actual_hand_contacts_r44.json"),new Gson().toJson(report));
    }
    private static JsonArray vector(Vector3f p){JsonArray a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;}
    private static JsonArray matrix(Matrix4f p){JsonArray a=new JsonArray();for(float value:p.get(new float[16]))a.add(value);return a;}
    private SharedHandContactWitnessR44(){}
}
