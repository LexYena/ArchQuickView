#!/usr/bin/env bash
set -e

# ── QuickView installer ────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing dependencies (requires sudo)..."
sudo pacman -S --needed --noconfirm \
    python-pyqt6 \
    python-pyqt6-webengine \
    poppler \
    ffmpegthumbnailer \
    ffmpeg \
    python-pillow \
    python-pygments

# python-mpv is optional (for media playback); skip if unavailable
if pacman -Ss '^python-mpv$' &>/dev/null; then
    sudo pacman -S --needed --noconfirm python-mpv
else
    echo "  [!] python-mpv not found in repos — media playback will be disabled"
    echo "      Install from AUR: yay -S python-mpv"
fi

echo ""
echo "==> Copying quickview to ~/.local/bin/..."
mkdir -p "$HOME/.local/bin"
cp "$SCRIPT_DIR/quickview.py" "$HOME/.local/bin/quickview"
chmod +x "$HOME/.local/bin/quickview"

echo "==> Installing Dolphin service menu..."
MENU_DIR="$HOME/.local/share/kio/servicemenus"
mkdir -p "$MENU_DIR"
# Write desktop file with the resolved absolute path
cat > "$MENU_DIR/quickview.desktop" << EOF
[Desktop Entry]
Type=Service
ServiceTypes=KonqPopupMenu/Plugin
MimeType=all/all;
Actions=quickview_action
X-KDE-Priority=TopLevel

[Desktop Action quickview_action]
Name=Quick View
Name[ru]=Быстрый просмотр
Icon=view-preview
Exec=python3 $HOME/.local/bin/quickview %F
EOF

echo "==> Installing application entry..."
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/quickview.desktop" << EOF
[Desktop Entry]
Type=Application
Name=QuickView
Icon=view-preview
Exec=python3 $HOME/.local/bin/quickview %F
StartupWMClass=quickview
NoDisplay=true
EOF

echo "==> Installing KWin rule (center + no shadow)..."
KWIN_CFG="$HOME/.config/kwinrulesrc"
if ! grep -q "wmclass=quickview" "$KWIN_CFG" 2>/dev/null; then
    RULE_ID="$(cat /proc/sys/kernel/random/uuid)"
    # Read existing count
    EXISTING=$(grep -Po '(?<=count=)\d+' "$KWIN_CFG" 2>/dev/null || echo "0")
    NEW_COUNT=$((EXISTING + 1))
    EXISTING_RULES=$(grep -Po '(?<=rules=)\S+' "$KWIN_CFG" 2>/dev/null || echo "")

    if [ -n "$EXISTING_RULES" ]; then
        RULES_LINE="$EXISTING_RULES,$RULE_ID"
    else
        RULES_LINE="$RULE_ID"
    fi

    # Update General section
    if grep -q "^\[General\]" "$KWIN_CFG" 2>/dev/null; then
        sed -i "s/^count=.*/count=$NEW_COUNT/" "$KWIN_CFG"
        sed -i "s/^rules=.*/rules=$RULES_LINE/" "$KWIN_CFG"
    else
        printf "[General]\ncount=%s\nrules=%s\n\n" "$NEW_COUNT" "$RULES_LINE" >> "$KWIN_CFG"
    fi

    cat >> "$KWIN_CFG" << EOF

[$RULE_ID]
Description=QuickView center + no shadow
placement=5
placementrule=3
noshadow=true
noshadowrule=3
wmclass=quickview
wmclasscomplete=false
wmclassmatch=1
types=0
EOF
    echo "  KWin rule added — reload KWin to apply: qdbus org.kde.KWin /KWin reconfigure"
else
    echo "  KWin rule already present, skipping."
fi

# Make sure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    echo "  NOTE: Add ~/.local/bin to your PATH:"
    echo "    fish:  fish_add_path ~/.local/bin"
    echo "    bash:  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Done! Restart Dolphin for the service menu to appear."
echo ""
echo "Usage:"
echo "  quickview <file>          — from terminal"
echo "  Right-click in Dolphin → Quick View"
echo "  Space key in Dolphin     — if keyboard shortcut is configured"
echo ""
echo "Optional: assign Space as keyboard shortcut:"
echo "  Dolphin → Settings → Configure Keyboard Shortcuts → search 'Quick View'"
