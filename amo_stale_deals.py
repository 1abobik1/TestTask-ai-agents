"""Открытые сделки amoCRM, у которых нет незакрытых задач или ближайшая задача просрочена."""
import os
import time

import requests

API = f"https://{os.environ['AMO_SUBDOMAIN']}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {os.environ['AMO_TOKEN']}"}
CLOSED_STATUSES = {142, 143}  # системные: "Успешно реализовано" и "Закрыто и не реализовано"


def fetch_all(entity, params=None):
    page = 1
    while True:
        r = requests.get(f"{API}/{entity}", headers=HEADERS, timeout=30,
                         params={**(params or {}), "page": page, "limit": 250})
        if r.status_code == 204:  # amoCRM так отвечает, когда данных нет
            return
        r.raise_for_status()
        data = r.json()
        yield from data["_embedded"][entity]
        if "next" not in data.get("_links", {}):
            return
        page += 1
        time.sleep(0.2)  # лимит API - 7 запросов в секунду


def stale_deals():
    # по каждой сделке запоминаем самый ранний срок среди незакрытых задач
    nearest_due = {}
    for task in fetch_all("tasks", {"filter[entity_type]": "leads", "filter[is_completed]": 0}):
        lead_id, due = task["entity_id"], task["complete_till"]
        nearest_due[lead_id] = min(due, nearest_due.get(lead_id, due))

    now = time.time()
    for lead in fetch_all("leads"):
        if lead["status_id"] in CLOSED_STATUSES:
            continue
        due = nearest_due.get(lead["id"])
        if due is None:
            yield lead, "нет задач"
        elif due < now:
            yield lead, "задача просрочена"


if __name__ == "__main__":
    for lead, reason in stale_deals():
        print(lead["id"], lead["name"], lead["responsible_user_id"], reason, sep="\t")
