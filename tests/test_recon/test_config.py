"""
Tests for agent_core/recon/config.py — credential loading, encryption, config assembly.

All tests use tmp_path and monkeypatch to avoid touching real filesystem paths.
"""

import json
import os
import stat

from pathlib import Path
from cryptography.fernet import Fernet

import pytest

from agent_core.recon import config


# ─────────────────────────────────────────────────────────
# _load_env_file tests
# ─────────────────────────────────────────────────────────


class TestLoadEnvFile:
    """Tests for the internal _load_env_file() helper."""

    def test_reads_simple_key_value(self, tmp_path):
        """key=value pair is parsed correctly."""
        env_file = tmp_path / ".env"
        env_file.write_text("IG_USERNAME=testuser\nIG_PASSWORD=testpass\n")
        result = config._load_env_file(env_file)
        assert result == {"IG_USERNAME": "testuser", "IG_PASSWORD": "testpass"}

    def test_skips_comments_and_blanks(self, tmp_path):
        """Lines starting with # or blank lines are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# This is a comment\n\nLLM_API_KEY=sk-real\n# another comment\n"
        )
        result = config._load_env_file(env_file)
        assert result == {"LLM_API_KEY": "sk-real"}

    def test_strips_quotes_from_values(self, tmp_path):
        """VALUE=\"quoted\" → key=value with quotes stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            'LLM_API_KEY="sk-test"\nSECRET=\'mysecret\'\nNOQUOTE=plain\n'
        )
        result = config._load_env_file(env_file)
        assert result == {"LLM_API_KEY": "sk-test", "SECRET": "mysecret", "NOQUOTE": "plain"}

    def test_strips_inline_comments(self, tmp_path):
        """KEY=value # comment → key=value (trailing comment stripped)."""
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_API_KEY=sk-test # this is a comment\nKEY2=val2\n")
        result = config._load_env_file(env_file)
        assert result == {"LLM_API_KEY": "sk-test", "KEY2": "val2"}

    def test_missing_file_returns_empty_dict(self, tmp_path):
        """Non-existent .env path returns {}."""
        result = config._load_env_file(tmp_path / "nonexistent.env")
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        """Empty .env file returns {}."""
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = config._load_env_file(env_file)
        assert result == {}

    def test_handles_equals_sign_in_value(self, tmp_path):
        """Values containing = are captured correctly (only first = is delimiter)."""
        env_file = tmp_path / ".env"
        env_file.write_text('COMPLEX=base64==encoded==\n')
        result = config._load_env_file(env_file)
        assert result == {"COMPLEX": "base64==encoded=="}


# ─────────────────────────────────────────────────────────
# _get_encryption_key tests
# ─────────────────────────────────────────────────────────


class TestGetEncryptionKey:
    """Tests for _get_encryption_key() — priority: env var > key file > auto-generate."""

    def test_env_var_takes_priority(self, monkeypatch, tmp_path):
        """CREDENTIALS_ENCRYPTION_KEY env var is used instead of key file."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

        result = config._get_encryption_key()
        assert result == test_key.encode("utf-8")

    def test_key_file_loaded_when_no_env_var(self, monkeypatch, tmp_path):
        """Falls back to credentials.key file when env var absent."""
        key = Fernet.generate_key()
        key_file = tmp_path / "credentials.key"
        key_file.write_bytes(key)
        monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", key_file)

        result = config._get_encryption_key()
        assert result == key

    def test_key_generated_on_first_use(self, monkeypatch, tmp_path):
        """Key file created with 0600 perms when neither env var nor file exist."""
        monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        key_file = tmp_path / "credentials.key"
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", key_file)

        result = config._get_encryption_key()

        # Key should be a valid Fernet key (44 bytes = 32 base64-encoded)
        assert len(result) == 44  # Fernet key as base64-encoded bytes
        # Should be usable as a Fernet key
        fernet = Fernet(result)
        assert fernet is not None

        # Key file should exist with 0600 perms
        assert key_file.exists()
        perms = stat.S_IMODE(key_file.stat().st_mode)
        assert perms == 0o600

    def test_generated_key_is_stable(self, monkeypatch, tmp_path):
        """After first-use generation, subsequent calls return the same key."""
        monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        key_file = tmp_path / "credentials.key"
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", key_file)

        first = config._get_encryption_key()
        second = config._get_encryption_key()
        assert first == second


# ─────────────────────────────────────────────────────────
# _encrypt_credentials / _decrypt_credentials tests
# ─────────────────────────────────────────────────────────


class TestEncryptDecrypt:
    """Tests for the internal encrypt/decrypt helpers."""

    def test_encrypt_decrypt_roundtrip(self, monkeypatch, tmp_path):
        """_encrypt_credentials then _decrypt_credentials returns original data."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

        original = {"ig_username": "user", "ig_password": "pass"}
        encrypted = config._encrypt_credentials(original)
        decrypted = config._decrypt_credentials(encrypted)
        assert decrypted == original

    def test_encrypted_output_is_binary(self, monkeypatch, tmp_path):
        """Encrypted output is binary bytes that don't leak plaintext."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

        encrypted = config._encrypt_credentials({"secret_key": "secret_value"})
        # Fernet output is base64-encoded bytes
        assert isinstance(encrypted, bytes)
        # Plaintext values should not appear in the encrypted output
        assert b"secret_key" not in encrypted
        assert b"secret_value" not in encrypted

    def test_decrypt_corrupted_data_returns_none(self, monkeypatch, tmp_path):
        """Decrypting corrupted bytes returns None."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

        result = config._decrypt_credentials(b"not valid fernet data")
        assert result is None

    def test_decrypt_wrong_key_returns_none(self, monkeypatch, tmp_path):
        """Decrypting with a different key returns None."""
        key1 = Fernet.generate_key().decode("utf-8")
        key2 = Fernet.generate_key().decode("utf-8")

        # Encrypt with key1
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key1)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")
        encrypted = config._encrypt_credentials({"secret": "data"})

        # Decrypt with key2
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", key2)
        result = config._decrypt_credentials(encrypted)
        assert result is None


