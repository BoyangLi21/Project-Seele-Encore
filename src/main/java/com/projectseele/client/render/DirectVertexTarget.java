package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.VertexFormat;

/** A quad buffer that accepts whole primitives as raw bytes. */
public interface DirectVertexTarget
{
    /** The format to encode for, or null while raw writes would corrupt the buffer. */
    VertexFormat projectseele$quadFormat();
    /** Address just past the last written vertex. */
    long projectseele$end();
    /** Claims room for more vertices and returns its address, which stays valid until the next buffer call. */
    long projectseele$reserve(int vertices);
}
