/**
 * API 설정 및 공통 함수 (개선된 버전)
 */

// API 기본 설정
const API_CONFIG = {
    BASE_URL: 'http://localhost:8000',
    TIMEOUT: 30000, // 30초
    RETRY_COUNT: 3,
    RETRY_DELAY: 1000, // 1초
    SERVICE_UNAVAILABLE_RETRY_COUNT: 5, // 503 에러용 재시도 횟수
    SERVICE_UNAVAILABLE_RETRY_DELAY: 2000 // 503 에러용 재시도 간격
};

// API URL 생성 헬퍼
function getApiUrl(endpoint) {
    // endpoint가 이미 full URL이면 그대로 반환
    if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
        return endpoint;
    }
    
    // /api로 시작하지 않으면 추가
    if (!endpoint.startsWith('/api')) {
        endpoint = '/api' + (endpoint.startsWith('/') ? '' : '/') + endpoint;
    }
    
    return API_CONFIG.BASE_URL + endpoint;
}

// 딜레이 함수
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 로딩 상태 관리
const LoadingManager = {
    activeRequests: new Set(),
    
    start(requestId) {
        this.activeRequests.add(requestId);
        this.updateUI();
    },
    
    stop(requestId) {
        this.activeRequests.delete(requestId);
        this.updateUI();
    },
    
    updateUI() {
        const isLoading = this.activeRequests.size > 0;
        const loadingElement = document.querySelector('.loading-spinner');
        if (loadingElement) {
            loadingElement.style.display = isLoading ? 'block' : 'none';
        }
        
        // 페이지 전체 로딩 표시
        if (isLoading) {
            document.body.style.cursor = 'wait';
        } else {
            document.body.style.cursor = 'default';
        }
    }
};

