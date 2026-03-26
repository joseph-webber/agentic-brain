# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for commerce shipping integrations."""

from __future__ import annotations

from decimal import Decimal

from agentic_brain.commerce import (
    AusPostCarrier,
    CarrierBase,
    Dimensions,
    Shipment,
    ShipmentStatus,
    ShipmentTracker,
    ShippingManager,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    TrackingInfo,
)
from agentic_brain.commerce.models import WooAddress


class FakeAusPostAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def get(self, path: str, params: dict) -> dict:
        self.calls.append((path, params))
        if "international" in path:
            return {
                "postage_result": {
                    "services": {
                        "service": [
                            {"code": "INTL", "name": "International", "price": "25.00"}
                        ]
                    }
                }
            }
        return {
            "postage_result": {
                "services": {
                    "service": [{"code": "DOM", "name": "Domestic", "price": "10.00"}]
                }
            }
        }

    def post(self, path: str, payload: dict) -> dict:
        self.calls.append((path, payload))
        return {
            "labels": [{"url": "https://label.example.com/label.pdf", "format": "pdf"}]
        }


class StubCarrier(CarrierBase):
    name = "Stub"

    def get_rates(self, origin, destination, packages, service_code=None):
        return [
            ShippingRate(
                carrier=self.name,
                service_code="STUB",
                service_name="Stub Service",
                cost=Decimal("12.50"),
            )
        ]

    def create_label(self, shipment: Shipment):
        return None

    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        return TrackingInfo(
            consignment_id=tracking_number, status="in_transit", carrier=self.name
        )


def test_shipping_zone_matches_country_and_postcode():
    zone = ShippingZone(
        zone_id="au-metro", name="AU Metro", countries=["AU"], postal_prefixes=["5"]
    )
    destination = WooAddress(postcode="5000", country="AU")
    assert zone.matches(destination) is True

    far_destination = WooAddress(postcode="2000", country="AU")
    assert zone.matches(far_destination) is False

    overseas = WooAddress(postcode="90210", country="US")
    assert zone.matches(overseas) is False


def test_shipping_manager_calculates_weighted_rates():
    manager = ShippingManager(auspost_api_key="", default_from_postcode="5000")
    manager.register_carrier(StubCarrier())
    manager.add_zone(ShippingZone(zone_id="au", name="Australia", countries=["AU"]))
    manager.add_method(
        ShippingMethod(
            method_id="local-standard",
            name="Local Standard",
            carrier="Stub",
            base_rate=Decimal("5.00"),
            per_kg_rate=Decimal("2.00"),
        )
    )

    destination = WooAddress(postcode="5000", country="AU")
    rates = manager.calculate_rates(destination, [Dimensions(10, 10, 10, 1.5)])

    assert rates[0].cost == Decimal("8.00")
    assert rates[0].service_name == "Local Standard"


def test_auspost_carrier_domestic_and_international_rates():
    api = FakeAusPostAPI()
    carrier = AusPostCarrier(api_key="test", api=api)
    origin = WooAddress(postcode="5000", country="AU")

    domestic = carrier.get_rates(
        origin, WooAddress(postcode="3000", country="AU"), [Dimensions(10, 10, 10, 1)]
    )
    international = carrier.get_rates(
        origin, WooAddress(postcode="90210", country="US"), [Dimensions(10, 10, 10, 1)]
    )

    assert domestic[0].service_code == "DOM"
    assert international[0].service_code == "INTL"
    assert "domestic" in api.calls[0][0]
    assert "international" in api.calls[1][0]


def test_shipment_tracker_records_updates():
    tracker = ShipmentTracker()
    tracker.record_update(
        "TRK123", "in_transit", description="Left facility", location="Adelaide"
    )
    latest = tracker.latest("TRK123")

    assert latest is not None
    assert latest.description == "Left facility"
    assert latest.location == "Adelaide"


def test_shipment_creation_updates_status():
    manager = ShippingManager(auspost_api_key="", default_from_postcode="5000")
    destination = WooAddress(postcode="5000", country="AU")
    shipment = manager.create_shipment(destination, [Dimensions(5, 5, 5, 0.5)])

    assert shipment.status in {ShipmentStatus.CREATED, ShipmentStatus.LABEL_CREATED}
    assert shipment.tracking_number
    assert shipment.shipment_id in manager.shipments
