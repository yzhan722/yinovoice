from __future__ import annotations

import re
import textwrap
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Admin-managed dialogue framework (scripts, triage, project explainers).
DEMO_PACIFIC_PLATFORM_PROMPT = textwrap.dedent(
    """\
    你是口腔机构的前台咨询客服。目标是自然完成约一两分钟咨询：先给清楚、有用的回答，再按需要做一个跟进问题或项目介绍，最后必要时引导到店或确认预约/回拨意向。

    ## 角色与表达
    - 专业、简洁、好懂：少术语，必要术语用大白话带一句解释。
    - 每次先答问题，再最多追问一个点；不要车轱辘话和模板腔。
    - 少用「需要医生检查后才能确定」这类套话。整通电话最多说一次类似提醒；多数情况直接给常识说明、流程介绍或行动建议。
    - 不要编造价格、排班、当天能否就诊、优惠或未核实的分院电话。
    - 不做确诊、不开药、不承诺疗效；可以说常见情况和一般怎么做。
    - 急重症（严重出血不止、呼吸困难、明显肿胀伴高热、外伤掉牙等）：建议立刻急诊或拨打急救电话，并可告知打客服热线协助；不要继续闲聊。

    ## 预约与回拨意向（可收集，不可宣称已成功）
    - 客户想预约或希望回电时：优先问清称呼/姓名（便于工作人员回拨），再按需问联系电话、项目（如洁牙）、大致时段（如周五下午）。
    - 一次只追问一个点：还不知道名字时先问「请问怎么称呼您？」；已有名字再问电话或时间。
    - 可以说「已记下您的意向，工作人员会联系确认档期」。
    - 禁止说「已经约好」「挂号成功」「系统已登记完成」「档期已锁定」等既成事实表述；本通道只登记意向，最终档期与医生排班由工作人员确认。
    - 不要编造某位医生是否有空、某日某时能否就诊；当前不做真实医生档期校验。
    - 会员制、预约制就诊规则可说明；核实地址/热线以业务知识为准。

    ## 项目怎么做（客户问流程时用，通俗短讲，不报价）
    - 种植牙：一般先拍片看牙槽骨，再植入种植体（像“牙根”），等稳固后装牙冠。周期因人而异，不要保证一次做完。
    - 正畸：先检查和拍片，再选托槽矫正或隐形牙套等，靠持续加力把牙排齐；疗程通常按月计。可问更在意整齐还是咬合。
    - 补牙：清理龋坏部分，再用补牙材料恢复外形；小洞常可一次完成。
    - 根管治疗（牙神经）：清理感染的牙髓，消毒后封填，必要时再做牙冠保护。
    - 洁牙/护理：超声波等方式清除牙石软垢，再抛光；建议定期做。
    - 美白：常见有诊室冷光美白等，先确认牙齿牙龈健康，再按疗程提亮；有蛀牙或牙龈问题宜先处理再美白。
    - 贴面等美容：在牙面做薄层修复改善颜色或外形；是否合适要面诊看。

    ## 症状沟通（一次只问一个）
    先简短共情 + 一句有用说明，再问一个细节；用「建议尽快到店看看」代替反复强调无法确定。
    - 牙痛：问是闷痛、咬合痛还是刺痛；下一轮可问冷热是否加重。
    - 牙龈肿或出血：问刷牙出血还是自发出血、有无肿胀；提醒清洁并建议尽早处理。
    - 敏感酸痛：问冷热酸甜哪类更明显；常见和牙本质暴露、过度磨损有关。
    - 智齿不适：问是否牵涉耳后、张口是否困难；反复发炎宜尽早面诊。
    - 缺牙/松动：可介绍种植或活动义齿等常见方向，并引导确认预约评估意向；不替客户选定方案。

    ## 多轮节奏
    - 先答事实或流程，再补充一句实用信息，需要时只追问一个问题。
    - 适时给地址、时间或热线（以业务知识中的核实信息为准），推动预约到店；不要用“抱歉没法回答”敷衍。
    - 无关话题礼貌拉回口腔咨询。
    """
).strip()

# Tenant-managed clinic facts / business knowledge (official site only).
DEMO_PACIFIC_DENTAL_TENANT_PROMPT = textwrap.dedent(
    """\
    ## 已核实公开信息（官网 http://www.cztpykq.com/）
    - 机构名称：常州太平洋口腔
    - 客服热线：400-0519-020
    - 总部电话：0519-86613222
    - 总部地址：常州市天宁区局前街223号（人民医院西侧约60米）
    - 电子邮箱：544648191@qq.com
    - 营业时间：无休假门诊，每天 8:30-17:30
    - 就诊方式：会员制、预约制就诊
    - 服务类别：牙齿种植、牙齿正畸、牙齿治疗、牙齿美容、牙齿美白、牙齿护理
    - 资质相关公开表述：常州市和武进区医保定点医疗机构（按官网简介）
    - 分院：新北店（新北区通江南路266号，三井加油站旁）；武进店（武进区玉塘路紫金城北区，中医院向南约30米）
    - 特色：美容齿科与种植牙；官网提及国际种植学会 ITI 相关合作表述

    ## 基础咨询补充
    - 总部地址：局前街223号，人民医院西侧约60米；可问更方便去总部还是分院。
    - 分院专线未核实时，引导打 400-0519-020 或 0519-86613222。
    - 医保报销细节到店由工作人员说明。
    """
).strip()

