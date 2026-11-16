# T16 · no tunnel故障与补验（2026-11-16）

旧地址18062f6f12a188.app.lhr.life实际502，正文no tunnel。本机18080的health仍200；通道日志已换到ac4dda85ff8882.app.lhr.life，新地址当时health/root均200。脚本选择日志首条URL，导致已发布状态仍指向失效域名。

旧分享主进程66537已不存在，后端66563和SSH66576成为PPID=1的孤儿。没有退出信号证据，不能确定主进程为何退出；核对命令和进程组归属后仅清理这两个分享子进程，未停止8000/5173开发服务。此前一分钟5次200仅代表当时，保留原报告，不据此声称长期稳定。

## 改动

仅修改scripts/share.py和app/tests/test_share.py；README、指南、任务板、CHANGELOG及本报告为文档，仍在已批准T16范围。

- 读取最新域名；先验证公网health，再原子更新状态文件。新地址不可达不发布；旧地址不能恢复或自动跳转。
- --background独立会话启动分享主进程；启动器退出后分享继续。保活仍只请求health。
- --status核对本项目进程身份及当前health，再输出最新地址；--stop向该主进程发停止信号，沿用子进程清理。兼容make使用相对Python路径。

## 实测

```text
make test
302 passed in 2.69s
Tests 34 passed (34)

make lint
All checks passed!
cd web && npx tsc --noEmit
exit 0

.venv/bin/python -m ruff check scripts/share.py
All checks passed!
```

追加5条回归：最新域名、轮换可达/不可达两分支、父进程组结束后后台存活、相对解释器身份。测试在对应实现补齐前失败，修复后全量通过；T16之前测试未改。

实际执行`.venv/bin/python -m scripts.share --background --tunnel localhost`，启动器返回；随后status成功输出新地址，独立请求公网health/root均200。主进程PPID=1且自有进程组。后续Python urllib复核出现一次SSL EOF，本地与主进程仍存活；紧接着curl复核health/root均200，不能宣称网络稳定。时间点证据及后续curl复核见[t16-rotation.json](t16-rotation.json)，运行时地址以--status为准。

模型日志仍4条（原3识别+1编排），本轮没有新增模型调用；134冻结项哈希不变。未改变模型、prompt、cases、数据库结构、依赖或前端。沿用T16既有375px截图，未重做UI及上传/生成。轮换处理依据真实故障日志及回归，未等待下一次服务商真实轮换。电脑断网/合盖/通道退出仍可能失效，免费域名仍需重新复制。
