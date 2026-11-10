"""airlift 图形界面 —— 一键开关通话录音提示音。

傻瓜式封装，四个按钮：检查设备/授权、去除提示音、恢复提示音、救援残留文件。
依赖同目录的 airlift.py，以及 Windows 上已安装的 Apple Mobile Device Support。
"""

from __future__ import annotations

import asyncio
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

import airlift

GREETINGS = "/var/mobile/Library/CallServices/Greetings/default"
TARGETS = (
    ("StartDisclosureWithTone.m4a", "开始录音提示音"),
    ("StopDisclosure.caf", "结束录音提示音"),
)
APP_NAME = "通话录音提示音开关"


def base_dir() -> Path:
    """Bundled data lives next to the script, or in PyInstaller's temp dir."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def silent_file(name: str) -> Path:
    return base_dir() / "silent" / name


def backup_file(name: str) -> Path:
    folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AirliftSilence" / "backup"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


# ── device ───────────────────────────────────────────────────────────────────

def check_device() -> dict:
    async def go():
        devices = await airlift.list_mux_devices()
        if not devices:
            raise airlift.AirLiftError(
                "没有检测到 USB 设备。\n请用数据线连接 iPhone，解锁屏幕，"
                "并在手机上点击「信任此电脑」。"
            )
        dev = await airlift._resolve_device()
        return {
            "name": dev["name"],
            "product": dev["product"],
            "version": dev["version"],
            "build": dev["build"],
            "tested": dev["tested"],
            "udid": dev["udid"],
        }
    return asyncio.run(go())


def ensure_firmware(info: dict) -> None:
    """Fail fast on firmware builds where the move has been patched."""
    if airlift.firmware_patched(info["version"]):
        raise airlift.AirLiftError(
            f"iOS {info['version']} 已修补 AirTraffic 资产搬运（CVE-2026-112612）。\n"
            "这个工具在该版本上无法使用；设备不会有任何文件被修改。"
        )


# ── operations ───────────────────────────────────────────────────────────────

def remove_sounds(log) -> None:
    ensure_firmware(check_device())
    for name, label in TARGETS:
        path = f"{GREETINGS}/{name}"
        source = silent_file(name)
        if not source.is_file():
            raise airlift.AirLiftError(f"缺少内置静音文件 {source}")

        silent = source.read_bytes()
        log(f"[{label}] 正在替换（约 1 分钟）…")
        previous = airlift.replace_file(path, silent)

        backup = backup_file(name)
        if previous is None:
            log(f"[{label}] ⚠ 没能读回被移走的文件：")
            log(f"[{label}]   原因可能是设备上原本没有这个文件，或设备拒绝了搬运（疑似已修补，"
                "请先看 ① 检查设备 的提示）。移出的文件滞留在 Media 暂存区，")
            log(f"[{label}]   点击「④ 救援」可以认领并放回。")
        elif previous == silent:
            log(f"[{label}] 设备上本来就是静音版")
            if not backup.is_file():
                log(f"[{label}] ⚠ 没有可用的原版备份，恢复功能将不可用")
        elif not backup.is_file():
            backup.write_bytes(previous)
            log(f"[{label}] 原文件已备份（{len(previous)} 字节）")
        else:
            log(f"[{label}] 已存在备份，未覆盖")

        log(f"[{label}] 正在校验写入结果（约 1 分钟）…")
        if airlift.read_file(path) != silent:
            raise airlift.AirLiftError(f"{label}：校验失败，设备上不是静音文件")
        log(f"[{label}] ✓ 完成")


def restore_sounds(log) -> None:
    ensure_firmware(check_device())
    for name, label in TARGETS:
        path = f"{GREETINGS}/{name}"
        backup = backup_file(name)
        if not backup.is_file():
            log(f"[{label}] 本地没有原版备份，尝试从 Media 暂存区救援…")
            found = airlift.rescue_files(log)
            for entry in found:
                if (entry.get("target", "").endswith(name)
                        and entry.get("restored") and entry.get("data")):
                    backup.write_bytes(entry["data"])
                    log(f"[{label}] 已从暂存区恢复原文件，并将其保存为本地备份")
                    break
            else:
                raise airlift.AirLiftError(
                    f"{label}：找不到原版备份，暂存区也没有可救援的文件。\n"
                    f"恢复需要先前用本工具备份过的文件：{backup}"
                )

        original = backup.read_bytes()
        log(f"[{label}] 正在恢复（约 1 分钟）…")
        airlift.replace_file(path, original)
        log(f"[{label}] 正在校验（约 1 分钟）…")
        if airlift.read_file(path) != original:
            raise airlift.AirLiftError(f"{label}：校验失败，恢复未生效")
        log(f"[{label}] ✓ 已恢复原版")


def rescue_files(log) -> None:
    log("正在扫描 Media 暂存区…")
    found = airlift.rescue_files(log)
    if found:
        log("\n提示：如果同时救援出了静音文件和原版提示音，最后恢复的那个会生效。")
        log("想达成确定状态，请再点一次 ② 去除提示音 或 ③ 恢复提示音。")


# ── gui ──────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.busy = False

        root.title(APP_NAME)
        root.geometry("720x460")
        root.minsize(600, 380)

        header = tk.Label(root, text=APP_NAME, font=("Microsoft YaHei UI", 16, "bold"))
        header.pack(pady=(14, 2))

        self.status = tk.Label(root, text="设备：未检查", font=("Microsoft YaHei UI", 10))
        self.status.pack(pady=(0, 10))

        buttons = tk.Frame(root)
        buttons.pack(pady=4)

        self.btn_check = tk.Button(
            buttons, text="① 检查设备 / 授权", width=17, height=2,
            font=("Microsoft YaHei UI", 11), command=self.on_check)
        self.btn_remove = tk.Button(
            buttons, text="② 去除提示音", width=15, height=2,
            font=("Microsoft YaHei UI", 11), command=self.on_remove)
        self.btn_restore = tk.Button(
            buttons, text="③ 恢复提示音", width=15, height=2,
            font=("Microsoft YaHei UI", 11), command=self.on_restore)
        self.btn_rescue = tk.Button(
            buttons, text="④ 救援残留文件", width=17, height=2,
            font=("Microsoft YaHei UI", 11), command=self.on_rescue)
        for i, b in enumerate((self.btn_check, self.btn_remove,
                               self.btn_restore, self.btn_rescue)):
            b.grid(row=0, column=i, padx=5)

        tip = tk.Label(
            root, fg="#555", justify="left", font=("Microsoft YaHei UI", 9),
            text="提示：操作期间请保持 iPhone 解锁并连着数据线。每次操作约需 2-4 分钟。")
        tip.pack(pady=(10, 4))

        self.text = ScrolledText(root, height=16, font=("Consolas", 9), wrap="word")
        self.text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.text.configure(state="disabled")

        self.log("准备就绪。")
        self.log(f"原版备份目录：{backup_file('x').parent}")
        self.root.after(300, self.on_check)
        self.root.after(120, self.pump)

    # logging ---------------------------------------------------------------
    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def pump(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.text.configure(state="normal")
            self.text.insert("end", message + "\n")
            self.text.see("end")
            self.text.configure(state="disabled")
        self.root.after(120, self.pump)

    # job plumbing ----------------------------------------------------------
    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_check, self.btn_remove, self.btn_restore, self.btn_rescue):
            b.configure(state=state)
        self.root.configure(cursor="watch" if busy else "")

    def run_job(self, title: str, fn) -> None:
        if self.busy:
            return
        self.set_busy(True)
        self.log(f"\n=== {title} ===")

        def worker():
            try:
                fn(self.log)
            except airlift.AirLiftError as exc:
                self.log(f"✗ 失败：{exc}")
            except Exception as exc:  # noqa: BLE001
                self.log(f"✗ 意外错误：{type(exc).__name__}: {exc}")
                self.log(traceback.format_exc())
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    # handlers --------------------------------------------------------------
    def on_check(self) -> None:
        def job(log):
            log("正在查找已连接的 iPhone…")
            info = check_device()
            log(f"✓ 已连接：{info['name']} · {info['product']} · "
                f"iOS {info['version']} ({info['build']})")
            if airlift.firmware_patched(info["version"]):
                log("✗ iOS 27.2 及以上版本已修补此漏洞（CVE-2026-112612），工具不可用。")
                log("  ②③④ 已被阻断；你的设备不会有任何文件被修改。")
                return
            if not info["tested"]:
                log(f"⚠ iOS {info['version']} ({info['build']}) 不在作者已验证的列表里，"
                    "仍可尝试；如遇失败，把日志发出来一起看。")
            self.root.after(0, lambda: self.status.configure(
                text=f"设备：{info['name']} · iOS {info['version']} ({info['build']})"))
        self.run_job("检查设备", job)

    def on_remove(self) -> None:
        def job(log):
            log("开始去除通话录音提示音。")
            remove_sounds(log)
            log("\n全部完成。建议现在打个电话试一下录音，确认提示音已消失。")
        self.run_job("去除提示音", job)

    def on_restore(self) -> None:
        def job(log):
            log("开始恢复原版提示音。")
            restore_sounds(log)
            log("\n全部完成。提示音已恢复为系统原版。")
        self.run_job("恢复提示音", job)

    def on_rescue(self) -> None:
        def job(log):
            rescue_files(log)
            log("\n救援结束。")
        self.run_job("救援残留文件", job)


def main() -> int:
    # A --windowed build has no stdio; keep stray prints from raising.
    if sys.stdout is None or sys.stderr is None:
        devnull = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = sys.stdout or devnull
        sys.stderr = sys.stderr or devnull

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
