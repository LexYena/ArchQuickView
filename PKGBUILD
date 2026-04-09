# Maintainer: LexYena <https://github.com/LexYena>
pkgname=quickview
pkgver=1.0.0
pkgrel=1
pkgdesc="macOS Quick Look for KDE Plasma 6 / Dolphin"
arch=('any')
url="https://github.com/LexYena/ArchQuickView"
license=('MIT')
depends=(
    'python'
    'python-pyqt6'
    'python-pyqt6-webengine'
    'poppler'            # pdftoppm — PDF preview
    'ffmpegthumbnailer'  # video thumbnails
    'ffmpeg'             # ffprobe for video dimensions + audio playback
    'python-pillow'      # fast image header reading
    'python-pygments'    # syntax highlighting for text/code
)
optdepends=(
    'python-mpv: video and audio playback'
)
source=("quickview.py"
        "quickview.desktop"
        "quickview-app.desktop")
sha256sums=('SKIP' 'SKIP' 'SKIP')

prepare() {
    # Write the app desktop file with correct install path
    cat > "$srcdir/quickview-app.desktop" << EOF
[Desktop Entry]
Type=Application
Name=QuickView
Icon=view-preview
Exec=python3 /usr/bin/quickview %F
StartupWMClass=quickview
NoDisplay=true
EOF
}

package() {
    # Main script
    install -Dm755 "$srcdir/quickview.py" "$pkgdir/usr/bin/quickview"

    # Dolphin service menu (system-wide)
    install -Dm644 "$srcdir/quickview.desktop" \
        "$pkgdir/usr/share/kio/servicemenus/quickview.desktop"

    # Fix Exec path in service menu
    sed -i "s|Exec=python3 .*quickview|Exec=python3 /usr/bin/quickview|g" \
        "$pkgdir/usr/share/kio/servicemenus/quickview.desktop"

    # Application entry
    install -Dm644 "$srcdir/quickview-app.desktop" \
        "$pkgdir/usr/share/applications/quickview.desktop"
}