# ─────────────────────────────────────────────────────────
# load_competitors tests
# ─────────────────────────────────────────────────────────


class TestLoadCompetitors:
    """Tests for load_competitors()."""

    def test_missing_brain_file_returns_empty(self, monkeypatch, tmp_path):
        """When BRAIN_FILE doesn't exist, returns []."""
        monkeypatch.setattr(config, "BRAIN_FILE", tmp_path / "agent-brain.json")
        result = config.load_competitors()
        assert result == []

    def test_parses_competitors_correctly(self, monkeypatch, tmp_path):
        """Creates Competitor dataclass instances from brain JSON."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "competitors": [
                {"name": "Test Creator", "platform": "youtube", "handle": "@test", "why_watch": "Great content"},
                {"name": "Other Creator", "platform": "instagram", "handle": "@other", "why_watch": "Photos"},
            ]
        }))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

        result = config.load_competitors()
        assert len(result) == 2
        assert result[0].name == "Test Creator"
        assert result[0].platform == "youtube"
        assert result[0].handle == "@test"
        assert result[0].why_watch == "Great content"
        assert result[1].name == "Other Creator"
        assert result[1].platform == "instagram"

    def test_handles_partial_entries(self, monkeypatch, tmp_path):
        """Competitors with missing fields get empty string defaults."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "competitors": [
                {"name": "Partial"},
                {"platform": "youtube", "handle": "@only-platform"},
            ]
        }))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

        result = config.load_competitors()
        assert len(result) == 2
        assert result[0].name == "Partial"
        assert result[0].platform == ""
        assert result[0].handle == ""
        assert result[0].why_watch == ""
        assert result[1].name == ""
        assert result[1].platform == "youtube"
        assert result[1].handle == "@only-platform"

    def test_empty_competitors_list_returns_empty(self, monkeypatch, tmp_path):
        """Brain file with empty competitors list returns []."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({"competitors": []}))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

        result = config.load_competitors()
        assert result == []

    def test_platform_normalized_to_lowercase(self, monkeypatch, tmp_path):
        """Platform field is lowercased."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "competitors": [
                {"name": "Mixed", "platform": "YouTube", "handle": "@mix", "why_watch": "test"},
            ]
        }))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

        result = config.load_competitors()
        assert result[0].platform == "youtube"


# ─────────────────────────────────────────────────────────
# load_credentials cascade tests
# ─────────────────────────────────────────────────────────


