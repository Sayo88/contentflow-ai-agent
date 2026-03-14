import streamlit as st
import json
import numpy as np
import requests
import pandas as pd
from streamlit_quill import st_quill
from openai import OpenAI
from streamlit_option_menu import option_menu  # 引入酷炫导航栏

# ---------------- 全局配置 ----------------
st.set_page_config(page_title="✨ ContentFlow AI | 智创内容中枢", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none !important;}
    header {background-color: transparent !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# 尝试从系统环境变量/保险箱读取，如果找不到就给个假字符串
api_key = st.secrets.get("api_key", "请在系统配置中填入你的API_KEY")
base_url = "https://api.siliconflow.cn/v1"
model_name = "Qwen/Qwen2.5-7B-Instruct"

# ---------------- 初始化系统的“记忆”（核心逻辑） ----------------
# 用于跨页面存储 AI 生成的内容，模拟数据库
if "inbox_tasks" not in st.session_state:
    st.session_state.inbox_tasks = {}
if "approved_count" not in st.session_state:
    st.session_state.approved_count = 1245
if "saved_hours" not in st.session_state:
    st.session_state.saved_hours = 320.0
if "scene_images" not in st.session_state:
    st.session_state.scene_images = {}

# ---------------- 核心 AI 引擎 ----------------
def generate_real_text(platforms, project_name, highlights, language, objective):
    results = {}
    system_prompt = f"你是一个海外营销专家。为以下产品写营销文案：\n【产品】{project_name}\n【卖点】{highlights}\n【目标】{objective}\n【语言】{language}"
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        for plat in platforms:
            user_prompt = f"目标平台：{plat}\n请输出符合该平台调性的文案。"
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.7,
                max_tokens=512
            )
            results[plat] = response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI 异常：{e}")
    if not results:
        results = {"生成失败": "生成失败，请检查 API 配置"}
    return results

def generate_real_image(prompt_text):
    """
    调用 SiliconFlow 生图 API，返回真实图片 URL。
    遵循要求：始终使用 images 键解析 JSON，payload 包含 num_inference_steps 和 guidance_scale，timeout=120。
    如果解析失败，不返回假图，仅打印错误信息。
    """
    api_url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    wrapped_prompt = f"高质量摄影大片，电影感光影，8k分辨率，商业广告。{prompt_text}"
    payload = {
        "model": "Kwai-Kolors/Kolors",
        "prompt": wrapped_prompt,
        "image_size": "1024x1024",
        "batch_size": 1,
        "num_inference_steps": 20,
        "guidance_scale": 7.5,
    }
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            print(f"生图 API HTTP {resp.status_code}: {resp.text[:500]}")
            return
        data = resp.json()
        # 必须严格使用 images 键
        images = data.get("images", None)
        if not images or not isinstance(images, list) or len(images) == 0:
            print("生图 API 返回格式异常: 未找到 images 键或其为空")
            return
        first = images[0]
        # images可能为字符串url或dict对象
        if isinstance(first, str):
            return first
        elif isinstance(first, dict):
            url = first.get("url") or first.get("image")
            if url:
                return url
            b64 = first.get("b64_json")
            if b64:
                return f"data:image/png;base64,{b64}"
            print("生图 API 单项图片对象缺少 url/image/b64_json")
        else:
            print("生图 API 图片项类型非字符串或字典")
    except requests.exceptions.RequestException as e:
        print(f"生图 API 网络异常: {e}")
    except Exception as e:
        print(f"生图 API 异常: {e}")
    # 失败情况直接返回 None，按要求不提供兜底假图

def generate_real_video_script(project_name, highlights, language):
    """调用大模型生成结构化视频分镜脚本，返回 DataFrame；解析失败时返回兜底 DataFrame"""
    system_prompt = "你是一个资深商业广告导演。请根据用户提供的产品和卖点，构思一个 4 个镜头的短视频分镜脚本。"
    user_prompt = f"产品：{project_name}\n卖点：{highlights}\n语言：{language}\n\n请**只能**输出一个合法的 JSON 数组（不要 Markdown 标记，不要多余废话）。每个 JSON 对象必须包含四个 Key：\"时间轴\", \"画面描述\", \"音效/旁白\", \"视频生成 Prompt\"。"
    fallback_df = pd.DataFrame([["-", "解析失败或未生成，请重试", "-", "-"]], columns=["时间轴", "画面描述", "音效/旁白", "视频生成 Prompt"])
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7,
            max_tokens=1024
        )
        raw = response.choices[0].message.content.strip()
        # 去除可能的 Markdown 代码块包裹
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return pd.DataFrame(parsed)
    except Exception as e:
        st.error(f"视频脚本生成异常：{e}")
    return fallback_df

