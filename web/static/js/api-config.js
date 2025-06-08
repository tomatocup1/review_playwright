/**
 * API 설정 및 공통 함수
 */

// API 기본 설정
const API_CONFIG = {
    BASE_URL: 'http://localhost:8000',
    TIMEOUT: 30000, // 30초
    RETRY_COUNT: 3,
    RETRY_DELAY: 1000 // 1초
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

// 재시도가 가능한 API 요청
async function apiRequestWithRetry(url, options = {}, retryCount = 0) {
    try {
        const fullUrl = getApiUrl(url);
        console.log(`[API] 요청: ${options.method || 'GET'} ${fullUrl}`);
        
        const response = await fetch(fullUrl, {
            timeout: API_CONFIG.TIMEOUT,
            ...options
        });
        
        // 응답 상태 확인
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log(`[API] 응답 성공: ${fullUrl}`);
        return data;
        
    } catch (error) {
        console.error(`[API] 요청 실패: ${error.message}`);
        
        // 네트워크 오류이고 재시도 가능한 경우
        if (retryCount < API_CONFIG.RETRY_COUNT && 
            (error.name === 'TypeError' || error.message.includes('fetch'))) {
            
            console.log(`[API] 재시도 ${retryCount + 1}/${API_CONFIG.RETRY_COUNT}: ${url}`);
            await delay(API_CONFIG.RETRY_DELAY * (retryCount + 1));
            return apiRequestWithRetry(url, options, retryCount + 1);
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
                throw new Error('인증이 만료되었습니다. 다시 로그인해주세요.');
            }
        }
        
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
    
    return await apiRequestWithRetry(url, mergedOptions);
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

// 전역 변수로 export
window.API_CONFIG = API_CONFIG;
window.getApiUrl = getApiUrl;
window.apiRequest = apiRequest;
window.publicApiRequest = publicApiRequest;
window.TokenManager = TokenManager;
window.getToken = getToken;
window.logout = logout;
window.checkAuth = checkAuth;

console.log('[API Config] 초기화 완료 - Base URL:', API_CONFIG.BASE_URL);
