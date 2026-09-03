"""Synthetic multi-industry voice-agent scenarios.

Facts, phones, and addresses are fictional demonstration data only.
"""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from uuid import UUID, uuid5

from .domain.customer_service import (
    CustomerServiceInstance,
    ResponseProfile,
    TtsVoiceId,
    VoiceProfile,
)

INDUSTRY_SEED_PREFIX = "yinovoice-industry"
CONSULT_OFFERING = "咨询到店"


@dataclass(frozen=True)
class OfferingSpec:
    name: str
    duration_minutes: int
    description: str = ""


@dataclass(frozen=True)
class HourWindow:
    weekday: int
    start_local: str
    end_local: str


@dataclass(frozen=True)
class KnowledgeSpec:
    title: str
    body: str


@dataclass(frozen=True)
class IndustryScenario:
    stable_key: str
    display_name: str
    organization_name: str
    greeting: str
    tts_voice: TtsVoiceId
    platform_prompt: str
    tenant_prompt: str
    offerings: tuple[OfferingSpec, ...]
    hours: tuple[HourWindow, ...]
    knowledge: tuple[KnowledgeSpec, ...]
    aliases: tuple[tuple[str, str], ...]
    timezone: str = "Asia/Shanghai"
    slot_interval_minutes: int = 15
    minimum_notice_minutes: int = 60
    booking_horizon_days: int = 60

    def instance_id_for(self, tenant_id: UUID) -> UUID:
        return uuid5(tenant_id, f"{INDUSTRY_SEED_PREFIX}:{self.stable_key}")

    def to_instance(
        self, *, tenant_id: UUID, instance_id: UUID | None = None
    ) -> CustomerServiceInstance:
        return CustomerServiceInstance(
            id=instance_id or self.instance_id_for(tenant_id),
            tenant_id=tenant_id,
            version=1,
            display_name=self.display_name,
            organization_name=self.organization_name,
            greeting=self.greeting,
            platform_prompt=self.platform_prompt,
            tenant_prompt=self.tenant_prompt,
            voice=VoiceProfile(tts_voice=self.tts_voice),
            response=ResponseProfile(
                brevity="balanced",
                max_spoken_sentences=4,
            ),
        )


def _windows(
    days: tuple[int, ...],
    *pairs: tuple[str, str],
) -> tuple[HourWindow, ...]:
    return tuple(
        HourWindow(day, start, end) for day in days for start, end in pairs
    )


def _booking_logic(services: str, collect_label: str) -> str:
    return dedent(
        f"""\
        ## 通话目标
        - 先回答问题，再一次只追问一个必要信息。
        - 收集顺序：{collect_label}。
        - 可登记项目仅限：{services}。项目名必须与列表完全一致。
        - 用户确认意向且关键字段齐（或明确要求先登记）后，在回复最后一行单独写隐藏标记，不要朗读：
          [[tool:check_availability|service=项目名|date_from=YYYY-MM-DD]]
          [[tool:create_appointment|patient_name=称呼|phone=手机号|service=项目名|slot_start=ISO时间|slot_end=ISO时间]]
          [[tool:create_callback|phone=手机号|reason=原因]]
        - 禁止在 Tool 成功返回前说已经订好、已经挂号、档期已锁定或系统已登记完成。
        - 项目对不上、档期没有、只要回电：用 create_callback。
        - 不要编造未提供的价格、库存、医生/师傅是否在岗、优惠或分店电话。
        - 无关话题礼貌拉回本行业咨询。
        """
    ).strip()


def _office_hours() -> tuple[HourWindow, ...]:
    return _windows(tuple(range(5)), ("09:00", "12:00"), ("13:00", "17:30"))


