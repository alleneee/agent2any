from dataclasses import dataclass


@dataclass
class StyleConfig:
    default_style: str = "现代日系动漫风格"
    default_image_ratio: str = "16:9"
    default_video_ratio: str = "16:9"
    default_scene_style: str = "现代日系动漫风格"
    default_prop_style: str = "精致道具特写"
    language: str = "zh"


class PromptTemplates:
    def __init__(self, style: StyleConfig | None = None):
        self.style = style or StyleConfig()

    @property
    def is_english(self) -> bool:
        return self.style.language == "en"

    def get_outline_prompt(self) -> str:
        if self.is_english:
            return """You are a professional short drama screenwriter. Based on the theme and number of episodes, create a complete short drama outline.

Requirements:
1. Compact plot with strong conflicts and fast pace
2. Each episode should have independent conflicts while connecting the main storyline
3. Clear character arcs and growth
4. Cliffhanger endings to hook viewers
5. Clear theme and emotional core

Output Format:
Return a JSON object containing:
- title: Drama title (creative and attractive)
- episodes: Episode list, each containing:
  - episode_number: Episode number
  - title: Episode title
  - summary: Episode content summary (50-100 words)
  - conflict: Main conflict point
  - cliffhanger: Cliffhanger ending (if any)

**CRITICAL: Return ONLY valid JSON. No markdown, no explanations.**"""

        return """你是专业短剧编剧。根据主题和剧集数量，创作完整的短剧大纲，规划好每一集的剧情走向。

要求：
1. 剧情紧凑，矛盾冲突强烈，节奏快
2. 每集都有独立的矛盾冲突，同时推进主线
3. 角色弧光清晰，成长变化明显
4. 悬念设置合理，吸引观众继续观看
5. 主题明确，情感内核清晰

输出格式：
返回一个JSON对象，包含：
- title: 剧名（富有创意和吸引力）
- episodes: 分集列表，每集包含：
  - episode_number: 集数
  - title: 本集标题
  - summary: 本集内容概要（50-100字）
  - conflict: 主要矛盾点
  - cliffhanger: 悬念结尾（如有）

**重要：必须只返回纯JSON，不要包含markdown代码块或说明文字。**"""

    def get_episode_script_prompt(self) -> str:
        if self.is_english:
            return """You are a professional short drama screenwriter. Expand the outline into detailed scripts.

Requirements:
1. Expand outline summary into detailed plot development
2. Write character dialogue and actions, not just description
3. Highlight conflict progression and emotional changes
4. Add scene transitions and atmosphere descriptions
5. Control rhythm, climax at 2/3 point
6. Each episode 800-1200 words, dialogue-rich
7. Keep consistent with character settings

Output Format:
Return JSON object with:
- episodes: Episode list, each containing:
  - episode_number: Episode number
  - title: Episode title
  - script_content: Detailed script content (800-1200 words)

**CRITICAL: Return ONLY valid JSON.**"""

        return """你是专业短剧编剧。将大纲扩展为详细剧本。

要求：
1. 将大纲概要扩展为具体的剧情发展
2. 写出角色的对话和动作，不是简单描述
3. 突出冲突的递进和情感的变化
4. 增加场景转换和氛围描写
5. 控制节奏，高潮在2/3处，结尾有收束
6. 每集800-1200字，对话丰富
7. 与角色设定保持一致

输出格式：
返回JSON对象：
- episodes: 分集列表，每集包含：
  - episode_number: 集数
  - title: 本集标题
  - script_content: 详细剧本内容（800-1200字）

**重要：必须只返回纯JSON。**"""

    def get_character_extraction_prompt(self) -> str:
        style = self.style.default_style
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""You are a professional character analyst.

Task: Extract and organize detailed character profiles from the script.

Requirements:
1. Extract all named characters (ignore unnamed background characters)
2. For each character, extract:
   - name: Character name
   - role: Character role (main/supporting/minor)
   - appearance: Physical appearance (150-300 words)
   - personality: Personality traits (100-200 words)
   - description: Background story and relationships (100-200 words)
