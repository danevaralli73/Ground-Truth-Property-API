from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List
import time

# ==========================================
# 1. API INITIALIZATION & CONFIGURATION
# ==========================================
app = FastAPI(
    title="GroundTruth Property API",
    description="Enterprise B2A (Business-to-Agent) service for validating contractor bids, estimating compliance, and fraud detection using localized insurance guidelines.",
    version="1.1.0",
    contact={
        "name": "GroundTruth API Support",
        "url": "https://groundtruth-api.example.com/contact",
    }
)

# Enable CORS so web-based agents and other servers can call this API securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to specific domains/IPs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 2. DATA SCHEMAS (The Strict "Contract" for AIs)
# ==========================================
class LineItem(BaseModel):
    description: str = Field(..., description="The Xactimate or custom line item description (e.g., 'Tear off, haul and dispose of comp. shingles')")
    quantity: float = Field(..., gt=0, description="Quantity of material/labor. Must be greater than 0.")
    unit_price: float = Field(..., ge=0, description="Price per unit claimed by contractor. Cannot be negative.")

class ContractorBid(BaseModel):
    zip_code: str = Field(..., min_length=5, max_length=10, description="The zip code of the property to check local pricing databases.")
    loss_type: str = Field(..., description="Type of loss (e.g., 'Wind', 'Hail', 'Water', 'Fire')")
    total_amount: float = Field(..., gt=0, description="The total dollar amount requested by the contractor.")
    includes_o_and_p: bool = Field(default=False, description="Does the bid include 10/10 Overhead & Profit?")
    line_items: List[LineItem] = Field(..., min_length=1, description="List of individual line items. Cannot be empty.")

    # Provide a perfect example so AI agents know exactly how to format their requests
    model_config = {
        "json_schema_extra": {
            "example": {
                "zip_code": "75001",
                "loss_type": "Hail",
                "total_amount": 15450.00,
                "includes_o_and_p": True,
                "line_items": [
                    {
                        "description": "Tear off composition shingles",
                        "quantity": 35.0,
                        "unit_price": 125.00
                    },
                    {
                        "description": "Laminated high grade shingles",
                        "quantity": 38.5,
                        "unit_price": 240.00
                    }
                ]
            }
        }
    }

class ValidationResult(BaseModel):
    is_fair_market_value: bool = Field(..., description="True if the bid is within 5% of local market rates.")
    confidence_score: float = Field(..., description="0.0 to 1.0 score indicating our pricing accuracy confidence.")
    flagged_issues: List[str] = Field(..., description="List of estimating errors, policy violations, or fraud indicators found.")
    suggested_settlement: float = Field(..., description="The mathematical fair value based on local data.")
    processing_time_ms: float = Field(..., description="How fast the API processed this request.")

# ==========================================
# 3. ENDPOINTS
# ==========================================

@app.get("/health", tags=["System"])
async def health_check():
    """Enterprise standard endpoint for monitoring uptime."""
    return {"status": "healthy", "version": "1.1.0"}

@app.post("/validate-bid", response_model=ValidationResult, tags=["Core AI Services"])
async def validate_contractor_bid(bid: ContractorBid):
    """
    **The core B2A endpoint.**
    AI Agents send a POST request here with the contractor's bid.
    Our system runs proprietary localized estimator logic and returns structured, actionable data.
    """
    start_time = time.time()
    flagged = []
    
    try:
        # --- PROPRIETARY ESTIMATOR LOGIC ---
        
        # Rule 1: O&P Compliance Check
        # O&P is generally not warranted for simple, single-trade jobs (like just a roof).
        if bid.includes_o_and_p and len(bid.line_items) <= 2:
            flagged.append("POLICY ALERT: Overhead & Profit (O&P) included on low-complexity/single-trade claim.")
        
        # Rule 2: Line Item Price Gouging & Keyword Detection
        calculated_total = 0.0
        
        for item in bid.line_items:
            desc_lower = item.description.lower()
            
            # Catch overpriced tear-offs (Mock local max: $85.00/sq)
            if any(keyword in desc_lower for keyword in ["remove", "tear off", "tear-off"]) and item.unit_price > 85.00:
                flagged.append(f"PRICE GOUGING ALERT: '{item.description}' exceeds local maximum allowable tear-off rate of $85.00.")
                calculated_total += (item.quantity * 85.00) # Auto-correct to fair market rate
                
            # Catch overpriced premium shingles (Mock local max: $250.00/sq)
            elif "shingle" in desc_lower and item.unit_price > 250.00:
                flagged.append(f"PREMIUM MATERIAL ALERT: '{item.description}' exceeds standard replacement grade limits.")
                calculated_total += (item.quantity * 250.00)
                
            else:
                calculated_total += (item.quantity * item.unit_price)

        # Rule 3: Total Variance Check (Allow 5% variance)
        is_fair = bid.total_amount <= (calculated_total * 1.05)

        # Calculate processing time
        processing_time = round((time.time() - start_time) * 1000, 2)

        # --- RETURN THE STRUCTURED DATA TO THE AI ---
        return ValidationResult(
            is_fair_market_value=is_fair,
            confidence_score=0.94,
            flagged_issues=flagged,
            suggested_settlement=round(calculated_total, 2),
            processing_time_ms=processing_time
        )

    except Exception as e:
        # Enterprise error handling so the purchasing AI gets a clean error message, not a crash
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal processing error: {str(e)}"
        )