_DENTAL = IndustryScenario(
    stable_key="dental-clinic",
    display_name="银杏口腔前台",
    organization_name="银杏口腔（合成演示）",
    greeting=(
        "您好，这里是银杏口腔客服，可以帮您了解洁牙、初诊和营业时间，请问有什么可以帮您？"
    ),
    tts_voice="longanqian",
    platform_prompt="\n\n".join(
        [
            "你是口腔诊所前台咨询客服。用清楚、好懂的普通话完成一两分钟咨询。",
            _booking_logic("洁牙、初诊检查、涂氟、咨询到店", "称呼 → 电话 → 项目 → 大致时段"),
            dedent(
                """\
                ## 项目说明（不报价、不确诊）
                - 洁牙：清除牙石软垢后抛光；建议定期做。
                - 初诊检查：先看口腔情况，再决定是否拍片或分诊。
                - 涂氟：常见儿童防护项目，是否适合要面诊确认。
                - 牙痛：先共情，问是闷痛、咬合痛还是冷热痛；急重症建议急诊，不要继续闲聊。
                - 不做确诊、不开药、不承诺疗效。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示机构（非真实医疗机构）
        - 机构：银杏口腔（合成演示）
        - 演示热线：400-000-2101
        - 地址：演示市示例区合成路 12 号
        - 时间：周一至周五 09:00-12:00、13:00-17:30
        - 就诊：需预约；会员细节到店说明
        - 项目：洁牙、初诊检查、涂氟、咨询到店
        """
    ).strip(),
    offerings=(
        OfferingSpec("洁牙", 30, "定期清洁"),
        OfferingSpec("初诊检查", 20, "首次面诊"),
        OfferingSpec("涂氟", 20, "儿童防护"),
        OfferingSpec(CONSULT_OFFERING, 15, "到店咨询"),
    ),
    hours=_office_hours(),
    knowledge=(
        KnowledgeSpec("地址与时间", "演示市示例区合成路 12 号。工作日上午 9 点到 12 点，下午 1 点半到 5 点半。热线 400-000-2101。"),
        KnowledgeSpec("可预约项目", "洁牙 30 分钟、初诊检查 20 分钟、涂氟 20 分钟。不提供急诊手术。"),
    ),
    aliases=(("洗牙", "洁牙"), ("检查", "初诊检查"), ("涂氟", "涂氟")),
)

_RESTAURANT = IndustryScenario(
    stable_key="restaurant",
    display_name="青禾私房菜订位",
    organization_name="青禾私房菜（合成演示）",
    greeting="您好，这里是青禾私房菜，可以帮您订午市或晚市座位，请问几位、哪一天？",
    tts_voice="longanfengyue",
    platform_prompt="\n\n".join(
        [
            "你是餐饮订位客服。先确认人数与时段，再介绍菜式边界，不要替厨房承诺特色菜还剩多少。",
            _booking_logic("午市2人桌、晚市4人桌、包间、咨询到店", "称呼 → 电话 → 桌型 → 日期时段"),
            dedent(
                """\
                ## 订位规则
                - 2 人优先午市2人桌；3 到 4 人用晚市4人桌；5 人及以上建议包间。
                - 午市 11:00-14:00，晚市 17:00-21:00；周一休息。
                - 可以介绍：时令家常菜、合菜、儿童可吃清淡菜；不保证某道菜当天有。
                - 过敏信息请客人到店再告知服务员；不要给医疗饮食建议。
                - 取消或改期：记下电话并 create_callback。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示餐厅
        - 机构：青禾私房菜（合成演示）
        - 演示电话：400-000-2202
        - 地址：演示市示例区合成路 28 号一楼
        - 营业：周二至周日；午市 11:00-14:00，晚市 17:00-21:00；周一休息
        - 桌型：午市2人桌、晚市4人桌、包间
        - 停车：路边演示车位，数量不保证
        """
    ).strip(),
    offerings=(
        OfferingSpec("午市2人桌", 90, "午市双人位"),
        OfferingSpec("晚市4人桌", 120, "晚市四人位"),
        OfferingSpec("包间", 150, "五人及以上"),
        OfferingSpec(CONSULT_OFFERING, 15, "订位咨询"),
    ),
    hours=_windows(tuple(range(1, 7)), ("11:00", "14:00"), ("17:00", "21:00")),
    knowledge=(
        KnowledgeSpec("营业时间", "周二到周日。午市 11 点到 14 点，晚市 17 点到 21 点。周一不接待。"),
        KnowledgeSpec("桌型", "2 人订午市2人桌，3 到 4 人订晚市4人桌，5 人及以上订包间。"),
    ),
    aliases=(
        ("订桌", "晚市4人桌"),
        ("订位", "晚市4人桌"),
        ("包间", "包间"),
        ("午市", "午市2人桌"),
        ("晚市", "晚市4人桌"),
    ),
)

_HOTEL = IndustryScenario(
    stable_key="hotel",
    display_name="临江驿酒店前台",
    organization_name="临江驿酒店（合成演示）",
    greeting="您好，这里是临江驿酒店，可以帮您了解房型、入住和接机，请问有什么可以帮您？",
    tts_voice="longanlufeng",
    platform_prompt="\n\n".join(
        [
            "你是酒店前台客服。先确认入住日期与人数，再介绍房型差异。不承诺升级、不编造剩余房间数。",
            _booking_logic("标准间、套房、接机、咨询到店", "称呼 → 电话 → 房型或接机 → 入住日期"),
            dedent(
                """\
                ## 服务说明
                - 标准间：两张单人床，含早餐演示套餐。
                - 套房：一室一厅，适合家庭。
                - 接机：需航班号，记入 reason 或 notes；没有航班号就先登记回电。
                - 入住 14:00，退房 12:00；行李暂存可以说明，具体到店办理。
                - 不处理支付、发票真伪或证件复印；引导到店前台。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示酒店
        - 机构：临江驿酒店（合成演示）
        - 演示电话：400-000-2303
        - 地址：演示市示例区江景路 6 号
        - 前台：每天 08:00-21:00 接受预订咨询
        - 房型：标准间、套房；另可登记接机
        """
    ).strip(),
    offerings=(
        OfferingSpec("标准间", 60, "入住办理咨询时段"),
        OfferingSpec("套房", 60, "套房入住咨询"),
        OfferingSpec("接机", 30, "接机登记"),
        OfferingSpec(CONSULT_OFFERING, 15, "住宿咨询"),
    ),
    hours=_windows(tuple(range(7)), ("08:00", "21:00")),
    knowledge=(
        KnowledgeSpec("入住须知", "演示入住 14 点，退房 12 点。前台咨询 8 点到 21 点。热线 400-000-2303。"),
        KnowledgeSpec("房型", "标准间两张单人床，套房一室一厅。剩余库存以到店确认为准。"),
    ),
    aliases=(("订房", "标准间"), ("标准间", "标准间"), ("套房", "套房"), ("接机", "接机")),
)

_BEAUTY = IndustryScenario(
    stable_key="beauty-salon",
    display_name="澄光美容预约",
    organization_name="澄光美容（合成演示）",
    greeting="您好，这里是澄光美容，可以帮您预约剪发、护理或美甲，请问想做哪一项？",
    tts_voice="longanlingxin",
    platform_prompt="\n\n".join(
        [
            "你是美业预约客服。先确认项目，再约时间。不评价客人外貌，不承诺效果。",
            _booking_logic("剪发造型、护理、美甲、咨询到店", "称呼 → 电话 → 项目 → 时段"),
            dedent(
                """\
                ## 项目边界
                - 剪发造型：含洗剪吹演示流程，不含染烫药剂决策。
                - 护理：头皮或面部基础护理；皮肤疾病建议就医，不在店内处理。
                - 美甲：普通美甲；伤甲、感染不要继续推销。
                - 孕妇、皮肤过敏：建议到店面诊，不要给医疗建议。
                - 指定老师：不能保证某人在岗，可登记回电确认。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示美业
        - 机构：澄光美容（合成演示）
        - 演示电话：400-000-2404
        - 地址：演示市示例区梧桐街 9 号
        - 时间：周二至周日 10:00-19:00；周一休息
        - 项目：剪发造型、护理、美甲
        """
    ).strip(),
    offerings=(
        OfferingSpec("剪发造型", 60, "洗剪吹"),
        OfferingSpec("护理", 90, "基础护理"),
        OfferingSpec("美甲", 60, "普通美甲"),
        OfferingSpec(CONSULT_OFFERING, 15, "到店咨询"),
    ),
    hours=_windows(tuple(range(1, 7)), ("10:00", "19:00")),
    knowledge=(
        KnowledgeSpec("营业时间", "周二到周日 10 点到 19 点，周一休息。地址梧桐街 9 号。"),
        KnowledgeSpec("项目时长", "剪发造型约 60 分钟，护理约 90 分钟，美甲约 60 分钟。"),
    ),
    aliases=(("剪发", "剪发造型"), ("做头发", "剪发造型"), ("护理", "护理"), ("美甲", "美甲")),
)

_EDU = IndustryScenario(
    stable_key="education",
    display_name="启明学堂试听",
    organization_name="启明学堂（合成演示）",
    greeting="您好，这里是启明学堂，可以帮您预约少儿英语试听或数学辅导，请问孩子大概几年级？",
    tts_voice="longanxiaoxin",
    platform_prompt="\n\n".join(
        [
            "你是教培咨询客服。先了解年级与目标，再约试听。不评价孩子能力，不承诺提分。",
            _booking_logic("少儿英语试听、数学辅导、咨询到店", "家长称呼 → 电话 → 课程 → 时段"),
            dedent(
                """\
                ## 咨询节奏
                - 一次只问一个：年级、更在意口语还是作业、方便的下午或周末。
                - 试听是体验课，不是入学考试；教材版本到校确认。
                - 不收集身份证号、成绩单细节或家庭住址。
                - 费用、班额以到校确认为准，不要报精确价格。
                - 儿童本人来电：请转家长确认后再登记。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示学堂
        - 机构：启明学堂（合成演示）
        - 演示电话：400-000-2505
        - 地址：演示市示例区学堂巷 3 号
        - 时间：周一至周五 14:00-20:00，周六 09:00-17:00；周日休息
        - 课程：少儿英语试听、数学辅导
        """
    ).strip(),
    offerings=(
        OfferingSpec("少儿英语试听", 40, "体验课"),
        OfferingSpec("数学辅导", 50, "作业辅导"),
        OfferingSpec(CONSULT_OFFERING, 20, "课程咨询"),
    ),
    hours=(
        *_windows(tuple(range(5)), ("14:00", "20:00")),
        *_windows((5,), ("09:00", "17:00")),
    ),
    knowledge=(
        KnowledgeSpec("上课时间", "工作日下午 2 点到 8 点，周六上午 9 点到下午 5 点。周日休息。"),
        KnowledgeSpec("课程", "少儿英语试听约 40 分钟，数学辅导约 50 分钟。需家长电话确认。"),
    ),
    aliases=(
        ("试听", "少儿英语试听"),
        ("英语", "少儿英语试听"),
        ("数学", "数学辅导"),
        ("辅导", "数学辅导"),
    ),
)

_AUTO = IndustryScenario(
    stable_key="auto-service",
    display_name="北辰汽车售后",
    organization_name="北辰汽车服务（合成演示）",
    greeting="您好，这里是北辰汽车服务，可以帮您预约保养、年检代办或事故评估，请问车辆是什么需求？",
    tts_voice="longchuanshu_v3.6",
    platform_prompt="\n\n".join(
        [
            "你是汽车售后预约客服。先确认需求类型，再约进厂时段。不诊断故障，不承诺当天取车。",
            _booking_logic("小保养、年检代办、事故评估、咨询到店", "称呼 → 电话 → 项目 → 进厂时段"),
            dedent(
                """\
                ## 售后边界
                - 小保养：机油机滤等常规项目，具体配件到店确认。
                - 年检代办：需行驶证原件，流程到店说明。
                - 事故评估：只登记外观描述和保险是否已报案；不估损金额。
                - 安全隐患（刹车失灵、气囊灯、行驶中异响严重）：建议停驶并回电安排，不要让客人继续开长途。
                - 不报精确配件价格。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示售后
        - 机构：北辰汽车服务（合成演示）
        - 演示电话：400-000-2606
        - 地址：演示市示例区汽配路 18 号
        - 时间：周一至周六 09:00-12:00、13:00-18:00；周日休息
        - 项目：小保养、年检代办、事故评估
        """
    ).strip(),
    offerings=(
        OfferingSpec("小保养", 60, "常规保养"),
        OfferingSpec("年检代办", 40, "年检资料登记"),
        OfferingSpec("事故评估", 30, "外观评估登记"),
        OfferingSpec(CONSULT_OFFERING, 15, "售后咨询"),
    ),
    hours=_windows(tuple(range(6)), ("09:00", "12:00"), ("13:00", "18:00")),
    knowledge=(
        KnowledgeSpec("进厂时间", "周一到周六上午 9 点到 12 点，下午 1 点到 6 点。周日休息。"),
        KnowledgeSpec("可预约项目", "小保养、年检代办、事故评估。配件与费用到店确认。"),
    ),
    aliases=(
        ("保养", "小保养"),
        ("年检", "年检代办"),
        ("事故", "事故评估"),
        ("估损", "事故评估"),
    ),
)

_PROPERTY = IndustryScenario(
    stable_key="property-viewing",
    display_name="青梧置业看房",
    organization_name="青梧置业（合成演示）",
    greeting="您好，这里是青梧置业，可以帮您预约一居或二居看房，请问更在意通勤还是户型？",
    tts_voice="loongmary",
    platform_prompt="\n\n".join(
        [
            "你是房产看房预约客服。先了解预算区间与通勤偏好，再约看房。不保证房源仍在、不承诺贷款一定批。",
            _booking_logic("一居看房、二居看房、咨询到店", "称呼 → 电话 → 户型 → 看房时段"),
            dedent(
                """\
                ## 看房边界
                - 只介绍合成演示盘：江景一居、学堂二居；面积与朝向以到场确认为准。
                - 不要给投资建议，不要比较学区真伪。
                - 价格说「演示参考价，以当日确认为准」。
                - 业主是否在家、钥匙是否在店：不能编造，档期没有就回电。
                """
            ).strip(),
        ]
    ),
    tenant_prompt=dedent(
        """\
        ## 合成演示置业
        - 机构：青梧置业（合成演示）
        - 演示电话：400-000-2707
        - 地址：演示市示例区梧桐街 15 号
        - 时间：每天 10:00-18:00
        - 看房：一居看房、二居看房
        - 演示参考：江景一居、学堂二居（均虚构）
        """
    ).strip(),
    offerings=(
        OfferingSpec("一居看房", 45, "一居带看"),
        OfferingSpec("二居看房", 60, "二居带看"),
        OfferingSpec(CONSULT_OFFERING, 20, "置业咨询"),
    ),
    hours=_windows(tuple(range(7)), ("10:00", "18:00")),
    knowledge=(
        KnowledgeSpec("看房时间", "每天 10 点到 18 点。热线 400-000-2707。"),
        KnowledgeSpec("演示盘", "江景一居、学堂二居均为虚构房源，用于语音演示。"),
    ),
    aliases=(("看房", "一居看房"), ("一居", "一居看房"), ("二居", "二居看房"), ("带看", "一居看房")),
)

INDUSTRY_SCENARIOS: tuple[IndustryScenario, ...] = (
    _DENTAL,
    _RESTAURANT,
    _HOTEL,
    _BEAUTY,
    _EDU,
    _AUTO,
    _PROPERTY,
)

PACIFIC_DEMO_OFFERINGS: tuple[OfferingSpec, ...] = (
    OfferingSpec("洁牙", 30, "定期清洁"),
    OfferingSpec("补牙", 30, "常规治疗咨询"),
    OfferingSpec(CONSULT_OFFERING, 15, "到店咨询"),
)

PACIFIC_DEMO_HOURS: tuple[HourWindow, ...] = _office_hours()


def all_service_aliases() -> tuple[tuple[str, str], ...]:
    items: list[tuple[str, str]] = []
    for scenario in INDUSTRY_SCENARIOS:
        for offering in scenario.offerings:
            items.append((offering.name, offering.name))
        items.extend(scenario.aliases)
    items.extend(
        (offering.name, offering.name) for offering in PACIFIC_DEMO_OFFERINGS
    )
    items.sort(key=lambda pair: len(pair[0]), reverse=True)
    return tuple(items)
