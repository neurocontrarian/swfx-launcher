#!/bin/sh
# Builds swfx-launcher_<version>_all.deb into dist/.
#
# Needs only dpkg-deb and gzip, both present on any Debian or Ubuntu based
# system. Run from the repository root:
#
#     ./build-deb.sh
#
set -eu

here=$(dirname "$0")
cd "$here"

version=$(sed -n 's/^Version: //p' packaging/control)
pkg="swfx-launcher_${version}_all"
tree="dist/$pkg"

rm -rf "$tree"
mkdir -p "$tree/DEBIAN" \
         "$tree/usr/bin" \
         "$tree/usr/share/applications" \
         "$tree/usr/share/doc/swfx-launcher"

# The script is installed without its .py extension, as a normal command.
install -m 755 swfx-launcher.py "$tree/usr/bin/swfx-launcher"
install -m 644 packaging/control "$tree/DEBIAN/control"
install -m 644 packaging/swfx-launcher.desktop \
               "$tree/usr/share/applications/swfx-launcher.desktop"
install -m 644 packaging/copyright "$tree/usr/share/doc/swfx-launcher/copyright"
install -m 644 README.md "$tree/usr/share/doc/swfx-launcher/README.md"

# Debian policy wants a compressed changelog.
printf 'swfx-launcher (%s) unstable; urgency=low\n\n  * Packaged release.\n\n -- %s  %s\n' \
    "$version" \
    "$(sed -n 's/^Maintainer: //p' packaging/control)" \
    "$(date -R)" \
    | gzip -9n > "$tree/usr/share/doc/swfx-launcher/changelog.Debian.gz"
chmod 644 "$tree/usr/share/doc/swfx-launcher/changelog.Debian.gz"

# --root-owner-group avoids needing fakeroot for correct root:root ownership.
dpkg-deb --root-owner-group --build "$tree" > /dev/null
rm -rf "$tree"

echo "dist/$pkg.deb"
