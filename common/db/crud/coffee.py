import json
import os
import uuid
from typing import List

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from common.define import TaskStatus, AudioConstant, audio_dir
from common.db.tables import coffee as coffee_table
from common.schemas import coffee as coffee_schema
from common.myerror import DBError
from common.define import Constant
from common.db.database import get_db
import random

db = next(get_db())


# Coffee
def get_task_uuid_status(db: Session, task_uuid):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
        return record.status


def add_new_coffee_task(db: Session, value: dict):
    record = coffee_table.Coffee(**value)
    db.add(record)
    db.commit()
    logger.info('add_new_coffee_task task={}'.format(value))


def get_one_waiting_record(db: Session, task_uuid=None) -> coffee_schema.CoffeeRecord:
    if task_uuid:
        if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).order_by(
                coffee_table.Coffee.id.asc()).first():
            return coffee_schema.CoffeeRecord.from_orm(record)
    else:
        if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting).order_by(
                coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first():
            return coffee_schema.CoffeeRecord.from_orm(record)


def get_one_waiting_record_by_type(db: Session, type=None):
    if type == Constant.FormulaType.white:
        if white_record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
                                                                coffee_table.Coffee.type == type).order_by(
            coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first():
            return coffee_schema.CoffeeRecord.from_orm(white_record)
    elif type == Constant.FormulaType.red:
        if red_record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
                                                              coffee_table.Coffee.type == type).order_by(
            coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first():
            return coffee_schema.CoffeeRecord.from_orm(red_record)
    # if processing_records := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.processing).order_by(
    #         coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).all():
    #     if len(processing_records) == 1:
    #         if processing_records[0].type == Constant.FormulaType.red:
    #             white_record = db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
    #                                                                 coffee_table.Coffee.type == Constant.FormulaType.white).order_by(
    #                 coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first()
    #             return coffee_schema.CoffeeRecord.from_orm(white_record)
    #         else:
    #             red_record = db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
    #                                                               coffee_table.Coffee.type == Constant.FormulaType.red).order_by(
    #                 coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first()
    #             return coffee_schema.CoffeeRecord.from_orm(red_record)
    # else:
    #     if red_record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
    #                                                           coffee_table.Coffee.type == Constant.FormulaType.red).order_by(
    #             coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first():
    #         return coffee_schema.CoffeeRecord.from_orm(red_record)
    #     elif white_record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting,
    #                                                               coffee_table.Coffee.type == Constant.FormulaType.white).order_by(
    #             coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).first():
    #         return coffee_schema.CoffeeRecord.from_orm(white_record)


def get_one_processing_record(db: Session):
    if processing_records := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status.in_([TaskStatus.processing, TaskStatus.waiting])).order_by(
            coffee_table.Coffee.create_time.asc(), coffee_table.Coffee.id.asc()).all():
        return False
    else:
        return True


def exist_next_record(db: Session):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status == TaskStatus.waiting).order_by(
            coffee_table.Coffee.id.asc()).first():
        return record.task_uuid


def update_coffee_by_task_uuid(db: Session, task_uuid, update_dict: dict):
    if record := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.task_uuid == task_uuid).first():
        for key, value in update_dict.items():
            setattr(record, key, value)
        db.add(record)
        logger.info('update task_uuid={} value={}'.format(task_uuid, update_dict))
        db.commit()


def init_all_records_device_and_status(db: Session):
    if records := db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status != TaskStatus.completed).filter(
            coffee_table.Coffee.status != TaskStatus.failed).all():
        for record in records:
            record.status = TaskStatus.waiting
            db.add(record)
            logger.warning('set task_uuid={} status {} -> {}'.format(
                record.task_uuid, TaskStatus.processing, TaskStatus.waiting))
        db.commit()


# MaterialCurrent
def add_material(db: Session, new_dict):
    material = coffee_table.MaterialCurrent(**new_dict)
    old_material = get_material(db, name=material.name)
    if old_material:
        raise DBError('add error, material={} has already exist'.format(material.name))
    else:
        db.add(material)
    db.commit()
    logger.info('add_new_material, dict={}'.format(new_dict))


