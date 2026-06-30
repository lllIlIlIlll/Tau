"""tools 包：工具实现按 code_run/file_io/web 分文件，utils 为通用底座。
消费方一律 submodule 直接 import（from core.tools.<mod> import ...）；
此处不做重导出——避免 import 包即连带 web→simphtml→bs4。"""
