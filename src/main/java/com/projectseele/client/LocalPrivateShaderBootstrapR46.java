package com.projectseele.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraftforge.fml.loading.FMLPaths;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

/** Build the bundled offline recipe only inside the player's personal client instance. */
public final class LocalPrivateShaderBootstrapR46
{
    private static final String RECIPE="private_shader_recipe_v12.json";
    private static final String MARKER="config/projectseele-private-visuals-r46.json";

    public static void installAndSelect()
    {
        Path game=FMLPaths.GAMEDIR.get().toAbsolutePath().normalize();
        Path recipePath=game.resolve(RECIPE);
        // The Plain client does not carry the recipe or Oculus.
        if(!Files.isRegularFile(recipePath))return;
        try
        {
            var recipe=JsonParser.parseString(Files.readString(recipePath)).getAsJsonObject();
            if(!"projectseele.local-private-shader-adapter.v12".equals(recipe.get("schema").getAsString())
                    ||!"LOCAL_PERSONAL_ONLY_NOT_PREBUILT_SHADER_DISTRIBUTION".equals(recipe.get("scope").getAsString()))
                throw new IllegalArgumentException("Unrecognized personal shader recipe");
            String originalName=filename(recipe.get("input_filename").getAsString());
            String selected=filename(recipe.get("output_filename").getAsString());
            if(!"ComplementaryUnbound_r5.3.zip".equals(originalName)||!selected.startsWith("SEELE_Local_"))
                throw new IllegalArgumentException("Personal shader must have its own local name");
            Path directory=game.resolve("shaderpacks"),original=directory.resolve(originalName);
            byte[] source=Files.readAllBytes(original);
            Map<String,byte[]> entries=readArchive(source);
            byte[] license=present(entries.get("License.txt"),"License.txt");
            Map<String,byte[]> output=new TreeMap<>(entries);
            for(var value:recipe.getAsJsonArray("files"))
            {
                var file=value.getAsJsonObject();String name=entry(file.get("path").getAsString());
                byte[] bytes=present(entries.get(name),name);
                String[] lines=normalized(bytes).split("\n",-1);var result=new ArrayList<String>();
                for(var item:file.getAsJsonArray("parts"))
                {
                    var part=item.getAsJsonObject();String operation=part.get("op").getAsString();
                    switch(operation)
                    {
                        case "copy" ->
                        {
                            int start=part.get("index").getAsInt(),count=part.get("count").getAsInt();
                            if(start<0||count<0||start>lines.length-count)throw new IllegalArgumentException("Recipe line range");
                            result.addAll(Arrays.asList(lines).subList(start,start+count));
                        }
                        case "append" -> {for(var line:part.getAsJsonArray("lines"))result.add(line.getAsString());}
                        case "edit" ->
                        {
                            String line=lines[part.get("index").getAsInt()];
                            for(var ruleValue:part.getAsJsonArray("rules"))
                            {
                                var rule=ruleValue.getAsJsonObject();String action=rule.get("op").getAsString();
                                if("replace".equals(action))line=replaceOnce(line,rule.get("old").getAsString(),rule.get("new").getAsString());
                                else if("append_before_semicolon".equals(action)&&line.endsWith(";"))
                                    line=line.substring(0,line.length()-1)+rule.get("text").getAsString()+";";
                                else throw new IllegalArgumentException("Recipe edit operation");
                            }
                            result.add(line);
                        }
                        default -> throw new IllegalArgumentException("Recipe operation");
                    }
                }
                bytes=String.join("\n",result).getBytes(StandardCharsets.UTF_8);
                output.put(name,bytes);
            }
            for(var value:recipe.getAsJsonArray("project_authored_entries"))
            {
                var file=value.getAsJsonObject();String name=entry(file.get("path").getAsString());
                output.put(name,file.get("project_authored_text").getAsString().getBytes(StandardCharsets.UTF_8));
            }
            for(var value:recipe.getAsJsonArray("clone_at_install_time"))
            {
                var file=value.getAsJsonObject();String name=entry(file.get("path").getAsString());
                String from=entry(file.get("source").getAsString());byte[] bytes=present(entries.get(from),from);
                bytes=replaceOnce(normalized(bytes),file.get("replace_old").getAsString(),file.get("replace_new").getAsString()).getBytes(StandardCharsets.UTF_8);
                output.put(name,bytes);
            }
            output.put("SEELE_LOCAL_PRIVATE_ADAPTATION.txt",recipe.get("credits").getAsString().getBytes(StandardCharsets.UTF_8));
            // The shader's own licence must ship unaltered with the adaptation.
            if(!Arrays.equals(output.get("License.txt"),license))throw new IllegalArgumentException("Recipe altered the shader License.txt");
            Path target=directory.resolve(selected);
            if(!Files.exists(target)||!sameEntries(target,output))
            {
                Path temporary=Files.createTempFile(directory,"seele-private-r46-",".partial");
                try
                {
                    try(var zip=new ZipOutputStream(Files.newOutputStream(temporary)))
                    {
                        for(var row:output.entrySet())
                        {zip.putNextEntry(new ZipEntry(row.getKey()));zip.write(row.getValue());zip.closeEntry();}
                    }
                    Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING);
                }
                finally {Files.deleteIfExists(temporary);}
            }
            Path settings=directory.resolve(selected+".txt");
            if(!Files.exists(settings))
            {
                var lines=new ArrayList<String>();for(var item:recipe.getAsJsonArray("settings"))lines.add(item.getAsString());
                Files.writeString(settings,String.join("\n",lines)+"\n",StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
            }
            Path marker=game.resolve(MARKER);
            // Once installed, leave a later deliberate shader selection untouched.
            if(!Files.exists(marker))
            {
                Class<?> iris=Class.forName("net.irisshaders.iris.Iris");Object config=iris.getMethod("getIrisConfig").invoke(null);
                @SuppressWarnings("unchecked") Optional<String> active=(Optional<String>)config.getClass().getMethod("getShaderPackName").invoke(config);
                boolean select=active.isEmpty()||active.get().equals(originalName)||active.get().equals(selected);
                if(select)
                {
                    config.getClass().getMethod("setShaderPackName",String.class).invoke(config,selected);
                    // Preserve the user's enableShaders choice, including the packaged disabled default.
                    config.getClass().getMethod("save").invoke(config);iris.getMethod("reload").invoke(null);
                }
                Files.createDirectories(marker.getParent());
                var receipt=new JsonObject();receipt.addProperty("schema","projectseele.personal-shader-installed.r46.v1");
                receipt.addProperty("original_sha256",hash(source));receipt.addProperty("recipe_sha256",hash(Files.readAllBytes(recipePath)));
                receipt.addProperty("local_output",selected);receipt.addProperty("local_output_sha256",hash(Files.readAllBytes(target)));
                receipt.addProperty("selected_on_first_install",select);receipt.addProperty("world_written",false);
                Files.writeString(marker,receipt.toString(),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
            }
            ProjectSeele.LOGGER.info("SEELE personal shader available: file={} sha256={} recipe_sha256={}",selected,hash(Files.readAllBytes(target)),hash(Files.readAllBytes(recipePath)));
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("SEELE personal shader install failed; inspect bundled original and offline recipe",failure);
        }
    }

    private static Map<String,byte[]> readArchive(byte[] bytes)throws Exception
    {
        var entries=new HashMap<String,byte[]>();int total=0;
        try(var zip=new ZipInputStream(new ByteArrayInputStream(bytes)))
        {
            for(ZipEntry file;(file=zip.getNextEntry())!=null;)
            {
                String name=entry(file.getName());byte[] content=zip.readNBytes(1_000_001);total+=content.length;
                if(content.length>1_000_000||total>16_000_000||entries.put(name,content)!=null)
                    throw new IllegalArgumentException("Oversize/duplicate shader archive entry");
            }
        }
        return entries;
    }
    private static boolean sameEntries(Path target,Map<String,byte[]> expected)throws Exception
    {
        Map<String,byte[]> actual=readArchive(Files.readAllBytes(target));
        if(!actual.keySet().equals(expected.keySet()))return false;
        for(var row:expected.entrySet())if(!Arrays.equals(actual.get(row.getKey()),row.getValue()))return false;
        return true;
    }
    private static String normalized(byte[] bytes){return new String(bytes,StandardCharsets.UTF_8).replace("\r","");}
    private static String replaceOnce(String text,String old,String replacement)
    {
        int at=text.indexOf(old);
        if(old.isEmpty()||at<0||text.indexOf(old,at+old.length())>=0)throw new IllegalArgumentException("Nonunique recipe selector");
        return text.substring(0,at)+replacement+text.substring(at+old.length());
    }
    private static String filename(String name)
    {
        if(!name.matches("[A-Za-z0-9_.-]+\\.zip"))throw new IllegalArgumentException("Invalid local shader filename");return name;
    }
    private static String entry(String name)
    {
        if(name.isEmpty()||name.startsWith("/")||name.contains("\\")||name.contains(":"))throw new IllegalArgumentException("Invalid shader entry");
        for(String part:name.split("/"))if(part.equals(".")||part.equals(".."))throw new IllegalArgumentException("Unsafe shader entry");
        return name;
    }
    private static String hash(byte[] bytes)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static byte[] present(byte[] bytes,String name)
    {if(bytes==null)throw new IllegalArgumentException("Shader entry missing: "+name);return bytes;}
    private LocalPrivateShaderBootstrapR46(){}
}
