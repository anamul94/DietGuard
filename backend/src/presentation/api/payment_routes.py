from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User, Payment
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.audit_service import AuditService
from ...infrastructure.utils.logger import logger

router = APIRouter(tags=["Payments"])

# Request/Response Models
class CreatePaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"
    payment_method: Optional[str] = None

class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    created_at: str

@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    request: Request,
    payment_data: CreatePaymentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a payment record (placeholder for Stripe integration).
    
    - **amount**: Payment amount
    - **currency**: Currency code (default: USD)
    - **payment_method**: Payment method (optional)
    
    Note: This is a placeholder. Stripe integration will be added later.
    
    Requires authentication.
    """
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        amount=Decimal(str(payment_data.amount)),
        currency=payment_data.currency,
        payment_method=payment_data.payment_method,
        status="pending"
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    # Log payment creation
    await AuditService.log_data_modification(
        db=db,
        action="create",
        user_id=str(current_user.id),
        resource="payment",
        resource_id=str(payment.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        changes={"amount": payment_data.amount, "currency": payment_data.currency}
    )
    
    logger.info("Payment record created", user_id=str(current_user.id), payment_id=str(payment.id))
    
    return {
        "id": str(payment.id),
        "amount": float(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "created_at": payment.created_at.isoformat()
    }

@router.get("/history", response_model=list)
async def get_payment_history(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payment history for current user.
    
    Requires authentication.
    """
    from sqlalchemy import select
    
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status,
            "payment_method": p.payment_method,
            "created_at": p.created_at.isoformat()
        }
        for p in payments
    ]
