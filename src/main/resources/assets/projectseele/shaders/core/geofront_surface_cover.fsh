#version 150

uniform sampler2D NativeDepth;
uniform sampler2D DhDepth;
uniform bool HasDh;
uniform vec2 SceneZ;
uniform vec2 DhToScene;
uniform vec3 Haze;
uniform usampler2D Survey;
uniform ivec4 Grid;
uniform ivec2 Tile;
uniform sampler2D GroundMap;
uniform vec4 MapBounds;
uniform float NativeRange;
uniform vec3 Eye;
uniform float HandoffRange;
in vec3 relative;
in vec3 colour;
in float valid;
in float canopy;
out vec4 fragColor;

// During DH's near handoff its depth can report an opaque face floating over a
// forest. Verify the hit against the highest surveyed neighbour, leaving water,
// structures, unsurveyed areas, and real native foreground to their own passes.
bool aboveCanopy(vec3 hit) {
    vec2 offset = abs(hit.xz - Eye.xz);
    if (canopy < 0.999 || max(offset.x, offset.y) >= HandoffRange) return false;
    ivec2 cell = ivec2(floor((hit.xz - vec2(Grid.xy)) / float(Grid.z)));
    ivec2 size = textureSize(Survey, 0);
    if (any(lessThan(cell, ivec2(1))) || any(greaterThanEqual(cell + 1, size))) return false;
    if (texelFetch(Survey, cell, 0).r < 128u) return false;
    uint highest = 0u;
    for (int dz = -1; dz <= 1; ++dz) for (int dx = -1; dx <= 1; ++dx) {
        uvec2 s = texelFetch(Survey, cell + ivec2(dx, dz), 0).rg;
        uint y = (s.r & 31u) * 256u + s.g;
        if (y == 0u) return false;
        highest = max(highest, y);
    }
    return hit.y > float(Grid.w) + float(highest) + 7.0;
}

// The index buffer emits two triangles in this order per 8-block square.
bool supportedTriangle(out bool mapped) {
    mapped = false;
    int square = gl_PrimitiveID / 2;
    ivec2 origin = Tile + ivec2(square % 64, square / 64);
    if (any(greaterThanEqual(origin + 1, textureSize(Survey, 0)))) return false;
    int side = gl_PrimitiveID % 2;
    uvec2 a = texelFetch(Survey, origin + ivec2(side), 0).rg;
    uvec2 b = texelFetch(Survey, origin + ivec2(0, 1), 0).rg;
    uvec2 c = texelFetch(Survey, origin + ivec2(1, 0), 0).rg;
    uint flags = a.r & b.r & c.r;
    mapped = (flags & 32u) != 0u;
    if ((flags & 64u) == 0u || (!mapped && HandoffRange <= 0.0)) return false;
    // The mapped terrain already uses the lower ground survey, including measured
    // cliff sides. Dropping a steep triangle here opens a view to the sky behind it.
    if (mapped) return true;
    // Outside the atlas we have only top-of-column samples, which can include
    // unsupported tree crowns even when each vertex has a natural material.
    uvec3 top = (uvec3(a.r, b.r, c.r) & 31u) * 256u + uvec3(a.g, b.g, c.g);
    return max(top.x, max(top.y, top.z)) - min(top.x, min(top.y, top.z)) <= uint(Grid.z * 2);
}

void main() {
    if (valid < 0.9999 || length(relative.xz) > 3072.0) discard;
    ivec2 p = ivec2(gl_FragCoord.xy);
    // The hole can expose a real, already drawn cavern wall hundreds of metres beyond the
    // missing hillside. Compare distances at this pixel, retaining nearer real geometry
    // and giving small surface differences to the full-resolution renderer.
    float eyeDepth = 1.0 / gl_FragCoord.w;
    float retained = eyeDepth + max(12.0, eyeDepth * 0.035);
    float limit = 0.5 * (1.0 - SceneZ.x + SceneZ.y / retained);
    float nativeZ = texelFetch(NativeDepth, p, 0).r;
    if (nativeZ < 1.0 && nativeZ <= limit) discard;
    if (HasDh) {
        float dhZ = texelFetch(DhDepth, p, 0).r;
        float sceneZ = dhZ * DhToScene.x + DhToScene.y;
        if (dhZ < 1.0 && sceneZ <= limit) {
            float distance = SceneZ.y / (2.0 * sceneZ - 1.0 + SceneZ.x);
            if (nativeZ < 1.0 || !aboveCanopy(Eye + relative * (distance / eyeDepth))) discard;
        }
    }
    bool mapped;
    if (!supportedTriangle(mapped)) discard;
    vec3 normal = normalize(cross(dFdx(relative), dFdy(relative)));
    normal *= normal.y < 0.0 ? -1.0 : 1.0;
    float shading = 0.56 + 0.35 * max(0.0, dot(normal, normalize(vec3(-0.4, 0.85, -0.35))));
    float distance = length(relative);
    vec3 surfaceColour = colour;
    float haze = 0.77 * smoothstep(180.0, 3300.0, distance);
    if (mapped) {
        // Sample the actual road, woodland and shore at the fragment position.
        // Interpolating three vertex colours smears a street over an entire triangle.
        vec2 uv = (Eye.xz + relative.xz - MapBounds.xy) / MapBounds.zw;
        surfaceColour = texture(GroundMap, uv).rgb;
        // This base appears in gaps in the native-to-DH fog transition.
        haze = max(haze, 0.50 * smoothstep(0.65 * NativeRange, 1.5 * NativeRange, distance));
    }
    fragColor = vec4(mix(surfaceColour * shading, Haze, haze), 1.0);
}