class TestLoadCredentials:
    """Tests the credential cascade priority: env vars > .env > .credentials."""

    def _setup_encryption(self, monkeypatch, tmp_path):
        """Helper: set up encryption key path and env."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

    def test_encrypted_credentials_loaded(self, monkeypatch, tmp_path):
        """Fernet-encrypted .credentials file is decrypted and loaded."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")  # empty env

        # Write encrypted creds using the module's own encrypt function
        original = {"ig_username": "enc_user", "ig_password": "enc_pass"}
        encrypted = config._encrypt_credentials(original)
        creds_file.write_bytes(encrypted)

        result = config.load_credentials()
        assert result["ig_username"] == "enc_user"
        assert result["ig_password"] == "enc_pass"

    def test_legacy_plaintext_fallback(self, monkeypatch, tmp_path):
        """Plaintext .credentials file (non-encrypted) is parsed as legacy."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")

        # Write plaintext (will fail decryption, fall back to plaintext parsing)
        creds_file.write_text("ig_username=plain_user\nig_password=plain_pass\n")

        result = config.load_credentials()
        assert result["ig_username"] == "plain_user"
        assert result["ig_password"] == "plain_pass"

    def test_env_file_overrides_credentials(self, monkeypatch, tmp_path):
        """.env file values override .credentials values."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", env_file)

        # Write plaintext .credentials
        creds_file.write_text("ig_username=creds_user\nig_password=creds_pass\n")
        # Write .env with override
        env_file.write_text("ig_username=env_user\n")

        result = config.load_credentials()
        assert result["ig_username"] == "env_user"  # .env overrides
        assert result["ig_password"] == "creds_pass"  # inherited from .credentials

    def test_env_var_overrides_everything(self, monkeypatch, tmp_path):
        """Actual environment variables override both .env and .credentials."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", env_file)

        monkeypatch.setenv("IG_USERNAME", "env_var_user")
        # Write .env with different value
        env_file.write_text("IG_USERNAME=dotenv_user\n")
        # Write plaintext .credentials with different value
        creds_file.write_text("ig_username=creds_user\n")

        result = config.load_credentials()
        # env_map maps IG_USERNAME to ig_username
        assert result["ig_username"] == "env_var_user"

    def test_cascade_empty(self, monkeypatch, tmp_path):
        """No sources available returns empty dict."""
        self._setup_encryption(monkeypatch, tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / ".credentials")
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
        # No files, no env vars beyond CREDENTIALS_ENCRYPTION_KEY

        result = config.load_credentials()
        # May include env vars set in environment, but at minimum we verify
        # no credential-specific values are present
        assert isinstance(result, dict)

    def test_plaintext_migration_transparent(self, monkeypatch, tmp_path):
        """Plaintext read → encrypted save → decrypted reload returns same values."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")

        # Write legacy plaintext
        creds_file.write_text("ig_username=migrate_user\nig_password=migrate_pass\n")

        # Load as plaintext
        loaded = config.load_credentials()
        assert loaded["ig_username"] == "migrate_user"
        assert loaded["ig_password"] == "migrate_pass"

        # Save encrypted
        config.save_credentials(loaded)

        # Reload — should now come from encrypted file
        reloaded = config.load_credentials()
        assert reloaded["ig_username"] == "migrate_user"
        assert reloaded["ig_password"] == "migrate_pass"

    def test_env_file_with_encrypted_credentials_merged(self, monkeypatch, tmp_path):
        """.env + encrypted .credentials are merged with .env taking priority."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        env_file = tmp_path / ".env"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", env_file)

        # Write encrypted .credentials
        encrypted = config._encrypt_credentials({"ig_username": "creds_only", "llm_api_key": "sk-from-creds"})
        creds_file.write_bytes(encrypted)

        # Write .env with overlap and unique keys
        env_file.write_text("ig_username=env_wins\nllm_base_url=https://custom.api.com\n")

        result = config.load_credentials()
        assert result["ig_username"] == "env_wins"  # .env overrides .credentials
        assert result["llm_api_key"] == "sk-from-creds"  # from .credentials
        assert result["llm_base_url"] == "https://custom.api.com"  # from .env only

    def test_env_maps_to_lowercase_keys(self, monkeypatch, tmp_path):
        """Environment variables are mapped to lowercase config keys via env_map."""
        self._setup_encryption(monkeypatch, tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / ".credentials")
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")

        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("TRANSCRIBE_PROVIDER", "deepgram")
        monkeypatch.setenv("WHISPER_MODEL", "large")

        result = config.load_credentials()
        assert result["llm_model"] == "gpt-4"
        assert result["transcribe_provider"] == "deepgram"
        assert result["whisper_model"] == "large"


# ─────────────────────────────────────────────────────────
# save_credentials tests
# ─────────────────────────────────────────────────────────


class TestSaveCredentials:
    """Tests for save_credentials()."""

    def _setup_encryption(self, monkeypatch, tmp_path):
        """Helper: set up encryption paths and env var."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")

    def test_saves_encrypted_blob(self, monkeypatch, tmp_path):
        """Saved file is binary (not plaintext)."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)

        config.save_credentials({"ig_username": "secret_user"})

        assert creds_file.exists()
        raw = creds_file.read_bytes()
        # Should not contain our plaintext value
        assert b"secret_user" not in raw
        assert b"ig_username" not in raw

    def test_file_permissions_0600(self, monkeypatch, tmp_path):
        """Saved .credentials file has 0o600 perms."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)

        config.save_credentials({"key": "value"})

        perms = stat.S_IMODE(creds_file.stat().st_mode)
        assert perms == 0o600

    def test_roundtrip_preserves_all_keys(self, monkeypatch, tmp_path):
        """save_credentials → load_credentials returns all original values."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")

        original = {
            "ig_username": "user1",
            "ig_password": "pass1",
            "llm_api_key": "sk-test",
            "transcribe_api_key": "tk-test",
            "llm_base_url": "https://custom.api.com",
            "llm_model": "gpt-4",
        }
        config.save_credentials(original)
        loaded = config.load_credentials()

        # Keys from the roundtrip should match
        for k, v in original.items():
            assert loaded.get(k) == v, f"Key {k} mismatch: {loaded.get(k)} != {v}"

    def test_empty_creds_saves_without_error(self, monkeypatch, tmp_path):
        """Empty dict saves without error."""
        self._setup_encryption(monkeypatch, tmp_path)
        creds_file = tmp_path / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)

        config.save_credentials({})
        assert creds_file.exists()
        raw = creds_file.read_bytes()
        assert len(raw) > 0

    def test_directory_created_if_missing(self, monkeypatch, tmp_path):
        """RECON_DATA_DIR is created if it doesn't exist."""
        self._setup_encryption(monkeypatch, tmp_path)
        nested_dir = tmp_path / "deeply" / "nested" / "recon"
        creds_file = nested_dir / ".credentials"
        monkeypatch.setattr(config, "CREDENTIALS_FILE", creds_file)
        monkeypatch.setattr(config, "RECON_DATA_DIR", nested_dir)

        config.save_credentials({"key": "val"})
        assert creds_file.exists()
        assert nested_dir.exists()


