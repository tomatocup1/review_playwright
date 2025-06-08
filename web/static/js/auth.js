/**
 * 인증 관련 JavaScript
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
            
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(loginData)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // 토큰 저장
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                
                showAlert('로그인 성공! 대시보드로 이동합니다.', 'success');
                
                // 대시보드로 리디렉션
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1000);
            } else {
                showAlert(data.detail || '로그인에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            showAlert('서버 오류가 발생했습니다.', 'error');
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
            
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(registerData)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showAlert('회원가입이 완료되었습니다! 로그인 페이지로 이동합니다.', 'success');
                
                // 로그인 페이지로 리디렉션
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else {
                // 422 에러 (Validation Error) 처리
                if (response.status === 422 && data.detail) {
                    // Pydantic validation error 처리
                    if (Array.isArray(data.detail)) {
                        const errorMessages = data.detail.map(err => {
                            const field = err.loc[err.loc.length - 1];
                            let fieldName = field;
                            let message = err.msg;
                            
                            // 필드명 한글화
                            const fieldNameMap = {
                                'email': '이메일',
                                'password': '비밀번호',
                                'name': '이름',
                                'phone': '전화번호',
                                'role': '사용자 유형',
                                'company_name': '회사명'
                            };
                            
                            fieldName = fieldNameMap[field] || field;
                            
                            // 에러 메시지 한글화
                            if (err.type === 'string_pattern_mismatch' && field === 'phone') {
                                message = '형식이 올바르지 않습니다. (예: 010-1234-5678)';
                            } else if (err.type === 'string_too_short') {
                                message = '너무 짧습니다.';
                            } else if (err.type === 'value_error') {
                                message = '올바른 값을 입력해주세요.';
                            }
                            
                            return `${fieldName}: ${message}`;
                        });
                        showAlert(errorMessages.join('\n'), 'error');
                    } else {
                        showAlert(data.detail, 'error');
                    }
                } else {
                    // 기타 에러
                    const errorMessage = typeof data.detail === 'string' 
                        ? data.detail 
                        : (data.message || '회원가입에 실패했습니다.');
                    showAlert(errorMessage, 'error');
                }
            }
        } catch (error) {
            console.error('Register error:', error);
            showAlert('서버 오류가 발생했습니다.', 'error');
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
    }
    
    // 10초 후 자동 제거
    setTimeout(() => {
        alert.remove();
    }, 10000);
}

// 로딩 표시
function showLoading(show) {
    const submitBtn = document.querySelector('button[type="submit"]');
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

// 토큰 관리
const TokenManager = {
    getAccessToken() {
        return localStorage.getItem('access_token');
    },
    
    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    },
    
    setTokens(accessToken, refreshToken) {
        localStorage.setItem('access_token', accessToken);
        if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
        }
    },
    
    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },
    
    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            return null;
        }
        
        try {
            const response = await fetch('/api/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token);
                return data.access_token;
            } else {
                this.clearTokens();
                window.location.href = '/login';
                return null;
            }
        } catch (error) {
            console.error('Token refresh error:', error);
            return null;
        }
    }
};

// API 요청 헬퍼
async function apiRequest(url, options = {}) {
    const accessToken = TokenManager.getAccessToken();
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(accessToken && { 'Authorization': `Bearer ${accessToken}` })
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    let response = await fetch(url, mergedOptions);
    
    // 토큰 만료시 자동 갱신
    if (response.status === 401) {
        const newToken = await TokenManager.refreshAccessToken();
        if (newToken) {
            mergedOptions.headers['Authorization'] = `Bearer ${newToken}`;
            response = await fetch(url, mergedOptions);
        }
    }
    
    return response;
}

// 인증된 API 요청 헬퍼 (store_register.html에서 사용)
async function makeAuthenticatedRequest(url, options = {}) {
    const accessToken = TokenManager.getAccessToken();
    
    if (!accessToken) {
        throw new Error('로그인이 필요합니다.');
    }
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    let response = await fetch(url, mergedOptions);
    
    // 토큰 만료시 자동 갱신
    if (response.status === 401) {
        const newToken = await TokenManager.refreshAccessToken();
        if (newToken) {
            mergedOptions.headers['Authorization'] = `Bearer ${newToken}`;
            response = await fetch(url, mergedOptions);
        } else {
            throw new Error('인증 토큰이 만료되었습니다. 다시 로그인해주세요.');
        }
    }
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.detail || data.message || '요청 처리에 실패했습니다.');
    }
    
    return data;
}

// 로그아웃
function logout() {
    TokenManager.clearTokens();
    window.location.href = '/';
}

// 인증 확인 함수
function checkAuth() {
    const accessToken = TokenManager.getAccessToken();
    if (!accessToken) {
        // 토큰이 없으면 로그인 페이지로 리다이렉트
        window.location.href = '/login';
        return false;
    }
    return true;
}

// Export for use in other scripts
window.TokenManager = TokenManager;
window.apiRequest = apiRequest;
window.makeAuthenticatedRequest = makeAuthenticatedRequest;
window.logout = logout;
window.checkAuth = checkAuth;
