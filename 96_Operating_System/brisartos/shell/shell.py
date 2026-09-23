"""
BrisartOS Shell
Pure Python.
No dependencies.
"""

from runtime import BrisartRuntime


PROMPT = "BrisartOS> "


def print_help():
    print()
    print("help")
    print("version")
    print("system")
    print("modules")
    print("describe <module>")
    print("run <module>")
    print("reload")
    print("services")
    print("service <name>")
    print("new-id")
    print("exit")
    print()


def shell_loop():
    runtime = BrisartRuntime()
    runtime.boot()

    print(
        "BrisartOS Modular Shell"
    )
    print(
        "Type help "
        "for commands."
    )
    print()

    running = True

    while running:
        try:
            command = input(
                PROMPT
            )
        except EOFError:
            break

        parts = (
            command
            .strip()
            .split()
        )

        if not parts:
            continue

        name = parts[0].lower()
        args = parts[1:]

        if name in (
            "exit",
            "quit",
            "shutdown",
        ):
            running = False

        elif name == "help":
            print_help()

        elif name == "version":
            print(
                runtime
                .version_text()
            )

        elif name == "system":
            runtime.print_system_info()

        elif name == "modules":
            runtime.print_modules()

        elif name == "describe":
            if args:
                runtime.describe_module(
                    args[0]
                )
            else:
                print("usage: describe <module>")

        elif name == "run":
            if args:
                runtime.run_module(
                    args[0]
                )
            else:
                print("usage: run <module>")

        elif name == "reload":
            runtime.reload_modules()

        elif name == "services":
            runtime.print_services()

        elif name == "service":
            if args:
                runtime.describe_service(
                    args[0]
                )
            else:
                print("usage: service <name>")

        elif name == "new-id":
            print(
                runtime.api
                .new_object_id()
            )

        else:
            print(
                f"unknown command: "
                f"{name}"
            )


if __name__ == "__main__":
    shell_loop()