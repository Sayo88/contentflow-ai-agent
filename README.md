# ✨ ContentFlow AI  

**一站式多模态营销 Agent**

ContentFlow AI 是一个强大的自动化内容中枢 MVP，旨在将产品卖点一键转化为全网多渠道的高转化图文与短视频物料。通过深度集成大语言模型（LLM）与生图大模型，系统实现了从“内容构思 -> 视觉生成 -> 沉浸式审查 -> 多端自动化分发”的完整闭环，大幅降低运营工时并提升营销 ROI。

### 🌟 核心功能与亮点 (Features)

* **🧠 多模态并发创作**：输入一次产品信息，即可根据各平台算法特性（微信公众号、LinkedIn、Twitter、Facebook、Instagram 等）并发生成专属语气的营销文案、配套视觉提示词（Prompt）以及短视频脚本（Caption）。
* **🎨 AI 视觉与排版引擎**：内置文本到图像（Text-to-Image）生成能力，并自动将渲染好的图像无缝嵌入富文本编辑器中，实现图文混排。
* **📱 沉浸式真机预览**：独创的多端渲染引擎，可在后台实时预览文案在移动端/桌面端的真实瀑布流排版效果（支持各大主流平台原生 UI 模拟）。
* **⚡ Webhook 自动化分发流**：只需点击一键推送，系统即会通过 Webhook 触发底层自动化工作流（如 Make.com），将物料精准分发至对应账号矩阵。
* **📊 数据看板与资产沉淀**：内置历史发布库与模拟数据大屏，实时追踪 AI 节省工时、生成的物料数量及跨渠道的 ROI 效能。

---

### 🛠️ 技术栈 (Tech Stack)

* **前端框架**：Streamlit (支持全响应式流式 UI)
* **大模型引擎**：硅基流动 (SiliconFlow) / OpenAI 兼容接口（文本：Qwen2.5-7B-Instruct，视觉：Kwai-Kolors）
* **核心组件**：Streamlit-Quill (富文本编辑器)、Streamlit-Option-Menu (自定义导航)
* **自动化底座**：Make.com / Webhook (负责跨平台 API 路由与异步分发)

---

### 🚀 快速启动 (Quick Start)

#### 1. 克隆项目
```bash
git clone [https://github.com/Sayo88/contentflow-ai-agent.git](https://github.com/Sayo88/contentflow-ai-agent.git)
cd contentflow-ai-agent
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 配置环境变量 (Secrets)
为保障系统安全，API 密钥和 Webhook 地址等敏感信息需要保存在本地环境变量中。请在项目根目录下创建一个 `.streamlit` 文件夹，并在其中新建一个 `secrets.toml` 文件：

```toml
# .streamlit/secrets.toml (注意：请勿将此文件推送到 GitHub)

# 主力供应商：硅基流动 (SiliconFlow) 或其他 OpenAI 兼容源
api_key = "sk-你的真实API_KEY"
base_url = "[https://api.siliconflow.cn/v1](https://api.siliconflow.cn/v1)"

# 备用供应商：全能中转站
proxy_api_key = "sk-你的备用API_KEY"
proxy_base_url = "https://你的中转站URL/v1"

# 自动化分发 Webhook (Make.com 等)
MAKE_WEBHOOK_URL = "[https://hook.us2.make.com/你的真实WebhookID](https://hook.us2.make.com/你的真实WebhookID)"
```

#### 4. 本地运行
```bash
streamlit run app_v2.py
```
