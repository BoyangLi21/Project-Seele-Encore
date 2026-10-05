package com.projectseele.compat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.loading.FMLEnvironment;
import net.minecraftforge.fml.loading.FMLPaths;

/** Portable producer contract, selected before optional Create transformations. */
public final class CityUnionPortableBootstrapR45
{
    public static final String ACTIVATION="exact_native_input_abi_r47";
    private static boolean configured,portableActive;
    private static String runtimeScope="";
    private CityUnionPortableBootstrapR45() {}
    public static boolean requested(){configure();return Boolean.getBoolean("projectseele.r45CityBalancedUnion");}
    public static synchronized void configure()
    {
        if(configured)return;
        runtimeScope=FMLEnvironment.dist==Dist.CLIENT?"forgeclient":"forgeserver";
        // Explicit on/off QA requests remain possible. Obsolete proof/class
        // properties cannot suppress the current portable owner selection.
        if(System.getProperty("projectseele.r45CityBalancedUnion")!=null)
        {configured=true;return;}
        Path file=FMLPaths.GAMEDIR.get().resolve("config/projectseele-runtime-r45.properties");
        if(!Files.isRegularFile(file)){configured=true;return;}
        try
        {
            Properties values=new Properties();
            try(var stream=Files.newInputStream(file)){values.load(stream);}
            if(!"projectseele.runtime-owners.r45.v1".equals(values.getProperty("schema")))
                throw new IllegalStateException("Unknown portable city configuration schema");
            for(String key:new String[]{"enabled","required"})
            {
                String client=values.getProperty("city.union.client."+key,"false").strip();
                String server=values.getProperty("city.union.server."+key,"false").strip();
                if(!client.equals(server)||!(client.equals("true")||client.equals("false")))
                    throw new IllegalStateException("Client/server city union policies must agree: "+key);
            }
            boolean enabled=Boolean.parseBoolean(values.getProperty("city.union.client.enabled","false"));
            boolean required=Boolean.parseBoolean(values.getProperty("city.union.client.required","false"));
            if(enabled!=required)throw new IllegalStateException("Enabled portable exact union requires actual activation");
            if(enabled)
            {
                if(!ACTIVATION.equals(values.getProperty("city.union.activation","")))
                    throw new IllegalStateException("Explicit current native input/ABI activation policy required");
                System.setProperty("projectseele.r45CityBalancedUnion","true");
                System.setProperty("projectseele.r45CityBalancedUnionRequired","true");
                portableActive=true;
            }
            configured=true;
        }
        catch(Exception failure){throw new IllegalStateException("Portable required city union configuration refused",failure);}
    }
    public static boolean portableActive(){configure();return portableActive;}
    public static String runtimeScope(){configure();return runtimeScope;}
}
