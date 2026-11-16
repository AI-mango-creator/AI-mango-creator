"""make share：真实生产构建 + 独立SQLite + 无账号Cloudflare临时HTTPS通道。"""
import argparse
import fcntl
import hashlib
import io
import json
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.llm.errors import LLMError

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026.11.0"
ARCHIVE_SHA256 = "8c2f90277ef06a6080bb40b964d33f09f1188102f8798f2e344174b6cf41accf"
DOWNLOAD_URL = f"https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-darwin-arm64.tgz"


def share_environment(root, *, recognition_limit, composition_limit):
    if min(recognition_limit, composition_limit) < 1:
        raise ValueError("每日测试额度必须是正整数。")
    return {**os.environ, "APP_DATA_DIR": str(root / "data/share"),
            "APP_WEB_DIR": str(root / "web/dist"), "APP_SERVE_WEB": "1", "APP_SHARE_MODE": "1",
            "APP_SHARE_RECOGNITION_LIMIT": str(recognition_limit),
            "APP_SHARE_COMPOSITION_LIMIT": str(composition_limit)}


def install_archive(content, target):
    if hashlib.sha256(content).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("cloudflared下载校验失败，未安装，请重试。")
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        member = next(m for m in archive.getmembers() if Path(m.name).name == "cloudflared" and m.isfile())
        with archive.extractfile(member) as stream:
            binary = stream.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.replace(target)
    target.with_suffix(".sha256").write_text(hashlib.sha256(binary).hexdigest())


def cloudflared():
    existing = shutil.which("cloudflared")
    if existing:
        return Path(existing)
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise ValueError("请先从Cloudflare官方安装适合本机的cloudflared；自动下载仅支持已验Apple Silicon Mac。")
    target = ROOT / "data/tools/cloudflared"
    checksum = target.with_suffix(".sha256")
    if target.is_file() and checksum.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == checksum.read_text():
        return target
    print(f"下载官方cloudflared {VERSION}（仅存data/tools，不装全局工具）…", flush=True)
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "wardrobe-share"})
    with urllib.request.urlopen(request, timeout=60) as response:
        install_archive(response.read(), target)
    return target


def stop_processes(processes):
    for process in reversed(processes):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def wait_health(base, process, *, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("服务启动中断，请查看data/share/server.log及cloudflare.log/localhost.log。")
        try:
            with urllib.request.urlopen(base + "/health", timeout=3) as response:
                if response.status == 200 and json.load(response) == {"status": "ok"}:
                    return
        except (OSError, ValueError):
            time.sleep(0.5)
    raise RuntimeError("服务未在限定时间内连通，请查看data/share/server.log及cloudflare.log/localhost.log后重试。")


def extract_tunnel_url(contents):
    matches = re.findall(r"https://[a-z0-9.-]+\.(?:trycloudflare\.com|lhr\.life|localhost\.run)", contents)
    return next((url for url in reversed(matches) if url != "https://admin.localhost.run"), None)


def keep_sharing(server, tunnel, url, *, heartbeat=wait_health, pause=time.sleep, log_path=None, on_url_change=None):
    while server.poll() is None and tunnel.poll() is None:
        # 免费通道/本地网络会回收空闲SSH；定时走真实HTTPS health保活，不调用模型。
        try:
            candidate = extract_tunnel_url(log_path.read_text(errors="replace")) if log_path and log_path.exists() else None
            candidate = candidate or url
            heartbeat(candidate, tunnel, seconds=10)
            if candidate != url:
                if on_url_change:
                    on_url_change(candidate)
                url = candidate
        except RuntimeError:
            print("公网暂时无法连通，保留服务等待网络恢复；若持续失败请更换网络后重新分享。", flush=True)
        pause(15)


def spawn_background(command, directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "launcher.log").open("a") as stream:
        return subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)


def write_status(path, status):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def is_share_process(command):
    parts = shlex.split(command)
    if len(parts) < 3 or parts[1:3] != ["-m", "scripts.share"]:
        return False
    executable = Path(parts[0])
    if not executable.is_absolute():
        executable = ROOT / executable
    return os.path.abspath(executable) == os.path.abspath(sys.executable)


def open_tunnel(provider, port, directory, processes):
    if provider == "cloudflare":
        command = [str(cloudflared()), "--no-autoupdate", "tunnel", "--config", "/dev/null", "--url",
                   f"http://127.0.0.1:{port}", "--protocol", "http2"]
    else:
        command = ["ssh", "-F", "/dev/null", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                   "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={ROOT / 'data/tools/share_known_hosts'}",
                   "-o", "IdentityAgent=none", "-o", "PubkeyAuthentication=no", "-o", "ServerAliveInterval=30",
                   "-o", "ServerAliveCountMax=10", "-o", "ExitOnForwardFailure=yes", "-R",
                   f"80:127.0.0.1:{port}", "nokey@localhost.run", "--", "--close-on-endpoint-change"]
    path = directory / f"{provider}.log"
    with path.open("w") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        deadline = time.monotonic() + 40
        while process.poll() is None and time.monotonic() < deadline:
            contents = path.read_text(errors="replace")
            url = extract_tunnel_url(contents)
            if url:
                wait_health(url, process, seconds=20)
                return process, url
            if provider == "cloudflare" and "hard_fail=true" in contents:
                raise RuntimeError("Cloudflare网络预检失败（7844端口），改用备用通道。")
            time.sleep(0.5)
    raise RuntimeError(f"{provider}未取得可访问地址，详见{path.name}。")


