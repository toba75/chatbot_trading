"""Capacité partagée explicite autour d'un convertisseur de page."""

from __future__ import annotations

from threading import BoundedSemaphore
from typing import Generic, Protocol, TypeVar


RequestT = TypeVar("RequestT", contravariant=True)
ResponseT = TypeVar("ResponseT", covariant=True)


class PageConverter(Protocol[RequestT, ResponseT]):
    def convert_page(self, request: RequestT) -> ResponseT:
        """Convertit une page selon le contrat du convertisseur enveloppé."""


class ConcurrencyLimitedPageConverter(Generic[RequestT, ResponseT]):
    """Partage une capacité bornée entre tous les appels au convertisseur."""

    def __init__(
        self,
        *,
        page_converter: PageConverter[RequestT, ResponseT],
        max_concurrency: int,
    ) -> None:
        if not callable(getattr(page_converter, "convert_page", None)):
            raise ValueError("convertisseur de page invalide")
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError("capacité de conversion invalide")
        self._page_converter = page_converter
        self._capacity = BoundedSemaphore(max_concurrency)

    def convert_page(self, request: RequestT) -> ResponseT:
        with self._capacity:
            return self._page_converter.convert_page(request)


class SharedPageConversionCapacity:
    """Capacité unique partagée par plusieurs familles de convertisseurs."""

    def __init__(self, *, max_concurrency: int) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError("capacité de conversion partagée invalide")
        self._capacity = BoundedSemaphore(max_concurrency)

    def limit(
        self,
        *,
        page_converter: PageConverter[RequestT, ResponseT],
    ) -> "SharedCapacityPageConverter[RequestT, ResponseT]":
        if not callable(getattr(page_converter, "convert_page", None)):
            raise ValueError("convertisseur de page partagé invalide")
        return SharedCapacityPageConverter(
            page_converter=page_converter,
            capacity=self._capacity,
        )


class SharedCapacityPageConverter(Generic[RequestT, ResponseT]):
    def __init__(
        self,
        *,
        page_converter: PageConverter[RequestT, ResponseT],
        capacity: BoundedSemaphore,
    ) -> None:
        self._page_converter = page_converter
        self._capacity = capacity

    def convert_page(self, request: RequestT) -> ResponseT:
        with self._capacity:
            return self._page_converter.convert_page(request)


__all__ = [
    "ConcurrencyLimitedPageConverter",
    "SharedPageConversionCapacity",
]
