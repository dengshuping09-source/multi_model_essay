from __future__ import annotations

from collections.abc import Iterable

from app.schemas.material import MaterialCategory, MaterialReference, MaterialType, WritingMaterial


DEFAULT_MATERIAL_TYPES: dict[MaterialCategory, MaterialType] = {
    "人物": "人物素材",
    "事件": "事件素材",
    "历史": "历史文化",
    "科技": "科技创新",
    "文化": "历史文化",
    "社会": "社会生活",
    "青春成长": "社会生活",
}


def _material(
    material_id: str,
    title: str,
    category: MaterialCategory,
    source_kind: str,
    background: str,
    facts: list[str],
    themes: list[str],
    supports: list[str],
    how_to_use: str,
    common_misuse: str,
    example_use: str,
    note: str,
    references: list[MaterialReference] | None = None,
    *,
    material_type: MaterialType | None = None,
    quote_text: str | None = None,
    attribution: str | None = None,
    origin: str | None = None,
    idiom_meaning: str | None = None,
    idiom_story: str | None = None,
    verification_note: str | None = None,
) -> WritingMaterial:
    return WritingMaterial(
        id=material_id,
        title=title,
        category=category,
        material_type=material_type or DEFAULT_MATERIAL_TYPES[category],
        source_kind=source_kind,  # validated at module import time
        background=background,
        core_facts=facts,
        themes=themes,
        supports_claims=supports,
        how_to_use=how_to_use,
        common_misuse=common_misuse,
        example_use=example_use,
        fact_check_note=note,
        reference_links=references or [],
        quote_text=quote_text,
        attribution=attribution,
        origin=origin,
        idiom_meaning=idiom_meaning,
        idiom_story=idiom_story,
        verification_note=verification_note,
    )


