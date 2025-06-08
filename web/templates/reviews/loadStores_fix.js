// 매장 목록 로드 함수 수정
async function loadStores() {
    try {
        const response = await safeApiRequest('/api/stores');
        const select = document.getElementById('storeSelect');
        
        // 기존 옵션 제거 (첫 번째 옵션 제외)
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        // API 응답이 배열인지 객체인지 확인
        const stores = Array.isArray(response) ? response : (response.stores || []);
        
        stores.forEach(store => {
            const option = document.createElement('option');
            option.value = store.store_code;
            option.textContent = `${store.store_name} (${store.platform})`;
            select.appendChild(option);
        });
        
        if (stores.length === 0) {
            showAlert('등록된 매장이 없습니다. 먼저 매장을 등록해주세요.', 'info');
        }
    } catch (error) {
        showAlert('매장 목록을 불러오는데 실패했습니다: ' + error.message, 'danger');
    }
}