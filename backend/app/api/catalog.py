from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Product
from app.db.session import get_db
from app.domain.models import ProductRead


router = APIRouter(prefix="/api/v1/products", tags=["catalog"])


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return list(db.scalars(select(Product).order_by(Product.id)))

