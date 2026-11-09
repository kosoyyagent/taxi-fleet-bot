"""Бизнес-логика автопарка. Отделена от aiogram — тестируется без Telegram."""
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from models import User, Car, Driver, Payment, MileageLog, Issue


class FleetService:
    def __init__(self, session: Session):
        self.s = session

    # ---------- пользователи/роли ----------
    def get_or_create_user(self, tg_id: int, name: str, role: str = "driver") -> User:
        u = self.s.query(User).filter_by(tg_id=tg_id).one_or_none()
        if not u:
            u = User(tg_id=tg_id, name=name, role=role)
            self.s.add(u)
            self.s.commit()
        return u

    # ---------- автомобили ----------
    def add_car(self, plate: str, model: str, to_interval_km: int = 10000,
                insurance_until: date | None = None) -> Car:
        if self.s.query(Car).filter_by(plate=plate).one_or_none():
            raise ValueError(f"Авто {plate} уже есть в базе")
        c = Car(plate=plate, model=model, to_interval_km=to_interval_km,
                insurance_until=insurance_until)
        self.s.add(c)
        self.s.commit()
        return c

    def list_cars(self) -> list[Car]:
        return self.s.query(Car).order_by(Car.plate).all()

    def set_car_status(self, car_id: int, status: str) -> Car:
        c = self.s.get(Car, car_id)
        c.status = status
        self.s.commit()
        return c

    # ---------- водители ----------
    def add_driver(self, tg_id: int, full_name: str, rent_amount: int,
                   rent_due_day: int = 1, phone: str | None = None) -> Driver:
        u = self.get_or_create_user(tg_id, full_name, role="driver")
        d = Driver(user_id=u.id, full_name=full_name, rent_amount=rent_amount,
                   rent_due_day=rent_due_day)
        self.s.add(d)
        self.s.commit()
        return d

    def assign_car(self, driver_id: int, car_id: int) -> Car:
        d = self.s.get(Driver, driver_id)
        c = self.s.get(Car, car_id)
        if c.driver_id:
            raise ValueError(f"Авто {c.plate} уже закреплено")
        c.driver_id = d.id
        c.status = "rented"
        self.s.commit()
        return c

    def unassign_car(self, car_id: int) -> Car:
        c = self.s.get(Car, car_id)
        c.driver_id = None
        c.status = "free"
        self.s.commit()
        return c

    def driver_by_tg(self, tg_id: int) -> Driver | None:
        return (self.s.query(Driver).join(User, Driver.user_id == User.id)
                .filter(User.tg_id == tg_id).one_or_none())

    # ---------- платежи ----------
    def submit_payment(self, driver_id: int, amount: int, photo_file_id: str) -> Payment:
        p = Payment(driver_id=driver_id, amount=amount, photo_file_id=photo_file_id)
        self.s.add(p)
        self.s.commit()
        return p

    def confirm_payment(self, payment_id: int, ok: bool = True, note: str = "") -> Payment:
        p = self.s.get(Payment, payment_id)
        p.status = "confirmed" if ok else "rejected"
        p.confirmed_at = datetime.now()
        p.note = note
        self.s.commit()
        return p

    def driver_debt(self, driver_id: int, weeks_back: int = 12) -> int:
        """Долг = аренда за прошедшие дни платежа с даты добавления - подтверждённые оплаты."""
        d = self.s.get(Driver, driver_id)
        start = (d.created_at or datetime.now()).date()
        today = date.today()
        weeks = (today - start).days // 7 + (1 if today.weekday() >= d.rent_due_day else 0)
        weeks = min(weeks_back, weeks)
        if weeks <= 0:
            return 0
        since = datetime.now() - timedelta(weeks=weeks)
        paid = sum(p.amount for p in self.s.query(Payment)
                   .filter(Payment.driver_id == driver_id,
                           Payment.status == "confirmed",
                           Payment.created_at >= since).all())
        return max(0, d.rent_amount * weeks - paid)

    def pending_payments(self) -> list[Payment]:
        return self.s.query(Payment).filter_by(status="pending").all()

    # ---------- пробег / ТО ----------
    def record_mileage(self, car_id: int, mileage: int, photo_file_id: str = "") -> MileageLog:
        c = self.s.get(Car, car_id)
        if mileage < c.mileage:
            raise ValueError("Пробег меньше предыдущего — проверьте фото одометра")
        c.mileage = mileage
        log = MileageLog(car_id=car_id, mileage=mileage, photo_file_id=photo_file_id)
        self.s.add(log)
        self.s.commit()
        return log

    def km_to_service(self, car: Car) -> int:
        return car.last_to_mileage + car.to_interval_km - car.mileage

    # ---------- неисправности ----------
    def report_issue(self, car_id: int, driver_id: int | None, text: str,
                     photo_file_id: str = "") -> Issue:
        i = Issue(car_id=car_id, driver_id=driver_id, text=text,
                  photo_file_id=photo_file_id)
        self.s.add(i)
        self.s.commit()
        return i

    # ---------- напоминания (вызываются планировщиком) ----------
    def reminders_due(self, today: date | None = None) -> list[dict]:
        """Кому что напомнить сегодня. Возвращает список событий."""
        today = today or date.today()
        out = []
        drivers = self.s.query(Driver).filter_by(active=True).all()
        for d in drivers:
            u = self.s.get(User, d.user_id)
            if today.weekday() == d.rent_due_day and d.rent_amount:
                out.append({"type": "rent_due", "tg_id": u.tg_id, "driver": d.full_name,
                            "amount": d.rent_amount})
        for c in self.list_cars():
            left = self.km_to_service(c)
            if 0 < left <= 1000:
                out.append({"type": "to_soon", "tg_id": None, "car": c.plate,
                            "km_left": left})
            if c.insurance_until and 0 <= (c.insurance_until - today).days <= 14:
                out.append({"type": "insurance", "tg_id": None, "car": c.plate,
                            "until": c.insurance_until.isoformat()})
        debtors = [(d, self.driver_debt(d.id)) for d in drivers]
        for d, debt in debtors:
            if debt > 0:
                out.append({"type": "debt", "tg_id": None, "driver": d.full_name,
                            "debt": debt})
        return out

    # ---------- аналитика ----------
    def stats(self) -> dict:
        cars = self.list_cars()
        confirmed = self.s.query(Payment).filter_by(status="confirmed").all()
        drivers = self.s.query(Driver).filter_by(active=True).all()
        return {
            "cars_total": len(cars),
            "cars_rented": sum(1 for c in cars if c.status == "rented"),
            "cars_free": sum(1 for c in cars if c.status == "free"),
            "cars_repair": sum(1 for c in cars if c.status == "repair"),
            "income_total": sum(p.amount for p in confirmed),
            "drivers": len(drivers),
            "debt_total": sum(self.driver_debt(d.id) for d in drivers),
            "open_issues": self.s.query(Issue).filter_by(status="open").count(),
        }
