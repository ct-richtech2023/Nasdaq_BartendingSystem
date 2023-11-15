import datetime

from sqlalchemy import Column, Integer, String, DateTime, func

from common.db.database import Base


class TapStatus(Base):
    __tablename__ = "tap_status"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    material_name = Column(String, unique=True, comment='material_name')
    status = Column(Integer, comment='0: closed; 1: open')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data
