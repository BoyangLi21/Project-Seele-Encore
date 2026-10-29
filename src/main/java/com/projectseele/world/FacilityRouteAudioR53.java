package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;

/** Original PA clips follow the relocated route's actual mechanism stages. */
final class FacilityRouteAudioR53
{
    private static final Map<EvaUnit01Entity,String> PREVIOUS=new WeakHashMap<>();
    private static final Map<EvaUnit01Entity,Countdown> COUNTDOWNS=new WeakHashMap<>();

    static final class Countdown
    {
        final UUID task;
        private int next=3;
        private long announcedAt;
        Countdown(UUID task){this.task=task;}
        int advance(long now,boolean prepared)
        {
            if(next<0)return 0;
            if(next<3&&now-announcedAt<1_000_000_000L)return -1;
            if(next<=1&&!prepared)return -1;
            // Start each interval when its cue is actually sent. Never consume
            // missed intervals after a stall or a burst of server catch-up ticks.
            announcedAt=now;
            return next--;
        }
    }

    static void tick(ServerLevel level,NervRouteRuntimeStateR52.Job job)
    {
        if(!(level.getEntity(job.snapshot().original().eva()) instanceof EvaUnit01Entity eva))return;
        var data=job.ownerData();
        var sound=eva.getPersistentData();long now=level.getGameTime();var position=eva.position();
        String motionStage=data.getCompound(NervLaunchPhasesR53.KEY).getString("Stage");
        String key=job.phase()+"/"+data.getString("Prepare")+"/"+data.getString("Finish");
        boolean changed=!key.equals(sound.getString("R53AudioMechanism"));
        boolean moved=sound.getLong("R53AudioAt")==now-1&&position.distanceToSqr(new net.minecraft.world.phys.Vec3(sound.getDouble("R53AudioX"),sound.getDouble("R53AudioY"),sound.getDouble("R53AudioZ")))>1e-8;
        boolean progressed=changed||sound.getInt("R53AudioPrepare")!=data.getInt("PrepareTicks")||sound.getInt("R53AudioFinish")!=data.getInt("FinishTicks");
        sound.putString("R53AudioMechanism",key);sound.putLong("R53AudioAt",now);sound.putDouble("R53AudioX",position.x);sound.putDouble("R53AudioY",position.y);sound.putDouble("R53AudioZ",position.z);sound.putInt("R53AudioPrepare",data.getInt("PrepareTicks"));sound.putInt("R53AudioFinish",data.getInt("FinishTicks"));
        boolean returnFinish=job.phase()==NervRouteRuntimeStateR52.Phase.FINISHING&&data.getBoolean("Returning");
        boolean outletActuator=job.phase()==NervRouteRuntimeStateR52.Phase.FINISHING&&!data.getBoolean("Returning")&&(data.getString("Finish").equals("EJECT_LOWER")||data.getString("Finish").equals("EJECT_CLOSE"));
        // The body travels ballistically at the outlet; only its returning rack is hydraulic.
        boolean transfer=moved&&(job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING||job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING||job.phase()==NervRouteRuntimeStateR52.Phase.RETURNING||returnFinish);
        boolean hydraulic=progressed&&(job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING||returnFinish||outletActuator);
        var mechanism=outletActuator?com.projectseele.entity.EvaMechanicalFrameR52.carrierFrameR52(eva,1).translation():position;
        var machine=mechanism.add(0,25,0);var speaker=mechanism.add(0,52,0);int variant=eva.getUnitVariant();
        boolean ascent=job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING&&motionStage.equals("ASCENT");
        if((transfer||hydraulic)&&!ascent&&(changed||!sound.contains("R54MechanismSoundAt")||now<sound.getLong("R54MechanismSoundAt")||now-sound.getLong("R54MechanismSoundAt")>=40))
        {
            sound.putLong("R54MechanismSoundAt",now);
            mechanical(level,eva,machine,com.projectseele.registry.ModSounds.FACILITY.get(transfer?"facility_rail_motion":"facility_hydraulic").get(),1.15F,transfer?.42F:.32F,1);
        }
        if((transfer||job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING)&&!ascent&&now%80==variant*7)FacilityPaR31.warning(level,speaker);
        // LOWER is entered only after the receiver clamps bear the original body.
        boolean receiverLocked=returnFinish&&data.getString("Finish").equals("LOWER");
        if(changed&&(receiverLocked||job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING&&data.getString("Prepare").equals("SEAL")||job.phase()==NervRouteRuntimeStateR52.Phase.READY||job.phase()==NervRouteRuntimeStateR52.Phase.PARKED))
            mechanical(level,eva,machine,com.projectseele.registry.ModSounds.FACILITY.get("facility_lock").get(),1.4F,.5F,1);
        if(changed&&job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING&&!ascent)
        {
            mechanical(level,eva,position.add(0,2,0),com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic_launch").get(),1.8F,.7F,1);
            mechanical(level,eva,machine,com.projectseele.registry.ModSounds.FACILITY.get("facility_catapult").get(),1,.55F,1);
        }
        // ASCENT is selected before clearance succeeds and survives reloads;
        // only the route's first committed movement may announce its launch.
        String clip=job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING?(ascent?null:"pa_launch"):switch(job.phase())
        {
            case PARKED -> "pa_standby";
            case READY -> "pa_ready";
            case RETURNING -> motionStage.equals("DESCENT")?"pa_recover":"pa_return";
            case CANCELLED -> "pa_fault";
            case PREPARING -> switch(data.getString("Prepare"))
            {
                case "", "HATCH", "BRIDGE" -> "pa_prepare";
                case "INSERT" -> "pa_insert";
                case "SEAL" -> "pa_lock";
                case "DRAIN" -> "pa_drain";
                case "READY" -> "pa_transfer";
                case "FRONT_SEAL_OPEN" -> "pa_door_open";
                default -> null;
            };
            case FINISHING -> !data.getBoolean("Returning")
                    ?(data.getString("Finish").equals("EJECT_CLOSE")?"pa_door_close":null)
                    :switch(data.getString("Finish"))
            {
                case "RECEIVE" -> "pa_recover";
                case "FRONT_SEAL_CLOSE" -> "pa_door_close";
                case "REFILL" -> "pa_fill";
                default -> null;
            };
            default -> null;
        };
        if(clip==null||clip.equals(PREVIOUS.get(eva)))return;
        if(!clip.equals("pa_launch")&&FacilityPaR31.busy(level,speaker))return;
        PREVIOUS.put(eva,clip);FacilityPaR31.announce(level,speaker,clip);
    }

    static boolean countdown(ServerLevel level,NervRouteRuntimeStateR52.Job job,CompoundTag data,boolean prepared)
    {
        if(data.getInt("PaCountdownTicksR53")>=60)return prepared;
        if(!(level.getEntity(job.snapshot().original().eva()) instanceof EvaUnit01Entity eva))return false;
        var clock=COUNTDOWNS.get(eva);
        if(clock==null||!clock.task.equals(job.snapshot().task()))
        {clock=new Countdown(job.snapshot().task());COUNTDOWNS.put(eva,clock);}
        int cue=clock.advance(System.nanoTime(),prepared);
        if(cue<0)return false;
        data.putLong("PaCountdownAtR53",level.getGameTime());
        if(cue==0){data.putInt("PaCountdownTicksR53",60);COUNTDOWNS.remove(eva);return true;}
        if(cue==3)mechanical(level,eva,eva.position().add(0,2,0),com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic_charge_r48").get(),2.4F,.9F,.9F);
        FacilityPaR31.announce(level,eva.position().add(0,52,0),"pa_"+cue);
        clock.announcedAt=System.nanoTime();
        data.putInt("PaCountdownTicksR53",(3-cue)*20+1);
        return false;
    }

    /** The pilot hears the same original recording through the carried frame.
     *  Its entity-bound source follows the seated pilot throughout the clip;
     *  spectators still hear the actual mechanism's positional source once. */
    static void mechanical(ServerLevel level,EvaUnit01Entity eva,net.minecraft.world.phys.Vec3 point,
            net.minecraft.sounds.SoundEvent event,float exterior,float cockpit,float pitch)
    {
        var pilot=eva!=null&&eva.getPilotEntity() instanceof net.minecraft.server.level.ServerPlayer player?player:null;
        level.playSound(pilot,point.x,point.y,point.z,event,net.minecraft.sounds.SoundSource.BLOCKS,exterior,pitch);
        if(pilot!=null)pilot.connection.send(new net.minecraft.network.protocol.game.ClientboundSoundEntityPacket(
                net.minecraft.core.Holder.direct(event),net.minecraft.sounds.SoundSource.BLOCKS,pilot,cockpit,pitch,level.random.nextLong()));
    }

    private FacilityRouteAudioR53(){}
}
