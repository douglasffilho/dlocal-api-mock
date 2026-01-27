"""
KYC Verification Flask Application
Based on dLocal KYC Verifications API - Remittances v1.1
"""

import hmac
import hashlib
import json
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kyc_verifications.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# dLocal API endpoints
DLOCAL_SANDBOX_URL = "https://sandbox.dlocal.com"
DLOCAL_PRODUCTION_URL = "https://api.dlocal.com"


# ============================================
# Database Models
# ============================================

class Verification(db.Model):
    """Model to store created verifications."""
    id = db.Column(db.Integer, primary_key=True)
    verification_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.String(100))  # User ID returned when verification is approved
    client_type = db.Column(db.String(20), nullable=False)  # REMITTER or BENEFICIARY
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    document_number = db.Column(db.String(50))
    external_reference = db.Column(db.String(100))
    status = db.Column(db.String(50))
    environment = db.Column(db.String(20))  # sandbox or production
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    raw_response = db.Column(db.Text)  # Store full API response
    
    def to_dict(self):
        return {
            "id": self.id,
            "verification_id": self.verification_id,
            "user_id": self.user_id,
            "client_type": self.client_type,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "document_number": self.document_number,
            "external_reference": self.external_reference,
            "status": self.status,
            "environment": self.environment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "display_name": f"{self.first_name} {self.last_name} - {self.status or 'N/A'}"
        }


class Document(db.Model):
    """Model to store verification documents."""
    id = db.Column(db.Integer, primary_key=True)
    verification_id = db.Column(db.String(100), nullable=False)
    document_id = db.Column(db.String(100), nullable=False)
    document_type = db.Column(db.String(100))
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "verification_id": self.verification_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "status": self.status,
            "display_name": f"{self.document_type} - {self.document_id[:30]}..."
        }


class Payment(db.Model):
    """Model to store payment information."""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.String(100), unique=True, nullable=False)
    order_id = db.Column(db.String(100))
    amount = db.Column(db.Float)
    currency = db.Column(db.String(10))
    country = db.Column(db.String(10))
    payment_method_id = db.Column(db.String(50))
    status = db.Column(db.String(50))
    status_detail = db.Column(db.String(200))
    status_code = db.Column(db.String(10))
    remitter_user_id = db.Column(db.String(100))
    beneficiary_user_id = db.Column(db.String(100))
    environment = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    raw_response = db.Column(db.Text)
    
    def to_dict(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "order_id": self.order_id,
            "amount": self.amount,
            "currency": self.currency,
            "country": self.country,
            "payment_method_id": self.payment_method_id,
            "status": self.status,
            "status_detail": self.status_detail,
            "status_code": self.status_code,
            "remitter_user_id": self.remitter_user_id,
            "beneficiary_user_id": self.beneficiary_user_id,
            "environment": self.environment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "display_name": f"{self.payment_id} - {self.status or 'N/A'} - {self.currency} {self.amount}"
        }


class Payout(db.Model):
    """Model to store payout information."""
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True, nullable=False)
    payout_id = db.Column(db.String(100))
    amount = db.Column(db.Float)
    currency = db.Column(db.String(10))
    country = db.Column(db.String(10))
    bank_account = db.Column(db.String(100))
    status = db.Column(db.String(50))
    status_detail = db.Column(db.String(200))
    remitter_user_id = db.Column(db.String(100))
    beneficiary_user_id = db.Column(db.String(100))
    purpose = db.Column(db.String(50))
    environment = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    raw_response = db.Column(db.Text)
    
    def to_dict(self):
        return {
            "id": self.id,
            "external_id": self.external_id,
            "payout_id": self.payout_id,
            "amount": self.amount,
            "currency": self.currency,
            "country": self.country,
            "bank_account": self.bank_account,
            "status": self.status,
            "status_detail": self.status_detail,
            "remitter_user_id": self.remitter_user_id,
            "beneficiary_user_id": self.beneficiary_user_id,
            "purpose": self.purpose,
            "environment": self.environment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "display_name": f"{self.external_id} - {self.status or 'N/A'} - {self.currency} {self.amount}"
        }


# Create tables
with app.app_context():
    db.create_all()


# ============================================
# Helper Functions
# ============================================

