"""
실시간 크롤링/답글 등록 모니터링 서비스
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass
from api.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

@dataclass
class CrawlMetric:
    """크롤링 메트릭 데이터 클래스"""
    platform: str
    store_code: str
    started_at: datetime
    completed_at: datetime = None
    status: str = "running"  # running, success, failed
    reviews_collected: int = 0
    error_message: str = ""
    login_attempts: int = 1
    login_success: bool = False

@dataclass
class ReplyMetric:
    """답글 등록 메트릭 데이터 클래스"""
    platform: str
    platform_code: str
    review_id: str
    started_at: datetime
    completed_at: datetime = None
    status: str = "processing"  # processing, posted, failed
    error_message: str = ""
    retry_count: int = 0

class MonitoringService:
    """실시간 모니터링 서비스"""
    
    def __init__(self, supabase_service: SupabaseService):
        self.supabase = supabase_service
        self.crawl_metrics: Dict[str, CrawlMetric] = {}
        self.reply_metrics: Dict[str, ReplyMetric] = {}
    
    async def start_crawl_tracking(self, platform: str, store_code: str) -> str:
        """크롤링 추적 시작"""
        tracking_id = f"{platform}_{store_code}_{int(datetime.now().timestamp())}"
        
        metric = CrawlMetric(
            platform=platform,
            store_code=store_code,
            started_at=datetime.now()
        )
        
        self.crawl_metrics[tracking_id] = metric
        
        # DB에 로그 저장
        await self._save_crawl_log(tracking_id, metric)
        
        logger.info(f"크롤링 추적 시작: {tracking_id}")
        return tracking_id
    
    async def complete_crawl_tracking(self, tracking_id: str, success: bool, 
                                     reviews_count: int = 0, error: str = ""):
        """크롤링 추적 완료"""
        if tracking_id not in self.crawl_metrics:
            logger.warning(f"추적 ID를 찾을 수 없음: {tracking_id}")
            return
        
        metric = self.crawl_metrics[tracking_id]
        metric.completed_at = datetime.now()
        metric.status = "success" if success else "failed"
        metric.reviews_collected = reviews_count
        metric.error_message = error
        
        # DB 업데이트
        await self._update_crawl_log(tracking_id, metric)
        
        # 실패율 체크
        await self._check_failure_rate("crawl", metric.platform)
        
        logger.info(f"크롤링 추적 완료: {tracking_id} - {'성공' if success else '실패'}")
    
    async def start_reply_tracking(self, platform: str, platform_code: str, review_id: str) -> str:
        """답글 등록 추적 시작"""
        tracking_id = f"{platform}_{platform_code}_{review_id}_{int(datetime.now().timestamp())}"
        
        metric = ReplyMetric(
            platform=platform,
            platform_code=platform_code,
            review_id=review_id,
            started_at=datetime.now()
        )
        
        self.reply_metrics[tracking_id] = metric
        
        # DB에 로그 저장
        await self._save_reply_log(tracking_id, metric)
        
        logger.info(f"답글 등록 추적 시작: {tracking_id}")
        return tracking_id
    
    async def complete_reply_tracking(self, tracking_id: str, success: bool, 
                                     error: str = "", retry_count: int = 0):
        """답글 등록 추적 완료"""
        if tracking_id not in self.reply_metrics:
            logger.warning(f"추적 ID를 찾을 수 없음: {tracking_id}")
            return
        
        metric = self.reply_metrics[tracking_id]
        metric.completed_at = datetime.now()
        metric.status = "posted" if success else "failed"
        metric.error_message = error
        metric.retry_count = retry_count
        
        # DB 업데이트
        await self._update_reply_log(tracking_id, metric)
        
        # 실패율 체크
        await self._check_failure_rate("reply", metric.platform)
        
        logger.info(f"답글 등록 추적 완료: {tracking_id} - {'성공' if success else '실패'}")
    
    async def get_realtime_stats(self) -> Dict[str, Any]:
        """실시간 통계 조회"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # 최근 1시간 크롤링 통계
        crawl_stats = await self._get_crawl_stats(one_hour_ago)
        
        # 최근 1시간 답글 등록 통계
        reply_stats = await self._get_reply_stats(one_hour_ago)
        
        return {
            "timestamp": now.isoformat(),
            "crawl_stats": crawl_stats,
            "reply_stats": reply_stats,
            "alerts": await self._get_active_alerts()
        }
    
    async def _save_crawl_log(self, tracking_id: str, metric: CrawlMetric):
        """크롤링 로그 저장"""
        try:
            await self.supabase.client.table('crawl_logs').insert({
                'tracking_id': tracking_id,
                'platform': metric.platform,
                'store_code': metric.store_code,
                'started_at': metric.started_at.isoformat(),
                'status': metric.status,
                'reviews_collected': metric.reviews_collected,
                'created_at': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"크롤링 로그 저장 실패: {e}")
    
    async def _update_crawl_log(self, tracking_id: str, metric: CrawlMetric):
        """크롤링 로그 업데이트"""
        try:
            await self.supabase.client.table('crawl_logs').update({
                'completed_at': metric.completed_at.isoformat() if metric.completed_at else None,
                'status': metric.status,
                'reviews_collected': metric.reviews_collected,
                'error_message': metric.error_message,
                'updated_at': datetime.now().isoformat()
            }).eq('tracking_id', tracking_id).execute()
        except Exception as e:
            logger.error(f"크롤링 로그 업데이트 실패: {e}")
    
    async def _save_reply_log(self, tracking_id: str, metric: ReplyMetric):
        """답글 등록 로그 저장"""
        try:
            await self.supabase.client.table('reply_logs').insert({
                'tracking_id': tracking_id,
                'platform': metric.platform,
                'platform_code': metric.platform_code,
                'review_id': metric.review_id,
                'started_at': metric.started_at.isoformat(),
                'status': metric.status,
                'created_at': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"답글 로그 저장 실패: {e}")
    
    async def _update_reply_log(self, tracking_id: str, metric: ReplyMetric):
        """답글 등록 로그 업데이트"""
        try:
            await self.supabase.client.table('reply_logs').update({
                'completed_at': metric.completed_at.isoformat() if metric.completed_at else None,
                'status': metric.status,
                'error_message': metric.error_message,
                'retry_count': metric.retry_count,
                'updated_at': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"답글 로그 업데이트 실패: {e}")
    
    async def _check_failure_rate(self, operation_type: str, platform: str):
        """실패율 체크 및 알림"""
        try:
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            if operation_type == "crawl":
                table = 'crawl_logs'
            else:
                table = 'reply_logs'
            
            # 최근 1시간 통계 조회
            result = await self.supabase.client.table(table).select('status').gte(
                'started_at', one_hour_ago.isoformat()
            ).eq('platform', platform).execute()
            
            if not result.data or len(result.data) < 5:  # 최소 5건 이상일 때만 체크
                return
            
            total_count = len(result.data)
            failed_count = len([r for r in result.data if r['status'] == 'failed'])
            failure_rate = (failed_count / total_count) * 100
            
            if failure_rate > 20:  # 20% 초과 실패율
                await self._send_alert(
                    f"{platform} {operation_type} 실패율 경고: {failure_rate:.1f}% ({failed_count}/{total_count})"
                )
                
        except Exception as e:
            logger.error(f"실패율 체크 오류: {e}")
    
    async def _send_alert(self, message: str):
        """알림 발송 (Discord/Slack)"""
        logger.warning(f"🚨 알림: {message}")
        
        # TODO: Discord/Slack 웹훅 연동
        try:
            # Discord 웹훅 예시
            # import aiohttp
            # webhook_url = "YOUR_DISCORD_WEBHOOK_URL"
            # async with aiohttp.ClientSession() as session:
            #     await session.post(webhook_url, json={"content": f"🚨 {message}"})
            pass
        except Exception as e:
            logger.error(f"알림 발송 실패: {e}")
    
    async def _get_crawl_stats(self, since: datetime) -> Dict[str, Any]:
        """크롤링 통계 조회"""
        try:
            result = await self.supabase.client.table('crawl_logs').select('*').gte(
                'started_at', since.isoformat()
            ).execute()
            
            stats = {"total": 0, "success": 0, "failed": 0, "running": 0, "by_platform": {}}
            
            for log in result.data:
                stats["total"] += 1
                stats[log["status"]] = stats.get(log["status"], 0) + 1
                
                platform = log["platform"]
                if platform not in stats["by_platform"]:
                    stats["by_platform"][platform] = {"total": 0, "success": 0, "failed": 0}
                
                stats["by_platform"][platform]["total"] += 1
                stats["by_platform"][platform][log["status"]] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"크롤링 통계 조회 실패: {e}")
            return {}
    
    async def _get_reply_stats(self, since: datetime) -> Dict[str, Any]:
        """답글 등록 통계 조회"""
        try:
            result = await self.supabase.client.table('reply_logs').select('*').gte(
                'started_at', since.isoformat()
            ).execute()
            
            stats = {"total": 0, "posted": 0, "failed": 0, "processing": 0, "by_platform": {}}
            
            for log in result.data:
                stats["total"] += 1
                stats[log["status"]] = stats.get(log["status"], 0) + 1
                
                platform = log["platform"]
                if platform not in stats["by_platform"]:
                    stats["by_platform"][platform] = {"total": 0, "posted": 0, "failed": 0}
                
                stats["by_platform"][platform]["total"] += 1
                stats["by_platform"][platform][log["status"]] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"답글 통계 조회 실패: {e}")
            return {}
    
    async def _get_active_alerts(self) -> List[str]:
        """활성 알림 목록"""
        # TODO: 실제 알림 로직 구현
        return []