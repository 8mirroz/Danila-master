#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone

# Add the parent directory of this script to the python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from sqlmodel import Session, select, delete
from database import engine, init_db
from models import PartRequest

def main():
    print("Инициализация базы данных...")
    init_db()

    with Session(engine) as session:
        # Check if the test order already exists and delete it (using safe SQLModel delete)
        print("Проверка наличия старого тестового заказа REQ-TEST8888...")
        session.exec(delete(PartRequest).where(PartRequest.request_id == "REQ-TEST8888"))
        session.commit()

        # Create new test order
        print("Создание нового тестового заказа REQ-TEST8888...")
        test_request = PartRequest(
            tenant_id="default",
            request_id="REQ-TEST8888",
            source="telegram",
            status="NEW",
            priority="urgent",
            customer_name="Данила Мастер",
            customer_phone_masked="+7-***-***-8888",
            customer_email_masked="da***@master.ru",
            vehicle_vin_masked="WBAKS410X0L******",
            vehicle_make="BMW",
            vehicle_model="X5",
            vehicle_year=2016,
            parts_json='[{"name": "Тормозные колодки передние BMW X5 (E70)", "quantity": 1}, {"name": "Масляный фильтр BMW N55/N57", "quantity": 2}]',
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )

        session.add(test_request)
        session.commit()
        print("Тестовый заказ REQ-TEST8888 успешно добавлен в базу данных!")

if __name__ == "__main__":
    main()
