from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from starlette.datastructures import FormData, Headers
from starlette.formparsers import MultiPartException, MultiPartParser


class UploadTooLarge(MultiPartException):
    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"{field_name} dépasse la taille autorisée")


class BoundedMultiPartParser(MultiPartParser):
    def __init__(
        self,
        headers: Headers,
        stream: AsyncGenerator[bytes, None],
        *,
        part_limits: dict[str, int],
        spool_bytes: int,
    ) -> None:
        super().__init__(
            headers,
            stream,
            max_files=2,
            max_fields=4,
            max_part_size=max(part_limits.values()),
        )
        self.part_limits = part_limits
        self.spool_max_size = spool_bytes
        self._part_size = 0

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._part_size = 0

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._current_part.field_name not in self.part_limits:
            raise MultiPartException(
                f"Champ multipart inattendu : {self._current_part.field_name}"
            )

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self._part_size += end - start
        limit = self.part_limits[self._current_part.field_name]
        if self._part_size > limit:
            raise UploadTooLarge(self._current_part.field_name)
        super().on_part_data(data, start, end)

    async def parse_exact(self) -> FormData:
        try:
            form = await self.parse()
        except asyncio.CancelledError:
            for upload in self._files_to_close_on_error:
                upload.close()
            raise
        names = [name for name, _value in form.multi_items()]
        if len(names) != len(self.part_limits) or set(names) != set(self.part_limits):
            await form.close()
            raise MultiPartException("Le contrat multipart est incomplet ou dupliqué")
        return form