def revise_real_text(original_content, feedback):
    """根据人工修改意见，重新调用大模型修改文案"""
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        # 专门定制的重写 Prompt
        prompt = f"你是一个资深营销编辑。这是原来的文案初稿：\n\n{original_content}\n\n这是客户提出的修改意见：\n【{feedback}】\n\n请你严格按照修改意见，对原初稿进行重写优化。只输出修改后的正文即可，不要附带任何多余的解释。"
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=512
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"重写异常：{e}")
        return original_content

# ---------------- 左侧绝美导航栏 ----------------
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>✨ ContentFlow AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>一站式多模态营销 Agent V1.0</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # 核心菜单组件（支持“立即前往审核中心”传送门）
    default_idx = 1 if st.session_state.pop("navigate_to_inbox", False) else 0
    selected_page = option_menu(
        menu_title=None,
        options=["✨ 创作中心", "📥 待办审核", "📊 数据看板"],
        icons=["magic", "inbox", "bar-chart"],
        menu_icon="cast",
        default_index=default_idx,
    )

# ==================== 页面 1：创作中心 (Create) ====================
if selected_page == "✨ 创作中心":
    st.title("✨ 智能宣发创作中心")
    st.markdown("输入产品信息，一键并发生成多渠道图文与视频脚本。")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("项目名称", "大疆 DJI Osmo Pocket 3 云台相机")
            language = st.selectbox("语言", ["中文", "English"])
            objective = st.text_input(
                "宣发目的",
                "全网爆款种草与短视频带货转化，重点突出便携性和画质，吸引 Vlogger 购买"
            )
        with col2:
            platforms = st.multiselect("发布平台", ["微信公众号", "LinkedIn", "Twitter"], default=["微信公众号", "LinkedIn"])
            content_formats = st.multiselect("内容形式", ["纯文案", "图文排版", "视频脚本"], default=["图文排版", "视频脚本"])
            highlights = st.text_area("宣发重点", "1英寸CMOS传感器，4K/120fps超高清画质，三轴云台机械增稳，全像素疾速对焦，智能跟随6.0，原生横竖拍无损切换")

    if st.button("🚀 呼叫 AI 引擎生成", use_container_width=True, type="primary"):
        # 在按钮点击最开始清空图片 session 状态
        st.session_state.current_real_image = None

        if not content_formats:
            st.warning("⚠️ 请至少选择一种内容形式。")
        else:
            need_text = "纯文案" in content_formats or "图文排版" in content_formats
            need_video = "视频脚本" in content_formats

            new_texts = None
            video_df = None

            if need_text:
                with st.spinner("🧠 AI 正在写文案..."):
                    new_texts = generate_real_text(platforms, project_name, highlights, language, objective)
                st.session_state.inbox_tasks = new_texts if new_texts else {}
            else:
                st.session_state.inbox_tasks = {"视频分镜任务": "请查看下方视频分镜表"}

            # 保证总是用最新 generate_real_image，直接把结果存入 session_state
            if "图文排版" in content_formats:
                with st.spinner("🎨 AI 画师正在渲染配图..."):
                    new_real_image_url = generate_real_image(highlights)
                    st.session_state.current_real_image = new_real_image_url

            if need_video:
                with st.spinner("🎬 AI 导演正在构思视频分镜..."):
                    video_df = generate_real_video_script(project_name, highlights, language)
                    st.session_state.current_video_script = video_df
            else:
                st.session_state.current_video_script = None

            text_ok = need_text and new_texts and new_texts != {"生成失败": "生成失败，请检查 API 配置"}
            video_ok = need_video and video_df is not None and len(video_df) > 0
            if need_video and video_ok:
                first_row = video_df.iloc[0]
                if str(first_row.get("画面描述", "")).strip() == "解析失败或未生成，请重试":
                    video_ok = False
            task_success = text_ok or video_ok

            if task_success:
                st.success("✅ 生成完毕！任务已自动流转至【📥 待办审核】页面，请前往审批。")
                st.balloons()
                if st.button("👉 立即前往审核中心", use_container_width=True, type="primary"):
                    st.session_state.navigate_to_inbox = True
                    st.rerun()
            else:
                st.error("❌ 生成失败，请检查 API 配置或重试。")

