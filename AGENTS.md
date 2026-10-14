# Notebook 运行问题排查

- 区分编辑器显示的“运行中”、Jupyter Server 返回的内核状态和实际执行栈。修改单元格不会改变已经开始执行的那次代码；不要仅凭 provider 可用列表或界面状态判断卡点。
- `3.2.5-素材/version-RFB-320.onnx` 是较旧的导出文件，会产生大量 initializer 警告。在课程的 macOS Jupyter 环境（Python 3.11.15 x86_64、ONNX Runtime 1.23.2）中，已复现 Session 创建卡在 `AppleLogSink → NSLog → logToStderr`；即使指定 CPU 也会发生。该题保留 `SessionOptions.log_severity_level = 3`，只关闭 warning 及更低级别日志，错误日志仍会输出。已在相同课程环境确认此配置可以完成整张图片的检测流程；不要将这个配置当成普通清理项删除。

# LLM LoRA 示例

- `扩展练习/LLM代码风格微调` 仅训练注意力投影的 LoRA 参数，没有扩词表或训练 embedding。在 PEFT 0.18.1 中，`get_peft_model_state_dict` 和 `save_pretrained` 的 `save_embedding_layers="auto"` 会检查基础模型配置，可能引发额外的 Hugging Face 请求及超时。该示例显式使用 `save_embedding_layers=False`，避免把保存最佳状态时的网络等待误认为训练计算缓慢。若以后扩词表或训练 embedding，应重新确定保存范围。

# 学习资料与 KB 更新

- 课程 DOCX 同时存在常见 OOXML 和 Strict OOXML 命名空间。提取正文时应识别实际命名空间，连同表格和内嵌图片检查；不能因为固定命名空间没有匹配到段落就判断文档为空。
- KB 发布需要完整 Markdown。长文件应分段读取，确认没有输出截断提示并核对总长度；保存草稿后先用具体修订版本回读比对正文，再发布并核对线上正文与本地镜像一致。不得把工具截断后的输出当成文档源。
