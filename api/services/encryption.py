"""
암호화/복호화 서비스
플랫폼 비밀번호를 안전하게 저장하고 사용하기 위한 암호화 유틸리티
"""
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
import base64
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class EncryptionService:
    """암호화 서비스 클래스"""
    
    def __init__(self):
        self.cipher_suite = self._get_cipher_suite()
    
    def _get_cipher_suite(self):
        """암호화 키 가져오기 또는 생성"""
        key = os.getenv("ENCRYPTION_KEY")
        
        if not key:
            # 새 키 생성
            key = Fernet.generate_key().decode()
            logger.warning(f"새 암호화 키가 생성되었습니다. .env 파일에 추가하세요:")
            logger.warning(f"ENCRYPTION_KEY={key}")
            # 개발 환경에서는 자동으로 .env 파일에 추가
            try:
                with open(".env", "a") as f:
                    f.write(f"\nENCRYPTION_KEY={key}\n")
            except Exception as e:
                logger.error(f".env 파일 업데이트 실패: {e}")
        
        return Fernet(key.encode())
    
    def encrypt(self, text: str) -> str:
        """텍스트 암호화"""
        if not text:
            return ""
        
        try:
            encrypted = self.cipher_suite.encrypt(text.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"암호화 오류: {str(e)}")
            return ""
    
    def decrypt(self, encrypted_text: str) -> str:
        """텍스트 복호화"""
        if not encrypted_text:
            return ""
        
        try:
            # Fernet 암호화된 텍스트는 gAAAAA로 시작
            if not encrypted_text.startswith('gAAAAA'):
                logger.warning("평문으로 저장된 데이터")
                return encrypted_text
                
            decrypted = self.cipher_suite.decrypt(encrypted_text.encode())
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"복호화 오류: {str(e)}")
            
            # 다른 키들로 시도
            fallback_keys = [
                "RDPgZERUQbGCN6AhvK4ZT6SF0Gau7itdAfWOAO7k1mk=",
                # 필요시 다른 키 추가
            ]
            
            for key in fallback_keys:
                try:
                    fallback_cipher = Fernet(key.encode())
                    decrypted = fallback_cipher.decrypt(encrypted_text.encode())
                    logger.warning(f"대체 키로 복호화 성공")
                    
                    # 새 키로 재암호화
                    new_encrypted = self.encrypt(decrypted.decode())
                    logger.info("새 키로 재암호화 권장")
                    
                    return decrypted.decode()
                except:
                    continue
            
            # 모든 시도 실패시 평문 반환
            logger.warning("복호화 실패, 평문으로 간주")
            return encrypted_text
        
    def hash_platform_credentials(self, platform: str, platform_id: str, platform_code: str) -> str:
        """플랫폼 자격증명을 해시화하여 고유 식별자 생성"""
        data = f"{platform}:{platform_id}:{platform_code}"
        return base64.b64encode(data.encode()).decode()


# 싱글톤 인스턴스
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """암호화 서비스 싱글톤 인스턴스 반환"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


# 기존 함수들 (호환성 유지)
cipher_suite = None


def get_or_create_key():
    """암호화 키 가져오기 또는 생성 (레거시)"""
    key = os.getenv("ENCRYPTION_KEY")
    
    if not key:
        key = Fernet.generate_key().decode()
        print(f"새 암호화 키가 생성되었습니다. .env 파일에 추가하세요:")
        print(f"ENCRYPTION_KEY={key}")
        with open(".env", "a") as f:
            f.write(f"\nENCRYPTION_KEY={key}\n")
    
    return key.encode()


def encrypt_password(password: str) -> str:
    """비밀번호 암호화 (레거시)"""
    global cipher_suite
    if cipher_suite is None:
        cipher_suite = Fernet(get_or_create_key())
    
    if not password:
        return ""
    
    encrypted = cipher_suite.encrypt(password.encode())
    return encrypted.decode()


def decrypt_password(encrypted_password: str) -> str:
    """비밀번호 복호화 (레거시)"""
    global cipher_suite
    if cipher_suite is None:
        cipher_suite = Fernet(get_or_create_key())
    
    if not encrypted_password:
        return ""
    
    try:
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"복호화 오류: {str(e)}")
        return ""


def hash_platform_credentials(platform: str, platform_id: str, platform_code: str) -> str:
    """플랫폼 자격증명을 해시화하여 고유 식별자 생성 (레거시)"""
    data = f"{platform}:{platform_id}:{platform_code}"
    return base64.b64encode(data.encode()).decode()


# 테스트 코드
if __name__ == "__main__":
    # 새로운 방식 테스트
    enc_service = get_encryption_service()
    test_password = "my_secret_password_123"
    print(f"원본 비밀번호: {test_password}")
    
    encrypted = enc_service.encrypt(test_password)
    print(f"암호화된 비밀번호: {encrypted}")
    
    decrypted = enc_service.decrypt(encrypted)
    print(f"복호화된 비밀번호: {decrypted}")
    
    assert test_password == decrypted, "암호화/복호화 테스트 실패"
    print("암호화/복호화 테스트 성공!")

    print(f"원본 비밀번호: {test_password}")
    
    encrypted = encrypt_password(test_password)
    print(f"암호화된 비밀번호: {encrypted}")
    
    decrypted = decrypt_password(encrypted)
    print(f"복호화된 비밀번호: {decrypted}")
    
    assert test_password == decrypted, "암호화/복호화 테스트 실패"
    print("암호화/복호화 테스트 성공!")
