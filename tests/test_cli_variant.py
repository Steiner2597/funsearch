import pytest
from typer.testing import CliRunner
from experiments.cli import app
from experiments.config import load_config
import yaml
import os

runner = CliRunner()

def test_cli_variant_flag_A(tmp_path):
    config_data = {
        "run_id": "test_run",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "generator_provider_id": "fake",
        "refiner_provider_id": "fake",
        "task_name": "bin_packing",
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # We need to mock ExperimentRunner.run to avoid actually running the experiment
    # But for now, we just want to see if the CLI accepts the flag and passes it to load_config or similar.
    # Actually, the task says "Config object has variant field passed through".
    # Let's check if we can intercept the config object.
    
    # Since we can't easily intercept the config object without mocking ExperimentRunner,
    # let's mock ExperimentRunner in experiments.cli
    
    from unittest.mock import patch
    with patch("experiments.cli.ExperimentRunner") as mock_runner:
        result = runner.invoke(app, ["run", str(config_file), "--variant", "A"])
        assert result.exit_code == 0
        # Check if the config passed to ExperimentRunner has variant="a"
        args, kwargs = mock_runner.call_args
        config = args[0]
        assert config.variant == "a"

def test_cli_variant_flag_B(tmp_path):
    config_data = {
        "run_id": "test_run",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "generator_provider_id": "fake",
        "refiner_provider_id": "fake",
        "task_name": "bin_packing",
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    from unittest.mock import patch
    with patch("experiments.cli.ExperimentRunner") as mock_runner:
        result = runner.invoke(app, ["run", str(config_file), "--variant", "B"])
        assert result.exit_code == 0
        args, kwargs = mock_runner.call_args
        config = args[0]
        assert config.variant == "b"

def test_cli_variant_flag_both(tmp_path):
    config_data = {
        "run_id": "test_run",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "generator_provider_id": "fake",
        "refiner_provider_id": "fake",
        "task_name": "bin_packing",
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    from unittest.mock import patch
    with patch("experiments.cli.ExperimentRunner") as mock_runner:
        result = runner.invoke(app, ["run", str(config_file), "--variant", "both"])
        assert result.exit_code == 0
        args, kwargs = mock_runner.call_args
        config = args[0]
        assert config.variant == "both"

def test_cli_variant_default(tmp_path):
    config_data = {
        "run_id": "test_run",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "generator_provider_id": "fake",
        "refiner_provider_id": "fake",
        "task_name": "bin_packing",
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    from unittest.mock import patch
    with patch("experiments.cli.ExperimentRunner") as mock_runner:
        result = runner.invoke(app, ["run", str(config_file)])
        assert result.exit_code == 0
        args, kwargs = mock_runner.call_args
        config = args[0]
        assert config.variant == "both"

def test_cli_variant_invalid(tmp_path):
    config_data = {
        "run_id": "test_run",
        "seed": 42,
        "max_generations": 1,
        "population_size": 2,
        "num_islands": 1,
        "top_k_for_full_eval": 1,
        "generator_provider_id": "fake",
        "refiner_provider_id": "fake",
        "task_name": "bin_packing",
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(app, ["run", str(config_file), "--variant", "C"])
    assert result.exit_code != 0
    output = result.stdout + result.stderr
    assert "Invalid variant" in output or "Usage" in output
