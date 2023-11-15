import time
from typing import Literal, List

from fastapi import APIRouter, Depends
from loguru import logger
from starlette.responses import JSONResponse

# from business import get_adam_obj, Adam
from business import get_adam_obj, Adam
from common import define
from common.define import Channel
from common.myerror import MoveError
from common.api import AudioInterface, CoffeeInterface
from common.db.crud import adam as adam_crud
from devices.coffee.constant import MachineStatus

router = APIRouter(
    prefix="/{}".format(Channel.adam),
    tags=[Channel.adam],
    # dependencies=[Depends(get_admin_token)],
    responses={404: {"description": "Not found"}},
    on_startup=[get_adam_obj]
)

SUPPORT_FORMULA = Literal[
    'Gin Martini', 'Dirty Gin Martini', 'Vodka Martini', 'Dirty Vodka Martini', 'Cosmopolitan', 'Espresso Martini', 'Latte', 'Coffee', 'Latte Macchiato', 'Iced Latte', 'Flat White', 'Espresso', 'Cold Brew Coffee', 'Vanilla Sweet Cream Cold Brew',
    'Sea Salt Milk Cap Cold Brew Coffee', 'Iced Americano', 'Americano', 'Cappuccino',
    'Hot Milk', 'Matcha Latte', 'Chocolate Milk', 'Hot Water', 'Raw Coconut Latte',
    'Iced Thick Coconut Latte', 'Hot Thick Coconut Latte', 'Iced Cappuccino', 'Iced Matcha Latte', 'Espresso Double',
    'Paper plane with sugar rim', 'Cosmopolitan', 'Cranberry whiskey sour with sugar rim', 'Vodka screwdriver',
    'Orange juice', 'Cranberry juice', 'Beer A', 'Beer B', 'Double Beer', 'Double Beer A', 'Double Beer B']

SUPPORT_ARDUINO_MATERIAL = Literal['sea_salt_foam', 'coconut_water', 'coconut_milk', 'vanilla_cream', 'fresh_dairy',
                                   'chocolate_syrup', 'green_tea_syrup', 'cold_coffee', 'vanilla_syrup']

TAP_DICT = {'sea_salt_foam': 0}