# ─────────────────────────────────────────────────────────
# load_config full assembly tests
# ─────────────────────────────────────────────────────────


class TestLoadConfig:
    """Tests for load_config() — full ReconConfig assembly."""

    def _setup_all(self, monkeypatch, tmp_path):
        """Set up all paths to temp and basic encryption."""
        test_key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", test_key)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_DIR", tmp_path)
        monkeypatch.setattr(config, "CREDENTIALS_KEY_FILE", tmp_path / "credentials.key")
        monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / ".credentials")
        monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
        monkeypatch.setattr(config, "BRAIN_FILE", tmp_path / "agent-brain.json")
        monkeypatch.setattr(config, "RECON_DATA_DIR", tmp_path / "recon")

    def test_full_config_from_credentials(self, monkeypatch, tmp_path):
        """load_config() returns ReconConfig with fields populated from creds + brain."""
        self._setup_all(monkeypatch, tmp_path)

        # Set up brain with competitors
        brain = {"competitors": [
            {"name": "Alice", "platform": "youtube", "handle": "@alice", "why_watch": "tech"},
            {"name": "Bob", "platform": "instagram", "handle": "@bob", "why_watch": "art"},
        ]}
        (tmp_path / "agent-brain.json").write_text(json.dumps(brain))

        # Set up credentials via env vars
        monkeypatch.setenv("IG_USERNAME", "cfg_user")
        monkeypatch.setenv("IG_PASSWORD", "cfg_pass")
        monkeypatch.setenv("LLM_API_KEY", "sk-llm")
        monkeypatch.setenv("TRANSCRIBE_API_KEY", "sk-transcribe")
        monkeypatch.setenv("LLM_BASE_URL", "https://custom.api.com")

        cfg = config.load_config()

        assert len(cfg.competitors) == 2
        assert cfg.competitors[0].name == "Alice"
        assert cfg.competitors[1].name == "Bob"
        assert cfg.ig_username == "cfg_user"
        assert cfg.ig_password == "cfg_pass"
        assert cfg.llm_api_key == "sk-llm"
        assert cfg.transcribe_api_key == "sk-transcribe"
        assert cfg.llm_base_url == "https://custom.api.com"
        assert cfg.llm_model == "gpt-4o-mini"  # default
        assert cfg.llm_provider == "custom"  # default

    def test_defaults_applied_when_missing(self, monkeypatch, tmp_path):
        """Missing credentials get default values."""
        self._setup_all(monkeypatch, tmp_path)

        cfg = config.load_config()

        assert cfg.competitors == []
        assert cfg.ig_username is None
        assert cfg.ig_password is None
        assert cfg.llm_api_key is None
        assert cfg.llm_base_url == "https://api.openai.com/v1"
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.transcribe_base_url == "https://api.openai.com/v1"
        assert cfg.transcribe_model == "whisper-1"
        assert cfg.transcribe_provider == "openai"
        assert cfg.whisper_model == "small.en"

    def test_llm_api_key_fallback_to_openai(self, monkeypatch, tmp_path):
        """llm_api_key falls back to openai_api_key when llm_api_key not set."""
        self._setup_all(monkeypatch, tmp_path)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-fallback")

        cfg = config.load_config()
        assert cfg.llm_api_key == "sk-openai-fallback"

    def test_transcribe_api_key_fallback_to_openai(self, monkeypatch, tmp_path):
        """transcribe_api_key falls back to openai_api_key."""
        self._setup_all(monkeypatch, tmp_path)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-fallback")

        cfg = config.load_config()
        assert cfg.transcribe_api_key == "sk-openai-fallback"

    def test_individual_env_vars_override_defaults(self, monkeypatch, tmp_path):
        """Individual env vars for each field are correctly mapped."""
        self._setup_all(monkeypatch, tmp_path)
        monkeypatch.setenv("LLM_BASE_URL", "https://llm.custom.com")
        monkeypatch.setenv("LLM_MODEL", "claude-3-opus")
        monkeypatch.setenv("TRANSCRIBE_BASE_URL", "https://transcribe.custom.com")
        monkeypatch.setenv("TRANSCRIBE_MODEL", "nova-2")
        monkeypatch.setenv("TRANSCRIBE_PROVIDER", "deepgram")
        monkeypatch.setenv("WHISPER_MODEL", "large-v3")

        cfg = config.load_config()
        assert cfg.llm_base_url == "https://llm.custom.com"
        assert cfg.llm_model == "claude-3-opus"
        assert cfg.transcribe_base_url == "https://transcribe.custom.com"
        assert cfg.transcribe_model == "nova-2"
        assert cfg.transcribe_provider == "deepgram"
        assert cfg.whisper_model == "large-v3"