# Each item is intentionally a short original summary of well-established public facts
# or an explicitly labelled everyday observation. There are no quotations, fabricated
# dialogue, or precise figures that students could mistakenly repeat as facts.
BASE_MATERIALS: tuple[WritingMaterial, ...] = (
    _material(
        "sima-qian-shiji",
        "司马迁撰写《史记》",
        "历史",
        "公共事实",
        "司马迁在遭遇人生重创后，仍长期整理史料并完成《史记》。",
        ["《史记》是中国重要的纪传体史书。", "司马迁经历困境后没有放弃写作与治史。"],
        ["坚持", "责任", "理想", "挫折", "长期积累"],
        ["面对挫折仍坚持完成有价值的目标。", "责任感能支撑长期行动。"],
        "先交代他面对的困难，再写他如何把个人处境转化为长期行动，最后回到自己的观点。",
        "不要只写“他很伟大、很坚持”，也不要补写未经核实的心理活动或名言。",
        "当写“真正的坚持需要目标感”时，可用他长期整理史料、完成著作来说明坚持并非一时冲动。",
        "涉及具体年代、经历细节时，请在写作前自行核对可靠资料。",
        [
            MaterialReference(
                title="《史记》：中华民族的文化瑰宝",
                publisher="全国哲学社会科学工作办公室",
                url="https://www.nopss.gov.cn/n1/2024/0221/c458483-40180418.html",
            )
        ],
    ),
    _material(
        "tu-youyou-artemisinin",
        "屠呦呦与青蒿素研究",
        "人物",
        "公共事实",
        "屠呦呦参与抗疟药物研究，团队从传统医药文献中获得启发，并通过反复实验推进研究。",
        ["青蒿素的发现与疟疾治疗有关。", "研究过程结合了文献线索、实验验证与团队协作。"],
        ["坚持", "科研精神", "实践探索", "责任担当", "合作"],
        ["创新需要尊重已有知识，也需要实验验证。", "解决问题离不开耐心求证。"],
        "把“从资料中找到线索”和“用实验反复验证”连成因果，说明创新不是凭空想象。",
        "不要把科研写成单人灵光一现，也不要编造具体实验次数或名言。",
        "论证“创新离不开扎实求证”时，可写研究从文献启发出发，再经实验验证的过程。",
        "不使用精确年份、药效数字或引语；若需要，请查阅权威科研机构资料。",
        [
            MaterialReference(
                title="Tu Youyou – Biographical",
                publisher="诺贝尔奖官方网站",
                url="https://www.nobelprize.org/prizes/medicine/2015/tu/biographical/",
            )
        ],
    ),
    _material(
        "beidou-navigation",
        "北斗卫星导航系统",
        "科技",
        "公共事实",
        "北斗卫星导航系统服务于定位、导航和授时等应用，也进入交通、农业、救援等日常场景。",
        ["卫星导航依靠长期建设和多领域协作。", "技术价值会在具体应用场景中体现。"],
        ["科技报国", "协作", "长期投入", "创新", "服务生活"],
        ["重大技术进步来自长期积累和系统协作。", "科技的意义在于解决真实问题。"],
        "选择一个贴近题目的应用场景，再回到“长期投入如何改变生活”的观点。",
        "不要罗列专业参数，也不要把技术名称当成万能论据。",
        "写“科技应服务生活”时，可从导航、交通或救援等具体使用场景切入。",
        "技术参数更新较快；本条只提供稳定的公共事实和写作方向。",
        [
            MaterialReference(
                title="北斗卫星导航系统",
                publisher="中国卫星导航系统管理办公室",
                url="https://www.beidou.gov.cn/",
            )
        ],
    ),
    _material(
        "dunhuang-conservation",
        "敦煌文化遗产保护",
        "文化",
        "公共事实",
        "敦煌莫高窟等文化遗产需要文物工作者长期保护，也通过数字化等方式让更多人理解传统文化。",
        ["文化遗产保护需要专业、耐心和长期投入。", "数字化可以帮助公众接近珍贵文化遗产。"],
        ["文化传承", "守护", "创新", "责任", "耐心"],
        ["传承不是停留在口号，而是具体的守护与传播。", "新技术可以为传统文化打开新的理解方式。"],
        "先写“为什么需要保护”，再写保护者或数字化传播怎样回应这个问题。",
        "不要把文物保护简单说成“修旧如新”，也不要虚构洞窟、壁画的具体细节。",
        "写“传统文化需要当代守护”时，可将长期保护与数字化传播并列，形成更完整的论证。",
        "如果引用具体洞窟、作品或保护技术，请另行核对博物馆、研究机构资料。",
        [
            MaterialReference(
                title="敦煌研究院文物数字化研究所",
                publisher="敦煌研究院",
                url="https://www.dha.ac.cn/info/1194/2351.htm",
            )
        ],
    ),
    _material(
        "dujiangyan-water-project",
        "都江堰水利工程",
        "历史",
        "公共事实",
        "都江堰是古代水利工程，体现了因地制宜、顺应自然和长期惠及民生的工程智慧。",
        ["都江堰服务于水利调节和灌溉。", "其价值与因势利导、长期维护有关。"],
        ["智慧", "实践", "人与自然", "民生", "传承"],
        ["解决复杂问题需要观察实际条件。", "好的方案应兼顾当下需要与长远影响。"],
        "不要只报工程名称；写清“先观察自然条件，再寻找合适办法”的思考过程。",
        "不要把古代工程神化成无所不能，也不要堆砌术语。",
        "讨论“智慧来自实践”时，可用因地制宜的工程思路说明观察与方案之间的关系。",
        "工程细节和具体年代请以权威水利、文化遗产资料为准。",
        [
            MaterialReference(
                title="青城山—都江堰（世界遗产）",
                publisher="联合国教科文组织世界遗产中心",
                url="https://whc.unesco.org/en/list/1001/",
            )
        ],
    ),
    _material(
        "flood-relief-cooperation",
        "防汛救援中的协作",
        "事件",
        "公共事实",
        "面对汛情，救援人员、基层工作者和志愿者常需要分工配合，保障转移、物资和信息传递。",
        ["应急处置依赖清晰分工与彼此配合。", "公共安全需要许多人在各自位置承担责任。"],
        ["责任", "合作", "担当", "互助", "公共意识"],
        ["集体力量来自每个人做好自己的部分。", "责任并不一定是轰轰烈烈的行动。"],
        "选择“分工—配合—结果”中的一条线展开，避免把所有角色同时罗列。",
        "不要借真实灾害编造感人细节，也不要夸大个人作用。",
        "论证“合作让困难被看见并被解决”时，可写不同角色如何衔接信息、物资与行动。",
        "本条不对应某一次具体灾害；若写真实事件，请查证时间、地点和人物。",
        [
            MaterialReference(
                title="应急抢险救灾物资保障体系和能力建设指导意见",
                publisher="中华人民共和国应急管理部",
                url="https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/202410/t20241023_506225.shtml",
            )
        ],
    ),
    _material(
        "barrier-free-community",
        "社区无障碍设施改善",
        "社会",
        "生活观察",
        "坡道、扶手、清晰标识等无障碍设施，能让老人、儿童、推婴儿车者和行动不便者更方便地使用公共空间。",
        ["公共空间的细节会影响不同人群的生活。", "改善设施需要先看见他人的真实困难。"],
        ["同理心", "公共意识", "细节", "尊重", "行动"],
        ["关怀要落实在可使用的细节上。", "发现问题后可以从身边的小改动开始。"],
        "从一次观察到的不便切入，再写一个具体改变怎样帮助更多人。",
        "不要替行动不便者想象夸张感受，也不要把帮助写成居高临下的施舍。",
        "写“善意要落到细节”时，可以从坡道、标识或通道是否方便使用来展开。",
        "这是可在身边观察和核实的生活素材，不对应某个特定社区项目。",
        [
            MaterialReference(
                title="中华人民共和国无障碍环境建设法",
                publisher="中华人民共和国工业和信息化部",
                url="https://gxca.miit.gov.cn/zwgk/zcwj/flfg/art/2024/art_340a68cb6a8e45ae81c121630dd37346.html",
            )
        ],
    ),
    _material(
        "campus-book-corner",
        "整理校园图书角",
        "青春成长",
        "生活观察",
        "一个杂乱的校园图书角，可以通过分类、登记和同学轮流维护，逐渐变成愿意停留阅读的空间。",
        ["小事也需要分工、耐心和持续维护。", "环境改变常从主动发现问题开始。"],
        ["成长", "责任", "合作", "阅读", "行动"],
        ["成长体现在愿意承担一件具体小事。", "合作让一个人的想法变成持续的行动。"],
        "用“发现问题—提出办法—一起维护—看到变化”组织叙事，保留自己的真实经历。",
        "不要把它写成凭一人之力立刻改变所有人的奇迹；要写出过程和他人的参与。",
        "写“我在小事中成长”时，可从一次整理、一次分工或一次坚持维护写起。",
        "这是生活观察型素材，适合替换成你自己的真实校园经历。",
    ),
    _material(
        "migrant-birds-wetland",
        "湿地保护与候鸟栖息",
        "社会",
        "公共事实",
        "湿地为许多生物提供栖息环境，也与水资源调节和生态保护有关。保护湿地需要长期管理和公众参与。",
        ["生态保护与人类生活环境相互关联。", "公共议题需要长期行动，而不只是一次活动。"],
        ["自然保护", "责任", "长期行动", "共生", "公共参与"],
        ["尊重自然是对共同生活环境负责。", "长远问题需要持续行动。"],
        "从一个可观察的现象进入，再写为什么需要长期保护，避免只喊“保护环境”。",
        "不要编造候鸟数量、物种名称或保护成果。",
        "讨论“责任需要长期坚持”时，可用湿地保护需要持续管理来支撑观点。",
        "如需使用具体湿地或物种，请在写作前查阅当地自然保护机构资料。",
        [
            MaterialReference(
                title="中华人民共和国湿地保护法",
                publisher="中华人民共和国生态环境部",
                url="https://www.mee.gov.cn/ywgz/fgbz/fl/202112/t20211227_965347.shtml",
            )
        ],
    ),
)