3. Appearance must be detailed for AI image generation: gender, age, body type, facial features, hairstyle, clothing
4. Do NOT include scene/background/environment in appearance
5. Style: {style}
6. Image ratio: {ratio}

Output: Pure JSON array, each element is a character object.

**CRITICAL: Return ONLY valid JSON array starting with [ and ending with ].**"""

        return f"""你是专业角色分析师，擅长从剧本中提取角色信息。

任务：提取并整理剧中所有角色的详细设定。

要求：
1. 提取所有有名字的角色（忽略无名路人）
2. 对每个角色，提取以下信息：
   - name: 角色名字
   - role: 角色类型（main/supporting/minor）
   - appearance: 外貌描述（150-300字）
   - personality: 性格特点（100-200字）
   - description: 背景故事和角色关系（100-200字）
3. 外貌描述要详细，适合AI生成图片：性别、年龄、体型、面部特征、发型、服装风格
4. 外貌描述不要包含任何场景、背景、环境信息
5. 风格要求：{style}
6. 图片比例：{ratio}

输出：纯JSON数组，每个元素是一个角色对象。

**重要：必须只返回纯JSON数组，以 [ 开头，以 ] 结尾。**"""

    def get_scene_extraction_prompt(self) -> str:
        style = self.style.default_scene_style
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""Task: Extract all unique scene backgrounds from the script.

Requirements:
1. Identify all different scenes (location + time combinations)
2. Generate detailed image generation prompts for each scene
3. **Important**: Scenes must be pure backgrounds WITHOUT any characters
4. Must explicitly specify "no people, no characters, empty scene"
5. Style: {style}
6. Image ratio: {ratio}

Output: JSON array, each element containing:
- location: Location (e.g., "luxurious office")
- time: Time period (e.g., "afternoon")
- prompt: Complete image generation prompt (pure background, no people)

**CRITICAL: Return ONLY valid JSON array.**"""

        return f"""【任务】从剧本中提取所有唯一的场景背景

【要求】
1. 识别剧本中所有不同的场景（地点+时间组合）
2. 为每个场景生成详细的图片生成提示词
3. **重要**：场景描述必须是纯背景，不能包含人物
4. 必须明确说明"无人物、无角色、空场景"
5. 风格要求：{style}
6. 图片比例：{ratio}

【输出格式】
JSON数组，每个元素包含：
- location：地点（如"豪华办公室"）
- time：时间（如"下午"）
- prompt：完整的图片生成提示词（纯背景，明确说明无人物）

**重要：必须只返回纯JSON数组。**"""

    def get_storyboard_prompt(self) -> str:
        if self.is_english:
            return """[Role] You are a senior film storyboard artist, proficient in shot breakdown theory.

[Task] Break down the script into storyboard shots based on **independent action units**.

[Principles]
1. Action Unit Division: Each shot = one complete action
2. Shot Types: Extreme Long Shot/Long Shot/Medium Shot/Close-Up/Extreme Close-Up
3. Camera Movement: Fixed/Push/Pull/Pan/Follow/Tracking
4. Emotion Intensity: ↑↑↑(3)/↑↑(2)/↑(1)/→(0)/↓(-1)

[Output] JSON object with storyboards array, each containing:
- shot_number, title, shot_type, camera_angle, camera_movement
- location, time, action, result, dialogue
- atmosphere, emotion, emotion_intensity, duration (4-12 seconds)
- bgm_prompt, sound_effect, characters (ID array), is_primary

**CRITICAL: Return ONLY valid JSON.**"""

        return """【角色】你是资深影视分镜师，精通罗伯特·麦基的镜头拆解理论。

【任务】将剧本按**独立动作单元**拆解为分镜头方案。

【分镜原则】
1. 动作单元划分：一个动作 = 一个镜头
2. 景别标准：大远景/远景/中景/近景/特写
3. 运镜方式：固定/推镜/拉镜/摇镜/跟镜/移镜
4. 情绪强度：↑↑↑(3)/↑↑(2)/↑(1)/→(0)/↓(-1)

【输出】JSON对象，包含storyboards数组，每个镜头包含：
- shot_number: 镜头号
- title: 镜头标题（3-5字概括）
- shot_type: 景别
- camera_angle: 机位角度（平视/仰视/俯视/侧面/背面）
- camera_movement: 运镜方式
- location: 地点（详细描述≥20字）
- time: 时间（详细描述≥15字）
- action: 动作描述（详细≥25字）
- result: 画面结果（详细≥25字）
- dialogue: 对话/独白（如有）
- atmosphere: 环境氛围（详细≥20字）
- emotion: 情绪
- emotion_intensity: 强度（3/2/1/0/-1）
- duration: 时长（4-12秒）
- bgm_prompt: 配乐提示
- sound_effect: 音效描述
- characters: 角色ID数组
- is_primary: 是否主镜

【时长估算】
- 基础：纯对话4秒，纯动作5秒，混合6秒
- 对话调整：无+0，短(1-20字)+1-2，中(21-50字)+2-4，长(51+字)+4-6
- 动作调整：静态+0，简单+0-1，一般+1-2，复杂+2-4

**重要：必须只返回纯JSON。**"""

    def get_first_frame_prompt(self) -> str:
        style = self.style.default_style
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""You are a professional image prompt expert.

