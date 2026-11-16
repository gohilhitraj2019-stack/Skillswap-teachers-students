# 🤝 SKILL SWAP — MVP

**Skill Swap** is an online peer-to-peer skill-sharing marketplace connecting Students and Teachers through one-on-one live online classes. Users can learn or teach or both, powered by an escrow-backed, double-entry credit wallet system.

---

## 🚀 Key Highlights & Architectural Guarantees

- **18 Complete Modules**: Authentication, Teacher Verification, Profile Studio, Search & Discovery, Escrow Credit Wallet, Payment Gateway & Simulator, WebRTC Live Video Classroom, Real-time Chat & Doubt Solving, Review System, Notifications, and Admin Control Center.
- **Financial Ledger Integrity**:
  - Wallets are managed via atomic transactions.
  - Balances never drop below zero.
  - Held credits in booking escrow are protected from double spending.
  - Automatic settlement upon class completion: 100% credit deduction from student held balance, configurable platform commission (e.g. 20%), and net earnings credited to teacher.
  - Automatic refunds back to available balance on cancellations or declines.
  - Immutable ledger recording every event (`free_trial`, `purchase`, `hold`, `unhold_refund`, `settle_debit`, `settle_credit`, `commission`, `withdrawal_hold`, `withdrawal_payout`).
- **In-Browser WebRTC Peer Video & Socket.IO**:
  - Peer-to-peer audio/video streaming via Google STUN servers.
  - Camera toggle, microphone mute/unmute, and display screen sharing.
  - Real-time text chat + structured **Doubt Solver** where students post doubts and teachers can mark them resolved with a single click.
  - Direct meeting link integration and graceful fallback.
- **Payment Architecture**:
  - Razorpay Test Mode integration with signature verification (`HMAC-SHA256`).
  - Built-in **Development Payment Simulator** with transparent labeling and sandbox callbacks for instant evaluation without external keys.

---

## 📂 Project Structure

