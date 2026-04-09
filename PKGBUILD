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
    'poppler'
    'ffmpegthumbnailer'
    'ffmpeg'
    'python-pillow'
    'python-pygments'
)
optdepends=(
    'python-mpv: video and audio playback'
)
source=("$pkgname-$pkgver.tar.gz::https://github.com/LexYena/ArchQuickView/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
    cd "ArchQuickView-$pkgver"

    # Main script
    install -Dm755 quickview.py "$pkgdir/usr/bin/quickview"

    # Dolphin service menu
    install -Dm644 quickview.desktop \
        "$pkgdir/usr/share/kio/servicemenus/quickview.desktop"
    sed -i "s|Exec=python3 [^ ]*quickview|Exec=python3 /usr/bin/quickview|g" \
        "$pkgdir/usr/share/kio/servicemenus/quickview.desktop"

    # Application entry
    install -Dm644 /dev/stdin \
        "$pkgdir/usr/share/applications/quickview.desktop" << EOF
[Desktop Entry]
Type=Application
Name=QuickView
Icon=view-preview
Exec=python3 /usr/bin/quickview %F
StartupWMClass=quickview
NoDisplay=true
EOF

    # License
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
