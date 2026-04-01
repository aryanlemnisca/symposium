"""ZIP export for session outputs."""

import io
import zipfile


def create_zip(outputs: dict[str, str], session_name: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in outputs.items():
            zf.writestr(f"{session_name}/{filename}", content)
    buffer.seek(0)
    return buffer.read()
