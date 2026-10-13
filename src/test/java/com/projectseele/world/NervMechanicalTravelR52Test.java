package com.projectseele.world;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import java.io.*;

/** Actual persisted clock mapping, with geometric fraction left unchanged. */
public final class NervMechanicalTravelR52Test
{
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception
    {
        for(int ticks:new int[]{18,40,197,640,2000})
        {
            double previous=-1;check(NervMechanicalTravelR52.fraction(0,ticks)==0&&NervMechanicalTravelR52.fraction(ticks,ticks)==1,"Exact leg endpoints changed");
            for(int clock=0;clock<=ticks;clock++)
            {
                double value=NervMechanicalTravelR52.fraction(clock,ticks);check(value>=previous,"Actual path fraction reversed");previous=value;
                check(Math.abs(value+NervMechanicalTravelR52.fraction(ticks-clock,ticks)-1)<2e-14,"Original reverse path no longer has the same timing");
                var data=new CompoundTag();NervMechanicalTravelR52.remember(data,"actual/forward",2,ticks,clock);var bytes=new ByteArrayOutputStream();NbtIo.writeCompressed(data,bytes);
                var restored=NbtIo.readCompressed(new ByteArrayInputStream(bytes.toByteArray()));check(NervMechanicalTravelR52.restoredClock(restored,"actual/forward",2,ticks,value)==clock,"Cold reload changed actual mechanical clock");
                check(NervMechanicalTravelR52.restoredClock(restored,"foreign/route",2,ticks,value)==(value==0?0:-1),"Nonzero saved clock rebased to another route");
                check(NervMechanicalTravelR52.restoredClock(restored,"actual/forward",3,ticks,value)==(value==0?0:-1),"Nonzero saved clock rebased to another leg");
                check(NervMechanicalTravelR52.restoredClock(restored,"actual/forward",2,ticks+1,value)==-1,"A changed physical duration reused a saved clock");
            }
            double edge=NervMechanicalTravelR52.fraction(1,ticks),middle=NervMechanicalTravelR52.fraction(ticks/2+1,ticks)-NervMechanicalTravelR52.fraction(ticks/2,ticks);
            check(edge<middle*.04&&Math.abs(edge-(1-NervMechanicalTravelR52.fraction(ticks-1,ticks)))<2e-14,"Endpoint travel has not eased to rest symmetrically");
        }
        var data=new CompoundTag();check(NervMechanicalTravelR52.restoredClock(data,"original",0,40,0)==0,"Fresh actual endpoint rejected");check(NervMechanicalTravelR52.restoredClock(data,"original",0,40,.25)==-1,"Missing clock guessed from a moved body");
        String directory="c".repeat(64);for(int amount=0;amount<=9;amount++){var tag=new CompoundTag();tag.putInt("BridgeAmount",amount);tag.putLong("BridgeEpoch",52);tag.putString("BridgeDirectory",directory);check(NervAssemblyOwnerR52.savedBridgeProvenance(tag,52,directory),"Exact actual bridge state lost on save");check(!NervAssemblyOwnerR52.savedBridgeProvenance(tag,51,directory),"Old bridge epoch was accepted");check(!NervAssemblyOwnerR52.savedBridgeProvenance(tag,52,"d".repeat(64)),"Foreign bridge directory was accepted");}
        data.putInt("BridgeAmount",10);data.putLong("BridgeEpoch",52);data.putString("BridgeDirectory",directory);check(!NervAssemblyOwnerR52.savedBridgeProvenance(data,52,directory),"Out-of-range bridge stage was accepted");
        System.out.println("R52 actual persisted mechanical clock/bridge provenance PASS checks="+checks+"; no world/native acceptance");
    }
}
