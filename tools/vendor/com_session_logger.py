#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = REPO_ROOT / "LocalRuntime" / "Com"
DEFAULT_BAUD = 115200

SENSITIVE_PATTERN = re.compile(
    r'''(?ix)(?P<prefix>(?<!\w)(?P<quote>["']?)
    (?:ssid|passord|password|pass|mqtt_password|mqtt_pass|token|api_key|secret)
    (?P=quote)\s*[:=]\s*)
    (?P<value>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}]+)'''
)
SENSITIVE_COMMAND_PATTERN = re.compile(
    r"(?i)(\b(?:wpassword|wmqttpass|wserviceapsecret|wssid|wmqttlogin)\s*[:=]\s*)[^\r\n]*"
)
MAX_CAPTURE_LINE_CHARS = 65536
MAX_TCP_DISCARD_BYTES = 65536


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(dt: datetime | None = None) -> str:
    return (dt or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def display_time(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat(timespec="milliseconds")


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "port"


def redact_line_safe(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group("value")
        quote = value[0] if value[0] in "\"'" else ""
        return f"{match.group('prefix')}{quote}<redacted>{quote}"

    redacted = SENSITIVE_PATTERN.sub(replace, text)
    return SENSITIVE_COMMAND_PATTERN.sub(r"\1<redacted>", redacted)


def set_serial_control_lines(serial_port: Any, dtr: bool, rts: bool) -> None:
    try:
        serial_port.dtr = dtr
        serial_port.rts = rts
    except Exception:
        pass


def is_preferred_serial_port(device: str, description: str, hwid: str) -> bool:
    text = f"{device} {description} {hwid}".lower()
    if re.fullmatch(r"com\d+", device.strip(), re.IGNORECASE):
        return True
    preferred_markers = [
        "ttyusb",
        "ttyacm",
        "cu.usb",
        "usbserial",
        "usbmodem",
        "cp210",
        "ch340",
        "ch910",
        "ftdi",
        "silicon labs",
        "uart bridge",
        "esp32",
        "espressif",
    ]
    return any(marker in text for marker in preferred_markers)


def serial_candidates() -> list[dict[str, str]]:
    ports: list[dict[str, str]] = []
    if list_ports is not None:
        for port in list_ports.comports():
            device = str(port.device)
            description = str(port.description or "")
            hwid = str(port.hwid or "")
            ports.append(
                {
                    "device": device,
                    "description": description,
                    "hwid": hwid,
                    "preferred": "true" if is_preferred_serial_port(device, description, hwid) else "false",
                }
            )
        return sorted(ports, key=lambda item: (item["preferred"] != "true", item["device"]))

    patterns = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/tty.SLAB*",
        "/dev/tty.usbserial*",
        "/dev/tty.usbmodem*",
        "/dev/cu.SLAB*",
        "/dev/cu.usbserial*",
        "/dev/cu.usbmodem*",
    ]
    for pattern in patterns:
        for device in glob.glob(pattern):
            ports.append({"device": device, "description": "fallback glob", "hwid": "", "preferred": "true"})
    return sorted(ports, key=lambda item: item["device"])


def choose_port(requested: str) -> str:
    if requested.lower() != "auto":
        return requested
    ports = serial_candidates()
    preferred = [item for item in ports if item.get("preferred") == "true"]
    if not preferred:
        raise RuntimeError(
            "No likely USB controller serial port detected. Connect the controller USB or pass --port COMx explicitly."
        )
    return preferred[0]["device"]


def parse_tcp_target(value: str) -> tuple[str, int]:
    raw = value.strip()
    if raw.startswith("tcp://"):
        raw = raw[len("tcp://"):]
    if not raw or ":" not in raw:
        raise RuntimeError("TCP target must be host:port, for example --tcp 192.168.100.50:4001")
    host, port_text = raw.rsplit(":", 1)
    host = host.strip("[] ")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError(f"Invalid TCP port: {port_text}") from exc
    if not host or port < 1 or port > 65535:
        raise RuntimeError("TCP target must contain a valid host and port 1..65535")
    return host, port


class TcpSerialTransport:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def open(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=max(self.timeout, 1.0))
        try:
            self.sock.settimeout(self.timeout)
        except Exception:
            self.close()
            raise

    def read(self, size: int = 1) -> bytes:
        if self.sock is None:
            return b""
        try:
            data = self.sock.recv(max(1, size))
        except socket.timeout:
            return b""
        if not data:
            raise ConnectionError("TCP serial bridge closed the connection")
        return data

    def write(self, data: bytes) -> int:
        if self.sock is None:
            return 0
        self.sock.sendall(data)
        return len(data)

    def flush(self) -> None:
        return None

    def reset_input_buffer(self) -> None:
        if self.sock is None:
            return
        previous_timeout = self.sock.gettimeout()
        self.sock.settimeout(0.01)
        discarded = 0
        deadline = time.monotonic() + 1.0
        try:
            while discarded < MAX_TCP_DISCARD_BYTES and time.monotonic() < deadline:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        raise ConnectionError("TCP serial bridge closed the connection")
                    discarded += len(data)
                except socket.timeout:
                    return
            raise RuntimeError("TCP input drain limit reached; capture not started")
        finally:
            self.sock.settimeout(previous_timeout)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


def ensure_pyserial() -> None:
    if serial is None:
        raise RuntimeError(
            "pyserial is required for reading COM ports. Install it with: python -m pip install pyserial"
        )


def resolve_root(root: str) -> Path:
    path = Path(root)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def open_text(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8", newline="\n")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_session(root: Path, port: str, baud: int) -> dict[str, Path | str | int]:
    session_id = f"{utc_stamp()}_{safe_name(port)}_{baud}_{uuid.uuid4().hex}"
    session_dir = root / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=False)
    latest_path = root / "latest.log"
    latest_session_path = root / "latest-session.txt"
    latest_session_path.parent.mkdir(parents=True, exist_ok=True)
    latest_session_path.write_text(str(session_dir.relative_to(root)) + "\n", encoding="utf-8")
    latest_path.write_text("", encoding="utf-8")
    return {
        "session_id": session_id,
        "session_dir": session_dir,
        "log_path": session_dir / "serial.log",
        "manifest_path": session_dir / "manifest.json",
        "latest_path": latest_path,
        "latest_session_path": latest_session_path,
    }


def format_line(line: str, timestamps: bool, redact: bool, dual_time: bool = False) -> str:
    text = redact_line_safe(line) if redact else line
    if dual_time:
        device_time = "not_reported"
        for field in ("esp_us", "esp_ms", "uptime_ms", "at_us", "us", "at_ms"):
            match = re.search(r"\b" + field + r"=(\d+(?:\.\d+)?)(?=\s|$)", line)
            if match:
                device_time = field + ":" + match.group(1)
                break
        text = f"[esp_time={device_time}] {text}"
    if timestamps:
        return f"[{display_time()}] {text}"
    return text


def print_ports(as_json: bool) -> int:
    ports = serial_candidates()
    if as_json:
        print(json.dumps({"ports": ports}, ensure_ascii=False, indent=2))
        return 0
    if not ports:
        print("No serial ports detected.")
        return 0
    for item in ports:
        detail = item["description"] or item["hwid"]
        suffix = f" - {detail}" if detail else ""
        marker = "*" if item.get("preferred") == "true" else " "
        print(f"{marker} {item['device']}{suffix}")
    return 0


def write_log_line(files: list[Any], line: str, *, quiet: bool) -> None:
    for handle in files:
        handle.write(line + "\n")
        handle.flush()
    if not quiet:
        print(line, flush=True)


def run_logger(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    tcp_target = (args.tcp or "").strip()
    if tcp_target:
        tcp_host, tcp_port = parse_tcp_target(tcp_target)
        port = f"tcp://{tcp_host}:{tcp_port}"
        transport = "tcp"
    else:
        tcp_host = ""
        tcp_port = 0
        port = choose_port(args.port)
        transport = "serial"
    session = create_session(root, port, args.baud)
    started = utc_now()
    manifest = {
        "session_id": session["session_id"],
        "started_at_utc": started.isoformat(),
        "started_at_local": started.astimezone().isoformat(timespec="milliseconds"),
        "timestamp_semantics": "host receive time; device clocks remain separate",
        "read_during_send_delay": bool(args.read_during_send_delay),
        "ended_at_utc": None,
        "port": port,
        "baud": args.baud,
        "transport": transport,
        "root": str(root),
        "session_dir": str(session["session_dir"]),
        "log_path": str(session["log_path"]),
        "latest_path": str(session["latest_path"]),
        "redact": bool(args.redact),
        "timestamps": bool(args.timestamps),
        "dual_time": bool(args.dual_time),
        "commands_planned": [redact_line_safe(command) if args.redact else command for command in args.send or []],
        "commands_sent": [],
        "command_events": [],
        "dry_run": bool(args.dry_run),
        "pyserial": getattr(serial, "VERSION", None) if serial is not None else None,
        "status": "running",
    }
    write_json(session["manifest_path"], manifest)

    if args.dry_run:
        manifest["status"] = "dry_run"
        manifest["ended_at_utc"] = utc_now().isoformat()
        write_json(session["manifest_path"], manifest)
        print(f"Dry run OK. Session dir: {session['session_dir']}")
        return 0

    header = [
        f"# COM session {session['session_id']}",
        f"# port={port} baud={args.baud} started_at_utc={started.isoformat()}",
        f"# transport={transport}",
        f"# started_at_local={started.astimezone().isoformat(timespec='milliseconds')} timestamp_clock=host_utc_receive",
        f"# session_log={session['log_path']}",
        f"# latest_log={session['latest_path']}",
    ]

    serial_port = None
    files = []
    try:
        if transport == "serial":
            ensure_pyserial()
        files.append(open_text(session["log_path"]))
        files.append(open_text(session["latest_path"]))
        for item in header:
            write_log_line(files, item, quiet=args.quiet)

        if transport == "tcp":
            serial_port = TcpSerialTransport(tcp_host, tcp_port, args.timeout)
            serial_port.open()
        else:
            serial_port = serial.Serial()
            serial_port.port = port
            serial_port.baudrate = args.baud
            serial_port.timeout = args.timeout
            serial_port.write_timeout = 2
            serial_port.bytesize = 8
            serial_port.parity = "N"
            serial_port.stopbits = 1
            serial_port.xonxoff = False
            serial_port.rtscts = False
            serial_port.dsrdtr = False
            if hasattr(serial_port, "exclusive"):
                serial_port.exclusive = args.exclusive
            set_serial_control_lines(serial_port, args.dtr, args.rts)
            serial_port.open()
            set_serial_control_lines(serial_port, args.dtr, args.rts)
        time.sleep(args.startup_wait)
        serial_port.reset_input_buffer()

        buffer = ""

        def read_and_log():
            nonlocal buffer
            data = serial_port.read(args.chunk_size)
            if not data:
                return
            buffer += data.decode(args.encoding, errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if len(line) > MAX_CAPTURE_LINE_CHARS:
                    raise RuntimeError("Serial capture line limit reached")
                write_log_line(files, format_line(line.rstrip("\r"), args.timestamps, args.redact, args.dual_time), quiet=args.quiet)
            if len(buffer) > MAX_CAPTURE_LINE_CHARS:
                raise RuntimeError("Serial capture line limit reached")

        for command in args.send or []:
            payload = (command.rstrip("\r\n") + "\r\n").encode(args.encoding, errors="replace")
            write_started = utc_now()
            written = serial_port.write(payload)
            if written != len(payload):
                raise RuntimeError(f"Incomplete command write: {written}/{len(payload)} bytes; command outcome unknown")
            manifest["commands_sent"].append(redact_line_safe(command) if args.redact else command)
            write_finished = utc_now()
            manifest["command_events"].append({
                "command": redact_line_safe(command) if args.redact else command,
                "write_started_at_utc": write_started.isoformat(timespec="milliseconds"),
                "write_finished_at_utc": write_finished.isoformat(timespec="milliseconds"),
                "write_finished_at_local": write_finished.astimezone().isoformat(timespec="milliseconds"),
                "outcome": "full_write_device_execution_unverified",
            })
            serial_port.flush()
            write_log_line(files, format_line(f">>> {command}", args.timestamps, args.redact, args.dual_time), quiet=args.quiet)
            if args.read_during_send_delay:
                delay_deadline = time.monotonic() + args.send_delay
                while time.monotonic() < delay_deadline:
                    read_and_log()
            else:
                time.sleep(args.send_delay)

        deadline = time.monotonic() + args.duration if args.duration > 0 else None
        while deadline is None or time.monotonic() < deadline:
            read_and_log()

        if buffer:
            write_log_line(files, format_line(buffer.rstrip("\r"), args.timestamps, args.redact, args.dual_time), quiet=args.quiet)
        manifest["status"] = "completed"
        return 0
    except KeyboardInterrupt:
        write_log_line(files, "# stopped_by=keyboard_interrupt", quiet=args.quiet)
        manifest["status"] = "stopped"
        return 130
    except Exception as exc:
        message = str(exc)
        if transport == "tcp" and ("timed out" in message.lower() or "connection refused" in message.lower()):
            message = (
                f"TCP target {port} is unavailable. Check the remote serial-over-TCP bridge "
                f"and firewall. Original error: {exc}"
            )
        elif "PermissionError" in message or "Access is denied" in message or "could not open port" in message:
            message = (
                f"Serial port {port} is busy or unavailable. Close VS Code Serial Monitor, "
                f"Arduino monitor, PuTTY, or another logger, then retry. Original error: {exc}"
            )
        message = redact_line_safe(message) if args.redact else message
        manifest["status"] = "error"
        manifest["error"] = message
        try:
            write_log_line(files, f"# error={message}", quiet=args.quiet)
        except OSError:
            pass
        print(message, file=sys.stderr)
        return 2
    finally:
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                pass
        ended = utc_now()
        manifest["ended_at_utc"] = ended.isoformat()
        manifest["ended_at_local"] = ended.astimezone().isoformat(timespec="milliseconds")
        try:
            write_json(session["manifest_path"], manifest)
        finally:
            for handle in files:
                try:
                    handle.close()
                except Exception:
                    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Log a local USB Serial/COM port or remote raw serial-over-TCP endpoint into session files."
    )
    parser.add_argument("--list", action="store_true", help="List detected serial ports and exit.")
    parser.add_argument("--list-json", action="store_true", help="List detected serial ports as JSON and exit.")
    parser.add_argument("--port", default="auto", help="COM port, /dev/tty device, or auto. Default: auto.")
    parser.add_argument("--tcp", default="", help="Remote raw serial-over-TCP target as host:port or tcp://host:port.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"Baud rate. Default: {DEFAULT_BAUD}.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT.relative_to(REPO_ROOT)), help="Log root. Default: LocalRuntime/Com.")
    parser.add_argument("--duration", type=float, default=0, help="Seconds to run. 0 means until Ctrl+C.")
    parser.add_argument("--timeout", type=float, default=0.2, help="Serial read timeout in seconds.")
    parser.add_argument("--chunk-size", type=int, default=512, help="Serial read chunk size.")
    parser.add_argument("--encoding", default="utf-8", help="Serial text encoding.")
    parser.add_argument("--startup-wait", type=float, default=0.8, help="Seconds to wait after opening port.")
    parser.add_argument("--send", action="append", default=[], help="Command to send after opening the port. Repeatable.")
    parser.add_argument("--send-delay", type=float, default=0.5, help="Seconds between --send commands.")
    parser.add_argument("--read-during-send-delay", action="store_true", help="Read and timestamp incoming lines between commands instead of buffering them during send-delay.")
    parser.add_argument("--dual-time", action="store_true", help="Also label the device time present in each line; absent device times are marked not_reported.")
    parser.add_argument("--timestamps", action=argparse.BooleanOptionalAction, default=True, help="Prefix received lines with host UTC timestamps to milliseconds.")
    parser.add_argument("--redact", action=argparse.BooleanOptionalAction, default=True, help="Redact common secrets in logs.")
    parser.add_argument("--exclusive", action=argparse.BooleanOptionalAction, default=True, help="Use pyserial exclusive mode where supported, to catch busy Linux ports.")
    parser.add_argument("--dtr", action=argparse.BooleanOptionalAction, default=False, help="Drive DTR active after opening the serial port. Default keeps DTR inactive to reduce ESP32 auto-reset risk.")
    parser.add_argument("--rts", action=argparse.BooleanOptionalAction, default=False, help="Drive RTS active after opening the serial port. Default keeps RTS inactive to reduce ESP32 auto-reset risk.")
    parser.add_argument("--quiet", action="store_true", help="Do not mirror lines to stdout.")
    parser.add_argument("--dry-run", action="store_true", help="Create session metadata without opening the serial port.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for name in ("duration", "timeout", "startup_wait", "send_delay"):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 0:
            parser.error(f"--{name.replace('_', '-')} must be finite and nonnegative")
    if args.chunk_size <= 0 or args.baud <= 0:
        parser.error("--chunk-size and --baud must be positive")
    try:
        if args.list or args.list_json:
            return print_ports(args.list_json)
        return run_logger(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