_CLASSICS_REFERENCE_URL = "https://ctext.org/"
_CLASSICS_PUBLISHER = "中国哲学书电子化计划（古籍正文）"


def _classic_reference(origin: str) -> list[MaterialReference]:
    """Use a deliberately stable catalogue entry, never a model-generated link."""

    return [
        MaterialReference(
            title=f"{origin}（古籍正文检索）",
            publisher=_CLASSICS_PUBLISHER,
            url=_CLASSICS_REFERENCE_URL,
        )
    ]


def _quote(
    material_id: str,
    quote: str,
    origin: str,
    themes: list[str],
    claims: list[str],
    how_to_use: str,
    common_misuse: str,
    example_use: str,
) -> WritingMaterial:
    return _material(
        material_id,
        quote,
        "文化",
        "经典原文",
        f"出自{origin}的一句经典原文，适合先理解句意，再为自己的观点服务。",
        [quote, f"出处：{origin}。"],
        themes,
        claims,
        how_to_use,
        common_misuse,
        example_use,
        "本条按所列古籍正文核对；引用时请保留原意，不把它当作万能开头或结尾。",
        _classic_reference(origin),
        material_type="名人名言",
        quote_text=quote,
        origin=origin,
        verification_note="已按所列古籍正文人工核对；未使用网传归属或模型补写的出处。",
    )


