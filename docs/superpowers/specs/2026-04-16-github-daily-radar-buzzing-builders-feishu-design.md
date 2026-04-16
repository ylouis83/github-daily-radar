# GitHub Daily Radar × Buzzing × AI Builders 单卡日报设计

## 状态

本规范定义下一阶段的每日 Feishu 日报形态：

- `buzzing.cc` 进入发现源
- 科技类内容进入日报，但不取代 GitHub 主榜
- 现有 `AI Builders` 从独立卡片演进为主日报中的一个栏目
- 最终交付为一张单卡、三轨分层的 Feishu 日报

本设计是当前方向的权威说明，后续实现与计划应以此为准。

## 目标

把当前项目从“GitHub AI 雷达”升级为“以 GitHub 为主轴、吸收外部科技信号和 Builder 生态内容的单卡中文日报”，同时保持清晰边界，不退化成泛资讯聚合。

升级后的日报需要满足：

- 保持 GitHub 内容为主菜
- 让 `buzzing.cc` 作为稳定发现源接入
- 让科技类内容进入 Feishu，但以副栏目存在
- 保留 `AI Builders` 的独特价值，不把它并入科技热讯
- 把三类内容融合为一张结构清晰、视觉层级明确的 Feishu 卡片
- 保持局部失败可降级，不能因为一个外部源失效就整份停发

## 产品结果

系统每天产出一张中文 Feishu 单卡，整体读感像一份经过编辑挑选的 AI / 科技 / Builder 生态简报。

这张卡包含三条轨道：

1. `GitHub Radar`
2. `Tech Pulse`
3. `Builder Watch`

三轨共享同一标题、日期、统计和视觉体系，但内容角色不同：

- `GitHub Radar` 回答“今天最值得去 GitHub 看什么”
- `Tech Pulse` 回答“今天外部世界有什么值得知道的科技信号”
- `Builder Watch` 回答“今天 builder 生态里谁值得跟、哪篇内容值得点开”

## 非目标

这一轮设计不包括：

- 把项目改造成泛科技新闻站
- 为 Buzzing、Builders 和 GitHub 分别发送三张卡
- 引入前端、后台管理面板或人工审核台
- 将 `Buzzing` 条目强行塞进现有 `project / skill / discussion` 类型中
- 按用户画像个性化排序
- 大规模扩充非 AI / 非开发者生态的泛新闻来源

## 设计原则

### 1. GitHub 优先

本项目的主身份仍然是 GitHub Radar。外部发现源的职责是增强、补充和解释，而不是抢占主线。

### 2. 三轨分工必须稳定

同一条内容进入哪一轨，必须有规则，而不是由最终渲染时临时决定。

### 3. 来源原貌与日报视图分层

不同来源保留各自的原始结构，不在采集层强行统一；统一视图只在日报编排阶段生成。

### 4. 单卡交付

最终交付是一个单一 Feishu 卡片，而不是多卡拼接。信息应在一张卡内完成层次化组织。

### 5. 局部失败不拖垮全局

任一 collector、外部 feed 或 LLM 润色失败，都只能让某一轨变瘦，不得让整日报告失效。

## 用户体验

这张卡应该像一份“技术编辑晨报”：

- 先看到 GitHub 主榜
- 再看到外部科技热讯
- 最后看到值得跟的 builder 内容

阅读体验应满足：

- 主次分明，不让三轨视觉同权
- 每轨语气不同，不像同一模板复制三遍
- 中文为主，不直接泄露英文原文
- 热点、项目、观点各归其位
- 即使某一轨缺席，整卡仍然完整、可读

## 信息架构

建议采用“双源输入扩展为三类原生候选、单一日报视图输出”的结构。

### 输入源

保留或新增以下来源：

- GitHub 原生来源
  - `Trending`
  - `OSSInsight`
  - `Repo search`
  - `Skill collector`
  - `Discussion / Issues / PR`
