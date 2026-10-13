package com.projectseele.client.screen;

import com.projectseele.world.StaffUndergroundChoiceR52;

/** Structured GUI intent and ready-state decisions, without a client/world or machinery writes. */
public final class StaffUndergroundMenuR52Test
{
    public static void main(String[] args)
    {
        for(int unit=0;unit<3;unit++)for(boolean prepare:new boolean[]{false,true})
        {
            var choice=StaffUndergroundChoiceR52.parse(StaffUndergroundChoiceR52.request(unit,prepare));
            if(choice.unit()!=unit||choice.prepareFirst()!=prepare)throw new AssertionError("Unit/destination lost by UI request");
        }
        for(String bad:new String[]{"UNDERGROUND_DEPLOY:-1:ready","UNDERGROUND_DEPLOY:3:prepare","UNDERGROUND_DEPLOY:0:launch",
                "UNDERGROUND_DEPLOY:1:prepare:launch","UNDERGROUND:1:ready","UNDERGROUND_DEPLOY:x:ready"})
        {
            boolean rejected=false;try{StaffUndergroundChoiceR52.parse(bad);}catch(IllegalArgumentException expected){rejected=true;}
            if(!rejected)throw new AssertionError("Malformed or surface-launch request admitted: "+bad);
        }
        if(!StaffUndergroundChoiceR52.initialOperation(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY).equals("prepare"))
            throw new AssertionError("Underground combined order skipped physical preparation");
        for(String phase:new String[]{"PARKED","BRIDGE_RETRACTING","PLUG_INSERTING","DRAINING","TO_SILO","DEPLOYED","PLUG_FAULT"})
            if(StaffUndergroundChoiceR52.deploymentReady(phase)
                    ||!StaffUndergroundChoiceR52.readyContinuation(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY,phase).isEmpty())
                throw new AssertionError("Underground departure admitted before true SILO_READY: "+phase);
        if(!StaffUndergroundChoiceR52.readyContinuation(StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY,"SILO_READY").equals("underground")
                ||!StaffUndergroundChoiceR52.readyContinuation("deploy","SILO_READY").equals("launch")
                ||!StaffUndergroundChoiceR52.readyContinuation("prepare","SILO_READY").isEmpty())
            throw new AssertionError("Preparation confused underground/surface/prepare-only destinations");
        if(StaffUndergroundChoiceR52.deployedDoorReady("SILO_READY")||!StaffUndergroundChoiceR52.deployedDoorReady("DEPLOYED"))
            throw new AssertionError("Door-only operation still implicitly deployed a waiting EVA");
        for(boolean npc:new boolean[]{false,true})
        {
            String driver=npc?"npc":"human";
            if(!StaffConversationScreen.sortieRequest("sachiel",2,npc,"special").equals("ARMEDSORTIE:2:"+driver))
                throw new AssertionError("Unit02 standard sword selection stopped using its original equipment order");
            if(!StaffConversationScreen.sortieRequest("sachiel",1,npc,"melee").equals("CAMPAIGN:sortie:sachiel:1:"+driver+":melee"))
                throw new AssertionError("Ordinary sortie dispatch changed");
        }
        System.out.println("PASS: 3 units x2 underground choices; malformed requests rejected; prepare waits for SILO_READY; underground never maps to surface launch; door-only requires DEPLOYED; existing human/NPC Unit02 sword dispatch retained");
    }
}
