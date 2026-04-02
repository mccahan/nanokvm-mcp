"""FastAPI HTTP server for NanoKVM control."""

import asyncio
import base64
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .client import NanoKVMClient

logger = logging.getLogger(__name__)

# Global client instance
_client: Optional[NanoKVMClient] = None


def get_client() -> NanoKVMClient:
    """Get or create NanoKVM client from environment variables."""
    global _client
    if _client is None:
        host = os.environ.get("NANOKVM_HOST", "10.0.1.117")
        username = os.environ.get("NANOKVM_USERNAME", "admin")
        password = os.environ.get("NANOKVM_PASSWORD", "admin")
        screen_width = int(os.environ.get("NANOKVM_SCREEN_WIDTH", "1920"))
        screen_height = int(os.environ.get("NANOKVM_SCREEN_HEIGHT", "1080"))
        use_https = os.environ.get("NANOKVM_USE_HTTPS", "false").lower() == "true"
        
        _client = NanoKVMClient(
            host=host,
            username=username,
            password=password,
            screen_width=screen_width,
            screen_height=screen_height,
            use_https=use_https,
            verify_ssl=False,
        )
        logger.info(f"Created NanoKVM client for {host}")
    return _client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage client lifecycle."""
    yield
    global _client
    if _client:
        await _client.close()
        _client = None


app = FastAPI(
    title="NanoKVM API",
    description="HTTP API for controlling NanoKVM devices",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Request Models ---

class TypeTextRequest(BaseModel):
    text: str
    language: str = ""


class KeyRequest(BaseModel):
    key: str
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False


class MouseMoveRequest(BaseModel):
    x: int
    y: int


class MouseClickRequest(BaseModel):
    button: str = "left"
    x: Optional[int] = None
    y: Optional[int] = None


class ScrollRequest(BaseModel):
    delta: int


class PowerRequest(BaseModel):
    action: str = "power"
    duration: int = 800


class MountImageRequest(BaseModel):
    file: str
    cdrom: bool = True


# --- Health & Info ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/info")
async def get_info():
    """Get NanoKVM device information."""
    try:
        client = get_client()
        info = await client.get_info()
        return {"status": "ok", "data": info}
    except Exception as e:
        logger.exception("Failed to get info")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hdmi")
async def get_hdmi_status():
    """Get HDMI connection status."""
    try:
        client = get_client()
        status = await client.get_hdmi_status()
        return {"status": "ok", "data": status}
    except Exception as e:
        logger.exception("Failed to get HDMI status")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/resolution")
async def get_resolution():
    """Detect and return actual screen resolution from screenshot."""
    try:
        client = get_client()
        width, height = await client.detect_resolution()
        return {"status": "ok", "data": {"width": width, "height": height}}
    except Exception as e:
        logger.exception("Failed to detect resolution")
        raise HTTPException(status_code=500, detail=str(e))


# --- Screenshot ---

@app.get("/screenshot")
async def screenshot(
    format: str = "jpeg",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: int = 85,
):
    """
    Capture screenshot from NanoKVM.
    
    Args:
        format: Output format (jpeg or base64)
        max_width: Maximum width (resize if exceeded)
        max_height: Maximum height (resize if exceeded)
        quality: JPEG quality (1-100)
    """
    try:
        client = get_client()
        
        if format == "base64":
            b64 = await client.screenshot_base64(
                max_width=max_width,
                max_height=max_height,
                quality=quality,
            )
            return {"status": "ok", "data": b64, "content_type": "image/jpeg"}
        else:
            jpeg_data = await client.screenshot()
            return Response(content=jpeg_data, media_type="image/jpeg")
    except Exception as e:
        logger.exception("Failed to capture screenshot")
        raise HTTPException(status_code=500, detail=str(e))


# --- Keyboard ---

@app.post("/keyboard/type")
async def type_text(req: TypeTextRequest):
    """Type text using paste API (max 1024 chars)."""
    try:
        client = get_client()
        result = await client.paste_text(req.text, req.language)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to type text")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/keyboard/key")
async def send_key(req: KeyRequest):
    """Send a key press."""
    try:
        client = get_client()
        await client.send_key(
            req.key,
            ctrl=req.ctrl,
            shift=req.shift,
            alt=req.alt,
            meta=req.meta,
        )
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to send key")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/keyboard/text")
async def send_text_ws(req: TypeTextRequest):
    """Type text character by character via WebSocket."""
    try:
        client = get_client()
        await client.send_text_ws(req.text)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to send text")
        raise HTTPException(status_code=500, detail=str(e))


# --- Mouse ---

@app.post("/mouse/move")
async def mouse_move(req: MouseMoveRequest):
    """Move mouse to absolute position."""
    try:
        client = get_client()
        await client.mouse_move(req.x, req.y)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to move mouse")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mouse/click")
async def mouse_click(req: MouseClickRequest):
    """Click mouse button."""
    try:
        client = get_client()
        await client.mouse_click(req.button, req.x, req.y)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to click")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mouse/scroll")
async def mouse_scroll(req: ScrollRequest):
    """Scroll mouse wheel."""
    try:
        client = get_client()
        await client.mouse_scroll(req.delta)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Failed to scroll")
        raise HTTPException(status_code=500, detail=str(e))


# --- Power ---

@app.post("/power")
async def power_control(req: PowerRequest):
    """Control power button."""
    try:
        client = get_client()
        result = await client.power(req.action, req.duration)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to control power")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/power/short")
async def power_short():
    """Short press power button (800ms)."""
    try:
        client = get_client()
        result = await client.power_short()
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to short press power")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/power/long")
async def power_long():
    """Long press power button (5000ms) - force off."""
    try:
        client = get_client()
        result = await client.power_long()
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to long press power")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/power/led")
async def get_led_status():
    """Get power and HDD LED status."""
    try:
        client = get_client()
        status = await client.get_led_status()
        return {"status": "ok", "data": status}
    except Exception as e:
        logger.exception("Failed to get LED status")
        raise HTTPException(status_code=500, detail=str(e))


# --- HID ---

@app.post("/hid/reset")
async def reset_hid():
    """Reset HID devices."""
    try:
        client = get_client()
        result = await client.reset_hid()
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to reset HID")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hid/mode")
async def get_hid_mode():
    """Get current HID mode."""
    try:
        client = get_client()
        mode = await client.get_hid_mode()
        return {"status": "ok", "data": {"mode": mode}}
    except Exception as e:
        logger.exception("Failed to get HID mode")
        raise HTTPException(status_code=500, detail=str(e))


# --- Storage ---

@app.get("/storage/images")
async def list_images():
    """List available ISO images."""
    try:
        client = get_client()
        images = await client.list_images()
        return {"status": "ok", "data": images}
    except Exception as e:
        logger.exception("Failed to list images")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/storage/mounted")
async def get_mounted_image():
    """Get currently mounted image."""
    try:
        client = get_client()
        mounted = await client.get_mounted_image()
        return {"status": "ok", "data": mounted}
    except Exception as e:
        logger.exception("Failed to get mounted image")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/storage/mount")
async def mount_image(req: MountImageRequest):
    """Mount an ISO image."""
    try:
        client = get_client()
        result = await client.mount_image(req.file, req.cdrom)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to mount image")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/storage/unmount")
async def unmount_image():
    """Unmount currently mounted image."""
    try:
        client = get_client()
        result = await client.unmount_image()
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.exception("Failed to unmount image")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the API server."""
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
