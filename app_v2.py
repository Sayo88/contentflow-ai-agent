import streamlit as st
import json
import numpy as np
import requests
import pandas as pd
import io  # <--- 必须补上这个
from streamlit_quill import st_quill
from openai import OpenAI
from streamlit_option_menu import option_menu  # 引入酷炫导航栏
from datetime import datetime  # 新增依赖

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

# ---------------- 全局配置（多供应商架构） ----------------

# 🏢 供应商 A：硅基流动（目前的主力通道）

api_key = st.secrets.get("api_key", "请在系统配置中填入你的API_KEY")

base_url = "https://api.siliconflow.cn/v1"

text_model_name = "Qwen/Qwen2.5-7B-Instruct"      # 硅基文本主力

siliconflow_image_model = "Kwai-Kolors/Kolors"  # 🚀 硅基生图主力 (Kolors 强势回归)



# 🏢 供应商 B：全能中转站（随时待命的备用通道）

proxy_api_key = st.secrets.get("proxy_api_key", "请填入中转站API的KEY")

proxy_base_url = st.secrets.get("proxy_base_url", "https://中转站API的URL/v1")

image_model_name = "qwen-image"                 # 中转站的备用生图模型


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
if "published_history" not in st.session_state:  # 新增历史发布库
    st.session_state.published_history = []
if "draft_save_info" not in st.session_state:  # 用于草稿自动保存记录，每个平台一个
    st.session_state.draft_save_info = {}

# 🚀 新增：项目级草稿箱初始化
if "draft_list" not in st.session_state:
    st.session_state.draft_list = []
if "editing_draft_id" not in st.session_state:
    st.session_state.editing_draft_id = None

def generate_real_text(platforms, project_name, highlights, language, objective, basic_info):
    from openai import OpenAI
    import re

    client = OpenAI(api_key=api_key, base_url=base_url)
    is_english = "English" in language or "英文" in language

    PLATFORM_PERSONA = {
        "微信公众号": {
            "persona": "你是一名顶级微信公众号主编，擅长写能上热门的深度图文推文。",
            "style_guide": """
- 必须写成完整长推文，总字数【不少于500字】
- 结构：开头用一个强烈的钩子段（2-3句话抛出痛点或悬念）→ 正文2-3个段落（每段有小标题）→ 结尾有感情共鸣+行动号召
- 语气：温暖、有深度、像朋友在认真推荐
- 用空行分隔每个自然段，小标题用【】格式标注
- 禁止使用 Emoji，禁止使用 Hashtag""",
        },
        "LinkedIn": {
            "persona": "你是一名顶级B2B品牌营销总监，擅长写能引发行业共鸣的LinkedIn帖子。",
            "style_guide": """
- 总字数【不少于200字】
- 结构：第一行必须是能让人停止滑动的强力钩子句 → 空一行 → 正文3-5个短段落每段1-2句 → 结尾一个思考性问题邀请评论
- 语气：专业、克制、有洞察力，像行业专家在分享思考
- 结尾加3-5个专业Hashtag，如 #Innovation #ProductLaunch
- 禁止使用过度热情的感叹号""",
        },
        "Twitter": {
            "persona": "你是一名病毒式营销专家，专门写能引爆转发的推文。你深知 Twitter/X 有 280 字符的硬性上限，擅长在极小篇幅内制造最大冲击力。",
            "style_guide": """
- 【⚠️ 硬性限制】整条推文（正文 + Hashtag）总字符数绝对不得超过 270 个英文字符！这是生死红线！
- 【正文部分】控制在 200 个英文字符以内（约 3-4 个短句）：
  - 第一句话（15 词以内）必须极其抓人，让人停止滑动
  - 2-3 个短句交代核心卖点，多用数字和对比（如 "3x better than..."）
  - 最后一句号召行动
- 【Hashtag 部分】正文写完后换行，只加 2-3 个精准 Hashtag（控制在 60 字符内）
- 语气：直接、有力、带点挑衅感
- ⚠️ 宁可少写一个卖点，也绝不超过 270 字符！短即是力量！""",
        },
        "Facebook": {
            "persona": "你是一名社群运营专家，擅长写能引发互动讨论的Facebook帖子。",
            "style_guide": """
- 总字数【不少于150字】
- 结构：开头用问句或有趣场景引起共鸣 → 故事化叙述产品价值 → 结尾开放性问题引发评论
- 语气：轻松、亲切，有生活气息
- 适度使用2-4个Emoji点缀
- 结尾加2-3个相关Hashtag""",
        },
        "Instagram": {
            "persona": "你是一名顶级时尚生活方式博主，专门写能配合精美图片的IG文案。",
            "style_guide": """
- 总字数【不少于120字】
- 结构：开头1-2句极具视觉感和情绪感的描述 → 3-4行短句展示产品生活感 → 结尾行动号召
- 语气：有质感、充满情绪，像在晒生活而非卖货
- 每行1-2个精选Emoji
- 结尾单独一行放8-12个精准Hashtag""",
        },
    }

    lang_instruction = "【强制要求：所有输出内容必须100%使用英文，不允许出现任何中文字符】" if is_english else ""
    results = {}

    for plat in platforms:
        config = PLATFORM_PERSONA.get(plat, {
            "persona": "你是一名专业的社交媒体文案专家。",
            "style_guide": "- 总字数不少于150字\n- 语气专业，内容完整"
        })

        user_prompt = f"""【产品名称】{project_name}
【核心卖点】{highlights}
【宣发目标】{objective}
【必须包含的硬性信息】{basic_info}
【输出语言】{language}
{lang_instruction}

请为【{plat}】平台撰写一篇完整的营销文案。

【{plat} 平台专属风格指南】{config['style_guide']}

⚠️ 重要规则：
1. 直接输出文案正文，不要加JSON格式
2. 不要在开头加平台名称或任何前缀标签
3. 不要在文案首尾加方括号或花括号"""

        try:
            system_content = config["persona"]
            if is_english:
                system_content += " You MUST write 100% in English. Any Chinese character in your output is strictly forbidden."

            response = client.chat.completions.create(
                model=text_model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.85,
                max_tokens=1500
            )
            raw = response.choices[0].message.content.strip()

            # 清理残留杂质
            raw = re.sub(r'<!\[CDATA\[|\]\]>', '', raw)
            raw = raw.strip('[]{}"\' ')

            # 转换换行为 <br> 供 Quill 渲染
            raw = raw.replace('\n', '<br>')

            results[plat] = raw

        except Exception as e:
            results[plat] = f"【{plat} 文案生成失败：{str(e)}】"

    # 🚀 Twitter 专属后置校验：超过 280 字符自动压缩
    if "Twitter" in results and "生成失败" not in results["Twitter"]:
        char_count = count_twitter_chars(results["Twitter"])
        if char_count > 280:
            results["Twitter"] = compress_for_twitter(results["Twitter"])

    # 单独生成 image_prompt，与平台文案完全解耦
    try:
        img_response = client.chat.completions.create(
            model=text_model_name,
            messages=[
                {"role": "system", "content": "You are a professional AI image prompt engineer. Output only the image prompt text, nothing else. No explanations, no labels, no JSON."},
                {"role": "user", "content": f"Write a high-quality English image generation prompt for: {project_name}. Key features: {highlights}. Style requirements: commercial photography, cinematic lighting, 8K resolution, ultra detailed. Output the prompt text only."}
            ],
            temperature=0.7,
            max_tokens=120
        )
        results["image_prompt"] = img_response.choices[0].message.content.strip().strip('"\'')
    except:
        results["image_prompt"] = highlights

    return results if results else {"生成失败": "请检查 API 配置"}

