"""Five-service catalog is stable and exposed over HTTP (FR-080)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.simulator.config import Settings
from apps.simulator.main import create_app
from apps.simulator.services import ServiceId, ServiceRuntime, ServiceStatus, catalog


def test_catalog_contains_exactly_the_five_section_13_ids() -> None:
    ids = [spec.id for spec in catalog()]

    assert ids == [
        ServiceId.USER,
        ServiceId.ORDER,
        ServiceId.PAYMENT,
        ServiceId.INVENTORY,
        ServiceId.NOTIFICATION,
    ]
    assert {item.value for item in ids} == {
        "user",
        "order",
        "payment",
        "inventory",
        "notification",
    }


def test_catalog_is_stable_across_calls() -> None:
    assert catalog() == catalog()


def test_order_depends_on_user_inventory_and_payment() -> None:
    order = next(spec for spec in catalog() if spec.id is ServiceId.ORDER)

    assert order.depends_on == frozenset({ServiceId.USER, ServiceId.INVENTORY, ServiceId.PAYMENT})
    assert order.display_name == "Order Service"


def test_leaf_services_have_no_dependencies() -> None:
    for service_id in (
        ServiceId.USER,
        ServiceId.PAYMENT,
        ServiceId.INVENTORY,
        ServiceId.NOTIFICATION,
    ):
        spec = next(item for item in catalog() if item.id is service_id)
        assert spec.depends_on == frozenset()


def test_runtime_defaults_to_healthy() -> None:
    runtime = ServiceRuntime()

    assert all(row.status is ServiceStatus.HEALTHY for row in runtime.list_snapshots())


def test_runtime_status_is_data_not_a_side_effect() -> None:
    runtime = ServiceRuntime()
    runtime.set_status(ServiceId.PAYMENT, ServiceStatus.DEGRADED)

    assert runtime.status_of(ServiceId.PAYMENT) is ServiceStatus.DEGRADED
    assert runtime.status_of(ServiceId.USER) is ServiceStatus.HEALTHY


def test_get_services_lists_catalog_with_status() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        response = client.get("/services")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [
        "user",
        "order",
        "payment",
        "inventory",
        "notification",
    ]
    assert all(item["status"] == "healthy" for item in body)
    order = next(item for item in body if item["id"] == "order")
    assert order["depends_on"] == ["inventory", "payment", "user"]
