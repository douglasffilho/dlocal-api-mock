# KYC Verification - Technical Documentation

## Overview

A Flask-based web application for integrating with dLocal's KYC Verifications API (Remittances v1.1), Payments API, and Payouts API. This tool provides a unified interface for managing KYC verifications, creating remittance payments, and processing payouts.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Database Models](#database-models)
5. [Frontend Structure](#frontend-structure)
6. [dLocal API Integration](#dlocal-api-integration)
7. [Running the Application](#running-the-application)

---

## Architecture

```
kyc-verification/
├── app.py                 # Flask application (backend)
├── templates/
│   └── index.html         # Single-page application (frontend)
├── instance/
│   └── kyc_verifications.db  # SQLite database
├── venv/                  # Python virtual environment
└── requirements.txt       # Python dependencies
```

### Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy
- **Database**: SQLite
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **HTTP Client**: Python Requests library

---

## Authentication

### KYC & Payments API (HMAC-SHA256)

Uses dLocal's V2-HMAC-SHA256 signature scheme:

```python
# Signature generation
message = f"{login}{date_str}{body_json}"
signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()

# Headers
headers = {
    "X-Date": "2026-01-08T15:00:00.000Z",
    "X-Login": "<login>",
    "X-Trans-Key": "<transaction_key>",
    "Authorization": "V2-HMAC-SHA256, Signature: <signature>"
}
```

### Payouts API (Payload Signature)

Uses a different signature scheme with payload-based HMAC:

```python
# Signature generation (payload only)
payload_signature = hmac.new(secret_key, body_json, hashlib.sha256).hexdigest()

# Headers
headers = {
    "X-Date": "Thu, 08 Jan 2026 15:00:00 GMT",
    "X-Login": "<login>",
    "X-Trans-Key": "<transaction_key>",
    "payload-signature": "<payload_signature>",
    "Content-Type": "application/json"
}

# Body includes
{
    "login": "<login>",
    "pass": "<transaction_key>",
    "signature": true,
    ...
}
```

---

## API Endpoints

### Local Storage Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/local/verifications` | List all saved verifications |
| DELETE | `/api/local/verifications/<id>` | Delete verification by local ID |
| DELETE | `/api/local/verifications/<verification_id>` | Delete by verification ID |
| GET | `/api/local/verifications/<verification_id>/documents` | List saved documents |
| GET | `/api/local/verifications/approved` | Get approved verifications |
| GET | `/api/local/remitters/approved` | Get approved remitters |
| GET | `/api/local/beneficiaries/approved` | Get approved beneficiaries |
| GET | `/api/local/payments` | List all saved payments |
| DELETE | `/api/local/payments/<id>` | Delete payment by local ID |
| GET | `/api/local/payouts` | List all saved payouts |
| DELETE | `/api/local/payouts/<id>` | Delete payout by local ID |

### KYC Verification Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/verifications` | Create new verification (Remitter/Beneficiary) |
| POST | `/api/verifications/<verification_id>` | Get verification details |
| POST | `/api/verifications/<verification_id>/documents` | Get verification documents |
| POST | `/api/verifications/<verification_id>/documents/<document_id>` | Upload document |
| PATCH | `/api/verifications/<verification_id>/state` | Update verification state (Sandbox only) |
| POST | `/api/payments/<payment_id>` | Get payment details |

### Payment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payments` | Create remittance payment |

### Payout Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/payouts` | Create payout (cashout) |

---

## Database Models

### Verification

```python
class Verification(db.Model):
    id                  # Primary key
    verification_id     # dLocal verification ID (unique)
    user_id             # User ID returned when approved
    client_type         # REMITTER or BENEFICIARY
    first_name          # Client first name
    last_name           # Client last name
    document_number     # Document number
    external_reference  # External reference
    status              # CREATED, PENDING, APPROVED, REJECTED
    environment         # sandbox or production
    created_at          # Timestamp
    raw_response        # Full API response (JSON)
```

### Document

```python
class Document(db.Model):
    id              # Primary key
    verification_id # Associated verification ID
    document_id     # dLocal document ID
    document_type   # Document type
    status          # PENDING, UPLOADED, APPROVED, REJECTED
    created_at      # Timestamp
```

### Payment

```python
class Payment(db.Model):
    id                      # Primary key
    payment_id              # dLocal payment ID (unique)
    order_id                # Merchant order ID
    amount                  # Payment amount
    currency                # Payment currency
    country                 # Payment country
    payment_method_id       # Payment method
    status                  # PAID, PENDING, REJECTED, etc.
    status_detail           # Detailed status description
    status_code             # Status code
    remitter_user_id        # KYC remitter ID
    beneficiary_user_id     # KYC beneficiary ID
    environment             # sandbox or production
    created_at              # Timestamp
    raw_response            # Full API response (JSON)
```

### Payout

```python
class Payout(db.Model):
    id                      # Primary key
    external_id             # Merchant external ID (unique - main identifier)
    payout_id               # dLocal payout ID from API response
    amount                  # Payout amount
    currency                # Payout currency
    country                 # Payout country
    bank_account            # Bank account number
    status                  # COMPLETED, PENDING, FAILED, etc.
    status_detail           # Detailed status description
    remitter_user_id        # KYC remitter ID
    beneficiary_user_id     # KYC beneficiary ID
    purpose                 # Purpose code
    environment             # sandbox or production
    created_at              # Timestamp
    raw_response            # Full API response (JSON)
```

**Note:** Payouts are identified primarily by `external_id` (the ID you provide when creating the payout), not by the API's response ID.

---

## Frontend Structure

### Pages/Tabs

1. **Overview** - Dashboard showing verification, payment, and payout statistics with ability to refresh statuses
2. **Create** - Create new Remitter or Beneficiary verifications
3. **Get Details** - Retrieve verification status and details
4. **Documents** - View required documents for a verification
5. **Upload** - Upload documents for verification
6. **Update State** - Update verification state for testing (Sandbox only)
7. **Payment** - Create remittance payments
8. **Payment Status** - View detailed payment status and information
9. **Payouts** - Create payouts/cashouts
10. **Docs** - API documentation and examples

### Credential Management

- Credentials stored in browser localStorage
- Support for multiple saved profiles
- Environment toggle (Sandbox/Production)

---

## dLocal API Integration

### Base URLs

| Environment | URL |
|-------------|-----|
| Sandbox | `https://sandbox.dlocal.com` |
| Production | `https://api.dlocal.com` |

### KYC Verifications

**Create Verification**
```
POST /kyc/verifications
Content-Type: multipart/form-data
Body: { "body": <JSON payload> }
```

**Get Verification**
```
GET /kyc/verifications/{verification_id}?include=client_data
```

**Get Documents**
```
GET /kyc/verifications/{verification_id}/documents
```

**Upload Document**
```
PATCH /kyc/verifications/{verification_id}/documents/{document_id}
Content-Type: multipart/form-data
Body: { "file": <file> }
```

**Update Verification State (Sandbox Only)**
```
PATCH /kyc/sanbox-tools/verifications/{verification_id}
Content-Type: application/json
Body: { 
  "status": "<NEW_STATUS>",
  "status_detail": "<DESCRIPTION>"
}
```

⚠️ **Note:** The dLocal API documentation contains a typo - the endpoint uses "sanbox-tools" instead of "sandbox-tools".

This endpoint allows you to modify a verification's status in the sandbox environment for testing state transitions. The API preserves the verification's actual flow upon reaching the updated state, allowing you to simulate state transitions and receive notifications for those states.

**Available Status Values with Valid Status Details:**

**CREATING (300)**
- `creating` - Verification is being created

**PENDING (100-104)**
- `pending` - Verification is pending
- `documentation` - Verification is pending documentation
- `compliance_review` - Verification is pending review by compliance
- `resubmit_documentation` - Verification requires resubmission

**APPROVED (200)**
- `approved` - Verification is approved
- `approved_bypassed` - Approved bypassed

**REJECTED (500-506)**
- `rejected` - Verification is rejected
- `validation_legal_issues` - Verification rejected due to legal issues
- `invalid_taxid` - Verification rejected due to invalid KYC
- `high_risk` - Verification rejected due to high risk

**EXPIRED (600-602)**
- `expired` - Verification expired
- `expired_doc_not_completed` - Verification expired because documentation completion period elapsed
- `expired_period_of_validaity` - Verification expired due to the expiration date

**ERROR (700)**
- `error` - An error has occurred

**Required Fields:**
- `status` - The new status value (must be one of: CREATING, PENDING, APPROVED, REJECTED, EXPIRED, ERROR)
- `status_detail` - The specific status detail (must be one of the valid values for the chosen status)

Reference: [dLocal Verification Status Documentation](https://docs.dlocal.com/reference/verification-status)

### Payments (Payins)

**Create Payment**

⚠️ **Important:** dLocal uses different endpoints based on how you're paying:
- **Direct card information** (number, cvv): Use `/secure_payments`
- **Token or saved card_id**: Use `/payments`

The application automatically selects the correct endpoint based on the payment method.

```
POST /secure_payments  (for direct card info)
POST /payments         (for tokens/card_id)
Content-Type: application/json
```

**Request Body**
```json
{
    "amount": 100.00,
    "currency": "ARS",
    "country": "AR",
    "payment_method_id": "IO",
    "payment_method_flow": "DIRECT",
    "payer": {
        "name": "John Doe",
        "email": "john@example.com",
        "document": "12345678"
    },
    "order_id": "PAY-123456",
    "description": "200",
    "remitter_user_id": "KV-xxxxx",
    "beneficiary_user_id": "KV-xxxxx",
    "subpurpose": "EPREFA",
    "source_of_funds": "SAVINGS",
    "signature": true
}
```

**Sandbox Testing**

In sandbox mode, control payment outcomes using the `description` field:

| Description | Status   | Meaning                  |
|-------------|----------|--------------------------|
| "200"       | PAID     | Payment approved         |
| "300"       | REJECTED | Generic rejection        |
| "302"       | REJECTED | Insufficient funds       |

**Test Card Data** (for sandbox):
- Card Number: `4111111111111111`
- CVV: `123`
- Expiration: `10/2040`
- Holder Name: Any name

Reference: [dLocal Sandbox Testing Guide](https://docs.dlocal.com/docs/make-a-test-payment)

**Get Payment Details**
```
GET /payments/{payment_id}/details
```

Retrieves full payment information including status, amounts, and transaction details. The application automatically saves payment information to the local database and displays it in the Overview tab.

Reference: [dLocal Get Payment API](https://docs.dlocal.com/reference/retrieve-a-payment)

### Payouts (Cashouts)

**Create Payout**
```
POST /api_curl/cashout_api/request_cashout
Content-Type: application/json
```

**Request Body**
```json
{
    "login": "<login>",
    "pass": "<transaction_key>",
    "external_id": "PAYOUT-123",
    "country": "AR",
    "bank_code": "0",
    "bank_name": "Billetera Virtual",
    "bank_province": "Jujuy",
    "bank_account": "0000076500000035601368",
    "account_type": "C",
    "amount": "4000.00",
    "currency": "ARS",
    "purpose": "EPREMT",
    "remitter_user_id": "KV-xxxxx",
    "beneficiary_user_id": "KV-xxxxx",
    "subpurpose": "EPREFA",
    "source_of_funds": "SAVINGS",
    "signature": true
}
```

---

## Purpose & Subpurpose Codes

### Purpose Codes

| Code | Description |
|------|-------------|
| EPREMT | Remittance Transfer |
| EPRESE | Salary/Employment |
| EPREPD | Payment for Services |

### Subpurpose Codes

| Code | Description |
|------|-------------|
| EPREFA | Family Allowance |
| EPREGS | Goods and Services |
| EPRETE | Travel Expenses |
| EPRESI | Savings or Investments |
| EPREGI | Gifts |

### Source of Funds

- SAVINGS
- SALARY
- DONATION
- BUSINESS
- PENSION
- INHERITANCE
- LOAN

---

## Running the Application

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# Clone or navigate to project
cd kyc-verification

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
# Activate virtual environment
source venv/bin/activate

# Run Flask app
python app.py
```

Server runs at: `http://127.0.0.1:5000`

### Dependencies

```
Flask==3.1.2
Flask-SQLAlchemy==3.1.1
requests==2.32.5
```

---

## Error Handling

### Common dLocal Error Codes

| Code | Description |
|------|-------------|
| 301 | Empty param control - Missing required parameter |
| 401 | Unauthorized - Invalid credentials or signature |
| 404 | Not found - Resource doesn't exist |
| 5300 | Invalid signature |

### Troubleshooting

1. **SSL Errors**: Ensure the server has network access (not sandboxed)
2. **Signature Errors**: Verify credentials and signature calculation
3. **Empty Param Errors**: Check all required fields are populated
4. **404 on Verification**: User may not exist yet (needs approval)

---

## Security Notes

- Credentials are stored in browser localStorage (client-side only)
- Secret keys are never logged or exposed in API responses
- Use HTTPS in production
- Database contains raw API responses - secure appropriately

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial release with KYC, Payments |
| 1.1 | Jan 2026 | Added Payouts section, Payment Status tab |
| 1.2 | Jan 2026 | Added Payouts Overview to dashboard |

---

## References

- [dLocal KYC Verifications API](https://docs.dlocal.com/reference/kyc-verifications)
- [dLocal Payments API](https://docs.dlocal.com/reference/payments)
- [dLocal Payouts API](https://docs.dlocal.com/docs/integrate-payouts-v3)

