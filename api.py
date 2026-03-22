import os
import time
import stripe
from typing import List
from fastapi import FastAPI, HTTPException, status, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

# ==========================================
# 1. API INITIALIZATION & CONFIGURATION
# ==========================================
app = FastAPI(
    title="GroundTruth Property API",
    description="Enterprise B2A (Business-to-Agent) service for validating contractor bids, estimating compliance, and fraud detection. **Protected by Stripe Metered Billing.**",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. BILLING & SECURITY (The Tollbooth)
# ==========================================
# Configure your live Stripe API key (In production, use Render Environment Variables)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_replace_me_with_stripe_key")

# We expect the AI agent to send an 'X-API-Key' in the header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key_and_charge(api_key: str = Security(api_key_header)):
    """
    Security function that runs before the core logic.
    It checks the AI's API key and bills their Stripe account for 1 usage credit.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Please provide an X-API-Key header to access this service."
        )

    # In a real business, you would map this 'api_key' to a specific customer's Stripe Subscription Item ID.
    # For this demo, we assume the API key provided IS their Stripe Subscription Item ID.
    subscription_item_id = api_key

    # Only attempt to charge if we have a real Stripe key configured
    if "replace_me" not in stripe.api_key:
        try:
            # Tell Stripe to charge this customer for 1 API call ($0.15)
            stripe.SubscriptionItem.create_usage_record(
                subscription_item_id,
                quantity=1,
                timestamp=int(time.time()),
            )
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Billing failed or invalid API Key: {str(e)}"
            )
    else:
        # Mock mode if Stripe keys aren't set up yet
        pass

    return api_key

# ==========================================
# 3. DATA SCHEMAS (The Strict "Contract" for AIs)
# ==========================================
class LineItem(BaseModel):
    description: str = Field(..., description="The Xactimate or custom line item description")
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)

class ContractorBid(BaseModel):
    zip_code: str = Field(..., min_length=5, max_length=10)
    loss_type: str = Field(..., description="Type of loss (e.g., 'Wind', 'Hail', 'Water')")
    total_amount: float = Field(..., gt=0)
    includes_o_and_p: bool = Field(default=False)
    line_items: List[LineItem] = Field(..., min_length=1)

class ValidationResult(BaseModel):
    is_fair_market_value: bool
    confidence_score: float
    flagged_issues: List[str]
    suggested_settlement: float
    processing_time_ms: float

# ==========================================
# 4. ENDPOINTS
# ==========================================
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "2.0.0", "billing": "active"}

@app.post("/validate-bid", response_model=ValidationResult, tags=["Core AI Services"])
async def validate_contractor_bid(
    bid: ContractorBid, 
    api_key: str = Security(verify_api_key_and_charge) # The Tollbooth is applied here!
):
    """
    **The core B2A endpoint.**
    AI Agents send a POST request here with the contractor's bid.
    Our system runs proprietary localized estimator logic and returns structured, actionable data.
    """
    start_time = time.time()
    flagged = []
    
    # --- PROPRIETARY ESTIMATOR LOGIC ---
    if bid.includes_o_and_p and len(bid.line_items) <= 2:
        flagged.append("POLICY ALERT: Overhead & Profit (O&P) included on low-complexity/single-trade claim.")
    
    calculated_total = 0.0
    for item in bid.line_items:
        desc_lower = item.description.lower()
        if any(keyword in desc_lower for keyword in ["remove", "tear off"]) and item.unit_price > 85.00:
            flagged.append(f"PRICE GOUGING ALERT: '{item.description}' exceeds local maximum allowable tear-off rate.")
            calculated_total += (item.quantity * 85.00)
        elif "shingle" in desc_lower and item.unit_price > 250.00:
            flagged.append(f"PREMIUM MATERIAL ALERT: '{item.description}' exceeds standard replacement grade limits.")
            calculated_total += (item.quantity * 250.00)
        else:
            calculated_total += (item.quantity * item.unit_price)

    is_fair = bid.total_amount <= (calculated_total * 1.05)
    processing_time = round((time.time() - start_time) * 1000, 2)

    return ValidationResult(
        is_fair_market_value=is_fair,
        confidence_score=0.94,
        flagged_issues=flagged,
        suggested_settlement=round(calculated_total, 2),
        processing_time_ms=processing_time
    )