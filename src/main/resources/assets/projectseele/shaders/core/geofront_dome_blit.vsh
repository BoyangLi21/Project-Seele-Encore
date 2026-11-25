#version 150

// R65 GeoFront far view under a shader pack: the far view's own target laid over the screen at the far plane.
in vec2 Position;

out vec2 texCoord;

void main() {
    gl_Position = vec4(Position, 1.0, 1.0);
    texCoord = Position * 0.5 + 0.5;
}
