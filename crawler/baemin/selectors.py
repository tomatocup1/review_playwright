"""
배민 CSS 셀렉터 정의
웹사이트 구조 변경에 대응하기 쉽도록 한 곳에서 관리
"""

# 로그인 페이지
LOGIN_SELECTORS = {
    'id_input': 'input[name="id"]',
    'password_input': 'input[name="password"]',
    'login_button': 'button[type="submit"]',
    'error_alert': 'p[role="alert"]'
}

# 홈페이지 팝업
HOMEPAGE_POPUP_SELECTORS = {
    'close_nday': '#btn-close-nday',
    'close_button': 'button[aria-label="닫기"]',
    'overlay_close': 'div.button-overlay.css-fowwyy'
}

# 리뷰 페이지
REVIEW_PAGE_SELECTORS = {
    # 탭
    'uncommented_tab': [
        'button#no-comment[role="tab"]',
        'button[role="tab"]:has-text("미답변")',
        'button[contains(@class, "Tab_b_qmgb_sx92a1t")]:has-text("미답변")'
    ],
    
    # 리뷰 카드
    'review_card': [
        'div[class*="ReviewContent-module"]',
        'div.Container_c_qbca_1utdzds5.ReviewContent-module__Ksg4',
        'div[data-atelier-component="Container"]'
    ],
    
    # 리뷰 요소
    'author': 'span[class*="Typography_b_b8ew_1bisyd47"]',
    'rating_star': 'path[fill="#FFC600"]',
    'review_text': 'span[class*="Typography_b_b8ew_1bisyd49"]',
    'order_menu': 'span[class*="Badge_b_b8ew_19agxism"]',
    'delivery_review': 'div[class*="ReviewDelivery-module"] span[class*="Badge"]',
    
    # 날짜
    'date_element': [
        'span[class*="Typography_b_qmgb_1bisyd4b"]',
        'span:has-text("오늘")',
        'span:has-text("어제")',
        'span:has-text("그제")',
        'span:has-text("일 전")'
    ],
    
    # 댓글
    'comment_button': [
        'button:has-text("사장님 댓글")',
        'button:has-text("댓글")',
        'button:has-text("답글")'
    ],
    'comment_textarea': [
        'textarea.TextArea_b_qmgb_12i8sxie',
        'textarea.TextArea_b_qmgb_12i8sxig',
        'textarea'
    ],
    'submit_button': [
        'span:has-text("등록")',
        'button:has-text("등록")'
    ]
}

# 팝업
POPUP_SELECTORS = {
    '7day_popup': 'button:has-text("7일간 보지 않기")',
    '1day_popup': 'button:has-text("1일간 보지 않기")',
    'today_popup': 'span:has-text("오늘 하루 보지 않기")',
    'week_popup': 'span:has-text("일주일 동안 보지 않기")',
    
    # 금지어 알림
    'alert_dialog': 'div[role="alertdialog"]',
    'alert_confirm': 'button:has-text("확인")',
    'alert_cancel': 'button:has-text("취소")'
}

# 30일 경과 리뷰
OLD_REVIEW_SELECTORS = {
    'notice': '*:has-text("30일이 지난 리뷰")'
}
