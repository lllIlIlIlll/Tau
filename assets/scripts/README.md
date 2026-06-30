# assets/scripts/

跨平台用户配置向导 + 安装脚本 + 工具注入头。**不在 wheel**。

| 文件 | 这是什么 | 谁调它 |
|---|---|---|
| `configure_tauchain.py` | 邮件 SMTP 多账号交互式向导 (v2.2+) | `tau` 不直连；用户手动 |
| `configure_taukey.py` | LLM API Key + IM 平台一键配置 | `tau configure` |
| `code_run_header.py` | `code_run` 工具的 subprocess 注入头 | `core/tools/code_run.py` |
| `install-macos-app.sh` | macOS LaunchAgent 安装 | 用户安装时 |
| `install_python_windows.bat` | Windows Python 环境安装 | 用户安装时 |