def get_iso_date():
    """Get current date in ISO 8601 format."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def generate_signature(login: str, secret_key: str, date_str: str, body_str: str = "") -> str:
    """Generate HMAC-SHA256 signature for dLocal API authentication."""
    key = secret_key.encode('utf-8')
    message = f"{login}{date_str}{body_str}".encode('utf-8')
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return signature


def get_base_url(use_sandbox: bool = True) -> str:
    """Get the base URL for dLocal API."""
    return DLOCAL_SANDBOX_URL if use_sandbox else DLOCAL_PRODUCTION_URL


def make_headers(login: str, transaction_key: str, secret_key: str, date_str: str, body_str: str = "") -> dict:
    """Create headers for dLocal API request."""
    signature = generate_signature(login, secret_key, date_str, body_str)
    return {
        "X-Date": date_str,
        "X-Login": login,
        "X-Trans-Key": transaction_key,
        "Authorization": f"V2-HMAC-SHA256, Signature: {signature}",
    }


# ============================================
# KYC Request Body Builders
# ============================================

def create_remitter_body(form_data: dict) -> dict:
    """Create request body for Remitter verification."""
    return {
        "type": "REMITTANCE",
        "notification_url": form_data.get("notification_url", ""),
        "attributes": {
            "external_reference": form_data.get("external_reference", ""),
            "client": {
                "type": "REMITTER",
                "first_name": form_data.get("first_name", ""),
                "last_name": form_data.get("last_name", ""),
                "document_type": form_data.get("document_type", "TAX_ID"),
                "document_number": form_data.get("document_number", ""),
                "document_country": form_data.get("document_country", ""),
                "date_of_birth": form_data.get("date_of_birth", ""),
                "place_of_birth": form_data.get("place_of_birth", ""),
                "gender": form_data.get("gender", "MALE"),
                "nationality": form_data.get("nationality", ""),
                "marital_status": form_data.get("marital_status", ""),
                "phone": form_data.get("phone", ""),
                "email": form_data.get("email", ""),
                "is_pep": form_data.get("is_pep", False),
                "is_so": form_data.get("is_so", False),
                "profession": form_data.get("profession", ""),
                "source_of_funds": form_data.get("source_of_funds", ""),
                "consent": {
                    "type": "TERMS_AND_CONDITIONS",
                    "accepted": form_data.get("consent_accepted", True)
                },
                "address": {
                    "country": form_data.get("address_country", ""),
                    "city": form_data.get("address_city", ""),
                    "zip_code": form_data.get("address_zip_code", ""),
                    "state": form_data.get("address_state", ""),
                    "street_name": form_data.get("address_street_name", ""),
                    "street_number": form_data.get("address_street_number", "")
                }
            }
        }
    }


def create_beneficiary_body(form_data: dict) -> dict:
    """Create request body for Beneficiary verification."""
    # Build bank object with only non-empty fields
    bank = {"account_number": form_data.get("bank_account_number", "")}
    if form_data.get("bank_code"):
        bank["code"] = form_data.get("bank_code")
    if form_data.get("bank_branch"):
        bank["branch"] = form_data.get("bank_branch")
    if form_data.get("bank_account_type"):
        bank["account_type"] = form_data.get("bank_account_type")
    
    return {
        "type": "REMITTANCE",
        "notification_url": form_data.get("notification_url", ""),
        "attributes": {
            "external_reference": form_data.get("external_reference", ""),
            "client": {
                "type": "BENEFICIARY",
                "first_name": form_data.get("first_name", ""),
                "last_name": form_data.get("last_name", ""),
                "nationality": form_data.get("nationality", ""),
                "document_type": form_data.get("document_type", "TAX_ID"),
                "document_number": form_data.get("document_number", ""),
                "document_country": form_data.get("document_country", ""),
                "date_of_birth": form_data.get("date_of_birth", ""),
                "place_of_birth": form_data.get("place_of_birth", ""),
                "phone": form_data.get("phone", ""),
                "email": form_data.get("email", ""),
                "bank": bank,
                "address": {
                    "country": form_data.get("address_country", ""),
                    "city": form_data.get("address_city", ""),
                    "state": form_data.get("address_state", ""),
                    "zip_code": form_data.get("address_zip_code", ""),
                    "street_name": form_data.get("address_street_name", ""),
                    "street_number": form_data.get("address_street_number", "")
                }
            }
        }
    }


# ============================================
# API Response Handler
# ============================================

def handle_response(response, headers_sent, signature, date_str, body_sent=None):
    """Create standardized response object."""
    try:
        response_json = response.json() if response.text else {}
    except:
        response_json = {"raw": response.text}
    
    return {
        "success": response.ok,
        "status_code": response.status_code,
        "response": response_json,
        "response_headers": dict(response.headers),
        "headers_sent": {k: v for k, v in headers_sent.items() if k != "Authorization"},
        "signature": signature,
        "date": date_str,
        "body_sent": body_sent
    }


def handle_error(e, headers_sent, signature, date_str, body_sent=None):
    """Create error response object."""
    return {
        "success": False,
        "error": str(e),
        "response_headers": {},
        "headers_sent": {k: v for k, v in headers_sent.items() if k != "Authorization"},
        "signature": signature,
        "date": date_str,
        "body_sent": body_sent
    }


# ============================================
# Routes - Pages
# ============================================

@app.route("/")
def index():
    """Render the main KYC verification page."""
    return render_template("index.html")


# ============================================
# Routes - Local Verification Storage
# ============================================

@app.route("/api/local/verifications", methods=["GET"])
def list_verifications():
    """List all saved verifications."""
    verifications = Verification.query.order_by(Verification.created_at.desc()).all()
    return jsonify([v.to_dict() for v in verifications])


@app.route("/api/local/verifications/<int:id>", methods=["DELETE"])
def delete_verification_by_id(id):
    """Delete a saved verification by local ID."""
    verification = Verification.query.get_or_404(id)
    # Also delete associated documents
    Document.query.filter_by(verification_id=verification.verification_id).delete()
    db.session.delete(verification)
    db.session.commit()
    return jsonify({"success": True, "message": "Verification deleted"})


@app.route("/api/local/verifications/<verification_id>", methods=["DELETE"])
def delete_verification(verification_id):
    """Delete a saved verification by verification ID."""
    verification = Verification.query.filter_by(verification_id=verification_id).first_or_404()
    # Also delete associated documents
    Document.query.filter_by(verification_id=verification_id).delete()
    db.session.delete(verification)
    db.session.commit()
    return jsonify({"success": True, "message": "Verification deleted"})


@app.route("/api/local/verifications/<verification_id>/documents", methods=["GET"])
def list_local_documents(verification_id):
    """List saved documents for a verification."""
    documents = Document.query.filter_by(verification_id=verification_id).all()
    return jsonify([d.to_dict() for d in documents])


@app.route("/api/local/payments", methods=["GET"])
def list_payments():
    """List all saved payments."""
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payments])


@app.route("/api/local/payments/<int:id>", methods=["DELETE"])
def delete_payment_by_id(id):
    """Delete a saved payment by local ID."""
    payment = Payment.query.get_or_404(id)
    db.session.delete(payment)
    db.session.commit()
    return jsonify({"success": True, "message": "Payment deleted"})


@app.route("/api/local/payouts", methods=["GET"])
def list_payouts():
    """List all saved payouts."""
    payouts = Payout.query.order_by(Payout.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payouts])


@app.route("/api/local/payouts/<int:id>", methods=["DELETE"])
def delete_payout_by_id(id):
    """Delete a saved payout by local ID."""
    payout = Payout.query.get_or_404(id)
    db.session.delete(payout)
    db.session.commit()
    return jsonify({"success": True, "message": "Payout deleted"})


# ============================================
# Routes - Create Verification
# ============================================

@app.route("/api/verifications", methods=["POST"])
def create_verification():
    """Create a new KYC verification (Remitter or Beneficiary)."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    form_data = data.get("form_data", {})
    use_sandbox = data.get("use_sandbox", True)
    client_type = data.get("client_type", "REMITTER")
    
    # Validate credentials
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    # Build request body based on client type
    if client_type == "BENEFICIARY":
        body = create_beneficiary_body(form_data)
    else:
        body = create_remitter_body(form_data)
    
    # Prepare request
    date_str = get_iso_date()
    body_json = json.dumps(body)
    signature = generate_signature(login, secret_key, date_str, body_json)
    
    url = f"{get_base_url(use_sandbox)}/kyc/verifications"
    headers = make_headers(login, transaction_key, secret_key, date_str, body_json)
    
    # Send as form-data
    form_data_payload = {"body": (None, body_json, "text/plain")}
    
    try:
        response = requests.post(url, headers=headers, files=form_data_payload)
        result = handle_response(response, headers, signature, date_str, body)
        
        # Save successful verification to database (upsert)
        if response.ok and result.get("response", {}).get("id"):
            api_response = result["response"]
            verification_id = api_response.get("id")
            
            # Extract user_id from attributes.client.id
            client_data = api_response.get("attributes", {}).get("client", {})
            user_id = client_data.get("id")
            
            # Check if verification already exists
            existing = Verification.query.filter_by(verification_id=verification_id).first()
            
            if existing:
                # Update existing verification
                existing.status = api_response.get("status", existing.status)
                if user_id:
                    existing.user_id = user_id
                existing.raw_response = json.dumps(api_response)
                verification = existing
            else:
                # Create new verification
                verification = Verification(
                    verification_id=verification_id,
                    client_type=client_type,
                    first_name=form_data.get("first_name", ""),
                    last_name=form_data.get("last_name", ""),
                    document_number=form_data.get("document_number", ""),
                    external_reference=form_data.get("external_reference", ""),
                    status=api_response.get("status", "CREATED"),
                    user_id=user_id,
                    environment="sandbox" if use_sandbox else "production",
                    raw_response=json.dumps(api_response)
                )
                db.session.add(verification)
            
            db.session.commit()
            result["saved_locally"] = True
            result["local_id"] = verification.id
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str, body))


