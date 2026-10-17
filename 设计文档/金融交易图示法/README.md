# 金融交易图示法 FTN 1.0

以原有 Financial Transaction Notions 为基础整理的提案规范，日期 2026-10-17。

- [规范正文](规范.md)：规范性定义、形式语义、图形语法、交易示例及检查规则。
- [改进说明](改进说明.md)：与原设计的对应、改善、代价及尚未覆盖的范围。
- [规范 PDF](../../output/pdf/金融交易图示法-规范-v1.0.pdf)
- [改进说明 PDF](../../output/pdf/金融交易图示法-改进说明-v1.0.pdf)
- `figures/`：可编辑 SVG 图例；不依赖颜色辨义。
- `examples/`、`schema.json`：核心配置文件的机器表达。
- `tools/validate.py`、`tests/`：核心静态检查，不是支付执行引擎或生产账务系统。

## 重建与验证

需要 Python 3.11+、ReportLab、jsonschema、支持中文的 TrueType 字体，以及可选的 Poppler。字体由调用方传入，不绑定本机路径。

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/validate.py examples/*.json
python tools/build.py --font "$FTN_FONT"
```

从本目录执行以上命令。PDF 写入仓库的 `output/pdf/`；SVG 写入本目录的 `figures/`。正文是可维护源，PDF 是阅读版。金额示例均为构造数据；汇率只用于演算，不是实时报价。

## 使用边界

本规范是独立设计的领域图示语言，不声称符合 ISO 20022、BPMN、会计准则或特定清算系统规则。原始 OmniGraffle 文档是设计输入，未被本任务覆盖修改。SVG 可用于后续在 OmniGraffle 中重绘或组合；未声称交付原生 `.graffle` 模板。
