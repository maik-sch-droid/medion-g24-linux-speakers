#!/bin/sh
# SPDX-License-Identifier: 0BSD
set -eu
export LC_ALL=C
umask 022

if [ "$#" -gt 1 ]; then
    echo 'Usage: build.sh [output-directory]' >&2
    exit 2
fi
source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
destination=${1:-"$source_dir/dist"}
mkdir -p -- "$destination"
output_dir=$(CDPATH='' cd -- "$destination" && pwd -P)
work_dir=$(mktemp -d "$output_dir/.medion-build.XXXXXXXX")
trap 'rm -r -- "$work_dir"' EXIT
trap 'exit 1' HUP INT TERM

name=medion-g24-speakers
stage="$work_dir/package"
units="$stage/usr/lib/systemd/system"
docs="$stage/usr/share/doc/$name"
install -d "$stage/DEBIAN" "$stage/usr/libexec" "$units" "$docs"
install -m 0755 "$source_dir/$name.py" "$stage/usr/libexec/$name"
install -m 0644 "$source_dir/$name.service" "$source_dir/$name.timer" "$units/"
install -m 0644 "$source_dir/README.md" "$docs/README.md"
install -m 0644 "$source_dir/LICENSE" "$docs/copyright"
install -m 0644 "$source_dir/packaging/control" "$stage/DEBIAN/control"
for script in postinst prerm postrm; do
    install -m 0755 "$source_dir/packaging/$script" "$stage/DEBIAN/$script"
done

(cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum > DEBIAN/md5sums)
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1795392000}
export SOURCE_DATE_EPOCH
find "$stage" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
version=$(sed -n 's/^Version: //p' "$stage/DEBIAN/control")
artifact="${name}_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$stage" "$work_dir/$artifact"
mv -- "$work_dir/$artifact" "$output_dir/$artifact"
printf '%s\n' "$output_dir/$artifact"