# ============================================
# Routes - Get Verification
# ============================================

@app.route("/api/verifications/<verification_id>", methods=["POST"])
def get_verification(verification_id):
    """Get verification details."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    use_sandbox = data.get("use_sandbox", True)
    include_client_data = data.get("include_client_data", False)
    
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    date_str = get_iso_date()
    signature = generate_signature(login, secret_key, date_str, "")
    
    # Always include client_data to get the user_id (client.id)
    url = f"{get_base_url(use_sandbox)}/kyc/verifications/{verification_id}?include=client_data"
    
    headers = make_headers(login, transaction_key, secret_key, date_str, "")
    
    try:
        response = requests.get(url, headers=headers)
        result = handle_response(response, headers, signature, date_str)
        result["request_url"] = url  # Debug: show the URL used
        
        # Update local verification status and user_id if exists
        if response.ok:
            api_response = result.get("response", {})
            local_verification = Verification.query.filter_by(verification_id=verification_id).first()
            if local_verification:
                local_verification.status = api_response.get("status", local_verification.status)
                # Save user_id (client.id) - it's in attributes.client.id when using include=client_data
                client_data = api_response.get("attributes", {}).get("client", {})
                result["client_data_found"] = client_data  # Debug
                if client_data.get("id"):
                    local_verification.user_id = client_data.get("id")
                    result["user_id_saved"] = client_data.get("id")
                local_verification.raw_response = json.dumps(api_response)
                db.session.commit()
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str))


# ============================================
# Routes - Get Documents
# ============================================

@app.route("/api/verifications/<verification_id>/documents", methods=["POST"])
def get_documents(verification_id):
    """Get verification documents."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    use_sandbox = data.get("use_sandbox", True)
    
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    date_str = get_iso_date()
    signature = generate_signature(login, secret_key, date_str, "")
    
    url = f"{get_base_url(use_sandbox)}/kyc/verifications/{verification_id}/documents"
    headers = make_headers(login, transaction_key, secret_key, date_str, "")
    
    try:
        response = requests.get(url, headers=headers)
        result = handle_response(response, headers, signature, date_str)
        
        # Save documents locally
        if response.ok:
            api_response = result.get("response", {})
            items = api_response.get("items", [])
            for item in items:
                doc_id = item.get("id")
                if doc_id:
                    existing = Document.query.filter_by(
                        verification_id=verification_id, 
                        document_id=doc_id
                    ).first()
                    if not existing:
                        doc = Document(
                            verification_id=verification_id,
                            document_id=doc_id,
                            document_type=item.get("type", "Unknown"),
                            status=item.get("status", "PENDING")
                        )
                        db.session.add(doc)
                    else:
                        existing.status = item.get("status", existing.status)
                        existing.document_type = item.get("type", existing.document_type)
            db.session.commit()
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str))


