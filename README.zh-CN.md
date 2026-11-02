[English](README.md) · **简体中文**

# AirliftSilence

一键开关 iPhone 的「通话录音」提示音（"本次通话正在被录音"）。

基于 [airlift](https://github.com/0xjohnnydev/airlift) 的 AirTraffic 沙盒逃逸做的一个 Windows 小工具：
把 iOS 在录音开始、结束时会播放的两个音频文件换成等长静音文件，随时可以还原。

> [!NOTE]
> 本项目大量借助 AI 完成，并且建立在其他人的工作之上 —— 见[致谢](#致谢)。

## 环境要求

- Windows（漏洞需要 `AirTrafficHost.dll`，由 Apple 的软件提供）
- 已安装 64 位 iTunes 或 Apple Mobile Device Support
- iPhone 用数据线连接、解锁，并已点击「信任此电脑」

已在 **iOS 27.0.1 (24A446)** 上完整验证 —— 读取、替换、还原全部通过，并且**重启后依然有效**。
iOS 27.0 (24A437) 应该也可以；更早的版本没有测试过。

> [!WARNING]
> **iOS 27.2 正式版（24B119）及更高版本已被修补。** Apple 在 2026-10-26 的安全更新中修复了
> 本工具依赖的 ATAirlock 路径校验漏洞（CVE-2026-112612）：设备仍会接受 AirTraffic 同步，
> 但会静默跳过所有文件移动，于是替换/读取会在几分钟后报 `could not read ...`。
> 这无法在软件层面解决 —— 本工具仅支持 iOS 27.0 / 27.0.1 及 iOS 27.2 beta 1–2。
> 在已修补的系统上，本工具现在会自动识别并直接给出明确提示，不再让您空等。

## 快速开始

### 直接下载 exe

到 [Releases](../../releases) 下载 `AirliftSilence.exe`，插上 iPhone、解锁，然后点按钮即可。
目标电脑不需要安装 Python。

「① 检查设备」查找手机并触发信任弹窗 ·
「② 去除提示音」备份原文件并写入静音文件 ·
「③ 恢复提示音」把原文件写回。

每一步都会从设备上把文件读回来校验，失败会明确报告而不是默默略过。
原版备份保存在 `%LOCALAPPDATA%\AirliftSilence\backup\`。

### 从源码运行

```sh
pip install pymobiledevice3
python airlift_gui.py          # 图形界面
python airlift.py              # 命令行，输出用法
```

打包 exe：

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --name AirliftSilence \
  --add-data "silent/StartDisclosureWithTone.m4a;silent" \
  --add-data "silent/StopDisclosure.caf;silent" \
  airlift_gui.py
```

## 工具会改动什么

| 文件 | 作用 | 静音替身 |
|---|---|---|
| `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a` | 开始录音时播放 | AAC 44.1 kHz 单声道，等长 1.834 秒 |
| `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf` | 结束录音时播放 | PCM s16le 48 kHz 单声道，等长 1.770 秒 |

两个替身文件都是用 ffmpeg 从 `anullsrc` 生成的纯数字静音，时长与原版一致，播放节奏不变。

录音提示音会播给**通话双方**，长时间录音还可能重复播报。去除后，对方将不再收到「正在被录音」的提示。

### 替换是怎么实现的

AirTraffic 的 `moveItemAtPath:toPath:` 不允许覆盖已存在的文件，所以替换采用
「先把旧文件挪到 Media，再通过重定向后的链接写入新文件」的两步走。`airlift.py replace`
就是这么做的：只有把旧文件成功读回来后才会删除它——读回失败时原版文件会留在 Media 里，不会被销毁。

## Grappa 修复（iOS 27.0.1）

iOS 27.0.1 上所有 airlift 家族的工具都只剩一个 `SyncFailed {ErrorCode: 4}`。设备日志写出了原因：

```
atc{AirTrafficDevice} <ERROR>: Grappa session could not be established. Aborting
```

设备在 `Capabilities` 消息里宣告 `GrappaSupportInfo`，随后拒绝任何 `HostInfo` 不带 `Grappa` 会话的同步。
Windows 版 `AirTrafficHost.dll` 不会自行建立会话（`ATHostConnectionGetGrappaSessionId` 返回 0），需要调用方主动带上。

token 不针对具体设备：它们是按 `(version=1, deviceType=0, protocolVersion=1)`（即 iOS 27 设备宣告的参数）
预生成的客户端 token，共十个，发布在 [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS)，也就是 `airlift.py`
里 `GRAPPA_TOKENS` 的内容；对 24A446 来说第一个就够用。

所以 27.0.1 并没有修掉漏洞，只是加了一道自带万能钥匙的门。

## iOS 27.2：已被修补

Apple 在 2026-10-26 的安全更新中修复了底层的 ATAirlock 路径校验漏洞
（CVE-2026-112612，"路径处理问题已通过改进的校验修复"）。从 iOS 27.2 正式版（24B119）起，
设备仍会接受 AirTraffic 同步——包括合法的 Grappa 会话——但不再执行任何被请求的文件移动。
同步 API 不会上报这一点，第一个可见的症状是几分钟后读回步骤报 `could not read ...`。

这在主机侧无法绕过：airlift 家族的其他项目（[AirCard](https://github.com/Mak5er/AirCard)、
[AirCard-Windows](https://github.com/dhava-gautama/AirCard-Windows)、
[AirBeep](https://github.com/LinkPass888/AirBeep)）都止步于 27.2 beta 2。
本工具现在会识别已修补的系统（27.2 正式版及更高版本；构建号 5xxx 的早期 27.2 beta 仍可用），
并快速给出明确提示，而不是白白跑一轮同步。

## 命令行用法

```sh
python airlift.py write   <ios_path> <local_file>              # 写入新文件
python airlift.py read    <ios_path> <output_file>             # 读取文件（先移出再移回）
python airlift.py replace <ios_path> <local_file> [--backup P]  # 覆盖已存在的文件
```

`--device UDID` 跳过设备选择，`--logging` 输出进度。

## 致谢

- [airlift](https://github.com/0xjohnnydev/airlift) —— Johnny Franks：最初的 macOS PoC 以及
  本文所依赖的 ATAirlock 分析
- [airlift-windows](https://github.com/DahanGuy/airlift-windows) —— Guy Dahan：基于 ctypes 调用
  `AirTrafficHost.dll` 的 Windows 移植版，本仓库即从它 fork
- [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) —— Mak5er：Grappa 客户端 token 与修复思路的来源
- [bl_sbx](https://github.com/h2zi/bl_sbx) —— 让这两个文件静音的先例

## 法律提示

在要求**全员同意**才能录音的法域（德国、美国部分州等），去除提示音可能违法。
无论手机播不播报，录音法规都适用于你——录音前请先取得对方同意。

本项目是面向自有设备安全研究的 proof-of-concept，利用的是一个真实的 iOS 漏洞；
Apple 随时可能修复它，未来的 iOS 更新也可能把被改动的文件恢复。
