"""Unit tests for the structured GPU model parser and comparison."""

import pytest

try:
    from omnis.jobs.gpu import (
        AMD_DGPU_MODELS,
        AMD_IGPU_MODELS,
        INTEL_DGPU_MODELS,
        INTEL_IGPU_MODELS,
        NVIDIA_DGPU_MODELS,
        ParsedModel,
        compare_models,
        parse_model,
    )

    HAS_GPU = True
except ImportError:
    HAS_GPU = False

pytestmark = pytest.mark.skipif(not HAS_GPU, reason="gpu module not available")


def _parsed(model: str) -> "ParsedModel":
    """Parse a model name, failing the test if it cannot be ranked."""
    parsed = parse_model(model)
    assert parsed is not None, f"{model} should be rankable"
    return parsed


class TestParseModel:
    """Model names are turned into orderable tuples."""

    def test_parses_amd_model(self) -> None:
        parsed = _parsed("Radeon RX 9060 XT")
        assert (parsed.prefix, parsed.number) == ("RX", 9060)

    def test_parses_nvidia_model(self) -> None:
        parsed = _parsed("GeForce RTX 4070 Ti SUPER")
        assert (parsed.prefix, parsed.number) == ("RTX", 4070)

    def test_parses_arc_generation_letter(self) -> None:
        assert _parsed("Arc B580").series_rank > _parsed("Arc A770").series_rank

    def test_gtx_prefix_is_not_truncated_to_gt(self) -> None:
        parsed = _parsed("GeForce GTX 1080 Ti")
        assert parsed.prefix == "GTX"
        assert parsed.series_rank == 0

    def test_returns_none_for_unstructured_names(self) -> None:
        assert parse_model("Vega 8") is None
        assert parse_model("Radeon 780M") is None
        assert parse_model("Iris Xe") is None
        assert parse_model("UHD 630") is None

    def test_multi_model_string_keeps_its_own_suffix(self) -> None:
        assert _parsed("Radeon RX 7900 XT/7900 XTX") == _parsed("RX 7900 XT")


class TestModelOrdering:
    """Generation, then tier, then suffix."""

    def test_suffix_outranks_bare_model(self) -> None:
        assert _parsed("RX 9070 XT") > _parsed("RX 9070")

    def test_xtx_outranks_xt(self) -> None:
        assert _parsed("RX 7900 XTX") > _parsed("RX 7900 XT")

    def test_ti_super_outranks_ti(self) -> None:
        assert _parsed("RTX 4070 Ti SUPER") > _parsed("RTX 4070 Ti")

    def test_ti_outranks_super(self) -> None:
        assert _parsed("RTX 4070 Ti") > _parsed("RTX 4070 SUPER")

    def test_newer_generation_outranks_older_tier(self) -> None:
        assert _parsed("RX 9060 XT") > _parsed("RX 7900 XTX")

    def test_tier_orders_within_a_generation(self) -> None:
        assert _parsed("RTX 4080") > _parsed("RTX 4060 Ti")

    def test_arc_generation_beats_tier(self) -> None:
        assert _parsed("Arc B570") > _parsed("Arc A770")

    @pytest.mark.parametrize(
        "models",
        [AMD_DGPU_MODELS, NVIDIA_DGPU_MODELS, INTEL_DGPU_MODELS],
    )
    def test_parser_agrees_with_the_curated_lists(self, models: list[str]) -> None:
        """The parser must reproduce the hand-maintained ordering."""
        keys = [_parsed(model) for model in models]
        assert keys == sorted(keys)


class TestCompareModels:
    """Minimum requirement checks."""

    def test_unlisted_recent_amd_card_is_accepted(self) -> None:
        """RX 9060 XT is absent from the table but newer than the RX 560 minimum."""
        assert compare_models("Radeon RX 9060 XT", "RX 560", AMD_DGPU_MODELS) is True

    def test_unlisted_future_nvidia_card_is_accepted(self) -> None:
        assert compare_models("GeForce RTX 6080", "GTX 1650", NVIDIA_DGPU_MODELS) is True

    def test_older_card_below_minimum_is_rejected(self) -> None:
        assert compare_models("Radeon RX 550", "RX 560", AMD_DGPU_MODELS) is False
        assert compare_models("GeForce GTX 1050", "GTX 1650", NVIDIA_DGPU_MODELS) is False

    def test_equal_model_passes(self) -> None:
        assert compare_models("Radeon RX 560", "RX 560", AMD_DGPU_MODELS) is True

    def test_unknown_model_is_permissive(self) -> None:
        """An incomplete table must never block an installation."""
        assert compare_models("Mystery Accelerator 9000", "RX 560", AMD_DGPU_MODELS) is True

    def test_unknown_minimum_is_permissive(self) -> None:
        assert compare_models("Arc B580", "Xe", INTEL_DGPU_MODELS) is True

    def test_exception_table_still_ranks_amd_igpus(self) -> None:
        assert compare_models("Vega 8", "Vega 3", AMD_IGPU_MODELS) is True
        assert compare_models("Vega 3", "Vega 8", AMD_IGPU_MODELS) is False
        assert compare_models("Radeon 890M", "Radeon 780M", AMD_IGPU_MODELS) is True
        assert compare_models("Radeon 660M", "Radeon 780M", AMD_IGPU_MODELS) is False

    def test_exception_table_still_ranks_intel_igpus(self) -> None:
        assert compare_models("UHD 770", "Xe", INTEL_IGPU_MODELS) is True
        assert compare_models("Iris Xe", "Xe", INTEL_IGPU_MODELS) is True
        assert compare_models("UHD 630", "Xe", INTEL_IGPU_MODELS) is False
        assert compare_models("HD 4000", "Xe", INTEL_IGPU_MODELS) is False

    def test_iris_xe_max_is_not_shadowed_by_the_shorter_xe_entry(self) -> None:
        assert compare_models("Iris Xe MAX", "Iris Xe", INTEL_IGPU_MODELS) is True
