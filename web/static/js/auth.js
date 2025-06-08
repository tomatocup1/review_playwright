/**
 * 인증 관련 JavaScript - API 경로 수정됨 + 답글 등록 기능 호환성 추가
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

// 알림 표시 - 개선된 버전 (답글 등록 기능과 호환)
function showAlert(message, type = 'info') {
    // 기존 알림 제거
    const existingAlert = document.querySelector('.alert.position-fixed');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // 타입 매핑
    const typeMapping = {
        'error': 'danger',
        'success': 'success',
        'warning': 'warning',
        'info': 'info',
        'danger': 'danger'
    };
    
    const alertType = typeMapping[type] || 'info';
    
    // 새 알림 생성
    const alert = document.createElement('div');
    alert.className = `alert alert-${alertType} alert-dismissible fade show position-fixed`;
    alert.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 9999;
        max-width: 450px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        border-radius: 12px;
        border: none;
        animation: slideInRight 0.4s ease-out;
    `;
    alert.style.whiteSpace = 'pre-line';  // 줄바꿈 유지
    
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // body에 추가
    document.body.appendChild(alert);
    
    // 자동 제거
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// 토큰 관리 함수들 (reviews.js와 호환성을 위해)
function getToken() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
}

function setToken(token, refreshToken = null) {
    localStorage.setItem('access_token', token);
    if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken);
    }
}

function removeTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
}

// API 요청 함수 (reviews.js와 호환성을 위해)
async function apiRequest(url, options = {}) {
    const token = getToken();
    
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };
    
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    const response = await fetch('/api' + url, finalOptions);
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        // 401 에러 처리 (토큰 만료)
        if (response.status === 401) {
            removeTokens();
            showAlert('세션이 만료되었습니다. 다시 로그인해주세요.', 'warning');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            throw new Error('세션이 만료되었습니다.');
        }
        
        throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    return await response.json();
}

// 공개 API 요청 함수 (인증 불필요)
async function publicApiRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    const response = await fetch('/api' + url, finalOptions);
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
    }
    
    return await response.json();
}

// 로그아웃 함수
function logout() {
    removeTokens();
    
    showAlert('로그아웃되었습니다.', 'info');
    setTimeout(() => {
        window.location.href = '/login';
    }, 1000);
}

// 토큰 유효성 검사
async function validateToken() {
    const token = getToken();
    if (!token) {
        return false;
    }
    
    try {
        await apiRequest('/auth/me');
        return true;
    } catch (error) {
        console.error('Token validation failed:', error);
        removeTokens();
        return false;
    }
}

// 로딩 표시
function showLoading(show) {
    const submitBtn = document.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = show;
        const originalText = submitBtn.getAttribute('data-original-text') || submitBtn.textContent;
        
        if (show) {
            submitBtn.setAttribute('data-original-text', originalText);
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 처리 중...';
        } else {
            submitBtn.textContent = originalText;
        }
    }
}

// 페이지 로드시 인증 상태 확인
document.addEventListener('DOMContentLoaded', function() {
    const token = getToken();
    const currentPath = window.location.pathname;
    
    // 로그인이 필요한 페이지들
    const protectedPages = ['/dashboard', '/stores', '/reviews', '/settings'];
    
    // 로그인한 사용자가 접근하면 안 되는 페이지들
    const authPages = ['/login', '/register'];
    
    if (token) {
        // 토큰이 있으면서 로그인/회원가입 페이지에 있는 경우
        if (authPages.includes(currentPath)) {
            window.location.href = '/dashboard';
            return;
        }
        
        // 토큰 유효성 검사 (백그라운드에서)
        validateToken().then(isValid => {
            if (!isValid && protectedPages.includes(currentPath)) {
                window.location.href = '/login';
            }
        });
    } else {
        // 토큰이 없으면서 보호된 페이지에 있는 경우
        if (protectedPages.includes(currentPath)) {
            showAlert('로그인이 필요합니다.', 'warning');
            window.location.href = '/login';
            return;
        }
    }
});

// TokenManager 호환성을 위한 객체 (기존 코드와의 호환성)
window.TokenManager = {
    setTokens: function(accessToken, refreshToken) {
        setToken(accessToken, refreshToken);
    },
    
    getAccessToken: function() {
        return getToken();
    },
    
    removeTokens: function() {
        removeTokens();
    }
};

// CSS 애니메이션 추가 (알림용)
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .alert.position-fixed {
        animation: slideInRight 0.4s ease-out;
    }
`;
document.head.appendChild(style);

console.log('[Auth] 인증 스크립트 로드됨 - API Base URL:', window.API_CONFIG?.BASE_URL || 'api-config.js를 먼저 로드하세요');
console.log('[Auth] 답글 등록 기능 호환성 추가됨');
