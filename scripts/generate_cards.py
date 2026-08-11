"""
posts/shared.json의 각 글에 맞는 카드뉴스 스타일 이미지를 생성한다.

- 출력: cards/{post_id}.png (1080x1350, 4:5 비율 - Threads/인스타그램에 최적)
- 각 글의 제목(title)과 핵심 요약 3줄(highlights)은 아래 CARD_DATA에 미리 정리해둠
  (새 글을 posts/shared.json에 추가하면 CARD_DATA에도 항목을 추가해야 카드가 생성됨)
- 실행: python3 scripts/generate_cards.py
"""

import json
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

POSTS_PATH = "posts/shared.json"
OUTPUT_DIR = "cards"
CARD_SIZE = (1080, 1350)

FONT_DIR = "/usr/share/fonts/opentype/noto"
FONT_BLACK = os.path.join(FONT_DIR, "NotoSansCJK-Black.ttc")
FONT_BOLD = os.path.join(FONT_DIR, "NotoSansCJK-Bold.ttc")
FONT_MEDIUM = os.path.join(FONT_DIR, "NotoSansCJK-Medium.ttc")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoSansCJK-Regular.ttc")

# 카테고리별 배경/포인트 색상 (같은 색이 반복되지 않도록 다양하게)
CATEGORY_COLORS = {
    "교통": {"bg": (37, 99, 235), "accent": (191, 219, 254)},
    "라이프": {"bg": (124, 58, 237), "accent": (221, 214, 254)},
    "금융": {"bg": (5, 150, 105), "accent": (167, 243, 208)},
    "연금": {"bg": (234, 88, 12), "accent": (254, 215, 170)},
    "여행": {"bg": (13, 148, 136), "accent": (153, 246, 228)},
    "지원금": {"bg": (220, 38, 38), "accent": (254, 202, 202)},
    "세금": {"bg": (185, 28, 28), "accent": (254, 202, 202)},
    "자격증": {"bg": (79, 70, 229), "accent": (199, 210, 254)},
    "취업": {"bg": (67, 56, 202), "accent": (199, 210, 254)},
    "복지": {"bg": (219, 39, 119), "accent": (251, 207, 232)},
    "부동산": {"bg": (87, 83, 78), "accent": (231, 229, 228)},
    "여가": {"bg": (8, 145, 178), "accent": (165, 243, 252)},
    "안전": {"bg": (202, 138, 4), "accent": (253, 230, 138)},
}