```
skill_swap/
├── app/
│   ├── __init__.py               # Flask application factory & context processors
│   ├── config.py                 # Configuration loader
│   ├── extensions.py             # SQLAlchemy, LoginManager, Migrate, SocketIO
│   │
│   ├── models/
│   │   ├── __init__.py           # Export all database models
│   │   ├── user.py               # User model & auth roles (student, teacher, admin)
│   │   ├── teacher.py            # TeacherProfile & Availability models
│   │   ├── skill.py              # SkillCategory, Skill, TeacherSkill models
│   │   ├── wallet.py             # Wallet model (available, held, earned)
│   │   ├── transaction.py        # CreditTransaction immutable ledger model
│   │   ├── booking.py            # Booking model with escrow & settlement tracking
│   │   ├── payment.py            # CreditPackage & Payment transaction models
│   │   ├── classroom.py          # ClassroomSession & ChatMessage models
│   │   ├── review.py             # Review & rating model
│   │   ├── notification.py       # Notification model
│   │   ├── withdrawal.py         # Withdrawal payout request model
│   │   └── settings.py           # PlatformSettings singleton model
│   │
│   ├── auth/                     # User registration & authentication routes
│   ├── student/                  # Student dashboard, explore, profiles, bookings
│   ├── teacher/                  # Teacher studio, profile editor, earnings, withdrawals
│   ├── admin/                    # Admin dashboard, approvals, users, disputes, settings
│   ├── booking/                  # Booking creation, slot checking, cancellations
│   ├── wallet/                   # Wallet overview, credit packages, checkout, simulator
│   ├── classroom/                # Classroom view, session completion, Socket.IO WebRTC events
│   │
│   ├── services/
│   │   ├── credit_service.py     # Safe escrow, holds, releases, settlements
│   │   ├── payment_service.py    # Razorpay order generation & signature verification
│   │   ├── booking_service.py    # Slot overlap checks, accept, reject, complete
│   │   ├── notification_service.py # User alerts
│   │   └── payout_service.py     # Teacher withdrawal processing & approval
│   │
│   ├── templates/
│   │   ├── base.html             # Base layout with credit pill, nav, user dropdown
│   │   ├── index.html            # Landing page (hero, categories, teachers, how-it-works)
│   │   ├── auth/                 # Login, student registration, teacher application
│   │   ├── student/              # Student dashboard, explore, profile, bookings
│   │   ├── teacher/              # Teacher studio, profile editor, earnings, withdrawal
│   │   ├── booking/              # Class booking slot picker, confirmation
│   │   ├── wallet/               # Wallet ledger, credit packages, simulator
│   │   ├── classroom/            # Live video room, chat, doubt solver
│   │   └── admin/                # Admin dashboards, teacher approvals, settings
│   │
│   └── static/
│       ├── css/                  # style.css, dashboard.css, responsive.css
│       └── js/                   # main.js, booking.js, wallet.js, classroom.js
│
├── tests/
│   ├── conftest.py               # In-memory test fixtures and app setup
│   ├── test_auth.py              # Authentication & role tests
│   ├── test_wallet.py            # Financial ledger & commission settlement tests
│   ├── test_booking.py           # Slot overlap, booking lifecycle, escrow tests
│   ├── test_payments.py          # Payment orders & simulator tests
│   └── test_e2e_scenarios.py     # Full end-to-end acceptance lifecycle test
│
├── instance/                     # SQLite database file
├── .env.example                  # Environment configuration template
├── .env                          # Local environment variables
├── requirements.txt              # Production and dev dependencies
├── pytest.ini                    # Pytest configuration
├── seed.py                       # Realistic database seeder
├── run.py                        # Application entry point with SocketIO runner
└── README.md
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.13, Flask 3.1, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, Flask-SocketIO, `simple-websocket`
- **Database**: SQLite (local development) / PostgreSQL ready via SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, Jinja2 templates, JavaScript (ES6)
- **Real-Time Communication**: WebRTC (audio/video/screenshare with STUN servers) + Socket.IO (signaling, live chat, doubt solving)
- **Payment Processing**: Razorpay Test Mode + Integrated Development Payment Simulator
- **Testing**: Pytest

---

## ⚡ Quick Start: macOS Terminal Setup

### 1. Clone & Navigate
```bash
cd /path/to/Skillswap-teachers-students
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
```
*(By default, `.env` uses SQLite in `instance/skillswap.db` and enables the Development Payment Simulator)*

### 5. Initialize & Seed Database
```bash
python seed.py
```

### 6. Run the Application
```bash
python run.py
```
Open your browser and navigate to: **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

*(Note: Port 8080 is used by default because macOS Monterey/Ventura/Sonoma/Sequoia uses port 5000 for Apple AirPlay Receiver)*

---

## 🔑 Demo Accounts for Immediate Testing

Use these pre-seeded accounts or use the **1-Click Quick Demo Login** buttons on the Login page:

| Role | Email | Password | Details |
|---|---|---|---|
| **Admin** | `admin@skillswap.com` | `Admin@123` | Full access to approve teachers, view all wallets, manage settings, approve payouts |
| **Teacher (Approved)** | `sarah.dev@skillswap.com` | `Teacher@123` | Senior Python Teacher (6 yrs exp, 50 Cr/hr, 4.9★, 240 Cr earned balance) |
| **Teacher (Approved)** | `arjun.design@skillswap.com` | `Teacher@123` | Lead UI/UX & Figma Designer (5 yrs exp, 45 Cr/hr, 5.0★) |
| **Teacher (Pending)** | `alex.music@skillswap.com` | `Teacher@123` | Acoustic Guitar Teacher (Pending admin verification demo) |
| **Student** | `student@skillswap.com` | `Student@123` | Student with **100 credits** ready to book classes |

---

## 💳 Razorpay Test Mode Configuration

If you have Razorpay Test Keys:
1. Open your `.env` file.
2. Provide your test keys:
   ```env
   RAZORPAY_KEY_ID=rzp_test_YourKeyIdHere
   RAZORPAY_KEY_SECRET=YourKeySecretHere
   ENABLE_PAYMENT_SIMULATOR=False
   ```
3. Restart the server. The checkout page will automatically open the official Razorpay payment modal and verify signatures server-side.

**If keys are not provided:**
The platform automatically engages the **Development Payment Simulator**, clearly labeled with sandbox indicators, allowing full test coverage of payment verification and failure handling.

---

## 🧪 Running Automated Tests

Run the test suite verifying all 18 modules and financial constraints:

```bash
source .venv/bin/activate
pytest
```

To run with verbose output:
```bash
pytest -v
```

### Verified Test Results
- ✅ `test_auth.py`: Student registration, bonus credits, teacher application, duplicate email handling, login/logout.
- ✅ `test_wallet.py`: Escrow hold, balance validation, **100-credit class with 20% commission (Student loses 100, Teacher receives 80, Platform receives 20, duplicate settlement prevented)**, teacher withdrawal hold, and rejection refund.
- ✅ `test_booking.py`: Slot reservation, slot conflict prevention, booking acceptance, teacher decline credit refund.
- ✅ `test_payments.py`: Order generation, simulator checkout, balance update, failed payments.
- ✅ `test_e2e_scenarios.py`: Complete end-to-end lifecycle from teacher registration, admin approval, student signup, credit purchase, booking, classroom session, completion, settlement, review, and teacher withdrawal approval.

---

## 🛡️ Financial Ledger Reconciliation Test Proof

```
Class Charge: 100 Credits
Platform Commission: 20%

Initial:
- Student Available Balance: 100 Credits
- Teacher Earned Balance: 0 Credits

Step 1: Booking Confirmed (Escrow Hold)
- Student Available: 0 Credits
- Student Held Balance: 100 Credits

Step 2: Class Completed & Settled
- Student Held Balance: 0 Credits (permanently settled)
- Teacher Earned Balance: +80 Credits
- Platform Commission: +20 Credits
- Settlement Transaction Ref: Linked to booking (duplicate blocked)
- Ledger: Total Debited (100) == Total Credited (80 + 20)
```

---

## 🌐 External Credentials & Optional Integrations

The following integrations are pre-architected and configurable via `.env`:
1. **Razorpay Live/Test Gateway**: Provide `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`.
2. **PostgreSQL Migration**: Change `DATABASE_URL` to your PostgreSQL connection string (models are 100% SQLAlchemy PostgreSQL-compatible).
3. **TURN Server**: For strict enterprise firewalls, add TURN credentials to `rtcConfig` in `app/static/js/classroom.js` (default uses Google public STUN).
