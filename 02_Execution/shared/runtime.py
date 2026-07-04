from shared.io import load_json, load_csv, apply_stimulus_limit
from shared.console_ui import startup_menu, options_menu
from shared.experiment_session import run_session


def run_framework(framework):
    config = load_json(framework.CONFIG_FILE)
    config = framework.apply_default_options(config)

    show_options = startup_menu(framework)

    if show_options:
        config = options_menu(framework, config)

    stimuli = load_csv(framework.STIMULI_FILE)
    stimuli = apply_stimulus_limit(
        stimuli=stimuli,
        enable_extra_stimuli=config.get("enable_extra_stimuli", False),
        base_limit=framework.BASE_STIMULUS_LIMIT,
    )

    trials = framework.build_trials(config, stimuli)

    run_session(framework, config, stimuli, trials)