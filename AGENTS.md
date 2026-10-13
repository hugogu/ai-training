# Notebook 运行问题排查

- 区分编辑器显示的“运行中”、Jupyter Server 返回的内核状态和实际执行栈。修改单元格不会改变已经开始执行的那次代码；不要仅凭 provider 可用列表或界面状态判断卡点。
- `3.2.5-素材/version-RFB-320.onnx` 是较旧的导出文件，会产生大量 initializer 警告。在课程的 macOS Jupyter 环境（Python 3.11.15 x86_64、ONNX Runtime 1.23.2）中，已复现 Session 创建卡在 `AppleLogSink → NSLog → logToStderr`；即使指定 CPU 也会发生。该题保留 `SessionOptions.log_severity_level = 3`，只关闭 warning 及更低级别日志，错误日志仍会输出。已在相同课程环境确认此配置可以完成整张图片的检测流程；不要将这个配置当成普通清理项删除。
