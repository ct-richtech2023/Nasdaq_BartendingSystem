from uuid import UUID
from typing import Literal, Optional, List, Dict

from pydantic import BaseModel, validator

from common import define


class CoffeeRecord(BaseModel):
    task_uuid: UUID
    receipt_number: str
    formula: str
    cup: str
    sweetness: int
    ice: str
    milk: str
    failed_msg: Optional[str] = ''
    status: Literal[tuple([i for i in dir(define.TaskStatus) if '__' not in i])]  # noqa

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class MaterialCurrentRecord(BaseModel):
    name: str
    capacity: int
    count: int
    left: int

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewMaterialCurrent(BaseModel):
    name: str
    capacity: int
    alarm: int
    count: int
    left: float
    unit: int
    type: Literal[define.SUPPORT_MATERIAL_TYPE]
    machine: Literal[define.SUPPORT_MACHINE_TYPE]
    extra: Optional[str]
    in_use: int = 1

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class UpdateMaterialCurrent(BaseModel):
    capacity: Optional[int]
    alarm: Optional[int]
    unit: Optional[int]
    type: Optional[define.SUPPORT_MATERIAL_TYPE]
    machine: Optional[define.SUPPORT_MACHINE_TYPE]
    extra: Optional[str]

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewFormula(BaseModel):
    name: str
    cup: str
    with_ice: Literal[0, 1] = 0
    type: define.SUPPORT_FORMULA_TYPE
    in_use: Literal[0, 1] = 1
    composition: Dict[str, float]

    # @validator("composition")
    # def check_composition(cls, composition: dict):
    #     support_material_name = define.Constant.support_material_name
    #     for material in composition.keys():
    #         assert material in support_material_name, "key='{}'  must in {}".format(material, support_material_name)
    #     return composition

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class NewMachineConfig(BaseModel):
    name: str
    machine: Literal[define.SUPPORT_MACHINE_TYPE]
    num: int
    gpio: str
    speed: Optional[int]
    delay_time: Optional[int]
    type: Optional[str]  # 1: material, figure by speed, 2: action, use_delay_time

    @validator("gpio")
    def check_composition(cls, gpio: str):
        support_which = ['left', 'right']
        assert ',' in gpio, "gpio='{}' must have ','".format(gpio)
        values = [i.strip() for i in gpio.split(',')]
        assert len(values) == 2, "gpio='{}' must have 2 elements".format(gpio)
        assert values[0] in support_which, "composition='{}' first element must in {}".format(gpio, support_which)
        assert values[1].isdigit(), "gpio='{}' second element must be digit".format(gpio)
        return gpio

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class UpdateGpioConfig(BaseModel):
    arm: Optional[Literal['left', 'right']]
    num: Optional[int]
    speed: Optional[int]
    delay_time: Optional[int]
    type: Optional[str]  # 1: material, figure by speed, 2: action, use_delay_time

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True
