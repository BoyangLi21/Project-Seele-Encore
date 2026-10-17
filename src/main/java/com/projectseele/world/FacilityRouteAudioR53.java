package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;

/** Original PA clips follow the relocated route's actual mechanism stages. */
final class FacilityRouteAudioR53
{
    private static final Map<EvaUnit01Entity,String> PREVIOUS=new WeakHashMap<>();

    static void tick(ServerLevel level,NervRouteRuntimeStateR52.Job job)
    {
        if(!(level.getEntity(job.snapshot().original().eva()) instanceof EvaUnit01Entity eva))return;
        var data=job.ownerData();
        var sound=eva.getPersistentData();long now=level.getGameTime();var position=eva.position();
        String key=job.phase()+"/"+data.getString("Prepare")+"/"+data.getString("Finish");
        boolean changed=!key.equals(sound.getString("R53AudioMechanism"));
        boolean moved=sound.getLong("R53AudioAt")==now-1&&position.distanceToSqr(new net.minecraft.world.phys.Vec3(sound.getDouble("R53AudioX"),sound.getDouble("R53AudioY"),sound.getDouble("R53AudioZ")))>1e-8;
        boolean progressed=changed||sound.getInt("R53AudioPrepare")!=data.getInt("PrepareTicks")||sound.getInt("R53AudioFinish")!=data.getInt("FinishTicks");
        sound.putString("R53AudioMechanism",key);sound.putLong("R53AudioAt",now);sound.putDouble("R53AudioX",position.x);sound.putDouble("R53AudioY",position.y);sound.putDouble("R53AudioZ",position.z);sound.putInt("R53AudioPrepare",data.getInt("PrepareTicks"));sound.putInt("R53AudioFinish",data.getInt("FinishTicks"));
        boolean transfer=moved&&(job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING||job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING||job.phase()==NervRouteRuntimeStateR52.Phase.RETURNING||job.phase()==NervRouteRuntimeStateR52.Phase.FINISHING);
        boolean hydraulic=progressed&&(job.phase()==NervRouteRuntimeStateR52.Phase.PREPARING||job.phase()==NervRouteRuntimeStateR52.Phase.FINISHING);
        var machine=position.add(0,25,0);var speaker=position.add(0,52,0);int variant=eva.getUnitVariant();
        boolean ascent=data.getCompound(NervLaunchPhasesR53.KEY).getString("Stage").equals("ASCENT");
        if((transfer||hydraulic)&&!ascent&&now%40==variant*7)
            level.playSound(null,machine.x,machine.y,machine.z,com.projectseele.registry.ModSounds.FACILITY.get(transfer?"facility_rail_motion":"facility_hydraulic").get(),net.minecraft.sounds.SoundSource.BLOCKS,1.15F,1);
        if((transfer||job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING)&&!ascent&&now%80==variant*7)FacilityPaR31.warning(level,speaker);
        if(changed&&(data.getString("Prepare").equals("LOCK")||job.phase()==NervRouteRuntimeStateR52.Phase.READY||job.phase()==NervRouteRuntimeStateR52.Phase.PARKED))
            level.playSound(null,machine.x,machine.y,machine.z,com.projectseele.registry.ModSounds.FACILITY.get("facility_lock").get(),net.minecraft.sounds.SoundSource.BLOCKS,1.4F,1);
        if(changed&&job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING&&!ascent)
        {
            level.playSound(null,position.x,position.y+2,position.z,com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic_launch").get(),net.minecraft.sounds.SoundSource.BLOCKS,1.8F,1);
            level.playSound(null,machine.x,machine.y,machine.z,com.projectseele.registry.ModSounds.FACILITY.get("facility_catapult").get(),net.minecraft.sounds.SoundSource.BLOCKS,1,1);
        }
        String clip=job.phase()==NervRouteRuntimeStateR52.Phase.DEPARTING?"pa_launch":switch(job.phase())
        {
            case PARKED -> "pa_standby";
            case READY -> "pa_ready";
            case RETURNING -> "pa_return";
            case CANCELLED -> "pa_fault";
            case PREPARING -> switch(data.getString("Prepare"))
            {
                case "", "HATCH", "BRIDGE" -> "pa_prepare";
                case "INSERT" -> "pa_insert";
                case "LOCK" -> "pa_lock";
                case "DRAIN" -> "pa_drain";
                case "READY" -> "pa_transfer";
                case "FRONT_SEAL_OPEN" -> "pa_door_open";
                default -> null;
            };
            case FINISHING -> !data.getBoolean("Returning")?null:switch(data.getString("Finish"))
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

    static boolean countdown(ServerLevel level,NervRouteRuntimeStateR52.Job job,CompoundTag data)
    {
        if(data.getInt("PaCountdownTicksR53")>=60)return true;
        if(data.contains("PaCountdownAtR53")&&data.getLong("PaCountdownAtR53")==level.getGameTime())return false;
        int age=data.getInt("PaCountdownTicksR53");
        if(age%20==0&&level.getEntity(job.snapshot().original().eva()) instanceof EvaUnit01Entity eva)
        {
            if(age==0)level.playSound(null,eva.getX(),eva.getY()+2,eva.getZ(),com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic_charge_r48").get(),net.minecraft.sounds.SoundSource.BLOCKS,1,1);
            FacilityPaR31.announce(level,eva.position().add(0,52,0),"pa_"+(3-age/20));
        }
        data.putLong("PaCountdownAtR53",level.getGameTime());
        data.putInt("PaCountdownTicksR53",age+1);
        return false;
    }

    private FacilityRouteAudioR53(){}
}