def get_material(db: Session, name=None, in_use=None) -> List[coffee_table.MaterialCurrent]:
    conditions = []
    if name:
        conditions.append(coffee_table.MaterialCurrent.name == name)
    if in_use is not None:
        conditions.append(coffee_table.MaterialCurrent.in_use == in_use)
    materials = db.query(coffee_table.MaterialCurrent).filter(*conditions).all()
    return materials


def use_material(db: Session, name, quantity) -> coffee_table.MaterialCurrent:
    material = db.query(coffee_table.MaterialCurrent).filter_by(name=name, in_use=Constant.InUse.in_use).first()
    if material:
        material.count += 1
        material.left = round(material.left - quantity * material.batch, 2)
        material.left = 0 if material.left < 0 else material.left
        db.commit()
        return material
    else:
        raise DBError(' there is no material named {} in use'.format(name))


def update_material(db: Session, name, update_dict):
    material = db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first()
    if material:
        for k, v in update_dict.items():
            if v != None:
                setattr(material, k, v)
        db.commit()
    else:
        raise DBError('there are no material named {}'.format(name))


def reset_material(db: Session, names: List):
    for name in names:
        material = db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first()
        if material:
            history = coffee_table.AddMaterialHistory(name=material.name, before_add=material.left, count=material.count,
                                                      add=round(material.capacity - material.left, 2))
            db.add(history)

            material.left = material.capacity
            material.count = 0
        else:
            db.rollback()
            raise DBError('there are no material named {}'.format(material))
    db.commit()


def update_material_volume(db: Session, name, volume):
    if record := db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first():
        record.count += 1
        record.left -= volume
        record.left = 0 if record.left < 0 else record.left
        db.add(record)
        db.commit()
        return record.left


def get_material_capacity_left(db: Session) -> List[coffee_schema.MaterialCurrentRecord]:
    if records := db.query(coffee_table.MaterialCurrent).all():
        records = [coffee_schema.MaterialCurrentRecord.from_orm(record) for record in records]
        return records


def reset_material_capacity(db: Session, name):
    if record := db.query(coffee_table.MaterialCurrent).filter(coffee_table.MaterialCurrent.name == name).first():
        orm_record = coffee_schema.MaterialCurrentRecord.from_orm(record)
        history_record = coffee_table.AddMaterialHistory(**orm_record.dict())
        db.add(history_record)
        record.count = 0
        record.left = record.capacity
        db.add(record)
        db.commit()


# init
def init_data(db: Session, file):
    logger.warning('init data ..............')
    with open(file, 'r') as f:
        for line in f.readlines():
            if not line.startswith('--') and line != ('\n'):
                try:
                    db.execute(line)
                    db.commit()
                except IntegrityError:
                    db.rollback()


def init_service(db: Session):
    logger.warning('start service, clean queue msg')
    db.query(coffee_table.Coffee).filter(coffee_table.Coffee.status.in_([TaskStatus.waiting, TaskStatus.processing])).delete()
    db.commit()


# Formula
def add_formula(db: Session, new_dict):
    """
    new_dict:  {name: str, type: str, in_use: int, composition: dict}
    """
    composition_dict = new_dict.pop('composition')
    formula = coffee_table.Formula(**new_dict)
    old_formula = get_formula(db, formula.name, formula.cup)
    if old_formula:
        raise DBError('add error, formula={} has already exist'.format(formula.name))
    else:
        cup_obj = get_material(db, formula.cup, Constant.InUse.in_use)
        if not cup_obj:
            db.rollback()
            raise DBError('add error, there are no cup named {}'.format(formula.cup))
        db.add(formula)
        for material, count in composition_dict.items():
            material_obj = get_material(db, material)
            if material_obj:
                old_composition = db.query(coffee_table.Composition).filter_by(formula=formula.name,
                                                                               cup=formula.cup,
                                                                               material=material).first()
                if old_composition:
                    db.rollback()
                    raise DBError(
                        'composition formula={}, cup={}, material={} has already exist, please update/delete it'.format(
                            formula.name, formula.cup, material))

                composition = coffee_table.Composition(formula=formula.name, cup=formula.cup,
                                                       material=material, count=count)
                db.add(composition)
            else:
                db.rollback()
                raise DBError('add error, there no material named {}'.format(material))
        db.commit()
    logger.info('add_formula, dict={}'.format(new_dict))


