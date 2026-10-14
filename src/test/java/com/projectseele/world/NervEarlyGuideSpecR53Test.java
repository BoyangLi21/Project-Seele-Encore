package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.SiloHatchMechanism.Spec;
import java.io.*;
import java.nio.file.*;
import net.minecraft.nbt.*;

/** Production JSON, synced Spec codec and compressed cold NBT; no world start. */
public final class NervEarlyGuideSpecR53Test
{
    private static int checks;
    private static void require(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception
    {
        net.minecraft.SharedConstants.tryDetectVersion();var boot=net.minecraft.server.Bootstrap.class.getDeclaredField("isBootstrapped");boot.setAccessible(true);boot.setBoolean(null,true);net.minecraft.core.registries.BuiltInRegistries.bootStrap();
        var parse=NervAssemblyOwnerR52.class.getDeclaredMethod("siloSpec",JsonObject.class);parse.setAccessible(true);
        var validate=NervAssemblyOwnerR52.class.getDeclaredMethod("validateEarlyGuideRoleR53",String.class,int.class,Spec.class);validate.setAccessible(true);
        var encode=NervSiloDoorEntity.class.getDeclaredMethod("writeSpecR53",CompoundTag.class,Spec.class);encode.setAccessible(true);
        var decode=NervSiloDoorEntity.class.getDeclaredMethod("readSpec",CompoundTag.class);decode.setAccessible(true);
        var gates=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject().getAsJsonArray("gates");int early=0,ordinary=0;
        for(var raw:gates)
        {
            var gate=raw.getAsJsonObject();if(!gate.has("silo_hatch"))continue;var json=gate.getAsJsonObject("silo_hatch");var spec=(Spec)parse.invoke(null,json);
            boolean selected=gate.get("resource").getAsString().startsWith("bank_3_upper_lane_");
            validate.invoke(null,gate.get("resource").getAsString(),gate.get("variant").getAsInt(),spec);
            require(spec.uprightGuideEarlyVariant()==(selected?gate.get("variant").getAsInt():-1),"Missing role field accidentally selected early unit0");
            if(selected)early++;else if(spec.uprightGuidePorts())ordinary++;
            var data=new CompoundTag();data.putFloat("PreviousRaw",.234F);data.putFloat("CurrentRaw",.543F);data.putLong("At",927345L);data.putBoolean("OperatorFault",true);
            encode.invoke(null,data,spec);var bytes=new ByteArrayOutputStream();NbtIo.writeCompressed(data,bytes);var cold=NbtIo.readCompressed(new ByteArrayInputStream(bytes.toByteArray()));
            require(spec.equals(decode.invoke(null,cold)),"Explicit early fitting lost across compressed NBT save/read");
            require(cold.getFloat("PreviousRaw")==.234F&&cold.getFloat("CurrentRaw")==.543F&&cold.getLong("At")==927345L&&cold.getBoolean("OperatorFault"),"Spec encoding reset raw mechanism clock or unrelated state");
            cold.remove("UprightGuideEarlyVariant");require(((Spec)decode.invoke(null,cold)).uprightGuideEarlyVariant()==-1,"Legacy cold NBT must default to ordinary fitting");
        }
        require(early==3&&ordinary==24,"Only the three authorized bank3 upper specs may differ");
        require(new Spec(31,31,120,180,1,-2.01,false,true,0).uprightGuideEarlyVariant()==-1,"Original nine-argument constructor changed");
        var early0=new Spec(31,31,120,180,1,-2.01,false,true,0,0);
        for(String wrong:new String[]{"bank_1_upper_lane_2","bank_3_upper_lane_1"}){boolean rejected=false;try{validate.invoke(null,wrong,0,early0);}catch(java.lang.reflect.InvocationTargetException expected){rejected=true;}require(rejected,"Early fitting accepted an unrelated role or lane");}
        for(int bad:new int[]{-2,3}){boolean rejected=false;try{new Spec(31,31,120,180,1,-2.01,false,true,0,bad);}catch(IllegalArgumentException expected){rejected=true;}require(rejected,"Undeclared early variant accepted");}
        boolean nonGuideRejected=false;try{new Spec(33,33,120,180,-1,-2.01,true,false,180,0);}catch(IllegalArgumentException expected){nonGuideRejected=true;}require(nonGuideRejected,"Service pit accidentally received early launch fitting");
        System.out.println("PASS production early JSON/Spec/compressed cold NBT checks="+checks+" early="+early+" ordinary="+ordinary);
    }
}
