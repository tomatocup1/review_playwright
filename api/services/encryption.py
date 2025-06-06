"""
암호화/복호화 서비스
플랫폼 비밀번호를 안전하게 저장하고 사용하기 위한 암호화 유틸리티
"""
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
import base64

load_dotenv()

# 암호화 키 생성 또는 환경변수에서 로드
def get_or_create_key():
    """암호화 키 가져오기 또는 생성"""
    key = os.getenv("ENCRYPTION_KEY")
    
    if not key:
        # 새 키 생성
        key = Fernet.generate_key().decode()
        print(f"새 암호화 키가 생성되었습니다. .env 파일에 추가하세요:")
        print(f"ENCRYPTION_KEY={key}")
        # 개발 환경에서는 자동으로 .env 파일에 추가
        with open(".env", "a") as f:
            f.write(f"\nENCRYPTION_KEY={key}\n")
    
    return key.encode()

# Fernet 인스턴스 생성
cipher_suite = Fernet(get_or_create_key())

def encrypt_password(password: str) -> str:
    """비밀번호 암호화"""
    if not password:
        return ""
    
    encrypted = cipher_suite.encrypt(password.encode())
    return encrypted.decode()

def decrypt_password(encrypted_password: str) -> str:
    """비밀번호 복호화"""
    if not encrypted_password:
        return ""
    
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        # 복호화 실패시 빈 문자열 반환
        print(f"복호화 오류: {str(e)}")
        return ""

def hash_platform_credentials(platform: str, platform_id: str, platform_code: str) -> str:
    """플랫폼 자격증명을 해시화하여 고유 식별자 생성"""
    data = f"{platform}:{platform_id}:{platform_code}"
    return base64.b64encode(data.encode()).decode()

# 테스트 코드
if __name__ == "__main__":
    # 테스트
    test_password = "my_secret_password_123"
    print(f"원본 비밀번호: {test_password}")
    
    encrypted = encrypt_password(test_password)
    print(f"암호화된 비밀번호: {encrypted}")
    
    decrypted = decrypt_password(encrypted)
    print(f"복호화된 비밀번호: {decrypted}")
    
    assert test_password == decrypted, "암호화/복호화 테스트 실패"
    print("암호화/복호화 테스트 성공!")
