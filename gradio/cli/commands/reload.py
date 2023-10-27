"""

Contains the functions that run when `gradio` is called from the command line. Specifically, allows

$ gradio app.py, to run app.py in reload mode where any changes in the app.py file or Gradio library reloads the demo.
$ gradio app.py my_demo, to use variable names other than "demo"
"""
from __future__ import annotations

import inspect
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Optional

import typer
from rich import print
from uvicorn import Config
from uvicorn.supervisors import ChangeReload

import gradio
from gradio import networking, utils

reload_thread = threading.local()


def _setup_config(
    demo_path: Path,
    demo_name: str = "demo",
    additional_watch_dirs: list[str] | None = None,
    restart_server: bool = True,
):
    original_path = demo_path
    app_text = Path(original_path).read_text()

    patterns = [
        f"with gr\\.Blocks\\(\\) as {demo_name}",
        f"{demo_name} = gr\\.Blocks",
        f"{demo_name} = gr\\.Interface",
        f"{demo_name} = gr\\.ChatInterface",
        f"{demo_name} = gr\\.Series",
        f"{demo_name} = gr\\.Parallel",
        f"{demo_name} = gr\\.TabbedInterface",
    ]

    if not any(re.search(p, app_text) for p in patterns):
        print(
            f"\n[bold red]Warning[/]: Cannot statically find a gradio demo called {demo_name}. "
            "Reload work may fail."
        )

    abs_original_path = utils.abspath(original_path)
    if restart_server:
        path = os.path.normpath(original_path)
        path = path.replace("/", ".")
        path = path.replace("\\", ".")
        filename = os.path.splitext(path)[0]
        demo_name = f"{demo_name}.app"
    else:
        filename = Path(original_path).stem

    gradio_folder = Path(inspect.getfile(gradio)).parent

    message = "Watching:"
    message_change_count = 0

    watching_dirs = []
    if str(gradio_folder).strip():
        watching_dirs.append(gradio_folder)
        message += f" '{gradio_folder}'"
        message_change_count += 1

    abs_parent = abs_original_path.parent
    if str(abs_parent).strip():
        watching_dirs.append(abs_parent)
        if message_change_count == 1:
            message += ","
        message += f" '{abs_parent}'"

    abs_parent = Path(".").resolve()
    if str(abs_parent).strip():
        watching_dirs.append(abs_parent)
        if message_change_count == 1:
            message += ","
        message += f" '{abs_parent}'"

    for wd in additional_watch_dirs or []:
        if Path(wd) not in watching_dirs:
            watching_dirs.append(wd)

            if message_change_count == 1:
                message += ","
            message += f" '{wd}'"

    print(message + "\n")

    # guaranty access to the module of an app
    sys.path.insert(0, os.getcwd())
    return filename, abs_original_path, [str(s) for s in watching_dirs], demo_name


def main(
    demo_path: Path,
    demo_name: str = "demo",
    watch_dirs: Optional[List[str]] = None,
    restart_server: bool = True,
):
    # default execution pattern to start the server and watch changes
    filename, path, watch_dirs, demo_name = _setup_config(
        demo_path, demo_name, watch_dirs, restart_server
    )
    # extra_args = args[1:] if len(args) == 1 or args[1].startswith("--") else args[2:]
    if restart_server:
        port = networking.get_first_available_port(
            networking.INITIAL_PORT_VALUE,
            networking.INITIAL_PORT_VALUE + networking.TRY_NUM_PORTS,
        )
        gradio_app = f"{filename}:{demo_name}"
        cfg = Config(
            gradio_app,
            reload=True,
            port=port,
            log_level="warning",
            reload_dirs=watch_dirs,
        )
        server = networking.Server(cfg)
        sock = cfg.bind_socket()
        print(
            f"Launching in [bold][magenta]reload mode[/][/] on: http://{networking.LOCALHOST_NAME}:{port} (Press CTRL+C to quit)\n"
        )
        ChangeReload(cfg, target=server.run, sockets=[sock]).run()
    else:
        popen = subprocess.Popen(
            [sys.executable, "-u", path],
            env=dict(
                os.environ,
                GRADIO_WATCH_DIRS=",".join(watch_dirs),
                GRADIO_WATCH_FILE=filename,
                GRADIO_WATCH_DEMO_NAME=demo_name,
            ),
        )
        popen.wait()


if __name__ == "__main__":
    typer.run(main)
