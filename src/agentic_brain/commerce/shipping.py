# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""Shipping management with multi-carrier integrations.

Australia Post (AusPost) is the primary carrier, with scaffolding for USPS,
FedEx, and UPS as well as zone/method management for WooCommerce shipping.

AusPost API docs: https://developers.auspost.com.au/apis/pac/getting-started
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable, Protocol

from .models import WooAddress

logger = logging.getLogger(__name__)

_AUSPOST_BASE_URL = "https://digitalapi.auspost.com.au"
_AUSPOST_DOMESTIC_RATE_PATH = "/postage/parcel/domestic/service"
_AUSPOST_INTERNATIONAL_RATE_PATH = "/postage/parcel/international/service"
_AUSPOST_TRACK_PATH = "/track"
_AUSPOST_EPARCEL_LABEL_PATH = "/shipping/v1/labels"

# AusPost service codes
SERVICE_PARCEL_POST = "AUS_PARCEL_REGULAR"
SERVICE_EXPRESS_POST = "AUS_PARCEL_EXPRESS"
SERVICE_REGISTERED_POST = "AUS_LETTER_REGISTERED"


Money = Decimal


def _as_decimal(value: float | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class ShipmentStatus(StrEnum):
    """Status values used to track shipment progress."""

    CREATED = "created"
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


@dataclass(frozen=True)
class Dimensions:
    """Physical dimensions in centimetres / kilograms."""

    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float

    @property
    def weight_decimal(self) -> Decimal:
        return _as_decimal(self.weight_kg)

    @property
    def volume_cm3(self) -> float:
        return self.length_cm * self.width_cm * self.height_cm


@dataclass(frozen=True)
class ShippingZone:
    """Defines a WooCommerce shipping zone by country and optional postcode prefixes."""

    zone_id: str
    name: str
    countries: list[str] = field(default_factory=list)
    postal_prefixes: list[str] = field(default_factory=list)

    def matches(self, address: WooAddress) -> bool:
        """Return True when the address falls inside this zone."""
        if self.countries:
            if address.country.upper() not in {c.upper() for c in self.countries}:
                return False
        if self.postal_prefixes:
            return any(
                address.postcode.startswith(prefix)
                for prefix in self.postal_prefixes
                if prefix
            )
        return True


@dataclass(frozen=True)
class ShippingMethod:
    """A configured shipping method tied to a carrier service."""

    method_id: str
    name: str
    carrier: str
    service_code: str | None = None
    zone_id: str | None = None
    currency: str = "AUD"
    base_rate: Money | None = None
    per_kg_rate: Money | None = None
    estimated_days: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ShippingRate:
    """A single carrier-quoted rate."""

    carrier: str
    service_code: str
    service_name: str
    cost: Money
    currency: str = "AUD"
    estimated_days: int | None = None
    tracking_available: bool = True
    method_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrackingEvent:
    description: str
    date: str
    location: str
    status: str | None = None


@dataclass(frozen=True)
class TrackingInfo:
    consignment_id: str
    status: str
    events: list[TrackingEvent] = field(default_factory=list)
    carrier: str | None = None
    last_updated: str | None = None


@dataclass(frozen=True)
class ShipmentLabel:
    consignment_id: str
    label_url: str
    carrier: str
    service_code: str
    tracking_number: str
    label_format: str | None = None


@dataclass
class Shipment:
    """Represents a shipment and its lifecycle within the shipping manager."""

    shipment_id: str
    carrier: str
    service_code: str
    origin: WooAddress
    destination: WooAddress
    packages: list[Dimensions]
    tracking_number: str
    status: ShipmentStatus = ShipmentStatus.CREATED
    label_url: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_status(self, status: ShipmentStatus) -> None:
        self.status = status
        self.updated_at = datetime.now(UTC)


class CarrierClient(Protocol):
    """Minimal interface for AusPost HTTP clients."""

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]: ...

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class CarrierBase(ABC):
    """Abstract base class for carrier integrations."""

    name: str
    supports_domestic: bool = True
    supports_international: bool = True

    @abstractmethod
    def get_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        service_code: str | None = None,
    ) -> list[ShippingRate]:
        raise NotImplementedError

    @abstractmethod
    def create_label(self, shipment: Shipment) -> ShipmentLabel | None:
        raise NotImplementedError

    @abstractmethod
    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        raise NotImplementedError


