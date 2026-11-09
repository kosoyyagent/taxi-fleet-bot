"""Хендлеры aiogram: роли owner/admin видят админ-меню, driver — кабинет водителя."""
from datetime import date
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from db import SessionLocal
from services import FleetService
from keyboards import OWNER_KB, DRIVER_KB, confirm_payment_kb

router = Router()


def svc():
    return FleetService(SessionLocal())


class AddCar(StatesGroup):
    plate = State(); model = State()


class AddDriver(StatesGroup):
    tg_id = State(); name = State(); rent = State(); car = State()


class Pay(StatesGroup):
    amount = State(); photo = State()


class Mileage(StatesGroup):
    value = State(); photo = State()


class IssueReport(StatesGroup):
    text = State(); photo = State()


def _role(s: FleetService, tg_id: int) -> str:
    d = s.driver_by_tg(tg_id)
    if d:
        return "driver"
    from models import User
    u = s.s.query(User).filter_by(tg_id=tg_id).one_or_none()
    return u.role if u else "owner"  # первый старт — владелец (рег. код в проде)


@router.message(CommandStart())
async def start(m: Message):
    s = svc()
    u = s.get_or_create_user(m.from_user.id, m.from_user.full_name)
    role = _role(s, m.from_user.id)
    kb = DRIVER_KB if role == "driver" else OWNER_KB
    await m.answer(f"Автопарк MVP. Роль: {role}", reply_markup=kb)


# ============ ВЛАДЕЛЕЦ ============
@router.message(F.text == "🚗 Автомобили")
async def cars(m: Message):
    s = svc()
    lines = [f"{c.plate} · {c.model} · {c.status} · {c.mileage} км" for c in s.list_cars()]
    await m.answer("\n".join(lines) or "Авто нет. Добавьте: /add_car")


@router.message(F.text == "👷 Водители")
async def drivers(m: Message):
    s = svc()
    from models import Driver
    ds = s.s.query(Driver).filter_by(active=True).all()
    lines = [f"{d.full_name} · аренда {d.rent_amount} ₽ · долг {s.driver_debt(d.id)} ₽"
             for d in ds]
    await m.answer("\n".join(lines) or "Водителей нет. Добавьте: /add_driver")


@router.message(F.text == "💰 Платежи на проверке")
async def pending(m: Message):
    s = svc()
    ps = s.pending_payments()
    if not ps:
        return await m.answer("Неподтверждённых платежей нет")
    for p in ps:
        await m.answer(f"#{p.id} {p.driver.full_name}: {p.amount} ₽",
                       reply_markup=confirm_payment_kb(p.id))


@router.callback_query(F.data.startswith("pay_"))
async def pay_decision(cb: CallbackQuery):
    s = svc()
    ok, pid = cb.data.split(":")[0] == "pay_ok", int(cb.data.split(":")[1])
    p = s.confirm_payment(pid, ok=ok)
    await cb.message.edit_text(f"Платёж #{pid}: {'подтверждён' if ok else 'отклонён'}")
    await cb.answer()


@router.message(F.text == "📊 Статистика")
async def stats(m: Message):
    st = svc().stats()
    await m.answer(
        f"Авто: {st['cars_total']} (аренда {st['cars_rented']}, свободно {st['cars_free']}, ремонт {st['cars_repair']})\n"
        f"Водителей: {st['drivers']}\nДоход подтверждённый: {st['income_total']} ₽\n"
        f"Общий долг: {st['debt_total']} ₽\nОткрытых неисправностей: {st['open_issues']}")


# --- добавление авто ---
@router.message(F.text == "/add_car")
async def add_car(m: Message, state: FSMContext):
    await state.set_state(AddCar.plate)
    await m.answer("Госномер?")


@router.message(AddCar.plate)
async def ac_plate(m: Message, state: FSMContext):
    await state.update_data(plate=m.text.strip())
    await state.set_state(AddCar.model)
    await m.answer("Модель?")