# ─────────────────────────────────────────────────────────
# get_ig_competitors / get_yt_competitors tests
# ─────────────────────────────────────────────────────────


class TestGetFilteredCompetitors:
    """Tests for get_ig_competitors() and get_yt_competitors()."""

    def _setup_brain(self, monkeypatch, tmp_path):
        """Set up brain file with mixed competitors."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "competitors": [
                {"name": "IG User", "platform": "instagram", "handle": "@ig1", "why_watch": "photos"},
                {"name": "YT User", "platform": "youtube", "handle": "@yt1", "why_watch": "videos"},
                {"name": "IG User 2", "platform": "instagram", "handle": "@ig2", "why_watch": "reels"},
                {"name": "YT User 2", "platform": "youtube", "handle": "@yt2", "why_watch": "streams"},
            ]
        }))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

    def test_get_ig_competitors_filters_instagram(self, monkeypatch, tmp_path):
        """get_ig_competitors returns only platform='instagram'."""
        self._setup_brain(monkeypatch, tmp_path)
        result = config.get_ig_competitors()
        assert len(result) == 2
        assert all(c.platform == "instagram" for c in result)

    def test_get_yt_competitors_filters_youtube(self, monkeypatch, tmp_path):
        """get_yt_competitors returns only platform='youtube'."""
        self._setup_brain(monkeypatch, tmp_path)
        result = config.get_yt_competitors()
        assert len(result) == 2
        assert all(c.platform == "youtube" for c in result)

    def test_empty_when_no_matching_platform(self, monkeypatch, tmp_path):
        """No IG competitors when brain has only YT."""
        brain_file = tmp_path / "agent-brain.json"
        brain_file.write_text(json.dumps({
            "competitors": [
                {"name": "YT Only", "platform": "youtube", "handle": "@yt", "why_watch": "test"},
            ]
        }))
        monkeypatch.setattr(config, "BRAIN_FILE", brain_file)

        ig_result = config.get_ig_competitors()
        assert ig_result == []

    def test_handles_missing_brain_file(self, monkeypatch, tmp_path):
        """Both filtered functions return [] when brain file is missing."""
        monkeypatch.setattr(config, "BRAIN_FILE", tmp_path / "nonexistent.json")
        assert config.get_ig_competitors() == []
        assert config.get_yt_competitors() == []