class RequestsAusPostAPI:
    """Requests-backed AusPost API client."""

    def __init__(
        self,
        api_key: str,
        account_number: str | None = None,
        base_url: str = _AUSPOST_BASE_URL,
        timeout: int = 30,
        session: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.account_number = account_number
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session

    def _get_session(self) -> Any:
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retry = Retry(total=3, backoff_factor=0.5)
            session.mount("https://", HTTPAdapter(max_retries=retry))
            self._session = session
        return self._session

    def _headers(self) -> dict[str, str]:
        headers = {"AUTH-KEY": self.api_key}
        if self.account_number:
            headers["Account-Number"] = self.account_number
        return headers

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        session = self._get_session()
        url = f"{self.base_url}{path}"
        response = session.get(
            url, params=params, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._get_session()
        url = f"{self.base_url}{path}"
        response = session.post(
            url, json=payload, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


class AusPostCarrier(CarrierBase):
    """Australia Post carrier integration with domestic, international, and eParcel support."""

    name = "AusPost"

    def __init__(
        self,
        api_key: str | None = None,
        account_number: str | None = None,
        base_url: str = _AUSPOST_BASE_URL,
        timeout: int = 30,
        api: CarrierClient | None = None,
        default_origin_postcode: str = "5000",
    ) -> None:
        resolved_key = api_key or os.environ.get("AUSPOST_API_KEY", "")
        self.api_key = resolved_key
        self.account_number = account_number or os.environ.get("AUSPOST_ACCOUNT_NUMBER")
        self.default_origin_postcode = default_origin_postcode
        self._api = api or RequestsAusPostAPI(
            api_key=resolved_key,
            account_number=self.account_number,
            base_url=base_url,
            timeout=timeout,
        )

    @property
    def supports_eparcel(self) -> bool:
        return bool(self.account_number)

    def get_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        service_code: str | None = None,
    ) -> list[ShippingRate]:
        packages_list = list(packages)
        if not packages_list:
            return []
        if destination.country.upper() == "AU":
            return self._get_domestic_rates(
                origin, destination, packages_list, service_code
            )
        return self._get_international_rates(
            origin, destination, packages_list, service_code
        )

    def _rate_params(
        self, origin: WooAddress, destination: WooAddress, package: Dimensions
    ) -> dict[str, Any]:
        return {
            "from_postcode": origin.postcode,
            "to_postcode": destination.postcode,
            "length": package.length_cm,
            "width": package.width_cm,
            "height": package.height_cm,
            "weight": package.weight_kg,
        }

    def _get_domestic_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: list[Dimensions],
        service_code: str | None,
    ) -> list[ShippingRate]:
        try:
            payload = self._rate_params(origin, destination, packages[0])
            data = self._api.get(_AUSPOST_DOMESTIC_RATE_PATH, payload)
        except Exception as exc:
            logger.warning("AusPost domestic rates lookup failed: %s", exc)
            return []
        return self._parse_rates(data, service_code)

    def _get_international_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: list[Dimensions],
        service_code: str | None,
    ) -> list[ShippingRate]:
        try:
            payload = self._rate_params(origin, destination, packages[0])
            payload["country_code"] = destination.country.upper()
            data = self._api.get(_AUSPOST_INTERNATIONAL_RATE_PATH, payload)
        except Exception as exc:
            logger.warning("AusPost international rates lookup failed: %s", exc)
            return []
        return self._parse_rates(data, service_code)

    def _parse_rates(
        self, data: dict[str, Any], service_code: str | None
    ) -> list[ShippingRate]:
        services = data.get("postage_result", {}).get("services", {}).get("service", [])
        rates: list[ShippingRate] = []
        for service in services:
            code = service.get("code", "")
            if service_code and code != service_code:
                continue
            rates.append(
                ShippingRate(
                    carrier=self.name,
                    service_code=code,
                    service_name=service.get("name", ""),
                    cost=_as_decimal(service.get("price", "0")),
                    currency="AUD",
                    estimated_days=service.get("delivery_time"),
                )
            )
        logger.info("AusPost returned %d rate(s)", len(rates))
        return rates

    def create_label(self, shipment: Shipment) -> ShipmentLabel | None:
        if not self.supports_eparcel:
            logger.info(
                "AusPost label generation skipped (no eParcel account configured)"
            )
            return None
        payload = {
            "shipments": [
                {
                    "shipment_id": shipment.shipment_id,
                    "service_code": shipment.service_code,
                    "from": {"postcode": shipment.origin.postcode},
                    "to": {
                        "postcode": shipment.destination.postcode,
                        "country": shipment.destination.country,
                    },
                    "items": [
                        {
                            "length": pkg.length_cm,
                            "width": pkg.width_cm,
                            "height": pkg.height_cm,
                            "weight": pkg.weight_kg,
                        }
                        for pkg in shipment.packages
                    ],
                }
            ]
        }
        try:
            data = self._api.post(_AUSPOST_EPARCEL_LABEL_PATH, payload)
        except Exception as exc:
            logger.warning("AusPost label generation failed: %s", exc)
            return None
        labels = data.get("labels", [{}])
        label_url = labels[0].get("url", "") if labels else ""
        return ShipmentLabel(
            consignment_id=shipment.shipment_id,
            label_url=label_url,
            carrier=self.name,
            service_code=shipment.service_code,
            tracking_number=shipment.tracking_number,
            label_format=labels[0].get("format") if labels else None,
        )

    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        try:
            data = self._api.get(
                f"{_AUSPOST_TRACK_PATH}/summary", {"q": tracking_number}
            )
        except Exception as exc:
            logger.warning("AusPost tracking lookup failed: %s", exc)
            return TrackingInfo(
                consignment_id=tracking_number, status="unknown", carrier=self.name
            )

        shipments = data.get("TrackingSummaryResponse", {}).get("Shipment", [])
        if not shipments:
            return TrackingInfo(
                consignment_id=tracking_number, status="unknown", carrier=self.name
            )

        shipment = shipments[0] if isinstance(shipments, list) else shipments
        events = [
            TrackingEvent(
                description=e.get("Description", ""),
                date=e.get("Date", ""),
                location=e.get("Location", ""),
                status=e.get("EventType"),
            )
            for e in shipment.get("TrackingEvents", {}).get("TrackingEvent", [])
        ]
        return TrackingInfo(
            consignment_id=tracking_number,
            status=shipment.get("Status", "unknown"),
            events=events,
            carrier=self.name,
            last_updated=shipment.get("LastUpdated"),
        )

    # ------------------------------------------------------------------
    # Backwards-compatible helpers
    # ------------------------------------------------------------------

    def get_domestic_rates(
        self, from_postcode: str, to_postcode: str, dimensions: Dimensions
    ) -> list[ShippingRate]:
        origin = WooAddress(postcode=from_postcode, country="AU")
        destination = WooAddress(postcode=to_postcode, country="AU")
        return self.get_rates(origin, destination, [dimensions])

    def track(self, tracking_id: str) -> TrackingInfo:
        return self.track_shipment(tracking_id)