def get_formula(db: Session, name=None, cup=None, in_use=None) -> List[coffee_table.Formula]:
    conditions = []
    if name:
        conditions.append(coffee_table.Formula.name == name)
    if cup:
        conditions.append(coffee_table.Formula.cup == cup)
    if in_use:
        conditions.append(coffee_table.Formula.in_use == in_use)
    formulas = db.query(coffee_table.Formula).filter(*conditions).all()
    return formulas


def update_formula(db: Session, name, cup, update_dict):
    formula = db.query(coffee_table.Formula).filter_by(name=name, cup=cup).first()
    if formula:
        for k, v in update_dict.items():
            if v != None:
                setattr(formula, k, v)
        db.commit()
    else:
        raise DBError('there are no formula named {} with cup={}'.format(name, cup))


def delete_formula(db: Session, name, cup):
    try:
        db.query(coffee_table.Formula).filter_by(name=name, cup=cup).delete()
        db.query(coffee_table.Composition).filter_by(formula=name, cup=cup).delete()
        db.commit()
        return 1, 'success'
    except Exception as e:
        db.rollback()
        return 0, e


# Composition
def add_composition(db: Session, formula_name, cup, composition_list):
    """
    material_list: [{'name':'milk', 'count':80}]
    """
    formula = get_formula(db, formula_name)
    if not formula:
        raise DBError('no formula names={}, please check again'.format(formula_name))
    for material in composition_list:
        material_name = material.get('name')
        material_obj = get_material(db, name=material_name)
        if not material_obj:
            db.rollback()
            raise DBError('no material names={}, please check again'.format(material_name))
        old_composition = db.query(coffee_table.Composition).filter_by(formula=formula_name,
                                                                       cup=cup,
                                                                       material=material_name).first()
        if old_composition:
            db.rollback()
            raise DBError(
                'composition formula={}, material={} has already exist, please update/delete it'.format(formula_name,
                                                                                                        material_name))
        composition = coffee_table.Composition(formula=formula_name, material=material_name, cup=cup,
                                               count=material.get('count'))
        db.add(composition)
    db.commit()
    logger.info('add_composition, formula={}, composition{}'.format(formula_name, composition_list))


def get_composition_by_formula(db: Session, formula, cup, formula_in_use=None) -> dict:
    """
    return: {'material': {'count': 100, 'left':100, 'type': 'base_milktea', 'machine': 'tap_l', 'in_use': 1}}
    """
    formula_obj = get_formula(db, formula, cup, formula_in_use)
    if not formula_obj:
        return {}
    compositions = db.query(coffee_table.Composition).filter_by(formula=formula, cup=cup).all()
    return_data = {}
    for composition in compositions:
        materials = get_material(db, composition.material)
        logger.info('search {}, result={}'.format(composition.material, materials))
        if materials:
            material = materials[0]
            material_data = dict(count=composition.count, left=material.left, type=material.type,
                                 machine=material.machine, in_use=material.in_use)
            if material.machine == 'foam_machine':
                try:
                    material_data['extra'] = json.loads(composition.extra)
                except Exception:
                    pass
            if material.machine == 'coffee_machine':
                material_data['coffee_make'] = get_espresso_by_formula(db, formula)
            return_data[composition.material] = material_data
    return return_data


def update_composition_count(db: Session, formula, cup, material, count):
    composition = db.query(coffee_table.Composition).filter_by(formula=formula, cup=cup, material=material).first()
    if composition:
        composition.count = count
        db.commit()
    else:
        raise ('there are no composition of formula={}, cup={}, material={}'.format(formula, cup, material))