- Buzzing 外部来源
  - `Show HN`
  - `Product Hunt`
  - `HN`
  - `Dev.to`
- AI Builders 来源
  - `follow-builders` 提供的 `X / podcasts / blogs`

### 原生候选层

建议保留三套原生对象，而不是强行统一：

- `Candidate`
  - 继续服务 GitHub 现有发现链路
- `ExternalTechCandidate`
  - 表示来自 Buzzing 的科技线索
- `BuilderSignal`
  - 表示 Builder 生态中的推文、播客、博客信号

### 日报视图层

在最终编排前，统一映射到日报视图对象，例如：

- `DailyBrief`
  - `github_radar`
  - `tech_pulse`
  - `builder_watch`
  - `stats`
  - `coverage_notes`

这层是 Feishu renderer 唯一需要感知的结构。

## 三轨定义

### 轨道 1：GitHub Radar

这是整份日报的第一主区，保留当前项目核心定位。

包含内容：

- GitHub 原生项目
- Skills / MCP / tools
- 高信号 proposal / RFC / design / roadmap 讨论
- 被 Buzzing 发现但能稳定映射为 GitHub repo 的外部线索

不包含：

- 无法映射 repo 的外部文章或新闻
- 纯 builder 观点内容

职责：

- 展示值得打开 GitHub 深看的内容
- 优先强调仓库、能力包、提案本身

### 轨道 2：Tech Pulse

这是科技副栏目，用于承载外部世界的技术和产品信号。

首批包含内容：

- `Show HN`
- `Product Hunt`
- `HN`
- `Dev.to`

优先级：

1. AI、开发者工具、MCP、编程 Agent、工作流
2. 与 Builder / AI 工具链强相关的 broader tech 动态

排除内容：

- 泛消费电子八卦
- 与 AI / 开发者生态弱相关的社会新闻
- 纯投融资快讯
- 只是某 GitHub 仓库的重复报道

职责：

- 展示“今天外部世界值得知道的科技信号”
- 不负责取代 GitHub 主榜

### 轨道 3：Builder Watch

这是 Builder 生态栏目，承接现有 `AI Builders` 的独立价值。

包含内容：

- 高价值 builder 线程
- 值得跟的播客
- 值得点开的 blog post

不包含：

- 纯新闻事件本身
- 与 builder 视角无关的普通技术报道

职责：

- 展示“谁值得跟、谁给出了独特视角”
- 提供人物、内容、观点的入口

## 栏目边界和升级规则

### Buzzing → GitHub 的升级规则

如果 Buzzing 条目满足以下条件，应优先升级进入 `GitHub Radar`：

- 指向明确 GitHub repo
- 或能通过稳定规则反查到 GitHub repo
- 并且 repo 本身值得占据日报名额

升级后的处理方式：

- 条目以 GitHub 项目身份展示
- 在原项目 `raw_signals` 中补充 `buzzing_heat` 或等价热度信号
- 该条目不再进入 `Tech Pulse`

### Buzzing → Tech Pulse 的保留规则

如果 Buzzing 条目无法稳定映射 repo，但技术相关性强，则保留在 `Tech Pulse`。

典型情况：

- 新产品发布
- 高信号技术文章
- 外部工具趋势
- 值得跟的 HN 热议

### AI Builders 的保留规则

`AI Builders` 不并入 `Tech Pulse`。

理由：

- 它的价值不在“报新闻”
- 而在“给出 builder 视角、人物线索和内容消费入口”

因此即便内容与科技热讯有关，也保留在 `Builder Watch`，但表达角度必须是“谁在解释这件事”而不是“这件事发生了什么”。

## 去重策略

### 1. 跨源项目去重

同一 repo 出现在 GitHub 原生来源和 Buzzing 来源时：

- 优先保留 GitHub 轨道
- Buzzing 只提供额外热度信号

### 2. 跨轨主题去重

如果同一主题同时出现在 `Tech Pulse` 和 `Builder Watch`：

