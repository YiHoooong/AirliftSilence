# AirliftSilence

One-click switch for the iPhone call-recording announcement ("this call is being recorded").

A small Windows GUI on top of the [airlift](https://github.com/0xjohnnydev/airlift) AirTraffic
sandbox escape. It replaces the two audio files iOS plays when call recording starts and stops
with silent stand-ins, and can put the originals back.

> [!NOTE]
> Built with heavy AI assistance, and standing on other people's work — see [Credits](#credits).

## Requirements

- Windows (the exploit needs `AirTrafficHost.dll`, which ships with Apple's software)
- 64-bit iTunes or Apple Mobile Device Support installed
- A paired iPhone over USB, unlocked, with "Trust This Computer" accepted

Verified end to end on **iOS 27.0.1 (24A446)** — read, replace, restore, and it survives a reboot.
iOS 27.0 (24A437) should work; older versions are untested.

## Quick start

### Standalone executable

Download `AirliftSilence.exe` from [Releases](../../releases), plug in the iPhone, unlock it, and
press the buttons. No Python required on the target machine.

`① Check device` finds the phone and triggers the trust prompt ·
`② Remove sound` backs up the originals and writes the silent files ·
`③ Restore sound` puts the originals back.

Every step is verified by reading the file back off the device, so a failure is reported instead of
being silently ignored. Backups live in `%LOCALAPPDATA%\AirliftSilence\backup\`.

### From source

```sh
pip install pymobiledevice3
python airlift_gui.py          # GUI
python airlift.py              # CLI, prints usage
```

Building the exe:

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --name AirliftSilence \
  --add-data "silent/StartDisclosureWithTone.m4a;silent" \
  --add-data "silent/StopDisclosure.caf;silent" \
  airlift_gui.py
```

## What it touches

| File | Role | Silent stand-in |
|---|---|---|
| `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a` | played when recording starts | AAC 44.1 kHz mono, same 1.834 s duration |
| `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf` | played when recording stops | PCM s16le 48 kHz mono, same 1.770 s duration |

Both stand-ins are generated from `anullsrc` with ffmpeg — plain digital silence, nothing else. The
durations match the originals so playback timing is unchanged.

iOS plays the start announcement to **both parties** on the call, and may repeat it during a long
recording. Removing it means the other party is no longer told they are being recorded.

### How the swap works

AirTraffic's `moveItemAtPath:toPath:` refuses to overwrite an existing file, so a replacement is
"move the old file out to Media, then write the new one through the relocated link". `airlift.py
replace` does exactly that, and only deletes the old copy once it has been read back — a failed
readback leaves the original in Media rather than destroying it.

## The Grappa fix (iOS 27.0.1)

Every airlift-family tool stopped working on iOS 27.0.1 with nothing but
`SyncFailed {ErrorCode: 4}`. The device's own log says why:

```
atc{AirTrafficDevice} <ERROR>: Grappa session could not be established. Aborting
```

The device advertises `GrappaSupportInfo` in its `Capabilities` message and then refuses any sync
whose `HostInfo` carries no `Grappa` session. Apple's `AirTrafficHost.dll` does not establish one on
its own (`ATHostConnectionGetGrappaSessionId` returns 0) — the caller is expected to drive it.

The tokens are **not device-specific**: they are pre-generated client tokens for
`(version=1, deviceType=0, protocolVersion=1)`, which is what iOS 27 devices advertise. Ten of them
are published in [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) and are what `GRAPPA_TOKENS`
in `airlift.py` uses; the first one is enough for 24A446.

So 27.0.1 did not remove the vulnerability — it added a check that ships with a reusable key.

## CLI

```sh
python airlift.py write   <ios_path> <local_file>              # write a new file
python airlift.py read    <ios_path> <output_file>             # read a file (moves it out and back)
python airlift.py replace <ios_path> <local_file> [--backup P]  # overwrite an existing file
```

`--device UDID` skips the device picker, `--logging` prints progress.

## Credits

- [airlift](https://github.com/0xjohnnydev/airlift) — Johnny Franks: the original macOS PoC and the
  ATAirlock analysis this all rests on
- [airlift-windows](https://github.com/DahanGuy/airlift-windows) — Guy Dahan: the Windows port using
  `AirTrafficHost.dll` via ctypes, which this repository is forked from
- [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) — Mak5er: where the Grappa client tokens and
  the shape of the fix come from
- [bl_sbx](https://github.com/h2zi/bl_sbx) — prior art for silencing these two files

## Legal

Removing the announcement may be illegal where call recording requires **all-party consent**
(Germany, several US states, and others). Recording laws apply to you regardless of what your phone
does or does not announce — get consent before recording anyone.

This is a proof-of-concept for security research on hardware you own. It abuses a real iOS
vulnerability; Apple can fix it at any time, and the files may be restored by a future iOS update.

## 中文说明

一键开关 iPhone 的「通话录音」提示音。基于 [airlift](https://github.com/0xjohnnydev/airlift) 的
AirTraffic 沙盒逃逸，把 iOS 在录音开始/结束时播放的两个音频文件换成等长静音文件，可随时还原。

- **要求**：Windows + 已安装 iTunes / Apple Mobile Device Support；iPhone 用数据线连接、解锁并信任
- **实测**：iOS 27.0.1 (24A446)，读写/替换/还原全部通过，重启后依然有效
- **用法**：下载 Releases 里的 exe 双击，或 `python airlift_gui.py`。三个按钮：检查设备、去除提示音、恢复提示音
- **备份**：`%LOCALAPPDATA%\AirliftSilence\backup\`，随时可还原
- **注意**：提示音是**双方都能听到**的告知。在要求「双方同意」才能录音的法域（德国、美国部分州等），
  去掉它可能违法。录音前请先取得对方同意。
