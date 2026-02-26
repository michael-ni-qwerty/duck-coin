"""
NOWPayments API client.

Handles creating invoices and verifying IPN callbacks.
API docs: https://documenter.getpostman.com/view/7907941/2s93JusNJt
"""

import hashlib
import hmac
import json
import logging
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NOWPaymentsClient:
    """Client for the NOWPayments REST API."""

    def __init__(self):
        self._base_url = settings.nowpayments_api_url
        self._api_key = settings.nowpayments_api_key

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def get_status(self) -> Dict[str, Any]:
        """GET /status — check API availability."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base_url}/status", headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def get_available_currencies(self) -> list[Dict[str, Any]]:
        """GET /full-currencies — list available payment currencies with full details."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/full-currencies", headers=self._headers
            )
            resp.raise_for_status()
            return resp.json().get("currencies", [])

    async def get_estimated_price(
        self,
        amount: float,
        currency_from: str = "usd",
        currency_to: str = "btc",
    ) -> Dict[str, Any]:
        """GET /estimate — get estimated price in crypto for a fiat amount."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/estimate",
                headers=self._headers,
                params={
                    "amount": amount,
                    "currency_from": currency_from,
                    "currency_to": currency_to,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_min_amount(
        self, currency_from: str = "usd"
    ) -> Dict[str, Any]:
        """GET /min-amount — get minimum payment amount."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/min-amount",
                headers=self._headers,
                params={
                    "currency_from": currency_from,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def create_invoice(
        self,
        price_amount: float,
        price_currency: str = "usd",
        order_id: Optional[str] = None,
        order_description: Optional[str] = None,
        ipn_callback_url: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /invoice — create a payment invoice.

        Returns an invoice with a hosted payment page URL.
        The user is redirected there to pick a crypto and pay.
        """
        payload: Dict[str, Any] = {
            "price_amount": price_amount,
            "price_currency": price_currency,
        }
        if order_id:
            payload["order_id"] = order_id
        if order_description:
            payload["order_description"] = order_description
        if ipn_callback_url:
            payload["ipn_callback_url"] = ipn_callback_url
        if success_url:
            payload["success_url"] = success_url
        if cancel_url:
            payload["cancel_url"] = cancel_url

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/invoice",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_payment(
        self,
        price_amount: float,
        price_currency: str = "usd",
        pay_currency: str = "btc",
        order_id: Optional[str] = None,
        order_description: Optional[str] = None,
        ipn_callback_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /payment — create a direct payment (specific crypto chosen upfront).
        """
        payload: Dict[str, Any] = {
            "price_amount": price_amount,
            "price_currency": price_currency,
            "pay_currency": pay_currency,
        }
        if order_id:
            payload["order_id"] = order_id
        if order_description:
            payload["order_description"] = order_description
        if ipn_callback_url:
            payload["ipn_callback_url"] = ipn_callback_url

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/payment",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_payment_status(self, payment_id: int) -> Dict[str, Any]:
        """GET /payment/{payment_id} — get payment status."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/payment/{payment_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def verify_ipn_signature(payload_body: bytes, received_signature: str) -> bool:
        """
        Verify the IPN callback signature from NOWPayments.

        NOWPayments signs IPN callbacks with HMAC-SHA512 using the IPN secret key.
        The payload is sorted by keys before hashing.
        """
        if not settings.nowpayments_ipn_secret:
            logger.error("IPN secret not configured")
            return False

        try:
            payload = json.loads(payload_body)
        except (json.JSONDecodeError, ValueError):
            logger.error("Failed to parse IPN payload")
            return False

        # Sort payload by keys and serialize (NOWPayments requirement)
        sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        expected_sig = hmac.new(
            settings.nowpayments_ipn_secret.encode("utf-8"),
            sorted_payload.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, received_signature)


# Singleton instance
nowpayments_client = NOWPaymentsClient()
