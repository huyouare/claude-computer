import asyncio
import base64
import os
import subprocess
from pathlib import Path
from uuid import uuid4
from enum import StrEnum
from typing import TypedDict
import logging
import shutil
from PIL import Image

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
    _scaling_factor: float = 1.0
    _log_dir: Path

    def setup_logging(self):
        self._log_dir = Path('logs') / str(uuid4())
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / 'computer_tool.log'
        logging.basicConfig(filename=str(log_file), level=logging.INFO,
                            format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    def log_info(self, message):
        logging.info(message)

    @property
    def options(self) -> ComputerToolOptions:
        self.log_info(f"ComputerTool options: {self.width}, {self.height}, {self.display_num}")
        # width, height = self.scale_coordinates(
        #     ScalingSource.COMPUTER, self.width, self.height
        # )
        # self.log_info(f"Scaled options: {width}, {height}")
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
            "display_number": self.display_num,
        }

    def __init__(self):
        super().__init__()
        self.setup_logging()
        self.width, self.height = pyautogui.size()
        self._detect_retina_display()
        self.log_info(f"Initialized ComputerTool with screen size: {self.width}x{self.height}, scaling factor: {self._scaling_factor}")

    @property
    def options(self) -> ComputerToolOptions:
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
            "display_number": None,
        }

    async def __call__(self, *, action: str, text: str | None = None, coordinate: tuple[int, int] | None = None, **kwargs):
        if action in ("mouse_move", "left_click_drag"):
            self.log_info(f"Mouse move or drag to {coordinate}")
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            x, y = self._scale_coordinates(*coordinate)
            self.log_info(f"Scaled coordinates: {x}, {y}")
            if action == "mouse_move":
                pyautogui.moveTo(x, y)
            elif action == "left_click_drag":
                pyautogui.dragTo(x, y)
        elif action in ("key", "type"):
            self.log_info(f"Key or type: {text}")
            if text is None:
                raise ToolError(f"text is required for {action}")
            if action == "key":
                # Handle Mac-specific key combinations
                if text.lower().startswith("ctrl+"):
                    text = "command+" + text[5:]
                pyautogui.hotkey(*text.split('+'))
            elif action == "type":
                pyautogui.write(text)
        elif action in ("left_click", "right_click", "double_click", "middle_click"):
            self.log_info(f"Click: {action}")
            pyautogui.click(button=action.split('_')[0], clicks=2 if action == "double_click" else 1)
        elif action == "screenshot":
            self.log_info(f"Screenshot")
            return await self.screenshot()
        elif action == "cursor_position":
            self.log_info(f"Cursor position")
            x, y = pyautogui.position()
            self.log_info(f"Scaled cursor position: {x // self._scaling_factor}, {y // self._scaling_factor}")
            return ToolResult(output=f"X={x // self._scaling_factor},Y={y // self._scaling_factor}")
        else:
            raise ToolError(f"Invalid action: {action}")

        return await self.screenshot()

    def _scale_coordinates(self, x: int, y: int) -> tuple[int, int]:
        return int(x * self._scaling_factor), int(y * self._scaling_factor)

    async def screenshot(self):
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"
        
        # Create logs directory with named subdirectory for screenshots
        logs_dir = self._log_dir / "screenshots"
        logs_dir.mkdir(parents=True, exist_ok=True)
        logs_path = logs_dir / f"screenshot_{uuid4().hex}.png"
        
        subprocess.run(["screencapture", "-x", "-C", str(path)])

        if path.exists():
            # Downscale Retina image if necessary
            self.downscale_retina_image(path)
            
            # Downsize image if it's too large
            self.downsize_image(path)

            # Get screenshot dimensions
            with Image.open(path) as img:
                width, height = img.size
                dpi = img.info.get('dpi', (72, 72))

            # Log screenshot dimensions
            self.log_info(f"Screenshot dimensions: {width}x{height}, DPI: {dpi}")
            
            # Save a copy to the logs directory
            shutil.copy(path, logs_path)
            
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

    def downsize_image(self, image_path: Path, target_width: int = 1280, target_height: int = 720):
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            
            # Check if downsizing is necessary
            if original_width <= target_width and original_height <= target_height:
                return

            # Calculate aspect ratio
            aspect_ratio = original_width / original_height
            target_ratio = target_width / target_height

            if aspect_ratio > target_ratio:
                new_width = target_width
                new_height = int(target_width / aspect_ratio)
            else:
                new_height = target_height
                new_width = int(target_height * aspect_ratio)

            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            resized_img.save(image_path)

    def is_retina_image(self, image_path: Path) -> bool:
        with Image.open(image_path) as img:
            dpi = img.info.get('dpi', (72, 72))
            return dpi[0] > 72 or dpi[1] > 72

    def downscale_retina_image(self, image_path: Path):
        if self.is_retina_image(image_path):
            with Image.open(image_path) as img:
                width, height = img.size
                new_size = (width // 2, height // 2)
                resized_img = img.resize(new_size, Image.LANCZOS)
                resized_img.save(image_path, dpi=(72, 72))

    def _detect_retina_display(self):
        # This is a simple heuristic and might need adjustment
        if self.width > 2000 or self.height > 1500:
            self._scaling_factor = 2.0
            self.width //= 2
            self.height //= 2
        else:
            self._scaling_factor = 1.0

