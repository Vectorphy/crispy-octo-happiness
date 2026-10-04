import logging
from unittest.mock import patch

import pytest

from bot import CPO
from utils import (
    DISCORD_SNOWFLAKE_MAX,
    validate_bot_developer_id,
)


class TestValidateBotDeveloperId:
    """Test suite for validate_bot_developer_id function."""

    def test_valid_integer_snowflake(self):
        valid_id = 534168986149978112
        assert validate_bot_developer_id(valid_id) == valid_id

    def test_valid_string_snowflake(self):
        assert validate_bot_developer_id("534168986149978112") == 534168986149978112

    def test_valid_string_with_whitespace_and_quotes(self):
        assert validate_bot_developer_id("  534168986149978112  ") == 534168986149978112
        assert validate_bot_developer_id('"534168986149978112"') == 534168986149978112
        assert validate_bot_developer_id("'534168986149978112'") == 534168986149978112

    def test_valid_boundary_snowflakes(self):
        # 17 digits minimum
        min_snowflake = 10000000000000000
        assert validate_bot_developer_id(min_snowflake) == min_snowflake

        # 20 digits within 64-bit max
        max_valid_20_digit = 18446744073709551615
        assert validate_bot_developer_id(max_valid_20_digit) == max_valid_20_digit

    @pytest.mark.parametrize(
        "placeholder",
        [
            "your_discord_user_id_here",
            "YOUR_DISCORD_USER_ID_HERE",
            "your_user_id_here",
            "your_id_here",
            "discord_user_id_here",
            "bot_developer_id_here",
            "your_bot_developer_id",
            "123456789012345678",  # default in .env.example
            "1234567890123456789",
            "000000000000000000",
            "111111111111111111",
            "placeholder",
            "changeme",
            "CHANGEME",
            "none",
            "null",
            "undefined",
            "todo",
        ],
    )
    def test_rejects_known_placeholders_non_strict(self, placeholder):
        assert validate_bot_developer_id(placeholder, strict=False) is None

    @pytest.mark.parametrize(
        "placeholder",
        [
            "your_discord_user_id_here",
            "123456789012345678",
            "placeholder",
            "changeme",
            "none",
        ],
    )
    def test_rejects_known_placeholders_strict(self, placeholder):
        with pytest.raises(ValueError, match="placeholder"):
            validate_bot_developer_id(placeholder, strict=True)

    @pytest.mark.parametrize(
        "repetitive",
        [
            "111111111111111111",
            "222222222222222222",
            "888888888888888888",
            "999999999999999999",
        ],
    )
    def test_rejects_repetitive_digit_placeholders(self, repetitive):
        assert validate_bot_developer_id(repetitive, strict=False) is None
        with pytest.raises(ValueError, match="repetitive placeholder"):
            validate_bot_developer_id(repetitive, strict=True)

    def test_rejects_none_input(self):
        assert validate_bot_developer_id(None, strict=False) is None
        with pytest.raises(ValueError, match="not configured"):
            validate_bot_developer_id(None, strict=True)

    def test_rejects_empty_and_whitespace_string(self):
        assert validate_bot_developer_id("", strict=False) is None
        assert validate_bot_developer_id("   ", strict=False) is None
        with pytest.raises(ValueError, match="empty"):
            validate_bot_developer_id("", strict=True)

    def test_rejects_boolean_values(self):
        # In Python, bool is a subclass of int (True == 1, False == 0)
        assert validate_bot_developer_id(True, strict=False) is None
        assert validate_bot_developer_id(False, strict=False) is None
        with pytest.raises(ValueError, match="boolean"):
            validate_bot_developer_id(True, strict=True)
        with pytest.raises(ValueError, match="boolean"):
            validate_bot_developer_id(False, strict=True)

    def test_rejects_floats(self):
        assert validate_bot_developer_id(534168986149978112.5, strict=False) is None
        assert validate_bot_developer_id(534168986149978112.0, strict=False) is None
        with pytest.raises(ValueError, match="float"):
            validate_bot_developer_id(534168986149978112.5, strict=True)
        with pytest.raises(ValueError, match="float"):
            validate_bot_developer_id(534168986149978112.0, strict=True)

    def test_rejects_negative_or_zero(self):
        assert validate_bot_developer_id(0, strict=False) is None
        assert validate_bot_developer_id(-1, strict=False) is None
        assert validate_bot_developer_id("-534168986149978112", strict=False) is None
        with pytest.raises(ValueError, match="positive integer"):
            validate_bot_developer_id(0, strict=True)
        with pytest.raises(ValueError, match="positive integer"):
            validate_bot_developer_id(-1, strict=True)
        with pytest.raises(ValueError, match="positive integer"):
            validate_bot_developer_id("-534168986149978112", strict=True)

    def test_rejects_non_digit_strings(self):
        assert validate_bot_developer_id("abc123456789012345", strict=False) is None
        assert validate_bot_developer_id("53416898614997811x", strict=False) is None
        with pytest.raises(ValueError, match="only digits"):
            validate_bot_developer_id("invalid_snowflake", strict=True)

    def test_rejects_unsupported_types(self):
        assert validate_bot_developer_id([534168986149978112], strict=False) is None
        assert validate_bot_developer_id({"id": 534168986149978112}, strict=False) is None
        with pytest.raises(ValueError, match="unsupported type"):
            validate_bot_developer_id([123], strict=True)

    def test_rejects_overflow_beyond_64bit(self):
        overflow = DISCORD_SNOWFLAKE_MAX + 1
        assert validate_bot_developer_id(overflow, strict=False) is None
        with pytest.raises(ValueError, match="exceeds maximum 64-bit"):
            validate_bot_developer_id(overflow, strict=True)

    def test_short_id_behavior_with_allow_mock(self):
        # Without allow_mock, short IDs (< 17 digits) are rejected
        assert validate_bot_developer_id(999, allow_mock=False) is None
        with pytest.raises(ValueError, match="Discord snowflake"):
            validate_bot_developer_id(999, strict=True, allow_mock=False)

        # With allow_mock, short positive IDs are accepted for test harnesses
        assert validate_bot_developer_id(999, allow_mock=True) == 999
        assert validate_bot_developer_id("12345", allow_mock=True) == 12345

        # Placeholders are still rejected even with allow_mock=True
        assert validate_bot_developer_id("placeholder", allow_mock=True) is None
        assert validate_bot_developer_id("123456789012345678", allow_mock=True) is None

    def test_logging_in_non_strict_mode(self, caplog):
        with caplog.at_level(logging.WARNING):
            validate_bot_developer_id("not_a_snowflake", strict=False)
        assert any("must contain only digits" in record.message for record in caplog.records)


class TestCpoBotDeveloperIdIntegration:
    """Test CPO bot initialization with various developer ID configurations."""

    @patch("bot.BOT_DEVELOPER_ID", None)
    def test_cpo_default_with_none_env(self):
        bot = CPO()
        assert bot.bot_developer_id is None

    @patch("bot.BOT_DEVELOPER_ID", 534168986149978112)
    def test_cpo_default_with_valid_env(self):
        bot = CPO()
        assert bot.bot_developer_id == 534168986149978112

    def test_cpo_with_mock_override(self):
        # CPO should allow mock integer IDs when explicitly passed in constructor
        bot = CPO(bot_developer_id=999)
        assert bot.bot_developer_id == 999

    def test_cpo_with_valid_snowflake_override(self):
        bot = CPO(bot_developer_id="534168986149978112")
        assert bot.bot_developer_id == 534168986149978112

    def test_cpo_with_placeholder_override_sets_none(self):
        bot = CPO(bot_developer_id="your_discord_user_id_here")
        assert bot.bot_developer_id is None
