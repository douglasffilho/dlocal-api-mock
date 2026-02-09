# KYC Verification App

A Flask-based web application for integrating with **dLocal's KYC Verifications API** (Remittances v1.1), **Payments API**, and **Payouts API**. It provides a unified interface for managing KYC verifications, remittance payments, and payouts.

---

## Documentation

**For architecture, API details, authentication, database models, and troubleshooting, see:**

**[TECHNICAL_DOCS.md](./TECHNICAL_DOCS.md)**

The technical documentation covers:

- Architecture and tech stack
- Authentication (HMAC-SHA256 for KYC/Payments, payload signature for Payouts)
- All API endpoints (local storage, KYC, payments, payouts)
- Database models and frontend structure
- dLocal API integration and sandbox usage
- Error handling and security notes

---

## Quick Start

### Prerequisites

- Python 3.x

### Install and run

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

### Dependencies

- Flask
- Flask-SQLAlchemy
- requests

See [requirements.txt](./requirements.txt) for versions.

---

## Project structure

```
kyc-verification-app/
├── app.py              # Flask backend
├── templates/
│   └── index.html      # Single-page frontend
├── instance/           # SQLite DB (created on first run)
├── requirements.txt
├── README.md
└── TECHNICAL_DOCS.md   # Full technical documentation
```

---

## References

- [dLocal KYC Verifications API](https://docs.dlocal.com/reference/kyc-verifications)
- [dLocal Payments API](https://docs.dlocal.com/reference/payments)
- [dLocal Payouts API](https://docs.dlocal.com/docs/integrate-payouts-v3)
