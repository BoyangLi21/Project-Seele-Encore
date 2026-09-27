package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.FirstBattleClip;
import com.projectseele.entity.FirstBattleSignals;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.nio.file.Files;
import java.nio.file.Path;

/** Compares the actual submitted surface with its authored world points in the native review. */
public final class SachielWrapR14Audit
{
    private static final boolean R40="r31-combat".equals(System.getProperty("projectseele.regionalBuild",""))&&Boolean.getBoolean("projectseele.surfaceAuditR40");
    public static final boolean ENABLED=R40||"r10-firstbattle".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final long RUN=System.currentTimeMillis();
    private static int samples;
    private static float maxXZ,maxY;
    public static void sample(Entity entity,FirstBattleSignals.Actor actor,Matrix4f draw,
                              Vector3f rootLocal,Vector3f authored)
    {
        if(!ENABLED)return;
        var rendered=draw.transformPosition(new Vector3f(rootLocal));
        Vec3 expected=FirstBattleClip.world(actor.firstBattleSignals().spec(entity),new Vec3(authored.x,authored.y,authored.z));
        maxXZ=Math.max(maxXZ,(float)Math.hypot(rendered.x-expected.x,rendered.z-expected.z));maxY=Math.max(maxY,(float)Math.abs(rendered.y-expected.y));samples++;
        if(samples%128==0)
        {
            try
            {
                Path folder=Path.of(R40?"../artifacts/world_combat_r40/native_surface_audit":"../artifacts/world_refinement_r14/native");Files.createDirectories(folder);
                String json="{\"samples\":"+samples+",\"max_xz\":"+maxXZ+",\"max_y\":"+maxY+",\"passed\":"+(maxXZ<.03&&maxY<.12)+"}";
                Files.writeString(folder.resolve("surface_"+RUN+".json"),json);
            }
            catch(Exception e){ProjectSeele.LOGGER.error("R14 surface review output",e);}
        }
    }
    private SachielWrapR14Audit() {}
}