@router.message(AddCar.model)
async def ac_model(m: Message, state: FSMContext):
    d = await state.get_data()
    c = svc().add_car(d["plate"], m.text.strip())
    await state.clear()
    await m.answer(f"Авто {c.plate} добавлено", reply_markup=OWNER_KB)


# --- добавление водителя ---
@router.message(F.text == "/add_driver")
async def add_driver(m: Message, state: FSMContext):
    await state.set_state(AddDriver.tg_id)
    await m.answer("Telegram ID водителя (узнает через @userinfobot)?")


@router.message(AddDriver.tg_id)
async def ad_tg(m: Message, state: FSMContext):
    await state.update_data(tg_id=int(m.text.strip()))
    await state.set_state(AddDriver.name)
    await m.answer("ФИО?")


@router.message(AddDriver.name)
async def ad_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await state.set_state(AddDriver.rent)
    await m.answer("Аренда ₽/нед?")


@router.message(AddDriver.rent)
async def ad_rent(m: Message, state: FSMContext):
    d = await state.get_data()
    dr = svc().add_driver(d["tg_id"], d["name"], int(m.text.strip()))
    await state.clear()
    await m.answer(f"Водитель {dr.full_name} добавлен. Закрепить авто: /bind {dr.id} <car_id>",
                   reply_markup=OWNER_KB)


# ============ ВОДИТЕЛЬ ============
@router.message(F.text == "💳 Моя аренда")
async def my_rent(m: Message):
    s = svc()
    d = s.driver_by_tg(m.from_user.id)
    if not d:
        return await m.answer("Вы не зарегистрированы как водитель")
    debt = s.driver_debt(d.id)
    await m.answer(f"Аренда: {d.rent_amount} ₽/нед\nЗадолженность: {debt} ₽")


@router.message(F.text == "📤 Отправить оплату")
async def pay_start(m: Message, state: FSMContext):
    await state.set_state(Pay.amount)
    await m.answer("Сумма оплаты, ₽?")


@router.message(Pay.amount)
async def pay_amount(m: Message, state: FSMContext):
    await state.update_data(amount=int(m.text.strip()))
    await state.set_state(Pay.photo)
    await m.answer("Пришлите фото чека")


@router.message(Pay.photo, F.photo)
async def pay_photo(m: Message, state: FSMContext):
    d = await state.get_data()
    s = svc()
    dr = s.driver_by_tg(m.from_user.id)
    p = s.submit_payment(dr.id, d["amount"], m.photo[-1].file_id)
    await state.clear()
    await m.answer(f"Оплата #{p.id} отправлена на проверку", reply_markup=DRIVER_KB)


@router.message(F.text == "🛣 Передать пробег")
async def mil_start(m: Message, state: FSMContext):
    await state.set_state(Mileage.value)
    await m.answer("Текущий пробег, км?")


@router.message(Mileage.value)
async def mil_value(m: Message, state: FSMContext):
    s = svc()
    dr = s.driver_by_tg(m.from_user.id)
    if not dr or not dr.car:
        await state.clear()
        return await m.answer("За вами не закреплено авто")
    try:
        log = s.record_mileage(dr.car.id, int(m.text.strip()))
    except ValueError as e:
        await state.clear()
        return await m.answer(str(e))
    left = s.km_to_service(dr.car)
    await state.clear()
    await m.answer(f"Пробег {log.mileage} км записан. До ТО: {left} км",
                   reply_markup=DRIVER_KB)


@router.message(F.text == "🔧 Сообщить о неисправности")
async def issue_start(m: Message, state: FSMContext):
    await state.set_state(IssueReport.text)
    await m.answer("Опишите неисправность текстом; фото можно следующим сообщением")


@router.message(IssueReport.text)
async def issue_text(m: Message, state: FSMContext):
    s = svc()
    dr = s.driver_by_tg(m.from_user.id)
    i = s.report_issue(dr.car.id if dr and dr.car else None, dr.id if dr else None, m.text)
    await state.clear()
    await m.answer(f"Неисправность #{i.id} передана владельцу", reply_markup=DRIVER_KB)