def _idiom(
    material_id: str,
    idiom: str,
    meaning: str,
    origin: str,
    story: str,
    themes: list[str],
    claims: list[str],
    how_to_use: str,
    common_misuse: str,
    example_use: str,
) -> WritingMaterial:
    return _material(
        material_id,
        idiom,
        "历史",
        "古籍典故",
        f"“{idiom}”的典故见于{origin}，写作时应抓住它与论点真正相连的行动或选择。",
        [meaning, f"典故出处：{origin}。"],
        themes,
        claims,
        how_to_use,
        common_misuse,
        example_use,
        "本条只概括古籍中与成语相关的稳定情节；不要添加未经核验的对白、年份或细节。",
        _classic_reference(origin),
        material_type="成语典故",
        origin=origin,
        idiom_meaning=meaning,
        idiom_story=story,
        verification_note="典故按所列古籍正文人工核对；成语的现代引申义已与原典故事分开说明。",
    )


# These are a small, human-verified first batch. New catalogue entries must not
# be generated during a user request: quotations, attributions, and sources are
# intentionally curated before they become recommendable material.
CURATED_QUOTES: tuple[WritingMaterial, ...] = (
    _quote(
        "quote-tian-xing-jian",
        "天行健，君子以自强不息。",
        "《周易·乾卦·象传》",
        ["坚持", "成长", "自强", "长期积累"],
        ["持续自我要求，才能把目标落实为长期行动。"],
        "适合放在论证自我要求或长期行动的段落中，随后必须接自己的分析或事实。",
        "不要把“自强不息”写成只要努力就一定成功，也不要只引用不解释。",
        "面对长期目标，与其等待条件完美，不如在每天的学习中不断校正方向、积累行动。",
    ),
    _quote(
        "quote-qian-li-zhi-xing",
        "千里之行，始于足下。",
        "《道德经·第六十四章》",
        ["坚持", "行动", "目标", "积累"],
        ["远大的目标要靠当下可执行的第一步开始实现。"],
        "适合用来引出具体行动，例如把大目标拆成每天能完成的小步骤。",
        "不要只把它当作“努力”的同义句；重点是起步与持续积累的关系。",
        "真正的改变并不从口号开始，而是从今天愿意完成的一小步开始。",
    ),
    _quote(
        "quote-xue-er-bu-si",
        "学而不思则罔，思而不学则殆。",
        "《论语·为政》",
        ["学习", "思考", "实践", "成长"],
        ["学习既需要吸收知识，也需要独立思考和实践验证。"],
        "适合用于学习方法、独立思考或知行结合的论述。",
        "不要把“思考”理解成脱离学习的空想，也不要把原句拆开曲解。",
        "读书后的提问、整理和实践，能让获得的知识真正变成自己的理解。",
    ),
    _quote(
        "quote-jun-zi-he-er-bu-tong",
        "君子和而不同。",
        "《论语·子路》",
        ["合作", "尊重", "包容", "独立思考"],
        ["真正的合作可以保留不同意见，并在尊重中寻找共同目标。"],
        "适合讨论同学合作、公共讨论或如何面对不同观点。",
        "不要把它写成“所有意见都一样好”；尊重不同不等于放弃判断。",
        "小组讨论不必追求每个人立刻一致，更重要的是听见差异后共同寻找理由充分的方案。",
    ),
    _quote(
        "quote-zhi-bu-qiang-zhe-zhi-bu-da",
        "志不强者智不达。",
        "《墨子·修身》",
        ["理想", "坚持", "目标", "自律"],
        ["清晰而坚定的志向能帮助人把知识和行动落实下来。"],
        "适合写目标感、自律或面对困难时的方向选择。",
        "不要把它用成空泛的励志口号；要写出目标如何改变具体选择。",
        "有了明确方向，学习中的一次次取舍才不只是被动完成任务，而是在靠近自己认定的目标。",
    ),
    _quote(
        "quote-qiong-ze-bian",
        "穷则变，变则通，通则久。",
        "《周易·系辞下》",
        ["创新", "改变", "实践探索", "发展"],
        ["遇到困境时，调整方法比机械重复更可能打开新的局面。"],
        "适合讨论创新、解决问题或在受阻时如何调整方法。",
        "不要把“变”理解为随意放弃原则；应说明为什么要变、怎样变。",
        "当旧办法已无法回应新问题时，主动观察并调整路径，才可能让行动继续向前。",
    ),
    _quote(
        "quote-gou-ri-xin",
        "苟日新，日日新，又日新。",
        "《礼记·大学》",
        ["成长", "自我更新", "坚持", "学习"],
        ["成长来自持续反省和每天一点点的更新。"],
        "适合放在反思成长、习惯养成或持续改进的文章中。",
        "不要理解成每天都必须做惊天动地的新事；重点是持续改进。",
        "一次认真订正、一次改掉拖延的尝试，都是把“更新”落到日常的开始。",
    ),
    _quote(
        "quote-qie-er-bu-she",
        "锲而不舍，金石可镂。",
        "《荀子·劝学》",
        ["坚持", "毅力", "积累", "学习"],
        ["持久的投入能够把看似困难的事情逐步完成。"],
        "适合配合一个长期练习或反复改进的具体过程使用。",
        "不要只用它堆砌“坚持”；应说明坚持的对象、方法和过程。",
        "写作能力不会因为一次练习立刻成熟，但每次修改都在为更准确的表达留下痕迹。",
    ),
    _quote(
        "quote-bu-ji-kui-bu",
        "不积跬步，无以至千里；不积小流，无以成江海。",
        "《荀子·劝学》",
        ["积累", "坚持", "学习", "目标"],
        ["稳定的小积累会逐渐形成真正的能力与结果。"],
        "适合论证日常积累、基础训练或长期阅读的价值。",
        "不要把它和上一条“千里之行”简单重复；这里更强调积累本身。",
        "每天读几页、记下一个疑问，看似很小，却会在持续中构成更扎实的理解。",
    ),
    _quote(
        "quote-sheng-yu-you-huan",
        "生于忧患，死于安乐。",
        "《孟子·告子下》",
        ["挫折", "成长", "危机意识", "自省"],
        ["适度的困难能促使人反思、准备并增强解决问题的能力。"],
        "适合讨论如何面对挫折、保持警醒或从困难中成长。",
        "不要把困难浪漫化，更不能据此否认安稳生活的价值。",
        "困难本身不值得歌颂，但面对困难时学会调整和准备，能让人更有能力承担下一次挑战。",
    ),
)


