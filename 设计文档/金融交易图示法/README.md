# 金融交易图示法 FTN 1.1 · 业务分析版

以 Financial Transaction Notions 与用户 Whimsical「Payout Transaction」为基础，描述业务资金流、账内变化、业务信息及其账务映射。日期 2026-10-17。

- [规范正文](规范.md)：场景卡、符号语义、形式模型、出款及退款示例。
- [改进说明](改进说明.md)：与 FTN 1.0 的差异、示例修订及待确认假设。
- [规范 PDF](../../output/pdf/金融交易图示法-规范-v1.1.pdf)
- [改进说明 PDF](../../output/pdf/金融交易图示法-改进说明-v1.1.pdf)
- [出款示例](examples/payout.html) / [退款示例](examples/refund.html)：图、事件、分录、业务明细同页呈现。
- `figures/`：五幅可编辑 SVG，沿用圆圈、箭头和黄色便笺。
- `examples/*.json`、`schema.json`：可选机器表达；金额为正整数最小单位。
- `tools/validate.py`、`tests/`：文档静态检查。

## 重建与验证

需要 Python 3.11+、ReportLab、jsonschema，以及支持中文的 TrueType 字体。字体由调用方传入，不绑定本机路径。从本目录运行：

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/validate.py examples/*.json
python tools/build.py --font "$FTN_FONT"
```

PDF 输出到仓库 `output/pdf/`，SVG 输出到 `figures/`，业务示例 HTML 输出到 `examples/`。图中事件及分录由业务 JSON 生成；规范 Markdown 是正文维护源。

## 口径与边界

业务来源：[Whimsical · Payout Transaction](https://whimsical.com/nanke-s-workspace/payout-transaction-NvkWtLCTtiyLkNKZs6rz4R)。沿用 1,000 / 15 / 10 USD 数据；新增假设和原板差异见规范第 12 章。未修改原画板及 `.graffle` 文件，也不把示例会计处理视作正式批准的会计政策。

1.1 不兼容 1.0 的机器结构；旧版可从 Git 历史取得。本版不涉及 API、超时、重试或数据库事务。不声称属于 ISO 20022、BPMN 或正式会计准则。
