package com.projectseele.physics;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.joml.Matrix4f;

/** Opt-in replay inputs; never a source of physics state or a release acceptance gate. */
final class ArticulatedInputTraceR45
{
    private static final AtomicInteger IDS=new AtomicInteger();
    private final Path file;
    private int rows;
    ArticulatedInputTraceR45()
    {
        String directory=System.getProperty("projectseele.r45PhysicsTraceDirectory","");
        file=directory.isBlank()?null:Path.of(directory).resolve("body_"+IDS.incrementAndGet()+".jsonl");
    }
    void event(String operation,Object... pairs)
    {
        if(file==null||rows++>=16000)return;
        try
        {
            JsonObject row=new JsonObject();row.addProperty("op",operation);
            for(int i=0;i<pairs.length;i+=2)row.add((String)pairs[i],json(pairs[i+1]));
            Files.createDirectories(file.getParent());
            Files.writeString(file,row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
        catch(Exception exception){throw new IllegalStateException("Explicit physics replay capture failed",exception);}
    }
    private static JsonElement json(Object value)
    {
        if(value instanceof JsonElement element)return element;
        if(value instanceof Number number)return new JsonPrimitive(number);
        if(value instanceof String string)return new JsonPrimitive(string);
        if(value instanceof Matrix4f matrix)
        {JsonArray array=new JsonArray();for(float f:matrix.get(new float[16]))array.add(f);return array;}
        if(value instanceof Map<?,?> map)
        {JsonObject object=new JsonObject();map.forEach((k,v)->object.add(k.toString(),json(v)));return object;}
        if(value instanceof org.joml.Vector3f vector)
        {JsonArray array=new JsonArray();array.add(vector.x);array.add(vector.y);array.add(vector.z);return array;}
        if(value instanceof org.joml.Quaternionf q)
        {JsonArray array=new JsonArray();array.add(q.x);array.add(q.y);array.add(q.z);array.add(q.w);return array;}
        throw new IllegalArgumentException("Unknown trace input "+value);
    }
}