class AusPostClient(AusPostCarrier):
    """Backward-compatible alias for AusPostCarrier."""


class USPSCarrier(CarrierBase):
    name = "USPS"

    def get_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        service_code: str | None = None,
    ) -> list[ShippingRate]:
        raise NotImplementedError("USPS integration not implemented")

    def create_label(self, shipment: Shipment) -> ShipmentLabel | None:
        raise NotImplementedError("USPS label generation not implemented")

    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        raise NotImplementedError("USPS tracking not implemented")


class FedExCarrier(CarrierBase):
    name = "FedEx"

    def get_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        service_code: str | None = None,
    ) -> list[ShippingRate]:
        raise NotImplementedError("FedEx integration not implemented")

    def create_label(self, shipment: Shipment) -> ShipmentLabel | None:
        raise NotImplementedError("FedEx label generation not implemented")

    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        raise NotImplementedError("FedEx tracking not implemented")


class UPSCarrier(CarrierBase):
    name = "UPS"

    def get_rates(
        self,
        origin: WooAddress,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        service_code: str | None = None,
    ) -> list[ShippingRate]:
        raise NotImplementedError("UPS integration not implemented")

    def create_label(self, shipment: Shipment) -> ShipmentLabel | None:
        raise NotImplementedError("UPS label generation not implemented")

    def track_shipment(self, tracking_number: str) -> TrackingInfo:
        raise NotImplementedError("UPS tracking not implemented")


class ShipmentTracker:
    """Tracks shipment status updates and history."""

    def __init__(self) -> None:
        self._history: dict[str, list[TrackingEvent]] = {}

    def record_update(
        self,
        tracking_number: str,
        status: str,
        description: str = "",
        location: str = "",
        timestamp: datetime | None = None,
    ) -> TrackingEvent:
        timestamp = timestamp or datetime.now(UTC)
        event = TrackingEvent(
            description=description or status,
            date=timestamp.isoformat(),
            location=location,
            status=status,
        )
        self._history.setdefault(tracking_number, []).append(event)
        return event

    def history(self, tracking_number: str) -> list[TrackingEvent]:
        return list(self._history.get(tracking_number, []))

    def latest(self, tracking_number: str) -> TrackingEvent | None:
        updates = self._history.get(tracking_number, [])
        return updates[-1] if updates else None

    def sync_from_carrier(
        self, carrier: CarrierBase, tracking_number: str
    ) -> TrackingInfo:
        info = carrier.track_shipment(tracking_number)
        if info.status:
            self.record_update(
                tracking_number,
                info.status,
                description=f"{carrier.name} update: {info.status}",
            )
        for event in info.events:
            self._history.setdefault(tracking_number, []).append(event)
        return info


