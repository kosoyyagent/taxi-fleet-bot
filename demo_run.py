"""E2E-прогон бизнес-логики без Telegram: владелец заводит парк, водитель платит,
передаёт пробег, репортит неисправность, срабатывают напоминания. Печатает транскрипт."""
import os, sys
from datetime import date, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["FLEET_DB_URL"] = "sqlite:///demo_fleet.db"
if os.path.exists("demo_fleet.db"):
    os.remove("demo_fleet.db")

from db import init_db, SessionLocal
from services import FleetService

L = lambda *a: print(*a)

init_db()
s = FleetService(SessionLocal())

L("=== СЦЕНАРИЙ АВТОПАРКА (E2E по сервисному слою) ===\n")

L("— Владелец заводит автомобили —")
c1 = s.add_car("А123БВ777", "Kia Rio 2021", to_interval_km=10000,
              insurance_until=date.today() + timedelta(days=10))
c2 = s.add_car("Е456КХ777", "Hyundai Solaris 2022")
c3 = s.add_car("М789ОР777", "Skoda Octavia 2020")
L(f"  + {c1.plate} {c1.model}; страховка до {c1.insurance_until}")
L(f"  + {c2.plate} {c2.model}")
L(f"  + {c3.plate} {c3.model}")

L("\n— Владелец добавляет водителей и закрепляет авто —")
d1 = s.add_driver(111111, "Иван Петров", rent_amount=6000, rent_due_day=0)
d2 = s.add_driver(222222, "Сергей Сидоров", rent_amount=5500, rent_due_day=2)
s.assign_car(d1.id, c1.id); L(f"  {d1.full_name} -> {c1.plate} (аренда {d1.rent_amount} ₽/нед)")
s.assign_car(d2.id, c2.id); L(f"  {d2.full_name} -> {c2.plate} (аренда {d2.rent_amount} ₽/нед)")
L(f"  {c3.plate} осталась свободна (status={s.s.get(type(c3), c3.id).status})")

L("\n— Водитель Иван платит аренду и шлёт фото чека —")
p1 = s.submit_payment(d1.id, 6000, "FILE_ID_CHECK_001")
L(f"  платёж #{p1.id}: {p1.amount} ₽, статус {p1.status}")
p2 = s.submit_payment(d2.id, 5500, "FILE_ID_CHECK_002")
L(f"  платёж #{p2.id}: {p2.amount} ₽, статус {p2.status}")

L("\n— Владелец проверяет очередь платежей и подтверждает —")
for p in s.pending_payments():
    s.confirm_payment(p.id, ok=True)
    L(f"  платёж #{p.id} подтверждён")

L("\n— Пробеги от водителей —")
s.record_mileage(c1.id, 9500, "FILE_ID_ODO_1"); L(f"  {c1.plate}: 9500 км, до ТО {s.km_to_service(c1)} км")
s.record_mileage(c2.id, 21000, "FILE_ID_ODO_2"); L(f"  {c2.plate}: 21000 км, до ТО {s.km_to_service(c2)} км")
try:
    s.record_mileage(c1.id, 9000)
except ValueError as e:
    L(f"  защита: откат пробега отклонён («{e}»)")

L("\n— Водитель репортит неисправность —")
i = s.report_issue(c2.id, d2.id, "Стук в подвеске справа", "FILE_ID_PHOTO_1")
L(f"  неисправность #{i.id}: {i.text} ({c2.plate})")

L("\n— Планировщик: что уйдёт сегодня —")
for ev in s.reminders_due(date.today()):
    if ev["type"] == "rent_due":
        L(f"  → водителю {ev['driver']} (tg {ev['tg_id']}): платёж {ev['amount']} ₽")
    elif ev["type"] == "to_soon":
        L(f"  → владельцу: ТО скоро {ev['car']}, осталось {ev['km_left']} км")
    elif ev["type"] == "insurance":
        L(f"  → владельцу: страховка {ev['car']} до {ev['until']}")
    elif ev["type"] == "debt":
        L(f"  → владельцу: долг {ev['driver']} = {ev['debt']} ₽")

L("\n— Статистика для владельца —")
st = s.stats()
for k, v in st.items():
    L(f"  {k}: {v}")

L("\n=== ПРОГОН ЗАВЕРШЁН: все сценарии выполнены без ошибок ===")