# ==================== 页面 2：待办审核 (Inbox) ====================
elif selected_page == "📥 待办审核":
    st.title("📥 宣发物料审核中心")
    
    if not st.session_state.inbox_tasks:
        st.info("💡 当前没有待审核的任务，请先去【✨ 创作中心】生成吧！")
    else:
        st.markdown("##### 👩‍💻 人工复核与排版排期")
        st.caption("AI 初稿已送达。您可以直接在下方富文本框内进行加粗、标红、插入链接等精细化排版，确认无误后一键分发。")
        
        for plat, content in st.session_state.inbox_tasks.items():
            with st.container(border=True):
                st.markdown(f"### 📍 目标渠道：{plat}")
                
                # 🚨 绝杀一：给每个平台注册一个“版本号”（如果还没有的话，就设为1）
                version_key = f"version_{plat}"
                if version_key not in st.session_state:
                    st.session_state[version_key] = 1

                # --- 🎯 图文穿插主图逻辑（始终从 current_real_image 取最新，且 picsum 警告而不插）---
                img_url_val = st.session_state.get("current_real_image")
                if img_url_val and str(img_url_val).strip():
                    if "picsum" in str(img_url_val):
                        st.warning("⚠️ 未能成功生成主图，当前为占位图。请重试或联系技术支持。")
                        injected_content = content
                    else:
                        real_image_html = f'<br><br><img src="{img_url_val}" width="100%" style="border-radius:10px; margin: 10px 0;"><br><br>'
                        insert_pos = content.find('\n\n')
                        if insert_pos != -1:
                            injected_content = content[:insert_pos] + real_image_html + content[insert_pos:]
                        else:
                            injected_content = content + real_image_html
                else:
                    injected_content = content

                # 🚨 绝杀二：把版本号拼接到 key 里面！(例如 quill_微信公众号_1)
                dynamic_key = f"quill_{plat}_{st.session_state[version_key]}"
                edited_content = st_quill(value=injected_content, html=True, key=dynamic_key)
                
                # ================= 🚀 核心人机协同重写区 =================
                st.markdown("##### 💬 AI 协同打磨")
                feedback = st.text_input(
                    f"对 {plat} 内容不满意？输入指令让 AI 重新打磨：", 
                    placeholder="例如：语气再激昂一点、把最后一段删掉、多加几个 Emoji...", 
                    key=f"fb_{plat}"
                )
                
                col_action1, col_action2 = st.columns(2)
                with col_action1:
                    if st.button("🔄 根据意见重写", key=f"rewrite_{plat}", use_container_width=True):
                        if feedback:
                            with st.spinner("🧠 AI 正在疯狂理解你的意图并重写中..."):
                                # 1. 呼叫大模型重写
                                new_content = revise_real_text(content, feedback)
                                # 2. 覆盖系统记忆
                                st.session_state.inbox_tasks[plat] = new_content
                                
                                # 🚨 绝杀三：让版本号 +1 ！彻底摧毁旧编辑器，逼迫系统生成带新数据的全新编辑器！
                                st.session_state[version_key] += 1
                                
                                # 3. 强制页面重绘
                                st.rerun()
                        else:
                            st.warning("⚠️ 请先在上方输入框写下你的修改意见喔！")
                            
                with col_action2:
                    if st.button(f"✅ 审核通过，一键推送至 {plat}", key=f"pub_{plat}", type="primary", use_container_width=True):
                        st.success(f"🎉 成功！您修改后的图文排版已通过 API 同步至 {plat} 定时发布队列！")
                        st.balloons() # 满屏气球，给面试官带来视觉冲击！
                        st.session_state.approved_count += 1
                        st.session_state.saved_hours += 2.5
        # ================= 附属视觉资产区（高逼格展示） =================
        st.markdown("---")
        st.markdown("##### 🖼️ 附属视觉与视频资产 (多模态演示区)")
        st.caption("以下为系统自动调用的图像与视频大模型 API 生成的配套物料（当前为高保真 Mock 数据，二期将接入真实 API）。")
        
        col_img, col_video = st.columns([1, 2])
        
        with col_img:
            st.info("📸 AI 生成的宣发配图")
            img = st.session_state.get("current_real_image")
            # 判断 img 是否为空或是假图链接
            if img and "fake" not in str(img):
                st.image(img, use_container_width=True)
            else:
                st.info("等待生成中...")

        with col_video:
            st.info("🎬 AI 结构化输出的短视频分镜脚本")
            video_df = st.session_state.get("current_video_script")
            if video_df is not None and isinstance(video_df, pd.DataFrame) and len(video_df) > 0:
                st.download_button("⬇️ 导出分镜脚本 (CSV)", data=video_df.to_csv(index=False).encode('utf-8'), file_name="分镜脚本.csv", use_container_width=True)
                st.markdown("---")
                for index, row in video_df.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**⏱ 时间轴**：{row.get('时间轴', '-')}")
                        st.markdown(f"**🎬 画面描述**：{row.get('画面描述', '-')}")
                        st.markdown(f"**🔊 音效/旁白**：{row.get('音效/旁白', '-')}")
                        if st.button(f"🎥 渲染本镜画面 (Shot {index+1})", key=f"render_shot_{index}"):
                            prompt = f"{row.get('画面描述', '')} {row.get('视频生成 Prompt', '')}"
                            if prompt and str(prompt).strip() and str(prompt) != "-":
                                with st.spinner("🎨 正在渲染分镜画面..."):
                                    try:
                                        img_url = generate_real_image(str(prompt))
                                        st.session_state.scene_images[index] = img_url
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"渲染失败：{e}")
                            else:
                                st.warning("⚠️ 该镜头无有效视频生成 Prompt，无法渲染。")
                        if index in st.session_state.scene_images:
                            image_url = st.session_state.scene_images[index]
                            if image_url is not None:
                                st.image(image_url, use_container_width=True)
                            else:
                                st.error("🚨 接口超时或异常，未获取到图片，请重试")
            else:
                st.info("本次未选择生成视频脚本")
