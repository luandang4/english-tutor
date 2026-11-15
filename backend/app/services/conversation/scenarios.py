"""Preset conversation scenarios: goal, roles and useful phrases the learner can prepare before speaking.

Phrases come in two sets: `basic` for A1–A2 and `advanced` for B1+. Each phrase is (English, Vietnamese).
"""

from dataclasses import dataclass

Phrase = tuple[str, str]

GROUPS = ("Đời sống", "Du lịch", "Công việc", "Luyện thi")
BASIC_LEVELS = frozenset({"A1", "A2"})


@dataclass(frozen=True)
class Scenario:
    label: str  # Vietnamese, shown in the UI
    group: str  # one of GROUPS
    goal_vi: str  # what the learner can do after this lesson
    emma_role: str  # English, for the tutor prompt (and shown translated in the UI)
    learner_role: str
    roles_vi: tuple[str, str]  # (Emma's role, the learner's role) shown in the UI
    ai: str  # what Emma should do in this lesson (English, AI-facing)
    basic: tuple[Phrase, ...]
    advanced: tuple[Phrase, ...]

    def phrases(self, level: str) -> tuple[Phrase, ...]:
        return self.basic if level in BASIC_LEVELS else self.advanced


SCENARIOS: dict[str, Scenario] = {
    # --- Đời sống ---------------------------------------------------------------------------------
    "free_talk": Scenario(
        label="Nói chuyện tự do",
        group="Đời sống",
        goal_vi="Kể được về bản thân, sở thích và một ngày của bạn.",
        emma_role="a friendly English tutor",
        learner_role="yourself",
        roles_vi=("Giáo viên tiếng Anh thân thiện", "Chính bạn"),
        ai="Free conversation. Find out what the learner likes and talk about it.",
        basic=(
            ("In my free time, I usually …", "Lúc rảnh, tôi thường …"),
            ("I really like … because …", "Tôi rất thích … vì …"),
            ("I'm not sure, but I think …", "Tôi không chắc, nhưng tôi nghĩ …"),
            ("How about you?", "Còn bạn thì sao?"),
            ("Can you say that again, please?", "Bạn nói lại được không?"),
        ),
        advanced=(
            ("I've been really into … lately.", "Dạo này tôi rất mê …"),
            ("What I enjoy most about it is …", "Điều tôi thích nhất ở nó là …"),
            ("To be honest, …", "Thật lòng mà nói, …"),
            ("That reminds me of …", "Điều đó làm tôi nhớ tới …"),
            ("What about you? Have you ever …?", "Còn bạn? Bạn đã bao giờ … chưa?"),
        ),
    ),
    "coffee_shop": Scenario(
        label="Gọi đồ ở quán cà phê",
        group="Đời sống",
        goal_vi="Gọi được đồ uống, đồ ăn, hỏi giá và thanh toán.",
        emma_role="a barista",
        learner_role="a customer",
        roles_vi=("Nhân viên pha chế", "Khách gọi đồ"),
        ai="Role-play: you are a barista, the learner orders drinks and snacks.",
        basic=(
            ("Can I have a …, please?", "Cho tôi một …"),
            ("How much is it?", "Bao nhiêu tiền?"),
            ("Small, please. / Large, please.", "Cỡ nhỏ / cỡ lớn."),
            ("For here, please. / To go, please.", "Uống ở đây / mang đi."),
            ("Can I pay by card?", "Tôi trả bằng thẻ được không?"),
        ),
        advanced=(
            ("Could I get a … with oat milk?", "Cho tôi một … với sữa yến mạch."),
            ("What would you recommend?", "Bạn gợi ý món nào?"),
            ("Is there any sugar in it?", "Món này có đường không?"),
            ("I'll have it to go, thanks.", "Tôi mang đi nhé."),
            ("Could I get the receipt, please?", "Cho tôi xin hoá đơn."),
        ),
    ),
    "restaurant": Scenario(
        label="Gọi món ở nhà hàng",
        group="Đời sống",
        goal_vi="Đặt bàn, gọi món, hỏi về món ăn và xin thanh toán.",
        emma_role="a waiter in a restaurant",
        learner_role="a guest having dinner",
        roles_vi=("Phục vụ nhà hàng", "Khách ăn tối"),
        ai="Role-play: you are a waiter; the learner asks for a table, orders food and pays.",
        basic=(
            ("A table for two, please.", "Cho một bàn hai người."),
            ("Can I see the menu, please?", "Cho tôi xem thực đơn."),
            ("I'd like the chicken, please.", "Tôi muốn món gà."),
            ("Is it spicy?", "Món này có cay không?"),
            ("The bill, please.", "Cho tôi thanh toán."),
        ),
        advanced=(
            ("Do you have any vegetarian options?", "Nhà hàng có món chay không?"),
            ("What's in this dish?", "Món này gồm những gì?"),
            ("I'm allergic to peanuts.", "Tôi bị dị ứng đậu phộng."),
            ("Could we have some more water, please?", "Cho chúng tôi thêm nước nhé."),
            ("Could we split the bill?", "Chúng tôi trả riêng được không?"),
        ),
    ),
    "shopping": Scenario(
        label="Mua sắm quần áo",
        group="Đời sống",
        goal_vi="Hỏi cỡ, màu, thử đồ, hỏi giá và đổi trả.",
        emma_role="a shop assistant in a clothes shop",
        learner_role="a customer",
        roles_vi=("Nhân viên bán quần áo", "Khách mua đồ"),
        ai="Role-play: you are a shop assistant; the learner looks for clothes, tries them on and pays.",
        basic=(
            ("I'm looking for a …", "Tôi đang tìm một …"),
            ("Do you have this in medium?", "Cái này có cỡ M không?"),
            ("Can I try it on?", "Tôi thử được không?"),
            ("It's too big. / It's too small.", "Nó rộng quá / chật quá."),
            ("I'll take it.", "Tôi lấy cái này."),
        ),
        advanced=(
            ("Do you have this in a different colour?", "Cái này có màu khác không?"),
            ("Where are the fitting rooms?", "Phòng thử đồ ở đâu?"),
            ("It doesn't quite fit.", "Nó không vừa lắm."),
            ("Is this on sale?", "Cái này có giảm giá không?"),
            ("Can I return it if it doesn't fit?", "Không vừa thì tôi đổi trả được không?"),
        ),
    ),
    "doctor": Scenario(
        label="Đi khám bác sĩ",
        group="Đời sống",
        goal_vi="Mô tả triệu chứng, trả lời câu hỏi của bác sĩ và hiểu lời dặn.",
        emma_role="a doctor",
        learner_role="a patient",
        roles_vi=("Bác sĩ", "Bệnh nhân"),
        ai="Role-play: you are a doctor; the learner describes symptoms.",
        basic=(
            ("I have a headache.", "Tôi bị đau đầu."),
            ("I feel sick.", "Tôi thấy mệt / buồn nôn."),
            ("It started two days ago.", "Nó bắt đầu từ hai ngày trước."),
            ("It hurts here.", "Tôi đau ở đây."),
            ("How often do I take it?", "Tôi uống thuốc bao lâu một lần?"),
        ),
        advanced=(
            ("I've had a sore throat since Monday.", "Tôi bị đau họng từ thứ Hai."),
            ("I keep coughing at night.", "Tôi cứ ho suốt vào ban đêm."),
            ("It gets worse when I …", "Nó nặng hơn khi tôi …"),
            ("Are there any side effects?", "Thuốc có tác dụng phụ không?"),
            ("Should I come back for a check-up?", "Tôi có cần tái khám không?"),
        ),
    ),
    # --- Du lịch -----------------------------------------------------------------------------------
    "travel": Scenario(
        label="Nhận phòng khách sạn",
        group="Du lịch",
        goal_vi="Nhận phòng, hỏi về tiện ích và xin gợi ý đi chơi trong thành phố.",
        emma_role="a hotel receptionist",
        learner_role="a guest checking in",
        roles_vi=("Lễ tân khách sạn", "Khách nhận phòng"),
        ai="Role-play: you are a hotel receptionist; the learner checks in and asks about the city.",
        basic=(
            ("I have a reservation.", "Tôi đã đặt phòng."),
            ("My name is …", "Tên tôi là …"),
            ("What time is breakfast?", "Bữa sáng lúc mấy giờ?"),
            ("What's the Wi-Fi password?", "Mật khẩu Wi-Fi là gì?"),
            ("Where is a good place to eat?", "Ăn ở đâu thì ngon?"),
        ),
        advanced=(
            ("I booked a double room for three nights.", "Tôi đã đặt phòng đôi ba đêm."),
            ("Is breakfast included?", "Có bao gồm bữa sáng không?"),
            ("Could I get a late check-out?", "Tôi trả phòng muộn được không?"),
            ("What would you recommend seeing nearby?", "Gần đây có gì đáng xem?"),
            ("Could you call a taxi for me?", "Bạn gọi giúp tôi một chiếc taxi được không?"),
        ),
    ),
    "airport": Scenario(
        label="Làm thủ tục ở sân bay",
        group="Du lịch",
        goal_vi="Làm thủ tục, gửi hành lý, hỏi cửa ra máy bay và giờ lên máy bay.",
        emma_role="an airline check-in agent",
        learner_role="a passenger",
        roles_vi=("Nhân viên làm thủ tục", "Hành khách"),
        ai=(
            "Role-play: you are an airline check-in agent; the learner checks in, drops a bag and asks about "
            "the flight."
        ),
        basic=(
            ("Here is my passport.", "Đây là hộ chiếu của tôi."),
            ("I have one bag.", "Tôi có một túi hành lý."),
            ("Can I have a window seat?", "Cho tôi ghế cạnh cửa sổ."),
            ("Which gate is it?", "Cửa nào ạ?"),
            ("What time is boarding?", "Mấy giờ lên máy bay?"),
        ),
        advanced=(
            ("I'd like to check in for my flight to …", "Tôi muốn làm thủ tục chuyến bay đi …"),
            ("Is my bag over the weight limit?", "Hành lý của tôi có quá cân không?"),
            ("Could I have an aisle seat, please?", "Cho tôi ghế cạnh lối đi."),
            ("Is the flight on time?", "Chuyến bay có đúng giờ không?"),
            ("Where do I go through security?", "Tôi qua cửa an ninh ở đâu?"),
        ),
    ),
    "directions": Scenario(
        label="Hỏi đường",
        group="Du lịch",
        goal_vi="Hỏi đường, hiểu chỉ dẫn và hỏi lại khi chưa rõ.",
        emma_role="a local person on the street",
        learner_role="a tourist who is lost",
        roles_vi=("Người dân địa phương", "Du khách bị lạc"),
        ai="Role-play: you are a local; the learner is a tourist asking for directions. Give clear directions.",
        basic=(
            ("Excuse me, where is the …?", "Xin lỗi, … ở đâu ạ?"),
            ("Is it far?", "Có xa không?"),
            ("Go straight, then turn left.", "Đi thẳng, rồi rẽ trái."),
            ("Can I walk there?", "Tôi đi bộ tới được không?"),
            ("Thank you for your help.", "Cảm ơn bạn đã giúp."),
        ),
        advanced=(
            ("Could you tell me how to get to …?", "Bạn chỉ giúp tôi đường tới … được không?"),
            ("How long does it take on foot?", "Đi bộ mất bao lâu?"),
            ("Is there a bus that goes there?", "Có xe buýt nào đi tới đó không?"),
            ("Sorry, did you say the second left?", "Xin lỗi, bạn nói rẽ trái ở ngã thứ hai à?"),
            ("Is it on the left or the right?", "Nó ở bên trái hay bên phải?"),
        ),
    ),
    # --- Công việc ---------------------------------------------------------------------------------
    "job_interview": Scenario(
        label="Phỏng vấn xin việc",
        group="Công việc",
        goal_vi="Giới thiệu bản thân, kể kinh nghiệm và trả lời câu hỏi phỏng vấn thường gặp.",
        emma_role="an interviewer for a software engineer job",
        learner_role="a job candidate",
        roles_vi=("Nhà tuyển dụng", "Ứng viên"),
        ai="Role-play: you are an interviewer for a software engineer job.",
        basic=(
            ("My name is … and I'm a …", "Tôi tên là … và tôi là …"),
            ("I have … years of experience.", "Tôi có … năm kinh nghiệm."),
            ("I'm good at …", "Tôi giỏi về …"),
            ("I want this job because …", "Tôi muốn công việc này vì …"),
            ("Do you have any questions for me?", "Anh / chị có câu hỏi nào cho tôi không?"),
        ),
        advanced=(
            ("I've been working as a … for … years.", "Tôi làm … được … năm rồi."),
            ("One of my strengths is …", "Một điểm mạnh của tôi là …"),
            ("In my previous role, I was responsible for …", "Ở vị trí trước, tôi phụ trách …"),
            ("A challenge I faced was … and I handled it by …", "Một khó khăn tôi gặp là … và tôi xử lý bằng cách …"),
            ("Could you tell me more about the team?", "Anh / chị kể thêm về đội được không?"),
        ),
    ),
    "small_talk": Scenario(
        label="Làm quen đồng nghiệp",
        group="Công việc",
        goal_vi="Chào hỏi, làm quen và nói chuyện xã giao với đồng nghiệp mới.",
        emma_role="a new colleague at the office",
        learner_role="yourself, at work",
        roles_vi=("Đồng nghiệp mới", "Chính bạn ở công ty"),
        ai="Small talk with a new colleague at the office.",
        basic=(
            ("Nice to meet you.", "Rất vui được gặp bạn."),
            ("Which team are you in?", "Bạn ở nhóm nào?"),
            ("How long have you worked here?", "Bạn làm ở đây bao lâu rồi?"),
            ("Do you want to have lunch together?", "Bạn muốn ăn trưa cùng không?"),
            ("Have a nice weekend!", "Cuối tuần vui vẻ nhé!"),
        ),
        advanced=(
            ("I don't think we've met. I'm …", "Hình như mình chưa gặp nhau. Mình là …"),
            ("What do you do here?", "Bạn làm mảng gì ở đây?"),
            ("How's your week going?", "Tuần này của bạn thế nào?"),
            ("Any plans for the weekend?", "Cuối tuần có kế hoạch gì không?"),
            ("Let's grab a coffee sometime.", "Hôm nào mình đi cà phê nhé."),
        ),
    ),
    "team_meeting": Scenario(
        label="Họp nhóm báo cáo tiến độ",
        group="Công việc",
        goal_vi="Báo cáo việc đã làm, nêu vấn đề và đề xuất bước tiếp theo trong cuộc họp.",
        emma_role="a team lead running a short weekly meeting",
        learner_role="a team member giving an update",
        roles_vi=("Trưởng nhóm chủ trì họp", "Thành viên báo cáo"),
        ai="Role-play: you lead a short team meeting; ask the learner for a progress update, blockers and next steps.",
        basic=(
            ("This week, I finished …", "Tuần này tôi đã xong …"),
            ("I'm working on …", "Tôi đang làm …"),
            ("I have a problem with …", "Tôi gặp vấn đề với …"),
            ("I need help with …", "Tôi cần giúp về …"),
            ("Next week, I will …", "Tuần sau tôi sẽ …"),
        ),
        advanced=(
            ("Quick update from my side: …", "Cập nhật nhanh từ phía tôi: …"),
            ("We're on track to finish by …", "Chúng tôi đang đúng tiến độ để xong trước …"),
            ("The main blocker right now is …", "Vướng mắc chính lúc này là …"),
            ("I'd suggest that we …", "Tôi đề xuất chúng ta …"),
            ("Could you clarify what you mean by …?", "Anh / chị nói rõ hơn ý … được không?"),
        ),
    ),
    # --- Luyện thi ---------------------------------------------------------------------------------
    "ielts_part1": Scenario(
        label="IELTS Speaking Part 1",
        group="Luyện thi",
        goal_vi="Trả lời câu hỏi ngắn về bản thân bằng 2–3 câu có lý do và ví dụ.",
        emma_role="an IELTS speaking examiner",
        learner_role="an IELTS candidate",
        roles_vi=("Giám khảo IELTS", "Thí sinh"),
        ai=(
            "IELTS Speaking Part 1 practice: you are the examiner. Ask short questions on familiar topics (home, "
            "work or study, hobbies, daily routine), one at a time. Coach the learner to answer in 2-3 sentences "
            "with a reason or example."
        ),
        basic=(
            ("I live in … with my family.", "Tôi sống ở … cùng gia đình."),
            ("I'm a student. / I work as a …", "Tôi là sinh viên. / Tôi làm …"),
            ("I like … because …", "Tôi thích … vì …"),
            ("For example, …", "Ví dụ, …"),
            ("I usually … at the weekend.", "Cuối tuần tôi thường …"),
        ),
        advanced=(
            ("Well, to be honest, …", "À, thật lòng mà nói, …"),
            ("The main reason is that …", "Lý do chính là …"),
            ("For instance, last week I …", "Ví dụ, tuần trước tôi …"),
            ("It depends on …", "Còn tuỳ vào …"),
            ("I used to …, but these days I …", "Trước đây tôi hay …, nhưng giờ tôi …"),
        ),
    ),
    "ielts_part2": Scenario(
        label="IELTS Speaking Part 2",
        group="Luyện thi",
        goal_vi="Nói liên tục 1–2 phút theo thẻ đề, có mở bài, ý chính và kết.",
        emma_role="an IELTS speaking examiner",
        learner_role="an IELTS candidate",
        roles_vi=("Giám khảo IELTS", "Thí sinh"),
        ai=(
            "IELTS Speaking Part 2 practice: you are the examiner. Give a cue card (a topic plus 3-4 points to "
            "cover), give the learner a moment to prepare, then let them talk for 1-2 minutes without "
            "interrupting. Afterwards ask one or two rounding-off questions and give short feedback on structure."
        ),
        basic=(
            ("I'm going to talk about …", "Tôi sẽ nói về …"),
            ("First, …", "Đầu tiên, …"),
            ("After that, …", "Sau đó, …"),
            ("I liked it because …", "Tôi thích nó vì …"),
            ("That's why it's special to me.", "Đó là lý do nó đặc biệt với tôi."),
        ),
        advanced=(
            ("I'd like to talk about …", "Tôi muốn nói về …"),
            ("What made it memorable was …", "Điều làm nó đáng nhớ là …"),
            ("As far as I remember, …", "Theo như tôi nhớ, …"),
            ("Looking back, I realise …", "Nhìn lại, tôi nhận ra …"),
            ("All in all, …", "Tóm lại, …"),
        ),
    ),
    "ielts_part3": Scenario(
        label="IELTS Speaking Part 3",
        group="Luyện thi",
        goal_vi="Thảo luận vấn đề xã hội: nêu quan điểm, so sánh, đưa lý do và ví dụ.",
        emma_role="an IELTS speaking examiner",
        learner_role="an IELTS candidate",
        roles_vi=("Giám khảo IELTS", "Thí sinh"),
        ai=(
            "IELTS Speaking Part 3 practice: you are the examiner. Ask abstract discussion questions on a social "
            "topic (technology, education, environment, work). Push the learner to give opinions, compare, "
            "speculate and support ideas with reasons and examples."
        ),
        basic=(
            ("I think … because …", "Tôi nghĩ … vì …"),
            ("In my country, …", "Ở nước tôi, …"),
            ("Some people think …, but …", "Một số người nghĩ …, nhưng …"),
            ("It is good because …, but it is bad because …", "Nó tốt vì …, nhưng không tốt vì …"),
            ("In the future, maybe …", "Trong tương lai, có lẽ …"),
        ),
        advanced=(
            ("From my point of view, …", "Theo quan điểm của tôi, …"),
            ("On the one hand, … On the other hand, …", "Một mặt, … Mặt khác, …"),
            ("A good example of this is …", "Một ví dụ điển hình là …"),
            ("Compared to the past, …", "So với trước đây, …"),
            ("It's likely that in the future …", "Nhiều khả năng trong tương lai …"),
        ),
    ),
}


def scenario_label(key: str) -> str:
    return SCENARIOS[key].label if key in SCENARIOS else key


def lesson_text(key: str, level: str) -> str:
    """AI-facing lesson description: roles, task, goal and the phrases the learner prepared."""
    s = SCENARIOS[key]
    phrases = "; ".join(en for en, _ in s.phrases(level))
    return (
        f"{s.ai} You play {s.emma_role}; the learner plays {s.learner_role}. "
        f"Lesson goal (in Vietnamese for the learner): {s.goal_vi} "
        f"The learner saw these useful phrases before starting; encourage them to use them naturally: {phrases}."
    )
