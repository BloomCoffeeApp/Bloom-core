"""Frameless desktop window: the web UI draws its own title bar and calls this API.

Dragging is handed to Windows itself (WM_NCLBUTTONDOWN + HTCAPTION), so it feels native.
Windows only runs its own resize loop for windows with a thick frame, so resizing from the
edges is done here: follow the cursor while the button is held, respecting the minimum size.
Exposed to JS as `window.pywebview.api.*`; underscored members are not exposed.
"""

import ctypes
import json
import logging
import sys
import time
from pathlib import Path

log = logging.getLogger("cafeteria.window")

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    from ctypes import wintypes

    # Private loader instances: setting argtypes here must not affect pywebview's windll.
    user32 = ctypes.WinDLL("user32")
    dwmapi = ctypes.WinDLL("dwmapi")
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
    ]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


WM_NCLBUTTONDOWN = 0xA1
GWL_STYLE = -16
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
VK_LBUTTON = 0x01
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
RESIZE_EDGES = {"left", "right", "top", "bottom", "topleft", "topright", "bottomleft", "bottomright"}

HTCAPTION = 2


class WindowApi:
    def __init__(self, state_path: Path, min_size: tuple[int, int]) -> None:
        self._min_size = min_size
        self._window = None
        self._hwnd = 0
        self._state_path = state_path
        self._fullscreen = False
        self._fs_was_maximized = False

    # ---------------------------------------------------------------- setup (Python side)

    def _attach(self, window) -> None:
        self._window = window
        window.events.shown += self._on_shown
        window.events.closing += self._save_state

    def _form(self):
        from webview.platforms.winforms import BrowserView

        return BrowserView.instances.get(self._window.uid)

    def _ui(self, fn) -> None:
        """Runs `fn` on the WinForms UI thread (JS API calls arrive on worker threads)."""
        from System import Func, Type

        form = self._form()
        if form is not None:
            form.Invoke(Func[Type](fn))

    def _fit_maximized_bounds(self, form) -> None:
        if self._fullscreen:  # full screen covers the whole monitor, taskbar included
            return
        # A borderless form maximizes over the taskbar unless told the work area.
        # MaximizedBounds is relative to the monitor the window is on.
        from System.Drawing import Rectangle
        from System.Windows.Forms import Screen

        screen = Screen.FromHandle(form.Handle)
        wa, b = screen.WorkingArea, screen.Bounds
        form.MaximizedBounds = Rectangle(wa.X - b.X, wa.Y - b.Y, wa.Width, wa.Height)

    def _on_shown(self) -> None:
        if not IS_WINDOWS:
            return
        from System.Windows.Forms import FormWindowState

        def setup():
            form = self._form()
            self._hwnd = form.Handle.ToInt64()
            # Lets the taskbar button minimize/restore it and keeps Win+↑/↓ working.
            style = user32.GetWindowLongW(self._hwnd, GWL_STYLE)
            user32.SetWindowLongW(self._hwnd, GWL_STYLE, style | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            pref = ctypes.c_int(DWMWCP_ROUND)  # Windows 11 rounded corners; ignored on 10
            dwmapi.DwmSetWindowAttribute(self._hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), 4)
            # Restore the last rect first so un-maximizing later returns to it.
            rect = self._saved_rect()
            if rect:
                user32.SetWindowPos(self._hwnd, None, *rect, SWP_NOZORDER | SWP_NOACTIVATE)
            self._fit_maximized_bounds(form)
            if self._load_state().get("maximized"):
                form.WindowState = FormWindowState.Maximized
            form.Move += lambda *_: self._fit_maximized_bounds(form)

        try:
            self._ui(setup)
        except Exception:
            log.exception("Could not set up the frameless window")

    # ---------------------------------------------------------------- persisted size

    def _load_state(self) -> dict:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self) -> None:
        """Stores the window rect in physical pixels (exact regardless of DPI scaling)."""
        try:
            state = self._load_state()
            state["maximized"] = self.is_maximized() and not self._fullscreen or (self._fullscreen and self._fs_was_maximized)
            if not state["maximized"] and self._hwnd and not self._fullscreen:
                r = wintypes.RECT()
                user32.GetWindowRect(self._hwnd, ctypes.byref(r))
                state.update(x=r.left, y=r.top, width=r.right - r.left, height=r.bottom - r.top)
            self._state_path.write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            log.exception("Could not save the window state")

    def _saved_rect(self) -> tuple[int, int, int, int] | None:
        """The last window rect, if it still fits on a connected screen."""
        s = self._load_state()
        if not all(isinstance(s.get(k), int) for k in ("x", "y", "width", "height")):
            return None
        from System.Drawing import Rectangle
        from System.Windows.Forms import Screen

        # Needs a visible strip of the title bar on some screen to be reachable.
        grab = Rectangle(s["x"] + 40, s["y"], max(s["width"] - 80, 1), 30)
        if not any(sc.WorkingArea.IntersectsWith(grab) for sc in Screen.AllScreens):
            return None
        return s["x"], s["y"], s["width"], s["height"]

    def _initial_geometry(self, default_w: int, default_h: int) -> dict:
        # Position and maximized state are applied on show (physical pixels, see _on_shown).
        return {"width": default_w, "height": default_h}

    # ---------------------------------------------------------------- JS API

    def is_desktop(self) -> bool:
        return True

    def minimize(self) -> None:
        self._window.minimize()

    def is_maximized(self) -> bool:
        return bool(IS_WINDOWS and self._hwnd and user32.IsZoomed(self._hwnd))

    def toggle_maximize(self) -> bool:
        from System.Windows.Forms import FormWindowState

        def toggle():
            form = self._form()
            if form.WindowState == FormWindowState.Maximized:
                form.WindowState = FormWindowState.Normal
            else:
                self._fit_maximized_bounds(form)
                form.WindowState = FormWindowState.Maximized

        self._ui(toggle)
        return self.is_maximized()

    def is_fullscreen(self) -> bool:
        return self._fullscreen

    def toggle_fullscreen(self) -> bool:
        """Real full screen of the native window: covers the whole monitor (taskbar included) and Esc / the
        button leave it. pywebview's own `toggle_fullscreen` is undone by our `Move` handler that keeps the
        maximized bounds on the work area, and the page's `requestFullscreen()` does nothing inside the window."""
        if not IS_WINDOWS:
            return False
        from System.Drawing import Rectangle
        from System.Windows.Forms import FormWindowState, Screen

        def toggle():
            form = self._form()
            if not self._fullscreen:
                self._fs_was_maximized = form.WindowState == FormWindowState.Maximized
                self._fullscreen = True
                b = Screen.FromHandle(form.Handle).Bounds
                form.MaximizedBounds = Rectangle(0, 0, b.Width, b.Height)  # relative to the monitor
                if form.WindowState == FormWindowState.Maximized:
                    form.WindowState = FormWindowState.Normal  # so Windows recomputes the maximized rect
                form.WindowState = FormWindowState.Maximized
            else:
                self._fullscreen = False
                self._fit_maximized_bounds(form)
                form.WindowState = FormWindowState.Normal
                if self._fs_was_maximized:
                    form.WindowState = FormWindowState.Maximized

        self._ui(toggle)
        return self._fullscreen

    def close(self) -> None:
        self._window.destroy()

    def start_drag(self) -> None:
        """Called on mousedown in the title bar; Windows takes over until mouseup."""
        if not IS_WINDOWS:
            return
        from System.Drawing import Point
        from System.Windows.Forms import FormWindowState

        if self.is_maximized() and not self._moved_while_pressed():
            return  # a plain click (or the first half of a double-click) on a maximized window

        def drag():
            form = self._form()
            hwnd = form.Handle.ToInt64()
            if form.WindowState == FormWindowState.Maximized:
                # Like a native window: un-maximize under the cursor, keeping the
                # grab point at the same relative spot of the title bar.
                pt = _POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                ratio = (pt.x - form.Left) / max(form.Width, 1)
                form.WindowState = FormWindowState.Normal
                form.Location = Point(int(pt.x - form.Width * ratio), max(pt.y - 18, 0))
            user32.ReleaseCapture()
            user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)

        self._ui(drag)

    def _moved_while_pressed(self, threshold: int = 4) -> bool:
        """Waits (off the UI thread) until the cursor moves or the button is released."""
        start, pt = _POINT(), _POINT()
        user32.GetCursorPos(ctypes.byref(start))
        while user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
            user32.GetCursorPos(ctypes.byref(pt))
            if abs(pt.x - start.x) > threshold or abs(pt.y - start.y) > threshold:
                return True
            time.sleep(1 / 120)
        return False

    def start_resize(self, edge: str) -> None:
        """Called on mousedown on a window edge; resizes until the button is released."""
        hwnd = self._hwnd
        if not IS_WINDOWS or edge not in RESIZE_EDGES or not hwnd or user32.IsZoomed(hwnd):
            return
        start, rect = _POINT(), wintypes.RECT()
        user32.GetCursorPos(ctypes.byref(start))
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        scale = (user32.GetDpiForWindow(hwnd) or 96) / 96
        min_w, min_h = int(self._min_size[0] * scale), int(self._min_size[1] * scale)
        pt = _POINT()
        # Runs on the JS API worker thread; SetWindowPos is safe across threads.
        while user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
            user32.GetCursorPos(ctypes.byref(pt))
            dx, dy = pt.x - start.x, pt.y - start.y
            left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
            if "left" in edge:
                left = min(rect.left + dx, rect.right - min_w)
            if "right" in edge:
                right = max(rect.right + dx, rect.left + min_w)
            if "top" in edge:
                top = min(rect.top + dy, rect.bottom - min_h)
            if "bottom" in edge:
                bottom = max(rect.bottom + dy, rect.top + min_h)
            user32.SetWindowPos(hwnd, None, left, top, right - left, bottom - top, SWP_NOZORDER | SWP_NOACTIVATE)
            time.sleep(1 / 120)
