#!/bin/sh
# Sets the package version everywhere it appears.
#
# The version lives in packaging/control, which build-deb.sh reads, but the
# README also spells out the file name in its install commands. This keeps
# the two in step:
#
#     ./set-version.sh 0.2.0
#
# Then commit, tag, and publish:
#
#     git commit -am "Release 0.2.0" && git tag -a v0.2.0 -m "swfx-launcher 0.2.0"
#     git push origin main --follow-tags
#     ./build-deb.sh && gh release create v0.2.0 dist/swfx-launcher_0.2.0_all.deb
set -eu

if [ $# -ne 1 ]; then
    echo "usage: $0 <version>   (for example 0.2.0)" >&2
    exit 2
fi
new=$1

# Debian refuses a version that does not start with a digit; keep to the
# digits-and-dots form the package already uses.
if ! printf '%s' "$new" | grep -qE '^[0-9]+(\.[0-9]+)*$'; then
    echo "$0: '$new' is not a version of the form 1.2.3" >&2
    exit 2
fi

here=$(dirname "$0")
cd "$here"

old=$(sed -n 's/^Version: //p' packaging/control)
if [ -z "$old" ]; then
    echo "$0: no Version field in packaging/control" >&2
    exit 1
fi

if [ "$old" = "$new" ]; then
    echo "already at $new"
    exit 0
fi

sed -i "s/^Version: $old\$/Version: $new/" packaging/control
sed -i "s/swfx-launcher_${old}_all\.deb/swfx-launcher_${new}_all.deb/g" README.md

# Nothing should still name the previous version.
if grep -rn "swfx-launcher_${old}_all\.deb\|^Version: $old\$" README.md packaging/control; then
    echo "$0: some occurrences of $old were left behind" >&2
    exit 1
fi

echo "$old -> $new"
grep -c "swfx-launcher_${new}_all\.deb" README.md | sed 's/^/README.md occurrences: /'
