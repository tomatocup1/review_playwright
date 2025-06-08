"""
날짜 파싱 유틸리티
상대적 날짜 표현을 절대 날짜로 변환
"""
import re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def parse_relative_date(date_str: str) -> str:
    """
    상대적 날짜 표현을 YYYY-MM-DD 형식으로 변환
    
    Args:
        date_str: 상대적 날짜 문자열 (예: '오늘', '어제', '3일 전')
        
    Returns:
        YYYY-MM-DD 형식의 날짜 문자열
    """
    try:
        now = datetime.now()
        
        # 날짜 문자열 정규화
        date_str = date_str.strip()
        
        # 오늘
        if date_str == '오늘':
            return now.strftime('%Y-%m-%d')
        
        # 어제
        elif date_str == '어제':
            return (now - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 그제
        elif date_str == '그제' or date_str == '그저께':
            return (now - timedelta(days=2)).strftime('%Y-%m-%d')
        
        # N일 전
        elif '일 전' in date_str:
            match = re.search(r'(\d+)일 전', date_str)
            if match:
                days = int(match.group(1))
                return (now - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # N개월 전 (대략적으로 30일로 계산)
        elif '개월 전' in date_str:
            match = re.search(r'(\d+)개월 전', date_str)
            if match:
                months = int(match.group(1))
                # 더 정확한 계산을 위해 30일 대신 실제 월 계산
                target_date = now
                for _ in range(months):
                    # 한 달 전으로 이동
                    if target_date.month == 1:
                        target_date = target_date.replace(year=target_date.year - 1, month=12)
                    else:
                        target_date = target_date.replace(month=target_date.month - 1)
                return target_date.strftime('%Y-%m-%d')
        
        # N주 전
        elif '주 전' in date_str:
            match = re.search(r'(\d+)주 전', date_str)
            if match:
                weeks = int(match.group(1))
                return (now - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        # YYYY.MM.DD 또는 YYYY-MM-DD 형식
        elif re.match(r'\d{4}[.-]\d{1,2}[.-]\d{1,2}', date_str):
            # 구분자를 -로 통일
            date_str = date_str.replace('.', '-')
            parts = date_str.split('-')
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
        
        # MM월 DD일 형식
        elif re.match(r'\d{1,2}월 \d{1,2}일', date_str):
            match = re.search(r'(\d{1,2})월 (\d{1,2})일', date_str)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                # 현재 연도 사용 (만약 현재 날짜보다 미래면 작년으로)
                year = now.year
                test_date = datetime(year, month, day)
                if test_date > now:
                    year -= 1
                return f"{year:04d}-{month:02d}-{day:02d}"
        
        # 인식할 수 없는 형식
        else:
            logger.warning(f"인식할 수 없는 날짜 형식: {date_str}")
            return now.strftime('%Y-%m-%d')  # 기본값으로 오늘 날짜 반환
            
    except Exception as e:
        logger.error(f"날짜 파싱 중 오류: {date_str} - {str(e)}")
        return datetime.now().strftime('%Y-%m-%d')


def test_date_parser():
    """날짜 파서 테스트"""
    test_cases = [
        '오늘',
        '어제',
        '그제',
        '3일 전',
        '10일 전',
        '1개월 전',
        '2개월 전',
        '1주 전',
        '2024.12.25',
        '2024-12-25',
        '12월 25일',
        '알 수 없음'
    ]
    
    print("=== 날짜 파서 테스트 ===")
    for test in test_cases:
        result = parse_relative_date(test)
        print(f"{test:15} -> {result}")


if __name__ == "__main__":
    test_date_parser()