def main():
    parser = argparse.ArgumentParser(description="启动可分享的临时HTTPS测试版；电脑和进程必须保持运行。")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--recognition-limit", type=int, default=20)
    parser.add_argument("--composition-limit", type=int, default=30)
    parser.add_argument("--tunnel", choices=["auto", "cloudflare", "localhost"], default="auto")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--background", action="store_true", help="独立后台运行，不依赖当前终端/工具会话")
    mode.add_argument("--status", action="store_true", help="查询并验证当前最新地址")
    mode.add_argument("--stop", action="store_true", help="停止本项目的后台分享")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("端口必须在1024–65535之间。")
    if min(args.recognition_limit, args.composition_limit) < 1:
        parser.error("每日测试额度必须是正整数。")
    environment = share_environment(ROOT, recognition_limit=args.recognition_limit, composition_limit=args.composition_limit)
    directory = ROOT / "data/share"
    directory.mkdir(parents=True, exist_ok=True)
    processes = []
    status_path = directory / "share.json"

    if args.status or args.stop:
        try:
            status = json.loads(status_path.read_text())
            command = subprocess.check_output(["ps", "-p", str(status["pid"]), "-o", "command="], text=True).strip()
            if not is_share_process(command):
                raise RuntimeError("分享进程已结束或不匹配，请重新启动。")
            if args.stop:
                os.kill(status["pid"], signal.SIGTERM)
                print("已请求停止本项目分享。", flush=True)
            else:
                with urllib.request.urlopen(status["url"] + "/health", timeout=8) as response:
                    if response.status != 200 or json.load(response) != {"status": "ok"}:
                        raise RuntimeError("当前地址尚未连通，请稍候再查。")
                print(status["url"], flush=True)
            return 0
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"当前分享不可用：{error}", file=sys.stderr)
            return 1

    if args.background:
        command = [sys.executable, "-m", "scripts.share", *[x for x in sys.argv[1:] if x != "--background"]]
        child = spawn_background(command, directory)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline and child.poll() is None:
            try:
                status = json.loads(status_path.read_text())
                if status["pid"] == child.pid:
                    print(f"后台分享已连通：{status['url']}\n查询最新地址：.venv/bin/python -m scripts.share --status", flush=True)
                    return 0
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.5)
        print("后台启动未完成，请查看data/share/launcher.log后用--status复核。", file=sys.stderr)
        return 1

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        with (directory / "share.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("已有分享进程运行，请先结束原make share。") from None
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", args.port))
            status_path.unlink(missing_ok=True)
            from app.llm.client import _configuration

            key, _, model = _configuration()  # 只验证配置；不打印、不传命令行、不保存key。
            if not shutil.which("npm"):
                raise RuntimeError("找不到npm，请用zsh -ilc 'node -v'复核登录环境。")
            subprocess.run(["npm", "run", "build"], cwd=ROOT / "web", check=True)
            for file in (ROOT / "web/dist").rglob("*"):
                if file.is_file() and key.encode() in file.read_bytes():
                    raise RuntimeError("网页构建含密钥，拒绝公开。")
            (ROOT / "data/tools").mkdir(parents=True, exist_ok=True)
            with (directory / "server.log").open("a") as server_log:
                server = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                    cwd=ROOT, env=environment, stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True,
                )
                processes.append(server)
                local = f"http://127.0.0.1:{args.port}"
                wait_health(local, server)
                preferred_file = ROOT / "data/tools/last-tunnel"
                preferred = preferred_file.read_text().strip() if preferred_file.exists() else "cloudflare"
                providers = [preferred, "localhost" if preferred == "cloudflare" else "cloudflare"] if args.tunnel == "auto" else [args.tunnel]
                for provider in providers:
                    try:
                        tunnel, url = open_tunnel(provider, args.port, directory, processes)
                        break
                    except (OSError, ValueError, RuntimeError) as error:
                        print(str(error), flush=True)
                        stop_processes(processes[1:])
                else:
                    raise RuntimeError("临时通道均未连通，本次未发布成功。请更换网络后重试。")
                preferred_file.write_text(provider)
                status = {"url": url, "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                          "pid": os.getpid(), "port": args.port, "data_directory": str(directory),
                          "recognition_limit": args.recognition_limit, "composition_limit": args.composition_limit,
                          "text_model": model, "tunnel_provider": provider,
                          "cloudflared_version": VERSION if provider == "cloudflare" else None}
                write_status(status_path, status)
                print(f"\n测试链接已连通：{url}\n复制给朋友即可使用（上传后先逐件确认）。", flush=True)
                print(f"全站每日识别{args.recognition_limit}张/生成{args.composition_limit}次；原衣柜不在此测试库中。", flush=True)
                print("保持本进程和电脑联网；Ctrl-C关闭分享，照片保留在data/share/uploads。", flush=True)
                if shutil.which("caffeinate"):
                    processes.append(subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], start_new_session=True))
                def update_url(new_url):
                    status["url"] = new_url
                    status["updated_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
                    write_status(status_path, status)
                    print(f"测试地址已轮换：{new_url}", flush=True)

                keep_sharing(server, tunnel, url, log_path=directory / f"{provider}.log", on_url_change=update_url)
                raise RuntimeError("分享服务或通道已退出，请查看日志后重新运行make share。")
    except KeyboardInterrupt:
        print("\n正在停止分享…", flush=True)
        return 130
    except (OSError, ValueError, RuntimeError, LLMError, subprocess.CalledProcessError) as error:
        print(f"分享启动失败：{error}", file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)
        if processes:
            status_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