@router.post("/making_to_dance1", summary='let adam dance in music')
def making_to_dance1(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.making_to_dance1()
    return 'ok'


@router.post("/ring_bell_prepare", summary='let adam dance in music')
def ring_bell_prepare(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.ring_bell_prepare()
    return 'ok'


@router.post("/ring_bell_start", summary='let adam dance in music')
def ring_bell_start(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.ring_bell_start()
    return 'ok'


@router.post("/back_standby_pose", summary='let adam back standby pose')
def back_standby_pose(adam: Adam = Depends(get_adam_obj)):
    logger.info('back standby pose')
    adam.back_standby_pose()
    return 'ok'


@router.post("/parallel_arms", summary='let adam dance in music')
def parallel_arms(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.parallel_arms()
    return 'ok'


@router.post("/zero", summary='adam goto zero position')
def zero(adam: Adam = Depends(get_adam_obj)):
    logger.info('goto zero position')
    return adam.stop_and_goto_zero()


@router.post("/reset")
def standby_pose(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.stop_and_goto_zero()
        adam.goto_standby_pose()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/standby_pose")
def standby_pose(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_standby_pose()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


#                       IPO Event Requests                      #
@router.post("/take_shaker_and_ice")
def take_shaker_and_ice(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_shaker_and_ice()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_treacle")
def take_treacle(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_treacle()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/right_hand_take_treacle_and_put")
def right_hand_take_treacle_and_put(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.right_hand_take_treacle_and_put()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/wash_shaker")
def wash_shaker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.wash_shaker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_shaker")
def pour_shaker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_shaker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_beer")
def make_beer(which: Literal['left', 'right'], adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_beer(which)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_rotating_beers")
def make_rotating_beers(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_rotating_beers(formula)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/shake")
def shake(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.shake()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_cup_martini")
def take_cup_martini(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_cup_martini()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_5oz_cup")
def take_5oz_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_5oz_cup()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/dip_cup")
def dip_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.dip_cup()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_cup")
def put_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.put_cup()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_aperol")
def take_aperol(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_aperol()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_aperol")
def put_aperol(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.put_aperol()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_amero")
def take_amero(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_amero()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_amero")
def put_amero(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.put_amero()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_cointreau")
def take_cointreau(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_cointreau()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_cointreau")
def put_cointreau(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.put_cointreau()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_aperol")
def pour_aperol(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_aperol()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_amaro")
def pour_amaro(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_amaro()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_cointreau")
def pour_cointreau(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_cointreau()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_cointreau_cosmo")
def pour_cointreau_cosmo(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_cointreau_cosmo()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_paper_plane")
def make_paper_plane(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_paper_plane()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_cosmo")
def make_cosmo(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_cosmo()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_cranberry_juice")
def make_cranberry_juice(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_cranberry_juice()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_orange_juice")
def make_orange_juice(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_orange_juice()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_wiskey_sour")
def make_wiskey_sour(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_wiskey_sour()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_screwdriver")
def make_screwdriver(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_screwdriver()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/send_pump_command")
def send_pump_command(pump_num: str, pump_time: str, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.send_pump_command(pump_num, pump_time)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/moveto_packup_position")
def moveto_packup_position(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.moveto_packup_position()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_vodka")
def take_vodka(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_vodka()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_shaker")
def take_shaker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_shaker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_ice_maker")
def take_ice_maker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_ice_maker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_treacle")
def take_treacle(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_treacle()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pour_to_shaker")
def pour_to_shaker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.pour_to_shaker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/f1_shake")
def f1_shake(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.f1_shake()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/f1_put_shaker")
def f1_put_shaker(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.f1_put_shaker()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/shaker_pour")
def shaker_pour(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.shaker_pour()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_vermouth")
def take_vermouth(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_vermouth()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_vodka_martini")
def vodka_martini_demo(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_vodka_martini(formula)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/f1_make_drink")
def f1_make_drink(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.f1_make_drink(formula)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_gin_martini")
def gin_martini_demo(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_gin_martini(formula)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_cosmo_espresso")
def cosmo_espresso(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.make_cosmo_espresso(formula)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/warm_up")
def warm_up(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.warm_up()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/rotate_take_cup")
def rotate_take_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.rotate_take_cup()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_coffee_machine_espresso")
def take_coffee_machine_espresso(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.take_coffee_machine_espresso()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.get("/composition", summary='get_composition_by_option')
def get_composition(formula: SUPPORT_FORMULA, sweetness: int,
                    ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                    adam: Adam = Depends(get_adam_obj)):
    logger.info('get_composition')
    try:
        return adam.get_composition_by_option(formula, 'Medium Cup', sweetness, milk, ice)
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_wine", summary="take wine")
def take_wine(formula: define.SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    """
    """
    try:
        adam.take_wine(formula)
        return 'ok'
    except Exception as e:
        # logger.error(traceback.format_exc())
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_red_wine", summary='make_red_wine')
def make_red_wine(formula: str, sweetness: int, ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                  receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_red_wine')
    try:
        adam.make_red_wine(formula, sweetness, milk, ice, receipt_number)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_white_wine", summary='make_white_wine')
def make_white_wine(formula: str, sweetness: int, ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                    receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_white_wine')
    try:
        adam.make_white_wine(formula, sweetness, milk, ice, receipt_number)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_cold_drink", summary='make_cold_drink')
def make_cold_drink(formula: SUPPORT_FORMULA, sweetness: int,
                    ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                    receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_cold_drink')
    try:
        adam.make_cold_drink(formula, sweetness, milk, ice, receipt_number)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_hot_drink_event", summary='make_hot_drink for temp event only')
def make_hot_drink_event(formula: SUPPORT_FORMULA, sweetness: int,
                         ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                         receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_hot_drink_event')
    try:
        # adam.make_hot_drink_event(formula, sweetness, milk, ice, receipt_number)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/make_hot_drink", summary='make_hot_drink')
def make_hot_drink(formula: SUPPORT_FORMULA, sweetness: int,
                   ice: define.SUPPORT_ICE_TYPE, milk: define.SUPPORT_MILK_TYPE = define.MilkType.milk,
                   receipt_number: str = '', adam: Adam = Depends(get_adam_obj)):
    logger.info('make_hot_drink')
    try:
        # adam.make_hot_drink(formula, sweetness, milk, ice, receipt_number)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


# actions with left arm & right arm
@router.post("/pour", description="control adam's arm run to put the cup")
def pour(action: Literal['ice'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pour(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/pass_cup", description="Pass cup to right or left arm")
def pass_cup(action: Literal['from_left', 'from_right'], adam: Adam = Depends(get_adam_obj)):
    try:
        adam.pass_cup(action)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})
    except Exception as e:
        logger.debug(repr(e))
        logger.debug(str(e))


# left actions
@router.post("/take_hot_cup", description='take cup from left side of adam')
def take_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/check_sensor", description='take cup from left side of adam')
def check_sensor(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.check_sensor()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_daily_coffee", description='take cup from left side of adam')
def make_daily_coffee(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.make_daily_coffee()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_americano", description='take cup from left side of adam')
def take_americano(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_americano()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/classic_test_arduino", description="test arduino by charecter")
async def classic_test_arduino(char, adam: Adam = Depends(get_adam_obj)):
    try:
        logger.info('arduino_test')
        adam.classic_test_arduino(char)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_coffee_machine", description='make coffee from coffee_machine')
def take_coffee_machine(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        coffee_machine = composition.get('coffee_machine', {})
        logger.debug('coffee_machine = {}'.format(coffee_machine))
        adam.take_coffee_machine(coffee_machine)
        return 'ok'
    except Exception as e:
        raise e
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_from_bucket", description='take cup from bucket')
def take_from_bucket(formula: Literal['Tazo Tea', 'Americano'], adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.take_from_bucket(composition.get('bucket'), {})
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_ingredients", description='take cup from left side of adam')
def take_ingredients(arm: Literal['left', 'right'], formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.take_ingredients(arm, composition.get('tap', {}))
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/take_coffee_machine_demo", description='take cup from right side of adam')
def take_coffee_machine_demo(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_coffee_machine_demo()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


# right actions
@router.post("/take_cold_cup", description='take cup from right side of adam')
def take_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_foam_cup", description='take foam cup')
def take_foam_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.take_foam_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/take_ice", description='take ice from ice_machine')
def take_ice(ice: define.SUPPORT_ICE_TYPE, adam: Adam = Depends(get_adam_obj)):
    try:
        level = adam.get_ice_percent(ice)
        adam.take_ice(level)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/release_ice", description='release_ice from ice_machine')
def release_ice(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.release_ice()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/make_foam", description='take milk from tap and make foam')
def make_foam(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        adam.make_foam(composition.get(define.Constant.MachineType.foam_machine, {}))
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/clean_foamer", description='take cup from left side of adam')
def clean_foamer(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.clean_foamer()
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/put_hot_cup", description='take foam cup')
def put_hot_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_hot_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_foam_cup", description='take foam cup')
def put_foam_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_foam_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/put_cold_cup", description='take cup from right side of adam')
def put_cold_cup(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.put_cold_cup()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/arduino/test", description="go to pre position")
def arduino_test(name: SUPPORT_ARDUINO_MATERIAL, quantity: int, adam: Adam = Depends(get_adam_obj)):
    # def arduino_test(char, adam: Adam = Depends(get_adam_obj)):
    try:
        logger.info('arduino_test')
        open_dict = {name: int(quantity)}
        adam.arduino.open_port_together(open_dict)
        # adam.test_arduino(char)
        return 'ok'
    except Exception as e:
        return JSONResponse(status_code=510, content={'error': repr(e)})


@router.post("/dance", summary='let adam dance in music')
def dance(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.dance_in_thread()
    return 'ok'


@router.post("/dance1", summary='let adam dance in music')
def dance1(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.dance1_in_thread()
    return 'ok'


@router.post("/random_dance", summary='let adam dance in music')
def random_dance(choice: int, adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.dance_random(choice)
    return 'ok'


@router.post("/change_adam_status", summary='let adam dance in music')
def change_adam_status(status: str, adam: Adam = Depends(get_adam_obj)):
    logger.info('adam dance')
    adam.change_adam_status(status)
    return 'ok'


### China team made a new random_dance function
# @router.post("/random_dance", summary='let adam dance in music')
# def random_dance(adam: Adam = Depends(get_adam_obj)):
#     logger.info('adam random_dance')
#     adam.dance_random()
#     return 'ok'

@router.get("/status", summary='get adam task status')
def get_status(adam: Adam = Depends(get_adam_obj)):
    logger.info('get adam task status')
    # result = {'adam_status': adam.task_status, 'coffee_status': adam.coffee_thread.coffee_status}
    result = {'adam_status': adam.task_status, 'coffee_status': {'status': 'Idle'}}
    return result


@router.get("/tap_status", summary='get tap status')
def get_tap_status():
    logger.info('get_tap_status')
    result = adam_crud.get_all_status()
    return result


@router.post("/arduino/open", summary='open arduino serial')
async def open_arduino(adam: Adam = Depends(get_adam_obj)):
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead]:
        # adam.arduino.arduino.open()
        return 'ok'
    else:
        return JSONResponse(status_code=400,
                            content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/arduino/close", summary='close arduino serial')
async def close_arduino(adam: Adam = Depends(get_adam_obj)):
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead]:
        # adam.arduino.arduino.close()
        return 'ok'
    else:
        return JSONResponse(status_code=400,
                            content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/clean_tap", summary='clean tap')
async def open_tap(name: SUPPORT_ARDUINO_MATERIAL, action: Literal['0', '1'], adam: Adam = Depends(get_adam_obj)):
    logger.info('in open tap')
    if adam.task_status in [define.AdamTaskStatus.idle, define.AdamTaskStatus.stopped, define.AdamTaskStatus.dead]:
        tap_configs = CoffeeInterface.get_machine_config(machine=define.Constant.MachineType.tap)
        arduino_write_dict = {i.get('name'): i.get('arduino_write') for i in tap_configs}
        # adam.arduino.arduino.open()
        if action == '1':
            logger.debug('before send')
            adam.arduino.arduino.send_one_msg(arduino_write_dict.get(name))
            # adam.arduino.arduino.send_one_msg("1")
            logger.info('after _send')
            # logger.debug('send char {}'.format(arduino_write_dict.get(name)))
            adam_crud.update_one_tap(name, 1)
        else:
            close_char = chr(ord(str(arduino_write_dict.get(name))) + 48)  # 数字字符转英文字符
            # logger.debug('send char {}'.format(close_char))
            logger.info('before_send')
            adam.arduino.arduino.send_one_msg(close_char)
            # adam.arduino.arduino.send_one_msg('0')
            logger.info('after _send')
            adam_crud.update_one_tap(name, 0)
        # return 0
        return adam_crud.get_all_status()[name]
    else:
        return JSONResponse(status_code=400,
                            content={'error': 'Adam is busy now, status is {}'.format(adam.task_status)})


@router.post("/close_tap", summary='close all tap')
def close_tap(adam: Adam = Depends(get_adam_obj)):
    adam.arduino.arduino.open()
    adam.arduino.arduino.send_one_msg('0')
    adam.arduino.arduino.close()
    return 'ok'


@router.post("/clean_the_brewer", summary='clean_the_milk_froth')
def clean_the_brewer(adam: Adam = Depends(get_adam_obj)):
    if adam.coffee_driver.query_status().get('system_status') != MachineStatus.idle:
        AudioInterface.gtts('Coffee machine is busy now, please wait sometime')
        return JSONResponse(status_code=510, content={'error': 'Coffee machine is busy now, please wait sometime'})
    adam.coffee_driver.clean_the_brewer()
    while True:
        if adam.coffee_driver.query_status().get('system_status') == MachineStatus.idle:
            break
        else:
            time.sleep(1)
    return 'ok'


@router.post("/clean_the_milk_froth", summary='clean_the_milk_froth')
def clean_the_milk_froth(adam: Adam = Depends(get_adam_obj)):
    if adam.coffee_driver.query_status().get('system_status') != MachineStatus.idle:
        AudioInterface.gtts('Coffee machine is busy now, please wait sometime')
        return JSONResponse(status_code=510, content={'error': 'Coffee machine is busy now, please wait sometime'})
    AudioInterface.gtts('please check the coffee machine screen, and press the button')
    adam.coffee_driver.clean_the_milk_froth()
    while True:
        if adam.coffee_driver.query_status().get('system_status') == MachineStatus.idle:
            break
        else:
            time.sleep(1)
    return 'ok'


@router.post("/stop", summary='adam stop all action')
def stop(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam stop all action by http request')
    return adam.stop()


@router.post("/resume", summary='adam enable')
def resume(adam: Adam = Depends(get_adam_obj)):
    logger.info('adam enable')
    return adam.resume()


@router.post("/roll")
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.roll()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/open_gripper")
def roll(which: Literal['left', 'right'], position: int, adam: Adam = Depends(get_adam_obj)):
    try:
        adam.goto_gripper_position(which, position)
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/manual")
def manual(which: Literal['left', 'right'], action: Literal['close', 'open'], adam: Adam = Depends(get_adam_obj)):
    try:
        if action == 'open':
            return adam.manual(which, mode=2)
        else:
            return adam.manual(which, mode=0)
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/init")
def init(adam: Adam = Depends(get_adam_obj)):
    try:
        adam.init_adam()
        return 'ok'
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/coffee_status")
def roll(adam: Adam = Depends(get_adam_obj)):
    try:
        return adam.coffee_driver.query_status()
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})


@router.post("/coffee_make")
def roll(formula: SUPPORT_FORMULA, adam: Adam = Depends(get_adam_obj)):
    try:
        composition = adam.get_composition_by_option(formula, 'Medium Cup', 100, 'fresh_dairy')
        coffee_machine = composition.get('coffee_machine', {})
        for name, config in coffee_machine.items():
            adam.coffee_driver.make_coffee_from_dict(config.get('coffee_make'))
    except MoveError as e:
        return JSONResponse(status_code=510, content={'error': str(e)})
