package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.storage.LevelResource;
import java.nio.file.Files;
import java.util.*;

/** A short, persistent detection/identification briefing precedes every selected sortie. */
public final class TvMissionAlertR30
{
    private static final Map<ServerLevel,List<BlockPos>> BEACONS=new WeakHashMap<>();
    /** The two NERV HQ PA speakers the alert sounds from. */
    private static final List<net.minecraft.world.phys.Vec3> SPEAKERS=List.of(
            net.minecraft.world.phys.Vec3.atCenterOf(new BlockPos(30,-412,289)),net.minecraft.world.phys.Vec3.atCenterOf(new BlockPos(30,-391,-240)));
    private static final Map<ServerLevel,Long> LAST_LINE=new WeakHashMap<>();
    public static boolean active(ServerLevel level){return TvCampaignSavedData.get(level).phase.equals("alert");}
    private static List<BlockPos> beacons(ServerLevel level)
    {
        return BEACONS.computeIfAbsent(level,l->{
            var path=l.getServer().getWorldPath(LevelResource.ROOT).resolve("mission_alert_r30.json");if(!Files.isRegularFile(path))return List.of();
            try{var out=new ArrayList<BlockPos>();for(var raw:JsonParser.parseString(Files.readString(path)).getAsJsonObject().getAsJsonArray("command_beacons")){var a=raw.getAsJsonArray();out.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}return List.copyOf(out);}
            catch(Exception e){throw new IllegalStateException("Invalid mission alarm circuit",e);}
        });
    }
    public static boolean tick(ServerLevel level,TvCampaignSavedData data,ServerPlayer commander)
    {
        long age=level.getGameTime()-data.alertStarted;
        for(var p:beacons(level))if(level.hasChunkAt(p))
        {var s=level.getBlockState(p);boolean lit=age<180&&age%20<10;if(s.is(ModBlocks.NERV_ALERT_LIGHT.get())&&s.getValue(BlockStateProperties.LIT)!=lit)level.setBlock(p,s.setValue(BlockStateProperties.LIT,lit),2);}
        if(age<180&&age%60==0)
        {
            for(var p:SPEAKERS)FacilityPaR31.warning(level,p);
            // R64: the city alarm already carries the siren to everyone; without it, participants still get it at the ear.
            if(!com.projectseele.config.SeeleConfig.ALARM_ENABLED.get())
                MissionAudioR64.toParticipants(level,data,com.projectseele.registry.ModSounds.FACILITY.get("facility_siren").get(),
                        net.minecraft.sounds.SoundSource.BLOCKS,.48F,SPEAKERS);
        }
        Long lastLine=LAST_LINE.get(level);
        if(commander!=null&&data.alertLine<5&&age>=data.alertLine*35L
                &&(data.alertLine==0||lastLine==null||level.getGameTime()<lastLine||level.getGameTime()-lastLine>=35))
        {
            String[][] lines={{"伊吹摩耶","dialogue.projectseele.alert.detected"},{"伊吹摩耶","dialogue.projectseele.alert.blue"},{"葛城美里","dialogue.projectseele.alert.prepare"},{"赤木律子","dialogue.projectseele.alert.monitor"},{"葛城美里","dialogue.projectseele.alert.sortie"}};
            int index=data.alertLine++;var line=lines[index];NervStaffDialogue.say(commander,line[0]+" · 指挥通信",line[1]);
            for(var crew:data.sorties.values())if(!crew.npc&&!crew.commander.equals(commander.getUUID()))
            {var pilot=level.getServer().getPlayerList().getPlayer(crew.commander);if(pilot!=null&&pilot.level()==level)NervStaffDialogue.say(pilot,line[0]+" · 指挥通信",line[1]);}
            // Character dialogue remains text. This is a separate building-wide
            // announcement, without a named character or an actor-like voice.
            if(index==2)
            {
                for(var speaker:SPEAKERS)FacilityPaR31.announce(level,speaker,"pa_combat_r31");
                // R64: participants away from NERV HQ hear the same announcement at the ear.
                MissionAudioR64.toParticipants(level,data,com.projectseele.registry.ModSounds.FACILITY.get("pa_combat_r31").get(),
                        net.minecraft.sounds.SoundSource.BLOCKS,1F,SPEAKERS);
            }
            LAST_LINE.put(level,level.getGameTime());data.setDirty();
        }
        return age>=180&&data.alertLine>=5;
    }
    public static void clear(ServerLevel level)
    {for(var p:beacons(level))if(level.hasChunkAt(p)){var s=level.getBlockState(p);if(s.is(ModBlocks.NERV_ALERT_LIGHT.get()))level.setBlock(p,s.setValue(BlockStateProperties.LIT,false),2);}}
    private TvMissionAlertR30(){}
}