# id -> {title, highlights, category}
CARD_DATA = {
    "info-001": {"title": "K-패스 교통비 환급", "category": "교통",
                 "highlights": ["대중교통 월 15회+ 이용 시 환급", "청년 30% · 저소득층 최대 53%", "연 최대 약 60만원 환급"]},
    "info-002": {"title": "기후동행카드 vs K-패스", "category": "교통",
                 "highlights": ["서울 내 이동 많다면 기후동행카드", "전국 이동 많다면 K-패스", "청년·저소득층은 K-패스 유리"]},
    "info-003": {"title": "무료 MBTI 검사 사이트", "category": "라이프",
                 "highlights": ["16personalities 가장 대중적", "공식 유료 검사는 전문가 해석 포함", "재미용은 무료로 충분"]},
    "info-004": {"title": "거지맵, 소득분위 지도", "category": "라이프",
                 "highlights": ["건강보험료 기반 소득 시각화", "동 단위로 세분화 확인", "상권분석 참고자료로 활용"]},
    "info-005": {"title": "경기도 극저신용대출", "category": "금융",
                 "highlights": ["최대 300만원, 연 3~4%", "저신용자 대상 소액대출", "경기신용보증재단 신청"]},
    "info-006": {"title": "국민연금 수령액·조건", "category": "연금",
                 "highlights": ["출생연도별 62~65세 수령", "최소 납부 10년 이상", "조기·연기수령으로 조정 가능"]},
    "info-007": {"title": "경복궁·창덕궁·덕수궁 주차", "category": "여행",
                 "highlights": ["경복궁은 별도 주차장 없음", "창덕궁 30분 1,000원", "주말은 오전 일찍 방문 추천"]},
    "info-008": {"title": "근로장려금 지급금액", "category": "지원금",
                 "highlights": ["단독가구 최대 165만원", "맞벌이가구 최대 330만원", "신청기간 5월 1일~31일"]},
    "info-009": {"title": "금·은 시세 확인법", "category": "금융",
                 "highlights": ["매일 변동, 국제시세 연동", "매입가는 업체마다 차이", "2~3곳 비교 추천"]},
    "info-010": {"title": "기사·산업기사 무료 기출문제", "category": "자격증",
                 "highlights": ["CBT 형식 실전 연습 가능", "회원가입 없이 이용 가능", "종목별 자료 다양"]},
    "info-011": {"title": "장애인 스포츠강좌 이용권", "category": "복지",
                 "highlights": ["연 최대 12만원 지원", "등록 장애인 소득무관 대상", "미사용분 연말 소멸 주의"]},
    "info-012": {"title": "전국 파크골프장 예약", "category": "여가",
                 "highlights": ["통합예약시스템 이용 가능", "이용일 1~2주 전 오픈", "주말 오전 빠르게 마감"]},
    "info-013": {"title": "종합소득세 신고·환급", "category": "세금",
                 "highlights": ["신고기간 5월 1일~31일", "프리랜서·임대소득자 대상", "홈택스 모두채움 간편신고"]},
    "info-014": {"title": "제주 만장굴 방문 정보", "category": "여행",
                 "highlights": ["운영시간 09:00~18:00", "입장료 성인 4,000원", "오전 9시 방문이 쾌적"]},
    "info-015": {"title": "주택연금 수령액·조건", "category": "연금",
                 "highlights": ["만 55세+, 9억 이하 주택", "집 소유 유지하며 매달 수령", "국가(주금공)가 지급 보증"]},
    "info-016": {"title": "토지거래허가구역 안내", "category": "부동산",
                 "highlights": ["일정 면적 초과시 허가 필요", "허가 없이 계약시 무효", "계약 전 국토부 시스템 확인"]},
    "info-017": {"title": "통합돌봄서비스 지원 내용", "category": "복지",
                 "highlights": ["방문요양·방문목욕 지원", "단기보호 최대 9일", "지자체별 지원범위 상이"]},
    "info-018": {"title": "항공권 특가·환불 규정", "category": "여행",
                 "highlights": ["출발 6~8주 전이 안정적", "24시간 내 취소는 대부분 전액환불", "48시간 내는 수수료 최대 70%"]},
    "info-019": {"title": "전국 마라톤 대회 일정", "category": "여가",
                 "highlights": ["코스별(10km·하프·풀) 확인", "인기 대회는 빠르게 마감", "접수 시작일 미리 체크"]},
    "info-020": {"title": "모바일 로또 구매·확인", "category": "라이프",
                 "highlights": ["동행복권 앱 본인인증 구매", "당첨은 앱·검색으로 확인", "미수령금 청구기한 통상 1년"]},
    "info-021": {"title": "에어컨 셀프 점검·청소", "category": "라이프",
                 "highlights": ["냉방 안될 때 필터부터 확인", "필터는 2주에 한 번 세척", "곰팡이는 드레인팬 원인 많음"]},
    "info-022": {"title": "건강보험 본인부담상한제", "category": "복지",
                 "highlights": ["연간 초과분 환급 대상", "상한액 81만~598만원 차등", "신청기간 매년 8~9월"]},
    "info-023": {"title": "국민취업지원제도", "category": "취업",
                 "highlights": ["Ⅰ유형 최대 300만원", "Ⅱ유형 취업활동비용 지원", "만 15~69세 구직자 대상"]},
    "info-024": {"title": "청년미래적금 가입조건", "category": "금융",
                 "highlights": ["만 19~34세, 3년 만기", "월 최대 50만원 자유적립", "정부기여금 6~12%"]},
    "info-025": {"title": "청년도약계좌→청년미래적금", "category": "금융",
                 "highlights": ["청년미래적금 먼저 개설 후 해지", "특별중도해지시 혜택 유지", "정해진 기간에만 갈아타기 가능"]},
    "info-026": {"title": "전기차 구매보조금", "category": "금융",
                 "highlights": ["국고+지자체 보조금 함께 가능", "반드시 출고 전 신청 필수", "지역별 예산 소진시 조기마감"]},
    "info-027": {"title": "청년도약계좌 지금 알아야 할 것", "category": "금융",
                 "highlights": ["2025년 12월 신규가입 종료", "3년 이상 유지시 기여금 60% 수령", "청년미래적금 갈아타기 가능"]},
    "info-028": {"title": "청년월세지원 2026 변경사항", "category": "복지",
                 "highlights": ["월 최대 20만원, 최대 24개월", "2026년부터 상시 신청 전환", "보증금 5천·월세 70만원 이하"]},
    "info-029": {"title": "청년일자리도약장려금", "category": "취업",
                 "highlights": ["채용기업 대상 인건비 지원", "최대 24개월 지원", "채용일로부터 신청기한 有"]},
    "info-030": {"title": "경기 기후보험 자동가입", "category": "복지",
                 "highlights": ["경기도민 전원 자동가입, 무료", "온열질환 진단비 15만원", "사고위로금 30만·사망 300만원"]},
    "info-031": {"title": "경기도 청년월세지원", "category": "복지",
                 "highlights": ["월 최대 20만원, 최대 24개월", "만 19~34세 무주택 청년", "보증금 5천·월세 60만원 이하"]},
    "info-032": {"title": "경기도 행복주택", "category": "부동산",
                 "highlights": ["시세 대비 60~80% 임대료", "청년·신혼부부 우선공급", "청년 최대 6년 거주"]},
    "info-033": {"title": "난임부부 시술비 지원", "category": "복지",
                 "highlights": ["체외수정(신선) 최대 110만원", "인공수정 최대 50만원", "소득기준 없이 건강보험 가입자면 OK"]},
    "info-034": {"title": "재산세 감면 대상 확인", "category": "세금",
                 "highlights": ["1세대 1주택 세율특례 가능", "장기보유·고령자 추가공제", "공시가·조례에 따라 상이"]},
    "info-035": {"title": "경기도 청년 면접수당", "category": "취업",
                 "highlights": ["면접 1회당 5만원 지원", "재직·합격 여부 무관 신청", "잡아바 어플라이 온라인 신청"]},
    "info-036": {"title": "경기청년 역량강화 기회지원", "category": "취업",
                 "highlights": ["어학·자격시험 응시료 지원", "1인 최대 30만원 실비지원", "미취업 청년 대상, 선착순"]},
    "info-037": {"title": "모바일 신분증 활용법", "category": "라이프",
                 "highlights": ["정부24·PASS·카카오·네이버 등록", "병원·관공서 실물 대체 가능", "국내선 항공기 탑승도 가능"]},
    "info-038": {"title": "서울 청년 마음건강 지원", "category": "복지",
                 "highlights": ["만 19~39세 서울 거주 청년", "무료 심리상담 최대 10회", "서울시 청년포털 온라인 신청"]},
    "info-039": {"title": "실업크레딧", "category": "연금",
                 "highlights": ["구직급여 수급자 대상", "연금보험료 75% 국가 부담", "생애 최대 12개월 지원"]},
    "info-040": {"title": "경기도 국방전직지원 직업교육", "category": "취업",
                 "highlights": ["전역 예정·전역 후 군인 대상", "교육비 전액 무료", "IT·건설 등 다양한 직종"]},
    "info-041": {"title": "국가보훈부 취업지원", "category": "취업",
                 "highlights": ["1:1 취업지원관 무료 상담", "훈련장려금·전직지원금 별도", "보훈특별고용·채용가점 우대"]},
    "info-042": {"title": "국민내일배움카드", "category": "자격증",
                 "highlights": ["기본 300만원, 최대 500만원", "지원율 45~85%", "5년간 유효, 고용24 신청"]},
    "info-043": {"title": "버팀목전세자금대출", "category": "금융",
                 "highlights": ["일반 연 1%대 후반~3%대", "청년 최대 2억원", "신혼부부 최대 3억원(수도권)"]},
    "info-044": {"title": "실내 피서 명소", "category": "여가",
                 "highlights": ["국립중앙박물관 무료입장", "도서관 와이파이·콘센트·냉방", "영화관 낮시간 할인 요금"]},
    "info-045": {"title": "열대야 없는 여행지", "category": "여행",
                 "highlights": ["고지대·계곡은 밤 기온 낮음", "평창·인제·봉화 등이 대표적", "성수기 숙박비 상승 주의"]},
    "info-046": {"title": "열사병 대처법", "category": "안전",
                 "highlights": ["즉시 서늘한 곳으로 이동", "목·겨드랑이·사타구니 냉각", "119 즉시 신고가 우선"]},
    "info-047": {"title": "운전면허 갱신(적성검사)", "category": "라이프",
                 "highlights": ["1종은 10년마다 갱신", "2종은 65세 이후 5년마다", "미갱신시 면허 효력정지"]},
    "info-048": {"title": "장기전세주택(시프트)", "category": "부동산",
                 "highlights": ["시세보다 저렴한 임대료", "최장 20년 거주 가능", "무주택자 청약시 우대"]},
}


