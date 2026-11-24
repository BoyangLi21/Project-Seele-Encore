#version 150

// R65 GeoFront far view under a shader pack: the silhouette's own target laid over the screen at the far plane.
in vec3 Position;
in vec2 UV0;

out vec2 texCoord;

void main() {
    gl_Position = vec4(Position.xy, 1.0, 1.0);
    texCoord = UV0;
}
