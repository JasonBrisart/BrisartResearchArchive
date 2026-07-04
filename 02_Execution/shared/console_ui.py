def startup_menu(framework):
    print("\n" + "-" * 80)
    print(framework.VERSION_LABEL)
    print("-" * 80)

    print("Default settings:")
    for line in framework.DEFAULT_MODE_DESCRIPTION:
        print(f"- {line}")

    print()
    print("Press ENTER to start experiment")
    print("Press O for Options")

    choice = input("\nSelection: ").strip().upper()

    return choice == "O"


def is_default_configuration(config):
    """
    Returns True only when the current option settings match
    the official Default TFL configuration.

    Default TFL:
    - Extra stimuli OFF
    - Perturbations OFF
    - Probes ON
    - Delayed reentry ON
    """

    return (
        config.get("enable_extra_stimuli", False) is False
        and config.get("enable_perturbations", False) is False
        and config.get("enable_probes", True) is True
        and config.get("enable_delayed_reentry", True) is True
    )


def update_run_mode(config):
    """
    Automatically updates the run mode label based on the current settings.

    If the settings match Default TFL, label it Default TFL.
    If any setting differs, label it Modified TFL.
    """

    if is_default_configuration(config):
        config["run_mode"] = "default_tfl"
    else:
        config["run_mode"] = "modified_tfl"

    return config


def format_run_mode(run_mode):
    labels = {
        "default_tfl": "Default TFL",
        "modified_tfl": "Modified TFL",
    }

    return labels.get(run_mode, run_mode)


def print_current_options(framework, config):
    blocks = config.get("blocks", [])
    trials_per_block = config.get("trials_per_block", 0)
    total_trials = trials_per_block * len(blocks)

    config = update_run_mode(config)

    print("\nCurrent Settings")
    print("-" * 60)
    print(f"Framework: {framework.FRAMEWORK_NAME}")
    print(f"Run Configuration: {format_run_mode(config.get('run_mode', 'default_tfl'))}")
    print(f"Extra Stimuli: {'ON' if config.get('enable_extra_stimuli', False) else 'OFF'}")
    print(f"Perturbations: {'ON' if config.get('enable_perturbations', False) else 'OFF'}")
    print(f"Probes: {'ON' if config.get('enable_probes', True) else 'OFF'}")
    print(f"Delayed Reentry: {'ON' if config.get('enable_delayed_reentry', True) else 'OFF'}")
    print(f"Trials Per Block: {trials_per_block}")
    print(f"Blocks: {', '.join(blocks)}")
    print(f"Total Trials: {total_trials}")


def options_menu(framework, config):
    config = dict(config)
    config = update_run_mode(config)

    while True:
        print("\n" + "=" * 80)
        print(f"{framework.FRAMEWORK_ID} OPTIONS MENU")
        print("=" * 80)

        print_current_options(framework, config)

        print("\nOptions")
        print("-" * 60)
        print("1. Restore Default Settings")
        print("2. Toggle Perturbations")
        print("3. Toggle Extra Stimuli")
        print("4. Toggle Probes")
        print("5. Toggle Delayed Reentry")

        print("\nS. Save and Return")

        choice = input("\nChoice: ").strip().upper()

        if choice == "1":
            config = framework.apply_default_options(config)
            config = update_run_mode(config)
            print("\nDefault settings restored.")

        elif choice == "2":
            config["enable_perturbations"] = not config.get("enable_perturbations", False)
            config = update_run_mode(config)
            print(f"\nPerturbations are now {'ON' if config['enable_perturbations'] else 'OFF'}.")

        elif choice == "3":
            config["enable_extra_stimuli"] = not config.get("enable_extra_stimuli", False)
            config = update_run_mode(config)
            print(f"\nExtra Stimuli are now {'ON' if config['enable_extra_stimuli'] else 'OFF'}.")

        elif choice == "4":
            config["enable_probes"] = not config.get("enable_probes", True)
            config = update_run_mode(config)
            print(f"\nProbes are now {'ON' if config['enable_probes'] else 'OFF'}.")

        elif choice == "5":
            config["enable_delayed_reentry"] = not config.get("enable_delayed_reentry", True)
            config = update_run_mode(config)
            print(f"\nDelayed Reentry is now {'ON' if config['enable_delayed_reentry'] else 'OFF'}.")

        elif choice == "S":
            config = update_run_mode(config)
            print("\nOptions saved for this run.")
            return config

        else:
            print("Invalid choice. Please select 1-5 or S.")