# ==================== 页面 3：数据看板 (Dashboard) ====================
elif selected_page == "📊 数据看板":
    st.title("📊 宣发 ROI 与大模型效能分析")
    st.markdown("---")

    # 1. 核心指标区 (Hero Metrics)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("本月 AI 生成物料总数", f"{st.session_state.approved_count:,} 份", "↑ 12%")
    with m2:
        st.metric("节省人工工时", f"{st.session_state.saved_hours} 小时", "↑ 45h")
    with m3:
        st.metric("综合分发采纳率", "89%", "↑ 5%")
    with m4:
        st.metric("预估节省外包成本", "¥ 45,000", "↑ ¥12,000")

    st.markdown("---")

    # 2. 交互图表区
    col_chart1, col_chart2 = st.columns([6, 4])

    with col_chart1:
        st.markdown("### 📈 AI vs 人工：曝光转化率对比")
        np.random.seed(42)
        days = [f"D-{i}" for i in range(6, -1, -1)]
        df_trend = pd.DataFrame({
            "日期": days,
            "AI 宣发物料": np.random.uniform(2.5, 4.5, 7).round(2),
            "传统人工物料": np.random.uniform(1.5, 3.0, 7).round(2),
        })
        st.line_chart(df_trend.set_index("日期"))

    with col_chart2:
        st.markdown("### 🎯 渠道分发效能占比")
        df_channel = pd.DataFrame({
            "渠道": ["微信公众号", "Twitter", "LinkedIn", "小红书"],
            "转化率": [92, 78, 85, 88],
        })
        st.bar_chart(df_channel.set_index("渠道"))

    st.markdown("---")
    st.info("💡 商业化说明：当前展示的为 AI Agent 效能评估模拟数据。商业化二期规划中，我们将直接接入各大社媒平台的开放 API（如微信公众号数据看板 API），实现数据的真实全链路回流。")