# 辅助记单词的 agent

描述：用户在终端中输入英文单词，返回中文翻译、英译英定义、
发音信息、例句、词形变化与用法/记忆提示；
用户确认后将该词存入生词本。

## 目标与范围
- 提供可靠的单词释义与发音信息，避免凭空生成。
- 支持查询、确认、写入的闭环流程，并可配置自动写入策略。
- 输出透明：显示来源、置信度与关键步骤。

## 核心流程（建议）
1. 解析输入：识别单词与参数（如 `--no-save`、`--update`、`--dry-run`）。
2. 本地查询：先查生词本，命中则展示已有信息并询问是否更新。
3. 词典校验：优先使用本地词典（当前工作目录），
   必要时再调用在线词典 API；未命中时提供模糊候选列表，
   并支持交互选择重试。
4. 汇总输出：展示词性、英译英、中文翻译、发音（IPA/音频）、例句、
   词形变化与用法/记忆提示。
5. 用户确认：提供 `是/否/总是` 三选项；“总是”写入全局偏好。
6. 写入存档：规范化词形（小写/词元），幂等写入，记录来源与时间。

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
`user_note`、`status`。
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

## 流程不合理点与改进
- 仍需完善词形规范化（lemma 推导）与去重策略，避免同词多条冗余记录。
- 建议提供缓存重建/禁用开关，便于诊断与性能对比。
- 可选：为模型响应增加缓存，避免重复调用。

## 安全与隐私
- 不上传用户生词本内容；仅发送查询词与必要上下文。
- API Key 使用环境变量管理，并提供 `.env.example` 说明。