VoicePresetId = Literal["mandarin-standard"]
VoiceLocale = Literal["zh-CN"]
VoiceStyle = Literal["professional-friendly"]
VoiceEmotion = Literal["neutral"]
VoicePauseProfile = Literal["receptionist"]
# Exact Qwen-Audio Realtime supported set (from gateway error messages).
TtsVoiceId = Literal[
    "longanqian",
    "longanlingxin",
    "longanlingxi",
    "longanxiaoxin",
    "longanlufeng",
    "longanfengyue",
    "longanyuanfei",
    "longanhuan_v3.6",
    "longjielidou_v3.6",
    "longpaopao_v3.6",
    "longhuohuo_v3.6",
    "longchuanshu_v3.6",
    "loongmary",
    "loongeva_v3.6",
    "loongjohn",
]

TTS_VOICE_CHOICES: tuple[TtsVoiceId, ...] = (
    "longanqian",
    "longanlingxin",
    "longanlingxi",
    "longanxiaoxin",
    "longanlufeng",
    "longanfengyue",
    "longanyuanfei",
    "longanhuan_v3.6",
    "longjielidou_v3.6",
    "longpaopao_v3.6",
    "longhuohuo_v3.6",
    "longchuanshu_v3.6",
    "loongmary",
    "loongeva_v3.6",
    "loongjohn",
)

_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")
_GREETING_DISCLOSURE_OVERRIDE = re.compile(
    r"(?:(?<![A-Za-z])AI(?![A-Za-z])|人工|真人|机器人|大模型|语音模型)",
    re.IGNORECASE,
)


def _clean_single_line(value: str) -> str:
    result = value.strip()
    if _CONTROL_CHARACTER.search(result):
        raise ValueError("must not contain control characters")
    return result


def _validate_greeting(value: str) -> str:
    result = _clean_single_line(value)
    if _GREETING_DISCLOSURE_OVERRIDE.search(result):
        raise ValueError("must not make proactive AI or human identity claims")
    return result


class VoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: VoicePresetId = "mandarin-standard"
    locale: VoiceLocale = "zh-CN"
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    pitch: float = Field(default=0.0, ge=-1.0, le=1.0)
    style: VoiceStyle = "professional-friendly"
    emotion: VoiceEmotion = "neutral"
    pause_profile: VoicePauseProfile = "receptionist"
    tts_voice: TtsVoiceId = "longanqian"


class ResponseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brevity: Literal["concise", "balanced", "detailed"] = "concise"
    max_spoken_sentences: int = Field(default=3, ge=1, le=6)
    ask_one_question_at_a_time: Literal[True] = True


class CustomerServiceInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    version: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=120)
    business_profile: str = "generic-receptionist"
    primary_language: str = "zh-CN"
    greeting: str
    platform_prompt: str = ""
    tenant_prompt: str = ""
    voice: VoiceProfile
    response: ResponseProfile
    deleted_at: datetime | None = None

    @field_validator("display_name", "organization_name")
    @classmethod
    def validate_single_line_tenant_text(cls, value: str) -> str:
        return _clean_single_line(value)

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, value: str) -> str:
        return _validate_greeting(value)

    @classmethod
    def demo(
        cls,
        *,
        instance_id: UUID,
        tenant_id: UUID,
    ) -> CustomerServiceInstance:
        return cls(
            id=instance_id,
            tenant_id=tenant_id,
            version=1,
            display_name="常州太平洋口腔语音客服",
            organization_name="常州太平洋口腔",
            greeting=(
                "您好，这里是常州太平洋口腔客服，"
                "可以帮您了解门店地址、营业时间和诊疗服务，请问有什么可以帮您？"
            ),
            platform_prompt=DEMO_PACIFIC_PLATFORM_PROMPT,
            tenant_prompt=DEMO_PACIFIC_DENTAL_TENANT_PROMPT,
            voice=VoiceProfile(
                preset_id="mandarin-standard",
                tts_voice="longanqian",
            ),
            response=ResponseProfile(
                brevity="balanced",
                max_spoken_sentences=4,
            ),
        )


class CustomerServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=120)
    greeting: str = Field(min_length=1, max_length=300)
    platform_prompt: str = Field(default="", max_length=8000)
    tenant_prompt: str = Field(default="", max_length=8000)
    voice: VoiceProfile = Field(default_factory=VoiceProfile)
    response: ResponseProfile = Field(default_factory=ResponseProfile)

    @field_validator("display_name", "organization_name")
    @classmethod
    def validate_single_line_tenant_text(cls, value: str) -> str:
        return _clean_single_line(value)

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, value: str) -> str:
        return _validate_greeting(value)


class CustomerServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=120)
    greeting: str = Field(min_length=1, max_length=300)
    platform_prompt: str = Field(default="", max_length=8000)
    tenant_prompt: str = Field(default="", max_length=8000)
    voice: VoiceProfile
    response: ResponseProfile

    @field_validator("display_name", "organization_name")
    @classmethod
    def validate_single_line_tenant_text(cls, value: str) -> str:
        return _clean_single_line(value)

    @field_validator("greeting")
    @classmethod
    def validate_greeting(cls, value: str) -> str:
        return _validate_greeting(value)


DEMO_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_CUSTOMER_SERVICE_ID = UUID("00000000-0000-0000-0000-000000000101")
