import asyncio
import base64
import os
import subprocess
from pathlib import Path
from uuid import uuid4
from enum import StrEnum
from typing import TypedDict


import pyautogui

from .base import BaseAnthropicTool, ComputerToolOptions, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"

class Resolution(TypedDict):
    width: int
    height: int


# sizes above XGA/WXGA are not recommended (see README.md)
# scale down to one of these targets if ComputerTool._scaling_enabled is set
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),  # 4:3
    "WXGA": Resolution(width=1280, height=800),  # 16:10
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9
}


class ScalingSource(StrEnum):
    COMPUTER = "computer"
    API = "api"

class ComputerTool(BaseAnthropicTool):
    """
    A tool that allows the agent to interact with the screen, keyboard, and mouse of the current computer.
    The tool parameters are defined by Anthropic and are not editable.
    """

    name = "computer"
    api_type = "computer_20241022"
    width: int
    height: int
    display_num: int | None

    _screenshot_delay = 2.0
    _scaling_enabled = True

    @property
    def options(self) -> ComputerToolOptions:
        width, height = self.scale_coordinates(
            ScalingSource.COMPUTER, self.width, self.height
        )
        return {
            "display_width_px": width,
            "display_height_px": height,
            "display_number": self.display_num,
        }

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
    
    def scale_coordinates(self, source: ScalingSource, x: int, y: int):
        """Scale coordinates to a target maximum resolution."""
        if not self._scaling_enabled:
            return x, y
        ratio = self.width / self.height
        target_dimension = None
        for dimension in MAX_SCALING_TARGETS.values():
            # allow some error in the aspect ratio - not ratios are exactly 16:9
            if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
                if dimension["width"] < self.width:
                    target_dimension = dimension
                break
        if target_dimension is None:
            return x, y
        # should be less than 1
        x_scaling_factor = target_dimension["width"] / self.width
        y_scaling_factor = target_dimension["height"] / self.height
        if source == ScalingSource.API:
            if x > self.width or y > self.height:
                raise ToolError(f"Coordinates {x}, {y} are out of bounds")
            # scale up
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
        # scale down
        return round(x * x_scaling_factor), round(y * y_scaling_factor)