CURATED_IDIOMS: tuple[WritingMaterial, ...] = (
    _idiom(
        "idiom-yu-gong-yi-shan", "愚公移山", "比喻意志坚定，不畏艰难地长期努力。", "《列子·汤问》",
        "愚公面对阻路的两座山，和家人长期挖山；故事强调的是明确目标下的持续行动。",
        ["坚持", "毅力", "目标", "行动"], ["面对长期难题，需要把坚定目标落实为持续行动。"],
        "先点明难题，再写行动为何能持续，避免只复述故事结尾。", "不要把它写成不顾条件的蛮干；故事重点不是盲目逞强。",
        "面对需要长期解决的问题，重要的不是夸大困难，而是像愚公那样把目标落实为持续行动。",
    ),
    _idiom(
        "idiom-wo-xin-chang-dan", "卧薪尝胆", "形容人忍辱负重、发愤图强。", "《史记·越王勾践世家》",
        "越王勾践在困境中积蓄力量、图谋复国；后人用“卧薪尝胆”概括其忍耐与自励。",
        ["坚持", "忍耐", "目标", "自强"], ["面对低谷时，保持目标感并积蓄力量比一时冲动更重要。"],
        "适合写经历挫折后怎样重新准备、持续行动。", "不要把它泛化为忍受一切，也不要把忍耐写成唯一正确的选择。",
        "真正的自励不是沉溺于委屈，而是在困境中重新整理目标、积蓄继续前行的力量。",
    ),
    _idiom(
        "idiom-fu-jing-qing-zui", "负荆请罪", "表示主动承认错误、真诚道歉并愿意改正。", "《史记·廉颇蔺相如列传》",
        "廉颇认识到自己对蔺相如的误解后，袒露上身、背着荆条请罪；故事强调知错能改。",
        ["责任", "宽容", "合作", "改正错误"], ["承担错误并主动修复关系，是责任感的表现。"],
        "适合论证知错能改、合作中的理解与责任。", "不要只写道歉的场面；应写清认识错误和实际改正的过程。",
        "真正的担当不只是说“对不起”，还包括承认自己的误解，并用行动修复被伤害的信任。",
    ),
    _idiom(
        "idiom-po-fu-chen-zhou", "破釜沉舟", "比喻下定决心、不留退路地全力以赴。", "《史记·项羽本纪》",
        "项羽渡河后命士卒破釜沉舟，以此激励军队专注作战；后世由此引申出决心坚定的意思。",
        ["决心", "担当", "目标", "行动"], ["在关键目标前明确选择、集中力量，能减少摇摆。"],
        "适合用于讨论关键时刻的决断，需配合具体情境。", "不要鼓励鲁莽断绝退路；现实问题仍要评估风险和准备方案。",
        "面对重要选择时，清楚的取舍能让人把有限精力集中到真正值得完成的目标上。",
    ),
    _idiom(
        "idiom-wan-bi-gui-zhao", "完璧归赵", "比喻把原物完好地归还原主。", "《史记·廉颇蔺相如列传》",
        "蔺相如在外交交涉中设法保全和氏璧并送回赵国，故事体现机智、守信与担当。",
        ["诚信", "智慧", "责任", "担当"], ["守住承诺与原则，需要智慧地处理复杂情境。"],
        "适合讨论诚信、责任与机智如何共同发挥作用。", "不要只把它当“聪明”的故事；关键还在维护国家利益和承诺。",
        "诚信并非在顺境中轻易说出的承诺，而是在复杂处境里仍愿意守住原则并寻找合适办法。",
    ),
    _idiom(
        "idiom-shou-zhu-dai-tu", "守株待兔", "比喻拘守偶然经验而不知变通。", "《韩非子·五蠹》",
        "宋国农夫偶然捡到撞死在树桩上的兔子，便放弃耕作等待下一只兔子；故事讽刺把偶然当规律。",
        ["实践探索", "思考", "创新", "学习"], ["解决问题要尊重规律，不能依赖偶然和照搬经验。"],
        "适合讨论学习方法、创新或面对变化时怎样避免机械照搬。", "不要只写“不能懒惰”；典故更核心的是误把偶然经验当成固定规律。",
        "一次偶然的成功不能替代持续的思考，面对新问题仍要观察实际情况、寻找合适方法。",
    ),
    _idiom(
        "idiom-han-dan-xue-bu", "邯郸学步", "比喻盲目模仿别人，反而失去原有本领。", "《庄子·秋水》",
        "燕国少年到邯郸学习当地步法，没有学成，还忘了自己原来的走路方式；后世借此提醒避免盲目模仿。",
        ["独立思考", "学习", "创新", "自我认识"], ["学习他人经验要理解方法，而不是丢掉自己的判断。"],
        "适合讨论学习借鉴、个性发展或如何对待流行做法。", "不要把它理解成完全不能向别人学习；问题在于盲目照搬。",
        "借鉴优秀做法需要先弄清它为什么有效，再结合自己的情况调整，而不是把别人的路径原封不动搬来。",
    ),
    _idiom(
        "idiom-jing-wei-tian-hai", "精卫填海", "比喻意志坚决，不畏艰难。", "《山海经·北山经》",
        "传说炎帝少女溺于东海，化为精卫鸟，衔木石填海；后世借此表现不屈的意志。",
        ["坚持", "勇气", "不屈", "目标"], ["面对看似艰巨的任务，坚定意志能支撑持续行动。"],
        "适合讨论不轻易放弃的精神，但应回到现实行动。", "不要把神话细节当作历史事实，也不要只用悲壮语气替代分析。",
        "面对难题时，行动也许很小，却能在一次次不放弃中让目标逐渐靠近。",
    ),
    _idiom(
        "idiom-yi-nuo-qian-jin", "一诺千金", "形容说话守信用、极有分量。", "《史记·季布栾布列传》",
        "季布以守信闻名，民间有“得黄金百斤，不如得季布一诺”的说法；后人概括为“一诺千金”。",
        ["诚信", "责任", "承诺", "品格"], ["承诺的价值在于愿意兑现并为自己的话负责。"],
        "适合讨论守信、责任或同学之间建立信任。", "不要把它写成任何承诺都必须答应；诚信也包括谨慎承诺。",
        "一句承诺之所以有分量，不在于说得多么动人，而在于答应之前认真考虑、答应之后尽力做到。",
    ),
    _idiom(
        "idiom-tui-bi-san-she", "退避三舍", "比喻主动退让，不与人争利或避免冲突。", "《左传·僖公二十八年》",
        "晋文公为报旧恩，在与楚军交战前主动退让三舍；后世用来表示克制、守信和有原则的退让。",
        ["诚信", "克制", "责任", "智慧"], ["有原则的退让不是软弱，而是对承诺和大局的负责。"],
        "适合讨论克制、守信或如何处理冲突。", "不要把它写成一味忍让；典故中的退让有明确的承诺和边界。",
        "真正的克制不是逃避问题，而是在明白原则与边界后，选择更有利于长远关系的处理方式。",
    ),
)


