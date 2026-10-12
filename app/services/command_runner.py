import subprocess


class CommandRunner:
    @staticmethod
    def run(command: str, timeout: int = 15) -> str:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                timeout=timeout
            )

            stdout = CommandRunner._decode(result.stdout)
            stderr = CommandRunner._decode(result.stderr)

            output = stdout.strip()

            if stderr.strip():
                output += "\n" + stderr.strip()

            return output

        except subprocess.TimeoutExpired:
            return "ERROR: Command timed out."

        except Exception as exc:
            return f"ERROR: {exc}"

    @staticmethod
    def _decode(data: bytes) -> str:
        for encoding in ("utf-8", "cp857", "cp1254", "cp850"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

        return data.decode("utf-8", errors="replace")