Important: This is the FIRST FRAME - a completely static image showing the initial state BEFORE the action begins.

Key Points:
1. Focus on the initial static state - the moment before action
2. Must NOT include any action or movement
3. Describe character's initial posture, position, and expression
4. Include scene atmosphere and environmental details
5. Style: {style}
6. Image ratio: {ratio}

Output: JSON object with:
- prompt: Complete image generation prompt
- description: Brief description"""

        return f"""你是专业图像生成提示词专家。

重要：这是镜头的首帧 - 一个完全静态的画面，展示动作发生之前的初始状态。

关键要点：
1. 聚焦初始静态状态 - 动作发生之前的那一瞬间
2. 必须不包含任何动作或运动
3. 描述角色的初始姿态、位置和表情
4. 可以包含场景氛围和环境细节
5. 风格要求：{style}
6. 图片比例：{ratio}

输出：JSON对象
- prompt：完整的图片生成提示词
- description：简化描述"""

    def get_key_frame_prompt(self) -> str:
        style = self.style.default_style
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""You are a professional image prompt expert.

Important: This is the KEY FRAME - capturing the most intense moment of the action.

Key Points:
1. Focus on the most exciting moment
2. Capture peak emotional expression
3. Emphasize dynamic tension
4. Can include motion blur or dynamic effects
5. Style: {style}
6. Image ratio: {ratio}

Output: JSON object with prompt and description."""

        return f"""你是专业图像生成提示词专家。

重要：这是镜头的关键帧 - 捕捉动作最激烈、最精彩的瞬间。

关键要点：
1. 聚焦动作最精彩的时刻
2. 捕捉情绪表达的顶点
3. 强调动态张力
4. 可以包含动作模糊或动态效果
5. 风格要求：{style}
6. 图片比例：{ratio}

输出：JSON对象，包含prompt和description。"""

    def get_last_frame_prompt(self) -> str:
        style = self.style.default_style
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""You are a professional image prompt expert.

Important: This is the LAST FRAME - showing the final state after action ends.

Key Points:
1. Focus on the final state after action completion
2. Show the result of the action
3. Describe character's final posture and expression
4. Capture the calm moment after action
5. Style: {style}
6. Image ratio: {ratio}

Output: JSON object with prompt and description."""

        return f"""你是专业图像生成提示词专家。

重要：这是镜头的尾帧 - 展示动作结束后的最终状态和结果。

关键要点：
1. 聚焦动作完成后的最终状态
2. 展示动作的结果
3. 描述角色在动作完成后的姿态和表情
4. 捕捉动作结束后的平静瞬间
5. 风格要求：{style}
6. 图片比例：{ratio}

输出：JSON对象，包含prompt和description。"""

    def get_prop_extraction_prompt(self) -> str:
        style = f"{self.style.default_style}, {self.style.default_prop_style}"
        ratio = self.style.default_image_ratio

        if self.is_english:
            return f"""Extract key props from the script.

