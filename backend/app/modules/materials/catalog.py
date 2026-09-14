from __future__ import annotations

from collections.abc import Iterable

from app.schemas.material import MaterialCategory, MaterialReference, WritingMaterial


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
) -> WritingMaterial:
    return WritingMaterial(
        id=material_id,
        title=title,
        category=category,
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
    )


# Each item is intentionally a short original summary of well-established public facts
# or an explicitly labelled everyday observation. There are no quotations, fabricated
# dialogue, or precise figures that students could mistakenly repeat as facts.
MATERIALS: tuple[WritingMaterial, ...] = (
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
    theme: str | None = None,
) -> list[WritingMaterial]:
    normalized_query = (query or "").strip().lower()
    normalized_theme = (theme or "").strip().lower()
    results: list[WritingMaterial] = []
    for item in MATERIALS:
        if category is not None and item.category != category:
            continue
        if normalized_theme and not any(normalized_theme == value.lower() for value in item.themes):
            continue
        searchable = " ".join(
            [
                item.title,
                item.category,
                item.background,
                *item.core_facts,
                *item.themes,
                *item.supports_claims,
                item.how_to_use,
                item.common_misuse,
                item.example_use,
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
