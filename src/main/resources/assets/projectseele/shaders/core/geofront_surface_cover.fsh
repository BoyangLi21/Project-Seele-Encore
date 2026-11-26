#version 150

uniform sampler2D NativeDepth;
uniform sampler2D DhDepth;
uniform bool HasDh;
uniform vec2 SceneZ;
uniform vec2 DhToScene;
uniform vec3 Haze;
uniform usampler2D Survey;
uniform ivec4 Grid;
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
        uint y = (s.r & 127u) * 256u + s.g;
        if (y == 0u) return false;
        highest = max(highest, y);
    }
    return hit.y > float(Grid.w) + float(highest) + 7.0;
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
    vec3 normal = normalize(cross(dFdx(relative), dFdy(relative)));
    normal *= normal.y < 0.0 ? -1.0 : 1.0;
    float shading = 0.56 + 0.35 * max(0.0, dot(normal, normalize(vec3(-0.4, 0.85, -0.35))));
    float fog = smoothstep(180.0, 3300.0, length(relative));
    fragColor = vec4(mix(colour * shading, Haze, 0.77 * fog), 1.0);
}
