"""Error detection and retry logic utilities."""


##########################
# Token Limit Detection
##########################

def is_token_limit_exceeded(exception: Exception, model_name: str = None) -> bool:
    """Determine if an exception indicates a token/context limit was exceeded.

    Args:
        exception: The exception to analyze
        model_name: Optional model name to optimize provider detection

    Returns:
        True if the exception indicates a token limit was exceeded, False otherwise
    """
    error_str = str(exception).lower()

    # Step 1: Determine provider from model name if available
    provider = None
    if model_name:
        model_str = str(model_name).lower()
        if model_str.startswith('openai:'):
            provider = 'openai'
        elif model_str.startswith('anthropic:'):
            provider = 'anthropic'
        elif model_str.startswith('gemini:') or model_str.startswith('google:'):
            provider = 'gemini'

    # Step 2: Check provider-specific token limit patterns
    if provider == 'openai':
        return _check_openai_token_limit(exception, error_str)
    elif provider == 'anthropic':
        return _check_anthropic_token_limit(exception, error_str)
    elif provider == 'gemini':
        return _check_gemini_token_limit(exception, error_str)

    # Step 3: If provider unknown, check all providers
    return (
        _check_openai_token_limit(exception, error_str) or
        _check_anthropic_token_limit(exception, error_str) or
        _check_gemini_token_limit(exception, error_str)
    )


def _check_openai_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates OpenAI token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')

    # Check if this is an OpenAI exception
    is_openai_exception = (
        'openai' in exception_type.lower() or
        'openai' in module_name.lower()
    )

    # Check for typical OpenAI token limit error types
    is_request_error = class_name in ['BadRequestError', 'InvalidRequestError']

    if is_openai_exception and is_request_error:
        # Look for token-related keywords in error message
        token_keywords = ['token', 'context', 'length', 'maximum context', 'reduce']
        if any(keyword in error_str for keyword in token_keywords):
            return True

    # Check for specific OpenAI error codes
    if hasattr(exception, 'code') and hasattr(exception, 'type'):
        error_code = getattr(exception, 'code', '')
        error_type = getattr(exception, 'type', '')

        if (error_code == 'context_length_exceeded' or
            error_type == 'invalid_request_error'):
            return True

    return False


def _check_anthropic_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Anthropic token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')

    # Check if this is an Anthropic exception
    is_anthropic_exception = (
        'anthropic' in exception_type.lower() or
        'anthropic' in module_name.lower()
    )

    # Check for Anthropic-specific error patterns
    is_bad_request = class_name == 'BadRequestError'

    if is_anthropic_exception and is_bad_request:
        # Anthropic uses specific error messages for token limits
        if 'prompt is too long' in error_str:
            return True

    return False


def _check_gemini_token_limit(exception: Exception, error_str: str) -> bool:
    """Check if exception indicates Google/Gemini token limit exceeded."""
    # Analyze exception metadata
    exception_type = str(type(exception))
    class_name = exception.__class__.__name__
    module_name = getattr(exception.__class__, '__module__', '')

    # Check if this is a Google/Gemini exception
    is_google_exception = (
        'google' in exception_type.lower() or
        'google' in module_name.lower()
    )

    # Check for Google-specific resource exhaustion errors
    is_resource_exhausted = class_name in [
        'ResourceExhausted',
        'GoogleGenerativeAIFetchError'
    ]

    if is_google_exception and is_resource_exhausted:
        return True

    # Check for specific Google API resource exhaustion patterns
    if 'google.api_core.exceptions.resourceexhausted' in exception_type.lower():
        return True

    return False


##########################
# Retry Logic
##########################

def is_retryable_api_error(exception: Exception) -> bool:
    """Determine if an exception is retryable (rate limit, server error, timeout).

    Args:
        exception: The exception to analyze

    Returns:
        True if the exception is retryable, False otherwise
    """
    error_str = str(exception).lower()
    class_name = exception.__class__.__name__
    exception_type = str(type(exception)).lower()

    # Check for rate limit errors (429)
    rate_limit_indicators = [
        'rate limit',
        'ratelimit',
        'too many requests',
        '429',
        'quota exceeded',
        'resource_exhausted'
    ]
    if any(indicator in error_str for indicator in rate_limit_indicators):
        return True

    # Check for server errors (500, 503)
    server_error_indicators = [
        '500',
        '503',
        'internal server error',
        'service unavailable',
        'server error',
        'backend error'
    ]
    if any(indicator in error_str for indicator in server_error_indicators):
        return True

    # Check for timeout errors
    timeout_indicators = [
        'timeout',
        'timed out',
        'deadline exceeded'
    ]
    if any(indicator in error_str for indicator in timeout_indicators):
        return True

    # Check for specific exception types
    if class_name in ['RateLimitError', 'TimeoutError', 'ServiceUnavailableError']:
        return True

    return False


def calculate_backoff_delay(attempt: int, config) -> float:
    """Calculate exponential backoff delay for retry attempts.

    Args:
        attempt: The current attempt number (0-indexed)
        config: Configuration object with retry settings

    Returns:
        Delay in seconds, capped at max_delay
    """
    delay = config.api_retry_initial_delay * (config.api_retry_exponential_base ** attempt)
    return min(delay, config.api_retry_max_delay)
