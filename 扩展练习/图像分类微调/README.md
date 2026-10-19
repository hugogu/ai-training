# 图像分类微调：从通用 ResNet18 到蚂蚁/蜜蜂分类器

建议先读 [前置知识：从基础概念到本练习](前置知识.md)，再运行 Notebook。文档包含关键模型原理、数据形状、代码对应关系与自测解答。

打开 [ResNet18微调.ipynb](ResNet18微调.ipynb)，按顺序执行。它接在课程 2.2 的训练与评估、3.2 的图像预处理与预测之后。

这个例子实际训练两次：先固定预训练网络，只训练新分类层；再解冻 `layer4`，以更小学习率微调已有特征。Notebook 会检查权重有没有变化，按验证集选择模型，在保留的测试集上评估，保存并重新加载模型进行预测。

## 运行环境

推荐 Python 3.12。示例提供独立环境，不依赖课程根目录的 `requirements.txt`。在本目录执行：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

然后在 Notebook 的内核选择器中选择这个 `.venv` 对应的 Python。也可以在已有 Python 3.12 虚拟环境中用 `python -m pip install -r requirements.txt` 安装。

Apple Silicon Mac 请使用原生 arm64 Python；若课程原内核通过 Rosetta 运行，可为此示例选择新的 arm64 环境。Notebook 第一段会打印解释器和架构，便于确认。默认使用 CPU、单进程加载数据，先观察完整过程。

首次运行会下载官方预训练权重（约 45 MB）和官方教程图片包（约 45 MB）。后续复用下载结果。训练用图片和生成的模型放在本目录的 `data/`、`outputs/` 中，不提交到 Git。网络访问失败时可先从 Notebook 给出的官方下载地址下载图片包，解压到 `data/hymenoptera_data/`。

## 先理解这几种操作

| 操作 | 初始参数 | 本次是否更新参数 |
|---|---|---|
| 从头训练 | 随机初始化 | 更新指定的可训练参数 |
| 使用预训练模型预测 | 已训练参数 | 不更新 |
| 固定特征提取器 | 预训练骨干 + 新分类层 | 只训练新分类层 |
| 微调 | 已训练参数 | 更新部分或全部已有网络参数 |

微调也是训练，仍需输入、标签、损失函数和优化器；它的区别是从已有参数继续学习。本例的第二阶段才更新预训练骨干。把输出类别文字换掉、调用 `eval()`、加载模型再预测，都不会完成微调。

课程中的 ONNX 文件主要用于推理。这个例子使用 PyTorch 预训练权重和可训练网络；训练完成后还可以另行导出 ONNX，接上课程中的推理流程。

## Notebook 的学习顺序

1. 建立图片与标签映射，划分训练、验证、测试数据。
2. 加载预训练权重及其前处理，替换 1000 类输出为 2 类。
3. 只训练分类层，理解 `requires_grad` 和优化器。
4. 解冻最后一组残差层，以更小学习率微调。
5. 检查冻结/解冻的权重，按验证集选模型，再评估测试集。
6. 保存权重、类别和输入规则，重新加载，验证预测一致。

默认每类仅取 32 张训练图、每阶段训练 2 个 epoch，目的是快速观察机制。将 `TRAIN_PER_CLASS` 改为 `None` 可以使用全部训练图。epoch 是把当前训练集完整遍历一遍，不是一个样本，也不是一次梯度更新。

微调不保证分数提高。本例同时保留两个阶段的候选模型，由验证集损失选择发布哪一个，测试集不参与选择。官方图片包本身是 ImageNet 的小子集，而预训练也使用 ImageNet；因此最终测试指标只能作为教学流程结果，不能据此宣称对预训练未见图片的泛化能力。

## 一次实际运行

在 Python 3.12.14、PyTorch 2.10.0、Torchvision 0.25.0、arm64 CPU 环境，用默认参数完整运行了 Notebook。划分为 64 张训练图、76 张验证图和 77 张测试图。

| 状态 | 验证集损失 | 验证准确率 |
|---|---:|---:|
| 新分类层未训练 | 0.9681 | 31.6% |
| 只训练分类层 | 0.6113 | 67.1% |
| 微调 layer4 和分类层 | 0.4294 | 86.8% |

验证集选择了微调模型；随后一次最终测试的准确率为 93.5%（72/77）。四个 epoch 的训练和逐轮验证合计约 12 秒，不包含首次下载、导入及初始化。权重冻结/更新检查、重新加载检查均通过。Notebook 保留了真实输出和图表，完整报告与模型生成在 `outputs/`；不同环境和重新实验的结果可能不同，数据范围限制如上所述。

## 资料来源

- [PyTorch 官方迁移学习教程](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html)
- [Torchvision ResNet18 权重与前处理](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet18.html)
- [PyTorch 保存与加载模型](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html)
- [PyTorch 与 Torchvision 版本配对](https://pytorch.org/get-started/previous-versions/)

[返回扩展练习目录](../README.md)
