#version 150

// R65 GeoFront far view: one instance per cavity block face; the corners come from gl_VertexID (a strip of four).
// Base is the face's corner on its own plane (blocks from the cell origin), Extent its size along the face's axes:
// X faces (y, z), Y faces (x, z), Z faces (x, y). Looks holds per block state and face the sprite's rectangle in the
// block atlas, then the colour and 1 when the face is drawn with its texture.
in vec3 Base;
in vec2 Extent;
in int Face;
in int Look;

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform vec3 Camera;
uniform vec3 CellOrigin;
uniform samplerBuffer Looks;

out vec2 tile;
flat out vec4 rect;
flat out vec4 colour;
flat out vec3 meanTexel;
out vec3 relative;

void main() {
    vec2 c = vec2(gl_VertexID & 1, gl_VertexID >> 1);
    vec3 p = Base + CellOrigin;
    int axis = Face / 2;
    vec2 t;
    if (axis == 0) {
        p.y += c.x * Extent.x;
        p.z += c.y * Extent.y;
        t = vec2(c.y * Extent.y, (1.0 - c.x) * Extent.x);
    } else if (axis == 1) {
        p.x += c.x * Extent.x;
        p.z += c.y * Extent.y;
        t = vec2(c.x * Extent.x, c.y * Extent.y);
    } else {
        p.x += c.x * Extent.x;
        p.y += c.y * Extent.y;
        t = vec2(c.x * Extent.x, (1.0 - c.y) * Extent.y);
    }
    gl_Position = ProjMat * ModelViewMat * vec4(p, 1.0);
    tile = t;
    rect = texelFetch(Looks, Look * 3);
    vec4 look = texelFetch(Looks, Look * 3 + 1);
    meanTexel = texelFetch(Looks, Look * 3 + 2).rgb;
    float shade = Face == 3 ? 1.0 : Face == 2 ? 0.55 : axis == 0 ? 0.8 : 0.68;
    colour = vec4(look.rgb * shade, look.a);
    relative = p - Camera;
}