# ============================================
# Routes - Upload Document
# ============================================

@app.route("/api/verifications/<verification_id>/documents/<document_id>", methods=["POST"])
def upload_document(verification_id, document_id):
    """Upload/patch a document."""
    login = request.form.get("login")
    transaction_key = request.form.get("transaction_key")
    secret_key = request.form.get("secret_key")
    use_sandbox = request.form.get("use_sandbox", "true") == "true"
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    date_str = get_iso_date()
    signature = generate_signature(login, secret_key, date_str, "")
    
    url = f"{get_base_url(use_sandbox)}/kyc/verifications/{verification_id}/documents/{document_id}"
    headers = make_headers(login, transaction_key, secret_key, date_str, "")
    
    files = {
        "file": (file.filename, file.stream, file.content_type)
    }
    
    try:
        response = requests.patch(url, headers=headers, files=files)
        result = handle_response(response, headers, signature, date_str, {"file": file.filename})
        
        # Update document status locally
        if response.ok:
            doc = Document.query.filter_by(
                verification_id=verification_id,
                document_id=document_id
            ).first()
            if doc:
                api_response = result.get("response", {})
                doc.status = api_response.get("status", "UPLOADED")
                db.session.commit()
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str, {"file": file.filename}))


# ============================================
# Routes - Update Verification State (Sandbox Only)
# ============================================

