import traceback
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi import Depends
from fastapi import APIRouter
from loguru import logger
from starlette.responses import JSONResponse
from typing import Literal, List

from common import define
from common.api import AudioInterface
from common.db.database import get_db
from common.db.crud import coffee as coffee_crud
from common.db.crud.db_const import DB_Constant
from business import get_coffee_obj, Business
from common.myerror import DBError
from common.schemas.coffee import NewMaterialCurrent, UpdateMaterialCurrent, NewFormula, NewMachineConfig, UpdateGpioConfig

router = APIRouter(
    prefix="/{}".format(define.Channel.coffee),
    tags=[define.Channel.coffee],
    responses={404: {"description": "Not found"}},
    on_startup=[get_coffee_obj]
)
SUPPORT_FORMULA = Literal[
    'Latte', 'Coffee', 'Latte Macchiato', 'Iced Latte', 'Flat White', 'Espresso', 'Cold Brew Coffee', 'Vanilla Sweet Cream Cold Brew',
    'Sea Salt Milk Cap Cold Brew Coffee', 'Iced Americano', 'Americano', 'Cappuccino',
    'Hot Milk', 'Matcha Latte', 'Chocolate Milk', 'Hot Water', 'Raw Coconut Latte',
    'Iced Thick Coconut Latte', 'Hot Thick Coconut Latte', 'Iced Cappuccino', 'Iced Matcha Latte', 'Espresso Double',
    'Paper plane with sugar rim', 'Cosmopolitan', 'Cranberry whiskey sour with sugar rim', 'Vodka screwdriver',
    'Orange juice', 'Cranberry juice', 'Beer A', 'Beer B', 'Double Beer', 'Double Beer A', 'Double Beer B']
db = next(get_db())


@router.post("/make", description="control coffee machine to make drink")
def make(formula: str, type: str, sweetness: int, ice: define.SUPPORT_ICE_TYPE,
         milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk, cup=define.CupSize.medium_cup,
         task_uuid: UUID = None, receipt_number: str = '', create_time=None, coffee: Business = Depends(get_coffee_obj)):
    try:
        support_formula_name = DB_Constant.support_formula_name()
        assert formula in support_formula_name, 'drink [{}] not support, permitted {}'.format(formula, support_formula_name)

        new_dict = {
            'task_uuid': task_uuid,
            'receipt_number': receipt_number,
            'formula': formula,
            'type': type,
            'cup': cup,
            'sweetness': sweetness,
            'ice': ice,
            'milk': milk
        }
        if create_time:
            new_dict['create_time'] = create_time
        if task_uuid:
            if status := coffee_crud.get_task_uuid_status(db, task_uuid):  # coffee exist
                if status in [define.TaskStatus.completed, define.TaskStatus.canceled, define.TaskStatus.skipped]:
                    AudioInterface.gtts("{} {} with uuid={} cannot be made.".format(status, formula, str(task_uuid)[-4:]))
                    return JSONResponse(status_code=400, content="{} {} with uuid end_with={} cannot be made.".format(status, formula, task_uuid))
                else:
                    update_dict = dict(status=define.TaskStatus.waiting)
                    coffee_crud.update_coffee_by_task_uuid(db, task_uuid, update_dict)
            else:
                logger.info('adding coffee with task_uuid')
                coffee_crud.add_new_coffee_task(db, new_dict)
        else:
            task_uuid = uuid4()
            logger.debug('This is debug make! Generate a random uuid={}'.format(task_uuid))
            coffee_crud.add_new_coffee_task(db, new_dict)
        msg = 'make formula={}, task_uuid={}'.format(formula, task_uuid)
        coffee.start_make_coffee_thread(msg)
        return msg
    except HTTPException as http_exception:
        # Log HTTPException with status code 422
        logger.error(f"HTTPException: Status Code {http_exception.status_code}, Detail: {http_exception.detail}")
        return JSONResponse(status_code=http_exception.status_code, content=http_exception.detail)
    except Exception as e:
        logger.error("make failed, traceback={}".format(traceback.format_exc()))
        return JSONResponse(status_code=400, content=str(e))


@router.get("/current_task_status", description="current task status")
def current_task_status(coffee: Business = Depends(get_coffee_obj)):
    return coffee.make_coffee_thread.current_task_status


@router.get("/task/next", description="next waiting coffee record")
def get_next():
    next_uuid = coffee_crud.exist_next_record(db)
    if next_uuid:
        return next_uuid
    else:
        return ''


@router.put("/task/failed", description="set one task failed")
def task_failed(task_uuid: UUID = None, coffee: Business = Depends(get_coffee_obj)):
    return coffee.set_task_uuid_failed(task_uuid)


@router.put("/stop", description="stop all action")
def stop(coffee: Business = Depends(get_coffee_obj)):
    return coffee.stop()


@router.put("/resume", description="resume to work")
def resume(coffee: Business = Depends(get_coffee_obj)):
    return coffee.resume()


