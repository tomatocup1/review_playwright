/**
 * 인증 관련 JavaScript
 */

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
        
        // 비밀번호 강도 검사
        const password = formData.get('password');
        if (!isPasswordStrong(password)) {
            showAlert('비밀번호는 8자 이상이며, 영문/숫자/특수문자를 포함해야 합니다.', 'error');
            return;
        }
        
        const registerData = {
            email: formData.get('email'),
            password: formData.get('password'),
            name: formData.get('name'),
            phone: formData.get('phone') || null,
            company_name: formData.get('company_name') || null,
            role: formData.get('role'),
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
                showAlert(data.detail || '회원가입에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('Register error:', error);
            showAlert('서버 오류가 발생했습니다.', 'error');
        } finally {
            showLoading(false);
        }
    });
}

// 비밀번호 강도 검사
function isPasswordStrong(password) {
    const minLength = 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasNonalphas = /\W/.test(password);
    
    return password.length >= minLength && 
           (hasUpperCase || hasLowerCase) && 
           hasNumbers && 
           hasNonalphas;
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
    alert.textContent = message;
    
    // 폼 위에 추가
    const form = document.querySelector('.auth-form');
    if (form) {
        form.parentNode.insertBefore(alert, form);
    }
    
    // 5초 후 자동 제거
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

// 로딩 표시
function showLoading(show) {
    const submitBtn = document.querySelector('button[type="submit"]');
    if (submitBtn) {
        submitBtn.disabled = show;
        submitBtn.textContent = show ? '처리 중...' : submitBtn.getAttribute('data-original-text') || '제출';
        
        if (!show) {
            submitBtn.setAttribute('data-original-text', submitBtn.textContent);
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
        localStorage.setItem('refresh_token', refreshToken);
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

// 로그아웃
function logout() {
    TokenManager.clearTokens();
    window.location.href = '/';
}

// Export for use in other scripts
window.TokenManager = TokenManager;
window.apiRequest = apiRequest;
window.logout = logout;
