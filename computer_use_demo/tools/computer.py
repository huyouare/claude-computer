import asyncio
import base64
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pyautogui

from .base import BaseAnthropicTool, ComputerToolOptions, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"

class ComputerTool(BaseAnthropicTool):
    name = "computer"
    api_type = "computer_20241022"

    def __init__(self):
        super().__init__()
        self.width, self.height = pyautogui.size()

    @property
    def options(self) -> ComputerToolOptions:
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
            "display_number": None,
        }

    async def __call__(self, *, action: str, text: str | None = None, coordinate: tuple[int, int] | None = None, **kwargs):
        if action in ("mouse_move", "left_click_drag"):
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            x, y = coordinate
            if action == "mouse_move":
                pyautogui.moveTo(x, y)
            elif action == "left_click_drag":
                pyautogui.dragTo(x, y)
        elif action in ("key", "type"):
            if text is None:
                raise ToolError(f"text is required for {action}")
            if action == "key":
                pyautogui.press(text)
            elif action == "type":
                pyautogui.write(text)
        elif action in ("left_click", "right_click", "double_click", "middle_click"):
            pyautogui.click(button=action.split('_')[0], clicks=2 if action == "double_click" else 1)
        elif action == "screenshot":
            return await self.screenshot()
        elif action == "cursor_position":
            x, y = pyautogui.position()
            return ToolResult(output=f"X={x},Y={y}")
        else:
            raise ToolError(f"Invalid action: {action}")

        return await self.screenshot()

    async def screenshot(self):
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"
        
        subprocess.run(["screencapture", "-x", "-C", str(path)])

        if path.exists():
            return ToolResult(base64_image=base64.b64encode(path.read_bytes()).decode())
        raise ToolError("Failed to take screenshot")

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        _, stdout, stderr = await run(command)
        base64_image = None

        if take_screenshot:
            await asyncio.sleep(0.5)
            base64_image = (await self.screenshot()).base64_image

        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)
