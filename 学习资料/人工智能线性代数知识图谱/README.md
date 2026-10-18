# 线性代数 · 人工智能的数学语言

这是[人工智能总知识图谱](../人工智能知识图谱/README.md)中“线性代数”主题的展开。围绕 AI 所需的表示、运算、空间、分解、训练与数值实践组织，共 10 个主题区、54 张概念及示例卡片，另有 3 幅几何小图。

## 打开与阅读

- [Excalidraw 源文件](人工智能线性代数知识图谱.excalidraw)：打开 [Excalidraw](https://excalidraw.com/)，将文件拖入画布。文字、卡片、小图和连线均可编辑。
- [高清 PNG](人工智能线性代数知识图谱.png)：6440 × 12912 像素，适合放大阅读、插入课件。
- [矢量 SVG](人工智能线性代数知识图谱.svg)：可无损缩放，保留可重新导入 Excalidraw 的场景数据。
- [整图预览](人工智能线性代数知识图谱-预览.png)：适合快速定位主题。

## LaTeX 公式与编辑方式

图中的 241 处公式与数学记号均用 LaTeX 排版，经 MathJax 渲染为内嵌 SVG 矢量路径；上下标、分式、根式、求和、矩阵与列向量可清晰缩放。中文说明继续使用 Excalidraw 原生文字。分式和矩阵占用较高，卡片及整图已相应增高。

- [公式源码 JSON](公式源码.json)：按原文字块保存带 `$...$` 的 LaTeX 与中文说明；`sourceElement` 保留原文字块的标识、位置和分组信息。换行表示一行排版。
- 每个公式的 Excalidraw 图像元素还在 `customData.latex` 中保存对应源码；`sourceTextId` 可以关联到 JSON 中的文字块。
- 公式以图像元素呈现，可移动和缩放；在正式版 Excalidraw 中不能像普通文字那样直接修改公式内容，修改 LaTeX 后需要重新渲染。
- SVG 路径、颜色和公式素材全部内嵌在源文件中，打开图谱不需要额外字体或公式服务。

从上到下读主线，沿虚线看跨层关联：**投影 → 最小二乘；SVD → PCA；低秩 → LoRA**。不必一次背下所有公式；每次先说明对象是什么、形状为什么匹配、几何上发生了什么，再进入下一层。

| 主题区 | 核心问题 | AI 中的落点 |
| --- | --- | --- |
| 01 基本对象与形状 | 数字按什么结构组织？ | 样本、特征、批次、词元、权重、图像轴 |
| 02 核心运算与度量 | 数据如何组合和比较？ | 加权求和、线性层、广播、相似度检索 |
| 03 空间、方向与容量 | 哪些方向独立，哪些信息被丢弃？ | 子空间、冗余、投影、模型表达 |
| 04 方程与回归 | 有噪声或解不唯一时怎么拟合？ | 最小二乘、伪逆、岭回归 |
| 05 谱与矩阵分解 | 如何分离重要方向和特殊结构？ | SVD、特征分解、QR、Cholesky |
| 06 统计结构与表示 | 如何从数据提炼方向？ | 协方差、PCA、白化、核、低秩压缩 |
| 07 训练中的线性代数 | 网络如何前向与反向计算？ | 仿射层、Jacobian、梯度、Hessian、正则 |
| 08 模型落点 | 哪种数学机制用在哪里？ | Embedding、注意力、LoRA、卷积、推荐、GNN |
| 09 数值与数据边界 | 为什么公式正确还会算错？ | 条件数、精度、求解器、规模、数据泄漏 |
| 10 手算实例 | 能否用几个数解释完整机制？ | 余弦、回归投影、PCA、LoRA 参数量 |

## 先统一记号

本图以实数为主。单个向量通常按列写，数据批次按行组织：

$$
x\in\mathbb{R}^{d},\quad X\in\mathbb{R}^{N\times d},\quad W\in\mathbb{R}^{d\times h},\quad b\in\mathbb{R}^{h}.
$$

$N$ 是样本数，$d$ 是输入特征数，$h$ 是输出特征数；$T$ 在注意力中表示词元数。$\mathbb{R}$ 表示实数，$\in$ 表示“属于”，$\mathsf T$ 表示转置，$\odot$ 表示逐元素相乘，$@$ 表示代码中的矩阵乘法。

矩阵有两个轴，而矩阵的秩可以是 0、1、2 等不同数值。AI 框架中“张量的阶数/轴数”与“矩阵的秩”是两回事。

## 把关键公式读成一句话

### 矩阵乘法：许多次有组织的加权求和

$$
C=AB,\qquad C_{ij}=\sum_k A_{ik}B_{kj}.
$$

$A$ 为 $m\times n$、$B$ 为 $n\times p$，输出才会是 $m\times p$。共享的 $n$ 维被求和。矩阵乘法与逐元素乘法不是同一种运算；形状合法也不代表轴的业务含义正确。

### 投影：保留目标子空间中的部分

若 $Q$ 的列标准正交，即 $Q^{\mathsf T}Q=I$，则：

$$
p=QQ^{\mathsf T}x,\qquad r=x-p,\qquad Q^{\mathsf T}r=0.
$$

$p$ 是沿子空间保留的部分，$r$ 是被舍去的正交部分。$QQ^{\mathsf T}$ 一般不是单位矩阵；只有 $Q$ 还是方阵时才等于单位矩阵。

### 最小二乘：找到最接近目标的可表达结果

$$
\min_w\|Xw-y\|_2^2,\qquad X^{\mathsf T}(y-Xw)=0.
$$

$Xw$ 能表达的结果都在 $X$ 的列空间中。最优时，残差与这个空间正交。列满秩时解唯一；否则仍有最优预测，但参数可能不唯一。伪逆 $X^+y$ 给出最小范数的最小二乘解。

正规方程是数学关系，实际计算通常交给 QR 或 SVD 求解器，避免为了得到解而显式计算矩阵的逆。

### SVD：分开输入方向、拉伸程度与输出方向

$$
A=U\Sigma V^{\mathsf T}.
$$

完整分解的 $U,V$ 是正交矩阵；$\Sigma$ 是矩形对角结构，对角线上是非负奇异值。可以依次理解为“换到输入方向 → 沿各方向拉伸 → 换到输出方向”。

只保留最大的 $k$ 个奇异值及对应方向，可得到秩不超过 $k$ 的近似。小奇异值说明该方向作用较弱，但弱方向也可能包含对具体预测任务有用的信息。

### PCA：在中心化数据中找主要变化方向

$$
X_c=X-\mathbf{1}\mu^{\mathsf T},\qquad X_c=U\Sigma V^{\mathsf T},\qquad Z=X_cV_k.
$$

$\mu$ 是训练集特征均值；$V_k$ 的列是保留的主方向，$Z$ 是低维坐标。对 $N>1$ 的样本协方差，有：

$$
C=\frac{X_c^{\mathsf T}X_c}{N-1},\qquad \lambda_i(C)=\frac{\sigma_i^2}{N-1}.
$$

PCA 找高方差方向，通常不使用标签。标准化决定不同量纲如何参与比较，中心化决定围绕什么位置比较；两者不是同一步。标准化并不能保证变量不相关，白化则进一步处理保留方向间的协方差结构。

### 反向传播：维度一致的链式法则

设 $Z=XW+b$，令 $G=\partial L/\partial Z$，则：

$$
\frac{\partial L}{\partial W}=X^{\mathsf T}G,\qquad
\frac{\partial L}{\partial X}=GW^{\mathsf T},\qquad
\frac{\partial L}{\partial b}=\sum_{i=1}^{N}G_{i,:}.
$$

三个结果分别与 $W,X,b$ 的形状相同。如果损失取平均，平均因子已包含在 $G$ 内，不应机械地再除一次 $N$。加上激活函数后，还需先把激活的导数传递到 $G$。

PyTorch `Linear(d,h)` 把权重存成 $h\times d$，计算形式为 $XW_{\text{torch}}^{\mathsf T}+b$。这是存储约定不同，并非数学冲突。

### 注意力：先比较，再用分数加权取内容

单头自注意力中，$Q,K\in\mathbb{R}^{T\times d_k}$、$V\in\mathbb{R}^{T\times d_v}$：

$$
P=\operatorname{softmax}_{\text{row}}\left(\frac{QK^{\mathsf T}}{\sqrt{d_k}}+M\right),\qquad O=PV.
$$

$M$ 是加性掩码；$P$ 为 $T\times T$，$O$ 为 $T\times d_v$。矩阵乘法提供相似度计算和加权汇总，softmax 引入非线性。实际多头、多批次计算还包含对应的批次轴和头轴。

### LoRA：让权重更新经过小维度子空间

沿用本图 $W\in\mathbb{R}^{d\times h}$ 的约定：

$$
\Delta W=sAB,\quad A\in\mathbb{R}^{d\times r},\quad B\in\mathbb{R}^{r\times h},\quad \operatorname{rank}(\Delta W)\le r.
$$

$s$ 是缩放系数，图中为简洁省略。常见实现也会采用 $BA$ 的书写顺序和转置后的权重存储，核对形状即可。LoRA 学习低秩的更新，不要求原始权重本身低秩，也不是必须先对整个原始权重做 SVD。模型常同时在多个矩阵上应用 LoRA；图中参数例子只针对一个权重矩阵，不包含优化器、激活和其他参数的内存。

## 推荐学习路线与自检

先学 01—03，能说明向量、内积、矩阵乘法、秩、基、正交与投影。再用 04 的回归理解“拟合是投影”，用 05—06 理解“降维是在选择方向”。最后进入 07—08 的训练与现代模型，并随时回查 09 的数值和数据条件。

图中四个小例子已经过数值核对：余弦为 0.8；无截距回归系数为 $11/14$ 且残差与输入列正交；PCA 例子的协方差特征值为 2、0，一维可重建；单个 $1000\times1000$ 权重的秩 8 LoRA 更新有 16,000 个因子参数。

读完可尝试解释：为什么反向传播中会出现转置？为什么 PCA 能用 SVD 实现？为什么低秩更新能节省训练参数？为什么满秩并不保证数值稳定？

## 参考资料

- [Deep Learning，第 2 章 Linear Algebra](https://www.deeplearningbook.org/contents/linear_algebra.html)：AI 所需线性代数的背景与基础对象。
- [Mathematics for Machine Learning](https://mml-book.github.io/)：线性代数、解析几何、矩阵分解、向量微积分与回归/PCA 的学习顺序。
- [NumPy Linear Algebra](https://numpy.org/doc/stable/reference/routines.linalg.html)：求解、最小二乘、伪逆、分解、范数与条件数的计算入口。
- [scikit-learn：PCA 与矩阵分解](https://scikit-learn.org/stable/modules/decomposition.html#pca)：中心化、PCA 与分解方法。
- [scikit-learn：Pairwise Metrics and Kernels](https://scikit-learn.org/stable/modules/metrics.html)：相似度与核方法。
- [PyTorch Linear](https://docs.pytorch.org/docs/stable/generated/torch.nn.Linear.html)：仿射层及参数形状。
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762)：缩放点积注意力。
- [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)：低秩参数适配。
