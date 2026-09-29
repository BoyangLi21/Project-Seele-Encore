package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.world.*;
import net.minecraft.server.level.*;
import net.minecraft.world.phys.Vec3;

/** Real boarding, mission commands, operator queues and physical button presses. */
public final class AutoSortieGateR43
{
    private static int stage,age,total,ritsukoBase,misatoBase;
    private static boolean begun;
    private static final JsonArray checks=new JsonArray(),trace=new JsonArray();
    private static java.util.UUID evaId,plugId;
    public static boolean begun(){return begun;}
    private static void check(String name,boolean pass)
    {var r=new JsonObject();r.addProperty("name",name);r.addProperty("passed",pass);checks.add(r);if(!pass)throw new IllegalStateException("R43 mission gate: "+name);}
    private static void next(int value){stage=value;age=0;}
    private static void start(ServerPlayer player)
    {
        TvCampaignDirector.select(player,"shamshel");
        check("mission_start_"+stage,TvCampaignDirector.beginAssigned(player,1,false,false)==1);
    }
    public static JsonObject result()
    {var r=new JsonObject();r.add("checks",checks);r.add("trace",trace);r.addProperty("stage",stage);return r;}
    public static boolean tick(ServerLevel level,ServerPlayer player,NervStaffEntity ritsuko,NervStaffEntity misato)
    {
        begun=true;age++;total++;if(total>6500)throw new IllegalStateException("R43 gate deadline stage "+stage);
        EvaLogisticsDirector.loadControlTarget(level,1);
        var eva=EvaLogisticsDirector.canonicalUnit(level,1);var plug=EntryPlugDirector.canonical(level,1);
        if(eva==null||plug==null)return false;
        var mission=TvCampaignSavedData.get(level);var job=StaffCommandBookR24.unitOrder(level,1);
        String phase=EvaLogisticsDirector.status(level,1).phase();
        if(total%10==0)
        {
            var r=new JsonObject();r.addProperty("tick",total);r.addProperty("stage",stage);r.addProperty("phase",phase);
            r.addProperty("mission",mission.active);r.addProperty("mission_phase",mission.phase);
            r.addProperty("queued",job==null?"":job.operation);r.addProperty("automatic",job!=null&&job.automatic);
            r.addProperty("unassigned_0",EvaLogisticsDirector.status(level,0).phase());r.addProperty("unassigned_2",EvaLogisticsDirector.status(level,2).phase());
            r.addProperty("ritsuko_presses",ritsuko.pressCount());r.addProperty("misato_presses",misato.pressCount());trace.add(r);
        }
        if(stage>0)checkIdentity(eva,plug);
        switch(stage)
        {
            case 0 -> {
                check("initial_idle_and_parked",mission.active.isEmpty()&&phase.equals("PARKED"));
                if(!plug.hasCanonicalPose()||!plug.isHatchOpen())return false;
                evaId=eva.getUUID();plugId=plug.getUUID();ritsukoBase=ritsuko.pressCount();misatoBase=misato.pressCount();
                var deck=EvaHangarBuilder.boardingPosition(RegionalFacilityLayout.evaOrigin(level),1);
                check("real_boarding_deck_floor",level.getBlockState(deck.below()).isFaceSturdy(level,deck.below(),net.minecraft.core.Direction.UP));
                Vec3 eye=new Vec3(deck.getX()+.5,deck.getY()+player.getEyeHeight(),deck.getZ()+.5);
                Vec3 look=plug.transformPlugMarker(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P).subtract(eye);
                float yaw=(float)Math.toDegrees(Math.atan2(-look.x,look.z)),pitch=(float)-Math.toDegrees(Math.atan2(look.y,look.horizontalDistance()));
                player.teleportTo(level,eye.x,eye.y-player.getEyeHeight(),eye.z,yaw,pitch);player.setYHeadRot(yaw);player.yHeadRotO=yaw;
                plug.tryBoardFromHatch(player);check("boarded_via_real_hatch",plug.getFirstPassenger()==player);next(1);
            }
            case 1 -> {
                if(!phase.equals("PARKED")||job!=null&&job.automatic||ritsuko.pressCount()!=ritsukoBase)
                    check("no_task_does_not_queue_or_prepare",false);
                if(age<200)return false;
                check("no_task_200_ticks",true);start(player);next(2);
            }
            case 2 -> {
                if(job==null||!job.automatic)return false;
                check("automatic_prepare_queued",job.operation.equals("prepare")&&phase.equals("PARKED"));
                check("cancel_mission_before_prepare",TvCampaignDirector.cancel(player)==1);next(3);
            }
            case 3 -> {
                if(age<60||!mission.active.isEmpty())return false;
                check("cancelled_prepare_no_press",phase.equals("PARKED")&&ritsuko.pressCount()==ritsukoBase&&job==null);
                start(player);next(4);
            }
            case 4 -> {
                if(job==null||!job.automatic)return false;
                check("cancel_personal_auto_order",StaffCommandBookR24.cancel(player,ritsuko,1)>0);next(5);
            }
            case 5 -> {
                if(age<100)return false;
                check("cancelled_and_unassigned_units_stay_parked",phase.equals("PARKED")&&job==null&&ritsuko.pressCount()==ritsukoBase
                        &&EvaLogisticsDirector.status(level,0).phase().equals("PARKED")&&EvaLogisticsDirector.status(level,2).phase().equals("PARKED"));
                TvCampaignDirector.cancel(player);next(6);
            }
            case 6 -> {
                if(age<40||!mission.active.isEmpty())return false;
                start(player);next(7);
            }
            case 7 -> {
                if(phase.equals("PLUG_FAULT"))throw new IllegalStateException("Original unit plug fault during authorized prepare");
                if(!phase.equals("SILO_READY")||job==null||!job.automatic||!job.operation.equals("launch"))return false;
                check("authorized_prepare_pressed_once",ritsuko.pressCount()==ritsukoBase+1);
                check("cancel_before_launch",TvCampaignDirector.cancel(player)==1);next(8);
            }
            case 8 -> {
                if(age<80||!mission.active.isEmpty())return false;
                check("cancelled_launch_holds_at_silo",phase.equals("SILO_READY")&&job==null&&misato.pressCount()==misatoBase);
                check("manual_launch_allowed_without_mission",StaffCommandBookR24.request(player,misato,"launch",1)>0);next(9);
            }
            case 9 -> {
                if(!phase.equals("DEPLOYED")||!EvaLogisticsDirector.recoveryMotionSettled(eva))return false;
                check("manual_launch_pressed_once",misato.pressCount()==misatoBase+1);
                check("manual_recovery_allowed",EvaLogisticsDirector.requestRecovery(level,1).accepted());next(10);
            }
            case 10 -> {
                if(!phase.equals("PARKED"))return false;
                check("original_identity_after_manual_roundtrip",evaId.equals(eva.getUUID())&&plugId.equals(plug.getUUID()));
                player.stopRiding();eva.enterHangarStandby();next(11);return true;
            }
            default -> {return true;}
        }
        return false;
    }
    private static void checkIdentity(EvaUnit01Entity eva,EntryPlugCarrierEntity plug)
    {if(!evaId.equals(eva.getUUID())||!plugId.equals(plug.getUUID()))throw new IllegalStateException("Original identities changed during gate test");}
    private AutoSortieGateR43(){}
}
