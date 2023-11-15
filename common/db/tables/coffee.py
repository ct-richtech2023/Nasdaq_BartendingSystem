import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, Float, UniqueConstraint, SMALLINT
from sqlalchemy.dialects.postgresql import UUID

from common.db.database import Base


class Coffee(Base):
    __tablename__ = "coffee"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    task_uuid = Column(UUID(as_uuid=True), primary_key=True, unique=True, comment='task uuid')
    receipt_number = Column(String, default='', comment='receipt number')
    formula = Column(String, comment='formula name')
    type = Column(String, comment='type of drink; cold/hot/red/white')
    cup = Column(String, comment='cup name')
    sweetness = Column(Integer, comment='sweetness percent like 80, 100')
    ice = Column(String, comment='no_ice/light/more')
    milk = Column(String, comment='fresh_dairy or plant_milk')
    status = Column(String, default='waiting', comment='make status')
    refund = Column(SMALLINT, default=0, comment='0:no refund;1:refunded')
    discount = Column(SMALLINT, default=0, comment='0:no discount;1:resell; 2:normal')
    failed_msg = Column(String, default='', comment='failed msg')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Espresso(Base):
    __tablename__ = "espresso"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    formula = Column(String, unique=True, comment='formula name')
    drink_type = Column(Integer, comment='drink type')
    coffee = Column(Integer, comment='how much coffee')
    coffee_temp = Column(Integer, comment='level of coffee temperature, 0/1/2')
    coffee_concentration = Column(Integer, comment='concentration level of coffee, 0/1/2')
    water = Column(Integer, comment='how much hot water')
    water_temp = Column(Integer, comment='level of how water temperature, 0/1/2')
    milk_time = Column(Integer, comment='time of making milk')
    foam_time = Column(Integer, comment='time of making foam')
    precook = Column(Integer, comment='precook or not,true=1/false=0')
    enhance = Column(Integer, comment='enhance or not,true=1/false=0')
    together = Column(Integer, comment='coffee and milk out together or not, true=1/false=0')
    order = Column(Integer, comment='0：milk first then coffee; 1: coffee first then milk')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data

    def to_coffee_dict(self):
        """
            drinkType: 饮品类型,1-8
            volume: 咖啡量: 15-240 / 0
            coffeeTemperature: 咖啡温度 0/1/2 低/中/高
            concentration: 咖啡浓度 0/1/2 清淡/适中/浓郁
            hotWater: 热水量
            waterTemperature: 热水温度 0/1/2 低/中/高
            hotMilk: 牛奶时间 5-120 / 0
            foamTime: 奶沫时间  5-120 / 0
            precook: 预煮 1/0 是/否
            moreEspresso: 咖啡增强 1/0 是/否
            coffeeMilkTogether: 咖啡牛奶同时出 1/0 是/否
            adjustOrder: 出品顺序 1/0 0：先奶后咖啡/1：先咖啡后奶
        """
        coffee_dict = dict(
            drinkType=self.drink_type, volume=self.coffee, coffeeTemperature=self.coffee_temp,
            concentration=self.coffee_concentration, hotWater=self.water, waterTemperature=self.water_temp,
            hotMilk=self.milk_time, foamTime=self.foam_time, precook=self.precook, moreEspresso=self.enhance,
            coffeeMilkTogether=self.together, adjustOrder=self.order
        )
        return coffee_dict


class MaterialCurrent(Base):
    __tablename__ = "material_current"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, unique=True, comment='material name')
    display = Column(String, comment='material name displayed on pad')
    capacity = Column(Integer, comment='capacity')
    alarm = Column(Integer, comment='when to alarm')
    left = Column(Float, comment='left')
    count = Column(Integer, comment='use times')
    unit = Column(String, comment='unit of measurement')
    batch = Column(Integer, comment='minimum use in one time')
    type = Column(String, comment='type of material, choose in material_type table')
    in_use = Column(Integer, comment='formula in use? 1:in use; 0:not in use')
    machine = Column(String, comment='formula in use? 1:gpio; 2:scoop; 3: ice_maker')
    extra = Column(String, comment='extra param for future extend')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class AddMaterialHistory(Base):
    __tablename__ = "material_history"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='material name')
    before_add = Column(Float, comment='how much left before add')
    count = Column(Integer, comment='use times')
    add = Column(Float, comment='how much added')
    add_time = Column(DateTime, server_default=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Formula(Base):
    __tablename__ = "formula"  # noqa
    __table_args__ = (UniqueConstraint('name', 'cup'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, comment='formula name')
    cup = Column(String, comment='cup name')
    with_ice = Column(String, comment='ice in cup: 0: not in cup, 1: in cup')
    type = Column(String, comment='type of drink; cold/hot/red/white')
    in_use = Column(Integer, comment='formula in use? 1:in use; 0:not in use')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class Composition(Base):
    __tablename__ = "composition"  # noqa
    __table_args__ = (UniqueConstraint('formula', 'cup', 'material'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    formula = Column(String, comment='formula name')
    cup = Column(String, comment='cup_name')
    material = Column(String, comment='material name')
    count = Column(Integer, comment='the quantity required')
    extra = Column(String, default='', comment='prepare for extra param')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class MachineConfig(Base):
    __tablename__ = "machine_config"  # noqa
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    name = Column(String, unique=True, comment='material name or action name')
    machine = Column(String, comment='gpio/scoop/ice_maker')
    num = Column(Integer, comment='which num')
    gpio = Column(String, comment='arm,num')
    arduino_write = Column(String, comment='which:char, send char to which arduino')
    arduino_read = Column(String, comment='which:index, read index from which arduino')
    speed = Column(Integer, comment='flow rate')
    delay_time = Column(Float, comment='seconds')
    type = Column(String, comment='1: speed, figure by speed, 2: time, use_delay_time')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = str(value)
        return data


class SpeechText(Base):
    __tablename__ = "speech_text"  # noqa
    __table_args__ = (UniqueConstraint('code', 'text'),)
    id = Column(Integer, index=True, autoincrement=True, unique=True, primary_key=True)
    code = Column(String, comment='type of text such as get_order/making/take_wine')
    text = Column(String, comment='content')
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        data = {'id': self.id, 'code': self.code, 'text': self.text}
        return data
