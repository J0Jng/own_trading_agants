<div align="center">

# TradingAgents — 国内数据定制版

**基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (v0.3.1+) 的个人实验/研究 fork**
多智能体 LLM 金融交易框架 — 带**妙想(MX) + Tushare 国内数据源**与 **OpenCode LLM 提供商**

</div>

---

> ⚠️ **本仓库是深度定制的个人 fork**：数据源以国内中文源为主（妙想 / Tushare），LLM 提供商以 OpenCode 网关为主。框架核心机制（多智能体分工、结构化辩论、回溯、持久化）与上游一致。**用于研究/学习，不构成任何投资建议。**

## 与上游的差异

| 维度 | 上游 TauricResearch/TradingAgents | 本 fork |
|---|---|---|
| **股票/行情数据源** | Yahoo Finance / Alpha Vantage / FRED / Polymarket | **妙想 MX (东方财富) 优先，Tushare 兜底** |
| **新闻/基本面** | Alpha Vantage / Yahoo | 妙想 MX + Tushare |
| **LLM 提供商默认** | openai (gpt-5.x) | **codingplan** (火山方舟 Coding Plan, `ark-code-latest`) |
| **默认数据供应商** | yfinance | 保留 yfinance/alpha_vantage 但按 MX/Tushare 优先路由 |
| **新增配置** | — | `mx_min_call_interval` / `mx_request_timeout` |

### 数据层
- **MX 妙想**：东方财富的自然语言金融数据接口（`MX_APIKEY`）。覆盖 OHLCV、技术指标、基本面、三大报表、新闻、内部交易。内置调用间隔限流（默认 1.2s）与状态码 113 的退避重试。
- **Tushare**：国内行情/财务数据（`TUSHARE_TOKEN`），在 MX 不可用或失败时兜底。
- 路由层沿用了上游的**类型化错误处理**（`NoMarketDataError` / `VendorRateLimitError` / `VendorNotConfiguredError`）与可选类别降级（macro/prediction 失败不中断主分析）。

### LLM 提供商
- 默认 `llm_provider: codingplan`（模型固定 `ark-code-latest`），读取 **`CODINGPLAN_API_KEY`**，走火山方舟 Coding Plan 的 OpenAI 兼容接口（`https://ark.cn-beijing.volces.com/api/coding/v3`，启用 Responses API）。模型在控制台统一切换，也可用具体 Model Name（`doubao-seed-2.0-lite` / `kimi-k2.7-code` / `minimax-m3` / `doubao-seed-2.1-turbo` / `deepseek-v4-flash` / `glm-5.3` / `doubao-seed-evolving` / `deepseek-v4-pro` / `glm-5.3-flash` 等）。注意不支持 `Auto` 模式。
- 上游其它提供商（OpenAI、Anthropic、Google、DeepSeek、Qwen、GLM、MiniMax、Ollama、OpenRouter、Azure、Bedrock）全部保留，切换 `llm_provider` 即可。也可用 `opencode`（OpenCode Go 网关）。

---

## 快速开始

### 1. 克隆 & 安装

```bash
git clone https://github.com/J0Jng/own_trading_agants.git
cd own_trading_agants

# 使用 uv（推荐）或任意虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
uv pip install -e .
# 或 pip install .
```

### 2. 配置密钥（`.env`）

复制 `.env.example` 为 `.env`，至少填入你使用的数据源和 LLM 提供商密钥：

```bash
# ---- 数据源（至少一个）----
MX_APIKEY=your-mx-miaoxiang-key        # 妙想/East Money（推荐）
TUSHARE_TOKEN=your-tushare-token       # Tushare 兜底

# ---- LLM 提供商（默认 codingplan）----
CODINGPLAN_API_KEY=your-codingplan-key   # 火山方舟 Coding Plan（默认提供商，模型 ark-code-latest）
# 备用/其它: OPENCODE_API_KEY=...  或  OPENAI_API_KEY=...
```

> 默认 `llm_provider: codingplan`、模型 `ark-code-latest`。若要换用其它提供商，设 `TRADINGAGENTS_LLM_PROVIDER` 环境变量（如 `opencode` / `openai` / `deepseek` / `qwen-cn` 等）或直接改 `default_config.py`。

### 3. 运行

```bash
# 交互式 CLI
tradingagents
# 或
python -m cli.main

# 或直接跑 main.py（分析 NVDA 指定日期）
python main.py
```

---

## 框架机制

TradingAgents 模拟真实交易公司的运作，把复杂交易决策拆给多个专业 LLM 角色，通过结构化辩论协作给出决策。

### 角色分工
- **分析师团队**：基本面 / 情绪 / 新闻 / 技术分析师，各自评估公司的一个侧面。
- **研究员团队**：牛 / 熊研究员对分析师结论进行结构化辩论，权衡收益与风险。
- **交易员 Agent**：综合分析师与研究员报告，决定交易时机与仓位。
- **风控团队 & 组合经理**：持续评估组合风险，组合经理批准/否决交易提案。

### Python 用法

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["deep_think_llm"] = "ark-code-latest"   # 复杂推理（codingplan 默认模型）
config["quick_think_llm"] = "ark-code-latest"  # 快速任务
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

数据源可通过配置选择供应商（MX/Tushare/yfinance/alpha_vantage），或反向剔除：

```python
config["data_vendors"] = {
    "core_stock_apis": "mx,tushare",     # MX 优先，Tushare 兜底
    "technical_indicators": "mx,tushare",
    "fundamental_data": "mx",
    "news_data": "mx",
}
```

---

## 持久化与恢复
- **决策日志**：每次运行追加到 `~/.tradingagents/memory/trading_memory.md`，下次同标的分析时注入过往决策作参考（`TRADINGAGENTS_MEMORY_LOG_PATH` 可改路径）。
- **检查点恢复**：`--checkpoint` 开启后，LangGraph 逐节点保存状态，崩溃/中断可断点续跑（SQLite，存于 `~/.tradingagents/cache/checkpoints/`）。

---

## 复现性说明
LLM 驱动，两次运行不一定完全一致（模型采样与实时数据都会变）。要更可复现：
- 固定分析日期（价格/指标窗口固定），但新闻/社交数据仍反映"当下"。
- 设 `temperature=0`；若想更严格可换非 reasoning 模型。

---

## 致谢与引用
本仓库基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 深度定制，保留对原作者的致谢：

```bibtex
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```

Apache-2.0 许可证，详见 [LICENSE](LICENSE)。