- `Tech Pulse` 保留事件摘要
- `Builder Watch` 保留人物解读

两边可以同主题共存，但不能写成两条语义重复的摘要。

### 3. 主榜排他

如果某 repo 已作为 GitHub 主榜条目入选，不应再作为科技热讯重复出现。

### 4. Builder 不报纯新闻

`Builder Watch` 不应因为某事件很热就把它当新闻再讲一遍，必须体现“builder 谁说了什么”的增量价值。

## 建议配额

建议总量保持在一张 Feishu 卡可舒适阅读的范围内。

默认配额：

- `GitHub Radar`：8-12 条
- `Tech Pulse`：3-5 条
- `Builder Watch`：3-6 条

其中：

- `GitHub Radar` 是主菜，权重最高
- `Tech Pulse` 是科技副栏，短而准
- `Builder Watch` 是内容消费栏，轻但有辨识度

如当天质量不够：

- 优先压缩 `Tech Pulse`
- 再压缩 `Builder Watch`
- `GitHub Radar` 尽量保持稳定存在感

## 排序逻辑

### GitHub Radar

继续沿用现有的 stars、forks、comments、growth、release 等信号。

新增建议：

- `buzzing_heat_bonus`

它不应取代现有 GitHub 排序信号，只应作为加分项。

### Tech Pulse

建议按以下因子综合排序：

- 频道权重
- 热度指标
- AI / 开发者相关性
- 是否具备强行动价值或选题价值

默认频道权重建议：

- `Show HN`
- `Product Hunt`
- `HN`
- `Dev.to`

### Builder Watch

不建议按纯热度硬排。

更适合的排序因子：

- 信息密度
- 来源质量
- 是否提供独特视角
- 是否补充当天主榜或科技热讯

## Feishu 卡片设计

最终卡片采用“三轨单卡”的结构，而不是多张卡串发。

### 总体风格

建议采用：

- `Stripe` 的秩序感和统计面板
- `Claude` 的编辑感和阅读节奏
- `Linear` 的分区清晰度

在 Feishu 组件限制内，不追求花哨，而追求：

- 稳定层级
- 可扫读
- 视觉不过载

### 卡片结构

1. Header
2. Stats strip
3. GitHub Radar
4. Tech Pulse
5. Builder Watch
6. Footer

### Header

标题不再局限于 `GitHub 每日雷达`，而应反映三轨结构，例如：

- `AI Builder Radar · YYYY-MM-DD`
- `AI Daily Brief · YYYY-MM-DD`

副标题应明确三轨：

- `GitHub 主榜 · 科技热讯 · Builder Watch`

### Stats Strip

保留 `column_set`，但统计口径改为服务三轨：

- `GitHub 精选`
- `Tech Pulse`
- `Builders`
- `覆盖主题`

### GitHub Radar 渲染

这是视觉权重最高的部分。

建议：

- 前 3-5 条完整画像
- 剩余条目紧凑速览
- 继续使用项目 / 技能 / 讨论的类型化中文画像

### Tech Pulse 渲染

应比 GitHub 主区更轻，避免抢戏。

建议每条包含：

- 标题
- 来源标签
- 一句中文判断

不使用长画像，不展开过多技术细节。

### Builder Watch 渲染

不再以“一大段 remix 文本”作为核心呈现。

建议拆为三个轻分区：

- `X / Twitter`
- `Podcast`
- `Blog`

每块只放 1-3 条高价值内容。

### Footer

页脚应轻量但有说明力。

建议包括：

- 日期
- 数据源说明
- 漏斗转换，如 `82 candidates → 14 selected`

## 数据流设计

建议拆成五层：

1. `Source Collectors`
2. `Source-native candidates`
3. `Normalization + Promotion`
4. `Daily Brief Assembly`
5. `Feishu Rendering`

### 1. Source Collectors

负责抓取各来源原始数据。

### 2. Source-native candidates

保留每个来源自己的结构和字段，不在这里强行统一。