@router.post("/material/add", description="add a new material")
def new_material(material: NewMaterialCurrent):
    try:
        coffee_crud.add_material(db, material.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/material/get", description="get material by name or get all material")
def get_material(name=None, in_use: Literal['0', '1'] = None):
    return_data = []
    in_use = in_use if in_use is None else int(in_use)
    materials = coffee_crud.get_material(db, name, in_use)
    for material in materials:
        return_data.append(material.to_dict())
    return return_data


@router.post("/material/update", description="update a material")
def update_material(name: str, update: UpdateMaterialCurrent):
    try:
        coffee_crud.update_material(db, name, update.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/use", description="update a material")
def use_material(name: str, quantity: float = 0):
    try:
        material = coffee_crud.use_material(db, name, quantity)
        if material and material.left <= material.alarm:
            AudioInterface.gtts('please replace {}, {} {} left.'.format(name, material.left, material.unit))
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/bean_out", description="set coffee bean left 0")
def bean_out():
    try:
        material = coffee_crud.get_material(db, 'bean')
        if material:
            material[0].left = 0
            db.commit()
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/material/bean_reset", description="reset count of coffee bean")
def bean_reset():
    try:
        material = coffee_crud.get_material(db, 'bean')
        if material:
            material[0].left = material[0].capacity
            db.commit()
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


# @router.post("/material/off_use", description=" off_use a material")
# def off_use(name: str):
#     update_dict = dict(in_use=define.Constant.IN_USE.not_in_use)
#     try:
#         milktea_crud.update_material(db, name, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'
#
#
# @router.post("/material/on_use", description="on_use a material")
# def on_use(name: str):
#     update_dict = dict(in_use=define.Constant.IN_USE.in_use)
#     try:
#         milktea_crud.update_material(db, name, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'


@router.post("/material/reset", description="reset a material")
def on_use(names: List[str]):
    coffee_crud.reset_material(db, names)
    return 'ok'


@router.post("/formula/add", description="add a new formula")
def new_formula(formula: NewFormula):
    try:
        coffee_crud.add_formula(db, formula.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/formula/get", description="get formula")
def get_formula(name=None, cup: define.SUPPORT_CUP_SIZE_TYPE = None,
                in_use: Literal['0', '1'] = None):
    return_data = []
    in_use = in_use if in_use is None else int(in_use)
    formulas = coffee_crud.get_formula(db, name, cup, in_use)
    for formula in formulas:
        return_data.append(formula.to_dict())
    return return_data


# @router.post("/formula/off_use", description=" off_use a material")
# def formula_off_use(name: str, cup: define.SUPPORT_CUP_NAME):
#     update_dict = dict(in_use=define.Constant.IN_USE.not_in_use)
#     try:
#         milktea_crud.update_formula(db, name, cup, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'
#
#
# @router.post("/formula/on_use", description="on_use a material")
# def formula_on_use(name: str, cup: define.SUPPORT_CUP_NAME):
#     update_dict = dict(in_use=define.Constant.IN_USE.in_use)
#     try:
#         milktea_crud.update_formula(db, name, cup, update_dict)
#     except DBError as e:
#         return JSONResponse(status_code=400, content={'error': str(e)})
#     return 'ok'


@router.delete("/formula/delete", description="delete a formula")
def delete_formula(name: str, cup: define.SUPPORT_CUP_SIZE_TYPE):
    result, msg = coffee_crud.delete_formula(db, name, cup)
    logger.debug('delete_formula, result={}, msg={}'.format(result, msg))
    if result == 0:
        return JSONResponse(status_code=510, content={'error': str(msg)})
    return 'success'


@router.get("/composition/get", description="get composition of a formula")
def get(formula: SUPPORT_FORMULA, cup: define.SUPPORT_CUP_SIZE_TYPE, formula_in_use: Literal['0', '1'] = None):
    composition = coffee_crud.get_composition_by_formula(db, formula, cup, formula_in_use)
    return composition


@router.post("/composition/update", description="update count in composition")
def get(formula: str, cup: define.SUPPORT_CUP_SIZE_TYPE,
        material: str, count):
    try:
        coffee_crud.update_composition_count(db, formula, cup, material, count)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.post("/machine/add", description="add a new formula")
def new_machine(machine: NewMachineConfig):
    try:
        coffee_crud.add_machine_config(db, machine.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/machine/get", description="get gpio config")
def get(name: str = None, machine: str = None):
    return_data = []
    configs = coffee_crud.get_machine_config(db, name, machine)
    for config in configs:
        return_data.append(config.to_dict())
    return return_data


@router.post("/machine/update", description="update gpio config")
def update_gpio(name: str, update: UpdateGpioConfig):
    try:
        coffee_crud.update_machine_config_by_name(db, name, update.dict())
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'


@router.get("/speech/add", description="add one text into database")
def text(text: str, code: str):
    try:
        return coffee_crud.add_text(db, text, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})


@router.get("/speech/random", description="get one text from database")
def text(code: str):
    try:
        text = coffee_crud.choose_one_speech_text(db, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return text


@router.get("/speech/get_all", description="get all text by code")
def get_all_texts(code=None):
    try:
        texts = coffee_crud.get_all_text(db, code)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return texts


@router.post("/speech/update/", description="update text record by id")
def update_text(text_id, text: str):
    try:
        texts = coffee_crud.update_text_by_id(db, text_id, text=text)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return texts


@router.delete("/speech/delete/", description="update text record by id")
def update_text(text_id):
    try:
        coffee_crud.delete_text_by_id(db, text_id)
    except DBError as e:
        return JSONResponse(status_code=400, content={'error': str(e)})
    return 'ok'
