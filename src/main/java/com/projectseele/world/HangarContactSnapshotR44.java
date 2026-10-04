package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Vector3f;
import java.nio.file.Files;
import java.util.*;

/** Opt-in read-only body/shoulder/socket facts for the actual parked original fleet. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class HangarContactSnapshotR44
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44HangarContacts");
    private static boolean written;private static int age;
    private static JsonArray vector(double x,double y,double z){var a=new JsonArray();a.add(x);a.add(y);a.add(z);return a;}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||written||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();var world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))throw new IllegalStateException("Contact snapshot refuses non-review world");
        if(++age<160)return;var level=server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        try
        {
            var results=new JsonArray();
            for(var entity:level.getAllEntities())
            {
                if(!(entity instanceof EvaUnit01Entity unit)||unit.isExperimentalUnit())continue;
                int variant=unit.getUnitVariant();if(variant<0||variant>2)continue;
                int cx=new int[]{-12,30,72}[variant];
                if(Math.abs(unit.getX()-(cx+.5))>.05||Math.abs(unit.getY()+442)>.05||Math.abs(unit.getZ()+239.5)>.05)continue;
                var pose=EvaBodyPose.sample(unit,1);var row=new JsonObject();row.addProperty("variant",variant);row.addProperty("uuid",unit.getUUID().toString());row.addProperty("yaw",unit.getYRot());
                row.add("origin",vector(unit.getX(),unit.getY(),unit.getZ()));
                var fleet = EvaLogisticsDirector.status(level, variant);
                row.addProperty("s20_phase",fleet.phase());row.addProperty("lcl_layers",fleet.lclLayers());row.addProperty("phase_ticks",fleet.ticks());
                row.addProperty("carrier_rise",unit.carrierRiseProgress(1F));row.addProperty("launch_phase",unit.getLaunchPhase());
                row.addProperty("active_carrier_motion",unit.hasActiveCarrierMotion());row.addProperty("recovery_rack",unit.recoveryRackR39());
                var joints=new JsonArray();
                for(var b:pose.rig.values())
                {
                    String name=b.name();if(!name.startsWith("arm_")&&!name.contains("shoulder")&&!name.contains("pylon"))continue;
                    Vector3f p=pose.matrix(name).transformPosition(new Vector3f(b.pivot())).mul(EvaScale.RENDER_SCALE);
                    var joint=new JsonObject();joint.addProperty("bone",name);joint.add("local",vector(p.x,p.y,p.z));joints.add(joint);
                }
                row.add("measured_joint_points_local",joints);
                var hulls=new JsonArray();
                for(var b:EvaBodyPose.posedCarrierHulls(unit,pose))
                {var box=new JsonObject();box.add("lo",vector(b.minX,b.minY,b.minZ));box.add("hi",vector(b.maxX,b.maxY,b.maxZ));hulls.add(box);}
                row.add("complete_part_hulls_local",hulls);
                var socket=EntryPlugKinematics.socketTransform(unit);row.add("socket_world",vector(socket.translation().x,socket.translation().y,socket.translation().z));
                results.add(row);
            }
            if(results.size()!=3){if(age<600)return;throw new IllegalStateException("Read-only contact snapshot requires all three actual parked originals, found "+results.size());}
            var mechanics = new JsonArray();
            for (var entity : level.getAllEntities())
            {
                if (!(entity instanceof NervCarrierPlatformEntity visual)
                        || !(visual.isRestraintGantry() || visual.isPlugCrane())) continue;
                var row = new JsonObject();row.addProperty("uuid", visual.getUUID().toString());row.addProperty("entity_id", visual.getId());
                row.addProperty("variant", visual.getUnitVariant());row.addProperty("kind", visual.isRestraintGantry() ? "fixed_wet_gantry" : "plug_crane");
                row.add("position", vector(visual.getX(),visual.getY(),visual.getZ()));
                row.addProperty("restraint_progress",visual.getRestraintProgress());
                row.addProperty("alive",visual.isAlive());row.addProperty("ticks",visual.tickCount);
                row.addProperty("entity_ticking_chunk",level.isPositionEntityTicking(visual.blockPosition()));
                row.addProperty("actual_server_box",visual.getBoundingBox().toString());mechanics.add(row);
            }
            var result=new JsonObject();result.add("units",results);result.add("actual_server_mechanics",mechanics);
            result.addProperty("runtime_infrastructure_present",EvaHangarBuilder.runtimeInfrastructurePresent(level,RegionalFacilityLayout.evaOrigin(level)));
            result.addProperty("dynamic_blocks_enabled",com.projectseele.config.SeeleConfig.dynamicEvaFacilityBlocksEnabled());
            result.addProperty("status","READ_ONLY actual server pose/hulls/registered mechanics. Joint pivot is not an armour contact surface; actual client tracking and renderer contact separately required.");
            result.addProperty("render_scale",EvaScale.RENDER_SCALE);Files.writeString(world.resolve("r44_hangar_contacts.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));written=true;
            ProjectSeele.LOGGER.info("R44 measured original hangar body contact frames exported: 3; no actor/world state changed");
        }
        catch(Exception failure){written=true;ProjectSeele.LOGGER.error("Read-only R44 contact snapshot failed",failure);}
    }
    private HangarContactSnapshotR44() {}
}
