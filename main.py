import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckoutItem(BaseModel):
    id: str
    name: str
    unit_amount: int = Field(..., description="Price in cents")
    quantity: int = 1
    image: Optional[str] = None
    metadata: Optional[dict] = None


class CheckoutRequest(BaseModel):
    items: List[CheckoutItem]
    currency: str = "usd"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        # Try to import database module
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


@app.post("/checkout/create-session")
def create_checkout_session(payload: CheckoutRequest):
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=400, detail="Stripe is not configured. Please set STRIPE_SECRET_KEY in the backend environment.")

    try:
        import stripe
        stripe.api_key = stripe_secret

        line_items = []
        for item in payload.items:
            # Build product and price data inline
            price_data = {
                "currency": payload.currency,
                "product_data": {
                    "name": item.name,
                },
                "unit_amount": item.unit_amount,
            }
            if item.image:
                price_data["product_data"]["images"] = [item.image]
            if item.metadata:
                price_data["product_data"]["metadata"] = item.metadata

            line_items.append({
                "price_data": price_data,
                "quantity": item.quantity,
            })

        success_url = payload.success_url or os.getenv("FRONTEND_URL", "http://localhost:3000") + "/?checkout=success"
        cancel_url = payload.cancel_url or os.getenv("FRONTEND_URL", "http://localhost:3000") + "/?checkout=cancelled"

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
