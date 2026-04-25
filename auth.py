"""
Supabase auth + Stripe subscription guard.

Setup:
  1. pip install supabase stripe python-jose[cryptography]
  2. Copy .env.example → .env and fill in credentials
  3. In Supabase: create table 'subscriptions' with columns:
       user_id uuid (FK to auth.users), status text, plan text, stripe_customer_id text
  4. In Stripe: create a webhook pointing to POST /stripe/webhook
"""

import os
from typing import Optional
from fastapi import HTTPException, Header
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL          = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY          = os.getenv("SUPABASE_KEY", "")          # anon key — frontend only
SUPABASE_SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_KEY", "")  # service key — bypasses RLS
SUPABASE_JWT_SECRET   = os.getenv("SUPABASE_JWT_SECRET", "")
STRIPE_SECRET_KEY     = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true" and bool(SUPABASE_URL and SUPABASE_JWT_SECRET)

# ── Supabase admin client (service key — bypasses RLS) ────────────────────────
_supabase_admin = None

def get_supabase():
    global _supabase_admin
    if _supabase_admin is None:
        try:
            from supabase import create_client
            key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
            _supabase_admin = create_client(SUPABASE_URL, key)
        except ImportError:
            raise RuntimeError("Run: pip install supabase")
    return _supabase_admin


# ── JWT verification ───────────────────────────────────────────────────────────
def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_user_id(token: str) -> str:
    payload = verify_token(token)
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing user ID")
    return uid


# ── Subscription check ─────────────────────────────────────────────────────────
def is_subscribed(user_id: str) -> bool:
    try:
        sb = get_supabase()
        result = (
            sb.table("subscriptions")
            .select("status")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return result.data and result.data.get("status") == "active"
    except Exception:
        return False


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency that:
    - If AUTH_ENABLED=False (no Supabase credentials) → allows all requests (dev mode)
    - If AUTH_ENABLED=True → verifies JWT and checks active subscription
    Returns user_id string.
    """
    if not AUTH_ENABLED:
        return "dev-user"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization.split(" ", 1)[1]
    user_id = get_user_id(token)

    if not is_subscribed(user_id):
        raise HTTPException(status_code=403, detail="Active subscription required")

    return user_id


# ── Stripe helpers ─────────────────────────────────────────────────────────────
def handle_stripe_event(payload: bytes, sig_header: str) -> dict:
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ImportError:
        raise RuntimeError("Run: pip install stripe")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    sb = get_supabase()
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = data.get("customer")
        status = data.get("status")  # active, past_due, canceled, etc.
        plan = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("lookup_key", "")
        sb.table("subscriptions").upsert({
            "stripe_customer_id": customer_id,
            "status": status,
            "plan": plan,
        }).execute()

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        sb.table("subscriptions").update({"status": "canceled"}).eq(
            "stripe_customer_id", customer_id
        ).execute()

    return {"received": True}