@app.route("/api/verifications/<verification_id>/state", methods=["PATCH"])
def update_verification_state(verification_id):
    """
    Update verification state in sandbox environment (testing only).
    
    This endpoint allows you to simulate state transitions in sandbox for testing.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    use_sandbox = data.get("use_sandbox", True)
    new_status = data.get("status")
    status_detail = data.get("status_detail", "")
    
    # Validate credentials
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    if not new_status:
        return jsonify({"error": "Status is required"}), 400
    
    if not status_detail:
        return jsonify({"error": "Status detail is required"}), 400
    
    # This endpoint only works in sandbox
    if not use_sandbox:
        return jsonify({"error": "This endpoint only works in sandbox environment"}), 400
    
    # Build request body
    body = {
        "status": new_status,
        "status_detail": status_detail
    }
    
    # Prepare request
    date_str = get_iso_date()
    body_json = json.dumps(body)
    signature = generate_signature(login, secret_key, date_str, body_json)
    
    # Note: API docs have typo "sanbox-tools" instead of "sandbox-tools"
    url = f"{get_base_url(use_sandbox)}/kyc/sanbox-tools/verifications/{verification_id}"
    headers = make_headers(login, transaction_key, secret_key, date_str, body_json)
    headers["Content-Type"] = "application/json"
    
    try:
        response = requests.patch(url, headers=headers, data=body_json)
        result = handle_response(response, headers, signature, date_str, body)
        
        # Update local verification status if successful
        if response.ok:
            api_response = result.get("response", {})
            local_verification = Verification.query.filter_by(verification_id=verification_id).first()
            if local_verification:
                local_verification.status = api_response.get("status", new_status)
                local_verification.raw_response = json.dumps(api_response)
                db.session.commit()
                result["local_status_updated"] = True
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str, body))


# ============================================
# Routes - Get Approved Verifications
# ============================================

@app.route("/api/local/verifications/approved", methods=["GET"])
def get_approved_verifications():
    """Get approved verifications grouped by client type."""
    client_type = request.args.get("client_type")
    
    query = Verification.query.filter(
        Verification.status == "APPROVED",
        Verification.user_id.isnot(None)
    )
    
    if client_type:
        query = query.filter(Verification.client_type == client_type)
    
    verifications = query.order_by(Verification.created_at.desc()).all()
    
    return jsonify([v.to_dict() for v in verifications])


@app.route("/api/local/remitters/approved", methods=["GET"])
def get_approved_remitters():
    """Get approved remitters - use verification_id as user_id for payments."""
    remitters = Verification.query.filter(
        Verification.client_type == "REMITTER",
        Verification.status == "APPROVED"
    ).order_by(Verification.created_at.desc()).all()
    
    # For remittance verifications, the verification_id IS the user_id for payments
    result = []
    for r in remitters:
        data = r.to_dict()
        # Use verification_id as the payment user_id (per dLocal docs)
        data["payment_user_id"] = r.user_id or r.verification_id
        result.append(data)
    
    return jsonify(result)


@app.route("/api/local/beneficiaries/approved", methods=["GET"])
def get_approved_beneficiaries():
    """Get approved beneficiaries - use verification_id as user_id for payments."""
    beneficiaries = Verification.query.filter(
        Verification.client_type == "BENEFICIARY",
        Verification.status == "APPROVED"
    ).order_by(Verification.created_at.desc()).all()
    
    # For remittance verifications, the verification_id IS the user_id for payments
    result = []
    for b in beneficiaries:
        data = b.to_dict()
        # Use verification_id as the payment user_id (per dLocal docs)
        data["payment_user_id"] = b.user_id or b.verification_id
        result.append(data)
    
    return jsonify(result)


# ============================================
# Routes - Create Payment
# ============================================

@app.route("/api/payments", methods=["POST"])
def create_payment():
    """
    Create a remittance payment.
    
    Requires approved remitter and beneficiary user_ids.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    payment_data = data.get("payment_data", {})
    use_sandbox = data.get("use_sandbox", True)
    
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    # Build payment request body for remittance
    payment_method_id = payment_data.get("payment_method_id", "IO")  # IO = Instant, BT = Bank Transfer, CARD = Card
    
    # Build payer object with required fields
    payer = {
        "name": payment_data.get("payer_name", ""),
        "document": payment_data.get("payer_document", "")
    }
    
    # Only add email if it's not empty (some payment methods don't require it)
    payer_email = payment_data.get("payer_email", "")
    if payer_email:
        payer["email"] = payer_email
    
    body = {
        "amount": payment_data.get("amount"),
        "currency": payment_data.get("currency", "ARS"),
        "country": payment_data.get("country", "AR"),
        "payment_method_id": payment_method_id,
        "payment_method_flow": "DIRECT",
        "payer": payer,
        "order_id": payment_data.get("external_reference", ""),
        # Remittance specific fields
        "remitter_user_id": payment_data.get("remitter_user_id"), # KYC Verification ID
        "beneficiary_user_id": payment_data.get("beneficiary_user_id"), # KYC Verification ID
        "subpurpose": payment_data.get("subpurpose", "EPREFA"),  # Family Allowance
        "source_of_funds": payment_data.get("source_of_funds", "SAVINGS"),
    }
    
    # Add notification_url only if provided
    if payment_data.get("notification_url"):
        body["notification_url"] = payment_data.get("notification_url")
    
    # Add card data if payment method is CARD
    if payment_method_id == "CARD" and payment_data.get("card"):
        card_data = payment_data.get("card")
        if card_data.get("token"):
            # Using Smart Fields token
            capture_value = card_data.get("capture", "true")
            body["card"] = {
                "token": card_data.get("token"),
                "capture": capture_value == "true" or capture_value is True
            }
        else:
            # Direct card details
            capture_value = card_data.get("capture", "true")
            # Sanitize card number - remove spaces and dashes
            card_number = card_data.get("number", "").replace(" ", "").replace("-", "")
            
            body["card"] = {
                "holder_name": card_data.get("holder_name", ""),
                "number": card_number,  # Keep as string
                "cvv": card_data.get("cvv", ""),
                "expiration_month": int(card_data.get("expiration_month")) if card_data.get("expiration_month") else None,
                "expiration_year": int(card_data.get("expiration_year")) if card_data.get("expiration_year") else None,
                "capture": capture_value == "true" or capture_value is True
            }
    
    # Add optional fields if provided
    if payment_data.get("description"):
        body["description"] = payment_data.get("description")
    
    # Add signature flag to body
    body["signature"] = True
    
    # Prepare request
    date_str = get_iso_date()
    
    # Create body JSON - signature is computed on this exact string
    # Using standard JSON format (with spaces) to match Postman
    body_json = json.dumps(body)
    
    # For Payins/Payments API, signature is: login + date + body
    # The working Postman script shows: message = login + timestamp + body
    signature = generate_signature(login, secret_key, date_str, body_json)
    
    # Determine which endpoint to use based on card payment type
    # - Use /secure_payments for direct card information (number, cvv)
    # - Use /payments for tokens or card_id
    base = "https://sandbox.dlocal.com" if use_sandbox else "https://api.dlocal.com"
    
    use_secure_endpoint = False
    if payment_method_id == "CARD" and payment_data.get("card"):
        card_data = payment_data.get("card")
        # Check if using direct card information (has number and cvv)
        if card_data.get("number") and not card_data.get("token") and not card_data.get("card_id"):
            use_secure_endpoint = True
    
    url = f"{base}/secure_payments" if use_secure_endpoint else f"{base}/payments"
    
    # Build headers for JSON request (matching working curl)
    # The signature goes in the Authorization header
    headers = {
        "X-Date": date_str,
        "X-Login": login,
        "X-Trans-Key": transaction_key,
        "Content-Type": "application/json",
        "Authorization": f"V2-HMAC-SHA256, Signature: {signature}"
    }
    
    # Debug info
    message_for_signature = f"{login}{date_str}{body_json}"
    
    # Print debug info to console
    print("=" * 50)
    print("PAYMENT REQUEST DEBUG")
    print("=" * 50)
    print(f"Endpoint Type: {'SECURE_PAYMENTS (direct card info)' if use_secure_endpoint else 'PAYMENTS (token/card_id)'}")
    print(f"URL: {url}")
    print(f"X-Date: {date_str}")
    print(f"X-Login: {login}")
    print(f"Authorization: {headers['Authorization']}")
    print(f"Message for signature: {message_for_signature[:150]}...")
    print(f"Body JSON:\n{body_json}")
    print("=" * 50)
    
    try:
        # Use a Session for better control over the request
        session = requests.Session()
        
        # Create a prepared request to inspect what's actually being sent
        req = requests.Request('POST', url, headers=headers, data=body_json)
        prepared = session.prepare_request(req)
        
        print("=" * 50)
        print("PREPARED REQUEST DETAILS")
        print(f"URL: {prepared.url}")
        print(f"Headers: {dict(prepared.headers)}")
        print(f"Body: {prepared.body[:200] if prepared.body else 'None'}...")
        print("=" * 50)
        
        response = session.send(prepared)
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        result = handle_response(response, headers, signature, date_str, body)
        
        # Save successful payment to database
        if response.ok and result.get("response", {}).get("id"):
            api_response = result["response"]
            payment_id = api_response.get("id")
            
            # Check if payment already exists
            existing = Payment.query.filter_by(payment_id=payment_id).first()
            
            if existing:
                # Update existing payment
                existing.status = api_response.get("status", existing.status)
                existing.status_detail = api_response.get("status_detail", existing.status_detail)
                existing.status_code = api_response.get("status_code", existing.status_code)
                existing.raw_response = json.dumps(api_response)
                payment = existing
            else:
                # Create new payment record
                payment = Payment(
                    payment_id=payment_id,
                    order_id=api_response.get("order_id", payment_data.get("external_reference")),
                    amount=api_response.get("amount", payment_data.get("amount")),
                    currency=api_response.get("currency", payment_data.get("currency")),
                    country=api_response.get("country", payment_data.get("country")),
                    payment_method_id=api_response.get("payment_method_id", payment_method_id),
                    status=api_response.get("status", "CREATED"),
                    status_detail=api_response.get("status_detail", ""),
                    status_code=api_response.get("status_code", ""),
                    remitter_user_id=payment_data.get("remitter_user_id"),
                    beneficiary_user_id=payment_data.get("beneficiary_user_id"),
                    environment="sandbox" if use_sandbox else "production",
                    raw_response=json.dumps(api_response)
                )
                db.session.add(payment)
            
            db.session.commit()
            result["saved_locally"] = True
            result["local_id"] = payment.id
        
        # Add debug info with actual prepared request details
        result["debug"] = {
            "endpoint_type": "secure_payments (direct card)" if use_secure_endpoint else "payments (token/card_id)",
            "url": url,
            "message_for_signature": message_for_signature,
            "body_json": body_json,
            "headers_sent": {k: v for k, v in headers.items()},
            "prepared_headers": dict(prepared.headers),
            "prepared_body": prepared.body[:500] if prepared.body else None,
            "sent_as": "json"
        }
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str, body))


