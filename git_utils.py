from os import PathLike
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Sequence, TypeAlias

StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]
_CMD: TypeAlias = StrOrBytesPath | Sequence[StrOrBytesPath]


class NotAGitProjectError(OSError):
    pass


def is_git_proj(path: Path | str) -> bool:
    if isinstance(path, str):
        path = Path(path)
    if not path.is_dir():
        raise NotADirectoryError(f"Path provided is not a directory: '{path}'")
    git_path = path / ".git"
    return git_path.exists()


def proj_has_changes(path: Path | str) -> bool:
    if not is_git_proj(path):
        raise NotAGitProjectError(f"Path provided is not a git project: '{path}'")
    result = run_git(["status", "-s"], path)
    return result.stdout != ""


def _append_args(
    arg_list: list[StrOrBytesPath],
    args: _CMD,
) -> list[StrOrBytesPath]:
    if isinstance(args, (str, bytes, PathLike)):
        arg_list.append(args)
    else:
        arg_list.extend(args)
    return arg_list


def run_git(
    args: _CMD,
    cwd: StrOrBytesPath | None = None,
    *,
    cfg_opts: dict[str, str] | None = None,
    capture_output: bool = True,
    check: bool = True,
) -> CompletedProcess[str]:
    """Run a git command with some set of `args`

    Args:
        args (list): Arguments to be passed to `git` process call.
        cwd (StrOrBytesPath | None, optional): Directory to execute `git` from. When None, use default cwd. Defaults to None.
        cfg_opts (dict[str, str] | None = None, optional): Config options to be passed to the `git` process call with the `-c` flag. Defaults to None.
        capture_output (bool, optional): Capture stdout and stderr streams into returned `CompletedProcess` object. Defaults to True.
        check (bool, optional): Should this function check the process exit code and raise a `CalledProcessError` when it is non-zero. Defaults to True.

    Returns:
        CompletedProcess[str]: The result of executing the git process and args with `subprocess.run()`.
    """

    if cfg_opts:
        for key, val in cfg_opts.items():
            args = _append_args(["-c", f"{key}={val}"], args)

    return run(
        args=_append_args(["git"], args),
        cwd=cwd,
        encoding="utf-8",
        capture_output=capture_output,
        check=check,
    )


### About: trust_local_submodules ###
# "protocol.file.allow=always" lets the submodule command clone from a local directory. It's
# necessary as of Git 2.38.1, where the default was changed to "user" in response to
# CVE-2022-39253. It isn't a concern when all repos involved are trusted. For more
# information, see:
# https://github.blog/2022-10-18-git-security-vulnerabilities-announced/#cve-2022-39253
# https://bugs.launchpad.net/ubuntu/+source/git/+bug/1993586
# https://git-scm.com/docs/git-config#Documentation/git-config.txt-protocolallow


def git_clone(
    rem: StrOrBytesPath,
    local: StrOrBytesPath | None = None,
    *,
    init_submodules: bool = False,
    trust_local_submodules: bool = False,
    cfg_opts: dict[str, str] | None = None,
    capture_output: bool = True,
    check: bool = True,
) -> CompletedProcess[str]:

    args: list[StrOrBytesPath] = ["clone", rem]

    if local is not None:
        args.append(local)

    if init_submodules:
        args.append("--recurse-submodules")

    if trust_local_submodules:
        if not cfg_opts:
            cfg_opts = dict()
        cfg_opts["protocol.file.allow"] = "always"

    return run_git(
        args=args,
        cfg_opts=cfg_opts,
        capture_output=capture_output,
        check=check,
    )


def git_submodule_recursive_foreach(
    args: _CMD,
    cwd: StrOrBytesPath | None = None,
    *,
    trust_local_submodules: bool = False,
    cfg_opts: dict[str, str] | None = None,
    capture_output: bool = True,
    check: bool = True,
) -> CompletedProcess[str]:

    if trust_local_submodules:
        if not cfg_opts:
            cfg_opts = dict()
        cfg_opts["protocol.file.allow"] = "always"

    return run_git(
        args=_append_args(["submodule", "foreach", "--recursive"], args),
        cwd=cwd,
        cfg_opts=cfg_opts,
        capture_output=capture_output,
        check=check,
    )


if __name__ == "__main__":
    import os
    from subprocess import CalledProcessError

    root = Path(__file__).parent.absolute()

    try:
        # Print state of current project
        has_changes = proj_has_changes(root)
        msg = "has changes!" if has_changes else "is up to date!"
        print(f"Project '{root.name}' {msg}")
    except Exception as e:
        print(e)

    try:
        # Expect __file__ not to be a dir to print error example
        has_changes = proj_has_changes(Path(__file__))
    except Exception as e:
        print(e)

    home_directory = os.path.expanduser("~")

    try:
        # Expect home_directory not to be a git dir to print error example
        has_changes = proj_has_changes(Path(home_directory))
    except Exception as e:
        print(e)

    try:
        # Example usage of run_git
        result = run_git(["status", "-s"], root)
        print(result.stdout.rstrip())
    except Exception as e:
        print(e)

    if not is_git_proj(home_directory):
        try:
            # Example of errors raised by underlying git error
            result = run_git(["status"], home_directory)
        except CalledProcessError as cpe:
            print(cpe)
            print(cpe.stderr.rstrip())
        except Exception as e:
            print(e)