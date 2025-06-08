/**
 * 인증 관련 JavaScript - API 경로 수정됨
 */

// 전화번호 자동 포맷팅
function formatPhoneNumber(input) {
    // 숫자만 추출
    const numbers = input.value.replace(/\D/g, '');
    
    // 포맷팅
    let formatted = '';
    if (numbers.length <= 3) {
        formatted = numbers;
    } else if (numbers.length <= 7) {
        formatted = numbers.slice(0, 3) + '-' + numbers.slice(3);
    } else if (numbers.length <= 11) {
        formatted = numbers.slice(0, 3) + '-' + numbers.slice(3, 7) + '-' + numbers.slice(7, 11);
    } else {
        formatted = numbers.slice(0, 3) + '-' + numbers.slice(3, 7) + '-' + numbers.slice(7, 11);
    }
    
    input.value = formatted;
}

// 전화번호 입력 필드에 이벤트 리스너 추가
const phoneInput = document.getElementById('phone');
if (phoneInput) {
    phoneInput.addEventListener('input', function() {
        formatPhoneNumber(this);
    });
}

// 로그인 폼 처리
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(loginForm);
        const loginData = {
            email: formData.get('email'),
            password: formData.get('password')
        };
        
        try {
            showLoading(true);
            
            const response = await publicApiRequest('/auth/login', {
                method: 'POST',
                body: JSON.stringify(loginData)
            });
            
            if (response) {
                // 토큰 저장
                TokenManager.setTokens(response.access_token, response.refresh_token);
                
                showAlert('로그인 성공! 대시보드로 이동합니다.', 'success');
                
                // 대시보드로 리디렉션
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1000);
            }
        } catch (error) {
            console.error('Login error:', error);
            showAlert(error.message || '로그인에 실패했습니다.', 'error');
        } finally {
            showLoading(false);
        }
    });
}

// 회원가입 폼 처리
const registerForm = document.getElementById('registerForm');
if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(registerForm);
        
        // 비밀번호 확인
        if (formData.get('password') !== formData.get('password_confirm')) {
            showAlert('비밀번호가 일치하지 않습니다.', 'error');
            return;
        }
        
        // 비밀번호 길이 검사
        const password = formData.get('password');
        if (password.length < 8) {
            showAlert('비밀번호는 8자 이상이어야 합니다.', 'error');
            return;
        }
        
        // 전화번호가 있으면 형식 검사
        const phone = formData.get('phone');
        if (phone && phone.length > 0) {
            const phonePattern = /^\d{3}-\d{4}-\d{4}$/;
            if (!phonePattern.test(phone)) {
                showAlert('전화번호 형식이 올바르지 않습니다. (예: 010-1234-5678)', 'error');
                return;
            }
        }
        
        const registerData = {
            email: formData.get('email'),
            password: formData.get('password'),
            name: formData.get('name'),
            phone: phone || null,
            company_name: formData.get('company_name') || null,
            role: formData.get('role') || 'owner',
            marketing_consent: formData.get('marketing_consent') ? true : false
        };
        
        try {
            showLoading(true);
            
            const response = await publicApiRequest('/auth/register', {
                method: 'POST',
                body: JSON.stringify(registerData)
            });
            
            if (response) {
                showAlert('회원가입이 완료되었습니다! 로그인 페이지로 이동합니다.', 'success');
                
                // 로그인 페이지로 리디렉션
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            }
        } catch (error) {
            console.error('Register error:', error);
            
            // 상세 오류 메시지 처리
            let errorMessage = error.message || '회원가입에 실패했습니다.';
            
            // 422 에러 (Validation Error) 처리
            if (error.message && error.message.includes('422')) {
                errorMessage = '입력 정보를 확인해주세요.';
            } else if (error.message && error.message.includes('already exists')) {
                errorMessage = '이미 가입된 이메일입니다.';
            }
            
            showAlert(errorMessage, 'error');
        } finally {
            showLoading(false);
        }
    });
}

// 알림 표시
function showAlert(message, type = 'info') {
    // 기존 알림 제거
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // 새 알림 생성
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.style.whiteSpace = 'pre-line';  // 줄바꿈 유지
    alert.textContent = message;
    
    // 폼 위에 추가
    const form = document.querySelector('.auth-form');
    if (form) {
        form.parentNode.insertBefore(alert, form);
    } else {
        // 폼이 없으면 body에 추가
        document.body.insertBefore(alert, document.body.firstChild);
    }
    
    // 10초 후 자동 제거
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 10000);
}

// 로딩 표시
function showLoading(show) {
    const submitBtn = document.querySelector('button[type=\"submit\"]');
    if (submitBtn) {
        submitBtn.disabled = show;
        const originalText = submitBtn.getAttribute('data-original-text') || submitBtn.textContent;
        
        if (show) {
            submitBtn.setAttribute('data-original-text', originalText);
            submitBtn.textContent = '처리 중...';
        } else {
            submitBtn.textContent = originalText;
        }
    }
}

console.log('[Auth] 인증 스크립트 로드됨 - API Base URL:', window.API_CONFIG?.BASE_URL || 'api-config.js를 먼저 로드하세요');
