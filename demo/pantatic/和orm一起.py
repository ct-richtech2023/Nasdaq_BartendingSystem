from pydantic import BaseModel, root_validator
from typing import List
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from pydantic.utils import GetterDict


class BillingOrm(Base):
    __tablename__ = "billing"
    id = Column(Integer, primary_key=True, nullable=False)
    order_id = Column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    first_name = Column(String(20))


class OrderOrm(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, nullable=False)
    billing = relationship("BillingOrm")


class Billing(BaseModel):
    id: int
    order_id: int
    first_name: str

    class Config:
        orm_mode = True


class Order(BaseModel):
    id: int
    name: List[str] = None

    # billing: List[Billing]  # uncomment to verify the relationship is working

    class Config:
        orm_mode = True

        allow_population_by_field_name = True

    def __init__(self, **kwargs):
        # This __init__ function does not run when using from_orm to parse ORM object
        print("kwargs for orm:", kwargs)
        kwargs["name"] = kwargs["billing"]["first_name"]
        super().__init__(**kwargs)


billing_orm_1 = BillingOrm(id=1, order_id=1, first_name="foo")
billing_orm_2 = BillingOrm(id=2, order_id=1, first_name="bar")
order_orm = OrderOrm(id=1)
order_orm.billing.append(billing_orm_1)
order_orm.billing.append(billing_orm_2)
print(order_orm)
order_model = Order.from_orm(order_orm)
# Output returns 'None' for name instead of ['foo','bar']
print(order_model)  # id=1 name=None
