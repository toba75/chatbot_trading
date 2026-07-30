class AnalysisLimitation(RuntimeError):
    def __init__(self, status: str, code: str, message: str) -> None:
        self.status = status
        self.code = code
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def require_supported(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AnalysisLimitation("unsupported", code, message)


def require_unambiguous(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise AnalysisLimitation("ambiguous", code, message)
