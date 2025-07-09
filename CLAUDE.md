# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Korean e-commerce review management automation SaaS platform** that helps restaurant owners automatically:
- Crawl customer reviews from Korean food delivery platforms (Baemin, Yogiyo, Coupang Eats, Naver)
- Generate AI-powered responses using OpenAI GPT models
- Post replies automatically with 24/7 scheduling
- Manage multiple stores across different platforms

## Essential Commands

### Running the Application

```bash
# Start FastAPI server (development mode with reload)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Alternative: Run with main.py directly
python api/main.py

# Run with automation disabled (web server mode only)
export AUTO_START_JOBS=false
python -m uvicorn api.main:app --reload

# Run with immediate automation (auto mode)
export AUTO_START_JOBS=true
python -m uvicorn api.main:app --reload
```

### Testing

```bash
# Run all tests with async support
pytest --asyncio-mode=auto

# Run specific test suites
pytest tests/test_baemin_crawler.py
pytest tests/test_full_integration.py

# Test individual crawlers
python test_naver_crawler.py
python test_review_collector.py
```

### Code Quality

```bash
# Format code with black
black api/

# Check formatting without changes
black --check api/

# Run linter
flake8 api/

# Sort imports
isort api/
```

### Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install playwright browsers (required for crawlers)
playwright install
```

## Project Structure

```
/mnt/c/Review_playwright/
├── 📁 api/                         # FastAPI Backend Core
│   ├── main.py                     # Application entry point
│   ├── dependencies.py             # Dependency injection
│   ├── auth/                       # JWT authentication system
│   ├── routes/                     # API endpoints (auth, reviews, stores, replies)
│   ├── schemas/                    # Pydantic data models
│   ├── services/                   # Business logic layer
│   │   ├── ai_service.py           # OpenAI GPT integration
│   │   ├── review_collector_service.py # Review collection orchestration
│   │   ├── reply_posting_service.py # Reply posting orchestration
│   │   ├── supabase_service.py     # Database operations
│   │   └── platforms/              # Platform subprocess handlers
│   ├── crawlers/                   # Web crawling engines
│   │   ├── review_crawlers/        # Platform-specific review collection
│   │   ├── reply_managers/         # Platform-specific reply posting
│   │   ├── review_parsers/         # Review data parsing
│   │   └── store_crawlers/         # Store information crawling
│   └── utils/                      # Utility functions
├── 📁 config/                      # Configuration management
├── 📁 web/                         # Frontend (Jinja2 templates + JS)
│   ├── templates/                  # HTML templates
│   └── static/                     # CSS/JS assets
├── 📁 scripts/                     # Utility scripts
├── 📁 tests/                       # Test suite
├── 📁 logs/                        # Application logs
├── 📁 data/browser_data/           # Browser session persistence
├── 📁 docs/                        # Documentation
└── 📁 backups/                     # Code backups
```

## Architecture Overview

### Core Design Patterns

1. **Service-Oriented Architecture**: Each domain has its dedicated service (SupabaseService, AIService, ReviewCollectorService, etc.)
2. **Strategy Pattern**: Platform-specific implementations inherit from base classes (BaseCrawler, BaseReplyManager)
3. **Repository Pattern**: Database operations abstracted through SupabaseService
4. **Subprocess Isolation**: Browser automation runs in subprocesses to avoid async conflicts on Windows

### Key Components

**Backend Services:**
- `SupabaseService`: Database operations and data persistence
- `AIService`: OpenAI GPT integration for reply generation
- `ReviewCollectorService`: Orchestrates review collection across platforms
- `ReplyPostingService`: Manages reply posting workflow
- `EncryptionService`: Handles credential encryption/decryption
- `MonitoringService`: System health and performance monitoring

**Platform Crawlers:**
- `BaeminCrawler`: Baemin (배달의민족) review crawling and reply posting
- `YogiyoCrawler`: Yogiyo (요기요) platform automation
- `CoupangCrawler`: Coupang Eats integration
- `NaverCrawler`: Naver Place/Pay review management

### Critical Implementation Details

1. **Async/Sync Duality**: The project uses sync crawlers wrapped in subprocess calls due to Windows Playwright limitations. Never use async Playwright directly in Windows environment.

2. **Session Management**: Browser sessions are persisted in `data/browser_data/` to avoid repeated logins. Each platform/account combination has its own profile.

3. **Error Handling**: Comprehensive error logging with screenshots on failure. Errors are stored in both database and local logs.

4. **Reply Posting Workflow**:
   - Reviews collected → AI generates replies → 1-2 day delay → Batch by platform → Post via browser automation
   - Boss reviews (질문형) flagged for 2-day delay
   - Platform-specific forbidden words detection

5. **Credential Security**: Platform credentials encrypted using Fernet before database storage. Never log or expose decrypted credentials.

## Platform-Specific Notes

### Baemin
- Requires platform_code in addition to ID/password
- Complex popup handling for reply posting
- Session expires after ~30 days

### Yogiyo
- Store ID format: yo_[numeric_id]
- Simpler authentication than Baemin
- No platform_code required

### Coupang Eats
- Uses store_id directly from URL
- Contract-based review replies
- Strict rate limiting

### Naver
- Different login flow (Naver ID)
- Place ID required for store identification
- Review replies through "답글" button

## Common Development Tasks

### Adding a New Platform Crawler

1. Create crawler in `api/crawlers/review_crawlers/[platform]_sync_review_crawler.py`
2. Inherit from `BaseSyncReviewCrawler`
3. Implement required methods: `login()`, `get_reviews()`, `post_reply()`
4. Add subprocess handler in `api/services/platforms/`
5. Update `ReviewCollectorService` to include new platform

### Debugging Crawlers

```bash
# Enable debug mode with screenshots
export DEBUG=true

