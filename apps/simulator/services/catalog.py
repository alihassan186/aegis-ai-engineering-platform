"""In-process service catalog (FR-080, platform overview §13)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ServiceId(StrEnum):
    USER = "user"
    ORDER = "order"
    PAYMENT = "payment"
    INVENTORY = "inventory"
    NOTIFICATION = "notification"


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    id: ServiceId
    display_name: str
    depends_on: frozenset[ServiceId]


# Checkout-style graph only: order needs user + inventory + payment.
# Other edges are omitted on purpose (not a service mesh).
SERVICES: Mapping[ServiceId, ServiceSpec] = {
    ServiceId.USER: ServiceSpec(
        id=ServiceId.USER,
        display_name="User Service",
        depends_on=frozenset(),
    ),
    ServiceId.INVENTORY: ServiceSpec(
        id=ServiceId.INVENTORY,
        display_name="Inventory Service",
        depends_on=frozenset(),
    ),
    ServiceId.PAYMENT: ServiceSpec(
        id=ServiceId.PAYMENT,
        display_name="Payment Service",
        depends_on=frozenset(),
    ),
    ServiceId.ORDER: ServiceSpec(
        id=ServiceId.ORDER,
        display_name="Order Service",
        depends_on=frozenset({ServiceId.USER, ServiceId.INVENTORY, ServiceId.PAYMENT}),
    ),
    ServiceId.NOTIFICATION: ServiceSpec(
        id=ServiceId.NOTIFICATION,
        display_name="Notification Service",
        depends_on=frozenset(),
    ),
}


def catalog() -> tuple[ServiceSpec, ...]:
    """Stable order: user, order, payment, inventory, notification."""
    return (
        SERVICES[ServiceId.USER],
        SERVICES[ServiceId.ORDER],
        SERVICES[ServiceId.PAYMENT],
        SERVICES[ServiceId.INVENTORY],
        SERVICES[ServiceId.NOTIFICATION],
    )