def get_font(path, size):
    return ImageFont.truetype(path, size)


def wrap_text(draw, text, font, max_width):
    """주어진 폭에 맞춰 텍스트를 여러 줄로 감싼다 (한글 대응, 글자 단위로 자름)."""
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def draw_rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def make_card(post_id, data, output_path):
    colors = CATEGORY_COLORS.get(data["category"], {"bg": (55, 65, 81), "accent": (229, 231, 235)})
    bg_color = colors["bg"]
    accent_color = colors["accent"]

    img = Image.new("RGB", CARD_SIZE, bg_color)
    draw = ImageDraw.Draw(img)

    # 살짝 어두운 하단 그라데이션 느낌을 주기 위한 오버레이 사각형 (단순화된 그라데이션)
    overlay_height = 260
    for i in range(overlay_height):
        alpha_ratio = i / overlay_height
        shade = tuple(max(0, int(c * (1 - 0.35 * alpha_ratio))) for c in bg_color)
        y = CARD_SIZE[1] - overlay_height + i
        draw.line([(0, y), (CARD_SIZE[0], y)], fill=shade)

    margin = 80

    # 카테고리 배지
    tag_font = get_font(FONT_BOLD, 34)
    tag_text = data["category"]
    tag_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = tag_bbox[3] - tag_bbox[1]
    tag_pad_x, tag_pad_y = 34, 18
    tag_box = [margin, margin, margin + tag_w + tag_pad_x * 2, margin + tag_h + tag_pad_y * 2]
    draw_rounded_rect(draw, tag_box, radius=999, fill=(255, 255, 255))
    draw.text((tag_box[0] + tag_pad_x, tag_box[1] + tag_pad_y - 4), tag_text, font=tag_font, fill=bg_color)

    # 제목
    title_font = get_font(FONT_BLACK, 78)
    title_top = tag_box[3] + 70
    title_lines = wrap_text(draw, data["title"], title_font, CARD_SIZE[0] - margin * 2)
    y = title_top
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=(255, 255, 255))
        line_bbox = draw.textbbox((0, 0), line, font=title_font)
        y += (line_bbox[3] - line_bbox[1]) + 22

    # 흰색 카드 패널 (하이라이트 영역)
    panel_top = y + 50
    panel_bottom = CARD_SIZE[1] - 170
    panel_box = [margin, panel_top, CARD_SIZE[0] - margin, panel_bottom]
    draw_rounded_rect(draw, panel_box, radius=36, fill=(255, 255, 255))

    # 하이라이트 3줄
    hi_font = get_font(FONT_MEDIUM, 40)
    bullet_font = get_font(FONT_BOLD, 40)
    inner_margin = 56
    text_max_width = (panel_box[2] - panel_box[0]) - inner_margin * 2 - 60

    highlights = data["highlights"]
    n = len(highlights)
    panel_height = panel_bottom - panel_top
    row_height = panel_height / n

    for idx, h in enumerate(highlights):
        row_top = panel_top + row_height * idx
        text_y = row_top + row_height / 2

        # 불릿 원
        circle_r = 10
        circle_cy = text_y
        circle_cx = panel_box[0] + inner_margin + circle_r
        draw.ellipse(
            [circle_cx - circle_r, circle_cy - circle_r, circle_cx + circle_r, circle_cy + circle_r],
            fill=bg_color,
        )

        lines = wrap_text(draw, h, hi_font, text_max_width)
        text_x = circle_cx + circle_r + 26
        line_bbox = draw.textbbox((0, 0), "가", font=hi_font)
        line_h = (line_bbox[3] - line_bbox[1]) + 10
        total_text_h = line_h * len(lines)
        ty = text_y - total_text_h / 2
        for line in lines:
            draw.text((text_x, ty), line, font=hi_font, fill=(31, 41, 55))
            ty += line_h

        if idx < n - 1:
            sep_y = panel_top + row_height * (idx + 1)
            draw.line(
                [(panel_box[0] + inner_margin, sep_y), (panel_box[2] - inner_margin, sep_y)],
                fill=(229, 231, 235),
                width=2,
            )

    # 하단 브랜드 표시
    footer_font = get_font(FONT_BOLD, 34)
    footer_text = "정보 카드 · 지원금 안내"
    footer_y = CARD_SIZE[1] - 110
    draw.text((margin, footer_y), footer_text, font=footer_font, fill=(255, 255, 255))

    img.save(output_path, "PNG")


def main():
    posts = json.load(open(POSTS_PATH, encoding="utf-8"))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    missing = []
    for post in posts:
        pid = post["id"]
        data = CARD_DATA.get(pid)
        if not data:
            missing.append(pid)
            continue
        output_path = os.path.join(OUTPUT_DIR, f"{pid}.png")
        make_card(pid, data, output_path)
        print(f"생성 완료: {output_path}")

    if missing:
        print(f"\n⚠️ CARD_DATA에 없어서 카드를 만들지 못한 글: {missing}")
        print("scripts/generate_cards.py의 CARD_DATA에 title/highlights/category를 추가해주세요.")


if __name__ == "__main__":
    main()
