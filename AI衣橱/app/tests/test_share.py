"""分享服务在独立子进程注入环境，所有数据库/网页测试都使用tmp_path。"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db import connect_db, init_db, reserve_quota

ROOT = Path(__file__).resolve().parents[2]


def test_shared_web_data_and_private_files(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text('<div id="root">真实网页入口</div>')
    (web / "assets/app.js").write_text('console.log("test")')
    script = """
import json, os
from pathlib import Path
from app.db import DB_PATH
from app.llm.client import LOG_PATH
assert DB_PATH.parent == Path(os.environ['APP_DATA_DIR'])
assert LOG_PATH.parent == DB_PATH.parent
from app.main import app
from fastapi.testclient import TestClient
with TestClient(app) as c:
    headers={'X-Device-ID':'11111111-1111-4111-8111-111111111111'}
    results={'page':c.get('/').status_code, 'html':c.get('/').text,
             'asset':c.get('/assets/app.js').status_code,
             'health':c.get('/health').json(),
             'owned':c.get('/api/wardrobe/items',headers=headers).json(),
             'missing_owner':c.get('/api/wardrobe/items').status_code,
             'private':[c.get(p,headers=headers).status_code for p in
                        ['/.env','/data/app.db','/uploads/secret.jpg','/assets/../../.env']],
             'uploads':(DB_PATH.parent/'uploads').is_dir()}
print(json.dumps(results))
"""
    env = {**os.environ, "APP_DATA_DIR": str(tmp_path / "data"), "APP_SERVE_WEB": "1", "APP_WEB_DIR": str(web)}
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["page"] == data["asset"] == 200
    assert "真实网页入口" in data["html"]
    assert data["health"] == {"status": "ok"}
    assert data["owned"] == [] and data["missing_owner"] == 400
    assert data["private"] == [404] * 4
    assert data["uploads"] is True


@pytest.mark.parametrize("ability", ["recognition", "composition"])
def test_global_share_quota_cannot_be_bypassed_with_new_devices(tmp_path, monkeypatch, ability):
    path = tmp_path / "app.db"
    init_db(path)
    monkeypatch.setenv("APP_SHARE_MODE", "1")
    monkeypatch.setenv(f"APP_SHARE_{ability.upper()}_LIMIT", "2")
    reserve_quota(path, str(uuid4()), ability)
    reserve_quota(path, str(uuid4()), ability)
    with pytest.raises(HTTPException) as error:
        reserve_quota(path, str(uuid4()), ability)
    assert error.value.status_code == 429
    assert "测试服务今日" in error.value.detail
    assert int(error.value.headers["Retry-After"]) > 0
    with closing(connect_db(path)) as c:
        assert c.execute(f"SELECT sum({ability}) FROM daily_quotas").fetchone()[0] == 2


def test_global_quota_atomic_across_devices(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    init_db(path)
    monkeypatch.setenv("APP_SHARE_MODE", "1")
    monkeypatch.setenv("APP_SHARE_RECOGNITION_LIMIT", "3")

    def consume(_):
        try:
            reserve_quota(path, str(uuid4()), "recognition")
            return True
        except HTTPException as error:
            assert error.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=6) as executor:
        assert sum(executor.map(consume, range(12))) == 3


def test_share_cap_does_not_change_normal_dev_quota(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    init_db(path)
    monkeypatch.delenv("APP_SHARE_MODE", raising=False)
    monkeypatch.setenv("APP_SHARE_RECOGNITION_LIMIT", "1")
    for _ in range(3):
        reserve_quota(path, str(uuid4()), "recognition")


def test_share_still_obeys_per_device_quota(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    init_db(path)
    monkeypatch.setenv("APP_SHARE_MODE", "1")
    monkeypatch.setenv("APP_SHARE_RECOGNITION_LIMIT", "100")
    owner = str(uuid4())
    for _ in range(20):
        reserve_quota(path, owner, "recognition")
    with pytest.raises(HTTPException) as error:
        reserve_quota(path, owner, "recognition")
    assert error.value.status_code == 429


def test_cleanup_retains_other_devices_daily_global_usage(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    init_db(path)
    monkeypatch.setenv("APP_SHARE_MODE", "1")
    monkeypatch.setenv("APP_SHARE_RECOGNITION_LIMIT", "1")
    reserve_quota(path, str(uuid4()), "recognition")
    with closing(connect_db(path)) as c, c:
        c.execute("DELETE FROM wardrobe_items")
    with pytest.raises(HTTPException):
        reserve_quota(path, str(uuid4()), "recognition")


def test_share_launcher_uses_separate_store_without_changing_parent_env(tmp_path):
    from scripts.share import share_environment

    before = os.environ.copy()
    env = share_environment(tmp_path, recognition_limit=20, composition_limit=30)
    assert env["APP_DATA_DIR"] == str(tmp_path / "data/share")
    assert env["APP_WEB_DIR"] == str(tmp_path / "web/dist")
    assert env["APP_SHARE_MODE"] == env["APP_SERVE_WEB"] == "1"
    assert env["APP_SHARE_RECOGNITION_LIMIT"] == "20"
    assert env["APP_SHARE_COMPOSITION_LIMIT"] == "30"
    assert os.environ == before


def test_share_stop_terminates_owned_server(tmp_path):
    from scripts.share import stop_processes

    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        stop_processes([worker])
        assert worker.poll() is not None
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait()


def test_share_download_rejects_wrong_digest_without_installing(tmp_path):
    from scripts.share import install_archive

    with pytest.raises(ValueError, match="校验"):
        install_archive(b"not-an-official-archive", tmp_path / "cloudflared")
    assert not (tmp_path / "cloudflared").exists()


def test_tunnel_url_accepts_actual_multilevel_free_domain_and_ignores_admin():
    from scripts.share import extract_tunnel_url

    # 2026-11-16本机localhost.log真实输出；免费域名包含.app子域。
    log = "To set up custom domains go to https://admin.localhost.run/\n" \
          "7d83dd890621f0.app.lhr.life tunneled with tls termination, https://7d83dd890621f0.app.lhr.life\n"
    assert extract_tunnel_url(log) == "https://7d83dd890621f0.app.lhr.life"
    assert extract_tunnel_url("go to https://admin.localhost.run/") is None


def test_missing_model_configuration_has_chinese_startup_error(tmp_path):
    script = """