def generate_real_image(prompt_text):

    import requests
    import random

    safe_prompt = str(prompt_text)[:150].replace('\n', ' ') if prompt_text else "product"
    wrapped_prompt = f"高质量商业摄影，电影级光影，8k分辨率，超高细节。{safe_prompt}"

    # 🚀 将枪口调回供应商 A（硅基流动）
    api_url = f"{base_url.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 精简 Payload，防止非标准参数导致 API 报 400 错误拦截
    payload = {
        "model": siliconflow_image_model,
        "prompt": wrapped_prompt,
        "image_size": "1024x1024"
    }

    try:
        # 硅基流动偶尔会排队，给足 120 秒等待时间
        resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            # 🚀 核心修复：兼容标准的 'data' 键和 'images' 键
            images = data.get("images", []) or data.get("data", [])
            
            if images and len(images) > 0:
                first = images[0]
                
                # 1. 不管它是字符串还是字典，先把它真实的 URL 抠出来
                img_url = None
                if isinstance(first, str):
                    img_url = first
                elif isinstance(first, dict):
                    img_url = first.get("url") or first.get("image")
                    # 如果本来就是 base64 就直接用
                    if not img_url and first.get("b64_json"):
                        return f"data:image/png;base64,{first.get('b64_json')}"

                # 2. 只要拿到了 URL，就强制在后端下载并转成 Base64！
                if img_url:
                    try:
                        # 伪装成正常浏览器，防止 S3 储存桶拦截 Python 请求
                        fetch_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                        img_resp = requests.get(img_url, headers=fetch_headers, timeout=20)
                        if img_resp.status_code == 200:
                            import base64
                            b64_str = base64.b64encode(img_resp.content).decode("utf-8")
                            return f"data:image/png;base64,{b64_str}"
                        else:
                            print(f"后端下载图片被拒，状态码: {img_resp.status_code}")
                    except Exception as fetch_e:
                        print(f"后端下载图片网络异常: {fetch_e}")
                    
                    # 万一转码失败，再兜底返回原外链
                    return img_url
        else:
            print(f"Kolors API 异常: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"生图网络异常: {e}")

    # 🛡️ 终极兜底：换成国内 100% 能稳定加载的占位图
    return "https://img.alicdn.com/tfs/TB1WEZNkYvpK1RjSZFqXXcXgVXa-1024-1024.png"

def generate_real_video_script(project_name, highlights, language, basic_info):
    # 🚀 检测是否需要生成英文
    is_english = "English" in language or "英文" in language or "英语" in language

    system_prompt = "你是一个爆款短视频编导。请根据产品信息，直接写一段极其抓人的短视频配套文案（Caption）。"
    if is_english:
        system_prompt += "【⚠️ STRICT WARNING: YOU MUST WRITE THE ENTIRE CAPTION IN 100% PURE ENGLISH! DO NOT USE ANY CHINESE CHARACTERS!】"

    user_prompt = f"产品：{project_name}\n卖点：{highlights}\n必须涵盖的信息：{basic_info}\n最终输出语言：{language}\n请包含吸引点击的开头和相关的 Hashtags，并务必带上必须涵盖的信息。"
    
    if is_english:
        user_prompt += "\n🚨🚨🚨 强制警告：请务必将上述所有中文产品信息全部翻译成地道的英文进行输出！绝对不允许出现中英混杂！"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=text_model_name,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.8,
            max_tokens=512
        )
        result = response.choices[0].message.content.strip()
        import re
        result = re.sub(r'<!\[CDATA\[|\]\]>', '', result)
        result = result.strip('[]{}"\' ')
        return result
    except Exception as e:
        import streamlit as st
        st.error(f"视频文案生成异常：{e}")
        return "【好物推荐】这款神仙单品我不允许你还没看过！#爆款 #好物分享"

def revise_real_text(original_content, feedback):
    import re
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        clean_input = original_content.replace('<br>', '\n').replace('<br/>', '\n')
        clean_input = re.sub(r'<[^>]+>', '', clean_input).strip()

        # 自动检测原文语言：中文字符占比低于10%则判定为英文
        chinese_char_count = len(re.findall(r'[\u4e00-\u9fff]', clean_input))
        total_char_count = len(clean_input.replace(' ', ''))
        is_english = (total_char_count > 0 and chinese_char_count / total_char_count < 0.1)

        lang_lock = ""
        system_lang = "你是一个资深营销编辑，直接输出修改后的文案正文，不加任何格式符号。"
        if is_english:
            lang_lock = "\n🚨 语言强制锁定：原稿为英文，重写后必须100%使用纯英文，绝对不允许出现任何中文字符。"
            system_lang = "You are a senior marketing editor. Output ONLY the revised copy in 100% pure English. No Chinese characters allowed under any circumstances."

        prompt = f"""这是原来的文案初稿：

{clean_input}

这是客户提出的修改意见：【{feedback}】

请严格按照修改意见对原稿进行重写优化。
⚠️ 重要规则：
1. 只输出修改后的正文，不要附带任何解释
2. 不要加JSON格式、方括号、花括号
3. 如果原稿是长文（如微信公众号），重写后必须保持同等篇幅和段落结构{lang_lock}"""

        response = client.chat.completions.create(
            model=text_model_name,
            messages=[
                {"role": "system", "content": system_lang},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )
        result = response.choices[0].message.content.strip()
        result = re.sub(r'<!\[CDATA\[|\]\]>', '', result)
        result = result.strip('[]{}"\' ')
        result = result.replace('\n', '<br>')
        return result
    except Exception as e:
        st.error(f"重写异常：{e}")
        return original_content

# ---------------- Twitter 字符控制工具 ----------------
def count_twitter_chars(text):
    """按 Twitter 规则计算字符数：ASCII=1，CJK=2，换行=1"""
    import re
    # 先把 <br> 转为换行符（Twitter 中换行计 1 字符）
    clean = text.replace('<br>', '\n').replace('<br/>', '\n')
    # 段落标签也转为换行
    clean = re.sub(r'</p>\s*<p>', '\n', clean)
    # 去掉所有残余 HTML 标签
    clean = re.sub(r'<[^>]+>', '', clean).strip()
    count = 0
    for ch in clean:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            count += 2  # 中日韩字符算 2
        else:
            count += 1
    return count

def compress_for_twitter(content, max_chars=280, max_retries=2):
    """当推文超过 280 字符时，调用 AI 自动压缩（最多重试 2 次）"""
    import re
    current = content
    for attempt in range(max_retries):
        current_count = count_twitter_chars(current)
        if current_count <= max_chars:
            return current  # 已达标，直接返回

        # 清理 HTML 供 AI 阅读
        clean_input = current.replace('<br>', '\n')
        clean_input = re.sub(r'<[^>]+>', '', clean_input).strip()

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=text_model_name,
                messages=[
                    {"role": "system", "content": (
                        "You are a Twitter copy editor. Your ONLY job is to shorten the given tweet "
                        "to fit within 280 characters. Preserve the core message and keep 2-3 hashtags. "
                        "Output ONLY the shortened tweet text, nothing else. No explanations."
                    )},
                    {"role": "user", "content": (
                        f"This tweet is {current_count} characters, over the 280 limit. "
                        f"Shorten it to UNDER {max_chars} characters. Be ruthless — cut adjectives, "
                        f"merge sentences, but keep the key selling point and call-to-action.\n\n{clean_input}"
                    )}
                ],
                temperature=0.4,
                max_tokens=300
            )
            result = response.choices[0].message.content.strip()
            result = re.sub(r'<!\[CDATA\[|\]\]>', '', result).strip('[]{}"\' ')
            current = result.replace('\n', '<br>')
        except Exception:
            return current  # API 异常则返回当前版本

    return current  # 用尽重试次数，返回最后一版