### 3. Normalization + Promotion

负责：

- Buzzing 条目是否升级为 GitHub 项目
- Buzzing 条目是否保留为 Tech Pulse
- Builders 条目如何进入 Builder Watch

### 4. Daily Brief Assembly

负责生成单一日报对象。

### 5. Feishu Rendering

只关心日报视图，不关心来源抓取细节。

## 错误处理和降级

任一来源失败，都应退化为“栏目缺失或变瘦”，而不是整日报错。

### Buzzing 失败

- `Tech Pulse` 缺席或条目减少
- `GitHub Radar` 和 `Builder Watch` 正常发送

### AI Builders 失败

- `Builder Watch` 缺席
- 不影响其他栏目

### Buzzing 子频道部分失败

- 只影响 `Tech Pulse` 数量
- 不阻断主卡

### LLM 润色失败

- GitHub 继续使用现有 fallback 模板
- `Tech Pulse` 回退为规则模板摘要
- `Builder Watch` 回退为结构化清单

## 测试策略

需要至少覆盖四层测试：

### 1. Collector tests

- Buzzing feed 解析
- AI Builders feed 解析
- 空数据与异常处理

### 2. Promotion tests

- Buzzing 条目升级为 GitHub 项目
- Buzzing 条目进入 Tech Pulse
- 同一 repo 跨源去重

### 3. Assembly tests

- 三轨日报对象生成
- 某一轨缺失时的结构稳定性

### 4. Card rendering tests

- 三轨都存在
- 只有两轨或一轨存在
- Footer / stats / coverage note 正常渲染

## 分阶段上线

建议分四个阶段逐步上线。

### Phase 1：Buzzing 进入发现源

- 新增 Buzzing collector
- 暂不改 Feishu 展示
- 只做发现增强和 repo 映射验证

成功标准：

- feed 稳定可抓
- 技术类筛选质量可接受
- repo 映射命中率足够高

### Phase 2：开启 Tech Pulse

- 新增科技副栏目
- GitHub 主榜结构保持稳定

成功标准：

- 外部科技内容确实提升日报价值
- 不显著冲淡 GitHub 主线

### Phase 3：AI Builders 合流为 Builder Watch

- 不再单独发送 AI Builders 整卡
- 改为主日报中的独立栏目

成功标准：

- Builder 栏目有稳定存在感
- 不和 Tech Pulse 语义重叠

### Phase 4：统一重做单卡视觉

- 完成三轨单卡
- 统一 stats、header、footer、栏目样式

成功标准：

- 单卡比当前双卡/独立卡方案更清晰
- 三轨共存但不混乱

## 风险与应对

### 风险 1：项目定位被稀释

风险：

- GitHub Radar 被泛科技内容冲淡

应对：

- 保持 GitHub 第一主区
- 强制 `Tech Pulse` 为副栏目

### 风险 2：同主题重复过多

风险：

- 主榜、科技热讯、Builder Watch 同时讲同一件事

应对：

- 以“项目 / 事件 / 解读”三种不同表达角度做边界控制

### 风险 3：卡片信息量过载

风险：

- 三轨并入单卡后变得难扫读

应对：

- 只给 GitHub 主榜前几条完整画像
- `Tech Pulse` 和 `Builder Watch` 保持轻量

### 风险 4：外部源稳定性不足

风险：

- Buzzing 或 follow-builders 暂时不可用

应对：

- 允许栏目降级
- 保证 GitHub 主榜独立可运行

## 成功标准

这次升级成功的标准是：

- `buzzing.cc` 成为稳定发现源
- 科技类内容进入日报，但不抢占主榜
- `AI Builders` 成功合流为一个有辨识度的栏目
- 最终日报成为一张三轨单卡
- 任一外部源失效时，日报仍可正常发送
- 用户读完后能清楚分辨：
  - GitHub 上该看什么
  - 外部科技圈发生了什么
  - 哪些 builders 值得跟
