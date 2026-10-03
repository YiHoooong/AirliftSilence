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

## 快速开始

### 直接下载 exe

到 [Releases](../../releases) 下载 `AirliftSilence.exe`，插上 iPhone、解锁，然后点按钮即可。
目标电脑不需要安装 Python。

「① 检查设备」查找手机并触发信任弹窗 ·
「② 去除提示音」备份原文件并写入静音文件 ·
「③ 恢复提示音」把原文件放回去。

每一步都会**把文件读回本地校验**，所以失败会明确报错，而不是假装成功。
原版备份存放在 `%LOCALAPPDATA%\AirliftSilence\backup\`。

### 从源码运行

```sh
pip install pymobiledevice3
python airlift_gui.py          # 图形界面
python airlift.py              # 命令行，直接运行会打印用法
```

自己打包 exe：

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --name AirliftSilence \
  --add-data "silent/StartDisclosureWithTone.m4a;silent" \
  --add-data "silent/StopDisclosure.caf;silent" \
  airlift_gui.py
```

## 改动了哪两个文件

| 文件 | 作用 | 替换成的静音文件 |
|---|---|---|
| `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a` | 录音开始时播放 | AAC 44.1 kHz 单声道，时长同样 1.834 秒 |
| `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf` | 录音结束时播放 | PCM s16le 48 kHz 单声道，时长同样 1.770 秒 |

两个静音文件都是用 ffmpeg 的 `anullsrc` 生成的，就是纯数字静音，没有别的东西。
时长和原文件对齐，所以播放时机不会变。

录音开始时那段提示音，**通话双方都能听到**，而且长时间录音时可能还会重复播放。
去掉它，就意味着对方不再被告知自己正在被录音。

### 替换是怎么实现的

AirTraffic 的 `moveItemAtPath:toPath:` 不允许覆盖已存在的文件，所以"替换"实际上是
**先把旧文件搬到 Media，再通过搬过去的软链接写入新文件**。`airlift.py replace` 就是这么做的，
而且**只有在旧文件被成功读回本地之后才会删除它** —— 万一读回失败，原文件会留在 Media 里而不是被销毁。

## Grappa 修复（iOS 27.0.1）

airlift 系的所有工具在 iOS 27.0.1 上都失效了，报错只有一句 `SyncFailed {ErrorCode: 4}`。
设备自己的日志才说得出原因：

```
atc{AirTrafficDevice} <ERROR>: Grappa session could not be established. Aborting
```

设备会在 `Capabilities` 消息里通告 `GrappaSupportInfo`，然后拒绝任何 `HostInfo` 中
不带 Grappa 会话的同步请求。而 Apple 的 `AirTrafficHost.dll` 自己**不会**建立这个会话
（`ATHostConnectionGetGrappaSessionId` 返回 0）—— 它期望由调用方来驱动。

这些令牌**不是每台设备一份**：它们是为 `(version=1, deviceType=0, protocolVersion=1)`
预生成的客户端令牌，而这正是 iOS 27 设备广播的参数。
[AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) 公开了 10 个，`airlift.py` 里的
`GRAPPA_TOKENS` 用的就是它们；在 24A446 上第一个就够了。

所以说，**27.0.1 并没有修掉这个漏洞** —— 它只是加了一道锁，而钥匙是通用的。

## 命令行

```sh
python airlift.py write   <ios_path> <local_file>              # 写入新文件
python airlift.py read    <ios_path> <output_file>             # 读取文件（会移出再移回）
python airlift.py replace <ios_path> <local_file> [--backup P]  # 覆盖已存在的文件
```

`--device UDID` 跳过设备选择，`--logging` 打印过程日志。

## 致谢

- [airlift](https://github.com/0xjohnnydev/airlift) —— Johnny Franks：最初的 macOS PoC，
  以及这一切所依赖的 ATAirlock 分析
- [airlift-windows](https://github.com/DahanGuy/airlift-windows) —— Guy Dahan：用 ctypes 调用
  `AirTrafficHost.dll` 的 Windows 移植版，本仓库 fork 自它
- [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) —— Mak5er：Grappa 客户端令牌和修复思路的来源
- [bl_sbx](https://github.com/h2zi/bl_sbx) —— 替换这两个文件的先行者

## 法律

在要求**双方同意**才能录音的法域（德国、美国部分州等），去掉这个提示音可能违法。
无论你的手机是否播报告知，录音相关的法律都适用于你 —— 录音前请先取得对方同意。

这是一个针对自有设备做安全研究的概念验证工具。它利用的是真实的 iOS 漏洞，
Apple 随时可以修复，而且这些文件也可能在未来的 iOS 更新中被还原。
