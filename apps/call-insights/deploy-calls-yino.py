#!/usr/bin/env python3
"""Deploy a versioned VAPI Call Insights release over SSH.

Credentials are intentionally delegated to the local SSH agent/config. This
script never accepts or stores a password, API key, or mail recipient.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile


APP_ROOT = Path(__file__).resolve().parent
REMOTE_ROOT = "/opt/vapi-call-insights"
REMOTE_RELEASES = "/opt/vapi-call-insights/releases"
SERVICE_USER = "vapi-call-insights"
MAIL_SERVICE_USER = "vapi-call-insights-mail"
SOURCE_PATHS = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "src",
    "tools",
    "scripts",
    "deploy",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--mail-state",
        choices=("disabled", "enabled", "unchanged"),
        default="disabled",
    )
    return parser.parse_args()


def source_entries() -> list[Path]:
    entries: list[Path] = []
    for source_name in SOURCE_PATHS:
        source = APP_ROOT / source_name
        if not source.exists():
            raise RuntimeError(f"missing deployment source: {source_name}")
        candidates = [source]
        if source.is_dir():
            candidates.extend(sorted(source.rglob("*")))
        for candidate in candidates:
            if candidate.is_symlink() or not (
                candidate.is_dir() or candidate.is_file()
            ):
                raise RuntimeError(
                    f"unsupported deployment source: {candidate}"
                )
            entries.append(candidate)
    return entries


def source_digest(entries: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in entries:
        relative = path.relative_to(APP_ROOT).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def release_id(entries: list[Path]) -> str:
    return source_digest(entries)[:20]


def build_archive(
    destination: Path,
    release: str,
    entries: list[Path],
) -> None:
    with destination.open("wb") as raw_archive:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_archive,
            mtime=0,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in entries:
                    relative = path.relative_to(APP_ROOT).as_posix()
                    tar_info = archive.gettarinfo(
                        str(path),
                        arcname=f"{release}/{relative}",
                    )
                    tar_info.uid = 0
                    tar_info.gid = 0
                    tar_info.uname = "root"
                    tar_info.gname = "root"
                    tar_info.mtime = 0
                    tar_info.mode = (
                        0o755
                        if path.is_dir() or
                        relative == "scripts/backup-runtime.sh"
                        else 0o644
                    )
                    if path.is_file():
                        with path.open("rb") as contents:
                            archive.addfile(tar_info, contents)
                    else:
                        archive.addfile(tar_info)


def run(command: list[str], dry_run: bool) -> None:
    if dry_run:
        print(shlex.join(command))
        return
    subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()
    entries = source_entries()
    release = release_id(entries)
    target = f"{args.user}@{args.host}"
    with tempfile.TemporaryDirectory(prefix="vapi-call-insights-deploy-") as temp:
        archive = Path(temp) / f"{release}.tar.gz"
        build_archive(archive, release, entries)
        remote_archive = f"/tmp/{release}.tar.gz"
        ssh = ["ssh", "-p", str(args.port), target]
        scp = ["scp", "-P", str(args.port), str(archive), f"{target}:{remote_archive}"]
        run(scp, args.dry_run)

        mail_pre_activation = {
            "disabled": (
                "if test -n \"$mail_unit_state\"; then "
                "systemctl disable --now vapi-call-insights-mail.service; fi"
            ),
            "enabled": (
                "if test -n \"$mail_unit_state\"; then "
                "systemctl stop vapi-call-insights-mail.service; fi"
            ),
            "unchanged": ":",
        }[args.mail_state]
        mail_post_activation = {
            "disabled": ":",
            "enabled": (
                "systemctl enable vapi-call-insights-mail.service && "
                "systemctl restart vapi-call-insights-mail.service"
            ),
            "unchanged": (
                "if test \"$mail_was_active\" = active; then "
                "systemctl restart vapi-call-insights-mail.service; fi"
            ),
        }[args.mail_state]
        restore_mail_state = (
            ":"
            if args.mail_state == "disabled"
            else (
                "if test \"$mail_was_enabled\" = enabled; then "
                "systemctl enable vapi-call-insights-mail.service; "
                "else systemctl disable vapi-call-insights-mail.service; fi; "
                "if test \"$mail_was_active\" = active; then "
                "systemctl restart vapi-call-insights-mail.service; fi"
            )
        )
        mail_health_probe = (
            "{ mail_healthy=false; "
            "for attempt in $(seq 1 30); do "
            "if systemctl is-active --quiet "
            "vapi-call-insights-mail.service && "
            "curl --fail --max-time 2 -sS -o /dev/null "
            "http://127.0.0.1:3210/health; then "
            "mail_healthy=true; break; fi; sleep 1; done; "
            "test \"$mail_healthy\" = true; }"
        )
        mail_health_check = {
            "disabled": ":",
            "enabled": mail_health_probe,
            "unchanged": (
                "if test \"$mail_was_active\" = active; then "
                + mail_health_probe + "; fi"
            ),
        }[args.mail_state]
        api_health_probe = (
            "{ api_healthy=false; "
            "for attempt in $(seq 1 30); do "
            "if systemctl is-active --quiet "
            "vapi-call-insights.service && "
            "curl --fail --max-time 2 -sS -o /dev/null "
            "http://127.0.0.1:3210/livez; then "
            "api_healthy=true; break; fi; sleep 1; done; "
            "test \"$api_healthy\" = true; }"
        )
        install_units = " ".join(
            (
                "vapi-call-insights.service",
                "vapi-call-insights-mail.service",
                "vapi-call-insights-backup.service",
                "vapi-call-insights-backup.timer",
                "vapi-call-insights-retention.service",
                "vapi-call-insights-retention.timer",
            )
        )
        activation_steps = [
            f"ln -sfn {REMOTE_RELEASES}/{release} {REMOTE_ROOT}/current.next",
            f"mv -Tf {REMOTE_ROOT}/current.next {REMOTE_ROOT}/current",
            f"for unit in {install_units}; do install -m 0644 "
            f"{REMOTE_ROOT}/current/deploy/$unit /etc/systemd/system/ "
            "|| exit 1; done",
            f"install -m 0644 {REMOTE_ROOT}/current/deploy/"
            "logrotate-vapi-call-insights /etc/logrotate.d/vapi-call-insights",
            f"install -d -m 0750 -o root -g {SERVICE_USER} "
            "/etc/vapi-call-insights/profiles",
            "for profile in "
            f"{REMOTE_ROOT}/current/src/profiles/*.json; do "
            "dest=/etc/vapi-call-insights/profiles/"
            "$(basename \"$profile\"); "
            "if test ! -e \"$dest\"; then "
            f"install -m 0640 -o root -g {SERVICE_USER} "
            "\"$profile\" \"$dest\"; fi; done",
            "for envfile in api.env mail.env; do "
            "if test -f /etc/vapi-call-insights/$envfile && "
            "! grep -q '^PROFILES_DIRECTORY=' "
            "/etc/vapi-call-insights/$envfile; then "
            "printf '%s\\n' "
            "'PROFILES_DIRECTORY=/etc/vapi-call-insights/profiles' "
            ">> /etc/vapi-call-insights/$envfile; fi; done",
            "systemctl daemon-reload",
            "systemctl enable vapi-call-insights.service",
            "systemctl restart vapi-call-insights.service",
            api_health_probe,
            "systemctl enable --now vapi-call-insights-backup.timer "
            "vapi-call-insights-retention.timer",
            mail_post_activation,
            mail_health_check,
        ]
        rollback_steps = (
            "if test -n \"$previous_release\" && "
            "test -d \"$previous_release\"; then "
            f"ln -sfn \"$previous_release\" {REMOTE_ROOT}/current.next && "
            f"mv -Tf {REMOTE_ROOT}/current.next {REMOTE_ROOT}/current; "
            f"for unit in {install_units}; do "
            "if test -f \"$previous_release/deploy/$unit\"; then "
            "install -m 0644 \"$previous_release/deploy/$unit\" "
            "/etc/systemd/system/; fi; done; "
            "systemctl daemon-reload; "
            "systemctl restart vapi-call-insights.service || true; "
            + restore_mail_state + "; "
            "else systemctl disable --now "
            "vapi-call-insights-backup.timer "
            "vapi-call-insights-retention.timer || true; "
            "systemctl stop vapi-call-insights.service || true; "
            f"rm -f {REMOTE_ROOT}/current {REMOTE_ROOT}/current.next "
            "/etc/systemd/system/vapi-call-insights.service "
            "/etc/systemd/system/vapi-call-insights-mail.service "
            "/etc/systemd/system/vapi-call-insights-backup.service "
            "/etc/systemd/system/vapi-call-insights-backup.timer "
            "/etc/systemd/system/vapi-call-insights-retention.service "
            "/etc/systemd/system/vapi-call-insights-retention.timer "
            "/etc/logrotate.d/vapi-call-insights; "
            "systemctl daemon-reload; fi"
        )
        activate_or_rollback = (
            "if ! (" + " && ".join(activation_steps) + "); then "
            + rollback_steps + "; exit 1; fi"
        )
        remote_commands = [
            "test -x /usr/bin/node && test -x /usr/bin/npm "
            "&& test -x /usr/bin/sqlite3",
            "test \"$(/usr/bin/node -p "
            "'process.versions.node.split(`.`)[0]')\" = 24",
            f"(getent group {SERVICE_USER} >/dev/null || "
            f"groupadd --system {SERVICE_USER})",
            f"(id -u {SERVICE_USER} >/dev/null 2>&1 || "
            f"useradd --system --home /var/lib/vapi-call-insights "
            f"--gid {SERVICE_USER} --shell /usr/sbin/nologin {SERVICE_USER})",
            f"usermod --gid {SERVICE_USER} {SERVICE_USER}",
            f"(id -u {MAIL_SERVICE_USER} >/dev/null 2>&1 || "
            f"useradd --system --no-create-home --home /nonexistent "
            f"--gid {SERVICE_USER} --shell /usr/sbin/nologin "
            f"{MAIL_SERVICE_USER})",
            f"usermod --gid {SERVICE_USER} {MAIL_SERVICE_USER}",
            "mail_unit_state=$(systemctl list-unit-files --no-legend "
            "--no-pager vapi-call-insights-mail.service)",
            "mail_was_enabled=$(systemctl is-enabled "
            "vapi-call-insights-mail.service 2>/dev/null || true)",
            "mail_was_active=$(systemctl is-active "
            "vapi-call-insights-mail.service 2>/dev/null || true)",
            mail_pre_activation,
            f"install -d -m 0755 {REMOTE_RELEASES}",
            f"install -d -m 0770 -o {SERVICE_USER} -g {SERVICE_USER} "
            "/var/lib/vapi-call-insights /var/log/vapi-call-insights",
            f"chgrp -R {SERVICE_USER} "
            "/var/lib/vapi-call-insights /var/log/vapi-call-insights",
            "chmod -R g+rwX,o-rwx "
            "/var/lib/vapi-call-insights /var/log/vapi-call-insights",
            "install -d -m 0700 -o root -g root "
            "/var/backups/vapi-call-insights",
            "install -d -m 0711 -o root -g root /etc/vapi-call-insights",
            f"tar -xzf {shlex.quote(remote_archive)} -C {REMOTE_RELEASES}",
            f"cd {REMOTE_RELEASES}/{release} && /usr/bin/npm ci",
            f"if test -L {REMOTE_ROOT}/current; then "
            f"previous_release=$(readlink -f {REMOTE_ROOT}/current || true); "
            "else previous_release=; fi",
            activate_or_rollback,
            f"rm -f {shlex.quote(remote_archive)}",
        ]
        run(ssh + [" && ".join(remote_commands)], args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
