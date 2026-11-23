#!/usr/bin/python3 -I
# SPDX-License-Identifier: 0BSD
"""Apply the measured Medion G24 internal-speaker setting during startup."""
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

SYS = Path("/sys")
DMI = {"sys_vendor": "Medion", "product_name": "G24", "board_vendor": "Medion",
       "board_name": "H61H2-TI2", "board_version": "1.0", "bios_version": "H61TIW08.111"}
MUTED_WORD = 0x1F9B
SPEAKER_WORD = MUTED_WORD | (1 << 13)
I2C_SLAVE = 0x0703
I2C_SMBUS = 0x0720
WORD_DATA = 3
RETRY_SECONDS = 10
WAIT_SECONDS = 1200


class Unsupported(Exception):
    """Leave this system untouched."""


class NotReady(Exception):
    """Wait for devices which can appear later during startup."""


class SMBusData(ctypes.Union):
    _fields_ = [("word", ctypes.c_uint16), ("block", ctypes.c_ubyte * 34)]


class SMBusRequest(ctypes.Structure):
    _fields_ = [("direction", ctypes.c_ubyte), ("command", ctypes.c_ubyte),
                ("size", ctypes.c_uint32), ("data", ctypes.POINTER(SMBusData))]


def read_attr(directory, name):
    return (directory / name).read_text().strip()


def check_dmi():
    directory = SYS / "class/dmi/id"
    if any(read_attr(directory, key) != expected for key, expected in DMI.items()):
        raise Unsupported("DMI or BIOS outside the tested Medion G24 configuration")


def hardware():
    pci = SYS / "bus/pci/devices"
    hda = pci / "0000:00:1b.0"
    smbus = pci / "0000:00:1f.3"
    for device, address_id in ((hda, "0x1c20"), (smbus, "0x1c22")):
        if (read_attr(device, "vendor"), read_attr(device, "device")) != ("0x8086", address_id):
            raise Unsupported("PCI controller IDs differ from the tested configuration")
    codecs = [p for p in (SYS / "bus/hdaudio/devices").glob("hdaudioC*D0")
              if p.resolve().is_relative_to(hda.resolve())]
    if not codecs:
        raise NotReady("awaiting the analog codec")
    if len(codecs) != 1 or tuple(read_attr(codecs[0], attr) for attr in
            ("vendor_id", "subsystem_id", "revision_id")) != ("0x10ec0662", "0x10197c94", "0x100300"):
        raise Unsupported("analog codec identity differs from the tested configuration")
    if (smbus / "driver").resolve().name != "i801_smbus":
        raise NotReady("awaiting the Intel i801 driver")
    adapters = [p for p in (SYS / "class/i2c-dev").glob("i2c-*")
                if (p / "device").resolve().parent == smbus.resolve()]
    if not adapters:
        raise NotReady("awaiting the i2c-dev interface for the Intel SMBus")
    if len(adapters) != 1:
        raise Unsupported("ambiguous SMBus adapter")
    return adapters[0]


def word_transaction(fd, write=False):
    data = SMBusData()
    if write:
        data.word = SPEAKER_WORD
    request = SMBusRequest(0 if write else 1, 0x01, WORD_DATA, ctypes.pointer(data))
    fcntl.ioctl(fd, I2C_SMBUS, request)
    return data.word


def apply(adapter, check_only):
    path = Path("/dev") / adapter.name
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        node = os.fstat(fd)
        if not stat.S_ISCHR(node.st_mode) or read_attr(adapter, "dev") != f"{os.major(node.st_rdev)}:{os.minor(node.st_rdev)}":
            raise Unsupported("device node does not match the identified adapter")
        fcntl.ioctl(fd, I2C_SLAVE, 0x10)  # Respect kernel ownership of this address.
        initial = word_transaction(fd)
        if initial == SPEAKER_WORD:
            return "already enabled (0x3f9b)"
        if initial != MUTED_WORD:
            raise Unsupported(f"unexpected register word 0x{initial:04x}; skipped")
        if check_only:
            return "observed muted word (0x1f9b); check only"
        if word_transaction(fd) != MUTED_WORD:
            raise NotReady("register changed during verification")
        word_transaction(fd, write=True)
        observed = word_transaction(fd)
        if observed != SPEAKER_WORD:
            raise RuntimeError(f"readback after correction was 0x{observed:04x}")
        return "applied 0x1f9b -> 0x3f9b; verified by readback"
    finally:
        os.close(fd)


def main(args):
    if args not in ([], ["--check"], ["--prepare"]):
        print("Usage: medion-g24-speakers [--check]", file=sys.stderr)
        return 2
    check_only = bool(args)
    try:
        check_dmi()
        if args == ["--prepare"]:
            if not (SYS / "class/i2c-dev").exists():
                return subprocess.run(["/usr/sbin/modprobe", "i2c-dev"], check=False).returncode
            return 0
        deadline = time.monotonic() + WAIT_SECONDS
        warned = False
        while True:
            try:
                print(apply(hardware(), check_only), flush=True)
                return 0
            except (NotReady, OSError) as exc:
                if isinstance(exc, OSError) and exc.errno not in (
                    errno.ENOENT, errno.ENXIO, errno.ENODEV, errno.EREMOTEIO, errno.EAGAIN, errno.ETIMEDOUT):
                    raise
                if check_only or time.monotonic() >= deadline:
                    raise RuntimeError(f"device unavailable: {exc}") from exc
                if not warned:
                    print(f"Waiting for hardware: {exc}", flush=True)
                    warned = True
                time.sleep(RETRY_SECONDS)
    except Unsupported as exc:
        print(f"Skipped: {exc}", flush=True)
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"Speaker correction incomplete: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