Requirements:
1. Extract ONLY key props important to the plot
2. Do NOT extract common daily items unless they have special significance
3. Style: {style}
4. Image ratio: {ratio}

Output: JSON array, each object containing:
- name: Prop name
- type: Type (Weapon/Key Item/Daily Item/Special Device)
- description: Role in drama and visual description
- image_prompt: English image generation prompt

**Return JSON array directly.**"""

        return f"""从剧本中提取关键道具。

【要求】
1. 只提取对剧情发展有重要作用的关键道具
2. 普通生活用品如无特殊剧情意义不需要提取
3. 风格要求：{style}
4. 图片比例：{ratio}

【输出格式】
JSON数组，每个对象包含：
- name: 道具名称
- type: 类型（武器/关键证物/日常用品/特殊装置）
- description: 在剧中的作用和外观描述
- image_prompt: 图片生成提示词

**直接返回JSON数组。**"""

    def format_outline_request(self, theme: str, genre: str = "", episode_count: int = 5) -> str:
        if self.is_english:
            prompt = f"Please create a short drama outline for:\n\nTheme: {theme}"
            if genre:
                prompt += f"\nGenre: {genre}"
            prompt += f"\nNumber of episodes: {episode_count}"
            prompt += f"\n\n**Important: Must plan complete storylines for all {episode_count} episodes!**"
        else:
            prompt = f"请为以下主题创作短剧大纲：\n\n主题：{theme}"
            if genre:
                prompt += f"\n类型偏好：{genre}"
            prompt += f"\n剧集数量：{episode_count}集"
            prompt += f"\n\n**重要：必须在episodes数组中规划完整的{episode_count}集剧情！**"
        return prompt

    def format_character_request(self, script_content: str, max_count: int = 10) -> str:
        if self.is_english:
            return f"Script content:\n{script_content}\n\nPlease extract up to {max_count} main characters."
        return f"剧本内容：\n{script_content}\n\n请从剧本中提取最多 {max_count} 个主要角色的详细设定。"

    def format_storyboard_request(
        self, script_content: str, characters: list[dict], scenes: list[dict]
    ) -> str:
        char_list = "无角色"
        if characters:
            char_list = str([{"id": c.get("id"), "name": c.get("name")} for c in characters])

        scene_list = "无场景"
        if scenes:
            scene_list = str([{"id": s.get("id"), "location": s.get("location"), "time": s.get("time")} for s in scenes])

        if self.is_english:
            return f"""【Script Content】
{script_content}

【Available Characters】
{char_list}
**Important**: Only use character IDs from above list.

【Available Scenes】
{scene_list}
**Important**: Select matching scene_id from above list, or use null.

Please break down into storyboard shots."""

        return f"""【剧本内容】
{script_content}

【本剧可用角色列表】
{char_list}
**重要**：在characters字段中，只能使用上述角色列表中的角色ID。

【本剧已提取的场景背景列表】
{scene_list}
**重要**：在scene_id字段中，必须从上述背景列表中选择最匹配的背景ID，没有合适的则填null。

请将剧本拆解为分镜头方案。"""

    def format_frame_request(self, storyboard: dict, frame_type: str = "first") -> str:
        info = f"""镜头信息：
- 场景：{storyboard.get('location', '')}，{storyboard.get('time', '')}
- 景别：{storyboard.get('shot_type', '')}
- 角度：{storyboard.get('camera_angle', '')}
- 动作：{storyboard.get('action', '')}
- 结果：{storyboard.get('result', '')}
- 对话：{storyboard.get('dialogue', '')}
- 氛围：{storyboard.get('atmosphere', '')}
- 情绪：{storyboard.get('emotion', '')}"""

        frame_labels = {
            "first": "首帧",
            "key": "关键帧",
            "last": "尾帧",
        }
        label = frame_labels.get(frame_type, "首帧")

        return f"{info}\n\n请直接生成{label}的图像提示词，不要任何解释："
