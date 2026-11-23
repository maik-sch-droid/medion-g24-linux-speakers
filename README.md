# Medion G24 internal speakers

On the tested Medion G24, Linux played audio after a cold boot, but the internal speakers produced only noise or silence. A previous Ubuntu user reported that suspending and waking the same model restored the speakers. This package applies a hardware-specific correction during startup. [Original Ubuntu report](https://bugs.launchpad.net/bugs/1406097)

## Hardware

The correction was measured on one Medion G24 running Kubuntu 26.04.1 with kernel `7.0.0-43-generic`.

| Component | Tested configuration |
| --- | --- |
| Mainboard | Medion H61H2-TI2, revision 1.0 |
| BIOS | H61TIW08.111 |
| SMBus controller | Intel 8086:1c22 |
| Audio controller | Intel HDA 8086:1c20 |
| Analog codec | Realtek ALC662 rev3, 10ec:0662, subsystem 1019:7c94 |

## What was measured

During a cold boot with silent speakers, SMBus register `0x01` on the board device at 7-bit address `0x10` read `0x1F9B`. Setting bit 13 changed the word to `0x3F9B`. Readback confirmed that value. The internal microphone then picked up the test melody from both speaker channels. The display stayed on and the computer remained awake.

In a separate experiment with working speakers, clearing the same bit made the acoustic melody disappear while the digital output monitor continued to detect it. Restoring the bit brought the melody back. This establishes control of the speaker output on the tested unit. The identity of the board chip and the reason the bit starts clear are still open.

The cold-start experiment used a diagnostic program. This release packages its confirmed register change as a standalone startup service. Validation on additional machines and kernel versions is welcome.

## Install on Kubuntu

Download the Debian package from the release page. Open a terminal in the directory containing the file and run

```sh
sudo apt install ./medion-g24-speakers_0.1.0_all.deb
```

The package uses Linux's I²C device interface. It installs a Python helper and a systemd timer independently of the distribution kernel. The timer is scheduled for 20 seconds after boot. The helper checks the hardware identity, locates the matching adapter, and writes only after it reads the exact known silent word. It verifies the resulting word. If the adapter or device is temporarily unavailable, retries are bounded. An already-correct value needs no write. Startup uses no microphone and plays no test sound.

To run the correction immediately and inspect what happened in this boot, use

```sh
sudo systemctl start medion-g24-speakers.service
journalctl -b -u medion-g24-speakers.service --no-pager
```

The service exits after the check. To inspect the timer, run `systemctl status medion-g24-speakers.timer`. To uninstall, run `sudo apt purge medion-g24-speakers`. Removal stops future automatic corrections. A value already applied to the hardware can persist for the current session.

## Kurz auf Deutsch

Lade das Debian-Paket herunter und öffne im Downloadordner ein Terminal. Installiere es einmal mit `sudo apt install ./medion-g24-speakers_0.1.0_all.deb`. Beim Start prüft der Dienst den Wert auf der unterstützten Platine. Du kannst die Korrektur sofort mit `sudo systemctl start medion-g24-speakers.service` ausführen und danach Musik über die internen Lautsprecher abspielen. Mit `sudo apt purge medion-g24-speakers` entfernst du das Paket.

## Build from source

From the extracted source directory run `./build.sh` on a Debian-family system with `dpkg-deb`. An optional argument selects the output directory. The source is released under the BSD Zero Clause License (0BSD).
