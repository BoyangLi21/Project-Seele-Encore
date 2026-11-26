#version 150

uniform usampler2D Survey;
uniform ivec4 Grid;
uniform ivec2 Tile;
uniform mat4 Clip;
uniform vec3 Eye;
out vec3 relative;
out vec3 colour;
out float valid;

void main() {
    ivec2 cell = Tile + ivec2(gl_VertexID % 65, gl_VertexID / 65);
    ivec2 bounds = textureSize(Survey, 0);
    uvec4 s = texelFetch(Survey, min(cell, bounds - 1), 0);
    uint top = s.r * 256u + s.g;
    valid = top > 0u && all(lessThan(cell, bounds)) ? 1.0 : 0.0;
    uint rgb = s.b * 256u + s.a;
    colour = vec3(rgb >> 11u, (rgb >> 5u) & 63u, rgb & 31u) / vec3(31, 63, 31);
    vec2 xz = vec2(Grid.xy + cell * Grid.z) + 0.5 * float(Grid.z);
    vec3 world = vec3(xz.x, float(Grid.w) + float(top) - 3.0, xz.y);
    relative = world - Eye;
    gl_Position = Clip * vec4(world, 1.0);
}
