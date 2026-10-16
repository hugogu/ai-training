# 模型量化：FP32、动态 INT8 与静态 INT8

打开 [ONNX_INT8量化.ipynb](ONNX_INT8量化.ipynb)，按顺序执行。这个练习接在课程 2.2 的分类训练与评估、3.2 的 ONNX 推理之后，比较同一小模型的三种版本。

示例使用 scikit-learn 自带的 digits 数据，训练一个 64→64→10 的多层感知机（MLP），导出 FP32 ONNX，然后做动态、静态 INT8 量化。数据集只有 1797 张 8×8 灰度图；它不是课程中的 28×28 MNIST。安装依赖后，不需要下载数据或预训练权重，CPU 即可完整运行。

## 先学什么

| 概念 | 本例怎样观察 |
|---|---|
| 量化与普通类型转换 | 对一组小数计算整数表示、scale 和恢复误差，说明 astype(int8) 为什么不能替代模型量化 |
| 位宽与模型大小 | 对比真实 ONNX 文件字节数，解释权重理论缩小四倍与完整文件大小的区别 |
| 动态 PTQ | 权重先转换，部分激活范围在推理时确定，无需离线校准输入 |
| 静态 PTQ | 从训练部分取代表性输入校准，用 QDQ 表达量化边界 |
| QAT | 说明训练时模拟量化误差的思路；本例实际运行的是两种 PTQ |
| 质量变化 | 比较真实标签准确率、前后预测一致率、正确变错误和错误变正确的案例 |
| 性能变化 | 在同一 CPU、线程、预热和调用条件下测 batch=1/64，记录更快或更慢的结果 |
| 与 LLM 的关系 | 解释 FP16/BF16、W4A16/W8A8、GGUF 与 QLoRA 的含义和适用边界 |

先看 Notebook 的数值小例子，再运行完整模型转换。模型量化不是重新给图片打标签，也不是把输入数组改成整数；量化后仍可能要求 float32 输入并返回浮点概率。

## 运行

推荐 Python 3.12。在本目录执行：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

在 Notebook 内核选择器中选择这个虚拟环境。也可以在已有 Python 3.12 虚拟环境中使用：

```bash
python -m pip install -r requirements.txt
```

Apple Silicon Mac 优先选择原生 arm64 Python；Notebook 会打印实际架构、依赖版本与可用后端。为了比较同一执行条件，本例固定 CPUExecutionProvider、单线程；后端可用列表不会替本例自动选择 CoreML。

所有生成文件保存在本目录 outputs/，原 FP32 文件与两个量化文件分别保存。模型、报告、虚拟环境和运行缓存已加入忽略规则。

## 完整流程

1. 取自带 digits 数据，固定除以 16，把输入变为 float32 的 (N,64) 数组。
2. 分层划分训练/测试集（1437/360），训练 MLP。
3. 用 skl2onnx 导出 FP32，检查 ONNX 概率输出与原分类器接近。
4. 对 MatMul 执行动态量化，权重使用 INT8。
5. 用训练部分的 128 个输入做 MinMax 校准，生成静态 QDQ 模型；权重 INT8、激活 UINT8。
6. 检查实际整数权重和算子、原文件哈希、输入输出形状和概率。
7. 在同一测试集、同一质量评估 batch=64 下比较三个预先固定的版本。
8. 预热后分别测单张和批量调用，输出表格和报告。

动态量化的激活范围可能随 batch 内容变化，所以报告记录质量评估的批量大小。静态校准输入来自训练部分，不使用测试样本或标签。MinMax 校准与 sklearn 的 MinMaxScaler 是不同操作。

报告包含模型文件大小、INT8 权重检查、准确率与预测变化、概率差异、各轮耗时、架构、关键依赖版本和模型哈希。quality.csv、timing.csv 和 changed_predictions.csv 可用 Excel 打开，report.json 保留更完整的元数据。

## 怎样看结果

FP32 权重每个数 4 字节，INT8 每个数 1 字节，但计算图、偏置、scale 和未量化算子仍占空间。文件大小、运行时内存、速度和质量是四项不同指标；本例测了文件、质量和推理调用时间，没有测峰值内存。

量化会产生数值近似，不保证准确率下降，也不保证预测不变。准确率相同可能是新增错误和修正错误互相抵消；预测一致率 100% 也不代表概率完全相同。

性能计时只覆盖 session.run，包括运行时调用与输出处理，不含读取图片、预处理、Session 创建和量化。每个模型先预热 25 次，再做 7 轮、每轮重复调用 3000 次，并轮换顺序；表格报告各轮平均耗时的中位数与范围，不是单请求 P95。

小模型的整数计算收益可能抵不过量化/反量化和调用开销。即使文件变小、单张更慢，实验仍有学习价值；不能从这次结果推断所有设备、卷积网络或 LLM 的收益。

本例固定两种量化方案后做比较，没有根据测试分数继续挑选参数。实际部署应先定义可接受的质量、关键类召回、延迟和内存预算；需要调参时使用验证数据选择方案，再用独立测试数据确认。

## 一次实际运行

在 arm64 Mac、Python 3.12.14、ONNX Runtime 1.23.2、单线程 CPU 上完整运行，使用固定划分的 360 个测试样本：

| 指标 | FP32 | 动态 INT8 | 静态 INT8 |
|---|---:|---:|---:|
| 文件大小（KiB） | 20.26 | 8.07 | 8.85 |
| 测试准确率 | 95.00% | 94.72% | 95.00% |
| 与 FP32 不同的预测数 | 0 | 1 | 2 |
| 原本正确变错误 | 0 | 1 | 1 |
| 原本错误变正确 | 0 | 0 | 1 |
| batch=1 调用耗时（微秒） | 5.19 | 6.24 | 7.23 |
| batch=64 调用耗时（微秒） | 13.57 | 11.92 | 15.23 |

耗时是上述 7 轮平均值的中位数。动态量化文件约缩小 2.51 倍，但单张调用更慢；batch=64 时本次约快 1.14 倍。静态量化准确率没有变化，却有两个预测互换了正确与错误。这些小规模测量会受运行环境与系统负载影响，应在目标设备复测。

原模型完整性、导出近似等价、实际整数权重和概率检查均通过，Notebook 保留了真实输出。首次运行包含依赖首次导入和 Matplotlib 字体缓存构建，本次约 109 秒；缓存就绪后的完整运行约 4.3 秒，两者均不含安装依赖。

## 检查方法

```bash
.venv/bin/python -m unittest -v
```

单元测试检查量化刻度、零张量、无效输入、准确率与一致率的区别，以及 INT8 权重和 INT64 标签的区别。集成测试会在临时目录执行当前 Notebook 的全部代码单元，验证训练→导出→两种量化→评估→保存。Notebook 同时检查导出等价性、真实整数权重、算子、原文件未变和输出概率。测试不要求量化更快或准确率提高。

## 资料来源

- [ONNX Runtime 量化指南](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
- [ONNX QuantizeLinear 的舍入、缩放与饱和规则](https://onnx.ai/onnx/operators/onnx__QuantizeLinear.html)
- [digits 数据定义](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html)
- [sklearn-onnx 的概率输出与 ZipMap](https://onnx.ai/sklearn-onnx/auto_examples/plot_convert_zipmap.html)
- [量化与训练的原始研究](https://arxiv.org/abs/1712.05877)
- [QLoRA 论文](https://arxiv.org/abs/2305.14314)
- [GGUF 格式说明](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)

[返回扩展练习目录](../README.md)