# Check browser automation locally
python api/crawlers/review_crawlers/[platform]_sync_review_crawler.py

# View error screenshots in logs/screenshots/
```

### Database Migrations

The project uses Supabase (PostgreSQL). Key tables:
- `users`: User accounts with roles
- `platform_reply_rules`: Store configurations
- `reviews`: Collected reviews and AI replies
- `subscriptions`: SaaS subscriptions
- `error_logs`: Error tracking

## Testing Approach

- Unit tests for individual services
- Integration tests for crawler workflows
- Use `pytest-asyncio` for async code
- Mock external services (OpenAI, Supabase) in tests
- Test data in `scripts/insert_test_review.py`

## Environment Variables

Key environment variables (see `.env.example`):
- `SUPABASE_URL`, `SUPABASE_KEY`: Database connection
- `OPENAI_API_KEY`: AI reply generation
- `JWT_SECRET_KEY`: Authentication
- `AUTO_START_JOBS`: Enable/disable automation on startup
- `DEBUG`: Enable debug logging and screenshots

## Database Schema (Supabase/PostgreSQL)

### Core Tables

**User Management:**
- `users` - User accounts with role-based access (admin, franchise, sales, owner)
- `subscriptions` - SaaS subscription management with pricing plans
- `payments` - Payment processing and billing history
- `usage_tracking` - Monthly usage limits and tracking per user
- `user_store_permissions` - N:N relationship for multi-user store access

**Store & Review Management:**
- `platform_reply_rules` - Store configurations with encrypted credentials
- `reviews` - All collected reviews with AI-generated replies
- `reply_generation_history` - AI reply generation attempts and versions
- `user_activity_logs` - User action tracking and audit logs

**System Operations:**
- `error_logs` - Comprehensive error tracking with categorization
- `alert_settings` - Multi-channel notification preferences
- `alert_logs` - Notification delivery tracking
- `api_keys` - API access management for enterprise users
- `system_settings` - Dynamic configuration management
- `feature_flags` - A/B testing and gradual feature rollouts

### Key Database Functions

**Subscription Management:**
```sql
check_subscription_status(user_code) -- Check active subscription and limits
update_usage(user_code, reviews_count, ...) -- Update monthly usage stats
process_expired_subscriptions() -- Daily cleanup of expired subscriptions
```

**Permission System:**
```sql
check_user_permission(user_code, store_code, action) -- Role-based access control
```

**Analytics:**
```sql
calculate_review_stats(store_code, start_date, end_date) -- Review performance metrics
check_api_rate_limit(api_key) -- API usage limit validation
```

### Important Database Patterns

1. **Encryption**: All platform credentials stored using Fernet encryption
2. **Audit Trail**: Complete user activity logging with IP tracking
3. **Soft Deletes**: Reviews marked as deleted rather than physically removed
4. **Rate Limiting**: Real-time API usage tracking with automatic reset
5. **Multi-tenancy**: Store-level isolation with user permission matrix

## Common Issues

1. **Windows Async Error**: Always use sync crawlers with subprocess. Never use async Playwright on Windows.
2. **Login Failures**: Check stored sessions in `data/browser_data/`. Delete profile to force fresh login.
3. **Reply Posting Fails**: Check for platform-specific popups or changed selectors. Enable DEBUG for screenshots.
4. **Import Errors**: Ensure proper PYTHONPATH or use `python -m` to run scripts from project root.
5. **Database Connection**: Verify SUPABASE_URL and SUPABASE_KEY in environment variables.
6. **Credential Encryption**: Platform passwords must be encrypted before database storage using EncryptionService.