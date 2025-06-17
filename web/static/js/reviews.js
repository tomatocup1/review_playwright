/**
 * 리뷰 답글 등록 관련 JavaScript
 * 웹 UI에서 AI 답글을 실제 플랫폼에 등록하는 기능
 */

console.log('[ReviewsReplyPosting] 답글 등록 스크립트 로드됨');

// 전역 변수
let currentReviewForPosting = null;
let currentReplyContent = null;
let processingReviews = new Set(); // 처리 중인 리뷰 ID 저장
let isPostingInProgress = false; // 전역 처리 중 플래그 추가

// 페이지 로드시 초기화
document.addEventListener('DOMContentLoaded', function () {
    console.log('[ReviewsReplyPosting] DOM 로드 완료 - 답글 등록 기능 초기화');
    initializeReplyPostingFeatures();
});

/**
 * 답글 등록 기능 초기화
 */
function initializeReplyPostingFeatures() {
    // 모달 HTML이 존재하지 않으면 추가
    if (!document.getElementById('postReplyModal')) {
        addReplyPostingModal();
    }

    // 일괄 등록 버튼이 존재하지 않으면 추가
    if (!document.getElementById('batchActionsSection')) {
        addBatchActionsSection();
    }

    // 이벤트 리스너 설정
    setupReplyPostingEventListeners();

    // 처리 중 버튼 스타일 추가
    const style = document.createElement('style');
    style.textContent = `
        .post-reply-btn.processing {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .post-reply-btn.processing:hover {
            opacity: 0.6;
        }
    `;
    document.head.appendChild(style);
}

/**
 * 답글 등록 모달 HTML 추가
 */
