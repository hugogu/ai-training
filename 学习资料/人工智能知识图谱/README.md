# 人工智能知识图谱

一张从领域与应用，逐步展开到算法、数学和数据原理的 Excalidraw 学习地图。包含 7 层、40 个知识卡片，以及垃圾邮件识别、大语言模型两条贯穿全图的实例路径。内容为核心知识索引，并非穷尽分类。

## 文件与打开方式

- [可编辑 Excalidraw 源文件](人工智能知识图谱.excalidraw)：打开 [Excalidraw](https://excalidraw.com/)，将文件拖入画布，或从菜单选择打开。卡片内的文字与图形均可编辑。
- [高清 PNG](人工智能知识图谱.png)：6440 × 8180 像素，适合放大阅读、插入资料。
- [矢量 SVG](人工智能知识图谱.svg)：可缩放，保留 Excalidraw 场景数据，也可重新导入编辑。
- [阅读预览](人工智能知识图谱-预览.png)：适合快速浏览整张图。

## 专题展开

- [线性代数：从数据表示到模型机制](../人工智能线性代数知识图谱/README.md)

## 七层结构

| 层 | 回答的问题 | 内容 |
| --- | --- | --- |
| 1. 目标与任务 | 用 AI 做什么？ | 视觉、语言、语音、预测推荐、机器人决策、知识推理 |
| 2. 技术路线 | 用什么方式解决？ | 符号方法、机器学习、组合方法；包含 RAG 与 Agent |
| 3. 学习方式 | 模型从什么反馈中学习？ | 监督、无监督、自监督、半监督、强化学习 |
| 4. 模型与算法 | 具体怎样计算？ | 线性概率、距离与核、树与集成、聚类降维、神经网络、序贯决策；进一步展开生成模型与注意力 |
| 5. 训练机制 | 参数如何变好？ | 表示、前向、损失、反向、更新与独立评估 |
| 6. 数学基础 | 上述机制依赖什么？ | 线性代数、微积分优化、概率统计、信息论与学习理论、离散数学 |
| 7. 数据原理 | 学到的规律能否信任？ | 代表性、质量标注、防泄漏、表示、分布变化、安全与追溯 |

实线表示展开或计算流程，虚线表示跨层关联。图中的分类是多个维度：视觉是应用任务，监督学习是学习方式，Transformer 是模型结构，不应放在同一分类层级里。

自监督通常归入广义无监督学习，在图中单列便于理解大模型。深度学习是机器学习的一部分；生成式 AI 描述生成内容的能力，可以采用不同结构及学习方式。RAG 与 Agent 是系统组合方式，不是与监督学习平行的学习范式。

## 读懂三个核心表达式

常见监督训练的目标是：

$$
\min_{\theta}\left[\frac{1}{N}\sum_{i=1}^{N}\ell\left(f_{\theta}(x_i),y_i\right)+\lambda\Omega(\theta)\right]
$$

模型 $f_{\theta}$ 根据输入 $x_i$ 产生预测；损失 $\ell$ 衡量预测与目标 $y_i$ 的差距；正则项 $\Omega$ 约束模型，$\lambda$ 控制约束强度。这个表达式是常见形式，并不涵盖所有 AI 算法。

梯度下降的一步是：

$$
\theta \leftarrow \theta-\eta\nabla_{\theta}L
$$

梯度由求导获得，优化器负责据此更新参数；图中的这个更新式表示基本梯度下降，Adam 另有动量与自适应缩放。树的划分、KNN 等不必采用这种训练流程。

缩放点积注意力为：

$$
\operatorname{Attention}(Q,K,V)=\operatorname{softmax}\left(\frac{QK^{\mathsf T}}{\sqrt{d_k}}\right)V
$$

$Q$ 与 $K$ 计算关注权重，$V$ 提供加权的内容；$d_k$ 是键向量的维度。图中使用 `sqrt(d_k)` 保证跨环境字体可读。

## 建议学习顺序

数据与划分 → 线性与概率基础 → 监督学习 → 无监督学习 → 神经网络与训练 → Transformer 与生成模型 → 强化学习与组合系统。

先理解一个小模型如何从数据、损失和更新中学到规律，再沿图扩展到复杂模型。

## 参考资料

- [Goodfellow、Bengio、Courville：《Deep Learning》](https://www.deeplearningbook.org/)：数学基础、神经网络、优化与表示学习。
- [scikit-learn User Guide](https://scikit-learn.org/stable/user_guide.html)：监督、无监督、模型选择与数据预处理。
- [scikit-learn：Common pitfalls and recommended practices](https://scikit-learn.org/stable/common_pitfalls.html)：训练测试划分、预处理一致性与数据泄漏。
- [Sutton、Barto：《Reinforcement Learning: An Introduction》](https://mitpress.mit.edu/9780262352703/reinforcement-learning/)，第二版，MIT Press，2018：价值函数、Bellman 关系、时序差分与策略学习。