MATERIALS: tuple[WritingMaterial, ...] = (*BASE_MATERIALS, *CURATED_QUOTES, *CURATED_IDIOMS)


THEME_SYNONYMS: dict[str, tuple[str, ...]] = {
    "坚持": ("坚持", "不放弃", "挫折", "困难", "毅力", "努力"),
    "责任": ("责任", "担当", "负责", "使命"),
    "创新": ("创新", "科技", "发明", "探索", "求真"),
    "合作": ("合作", "团结", "协作", "集体", "分工"),
    "成长": ("成长", "青春", "改变", "长大", "勇气"),
    "文化传承": ("文化", "传承", "传统", "守护"),
    "公共意识": ("社会", "公共", "他人", "关怀", "无障碍"),
    "人与自然": ("自然", "生态", "环境", "湿地", "绿色"),
    "细节": ("细节", "具体", "描写", "画面"),
}


def all_materials() -> tuple[WritingMaterial, ...]:
    return MATERIALS


def find_material(material_id: str) -> WritingMaterial | None:
    return next((item for item in MATERIALS if item.id == material_id), None)


def search_materials(
    *,
    query: str | None = None,
    category: MaterialCategory | None = None,
    material_type: MaterialType | None = None,
    theme: str | None = None,
) -> list[WritingMaterial]:
    normalized_query = (query or "").strip().lower()
    normalized_theme = (theme or "").strip().lower()
    results: list[WritingMaterial] = []
    for item in MATERIALS:
        if category is not None and item.category != category:
            continue
        if material_type is not None and item.material_type != material_type:
            continue
        if normalized_theme and not any(normalized_theme == value.lower() for value in item.themes):
            continue
        searchable = " ".join(
            [
                item.title,
                item.category,
                item.material_type,
                item.source_kind,
                item.background,
                *item.core_facts,
                *item.themes,
                *item.supports_claims,
                item.how_to_use,
                item.common_misuse,
                item.example_use,
                item.quote_text or "",
                item.attribution or "",
                item.origin or "",
                item.idiom_meaning or "",
                item.idiom_story or "",
            ]
        ).lower()
        if normalized_query and normalized_query not in searchable:
            continue
        results.append(item)
    return results


def detected_themes(values: Iterable[str | None]) -> set[str]:
    text = " ".join(value.strip().lower() for value in values if isinstance(value, str) and value.strip())
    return {
        theme
        for theme, keywords in THEME_SYNONYMS.items()
        if theme.lower() in text or any(keyword.lower() in text for keyword in keywords)
    }
