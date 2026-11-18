from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from logging import LogRecord
from pathlib import Path
from typing import Optional

import typer
from deepdiff import DeepDiff

from srl_converter import lab

############################################################################################################
#  LOGGER
#
############################################################################################################

logger = logging.getLogger("srl_converter")
logger.setLevel(logging.INFO)

def create_console_logger():
    fh = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    fh.setLevel(logger.level)
    logger.addHandler(fh)

def create_file_logger(filename="console.log"):
    global logger

    if filename:
        fh = logging.FileHandler(filename)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        fh.setLevel(logger.level)
        logger.addHandler(fh)

def set_logger_debug():
    global logger

    """Sets the logger and all its handlers to DEBUG level."""
    logger.setLevel(logging.DEBUG)

    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)


def _create_output_folders(output_folder: Path=None):
    #Create output folder
    workdir=None
    if output_folder is None:
        workdir = Path(tempfile.mkdtemp(prefix="srl_converter-"))
    else:
        #Create folder
        logger.info(f"Creating folder {output_folder}")
        workdir = output_folder.mkdir(parents=True, exist_ok=True)
        workdir = output_folder

    if not workdir:
        msg = f"Unknow folder {output_folder}"
        raise FileNotFoundError(msg)

    #Create subfolders
    if workdir:
        logger.info("Creating subfolders")
        for subfolder in ["diff_files", "conversion_files", "output" ]:
            subdir = workdir / subfolder
            subdir.mkdir(parents=True, exist_ok=True)

    return workdir

def _get_version() -> str:
    try:
        return version("srlconv")
    except PackageNotFoundError:
        return "0.0.0"




def _syntax_theme_for_deepdiff() -> str:
    """Pick Rich Syntax theme for the host terminal.

    Rich cannot query the real background color portably. We use built-in
    ``ansi_light`` / ``ansi_dark`` (terminal-native 16-color pairs), plus:

    - ``SRLCONV_SYNTAX_THEME=ansi_light|ansi_dark|monokai`` to force a style.
    - If unset, ``COLORFGBG`` (``fg;bg``, 0--15) when present: background
      ``>= 8`` is treated as a light screen → ``ansi_light``, else ``ansi_dark``.
    - Otherwise ``ansi_dark`` (closest to the previous fixed ``monokai`` look).
    """
    override = os.environ.get("SRLCONV_SYNTAX_THEME", "").strip().lower()
    if override in ("ansi_light", "light"):
        return "ansi_light"
    if override in ("ansi_dark", "dark"):
        return "ansi_dark"
    if override == "monokai":
        return "monokai"
    fgbg = os.environ.get("COLORFGBG", "")
    parts = fgbg.split(";")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        bg = int(parts[1])
        if bg >= 8:
            return "ansi_light"
        return "ansi_dark"
    return "ansi_dark"


def _multiline_git_diff(path1: Path, path2: Path) -> str:
    q1 = shlex.quote(str(path1))
    q2 = shlex.quote(str(path2))
    return f"git diff --patience --color-moved=dimmed-zebra \\\n{q1} \\\n{q2}"


def _json_without_preamble(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if k != "_preamble"}
    return obj




def _generate_deepdiff( left: Path, right: Path, *, as_json: bool, filename: str ) -> None:
    try:
        if as_json:
            with left.open(encoding="utf-8") as f:
                a = _json_without_preamble(json.load(f))
            with right.open(encoding="utf-8") as f:
                b = _json_without_preamble(json.load(f))
        else:
            a = left.read_text(encoding="utf-8").splitlines()
            b = right.read_text(encoding="utf-8").splitlines()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        raise typer.Exit(1) from e
    except OSError as e:
        logger.error(f"{e}")
        raise typer.Exit(1) from e

    diff = DeepDiff(a, b, ignore_order=True)
    if not diff:
        logger.info( f"No differences (ignoring list/order where applicable)." )
        return None

    with open(filename, "w", encoding="utf-8") as f:
        f.write(diff.to_json(indent=2))

