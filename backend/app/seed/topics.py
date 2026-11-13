"""Preset topics. Upserted by slug on startup — edit this list to add/change topics."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Skill
from app.models.topic import Topic

# (slug, icon, title, title_vi, description_vi, focus-for-AI)
VOCABULARY = [
    (
        "daily-routine",
        "☀️",
        "Daily Routine",
        "Thói quen hằng ngày",
        "Hoạt động trong ngày, giờ giấc, việc nhà.",
        "everyday actions, time expressions, household chores",
    ),
    (
        "food-cooking",
        "🍜",
        "Food & Cooking",
        "Ẩm thực & nấu ăn",
        "Món ăn, hương vị, cách chế biến, gọi món.",
        "dishes, tastes, cooking verbs, ordering food",
    ),
    (
        "travel",
        "✈️",
        "Travel",
        "Du lịch",
        "Sân bay, khách sạn, hỏi đường, tham quan.",
        "airport, accommodation, directions, sightseeing",
    ),
    (
        "work-office",
        "💼",
        "Work & Office",
        "Công việc & văn phòng",
        "Họp hành, email, deadline, đồng nghiệp.",
        "meetings, deadlines, office tasks, workplace collocations",
    ),
    (
        "technology",
        "💻",
        "Technology",
        "Công nghệ",
        "Thiết bị, phần mềm, Internet, AI.",
        "devices, software, internet, AI, tech verbs like install/update/crash",
    ),
    (
        "health",
        "🩺",
        "Health & Body",
        "Sức khỏe & cơ thể",
        "Triệu chứng, đi khám, lối sống lành mạnh.",
        "symptoms, doctor visits, fitness, healthy habits",
    ),
    (
        "shopping-money",
        "🛍️",
        "Shopping & Money",
        "Mua sắm & tiền bạc",
        "Giá cả, thanh toán, đổi trả, tiết kiệm.",
        "prices, payment, refunds, budgeting",
    ),
    (
        "feelings",
        "💜",
        "Feelings & Personality",
        "Cảm xúc & tính cách",
        "Mô tả cảm xúc, tâm trạng, tính cách.",
        "emotions, moods, personality adjectives",
    ),
    (
        "environment",
        "🌿",
        "Environment",
        "Môi trường",
        "Biến đổi khí hậu, ô nhiễm, tái chế.",
        "climate change, pollution, recycling, sustainability",
    ),
    (
        "phrasal-verbs",
        "🔗",
        "Common Phrasal Verbs",
        "Cụm động từ thông dụng",
        "Phrasal verbs hay gặp trong giao tiếp.",
        "high-frequency phrasal verbs in daily conversation",
    ),
]

GRAMMAR = [
    (
        "present-simple-continuous",
        "⏱️",
        "Present Simple vs Present Continuous",
        "Hiện tại đơn & hiện tại tiếp diễn",
        "Thói quen hay hành động đang diễn ra?",
        "form, use, stative verbs, signal words",
    ),
    (
        "past-simple-present-perfect",
        "📅",
        "Past Simple vs Present Perfect",
        "Quá khứ đơn & hiện tại hoàn thành",
        "Khi nào dùng 'did' và khi nào dùng 'have done'.",
        "finished vs unfinished time, ever/never/just/already/yet, for/since",
    ),
    (
        "future-forms",
        "🔮",
        "Future Forms",
        "Các cách nói tương lai",
        "will, be going to, hiện tại tiếp diễn cho tương lai.",
        "will vs be going to vs present continuous for arrangements",
    ),
    (
        "articles",
        "🅰️",
        "Articles: a / an / the / ∅",
        "Mạo từ a / an / the",
        "Lỗi rất phổ biến của người Việt.",
        "a/an/the/zero article, first vs second mention, generic nouns",
    ),
    (
        "countable-quantifiers",
        "🔢",
        "Countable & Uncountable Nouns",
        "Danh từ đếm được & không đếm được",
        "much/many, a few/a little, some/any.",
        "countable vs uncountable, quantifiers",
    ),
    (
        "comparatives",
        "📈",
        "Comparatives & Superlatives",
        "So sánh hơn & so sánh nhất",
        "Cách so sánh tính từ, trạng từ.",
        "comparative/superlative forms, as...as, irregulars",
    ),
    (
        "modals",
        "🧭",
        "Modal Verbs",
        "Động từ khuyết thiếu",
        "can, could, must, have to, should, might...",
        "ability, permission, obligation, advice, possibility",
    ),
    (
        "conditionals",
        "🔀",
        "Conditionals (0, 1, 2, 3)",
        "Câu điều kiện loại 0–3",
        "If-clauses và cách dùng thực tế.",
        "zero, first, second, third conditionals; unless",
    ),
    (
        "passive-voice",
        "🔁",
        "Passive Voice",
        "Câu bị động",
        "Khi nào và cách chuyển sang bị động.",
        "passive forms across tenses, by-agent, when to use",
    ),
    (
        "relative-clauses",
        "🧩",
        "Relative Clauses",
        "Mệnh đề quan hệ",
        "who, which, that, where, whose.",
        "defining vs non-defining relative clauses, omission of pronoun",
    ),
    (
        "reported-speech",
        "💬",
        "Reported Speech",
        "Câu tường thuật",
        "Thuật lại lời nói, câu hỏi, mệnh lệnh.",
        "backshift, reporting verbs, reported questions and commands",
    ),
    (
        "prepositions",
        "📍",
        "Prepositions of Time & Place",
        "Giới từ chỉ thời gian & nơi chốn",
        "in / on / at và hơn thế.",
        "in/on/at for time and place, common fixed prepositional phrases",
    ),
]

WRITING = [
    (
        "personal-email",
        "✉️",
        "Informal Email",
        "Email thân mật",
        "Viết thư cho bạn bè, người thân.",
        "informal email to a friend: news, invitation or advice",
    ),
    (
        "formal-email",
        "📨",
        "Formal Email",
        "Email trang trọng",
        "Thư xin việc, khiếu nại, hỏi thông tin.",
        "formal email: complaint, enquiry or application",
    ),
    (
        "opinion-essay",
        "🗣️",
        "Opinion Essay",
        "Bài luận nêu quan điểm",
        "Trình bày và bảo vệ quan điểm.",
        "opinion essay on a modern social topic with reasons and examples",
    ),
    (
        "describe-experience",
        "🌅",
        "Describe an Experience",
        "Kể lại một trải nghiệm",
        "Kể chuyện bằng thì quá khứ.",
        "narrative about a memorable experience using past tenses",
    ),
    (
        "review",
        "⭐",
        "Review",
        "Bài đánh giá",
        "Đánh giá phim, sách, nhà hàng, sản phẩm.",
        "review of a film, book, restaurant or app with recommendation",
    ),
    (
        "work-report",
        "📊",
        "Work Update / Report",
        "Báo cáo công việc",
        "Cập nhật tiến độ, đề xuất giải pháp.",
        "short workplace report or status update with a recommendation",
    ),
]


async def seed_topics(session: AsyncSession) -> None:
    existing = {t.slug: t for t in (await session.scalars(select(Topic))).all()}
    for skill, rows in ((Skill.VOCABULARY, VOCABULARY), (Skill.GRAMMAR, GRAMMAR), (Skill.WRITING, WRITING)):
        for order, (slug, icon, title, title_vi, desc, focus) in enumerate(rows):
            t = existing.get(slug) or Topic(slug=slug)
            t.skill, t.icon, t.title, t.title_vi = skill, icon, title, title_vi
            t.description_vi, t.focus, t.sort_order = desc, focus, order
            session.add(t)
    await session.commit()
