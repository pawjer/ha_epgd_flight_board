"""Tests for config flow validation."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from custom_components.gdansk_airport.config_flow import validate_connection


async def test_validate_connection_success():
    """Test successful connection validation."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        return_value=[],
    ):
        mock_get_session.return_value = Mock()
        result = await validate_connection(mock_hass)

    assert result is True


async def test_validate_connection_timeout():
    """Test connection validation with timeout."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        side_effect=asyncio.TimeoutError(),
    ):
        mock_get_session.return_value = Mock()

        with pytest.raises(asyncio.TimeoutError):
            await validate_connection(mock_hass)


async def test_validate_connection_client_error():
    """Test connection validation with client error."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        side_effect=aiohttp.ClientError("Connection failed"),
    ):
        mock_get_session.return_value = Mock()

        with pytest.raises(aiohttp.ClientError):
            await validate_connection(mock_hass)


async def test_validate_connection_unexpected_error():
    """Test connection validation with unexpected error."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        side_effect=ValueError("Unexpected error"),
    ):
        mock_get_session.return_value = Mock()

        with pytest.raises(ValueError):
            await validate_connection(mock_hass)


async def test_validate_connection_logs_url():
    """Test that connection validation logs the URL being tested."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "custom_components.gdansk_airport.config_flow._LOGGER"
    ) as mock_logger:
        mock_get_session.return_value = Mock()
        await validate_connection(mock_hass)

        # Verify debug logging was called
        assert mock_logger.debug.call_count >= 1
        # Check that URL was logged
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("airport.gdansk.pl" in str(call) for call in debug_calls)


async def test_validate_connection_logs_error_details():
    """Test that connection errors are logged with details."""
    mock_hass = Mock()

    with patch(
        "custom_components.gdansk_airport.config_flow.async_get_clientsession"
    ) as mock_get_session, patch(
        "custom_components.gdansk_airport.config_flow.fetch_flights",
        new_callable=AsyncMock,
        side_effect=aiohttp.ClientConnectorError(Mock(), Mock()),
    ), patch(
        "custom_components.gdansk_airport.config_flow._LOGGER"
    ) as mock_logger:
        mock_get_session.return_value = Mock()

        with pytest.raises(aiohttp.ClientError):
            await validate_connection(mock_hass)

        # Verify error logging was called
        assert mock_logger.error.call_count >= 1
        # Check that error type was logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("ClientConnectorError" in str(call) for call in error_calls)
