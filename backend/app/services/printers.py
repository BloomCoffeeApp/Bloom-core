"""Raw transports to thermal printers (no Windows print dialog, no drivers' rendering):

- Windows printers: the spooler with datatype RAW (OpenPrinter/StartDocPrinter/WritePrinter), through
  ctypes on winspool.drv — no pywin32 dependency. Works with USB printers installed with the vendor's
  driver or the "Generic / Text Only" driver.
- Network printers: raw TCP to IP:9100 (JetDirect / "AppSocket"), what Ethernet/Wi-Fi thermals speak.
"""

import ctypes
import socket
import sys
from typing import Any


class PrintError(Exception):
    """Printing failed; the message is shown to the user (Spanish)."""


IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    _winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class _PRINTER_INFO_4(ctypes.Structure):  # noqa: N801 (Win32 name)
        _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR), ("Attributes", wintypes.DWORD)]

    class _DOC_INFO_1(ctypes.Structure):  # noqa: N801
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    _winspool.EnumPrintersW.argtypes = [
        wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    _winspool.EnumPrintersW.restype = wintypes.BOOL
    _winspool.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _winspool.GetDefaultPrinterW.restype = wintypes.BOOL
    _winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    _winspool.OpenPrinterW.restype = wintypes.BOOL
    _winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(_DOC_INFO_1)]
    _winspool.StartDocPrinterW.restype = wintypes.DWORD
    _winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    _winspool.StartPagePrinter.restype = wintypes.BOOL
    _winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _winspool.WritePrinter.restype = wintypes.BOOL
    for _fn in ("EndPagePrinter", "EndDocPrinter", "ClosePrinter"):
        getattr(_winspool, _fn).argtypes = [wintypes.HANDLE]
        getattr(_winspool, _fn).restype = wintypes.BOOL

PRINTER_ENUM_LOCAL = 0x2
PRINTER_ENUM_CONNECTIONS = 0x4


def list_windows_printers() -> list[dict[str, Any]]:
    """Installed printers (local + shared connections). Empty outside Windows."""
    if not IS_WINDOWS:
        return []
    flags = PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    needed, returned = wintypes.DWORD(0), wintypes.DWORD(0)
    _winspool.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return []
    buf = (ctypes.c_byte * needed.value)()
    if not _winspool.EnumPrintersW(flags, None, 4, buf, needed, ctypes.byref(needed), ctypes.byref(returned)):
        raise PrintError(f"No se pudo leer la lista de impresoras de Windows (error {ctypes.get_last_error()})")
    infos = ctypes.cast(buf, ctypes.POINTER(_PRINTER_INFO_4 * returned.value)).contents
    default = _default_printer()
    names = [i.pPrinterName for i in infos if i.pPrinterName]
    return [{"name": n, "default": n == default} for n in sorted(names, key=str.lower)]


def _default_printer() -> str | None:
    size = wintypes.DWORD(0)
    _winspool.GetDefaultPrinterW(None, ctypes.byref(size))
    if not size.value:
        return None
    buf = ctypes.create_unicode_buffer(size.value)
    return buf.value if _winspool.GetDefaultPrinterW(buf, ctypes.byref(size)) else None


def send_windows(printer_name: str, data: bytes, doc_name: str = "Bloom") -> None:
    """RAW job to the Windows spooler (bypasses the driver's rendering: the printer gets our bytes)."""
    if not IS_WINDOWS:
        raise PrintError("Las impresoras de Windows solo están disponibles en Windows")
    handle = wintypes.HANDLE()
    if not _winspool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        raise PrintError(f"No se encontró la impresora «{printer_name}» (¿la desinstalaron o le cambiaron el nombre?)")
    try:
        info = _DOC_INFO_1(doc_name, None, "RAW")
        if not _winspool.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise PrintError(
                f"La impresora «{printer_name}» no aceptó el trabajo (error {ctypes.get_last_error()}). "
                "Si usa un driver nuevo (v4/XPS), instalala con el driver del fabricante o «Generic / Text Only»."
            )
        try:
            if not _winspool.StartPagePrinter(handle):
                raise PrintError(f"No se pudo empezar a imprimir en «{printer_name}»")
            written = wintypes.DWORD(0)
            ok = _winspool.WritePrinter(handle, data, len(data), ctypes.byref(written))
            _winspool.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise PrintError(f"No se pudo enviar el ticket a «{printer_name}» (error {ctypes.get_last_error()})")
        finally:
            _winspool.EndDocPrinter(handle)
    finally:
        _winspool.ClosePrinter(handle)


def send_tcp(host: str, port: int, data: bytes, timeout: float = 5.0) -> None:
    """Raw TCP (port 9100) to a network printer."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.sendall(data)
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    except TimeoutError as e:
        raise PrintError(f"La impresora {host}:{port} no respondió. ¿Está prendida y en la misma red?") from e
    except OSError as e:
        raise PrintError(f"No se pudo conectar con la impresora {host}:{port} ({e.strerror or e})") from e