def delete_composition(db: Session, formula, material=None):
    if material:
        db.query(coffee_table.Composition).filter_by(formula=formula, material=material).delete()
    else:
        db.query(coffee_table.Composition).filter_by(formula=formula).delete()
    db.commit()


# Machine_Config
def _check_config(machine_config):
    pass


def add_machine_config(db: Session, new_dict):
    machine_config = coffee_table.MachineConfig(**new_dict)
    if machine_config.gpio is not None:
        if machine_config.speed is None or machine_config.delay_time is None or machine_config.type is None:
            raise DBError('speed or delay_time or type is necessary with gpio')

    material_name = machine_config.name.split('_')[0]
    material_obj = get_material(db, material_name)
    if not material_obj:
        db.rollback()
        raise DBError('no material names={}, please check again'.format(material_name))
    material_obj = material_obj[0]
    if material_obj.machine != machine_config.machine:
        raise DBError('material {}\'s machine is {} while machine_config\'s machine is {}'.format(material_name,
                                                                                                  material_obj.machine,
                                                                                                  machine_config.machine))
    old_machine_config = db.query(coffee_table.MachineConfig).filter_by(name=machine_config.name).first()
    if old_machine_config:
        db.rollback()
        raise DBError(
            'machine_config with name={} has already exist, please update/delete it'.format(machine_config.name))
    db.add(machine_config)
    db.commit()
    logger.info('add_machine_config, dict={}'.format(new_dict))


def get_machine_config(db: Session, name=None, machine=None) -> List[coffee_table.MachineConfig]:
    conditions = []
    if name:
        conditions.append(coffee_table.MachineConfig.name == name)
    if machine:
        conditions.append(coffee_table.MachineConfig.machine == machine)
    configs = db.query(coffee_table.MachineConfig).filter(*conditions).all()
    return configs


def update_machine_config_by_name(db: Session, name, update_dict):
    gpio_config = db.query(coffee_table.MachineConfig).filter_by(name=name).first()
    if gpio_config:
        for k, v in update_dict.items():
            if v != None:
                setattr(gpio_config, k, v)
        db.commit()
    else:
        raise DBError('there are no gpio config with name={}'.format(name))


# Espresso
def get_espresso_by_formula(db: Session, formula):
    espresso = db.query(coffee_table.Espresso).filter_by(formula=formula).first()
    if espresso:
        return espresso.to_coffee_dict()


# SpeechText
def choose_one_speech_text(db: Session, code: str):
    if code in AudioConstant.TextCode.LOCAL_CODE.keys():
        file_name = '{}{}.mp3'.format(code, random.randint(1, AudioConstant.TextCode.LOCAL_CODE.get(code)))
        path = os.path.join(audio_dir, 'voices', file_name)
        if os.path.exists(path):
            return path

    speech_texts = db.query(coffee_table.SpeechText).filter_by(code=code).all()
    if speech_texts:
        return random.choice(speech_texts).text
    else:
        return ''


def get_all_text(db: Session, code: str = None):
    conditions = []
    if code:
        conditions.append(coffee_table.SpeechText.code == code)
    speech_texts = db.query(coffee_table.SpeechText).filter(*conditions).all()
    result = []
    for text in speech_texts:
        result.append(text.to_dict())
    return result


def add_text(db: Session, text, code):
    old_text = db.query(coffee_table.SpeechText).filter_by(code=code, text=text).first()
    if old_text:
        return 'ok'
    text = coffee_table.SpeechText(code=code, text=text)
    db.add(text)
    db.commit()
    logger.info('add_text, code={}, text{}'.format(code, text))
    return 'ok'


def update_text_by_id(db: Session, text_id: int, code: str = None, text: str = None):
    old_text = db.query(coffee_table.SpeechText).filter_by(id=text_id).first()
    if old_text:
        if code:
            old_text.code = code
        if text:
            old_text.text = text
        db.commit()


def delete_text_by_id(db: Session, id: int):
    db.query(coffee_table.SpeechText).filter_by(id=id).delete()
    db.commit()
