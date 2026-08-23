#!/bin/bash
set -e

# Start D-Bus session (used by Chromium/Firefox inside the container).
mkdir -p /home/chat/.dbus
export DBUS_SESSION_BUS_ADDRESS="unix:path=/home/chat/.dbus/session-bus"
dbus-daemon --session --address="${DBUS_SESSION_BUS_ADDRESS}" --nofork --nopidfile &

# Start X virtual framebuffer.
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

# Start a lightweight window manager.
openbox &

# Start VNC server.
mkdir -p /home/chat/.vnc
x11vnc -forever -nopw -display :99 -rfbport 5900 &

# Start noVNC WebSocket proxy.
websockify --web /usr/share/novnc 6080 localhost:5900 &

# Keep container alive and ready for `podman exec` agent commands.
exec tail -f /dev/null