class ShippingManager:
    """Unified shipping manager supporting multiple carriers and zones."""

    def __init__(
        self,
        auspost_api_key: str | None = None,
        default_from_postcode: str = "5000",  # Adelaide CBD
        auspost_client: AusPostCarrier | None = None,
        carriers: dict[str, CarrierBase] | None = None,
        tracker: ShipmentTracker | None = None,
    ) -> None:
        self.default_from_postcode = default_from_postcode
        self._auspost = auspost_client or AusPostCarrier(
            api_key=auspost_api_key,
            default_origin_postcode=default_from_postcode,
        )
        self.carriers: dict[str, CarrierBase] = carriers.copy() if carriers else {}
        self.register_carrier(self._auspost)
        self.zones: dict[str, ShippingZone] = {}
        self.methods: dict[str, ShippingMethod] = {}
        self.shipments: dict[str, Shipment] = {}
        self.tracker = tracker or ShipmentTracker()

    # ------------------------------------------------------------------
    # Zone and method management
    # ------------------------------------------------------------------

    def register_carrier(self, carrier: CarrierBase) -> None:
        self.carriers[carrier.name] = carrier

    def add_zone(self, zone: ShippingZone) -> None:
        self.zones[zone.zone_id] = zone

    def add_method(self, method: ShippingMethod) -> None:
        self.methods[method.method_id] = method

    def match_zone(self, destination: WooAddress) -> ShippingZone | None:
        for zone in self.zones.values():
            if zone.matches(destination):
                return zone
        return None

    def _default_origin(self) -> WooAddress:
        return WooAddress(postcode=self.default_from_postcode, country="AU")

    # ------------------------------------------------------------------
    # Rate calculations
    # ------------------------------------------------------------------

    def calculate_rate_total(
        self, base_rate: Money, per_kg_rate: Money, total_weight: Money
    ) -> Money:
        return base_rate + (per_kg_rate * total_weight)

    def calculate_rates(
        self,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        origin: WooAddress | None = None,
        method_ids: Iterable[str] | None = None,
    ) -> list[ShippingRate]:
        origin = origin or self._default_origin()
        packages_list = list(packages)
        total_weight = sum((pkg.weight_decimal for pkg in packages_list), Decimal("0"))

        zone = self.match_zone(destination)
        selected_methods = [
            method
            for method in self.methods.values()
            if method.enabled
            and (
                zone is None or method.zone_id is None or method.zone_id == zone.zone_id
            )
            and (method_ids is None or method.method_id in set(method_ids))
        ]

        rates: list[ShippingRate] = []
        if not selected_methods:
            return self._auspost.get_rates(origin, destination, packages_list)

        for method in selected_methods:
            if method.base_rate is not None or method.per_kg_rate is not None:
                base_rate = method.base_rate or Decimal("0")
                per_kg_rate = method.per_kg_rate or Decimal("0")
                total = self.calculate_rate_total(base_rate, per_kg_rate, total_weight)
                rates.append(
                    ShippingRate(
                        carrier=method.carrier,
                        service_code=method.service_code or "",
                        service_name=method.name,
                        cost=total,
                        currency=method.currency,
                        estimated_days=method.estimated_days,
                        method_id=method.method_id,
                    )
                )
                continue

            carrier = self.carriers.get(method.carrier)
            if carrier is None:
                logger.warning("Carrier %s not registered", method.carrier)
                continue
            carrier_rates = carrier.get_rates(
                origin, destination, packages_list, method.service_code
            )
            for rate in carrier_rates:
                rates.append(
                    ShippingRate(
                        carrier=rate.carrier,
                        service_code=rate.service_code,
                        service_name=method.name or rate.service_name,
                        cost=rate.cost,
                        currency=rate.currency,
                        estimated_days=method.estimated_days or rate.estimated_days,
                        tracking_available=rate.tracking_available,
                        method_id=method.method_id,
                        metadata=rate.metadata,
                    )
                )
        return rates

    def get_rates(
        self, to_postcode: str, dimensions: Dimensions, from_postcode: str | None = None
    ) -> list[ShippingRate]:
        """Get all available rates to a destination postcode."""
        origin = WooAddress(
            postcode=from_postcode or self.default_from_postcode, country="AU"
        )
        destination = WooAddress(postcode=to_postcode, country="AU")
        return self.calculate_rates(destination, [dimensions], origin=origin)

    def get_cheapest_rate(
        self,
        to_postcode: str,
        dimensions: Dimensions,
        from_postcode: str | None = None,
    ) -> ShippingRate | None:
        rates = self.get_rates(to_postcode, dimensions, from_postcode)
        return min(rates, key=lambda r: r.cost) if rates else None

    def get_fastest_rate(
        self,
        to_postcode: str,
        dimensions: Dimensions,
        from_postcode: str | None = None,
    ) -> ShippingRate | None:
        rates = self.get_rates(to_postcode, dimensions, from_postcode)
        rates_with_days = [r for r in rates if r.estimated_days is not None]
        if not rates:
            return None
        return (
            min(rates_with_days, key=lambda r: r.estimated_days)
            if rates_with_days
            else rates[0]
        )

    # ------------------------------------------------------------------
    # Tracking and labels
    # ------------------------------------------------------------------

    def generate_tracking_number(self, carrier: str) -> str:
        token = uuid.uuid4().hex[:12].upper()
        return f"{carrier[:3].upper()}-{token}"

    def create_shipment(
        self,
        destination: WooAddress,
        packages: Iterable[Dimensions],
        carrier_name: str = "AusPost",
        service_code: str = SERVICE_PARCEL_POST,
        origin: WooAddress | None = None,
    ) -> Shipment:
        carrier = self.carriers.get(carrier_name)
        if carrier is None:
            raise ValueError(f"Carrier {carrier_name} not registered")
        origin = origin or self._default_origin()
        tracking_number = self.generate_tracking_number(carrier.name)
        shipment_id = uuid.uuid4().hex
        shipment = Shipment(
            shipment_id=shipment_id,
            carrier=carrier.name,
            service_code=service_code,
            origin=origin,
            destination=destination,
            packages=list(packages),
            tracking_number=tracking_number,
        )

        label = None
        try:
            label = carrier.create_label(shipment)
        except NotImplementedError:
            logger.debug("Label generation not implemented for %s", carrier.name)
        if label:
            shipment.label_url = label.label_url
            shipment.update_status(ShipmentStatus.LABEL_CREATED)

        self.shipments[shipment_id] = shipment
        self.tracker.record_update(
            tracking_number, shipment.status.value, location=origin.postcode
        )
        return shipment

    def update_shipment_status(self, shipment_id: str, status: ShipmentStatus) -> None:
        shipment = self.shipments.get(shipment_id)
        if not shipment:
            raise KeyError(f"Shipment {shipment_id} not found")
        shipment.update_status(status)
        self.tracker.record_update(shipment.tracking_number, status.value)

    def track(self, tracking_id: str) -> TrackingInfo:
        """Track a shipment by consignment / tracking ID."""
        shipment = next(
            (s for s in self.shipments.values() if s.tracking_number == tracking_id),
            None,
        )
        carrier = self.carriers.get(shipment.carrier) if shipment else self._auspost
        return carrier.track_shipment(tracking_id)

    # ------------------------------------------------------------------
    # WooCommerce order helpers
    # ------------------------------------------------------------------

    def rates_for_order(
        self, order: dict[str, Any], dimensions: Dimensions
    ) -> list[ShippingRate]:
        """Convenience method — derive destination from a WooOrder dict."""
        shipping = order.get("shipping", {})
        billing = order.get("billing", {})
        destination = WooAddress(
            postcode=shipping.get("postcode") or billing.get("postcode") or "",
            country=shipping.get("country") or billing.get("country") or "AU",
        )
        if not destination.postcode:
            logger.warning("Cannot determine postcode from order %s", order.get("id"))
            return []
        return self.calculate_rates(destination, [dimensions])


__all__ = [
    "AusPostCarrier",
    "AusPostClient",
    "CarrierBase",
    "Dimensions",
    "FedExCarrier",
    "ShippingManager",
    "ShippingMethod",
    "ShippingRate",
    "ShippingZone",
    "Shipment",
    "ShipmentLabel",
    "ShipmentStatus",
    "ShipmentTracker",
    "TrackingEvent",
    "TrackingInfo",
    "UPSCarrier",
    "USPSCarrier",
]
