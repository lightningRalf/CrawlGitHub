import pytest
import stamina


class TransientError(RuntimeError):
    """Raised to test stamina retry behavior."""


def test_stamina_retries_until_exhausted() -> None:
    attempts = {"count": 0}

    @stamina.retry(
        on=TransientError,
        attempts=3,
        wait_initial=0.0,
        wait_max=0.0,
        wait_jitter=0.0,
    )
    def always_fails() -> None:
        attempts["count"] += 1
        raise TransientError("boom")

    with pytest.raises(TransientError, match="boom"):
        always_fails()

    assert attempts["count"] == 3


def test_stamina_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    @stamina.retry(
        on=TransientError,
        attempts=4,
        wait_initial=0.0,
        wait_max=0.0,
        wait_jitter=0.0,
    )
    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TransientError("retry")
        return "ok"

    result = flaky()

    assert result == "ok"
    assert attempts["count"] == 3