# ---------------- 左侧绝美导航栏 ----------------
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>✨ ContentFlow AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>一站式多模态营销 Agent V1.0</p>", unsafe_allow_html=True)
    st.markdown("---")

    # === 终极路由接管逻辑 ===
    force_page = None
    if st.session_state.pop("navigate_to_inbox", False):
        force_page = "📥 待办审核"
    # 🚀 必须有这行，告诉系统如何跳去看板
    if st.session_state.pop("navigate_to_dashboard", False):
        force_page = "📊 数据看板"

    if "menu_key" not in st.session_state:
        st.session_state.menu_key = "menu_init"
        st.session_state.default_idx = 0
        
    if force_page == "📥 待办审核":
        st.session_state.default_idx = 1
        st.session_state.menu_key = f"menu_{datetime.now().timestamp()}"
    elif force_page == "📊 数据看板":
        st.session_state.default_idx = 2
        st.session_state.menu_key = f"menu_{datetime.now().timestamp()}"

    selected_page = option_menu(
        menu_title=None,
        options=["✨ 创作中心", "📥 待办审核", "📊 数据看板", "📚 历史发布"],
        icons=["magic", "inbox", "bar-chart", "archive"],
        menu_icon="cast",
        default_index=st.session_state.default_idx,
        key=st.session_state.menu_key
    )

    # 补刀：防止前端组件在换 key 的第一帧装死，Python 后端强行接管页面渲染
    if force_page:
        selected_page = force_page
    elif not selected_page:
        pages = ["✨ 创作中心", "📥 待办审核", "📊 数据看板", "📚 历史发布"]
        selected_page = pages[st.session_state.default_idx]

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
            # 🚀 新增：必须涵盖的基本硬性信息
            basic_info = st.text_area(
                "需涵盖的基本信息", 
                "发售价格：￥3499\n开售时间：9月15日晚8点\n行动号召：点击左下角链接直接购买"
            )
        with col2:
            platforms = st.multiselect(
                "发布平台",
                ["LinkedIn", "Twitter", "Facebook", "Instagram", "微信公众号"],
                default=["LinkedIn", "Twitter", "Facebook", "Instagram", "微信公众号"]
            )

            content_formats = st.multiselect(
                "内容形式",
                ["纯文案", "图文排版", "短视频"],
                default=["图文排版", "短视频"]
            )
            highlights = st.text_area("宣发重点", "1英寸CMOS传感器，4K/120fps超高清画质，三轴云台机械增稳，全像素疾速对焦，智能跟随6.0，原生横竖拍无损切换")

    if st.button("🚀 呼叫 AI 引擎生成", use_container_width=True, type="primary"):
        st.session_state.current_real_image = None

        if not content_formats:
            st.warning("⚠️ 请至少选择一种内容形式。")
        else:
            # 2. 确保这里的判断字符串和上面的选项完全一致
            need_text = "纯文案" in content_formats or "图文排版" in content_formats
            need_video = "短视频" in content_formats

            new_texts = None
            video_cap = None

            # 用来存放提取出来的专属画图 Prompt，兜底用 highlights
            ai_image_prompt = highlights 

            if need_text:
                with st.spinner("🧠 大脑运转中：正在构思全网文案与视觉分镜..."):
                    new_texts = generate_real_text(platforms, project_name, highlights, language, objective, basic_info)
                    
                    if new_texts and "生成失败" not in new_texts:
                        # 🚀 核心接力：把 image_prompt 从大模型的回答中扣出来
                        ai_image_prompt = new_texts.pop("image_prompt", highlights)
                        st.session_state.inbox_tasks = new_texts
                    else:
                        st.session_state.inbox_tasks = {}
            else:
                st.session_state.inbox_tasks = {}

            if "图文排版" in content_formats:
                with st.spinner("🎨 美术发力中：正在根据 AI 提示词绘图..."):
                    if need_text:
                        # 在界面上展示一下生成的提示词，专业感拉满！
                        st.info(f"💡 AI 自动提炼的生图指令：{ai_image_prompt}")
                    # 🚀 把大模型写的高级英文 Prompt 喂给画图 API
                    new_real_image_url = generate_real_image(ai_image_prompt)
                    st.session_state.current_real_image = new_real_image_url

            if need_video:
                with st.spinner("🎬 AI 正在构思视频配套文案..."):
                    # 🚀 传参加入 basic_info
                    video_cap = generate_real_video_script(project_name, highlights, language, basic_info)
                    st.session_state.global_video_caption = video_cap
                    st.session_state.inbox_tasks["短视频"] = "VIDEO_TASK_MARKER"
            else:
                st.session_state.global_video_caption = None

            text_ok = need_text and new_texts and new_texts != {"生成失败": "生成失败，请检查 API 配置"}
            video_ok = need_video and video_cap is not None
            task_success = text_ok or video_ok

            if task_success:
                # 🚀 核心升级：每次生成完毕，打包成一个新项目塞进草稿列表
                import uuid
                new_draft = {
                    "id": str(uuid.uuid4()),  # 唯一项目ID
                    "project_name": project_name,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    # 用 dict() 复制一份全新的数据，防止互相覆盖
                    "inbox_tasks": dict(st.session_state.get("inbox_tasks", {})),
                    "current_real_image": st.session_state.get("current_real_image"),
                    "global_video_caption": st.session_state.get("global_video_caption")
                }
                st.session_state.draft_list.append(new_draft)

                st.session_state.gen_done = True
                st.session_state.show_balloons = True
                # 🚀 核心新增：记住最新生成的这个草稿的专属 ID
                st.session_state.latest_draft_id = new_draft["id"]
            else:
                st.error("❌ 生成失败，请检查 API 配置或重试。")

    # 🚀 核心脱钩：把成功后的界面渲染，拿到大按钮的外面来！（注意这里的缩进）
    if st.session_state.get("gen_done", False):
        st.success("✅ 生成完毕！任务已自动流转至【📥 待办审核】页面，请前往审批。")
        if st.session_state.pop("show_balloons", False):
            st.balloons()
            
        if st.button("👉 立即前往审核中心", use_container_width=True, type="primary"):
            st.session_state.navigate_to_inbox = True
            st.session_state.gen_done = False  # 跳走前销毁状态
            # 🚀 核心新增：把状态切换为“正在编辑最新草稿”，实现穿透跳转！
            if "latest_draft_id" in st.session_state:
                st.session_state.editing_draft_id = st.session_state.latest_draft_id
            st.rerun()

