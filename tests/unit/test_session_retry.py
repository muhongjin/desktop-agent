from desktop_agent.agent.session_retry import SessionRetry
from desktop_agent.providers.openai_compatible import ProviderError


def test_5xx_is_retryable_even_without_provider_hint():
    decision = SessionRetry().classify(ProviderError("bad gateway", status_code=502))
    assert decision.retryable is True
    assert decision.context_overflow is False


def test_401_is_not_retryable():
    decision = SessionRetry().classify(ProviderError("unauthorized", status_code=401))
    assert decision.retryable is False
    assert decision.context_overflow is False


def test_context_overflow_is_never_retryable():
    decision = SessionRetry().classify(
        ProviderError(
            "request failed",
            retryable=True,
            status_code=413,
            response_body='{"error":{"code":"context_length_exceeded"}}',
        )
    )
    assert decision.retryable is False
    assert decision.context_overflow is True


def test_exponential_delay_matches_opencode_without_headers():
    retry = SessionRetry()
    error = ProviderError("connection reset")
    assert [retry.delay(attempt, error) for attempt in range(1, 5)] == [2, 4, 8, 16]
    assert retry.delay(6, error) == 30


def test_retry_after_headers_take_priority():
    retry = SessionRetry()
    milliseconds = ProviderError(
        "rate limited", response_headers={"retry-after-ms": "2500"}
    )
    seconds = ProviderError("rate limited", response_headers={"Retry-After": "1.25"})
    assert retry.delay(1, milliseconds) == 2.5
    assert retry.delay(1, seconds) == 1.25
