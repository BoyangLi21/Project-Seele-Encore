import com.google.gson.*;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Independent reader, same JOML 1.10.5 float operations as the actual renderer. */
public final class ReplayRiggedSkinFloatR44
{
    static float[] floats(JsonArray a) { float[] v=new float[a.size()]; for(int i=0;i<v.length;i++)v[i]=a.get(i).getAsFloat();return v; }
    static int[] ints(JsonArray a) { int[] v=new int[a.size()];for(int i=0;i<v.length;i++)v[i]=a.get(i).getAsInt();return v; }
    static Quaternionf quaternion(JsonArray a) { float[] q=floats(a);return new Quaternionf(q[0],q[1],q[2],q[3]); }
    static Vector3f referencePoint(float[] input,int i,int[] ids,float[] weights,int j,Quaternionf[] real,Quaternionf[] dual,Matrix4f[] matrices,boolean[] scaled,int rule)
    {
        Vector3f p=new Vector3f(-input[i]/16,input[i+1]/16,input[i+2]/16),work=new Vector3f();boolean hasScale=false;
        for(int k=0;k<4;k++)hasScale|=weights[j+k]>0&&scaled[ids[j+k]];
        if(hasScale){float x=p.x,y=p.y,z=p.z;p.zero();for(int k=0;k<4;k++)if(weights[j+k]>0){matrices[ids[j+k]].transformPosition(work.set(x,y,z));p.fma(weights[j+k],work);}return p;}
        int reference=ids[j];float strongest=0;
        if(rule==1)for(int k=0;k<4;k++)if(weights[j+k]>strongest||weights[j+k]==strongest&&weights[j+k]>0&&ids[j+k]<reference){strongest=weights[j+k];reference=ids[j+k];}
        Quaternionf q=new Quaternionf(0,0,0,0),d=new Quaternionf(0,0,0,0);
        for(int k=0;k<4;k++){float w=weights[j+k];if(w==0)continue;int b=ids[j+k];if((rule==2?q:real[reference]).dot(real[b])<0)w=-w;q.x+=real[b].x*w;q.y+=real[b].y*w;q.z+=real[b].z*w;q.w+=real[b].w*w;d.x+=dual[b].x*w;d.y+=dual[b].y*w;d.z+=dual[b].z*w;d.w+=dual[b].w*w;}
        float length=(float)Math.sqrt(q.lengthSquared());q.mul(1/length);d.mul(1/length);float orthogonal=q.dot(d);
        d.x-=q.x*orthogonal;d.y-=q.y*orthogonal;d.z-=q.z*orthogonal;d.w-=q.w*orthogonal;
        Quaternionf t=new Quaternionf(d).mul(new Quaternionf(q).conjugate());q.transform(p);return p.add(2*t.x,2*t.y,2*t.z);
    }
    public static void main(String[] args) throws Exception
    {
        Map<String,JsonObject> identities=new HashMap<>();JsonArray samples=new JsonArray();
        JsonObject bindingCandidate=args.length>2?JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject():null;
        int count=0,vertices=0,different=0;double maximum=0,maxUlps=0;String worst="";
        try(var reader=Files.newBufferedReader(Path.of(args[0])))
        {
            String line;
            while((line=reader.readLine())!=null)
            {
                var row=JsonParser.parseString(line).getAsJsonObject();String kind=row.get("kind").getAsString();
                if(kind.equals("actual-parsed-weighted-resource")){identities.put(row.get("resource").getAsString(),row);continue;}
                if(!kind.equals("actual-weighted-emit-vertices")||row.get("branch").getAsString().equals("wrap-cache"))continue;
                var identity=identities.get(row.get("resource").getAsString());if(identity==null)throw new IllegalArgumentException("No actual decoded resource");
                float[] input=floats(identity.getAsJsonArray("decoded_vertices")),weights=floats(identity.getAsJsonArray("parsed_weights"));int[] ids=ints(identity.getAsJsonArray("parsed_indices"));
                if(bindingCandidate!=null)
                {
                    float[] geometry=floats(bindingCandidate.getAsJsonObject("parts").getAsJsonObject("root").getAsJsonArray("vertices"));
                    if(!Arrays.equals(input,geometry))throw new IllegalArgumentException("Candidate changed actual decoded geometry");
                    weights=floats(bindingCandidate.getAsJsonObject("skin").getAsJsonArray("weights"));ids=ints(bindingCandidate.getAsJsonObject("skin").getAsJsonArray("indices"));
                }
                var palette=row.getAsJsonArray("actual_palette");int n=palette.size();Matrix4f[] matrices=new Matrix4f[n];Quaternionf[] real=new Quaternionf[n],dual=new Quaternionf[n];boolean[] scaled=new boolean[n];
                for(int i=0;i<n;i++)
                {
                    var p=palette.get(i).getAsJsonObject();matrices[i]=new Matrix4f().set(floats(p.getAsJsonArray("actual_root_relative_matrix_column_major")));
                    real[i]=quaternion(p.getAsJsonArray("actual_real_quaternion_xyzw"));dual[i]=quaternion(p.getAsJsonArray("actual_dual_quaternion_xyzw"));scaled[i]=p.get("scaled_lbs_branch").getAsBoolean();
                }
                Matrix4f world=new Matrix4f().set(floats(row.getAsJsonArray("actual_emit_to_world_matrix_column_major")));
                Vector3f lift=new Vector3f();if(row.has("actual_ground_support_translation_emit_xyz")){float[] v=floats(row.getAsJsonArray("actual_ground_support_translation_emit_xyz"));lift.set(v[0],v[1],v[2]);}
                float[] actual=floats(row.getAsJsonArray("vertices_world_xyz"));float[] localActual=row.has("vertices_emit_xyz")?floats(row.getAsJsonArray("vertices_emit_xyz")):null;
                Quaternionf q=new Quaternionf(),d=new Quaternionf(),translation=new Quaternionf(),conjugate=new Quaternionf();Vector3f point=new Vector3f(),work=new Vector3f();double localMax=0,sampleMax=0,sampleUlps=0;int sampleDifferent=0;
                boolean dominant=row.get("dominant_review").getAsBoolean(),running=row.has("running_sum_review")&&row.get("running_sum_review").getAsBoolean();double[] ruleLocal=new double[3],ruleWorld=new double[3];int[] ruleWorst=new int[3];
                for(int vertex=0;vertex<input.length/8;vertex++)
                {
                    int i=vertex*8,j=vertex*4;point.set(-input[i]/16,input[i+1]/16,input[i+2]/16);
                    boolean hasScale=false;for(int k=0;k<4;k++)hasScale|=weights[j+k]>0&&scaled[ids[j+k]];
                    if(hasScale)
                    {
                        float x=point.x,y=point.y,z=point.z;point.zero();
                        for(int k=0;k<4;k++)if(weights[j+k]>0){matrices[ids[j+k]].transformPosition(work.set(x,y,z));point.fma(weights[j+k],work);}
                    }
                    else
                    {
                        int reference=ids[j];float strongest=0;
                        if(dominant)for(int k=0;k<4;k++)if(weights[j+k]>strongest||weights[j+k]==strongest&&weights[j+k]>0&&ids[j+k]<reference){strongest=weights[j+k];reference=ids[j+k];}
                        q.set(0,0,0,0);d.set(0,0,0,0);
                        for(int k=0;k<4;k++)
                        {
                            float weight=weights[j+k];if(weight==0)continue;int b=ids[j+k];if((running?q:real[reference]).dot(real[b])<0)weight=-weight;
                            q.x+=real[b].x*weight;q.y+=real[b].y*weight;q.z+=real[b].z*weight;q.w+=real[b].w*weight;
                            d.x+=dual[b].x*weight;d.y+=dual[b].y*weight;d.z+=dual[b].z*weight;d.w+=dual[b].w*weight;
                        }
                        float length=(float)Math.sqrt(q.lengthSquared());q.mul(1/length);d.mul(1/length);float orthogonal=q.dot(d);
                        d.x-=q.x*orthogonal;d.y-=q.y*orthogonal;d.z-=q.z*orthogonal;d.w-=q.w*orthogonal;
                        translation.set(d).mul(conjugate.set(q).conjugate());q.transform(point);point.add(2*translation.x,2*translation.y,2*translation.z);
                    }
                    point.add(lift);
                    if(localActual!=null){double dx=point.x-localActual[vertex*3],dy=point.y-localActual[vertex*3+1],dz=point.z-localActual[vertex*3+2];localMax=Math.max(localMax,Math.sqrt(dx*dx+dy*dy+dz*dz));}
                    Vector3f emitLocal=new Vector3f(point);world.transformPosition(point);double squared=0;boolean changed=false;
                    for(int rule=0;rule<3;rule++)
                    {
                        Vector3f candidate=referencePoint(input,i,ids,weights,j,real,dual,matrices,scaled,rule).add(lift);
                        double localError=candidate.distance(emitLocal);world.transformPosition(candidate);double worldError=candidate.distance(point);
                        if(localError>ruleLocal[rule]){ruleLocal[rule]=localError;ruleWorst[rule]=vertex;}ruleWorld[rule]=Math.max(ruleWorld[rule],worldError);
                    }
                    for(int axis=0;axis<3;axis++)
                    {
                        float expected=actual[vertex*3+axis],computed=point.get(axis);double error=(double)computed-expected;squared+=error*error;
                        changed|=Float.floatToIntBits(expected)!=Float.floatToIntBits(computed);sampleUlps=Math.max(sampleUlps,Math.abs(error)/Math.ulp(expected));
                    }
                    if(changed)sampleDifferent++;double error=Math.sqrt(squared);
                    if(error>maximum){maximum=error;worst=row.get("frame")+":"+vertex+" emit="+emitLocal+" world="+point;}
                    sampleMax=Math.max(sampleMax,error);vertices++;
                }
                count++;different+=sampleDifferent;maxUlps=Math.max(maxUlps,sampleUlps);
                JsonObject result=new JsonObject();result.add("frame",row.get("frame"));result.addProperty("world_max_error_blocks",sampleMax);result.addProperty("maximum_world_component_ulps",sampleUlps);result.addProperty("non_bit_identical_vertices",sampleDifferent);result.addProperty("local_emit_available",localActual!=null);if(localActual!=null)result.addProperty("local_emit_max_error",localMax);
                JsonArray comparisons=new JsonArray();String[] rules={"first_slot","dominant_stable","running_sum_capture_order"};
                for(int rule=0;rule<3;rule++){JsonObject c=new JsonObject();c.addProperty("rule",rules[rule]);c.addProperty("same_native_palette_local_max_delta",ruleLocal[rule]);c.addProperty("same_native_palette_world_max_delta_blocks",ruleWorld[rule]);c.addProperty("worst_vertex",ruleWorst[rule]);JsonArray bones=new JsonArray(),ws=new JsonArray();for(int slot=0;slot<4;slot++){bones.add(identity.getAsJsonArray("bones").get(ids[ruleWorst[rule]*4+slot]).getAsString());ws.add(weights[ruleWorst[rule]*4+slot]);}c.add("actual_decoded_bones",bones);c.add("actual_decoded_weights",ws);comparisons.add(c);}result.add("same_pose_reference_comparisons",comparisons);samples.add(result);
            }
        }
        JsonObject result=new JsonObject();result.addProperty("actual_draw_samples",count);result.addProperty("actual_vertices_replayed",vertices);result.addProperty(bindingCandidate==null?"maximum_same_float32_joml_world_error_blocks":"counterfactual_binding_change_from_actual_baseline_blocks",maximum);result.addProperty("maximum_world_component_ulps",maxUlps);result.addProperty("non_bit_identical_vertices",different);result.addProperty("worst",worst);result.addProperty("bit_identical_world_vertices",different==0);result.addProperty("counterfactual_binding_candidate",bindingCandidate!=null);result.addProperty("scope",bindingCandidate==null?"Standalone streaming actual parsed resource/palette/emit witness, exact renderer JOML float32 operation order; no Minecraft or Gradle run, no artistic approval":"Candidate binding only on actual A decoded unchanged geometry and each of its actual palettes. Observed vertices still belong to original A; not a native C capture or numerical mismatch pass/fail.");result.add("samples",samples);Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));result.remove("samples");System.out.println(result);
    }
}