import sys
import socket
from pathlib import Path
from app.llm import client
from scripts import share
share.ROOT = Path(sys.argv[1])
client.ENV_PATH = share.ROOT / 'missing.env'
with socket.socket() as probe:
    probe.bind(('127.0.0.1',0))
    port=probe.getsockname()[1]
sys.argv = ['share','--port',str(port)]
raise SystemExit(share.main())
"""
    env = {key: value for key, value in os.environ.items() if not key.startswith("DASHSCOPE_")}
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert "分享启动失败" in result.stderr
    assert "DASHSCOPE_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr


def test_idle_share_sends_public_health_heartbeat_without_model_calls():
    from scripts.share import keep_sharing

    class Running:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

    server, tunnel = Running(), Running()
    heartbeats = []

    def health(url, process, *, seconds):
        assert process is tunnel
        heartbeats.append(url)

    def finish(_):
        tunnel.stopped = True

    keep_sharing(server, tunnel, "https://example.test", heartbeat=health, pause=finish)
    assert heartbeats == ["https://example.test"]


def test_transient_public_error_does_not_close_running_share():
    from scripts.share import keep_sharing

    class Running:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

    server, tunnel = Running(), Running()
    attempts = []

    def health(*_, **__):
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("短暂502")

    def tick(_):
        if len(attempts) == 2:
            tunnel.stopped = True

    keep_sharing(server, tunnel, "https://example.test", heartbeat=health, pause=tick)
    assert len(attempts) == 2


def test_tunnel_rotation_selects_last_real_address():
    from scripts.share import extract_tunnel_url

    actual = "https://18062f6f12a188.app.lhr.life\nhttps://ac4dda85ff8882.app.lhr.life\n"
    assert extract_tunnel_url(actual) == "https://ac4dda85ff8882.app.lhr.life"


@pytest.mark.parametrize("new_reachable", [True, False])
def test_domain_rotation_publishes_only_verified_address(tmp_path, new_reachable):
    from scripts.share import keep_sharing

    class Running:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

    server, tunnel = Running(), Running()
    old, new = "https://old.app.lhr.life", "https://new.app.lhr.life"
    log = tmp_path / "tunnel.log"
    log.write_text(old + "\n")
    updated, checked = [], []

    def health(url, *_, **__):
        checked.append(url)
        if url == new and not new_reachable:
            raise RuntimeError("新地址尚未可达")

    def tick(_):
        if new in checked:
            tunnel.stopped = True
        else:
            log.write_text(old + "\n" + new + "\n")

    keep_sharing(server, tunnel, old, heartbeat=health, pause=tick, log_path=log, on_url_change=updated.append)
    assert new in checked
    assert updated == ([new] if new_reachable else [])


def test_detached_supervisor_survives_parent_process_group_exit(tmp_path):
    # 模拟工具终端退出：父进程组结束后，分享主进程必须仍存活。
    import signal
    import time

    script = """
import sys,time
from pathlib import Path
from scripts.share import spawn_background
worker = spawn_background([sys.executable,'-c','import time; time.sleep(60)'], Path(sys.argv[1]))
print(worker.pid,flush=True)
time.sleep(60)
"""
    parent = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT,
                              stdout=subprocess.PIPE, text=True, start_new_session=True)
    worker_pid = None
    try:
        worker_pid = int(parent.stdout.readline().strip())
        os.killpg(parent.pid, signal.SIGTERM)
        parent.wait(timeout=3)
        time.sleep(0.05)
        os.kill(worker_pid, 0)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if worker_pid is not None:
            try:
                os.killpg(worker_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_status_accepts_make_relative_python_but_not_unrelated_commands():
    from scripts.share import is_share_process

    assert is_share_process(".venv/bin/python -m scripts.share")
    assert is_share_process(f"{sys.executable} -m scripts.share --tunnel localhost")
    assert not is_share_process(f"{sys.executable} -m unrelated.module")