# ==================== 页面 2：待办审核 (Inbox) ====================
elif selected_page == "📥 待办审核":
    st.title("📥 宣发物料审核中心")
    
    # 🚀 新增：手动跳转提示面板 (只有刚发布完才会出现)
    if st.session_state.get("show_jump_panel", False):
        with st.container(border=True):
            st.success("🎉 发布成功！您的物料已进入全网分发队列。")
            col_btn1, col_btn2, _ = st.columns([2, 2, 4])
            with col_btn1:
                if st.button("📊 前往数据看板查看 ROI", type="primary", use_container_width=True):
                    st.session_state.show_jump_panel = False
                    st.session_state.navigate_to_dashboard = True
                    st.rerun()
            with col_btn2:
                if st.button("留在本页继续审核", use_container_width=True):
                    st.session_state.show_jump_panel = False
                    st.rerun()
        st.markdown("---")

    # ======== 🎯 路由 1：展示未发布的草稿项目列表 ========
    if not st.session_state.get("editing_draft_id"):
        st.markdown("##### 🗂️ 未发布项目草稿箱")
        if not st.session_state.draft_list:
            st.info("💡 当前草稿箱为空，请先去【✨ 创作中心】生成项目吧！")
        else:
            # 🚀 核心修复：定义一个强制联动的回调函数
            def toggle_all():
                for d in st.session_state.draft_list:
                    # 把下面所有小框的底层记忆，强制设为和全选框一样
                    st.session_state[f"chk_{d['id']}"] = st.session_state.select_all_drafts

            # 绘制表头
            col_sel, col_name, col_time, col_act, col_del = st.columns([0.5, 3, 2, 1, 1])
            # 把回调函数绑在全选框上 (on_change)
            col_sel.checkbox("全选", key="select_all_drafts", on_change=toggle_all)
            col_name.markdown("**项目名称**")
            col_time.markdown("**上次修改时间**")
            col_act.markdown("**操作**")
            col_del.markdown("")
            st.markdown("---")
            
            # 绘制列表项与批量勾选逻辑
            selected_ids = []
            for idx, draft in enumerate(st.session_state.draft_list):
                c1, c2, c3, c4, c5 = st.columns([0.5, 3, 2, 1, 1])
                
                # 这里的 checkbox 只需要管好自己的 key 就可以了，状态由系统底层统一管理
                if c1.checkbox("", key=f"chk_{draft['id']}"):
                    selected_ids.append(draft["id"])
                
                c2.write(draft["project_name"])
                c3.write(draft["time"])
                
                # 🚀 点击进入具体项目
                if c4.button("✏️ 进入审核", key=f"edit_{draft['id']}"):
                    st.session_state.editing_draft_id = draft["id"]
                    # 将该项目的专属数据调取到全局变量供下方富文本使用
                    st.session_state.inbox_tasks = draft["inbox_tasks"]
                    st.session_state.current_real_image = draft["current_real_image"]
                    st.session_state.global_video_caption = draft.get("global_video_caption")
                    st.rerun()
                    
                # 🗑️ 单点删除
                if c5.button("🗑️ 删除", key=f"del_{draft['id']}"):
                    st.session_state.draft_list.pop(idx)
                    st.rerun()
                    
            st.markdown("---")
            # 🗑️ 批量删除
            if st.button("🗑️ 批量删除选中项目", type="primary"):
                if selected_ids:
                    st.session_state.draft_list = [d for d in st.session_state.draft_list if d["id"] not in selected_ids]
                    st.success("✅ 批量删除成功！")
                    st.rerun()
                else:
                    st.warning("⚠️ 请先在上方勾选要删除的项目。")

    # ======== 🎯 路由 2：进入具体某个项目的排版编辑器 ========
    else:
        # 🚀 自动销毁与拦截逻辑：如果任务全都发完了（空了），直接静默删掉这个草稿并跳回列表！
        if not st.session_state.inbox_tasks:
            st.session_state.draft_list = [d for d in st.session_state.draft_list if d["id"] != st.session_state.editing_draft_id]
            st.session_state.editing_draft_id = None
            # 埋下一个 Toast 提示弹窗，在跳回列表时告诉用户发生什么
            st.toast("🎉 该项目所有渠道已发布完毕，草稿已自动清理归档！", icon="✨")
            st.rerun()

        # 🔙 正常返回按钮（附带自动把内存保存回草稿箱的逻辑）
        if st.button("🔙 返回项目列表 (自动保存)"):
            for d in st.session_state.draft_list:
                if d["id"] == st.session_state.editing_draft_id:
                    d["inbox_tasks"] = st.session_state.inbox_tasks
                    d["current_real_image"] = st.session_state.current_real_image
                    d["global_video_caption"] = st.session_state.get("global_video_caption")
                    d["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    break
            st.session_state.editing_draft_id = None
            st.rerun()
            
        st.markdown("##### 👩‍💻 人工复核与排版排期")
        st.caption("AI 初稿已送达。您可以直接在下方富文本框内进行加粗、标红、插入链接等精细化排版，确认无误后一键分发。")
        
        for plat, content in st.session_state.inbox_tasks.copy().items():
            # 🚀 核心修复：遇到短视频直接跳过，不给它渲染富文本框！
            if plat == "短视频":
                continue
                
            with st.container(border=True):
                st.markdown(f"### 📍 目标渠道：{plat}")
                
                version_key = f"version_{plat}"
                if version_key not in st.session_state:
                    st.session_state[version_key] = 1

# 1. 解决图片重复插入的 Bug：检查 content 是否已经包含了图片标签
                img_url_val = st.session_state.get("current_real_image")
                                
                if img_url_val and str(img_url_val).strip() and "<img" not in content:
                    if "alicdn" in str(img_url_val):  # 👈 把判断暗号改成 alicdn
                        st.warning("⚠️ 未能成功生成主图，当前为占位图。请重试或联系技术支持。")
                    
                    # 🚀 核心修复：不论是真图还是占位图，都执行插入逻辑！
                    real_image_html = f'<br><br><img src="{img_url_val}" width="100%" style="border-radius:10px; margin: 10px 0;"><br><br>'
                    
                    # 🚀 智能定位算法：计算文章长度，寻找最靠近中间位置的换行符
                    mid_idx = len(content) // 2
                    insert_pos = content.find('<br>', mid_idx) # 从中间开始找下一个 <br>
                    
                    if insert_pos == -1: # 如果后半段没有，就从头找第一个 <br>
                        insert_pos = content.find('<br>')
                        
                    if insert_pos != -1:
                        injected_content = content[:insert_pos] + real_image_html + content[insert_pos:]
                    else:
                        injected_content = content + real_image_html
                else:
                    injected_content = content

                dynamic_key = f"quill_{plat}_{st.session_state[version_key]}"
                
                # 🚀 核心改动 1：引入双标签页
                tab_edit, tab_preview = st.tabs(["✏️ 内容编辑与打磨", "👁️ 多端平台沉浸式预览"])
                
                with tab_edit:
                    # 🚀 核心优化：按平台特性动态切换工具栏
                    if plat == "微信公众号":
                        # 微信公众号：保留最完整的默认豪华富文本组件！
                        edited_content = st_quill(
                            value=injected_content, 
                            html=True, 
                            key=dynamic_key
                        )
                    else:
                        # 社交平台（LinkedIn/Twitter/FB/IG）：精简排版，但【必须】保留配图功能！
                        custom_toolbar = [
                            ['bold', 'italic'],          # 保留最基础的加粗斜体（部分海外平台支持）
                            ['link', 'image', 'video'],  # 🚀 核心：保留加链接、发图、发视频的灵魂功能！
                            ['clean']                    # 一键清除格式（防乱码神器）
                        ]
                        # 给用户一个充满专业感的提示
                        st.info(f"💡 **智能模式已开启**：检测到目标渠道为 **{plat}**。已自动精简不兼容的排版工具，但保留了**插入配图/视频**功能，请放心创作。")
                        
                        edited_content = st_quill(
                            value=injected_content, 
                            html=True, 
                            toolbar=custom_toolbar, 
                            key=dynamic_key
                        )

                    # ----------- 极简自动草稿箱逻辑 start -----------
                    baseline_key = f"baseline_{dynamic_key}"
                    save_time_key = f"save_time_{dynamic_key}"

                    if edited_content is None:
                        if save_time_key in st.session_state:
                            st.caption(f"✅ **已保存草稿** ({st.session_state[save_time_key]})")
                        else:
                            st.caption("⚡️ 编辑区：已开启自动保存...")
                    else:
                        if baseline_key not in st.session_state:
                            st.session_state[baseline_key] = edited_content
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            st.session_state[save_time_key] = now_str
                            st.caption(f"✅ **AI 初稿已自动保存** ({now_str})")
                        else:
                            if edited_content != st.session_state[baseline_key]:
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                st.session_state.inbox_tasks[plat] = edited_content
                                st.session_state[baseline_key] = edited_content
                                st.session_state[save_time_key] = now_str
                                st.caption(f"✅ **已保存最新修改** ({now_str})")
                            else:
                                if save_time_key in st.session_state:
                                    st.caption(f"✅ **已保存草稿** ({st.session_state[save_time_key]})")
                                else:
                                    st.caption("⚡️ 编辑区：已开启自动保存...")
                    # ----------- 极简自动草稿箱逻辑 end -----------                

                    # ----------- Twitter 实时字符计数器 start -----------
                    if plat == "Twitter":
                        import re as _re
                        counter_source = edited_content if edited_content is not None else injected_content
                        # 去掉图片标签（Twitter 图片附件不计入字符数）
                        counter_clean = _re.sub(r'<img[^>]+>', '', counter_source)
                        char_count = count_twitter_chars(counter_clean)
                        remaining = 280 - char_count

                        col_counter1, col_counter2 = st.columns([4, 1])
                        with col_counter1:
                            if char_count > 280:
                                st.error(f"🚫 超出 Twitter 限制！当前 **{char_count}/280** 字符，需删减 **{-remaining}** 个字符")
                            elif char_count > 250:
                                st.warning(f"⚡ 接近上限：**{char_count}/280** 字符（剩余 {remaining}）")
                            else:
                                st.success(f"✅ **{char_count}/280** 字符（剩余 {remaining}）")
                        with col_counter2:
                            st.progress(min(char_count / 280, 1.0))
                    # ----------- Twitter 实时字符计数器 end -----------

                    st.markdown("##### 💬 AI 协同打磨")
                    PLATFORM_FEEDBACK_PLACEHOLDER = {
                        "微信公众号": "例如：在第二段插入一个旅行博主用 Pocket 3 记录日落的真实故事，结尾补充'9月15日晚8点开抢，前500名享3299元早鸟价'的价格锚点",
                        "LinkedIn": "例如：把画质描述改为'1英寸CMOS较上一代进光量提升300%'的量化数据，结尾改为邀请专业影像创作者参与DJI共创计划的合作号召",
                        "Twitter": "例如：第一句改成'3499元能拍出院线级画面？'的设问句，中间加一句Pocket 3与iPhone 15 Pro Max同场景4K画质对比的尖锐数据",
                        "Facebook": "例如：加入一个用户带着Pocket 3去云南拍泸沽湖日出的场景故事，结尾互动引导改为'评论区晒出你今年最满意的一条Vlog，抽3人送周边大礼包'",
                        "Instagram": "例如：开头改为黄金时段在街头抬手就拍的情绪感短句，结尾hashtag替换为 #DJIPocket3 #Vlog #旅拍必备 #创作者 #口袋里的电影机",
                    }
                    feedback = st.text_input(
                        f"对 {plat} 内容不满意？输入指令让 AI 重新打磨：", 
                        value=PLATFORM_FEEDBACK_PLACEHOLDER.get(plat, "例如：补充产品核心数据、调整行动号召、修改目标受众定位..."), 
                        key=f"fb_{plat}"
                    )
                    
                    col_action1, col_action2, col_action3 = st.columns(3)
                    with col_action1:
                        if st.button("🔄 根据意见重写", key=f"rewrite_{plat}", use_container_width=True):
                            if feedback:
                                with st.spinner("🧠 AI 正在疯狂理解你的意图并重写中..."):
                                    new_content = revise_real_text(content, feedback)
                                    # 🚀 Twitter 重写后自动压缩校验
                                    if plat == "Twitter":
                                        rewrite_count = count_twitter_chars(new_content)
                                        if rewrite_count > 280:
                                            new_content = compress_for_twitter(new_content)
                                    st.session_state.inbox_tasks[plat] = new_content
                                    st.session_state[version_key] += 1
                                    if plat not in st.session_state.draft_save_info:
                                        st.session_state.draft_save_info[plat] = {}
                                    st.session_state.draft_save_info[plat]["old_val"] = new_content
                                    st.session_state.draft_save_info[plat]["save_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    st.rerun()
                            else:
                                st.warning("⚠️ 请先在上方输入框写下你的修改意见喔！")

                    with col_action2:
                        if st.button(f"✅ 审核通过，一键推送至 {plat}", key=f"pub_{plat}", type="primary", use_container_width=True):
                            # 🚀 Twitter 发布前终极拦截
                            if plat == "Twitter":
                                import re as _re2
                                pub_source = edited_content if edited_content is not None else injected_content
                                pub_clean = _re2.sub(r'<img[^>]+>', '', pub_source)
                                pub_count = count_twitter_chars(pub_clean)
                                if pub_count > 280:
                                    st.error(f"🚫 发布被拦截！当前推文 {pub_count} 字符，超出 Twitter 280 字符上限。请先在上方编辑区精简内容，或点击「根据意见重写」让 AI 自动压缩。")
                                    st.stop()

                            with st.spinner(f"🚀 正在通过 API 真实推送至 {plat}..."):
                                
                                # 1. 组装要发送的真实数据包 (Payload) 前先处理 clean_content
                                import re
                                if plat == "微信公众号":
                                    clean_content = edited_content
                                else:
                                    # 移除base64图片标签
                                    tmp_content = re.sub(r'<img[^>]*src="data:image/[^"]*"[^>]*>', '', edited_content)
                                    # 移除所有HTML标签
                                    clean_content = re.sub(r'<[^>]+>', '', tmp_content).strip()
                                # 处理 image_url: 如果是 base64 字符串，只取逗号后的部分
                                image_url_raw = st.session_state.get("current_real_image", "")
                                if image_url_raw.startswith("data:image"):
                                    # 提取 base64 部分
                                    comma_index = image_url_raw.find(',')
                                    image_url = image_url_raw[comma_index+1:] if comma_index != -1 else ""
                                else:
                                    image_url = image_url_raw
                                payload = {
                                    "project": st.session_state.get("project_name", "未命名项目"),
                                    "platform": plat,
                                    "content": clean_content, # 你最终修改好的文案 (根据平台处理)
                                    "image_url": image_url # 若为base64只发base64，否则直接发URL
                                }
                                
                                # 2. 向你的 Webhook 中枢发送真实的 POST 请求
                                webhook_url = st.secrets.get("MAKE_WEBHOOK_URL") # 替换成你申请的真实 URL
                                
                                try:
                                    # 🚀 真枪实弹：向你的 Webhook 发送真实的 POST 请求！
                                    response = requests.post(webhook_url, json=payload, timeout=10)
                                    
                                    if response.status_code == 200:
                                        st.success(f"🎉 成功！您修改后的图文排版已通过 API 真实发送至 {plat}！")
                                        st.balloons()
                                        
                                        # 记录成功历史
                                        st.session_state.approved_count += 1
                                        st.session_state.saved_hours += 2.5
                                        history_record = {
                                            "项目": payload["project"],
                                            "平台": plat,
                                            "内容": edited_content,
                                            "时间": datetime.now().strftime("%Y-%m-%d %H:%M")
                                        }
                                        st.session_state.published_history.append(history_record)
                                        
                                        # 清理任务流
                                        st.session_state.inbox_tasks.pop(plat, None)
                                        if plat in st.session_state.draft_save_info:
                                            st.session_state.draft_save_info.pop(plat, None)
                                            
                                        st.session_state.show_jump_panel = True
                                        st.rerun()
                                    else:
                                        st.error(f"❌ API 推送失败，错误代码：{response.status_code}")
                                except Exception as e:
                                    st.error(f"❌ 网络请求异常：{e}")

                    with col_action3:
                        export_format = st.selectbox("", options=["Word文档 (.doc)", "网页源码 (.html)", "Markdown (.md)"], key=f"fmt_{plat}", label_visibility="collapsed")
                        data = f"<html><meta charset='utf-8'><body>{edited_content}</body></html>".encode('utf-8') if "doc" in export_format or "html" in export_format else edited_content.encode('utf-8')
                        mime = "application/msword" if "doc" in export_format else "text/html" if "html" in export_format else "text/markdown"
                        file_ext = ".doc" if "doc" in export_format else ".html" if "html" in export_format else ".md"
                        
                        st.download_button(f"⬇️ 导出 {export_format.split(' ')[0]}", data=data, file_name=f"ContentFlow_{plat}{file_ext}", mime=mime, use_container_width=True)

                # 🚀 绝美的双端真机预览 UI (支持创作中心的 5 大原生平台)
                with tab_preview:
                    # 终端切换开关
                    preview_mode = st.radio(
                        "🔍 选择预览设备", 
                        ["📱 移动端沉浸体验", "💻 桌面端大屏体验"], 
                        horizontal=True, 
                        key=f"preview_mode_{plat}",
                        label_visibility="collapsed"
                    )
                    
                    preview_html = edited_content if edited_content is not None else injected_content
                    
                    # 🚀 核心优化：图文分离解析，实现原生社交平台的瀑布流排版
                    import re
                    # 提取所有 img 标签
                    img_tags = re.findall(r'<img[^>]+>', preview_html)
                    # 剔除 img 标签，保留纯文字
                    text_html = re.sub(r'<img[^>]+>', '', preview_html)
                    
                    # 预设通用大图样式（针对 Twitter 等支持圆角的平台）
                    media_html = ""
                    if img_tags:
                        styled_imgs = [img.replace('<img ', '<img style="width: 100%; height: auto; display: block; margin-top: 12px; border-radius: 16px; border: 1px solid #eff3f4;" ') for img in img_tags]
                        media_html = "".join(styled_imgs)

                    # IG / FB 专属的无缝全宽大图样式
                    edge_media_html = ""
                    if img_tags:
                        edge_styled_imgs = [img.replace('<img ', '<img style="width: 100%; height: auto; display: block; border: none; margin: 0; border-radius: 0;" ') for img in img_tags]
                        edge_media_html = "".join(edge_styled_imgs)

                    # ======= 🎨 构造 5 大平台专属的内部原生 UI =======
                    # (注意：这里的 HTML 必须全部顶格写，防止被 Streamlit 误判为 Markdown 代码块)
                    platform_ui = ""
                    
                    if plat == "Twitter" or plat == "X":
                        platform_ui = f"""<div style="padding: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: left; background: white;">
<div style="display: flex; align-items: center; margin-bottom: 12px;">
<div style="width: 48px; height: 48px; border-radius: 50%; background-color: #000000; color: white; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 24px; margin-right: 12px;">𝕏</div>
<div>
<div style="font-weight: bold; color: #0f1419; font-size: 15px;">品牌官方账号 <span style="color: #1DA1F2;">☑️</span></div>
<div style="color: #536471; font-size: 15px;">@OfficialBrand</div>
</div>
</div>
<div style="color: #0f1419; font-size: 15px; line-height: 1.5;">{text_html}</div>
{media_html}
<div style="color: #536471; font-size: 14px; margin-top: 12px; margin-bottom: 16px;">下午 8:00 · 刚刚发布</div>
<div style="border-top: 1px solid #eff3f4; border-bottom: 1px solid #eff3f4; padding: 12px 0; display: flex; justify-content: space-between; color: #536471; padding: 12px 10%;">
<span>💬 128</span> <span>🔄 56</span> <span>❤️ 4.2K</span> <span>📊 12万</span>
</div>
</div>"""
                        
                    elif plat == "LinkedIn":
                        platform_ui = f"""<div style="padding: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: left; background: white; border-radius: 8px;">
<div style="display: flex; align-items: center; margin-bottom: 12px;">
<div style="width: 48px; height: 48px; border-radius: 4px; background-color: #0a66c2; color: white; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 20px; margin-right: 12px;">in</div>
<div>
<div style="font-weight: 600; color: rgba(0,0,0,0.9); font-size: 14px;">品牌官方账号</div>
<div style="color: rgba(0,0,0,0.6); font-size: 12px;">专注提供优质的行业解决方案</div>
<div style="color: rgba(0,0,0,0.6); font-size: 12px;">刚刚 • 🌐</div>
</div>
</div>
<div style="color: rgba(0,0,0,0.9); font-size: 14px; line-height: 1.6;">{text_html}</div>
{edge_media_html}
<div style="border-top: 1px solid #e0dfdc; padding-top: 12px; margin-top: 12px; display: flex; justify-content: space-around; color: rgba(0,0,0,0.6); font-weight: 600; font-size: 13px;">
<span>👍 赞</span> <span>💬 评论</span> <span>🔄 转发</span> <span>✈️ 发送</span>
</div>
</div>"""
                        
                    elif plat == "Facebook" or plat == "Facebook":
                        platform_ui = f"""<div style="padding: 16px; font-family: system-ui, -apple-system, sans-serif; text-align: left; background: white;">
<div style="display: flex; align-items: center; margin-bottom: 12px;">
<div style="width: 40px; height: 40px; border-radius: 50%; background-color: #0866FF; color: white; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 24px; margin-right: 12px;">f</div>
<div>
<div style="font-weight: 600; color: #050505; font-size: 15px;">官方品牌主页</div>
<div style="color: #65676B; font-size: 13px;">刚刚 · 🌎</div>
</div>
</div>
<div style="color: #050505; font-size: 15px; line-height: 1.5;">{text_html}</div>
{edge_media_html}
<div style="border-top: 1px solid #CED0D4; border-bottom: 1px solid #CED0D4; padding: 4px 0; display: flex; justify-content: space-around; color: #65676B; font-weight: 600; font-size: 15px; margin-top: 12px;">
<span style="padding: 6px 0;">👍 赞</span> <span style="padding: 6px 0;">💬 评论</span> <span style="padding: 6px 0;">🔗 分享</span>
</div>
</div>"""
                        
                    elif plat == "Instagram":
                        platform_ui = f"""<div style="padding: 16px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; text-align: left; background: white;">
<div style="display: flex; align-items: center; padding: 0 16px; margin-bottom: 12px;">
<div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); display: flex; justify-content: center; align-items: center; margin-right: 10px;">
<div style="width: 32px; height: 32px; border-radius: 50%; background-color: white; border: 2px solid white;"></div>
</div>
<div style="font-weight: 600; color: #262626; font-size: 14px;">official_brand</div>
<div style="margin-left: auto; font-weight: bold; color: #262626;">⋯</div>
</div>
{edge_media_html}
<div style="padding: 0 16px; margin-top: 12px; margin-bottom: 12px; display: flex; align-items: center;">
<svg style="margin-right: 16px;" aria-label="赞" color="#262626" fill="#262626" height="24" role="img" viewBox="0 0 24 24" width="24"><path d="M16.792 3.904A4.989 4.989 0 0121.5 9.122c0 3.072-2.652 4.959-5.197 7.222-2.512 2.243-3.865 3.469-4.303 3.752-.477-.309-2.143-1.823-4.303-3.752C5.141 14.072 2.5 12.167 2.5 9.122a4.989 4.989 0 014.708-5.218 4.21 4.21 0 013.675 1.941c.84 1.174.98 1.514 1.117 1.514s.277-.34 1.117-1.514a4.21 4.21 0 013.675-1.941z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
<svg style="margin-right: 16px;" aria-label="评论" color="#262626" fill="#262626" height="24" role="img" viewBox="0 0 24 24" width="24"><path d="M20.656 17.008a9.993 9.993 0 10-3.59 3.615L22 22z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="2"></path></svg>
<svg aria-label="分享" color="#262626" fill="#262626" height="24" role="img" viewBox="0 0 24 24" width="24"><line fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="2" x1="22" x2="9.218" y1="3" y2="10.083"></line><polygon fill="none" points="11.698 20.334 22 3.001 2 3.001 9.218 10.084 11.698 20.334" stroke="currentColor" stroke-linejoin="round" stroke-width="2"></polygon></svg>
<svg style="margin-left: auto;" aria-label="收藏" color="#262626" fill="#262626" height="24" role="img" viewBox="0 0 24 24" width="24"><polygon fill="none" points="20 21 12 13.44 4 21 4 3 20 3 20 21" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></polygon></svg>
</div>
<div style="padding: 0 16px; font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #262626;">12,345 次赞</div>
<div style="padding: 0 16px; font-size: 14px; line-height: 1.5; color: #262626;">
<span style="font-weight: 600; margin-right: 6px;">official_brand</span>{text_html}
</div>
</div>"""
                        
                    elif plat == "微信公众号":
                        # 微信公众号是富文本平台，图文不分离，直接渲染原始 preview_html
                        fake_title = st.session_state.get("project_name", "最新产品发布")
                        platform_ui = f"""<div style="padding: 20px 16px; font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'PingFang SC', sans-serif; text-align: left; background: white;">
<h2 style="font-size: 22px; font-weight: 400; line-height: 1.4; margin-bottom: 14px; color: #333;">{fake_title}：突破想象的全新体验</h2>
<div style="margin-bottom: 22px; font-size: 15px; color: #576b95;">
<span style="color: rgba(0,0,0,0.3); margin-right: 8px;">原创</span> 官方服务号
</div>
<div style="font-size: 17px; color: #333; line-height: 1.6; letter-spacing: 0.034em;">{preview_html}</div>
<div style="margin-top: 30px; display: flex; justify-content: space-between; color: rgba(0,0,0,0.3); font-size: 15px;">
<span>阅读 10万+</span>
<div><span style="margin-right: 15px;">分享</span><span>👍 赞</span><span> ✨ 在看</span></div>
</div>
</div>"""
                    else:
                        platform_ui = f"<div style='padding:16px;'>{preview_html}</div>"

                    # ======= 📱 包装到手机或电脑外壳中 =======
                    if "移动端" in preview_mode:
                        bg_color = '#f3f2ef' if plat == 'LinkedIn' else '#ffffff'
                        mockup_css = f"""<div style="display: flex; justify-content: center; padding: 20px 0;">
<div style="width: 375px; height: 667px; background-color: {bg_color}; border: 12px solid #1a1a1a; border-radius: 40px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.15); position: relative;">
<div style="position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 130px; height: 25px; background-color: #1a1a1a; border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; z-index: 10;"></div>
<div style="height: 44px; background-color: #f7f7f7; display: flex; align-items: flex-end; justify-content: center; padding-bottom: 8px; font-family: -apple-system, sans-serif; font-size: 15px; font-weight: 600; color: #111;">
{plat}
</div>
<div style="height: calc(100% - 44px); overflow-y: auto;">
<div style="margin-top: {'8px' if plat == 'LinkedIn' else '0'};">
{platform_ui}
</div>
</div>
</div>
</div>"""
                    else:
                        bg_color = '#f3f2ef' if plat == 'LinkedIn' else '#eff3f4' if plat in ['Twitter', 'X'] else '#f0f2f5' if 'Facebook' in plat else '#fafafa' if plat == 'Instagram' else '#f2f2f2'
                        mockup_css = f"""<div style="display: flex; justify-content: center; padding: 20px 0;">
<div style="width: 100%; max-width: 800px; height: 600px; background-color: {bg_color}; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.1); display: flex; flex-direction: column;">
<div style="height: 40px; background-color: #ffffff; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; padding: 0 16px; flex-shrink: 0;">
<div style="width: 12px; height: 12px; border-radius: 50%; background-color: #ff5f56; margin-right: 8px;"></div>
<div style="width: 12px; height: 12px; border-radius: 50%; background-color: #ffbd2e; margin-right: 8px;"></div>
<div style="width: 12px; height: 12px; border-radius: 50%; background-color: #27c93f;"></div>
<div style="flex-grow: 1; text-align: center; font-family: -apple-system, sans-serif; font-size: 14px; font-weight: 500; color: #666;">
{plat} - 网页端浏览
</div>
<div style="width: 50px;"></div>
</div>
<div style="flex-grow: 1; overflow-y: auto; display: flex; justify-content: center; padding: 20px;">
<div style="width: 100%; max-width: 600px; border-radius: {'8px' if plat not in ['微信公众号', 'Instagram'] else '0'}; box-shadow: {'0 1px 3px rgba(0,0,0,0.1)' if plat in ['LinkedIn', 'Facebook', 'Facebook', 'Instagram'] else 'none'}; height: fit-content; border: {'1px solid #e0dfdc' if plat == 'LinkedIn' else '1px solid #dbdbdb' if plat == 'Instagram' else 'none'};">
{platform_ui}
</div>
</div>
</div>
</div>"""
                    
                    st.markdown(mockup_css, unsafe_allow_html=True)
        # ================= 🎬 视频资产与分发工作台 =================

        st.markdown("---")

        st.markdown("##### 🎬 短视频与 Caption 分发工作台")

        st.caption("视频资产具有极强的跨平台通用性。您可以在此统一审阅视频与文案，并一键分发至各大短视频平台。")

        # 1. 修正暗号匹配，仅寻找“短视频”
        video_task_marker = st.session_state.inbox_tasks.get("短视频")

        if video_task_marker:

            # 使用一个美观的容器包裹整个工作台
            with st.container(border=True):

                col_vid_player, col_caption = st.columns([1, 1.2])

                with col_vid_player:

                    st.info("📺 AI 生成的成片预览")
                    st.video("https://www.w3schools.com/html/mov_bbb.mp4")

                    st.markdown("###### 🎥 画面调优指令")
                    vid_feedback = st.text_input(
                        "视频修改意见",
                        value="例如：开头从产品开箱改为博主单手持机在人流中穿梭的街拍实拍，中间插入云台防抖与手机拍摄的分屏对比镜头，结尾用慢动作定格日落剪影，背景音乐换成有旅行感的轻吉他",
                        key="vid_fb_global",
                        label_visibility="collapsed"
                    )

                    if st.button("🔄 提交视频重绘请求", key="btn_vid_global", use_container_width=True):
                        if vid_feedback:
                            st.toast(f"收到视频调优指令：'{vid_feedback}'。二期将接入视频大模型重新渲染！", icon="⏳")
                        else:
                            st.warning("请先输入视频修改意见")

                with col_caption:

                    st.info("📝 通用配套文案 (Caption)")

                    # 🚀 核心修复：将草稿 ID 绑定进 Key 中，强制每个项目读取自己的专属文案缓存
                    current_draft_id = st.session_state.get("editing_draft_id", "default_id")
                    cap_key = f"global_video_caption_edit_{current_draft_id}"
                    cap_version_key = f"cap_version_{current_draft_id}"

                    if cap_key not in st.session_state:
                        generated_cap = st.session_state.get("global_video_caption", "暂无文案生成")
                        st.session_state[cap_key] = generated_cap
                    if cap_version_key not in st.session_state:
                        st.session_state[cap_version_key] = 1

                    cap_widget_key = f"widget_cap_{current_draft_id}_{st.session_state[cap_version_key]}"

                    edited_caption = st.text_area(
                        "直接在此修改各平台通用的 Caption",
                        value=st.session_state[cap_key],
                        height=180,
                        key=cap_widget_key
                    )

                    if edited_caption != st.session_state[cap_key]:
                        st.session_state[cap_key] = edited_caption
                        st.caption(f"✅ **已自动保存最新文案** ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

                    st.markdown("###### 💬 文案风格调优")
                    txt_feedback = st.text_input(
                        "文案修改意见",
                        value="例如：开头加一句'带它出门3天，删掉了手机里所有的视频'的反差钩子，结尾加'限时优惠至9月20日，点击主页链接直接下单'的紧迫感，hashtag补充 #DJI #口袋相机 #Vlog神器 #创作者必备 #国庆出行装备",
                        key="txt_fb_global",
                        label_visibility="collapsed"
                    )

                    if st.button("✨ 优化 Caption", key="btn_txt_global", use_container_width=True):
                        if txt_feedback:
                            with st.spinner("🧠 AI 正在根据意见重写 Caption..."):
                                # 直接在按钮处调用 API，不走 revise_real_text，错误完全可见
                                try:
                                    import re
                                    source = st.session_state[cap_key] if st.session_state[cap_key] else edited_caption
                                    clean_input = source.replace('<br>', '\n')
                                    clean_input = re.sub(r'<[^>]+>', '', clean_input).strip()

                                    chinese_count = len(re.findall(r'[\u4e00-\u9fff]', clean_input))
                                    total_count = len(clean_input.replace(' ', ''))
                                    is_eng = total_count > 0 and chinese_count / total_count < 0.1
                                    system_msg = "You are a senior marketing editor. Output ONLY the revised copy in 100% pure English. No Chinese." if is_eng else "你是资深营销编辑，直接输出修改后的正文，不加任何解释和格式符号。"

                                    cap_client = OpenAI(api_key=api_key, base_url=base_url)
                                    cap_resp = cap_client.chat.completions.create(
                                        model=text_model_name,
                                        messages=[
                                            {"role": "system", "content": system_msg},
                                            {"role": "user", "content": f"原文：\n{clean_input}\n\n修改意见：【{txt_feedback}】\n\n请重写，只输出正文。"}
                                        ],
                                        temperature=0.8,
                                        max_tokens=1500
                                    )
                                    new_cap = cap_resp.choices[0].message.content.strip()
                                    new_cap = re.sub(r'<!\[CDATA\[|\]\]>', '', new_cap).strip('[]{}"\' ')
                                    st.session_state[cap_key] = new_cap
                                    st.session_state[cap_version_key] += 1
                                    st.rerun()
                                except Exception as cap_err:
                                    st.error(f"❌ Caption 重写失败，错误详情：{cap_err}")
                        else:
                            st.warning("请先输入文案修改意见")

                st.divider()
                col_ch, col_exp, col_pub = st.columns([2, 1, 1])

                with col_ch:
                    # 1. 改为多选框，并同步创作中心的平台列表
                    publish_channels = st.multiselect(
                        "🎯 选择短视频分发渠道（可多选）",
                        ["LinkedIn", "Twitter", "Facebook", "Instagram", "微信公众号"],
                        default=["LinkedIn", "Twitter"], # 默认选中两个展示效果
                        key="sel_global_vid"
                    )
                with col_exp:
                    # 2. 导出文件名改为通用名称，因为现在是多个渠道了
                    st.download_button(
                        "⬇️ 导出视频配套物料",
                        data=edited_caption.encode('utf-8'),
                        file_name="短视频_caption.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                with col_pub:
                    if st.button("🚀 一键多平台发布", type="primary", key="pub_global_vid", use_container_width=True):
                        if not publish_channels:
                            st.warning("⚠️ 请至少选择一个发布渠道！")
                        else:
                            with st.spinner("🚀 正在通过 Webhook 批量分发视频资产..."):
                                _project_name = st.session_state.get("project_name", "未命名项目")
                                webhook_url = st.secrets.get("MAKE_WEBHOOK_URL")
                                import requests
                                
                                success_count = 0
                                for ch in publish_channels:
                                    payload = {
                                        "action": "publish_video",
                                        "project_name": _project_name,
                                        "platform": ch,
                                        "caption": edited_caption,
                                        "video_url": "https://www.w3schools.com/html/mov_bbb.mp4", # 这里替换为真实的视频资产 URL
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    }
                                    
                                    try:
                                        # 🚀 真枪实弹：真实向 Webhook 批量派发视频物料！
                                        resp = requests.post(webhook_url, json=payload, timeout=10)
                                        if resp.status_code == 200:
                                            success_count += 1
                                            
                                            history_record = {
                                                "项目": _project_name,
                                                "平台": ch,
                                                "内容": f"[视频物料] + {edited_caption[:50]}...",
                                                "时间": payload["timestamp"]
                                            }
                                            st.session_state.published_history.append(history_record)
                                    except Exception as e:
                                        st.error(f"向 {ch} 推送异常: {e}")
                                
                                if success_count > 0:
                                    channels_str = "、".join(publish_channels)
                                    st.success(f"🎉 真实推送成功！视频资产与配套文案已发往中转站，目标：【{channels_str}】！")
                                    st.balloons()
                                    st.session_state.inbox_tasks.pop("短视频", None)
                                    st.session_state.show_jump_panel = True
                                    st.rerun()

        else:
            st.info("💡 本次宣发任务未包含短视频物料。")

# ==================== 页面 3：数据看板 (Dashboard) ====================
elif selected_page == "📊 数据看板":
    st.title("📊 宣发 ROI 与大模型效能分析")
    st.markdown("---")

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

# ==================== 页面 4：历史发布 ====================
elif selected_page == "📚 历史发布":
    st.title("📚 历史发布库")
    published_history = st.session_state.published_history

    if published_history:
        # 动态收集所有平台选项去重
        platforms_all = list({item["平台"] for item in published_history if "平台" in item})
        platforms_all.sort()
        selected_platforms = st.multiselect("筛选发布平台", options=platforms_all, default=platforms_all)

        # 筛选历史记录
        filtered_history = [
            h for h in published_history if h.get("平台", "") in selected_platforms
        ] if selected_platforms else published_history

        if filtered_history:
            # 按时间逆序展示(让最新在前)
            filtered_history_sorted = sorted(filtered_history, key=lambda x: x.get("时间", ""), reverse=True)
            for idx, item in enumerate(filtered_history_sorted):
                title = f"[{item.get('平台', '-')}] 发布于 {item.get('时间', '-')}"
                with st.expander(title, expanded=False):
                    # 项目名展示(可选)
                    proj_name = item.get('项目', '')
                    if proj_name:
                        st.caption(f"项目：{proj_name}")
                    st.markdown(item.get("内容", "-"), unsafe_allow_html=True)
        else:
            st.info("💡 当前无匹配筛选的发布记录，请更改筛选条件。")
    else:
        st.info("💡 当前暂无发布记录，快去创作中心生成吧！")