def _generate_deepdiffs( workdir: Path, *, orig_cfg_path: Path, converted_path: Path, orig_cli_path: Path, cli_path: Path, orig_cli_flat_path: Path, cli_flat_path: Path ) -> None:

    if workdir is None or not isinstance(workdir, Path):
        logger.error( f"Folder {workdir} is not valid." )
        return None

    diff_files = workdir / "diff_files"
    if diff_files is None or not isinstance(diff_files, Path):
        logger.error( f"Folder {diff_files} is not valid." )
        return None    

    filename = str( diff_files / "diff-config.json" )
    _generate_deepdiff(orig_cfg_path, converted_path, as_json=True, filename=filename )

    filename = str( diff_files / "diff-cli.json" )
    _generate_deepdiff(orig_cli_path, cli_path, as_json=False, filename=filename )

    filename = str( diff_files / "diff-cli_flat.json" )
    _generate_deepdiff(orig_cli_flat_path, cli_flat_path, as_json=False, filename=filename )




def _version_callback(value: bool) -> None:
    if value:
        logger.info(_get_version())
        raise typer.Exit(0)


app = typer.Typer(
    invoke_without_command=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def main(
    ctx: typer.Context,
    show_version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_flag=True,
        is_eager=True,
    ),
) -> None:
    #Create Console logger
    create_console_logger()

    if ctx.invoked_subcommand is None:
        logger.info(ctx.get_help())


@app.command("version")
def version_cmd() -> None:
    """Print the installed srlconv version."""
    logger.info(_get_version())


@app.command("convert")
def convert_cmd(
    current_version: str = typer.Option(
        ...,
        "--current-version",
        help="Current SR Linux version (e.g. 25.10.1 or v25.10.1).",
    ),
    current_config: Path = typer.Option(
        ...,
        "--current-config",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the current configuration file.",
    ),
    current_type: str = typer.Option(
        "ixr-d2l",
        "--current-type",
        help="SR Linux device type for the source node.",
    ),
    target_version: str = typer.Option(
        ...,
        "--target-version",
        help="Target SR Linux version (e.g. 25.10.1 or v25.10.1).",
    ),
    target_type: Optional[str] = typer.Option(
        None,
        "--target-type",
        help="SR Linux device type for the target node (defaults to --current-type).",
    ),
    show_git_diff_commands: bool = typer.Option(
        False,
        "--show-git-diff-commands",
        help="Print suggested git diff commands for CLI and CLI-flat configs.",
    ),

    output_folder: Path = typer.Option(
        ...,
        "--output",
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        help="Output folder path",
    ),
    enable_debug: Optional[bool] = typer.Option(
        None,
        "--debug",
        "-d",
        help="Enable DEBUG",
        is_flag=True,
    )
) -> None:
    """Template a Containerlab topology and deploy it for configuration conversion."""

    #Create output folder
    workdir = _create_output_folders(output_folder)

    #Set session log
    console_log = f'{ workdir / "console.log"}'
    create_file_logger(filename=console_log)

    if enable_debug:
        set_logger_debug()


    try:
        lab.ensure_containerlab_cli()
    except RuntimeError as e:
        logger.error(f"{e}")
        raise typer.Exit(1) from e

    effective_target_type = target_type if target_type is not None else current_type
    cv = lab.normalize_srlinux_version(current_version)
    tv = lab.normalize_srlinux_version(target_version)
    # console = Console()

    try:
        (
            workdir,
            orig_cfg_path,
            orig_cli_path,
            orig_cli_flat_path,
            converted_path,
            cli_path,
            cli_flat_path,
            topology_path
        ) = lab.prepare_and_deploy(
            output_folder=output_folder,
            current_version=current_version,
            current_config=current_config,
            current_type=current_type,
            target_version=target_version,
            target_type=effective_target_type
        )

        #try to destroy the lab
        lab.destroy( workdir, topology_path )

    except FileNotFoundError as e:
        logger.error(f"{e}")
        raise typer.Exit(1) from e
    except subprocess.CalledProcessError as e:
        logger.error(f"Containerlab exited with status {e.returncode}")
        err_text = (e.stderr or "").strip()
        out_text = (e.stdout or "").strip()
        detail = "\n".join(x for x in (err_text, out_text) if x)
        if detail:
            logger.error(f"{rich_escape(detail)}")
        raise typer.Exit(e.returncode or 1) from e
    except RuntimeError as e:
        logger.error(f"{e}")
        raise typer.Exit(1) from e



    logger.info(f"Generating Diffs: {workdir/"diff_files"}")
    _generate_deepdiffs(
        workdir,
        orig_cfg_path=orig_cfg_path,
        converted_path=converted_path,
        orig_cli_path=orig_cli_path,
        cli_path=cli_path,
        orig_cli_flat_path=orig_cli_flat_path,
        cli_flat_path=cli_flat_path,
    )