package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.Vec3;
import java.util.Map;
import java.util.WeakHashMap;

/** Audio follows the authoritative mechanics; rendering never triggers sounds. */
public final class FacilityAudioR21
{
    private static final Map<EvaUnit01Entity,EvaFleetSavedData.Phase> PREVIOUS=new WeakHashMap<>();
    private static final Map<EvaUnit01Entity,Long> COUNTDOWN=new WeakHashMap<>();
    private static final java.util.Set<EvaUnit01Entity> CHARGED_R48=java.util.Collections.newSetFromMap(new WeakHashMap<>());
    private static final java.util.Set<EvaUnit01Entity> ASCENT_SOUNDED_R48=java.util.Collections.newSetFromMap(new WeakHashMap<>());
    private static final Map<ServerLevel,Map<String,MilitaryR07Director.Phase>> AUXILIARY=new WeakHashMap<>();
    public static void auxiliary(ServerLevel level,String id,MilitaryR07Director.Phase phase,Vec3 door)
    {
        var previous=AUXILIARY.computeIfAbsent(level,l->new java.util.HashMap<>()).put(id,phase);
        Vec3 speaker=door.add(0,45,0);boolean moving=phase==MilitaryR07Director.Phase.OPENING||phase==MilitaryR07Director.Phase.CLOSING;
        if(previous!=null&&previous!=phase)
        {
            String name=switch(phase){case DRAINING->"pa_drain";case FILLING->"pa_fill";case OPENING->"pa_door_open";case CLOSING->"pa_door_close";default->null;};
            if(name!=null)FacilityPaR31.announce(level,speaker,name);
        }
        long time=level.getGameTime();
        if((phase==MilitaryR07Director.Phase.DRAINING||phase==MilitaryR07Director.Phase.FILLING)&&time%40==0)play(level,door.add(0,15,0),ModSounds.FACILITY.get("facility_hydraulic").get(),1.1F);
        if(moving&&time%80==0)FacilityPaR31.warning(level,speaker);
        if(time%10==0)for(int side:new int[]{-1,1})
        {
            boolean wide=UNHangarDimensionsR31.active(level);
            BlockPos p=BlockPos.containing(door.add(side*(wide?26:19),67,wide?3:0));var state=level.getBlockState(p);boolean lit=moving&&time%20<10;
            if(state.is(com.projectseele.registry.ModBlocks.NERV_WARNING_BEACON.get())&&state.getValue(BlockStateProperties.LIT)!=lit)level.setBlock(p,state.setValue(BlockStateProperties.LIT,lit),2);
        }
    }
    public static void tick(ServerLevel level,int variant,EvaFleetSavedData.FleetEntry entry,EvaUnit01Entity unit,BlockPos cage,BlockPos silo)
    {
        if(!unit.isLaunchCommandReleased()||unit.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_LOCKED)CHARGED_R48.remove(unit);
        if(unit.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_ASCENT)ASCENT_SOUNDED_R48.remove(unit);
        if(!TvLaunchFacility.enabled(level))return;
        var phase=entry.phase();var previous=PREVIOUS.put(unit,phase);
        Vec3 machine=unit.position().add(0,25,0),speaker=unit.position().add(0,52,0);
        if(previous!=null&&phase!=previous)
        {
            String voice=switch(phase){case BRIDGE_RETRACTING->"pa_prepare";case PLUG_INSERTING->"pa_insert";case PLUG_LOCKING->"pa_lock";case DRAINING->"pa_drain";case TO_SILO->"pa_transfer";case SILO_READY->"pa_ready";case DESCENDING->"pa_recover";case TO_HANGAR->"pa_return";case FILLING->"pa_fill";case PARKED->"pa_standby";case PLUG_FAULT,PLUG_ABORT_RETURNING->"pa_fault";default->null;};
            if(voice!=null)FacilityPaR31.announce(level,speaker,voice);
            if(phase==EvaFleetSavedData.Phase.PLUG_LOCKING||phase==EvaFleetSavedData.Phase.SILO_READY||phase==EvaFleetSavedData.Phase.PARKED)
                play(level,machine,ModSounds.FACILITY.get("facility_lock").get(),1.4F);
        }
        boolean transfer=phase==EvaFleetSavedData.Phase.TO_SILO||phase==EvaFleetSavedData.Phase.TO_HANGAR||phase==EvaFleetSavedData.Phase.DESCENDING;
        boolean hydraulic=phase==EvaFleetSavedData.Phase.PLUG_INSERTING||phase==EvaFleetSavedData.Phase.PLUG_LOCKING||phase==EvaFleetSavedData.Phase.DRAINING||phase==EvaFleetSavedData.Phase.FILLING||phase==EvaFleetSavedData.Phase.BRIDGE_RETRACTING;
        boolean launch=unit.isLaunchSequenceActive()&&unit.isLaunchCommandReleased();
        long time=level.getGameTime();
        if((transfer||hydraulic)&&time%40==variant*7)
            play(level,machine,ModSounds.FACILITY.get(transfer?"facility_rail_motion":"facility_hydraulic").get(),1.15F);
        if((transfer||launch)&&time%80==variant*7)FacilityPaR31.warning(level,speaker);
        if(time%10==0)
        {
            boolean lit=(transfer||launch||TvMissionAlertR30.active(level))&&time%20<10;
            for(BlockPos anchor:new BlockPos[]{cage.offset(-17,64,19),cage.offset(17,64,19),silo.offset(-17,55,-17),silo.offset(17,55,-17)})
            {
                if(!level.hasChunkAt(anchor))continue;
                var state=level.getBlockState(anchor);
                if(state.is(com.projectseele.registry.ModBlocks.NERV_WARNING_BEACON.get())&&state.getValue(BlockStateProperties.LIT)!=lit)
                    level.setBlock(anchor,state.setValue(BlockStateProperties.LIT,lit),2);
            }
        }
        if(launch&&unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_LOCKED)
        {
            int ticks=unit.getLaunchTicks();int number=(ticks-20+19)/20;
            if(number>=1&&number<=3)
            {
                long key=number;Long last=COUNTDOWN.put(unit,key);
                if(last==null||last!=key)FacilityPaR31.announce(level,speaker,"pa_"+number);
            }
        }
        else if(unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_ASCENT)
        {
            Long last=COUNTDOWN.put(unit,0L);
            if(last==null||last!=0)FacilityPaR31.announce(level,speaker,"pa_launch");
        }
        else COUNTDOWN.remove(unit);
    }
    /** Called by the accepted command after its released flag and native countdown are set. */
    public static void authorizedLaunchChargeR48(EvaUnit01Entity unit,int releaseTicks)
    {
        if(!(unit.level() instanceof ServerLevel level)||!TvLaunchFacility.enabled(level)||releaseTicks<80
                ||!unit.isLaunchCommandReleased()||unit.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_LOCKED
                ||!CHARGED_R48.add(unit))return;
        play(level,unit.position().add(0,2,0),ModSounds.FACILITY.get("facility_hydraulic_charge_r48").get(),1.0F);
    }
    /** The native ascent start owns both distinct mechanical layers, once per launch. */
    public static void beginCatapultR48(EvaUnit01Entity unit)
    {
        if(!(unit.level() instanceof ServerLevel level)||!unit.isLaunchCommandReleased()
                ||unit.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_ASCENT||!ASCENT_SOUNDED_R48.add(unit))return;
        play(level,unit.position().add(0,2,0),ModSounds.FACILITY.get("facility_hydraulic_launch").get(),1.8F);
        if(TvLaunchFacility.enabled(level))play(level,unit.position().add(0,25,0),ModSounds.FACILITY.get("facility_catapult").get(),1.0F);
    }
    private static void play(ServerLevel level,Vec3 pos,SoundEvent sound,float volume)
    {
        level.playSound(null,pos.x,pos.y,pos.z,sound,SoundSource.BLOCKS,volume,1);
    }
    private FacilityAudioR21(){}
}