# ============================================
# Routes - Get Payment Details
# ============================================

@app.route("/api/payments/<payment_id>", methods=["POST"])
def get_payment(payment_id):
    """
    Retrieve payment information with details.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    use_sandbox = data.get("use_sandbox", True)
    
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    date_str = get_iso_date()
    signature = generate_signature(login, secret_key, date_str, "")
    
    # Use /details endpoint to get full payment information
    base = "https://sandbox.dlocal.com" if use_sandbox else "https://api.dlocal.com"
    url = f"{base}/payments/{payment_id}/details"
    
    headers = make_headers(login, transaction_key, secret_key, date_str, "")
    
    try:
        # Debug info
        print("=" * 50)
        print("GET PAYMENT DETAILS DEBUG")
        print("=" * 50)
        print(f"URL: {url}")
        print("=" * 50)

        response = requests.get(url, headers=headers)
       
        result = handle_response(response, headers, signature, date_str)

        print(f"RESPONSE: {result}")
        
        # Update local payment status if exists
        if response.ok:
            api_response = result.get("response", {})
            local_payment = Payment.query.filter_by(payment_id=payment_id).first()
            if local_payment:
                local_payment.status = api_response.get("status", local_payment.status)
                local_payment.status_detail = api_response.get("status_detail", local_payment.status_detail)
                local_payment.status_code = api_response.get("status_code", local_payment.status_code)
                local_payment.raw_response = json.dumps(api_response)
                db.session.commit()
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify(handle_error(e, headers, signature, date_str))


# ============================================
# Routes - Payouts
# ============================================

# dLocal Payouts API endpoints
DLOCAL_PAYOUTS_SANDBOX_URL = "https://sandbox.dlocal.com"
DLOCAL_PAYOUTS_PRODUCTION_URL = "https://api.dlocal.com"


@app.route("/api/payouts", methods=["POST"])
def create_payout():
    """
    Create a payout using dLocal Payouts API.
    
    Uses the same credentials (login, transaction_key, secret_key) as other endpoints.
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    credentials = data.get("credentials", {})
    payout_data = data.get("payout_data", {})
    use_sandbox = data.get("use_sandbox", True)
    
    # Validate credentials
    login = credentials.get("login")
    transaction_key = credentials.get("transaction_key")
    secret_key = credentials.get("secret_key")
    
    if not all([login, transaction_key, secret_key]):
        return jsonify({"error": "Missing required credentials"}), 400
    
    # Build payout request body
    # The payout API uses login and transaction_key as pass
    body = {
        "login": login,
        "pass": transaction_key,
        "external_id": payout_data.get("external_id", ""), # My own payout ID
        "country": payout_data.get("country", "AR"),
        "bank_code": payout_data.get("bank_code", "0"),
        "bank_name": payout_data.get("bank_name", ""),
        "bank_province": payout_data.get("bank_province", ""),
        "bank_account": payout_data.get("bank_account", ""),
        "account_type": payout_data.get("account_type", "C"),
        "amount": payout_data.get("amount", "0.00"),
        "currency": payout_data.get("currency", "ARS"),
        "purpose": payout_data.get("purpose", "EPREMT"),
        "remitter_user_id": payout_data.get("remitter_user_id", ""), # KYC Verification ID
        "beneficiary_user_id": payout_data.get("beneficiary_user_id", ""), # KYC Verification ID
        "subpurpose": payout_data.get("subpurpose", "EPREFA"),
        "source_of_funds": payout_data.get("source_of_funds", "SAVINGS"),
        "signature": True,
    }
    
    # Add optional fields if provided
    if payout_data.get("notification_url"):
        body["notification_url"] = payout_data.get("notification_url")
    if payout_data.get("beneficiary_name"):
        body["beneficiary_name"] = payout_data.get("beneficiary_name")
    if payout_data.get("beneficiary_document"):
        body["beneficiary_document"] = payout_data.get("beneficiary_document")
    if payout_data.get("beneficiary_document_type"):
        body["beneficiary_document_type"] = payout_data.get("beneficiary_document_type")
    
    # Prepare request
    base_url = DLOCAL_PAYOUTS_SANDBOX_URL if use_sandbox else DLOCAL_PAYOUTS_PRODUCTION_URL
    url = f"{base_url}/api_curl/cashout_api/request_cashout"
    
    body_json = json.dumps(body)
    
    # Generate payload signature (HMAC-SHA256 of JSON payload using secret_key)
    payload_signature = hmac.new(
        secret_key.encode('utf-8'),
        body_json.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Get timestamp in UTC string format
    from email.utils import formatdate
    timestamp = formatdate(timeval=None, localtime=False, usegmt=True)
    
    headers = {
        "Content-Type": "application/json",
        "X-Date": timestamp,
        "X-Login": login,
        "X-Trans-Key": transaction_key,
        "payload-signature": payload_signature,
    }
    
    # Debug info
    print("=" * 50)
    print("PAYOUT REQUEST DEBUG")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"X-Date: {timestamp}")
    print(f"X-Login: {login}")
    print(f"payload-signature: {payload_signature}")
    print(f"Body JSON:\n{body_json}")
    print("=" * 50)
    
    try:
        response = requests.post(url, headers=headers, data=body_json)
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'Empty'}")
        
        try:
            response_json = response.json() if response.text else {}
        except:
            response_json = {"raw": response.text}
        
        result = {
            "success": response.ok,
            "status_code": response.status_code,
            "response": response_json,
            "response_headers": dict(response.headers),
            "body_sent": body,
            "url": url
        }
        
        # Save successful payout to database
        if response.ok:
            external_id = payout_data.get("external_id")
            
            if external_id:
                try:
                    # Extract payout_id from response if available
                    api_payout_id = None
                    if response_json and isinstance(response_json, dict):
                        api_payout_id = (response_json.get("id") or 
                                       response_json.get("payout_id") or 
                                       response_json.get("payment_id") or
                                       response_json.get("cashout_id") or
                                       response_json.get("transaction_id"))
                    
                    print(f"Attempting to save payout with external_id: {external_id}")
                    if api_payout_id:
                        print(f"API returned payout_id: {api_payout_id}")
                    if response_json and isinstance(response_json, dict):
                        print(f"Response keys: {list(response_json.keys())}")
                    
                    # Check if payout already exists by external_id
                    existing = Payout.query.filter_by(external_id=external_id).first()
                    
                    if existing:
                        # Update existing payout
                        if api_payout_id:
                            existing.payout_id = api_payout_id
                        if response_json and isinstance(response_json, dict):
                            existing.status = response_json.get("status", existing.status)
                            existing.status_detail = response_json.get("status_detail", existing.status_detail)
                            existing.raw_response = json.dumps(response_json)
                        payout = existing
                        print(f"Updated existing payout: {external_id}")
                    else:
                        # Create new payout record
                        payout = Payout(
                            external_id=external_id,
                            payout_id=api_payout_id,
                            amount=float(payout_data.get("amount", "0.00")),
                            currency=payout_data.get("currency"),
                            country=payout_data.get("country"),
                            bank_account=payout_data.get("bank_account"),
                            status=response_json.get("status", "PENDING") if response_json and isinstance(response_json, dict) else "PENDING",
                            status_detail=response_json.get("status_detail", "") if response_json and isinstance(response_json, dict) else "",
                            remitter_user_id=payout_data.get("remitter_user_id"),
                            beneficiary_user_id=payout_data.get("beneficiary_user_id"),
                            purpose=payout_data.get("purpose"),
                            environment="sandbox" if use_sandbox else "production",
                            raw_response=json.dumps(response_json) if response_json else "{}"
                        )
                        db.session.add(payout)
                        print(f"Created new payout: {external_id}")
                    
                    db.session.commit()
                    result["saved_locally"] = True
                    result["local_id"] = payout.id
                    print(f"Payout saved successfully with local ID: {payout.id}")
                except Exception as e:
                    print(f"Error saving payout to database: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    db.session.rollback()
                    result["save_error"] = str(e)
            else:
                print("No external_id provided, cannot save payout")
        
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "body_sent": body,
            "url": url
        })


if __name__ == "__main__":
    # Ensure all database tables are created
    with app.app_context():
        db.create_all()
        print("Database tables created/verified")
    
    app.run(debug=True, port=5000)