function addReplyPostingModal() {
    const modalHtml = `
    <!-- 답글 등록 확인 모달 -->
    <div class="modal fade" id="postReplyModal" tabindex="-1" aria-labelledby="postReplyModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="postReplyModalLabel">📤 답글 등록 확인</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i>
                        <strong>주의:</strong> 답글을 등록하면 실제 플랫폼(배민/요기요/쿠팡이츠)에 게시됩니다.
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <h6>📝 원본 리뷰</h6>
                            <div class="border rounded p-3 bg-light" style="max-height: 200px; overflow-y: auto;">
                                <div id="modalReviewContent">리뷰 내용을 불러오는 중...</div>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <span id="modalReviewAuthor"></span> | 
                                        <span id="modalReviewRating"></span> | 
                                        <span id="modalReviewDate"></span>
                                    </small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <h6>💬 등록할 답글</h6>
                            <div class="border rounded p-3" style="max-height: 200px; overflow-y: auto; background-color: #f0f8ff;">
                                <div id="modalReplyContent">답글 내용을 불러오는 중...</div>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <span id="modalReplyType"></span> | 
                                        <span id="modalReplyLength"></span>자
                                    </small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <h6>📋 매장 정보</h6>
                        <div class="row">
                            <div class="col-md-6">
                                <small><strong>매장명:</strong> <span id="modalStoreName"></span></small>
                            </div>
                            <div class="col-md-6">
                                <small><strong>플랫폼:</strong> <span id="modalPlatform"></span></small>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="bi bi-x-circle"></i> 취소
                    </button>
                    <button type="button" class="btn btn-success" id="confirmPostReplyBtn">
                        <i class="bi bi-send"></i> 답글 등록
                    </button>
                </div>
            </div>
        </div>
    </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

/**
 * 일괄 등록 섹션 추가
 */
function addBatchActionsSection() {
    const existingFilterSection = document.querySelector('.filter-section');
    if (!existingFilterSection) return;

    const batchSectionHtml = `
    <div id="batchActionsSection" class="batch-actions" style="display: none;">
        <h6><i class="bi bi-lightning"></i> 일괄 처리</h6>
        <div class="d-flex gap-2 flex-wrap">
            <button id="batchPostAll" class="btn btn-primary btn-sm" data-store-code="">
                <i class="bi bi-send-fill"></i> 선택된 매장의 모든 답글 등록
            </button>
            <button id="batchPostGenerated" class="btn btn-info btn-sm" data-store-code="">
                <i class="bi bi-robot"></i> AI 생성된 답글만 등록
            </button>
            <button id="batchPostReady" class="btn btn-success btn-sm" data-store-code="">
                <i class="bi bi-check-circle"></i> 등록 준비된 답글만 등록
            </button>
        </div>
        <small class="text-muted">※ 일괄 등록은 백그라운드에서 처리되며, 완료 후 알림으로 결과를 확인할 수 있습니다.</small>
    </div>
    `;

    existingFilterSection.insertAdjacentHTML('afterend', batchSectionHtml);
}

/**
 * 이벤트 리스너 설정
 */
function setupReplyPostingEventListeners() {
    // 답글 등록 확인 버튼
    document.addEventListener('click', function (e) {
        if (e.target && e.target.id === 'confirmPostReplyBtn') {
            handleConfirmPostReply();
        }
    });

    // 일괄 등록 버튼들
    document.addEventListener('click', function (e) {
        if (e.target && e.target.id === 'batchPostAll') {
            handleBatchPostAll();
        } else if (e.target && e.target.id === 'batchPostGenerated') {
            handleBatchPostGenerated();
        } else if (e.target && e.target.id === 'batchPostReady') {
            handleBatchPostReady();
        }
    });

    // 모달 이벤트 리스너 추가
    const postReplyModal = document.getElementById('postReplyModal');
    if (postReplyModal) {
        postReplyModal.addEventListener('hidden.bs.modal', function () {
            // 모달이 닫힐 때 처리 중 상태 초기화
            if (currentReviewForPosting) {
                processingReviews.delete(currentReviewForPosting.reviewId);
                isPostingInProgress = false;
            }
        });
    }
}

/**
 * 리뷰 목록에 답글 등록 버튼 추가 (기존 displayReviews 함수 확장)
 */
function addReplyPostingButtons(reviewsHtml, reviews) {
    return reviews.map(review => {
        // 기존 AI 컨트롤 섹션 수정
        let replyPostingControls = '';

        if (review.response_status === 'generated' || review.response_status === 'ready_to_post') {
            replyPostingControls = `
                <button class="btn btn-success btn-sm post-reply-btn" 
                        data-review-id="${review.review_id}"
                        data-reply-content="${escapeHtml(review.final_response || review.ai_response || '')}"
                        data-store-name="${escapeHtml(review.store_name || '')}"
                        data-platform="${review.platform || ''}">
                    <i class="bi bi-send"></i> 답글 등록
                </button>
            `;
        } else if (review.response_status === 'posted') {
            replyPostingControls = `
                <span class="badge bg-success">
                    <i class="bi bi-check-circle"></i> 등록완료
                </span>
            `;
        } else if (review.response_status === 'failed') {
            replyPostingControls = `
                <button class="btn btn-warning btn-sm retry-reply-btn" 
                        data-review-id="${review.review_id}">
                    <i class="bi bi-arrow-clockwise"></i> 재시도
                </button>
            `;
        }

        return replyPostingControls;
    });
}

/**
 * 답글 등록 버튼 클릭 처리
 */
function handlePostReplyClick(button) {
    const reviewId = button.dataset.reviewId;

    // 전역 처리 중 체크
    if (isPostingInProgress) {
        console.log('다른 답글 등록이 진행 중입니다.');
        showAlert('다른 답글 등록이 진행 중입니다. 잠시 후 다시 시도해주세요.', 'warning');
        return;
    }

    // 이미 처리 중인지 확인
    if (processingReviews.has(reviewId)) {
        showAlert('이미 답글 등록이 진행 중입니다.', 'warning');
        return;
    }

    // 중복 클릭 방지
    if (button.disabled || button.classList.contains('processing')) {
        return;
    }

    // 처리 시작 표시
    isPostingInProgress = true;
    processingReviews.add(reviewId);

    // 버튼 비활성화
    button.disabled = true;
    button.classList.add('processing');
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 처리중...';

    currentReviewForPosting = {
        reviewId: reviewId,
        replyContent: button.dataset.replyContent,
        storeName: button.dataset.storeName,
        platform: button.dataset.platform
    };

    // 모달에 정보 표시
    populateReplyPostingModal(button).then(() => {
        // 모달 표시
        const modal = new bootstrap.Modal(document.getElementById('postReplyModal'));
        modal.show();

        // 버튼 원상복구
        button.disabled = false;
        button.classList.remove('processing');
        button.innerHTML = '<i class="bi bi-send"></i> 답글 등록';
        isPostingInProgress = false;
    }).catch(error => {
        // 에러 시에도 원상복구
        button.disabled = false;
        button.classList.remove('processing');
        button.innerHTML = '<i class="bi bi-send"></i> 답글 등록';
        processingReviews.delete(reviewId);
        isPostingInProgress = false;
        console.error('모달 정보 로드 실패:', error);
        showAlert('리뷰 정보를 불러오는데 실패했습니다.', 'danger');
    });
}

/**
 * 모달에 리뷰 및 답글 정보 채우기
 */
async function populateReplyPostingModal(button) {
    const reviewId = button.dataset.reviewId;

    try {
        // 리뷰 상세 정보 가져오기 - 수정된 부분
        const reviewInfo = await apiRequest(`/reviews/${reviewId}`);

        // 모달 내용 업데이트
        document.getElementById('modalReviewContent').innerHTML = escapeHtml(reviewInfo.review_content || '');
        document.getElementById('modalReviewAuthor').textContent = reviewInfo.review_name || '익명';
        document.getElementById('modalReviewRating').textContent = '★'.repeat(reviewInfo.rating || 0) + '☆'.repeat(5 - (reviewInfo.rating || 0));
        document.getElementById('modalReviewDate').textContent = formatDate(reviewInfo.review_date);

        document.getElementById('modalReplyContent').innerHTML = escapeHtml(button.dataset.replyContent);
        document.getElementById('modalReplyType').textContent = getReplyTypeText(reviewInfo.response_method || 'ai_auto');
        document.getElementById('modalReplyLength').textContent = (button.dataset.replyContent || '').length;

        document.getElementById('modalStoreName').textContent = button.dataset.storeName;
        document.getElementById('modalPlatform').textContent = getPlatformText(button.dataset.platform);

    } catch (error) {
        console.error('리뷰 정보 로드 실패:', error);
        showAlert('리뷰 정보를 불러오는데 실패했습니다: ' + error.message, 'danger');
    }
}

/**
 * 답글 등록 확인 처리
 */
async function handleConfirmPostReply() {
    if (!currentReviewForPosting || !currentReviewForPosting.reviewId) {
        showAlert('오류: 등록할 답글 정보가 없습니다.', 'danger');
        return;
    }

    const reviewId = currentReviewForPosting.reviewId;

    // 이미 처리 중인지 확인
    if (processingReviews.has(reviewId)) {
        console.log('이미 답글 등록 중입니다:', reviewId);
        showAlert('이미 답글 등록이 진행 중입니다.', 'warning');
        return;
    }

    const confirmBtn = document.getElementById('confirmPostReplyBtn');
    const originalText = confirmBtn.innerHTML;

    // 처리 중 플래그 설정
    isPostingInProgress = true;

    try {
        // 처리 중 표시
        processingReviews.add(reviewId);
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 등록 중...';

        // 모달의 닫기 버튼도 비활성화
        const modalCloseButtons = document.querySelectorAll('#postReplyModal .btn-close, #postReplyModal .btn-secondary');
        modalCloseButtons.forEach(btn => btn.disabled = true);

        addDebugInfo(`답글 등록 시작: ${reviewId}`);

        const response = await fetch(`/api/reply-posting/${reviewId}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getToken()}`
            },
            body: JSON.stringify({
                reply_content: currentReviewForPosting.replyContent,
                auto_submit: true
            })
        });

        const result = await response.json();
        addDebugInfo(`답글 등록 응답: ${JSON.stringify(result)}`);

        if (response.ok && result.success) {
            // 이미 등록된 경우도 성공으로 처리
            if (result.status === 'already_posted') {
                showAlert('이미 답글이 등록되어 있습니다.', 'info');
            } else {
                showAlert('답글이 성공적으로 등록되었습니다! 🎉', 'success');
            }

            // 모달 닫기
            const modal = bootstrap.Modal.getInstance(document.getElementById('postReplyModal'));
            modal.hide();

            // 리뷰 목록 새로고침
            setTimeout(() => {
                loadReviews();
            }, 1500);

        } else {
            // 이미 등록된 경우 처리
            if (result.status === 'already_posted' || result.message?.includes('이미 답글이 등록')) {
                showAlert('이미 답글이 등록되어 있습니다.', 'info');
                // 모달 닫기
                const modal = bootstrap.Modal.getInstance(document.getElementById('postReplyModal'));
                modal.hide();
                // 리뷰 목록 새로고침
                setTimeout(() => {
                    loadReviews();
                }, 1500);
            } else {
                throw new Error(result.detail || result.message || '답글 등록에 실패했습니다.');
            }
        }

    } catch (error) {
        console.error('답글 등록 오류:', error);
        addDebugInfo(`답글 등록 실패: ${error.message}`);
        showAlert(`답글 등록 실패: ${error.message}`, 'danger');
    } finally {
        // 처리 완료 표시
        processingReviews.delete(reviewId);
        isPostingInProgress = false;

        // 버튼 상태 원상복구
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = originalText;

        // 모달 버튼들도 활성화
        const modalCloseButtons = document.querySelectorAll('#postReplyModal .btn-close, #postReplyModal .btn-secondary');
        modalCloseButtons.forEach(btn => btn.disabled = false);
    }
}

/**
 * 매장별 모든 답글 일괄 등록
 */
async function handleBatchPostAll() {
    if (!currentStoreCode) {
        showAlert('매장을 먼저 선택해주세요.', 'warning');
        return;
    }

    if (!confirm('이 매장의 모든 대기 중인 답글을 등록하시겠습니까?\n\n※ 실제 플랫폼에 답글이 게시됩니다.')) {
        return;
    }

    await performBatchPosting('all', '모든 답글');
}

/**
 * AI 생성된 답글만 일괄 등록
 */
async function handleBatchPostGenerated() {
    if (!currentStoreCode) {
        showAlert('매장을 먼저 선택해주세요.', 'warning');
        return;
    }

    if (!confirm('이 매장의 AI 생성된 답글을 모두 등록하시겠습니까?')) {
        return;
    }

    await performBatchPosting('generated', 'AI 생성된 답글');
}

/**
 * 등록 준비된 답글만 일괄 등록
 */
async function handleBatchPostReady() {
    if (!currentStoreCode) {
        showAlert('매장을 먼저 선택해주세요.', 'warning');
        return;
    }

    if (!confirm('이 매장의 등록 준비된 답글을 모두 등록하시겠습니까?')) {
        return;
    }

    await performBatchPosting('ready_to_post', '등록 준비된 답글');
}

/**
 * 일괄 등록 실행
 */
async function performBatchPosting(type, description) {
    const button = event.target;
    const originalText = button.innerHTML;

    try {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 일괄 등록 중...';

        addDebugInfo(`일괄 등록 시작: ${type} - ${currentStoreCode}`);

        const filters = {};
        if (type === 'generated') {
            filters.status = ['generated'];
        } else if (type === 'ready_to_post') {
            filters.status = ['ready_to_post'];
        } else {
            filters.status = ['generated', 'ready_to_post'];
        }

        const response = await fetch(`/api/reply-posting/batch/${currentStoreCode}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getToken()}`
            },
            body: JSON.stringify({
                filters: filters,
                auto_submit: true
            })
        });

        const result = await response.json();
        addDebugInfo(`일괄 등록 응답: ${JSON.stringify(result)}`);

        if (response.ok && result.success) {
            const message = `${description} ${result.posted_count}개가 성공적으로 등록되었습니다! 🎉
            ${result.failed_count > 0 ? `\n실패: ${result.failed_count}개` : ''}`;

            showAlert(message, 'success');

            // 리뷰 목록 새로고침
            setTimeout(() => {
                loadReviews();
                loadStats();
            }, 2000);

        } else {
            throw new Error(result.detail || result.message || '일괄 등록에 실패했습니다.');
        }

    } catch (error) {
        console.error('일괄 등록 오류:', error);
        addDebugInfo(`일괄 등록 실패: ${error.message}`);
        showAlert(`일괄 등록 실패: ${error.message}`, 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

/**
 * 매장 선택시 일괄 처리 섹션 표시/숨김
 */
function toggleBatchActionsSection(storeCode) {
    const batchSection = document.getElementById('batchActionsSection');
    if (batchSection) {
        if (storeCode) {
            batchSection.style.display = 'block';
            // 버튼들에 store_code 설정
            document.getElementById('batchPostAll').dataset.storeCode = storeCode;
            document.getElementById('batchPostGenerated').dataset.storeCode = storeCode;
            document.getElementById('batchPostReady').dataset.storeCode = storeCode;
        } else {
            batchSection.style.display = 'none';
        }
    }
}

/**
 * 유틸리티 함수들
 */
function getReplyTypeText(method) {
    const methodMap = {
        'ai_auto': 'AI 자동생성',
        'ai_manual': 'AI 수동선택',
        'ai_retry': 'AI 재생성',
        'full_manual': '완전수동'
    };
    return methodMap[method] || method;
}

function getPlatformText(platform) {
    const platformMap = {
        'baemin': '배달의민족',
        'yogiyo': '요기요',
        'coupang': '쿠팡이츠'
    };
    return platformMap[platform] || platform;
}

// 기존 onStoreChange 함수 확장 (전역 범위에서 접근 가능하도록)
if (typeof window.originalOnStoreChange === 'undefined') {
    window.originalOnStoreChange = onStoreChange;

    window.onStoreChange = async function () {
        // 기존 로직 실행
        await window.originalOnStoreChange();

        // 일괄 처리 섹션 토글
        toggleBatchActionsSection(currentStoreCode);
    };
}

// 기존 displayReviews 함수 확장
if (typeof window.originalDisplayReviews === 'undefined') {
    window.originalDisplayReviews = displayReviews;

    window.displayReviews = function (reviews) {
        // 기존 로직 실행
        window.originalDisplayReviews(reviews);

        // 답글 등록 버튼 이벤트 리스너 추가
        document.querySelectorAll('.post-reply-btn').forEach(button => {
            button.addEventListener('click', function () {
                handlePostReplyClick(this);
            });
        });

        // 재시도 버튼 이벤트 리스너 추가
        document.querySelectorAll('.retry-reply-btn').forEach(button => {
            button.addEventListener('click', function () {
                handleRetryReply(this.dataset.reviewId);
            });
        });
    };
}

/**
 * 답글 재시도 처리
 */
async function handleRetryReply(reviewId) {
    try {
        const response = await fetch(`/api/reply-status/${reviewId}/retry`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (response.ok && result.success) {
            showAlert('답글 재시도가 시작되었습니다.', 'info');
            setTimeout(() => {
                loadReviews();
            }, 3000);
        } else {
            throw new Error(result.detail || '재시도 실패');
        }

    } catch (error) {
        console.error('답글 재시도 오류:', error);
        showAlert(`답글 재시도 실패: ${error.message}`, 'danger');
    }
}

console.log('[ReviewsReplyPosting] 답글 등록 스크립트 초기화 완료');