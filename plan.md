# 辅助记单词的 agent

描述：用户在终端中输入英文单词，返回中文翻译、英译英定义、
发音信息、例句、词形变化与用法/记忆提示；
用户确认后将该词存入生词本。

## 目标与范围
- 提供可靠的单词/科研术语释义与发音信息，避免凭空生成。
- 支持查询、确认、写入的闭环流程，并可配置自动写入策略。
- 输出透明：显示来源、置信度与关键步骤。

## 核心流程（建议）
1. 解析输入：识别单词、连字符术语或多词短语与参数（如 `--no-save`、`--update`、`--dry-run`）。
2. 本地查询：先查生词本，命中则展示已有信息并询问是否更新。
3. 词典校验：优先使用本地词典（当前工作目录），
   必要时再调用在线词典 API；未命中时提供模糊候选列表，
   并支持交互选择重试。对连字符/多词科研术语，直接跳过本地词典，
   必须在允许远程/本地 LLM 时将完整术语交给模型翻译；如果模型不可用，
   直接提示失败，禁止词组拼接或逐词翻译兜底。
4. 汇总输出：展示词性、英译英、中文翻译、发音（IPA/音频）、例句、
   词形变化与用法/记忆提示。
5. 用户确认：提供 `是/否/总是` 三选项；“总是”写入全局偏好。
6. 写入存档：规范化词形（小写/词元），幂等写入，记录来源与时间。

## 最小 Agent Loop 设计
目标：在现有 CLI 上引入最小 LLM 驱动循环，但保持可控、可解释、可回退。

### 关键状态
- `word`：当前查询词（可能被纠错/选择更新）。
- `candidates`：模糊匹配候选列表。
- `dict_entry`：本地词典结果。
- `enhancement`：模型补充结果（可选）。
- `save_policy`：保存策略（prompt/always/never）。
- `step_count`：循环步数（用于终止）。

### 可调用工具（actions）
- `wordbook.find(word)`：查生词本。
- `dictionary.lookup(word)`：查本地词典。
- `dictionary.suggest(word)`：生成候选并允许交互选择。
- `provider.enhance(entry)`：模型补充（词形/用法/记忆/例句）。
- `provider.review_coach(entry)`：纠错提示与易混词建议（可选）。
- `wordbook.upsert(entry)`：保存或更新词条。
- `update_save_policy(choice)`：更新全局偏好。

### Loop 流程（MVP）
1. Observe：加载偏好与配置，读取输入词与参数。
2. Decide：根据状态选择下一步工具（优先本地词典，再模型补充）。
3. Act：执行工具并收集输出（结果或错误）。
4. Render：输出摘要与词条内容。
5. Save：按策略决定是否写入生词本。
6. Terminate：成功、用户取消、候选为空、或达到 `max_steps`。

### 控制与回退
- `max_steps`：默认 6，避免无限循环。
- 提供 `--loop` 连续学习模式；输入空行或 `q/quit/exit` 可退出。
- 提供 `--agent` 模式，让模型选择 review/lookup/exit 等动作。
- LLM 决策输出采用结构化 JSON（tool + args），并做严格校验。
- LLM 不可用或解析失败时，回退到当前确定性流程。
- 仅记录工具结果与摘要，不保存链路推理。

## 复习与学习目标
- `--review` 进入复习模式，用户自评 0-5 分，按 SM-2 调整间隔。
- `--goal` 设置每次会话目标（复习/新词条数量），并写入配置。
- 答错时可调用模型生成纠错提示与易混词，写入 `review_tip`/`confusions`。
- 模型可用时，复习会补全缺失的英文定义、例句、词形、用法、记忆提示。
- 缺失发音时，可调用模型补全 IPA（仅作为补充，不覆盖已有发音）。

## 工具与数据
- 查询工具：本地生词本检索、本地词典检索、可选在线词典 API、
  模糊匹配建议。
- 写入工具：将单词追加到 `data/wordbook.csv`，并做去重。
- 词典数据：使用主流词典（如 ECDICT `ecdict.csv`、WordNet、Wiktionary）
  下载到当前工作目录。
- 缓存：`data/cache/` 保存词典索引（SQLite），加速启动与查询。
- 便捷命令：可通过 shell 函数提供 `w` 入口，支持跨目录调用。

## 生词本格式（CSV）
字段建议：`word`、`lemma`、`pos`、`pronunciation`（IPA/美音/英音）、
`definitions_en`、`translations_zh`、`examples`、`word_forms`、`usage_tips`、
`mnemonics`、`source`、`model`、`confidence`、`created_at`、`updated_at`、
`user_note`、`status`、`review_due`、`review_interval_days`、`review_ease`、
`review_streak`、`review_lapses`、`reviewed_at`、`review_tip`、`confusions`。
CSV 需包含表头，UTF-8 编码，每行一词。

## 模型与 API 选择（可配置多家）
当前开源项目里常见的做法是支持 OpenAI-Compatible 接口，
因生态成熟、SDK 统一。
常见模型/方案：
- 远程 API：OpenAI、Anthropic、Google Gemini、Azure OpenAI。
- 本地/开源：Ollama/LM Studio + Llama 3、Mistral、Qwen、Yi、DeepSeek。
建议：词义以“本地词典”作为主来源，在线 API 仅作补全与兜底；
模型只负责英译英润色、例句生成、词形变化与用法/记忆提示补充。
通过环境变量切换：`PROVIDER`、`MODEL`、`API_BASE`、`API_KEY`。

## 可靠性 / 透明性 / 可控性
- Reliable：本地词典优先、超时重试、低置信度不写入、
  结构化校验与日志记录。
- Transparent：展示来源、置信度、工具调用摘要；模糊匹配明确标注。
- Controllable：支持 `--dry-run`、`--no-remote`、自动写入开关、单次覆盖偏好。
- 可读性：终端输出使用高对比度颜色（偏好写入配置，`NO_COLOR=1` 临时关闭）。
- 发音：支持本地 TTS 播放，偏好写入配置（macOS 使用 `say`）。

## 流程不合理点与改进
- 仍需完善词形规范化（lemma 推导）与去重策略，避免同词多条冗余记录。
- 建议提供缓存重建/禁用开关，便于诊断与性能对比。
- 可选：为模型响应增加缓存，避免重复调用。

## 安全与隐私
- 不上传用户生词本内容；仅发送查询词与必要上下文。
- API Key 使用环境变量管理，并提供 `.env.example` 说明。