// 에러 메시지 표시
function showErrorMessage(message, duration = 5000) {
    // 기존 에러 메시지 제거
    const existingError = document.querySelector('.api-error-message');
    if (existingError) {
        existingError.remove();
    }
    
    // 새 에러 메시지 생성
    const errorDiv = document.createElement('div');
    errorDiv.className = 'api-error-message alert alert-danger';
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        max-width: 400px;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        animation: slideInRight 0.3s ease;
    `;
    errorDiv.innerHTML = `
        <strong>오류:</strong> ${message}
        <button type="button" class="btn-close" style="float: right; background: none; border: none; font-size: 20px; cursor: pointer;">&times;</button>
    `;
    
    // 닫기 버튼 이벤트
    errorDiv.querySelector('.btn-close').onclick = () => errorDiv.remove();
    
    document.body.appendChild(errorDiv);
    
    // 자동 제거
    if (duration > 0) {
        setTimeout(() => errorDiv.remove(), duration);
    }
}

// 재시도가 가능한 API 요청 (개선된 버전)
async function apiRequestWithRetry(url, options = {}, retryCount = 0) {
    const requestId = Math.random().toString(36).substr(2, 9);
    LoadingManager.start(requestId);
    
    try {
        const fullUrl = getApiUrl(url);
        console.log(`[API] 요청: ${options.method || 'GET'} ${fullUrl}`);
        
        const response = await fetch(fullUrl, {
            timeout: API_CONFIG.TIMEOUT,
            ...options
        });
        
        // 503 Service Unavailable 특별 처리
        if (response.status === 503) {
            LoadingManager.stop(requestId);
            
            if (retryCount < API_CONFIG.SERVICE_UNAVAILABLE_RETRY_COUNT) {
                console.log(`[API] 서비스 일시 불가 - 재시도 ${retryCount + 1}/${API_CONFIG.SERVICE_UNAVAILABLE_RETRY_COUNT}: ${url}`);
                
                // 사용자에게 재시도 중임을 알림
                if (retryCount === 0) {
                    showErrorMessage('서버 연결 중... 잠시만 기다려주세요.', 0);
                }
                
                await delay(API_CONFIG.SERVICE_UNAVAILABLE_RETRY_DELAY * (retryCount + 1));
                return apiRequestWithRetry(url, options, retryCount + 1);
            } else {
                throw new Error('서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
            }
        }
        
        // 기타 HTTP 오류 처리
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log(`[API] 응답 성공: ${fullUrl}`);
        
        // 성공 시 에러 메시지 제거
        const existingError = document.querySelector('.api-error-message');
        if (existingError) {
            existingError.remove();
        }
        
        LoadingManager.stop(requestId);
        return data;
        
    } catch (error) {
        LoadingManager.stop(requestId);
        console.error(`[API] 요청 실패: ${error.message}`);
        
        // "Server disconnected" 에러를 사용자 친화적 메시지로 변환
        if (error.message.includes('Server disconnected') || 
            error.message.includes('Failed to fetch') ||
            error.name === 'TypeError') {
            
            if (retryCount < API_CONFIG.RETRY_COUNT) {
                console.log(`[API] 연결 오류 재시도 ${retryCount + 1}/${API_CONFIG.RETRY_COUNT}: ${url}`);
                await delay(API_CONFIG.RETRY_DELAY * (retryCount + 1));
                return apiRequestWithRetry(url, options, retryCount + 1);
            } else {
                throw new Error('서버와 연결이 끊어졌습니다. 네트워크 상태를 확인하고 다시 시도해주세요.');
            }
        }
        
        throw error;
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
            const response = await apiRequestWithRetry('/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            
            this.setTokens(response.access_token, response.refresh_token);
            return response.access_token;
            
        } catch (error) {
            console.error('토큰 갱신 실패:', error);
            this.clearTokens();
            return null;
        }
    }
};

// 인증된 API 요청
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
    
    try {
        return await apiRequestWithRetry(url, mergedOptions);
    } catch (error) {
        // 401 에러 (인증 오류)인 경우 토큰 갱신 시도
        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
            const newToken = await TokenManager.refreshAccessToken();
            if (newToken) {
                // 새 토큰으로 재시도
                mergedOptions.headers['Authorization'] = `Bearer ${newToken}`;
                return await apiRequestWithRetry(url, mergedOptions);
            } else {
                // 토큰 갱신 실패시 로그인 페이지로 이동
                showErrorMessage('인증이 만료되었습니다. 다시 로그인해주세요.');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
                throw new Error('인증이 만료되었습니다. 다시 로그인해주세요.');
            }
        }
        
        // 사용자 친화적 에러 메시지 표시
        showErrorMessage(error.message);
        throw error;
    }
}

// 토큰 없이 요청하는 API (로그인, 회원가입 등)
async function publicApiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
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
    
    try {
        return await apiRequestWithRetry(url, mergedOptions);
    } catch (error) {
        // 사용자 친화적 에러 메시지 표시
        showErrorMessage(error.message);
        throw error;
    }
}

// 토큰 유효성 확인
function getToken() {
    return TokenManager.getAccessToken();
}

// 로그아웃
function logout() {
    TokenManager.clearTokens();
    window.location.href = '/login';
}

// 인증 확인
function checkAuth() {
    const accessToken = TokenManager.getAccessToken();
    if (!accessToken) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

// CSS 애니메이션 추가
if (!document.querySelector('#api-config-styles')) {
    const style = document.createElement('style');
    style.id = 'api-config-styles';
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
        
        .api-error-message {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            border: 1px solid #dc3545;
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .loading-spinner {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 10000;
            background: rgba(255, 255, 255, 0.9);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .loading-spinner::after {
            content: '';
            display: block;
            width: 40px;
            height: 40px;
            margin: 8px auto;
            border-radius: 50%;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// 전역 변수로 export
window.API_CONFIG = API_CONFIG;
window.getApiUrl = getApiUrl;
window.apiRequest = apiRequest;
window.publicApiRequest = publicApiRequest;
window.TokenManager = TokenManager;
window.getToken = getToken;
window.logout = logout;
window.checkAuth = checkAuth;
window.showErrorMessage = showErrorMessage;
window.LoadingManager = LoadingManager;

console.log('[API Config] 초기화 완료 (개선된 버전) - Base URL:', API_CONFIG.BASE_URL);
