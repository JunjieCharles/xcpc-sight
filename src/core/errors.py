class XcpcSightError(Exception):
    """Base exception for xcpc-sight."""


class DataValidationError(XcpcSightError):
    """Upstream or caller-provided data violates the expected contract."""


class IdentityConflictError(DataValidationError):
    """Two participant records resolve to an ambiguous identity."""


class RankLandError(XcpcSightError):
    """A RankLand request failed or returned an unsuccessful response."""


class NowcoderError(XcpcSightError):
    """A Nowcoder request failed or returned an unsuccessful response."""
