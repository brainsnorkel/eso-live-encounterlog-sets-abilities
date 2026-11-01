"""
One frame of a monitor through DXGI Desktop Duplication, in the desktop's own pixel
format: BGRA8 on an SDR desktop, RGBA16F (linear scRGB) when Windows HDR is on.

Design: Desktop Duplication through ctypes. The trial completion banner (issue #167)
must be captured on an HDR desktop, where every 8-bit grab (GDI, Qt's
QScreen.grabWindow, Windows Graphics Capture with an 8-bit format) comes out
washed-out: Windows composes an HDR desktop in linear scRGB floating point and the
8-bit paths clip it without the transfer curve. Desktop Duplication hands the
composed desktop over as it is, R16G16B16A16_FLOAT when HDR is on, so the
conversion to sRGB can be done properly (gui.banner_burst.frame_to_image). The
packages that wrap the API either need numpy and OpenCV (windows-capture, about
150 MB in the frozen app) or still need a Direct3D device made by hand (pywinrt), so
the API is driven directly through ctypes: a Direct3D 11 device per adapter, its
outputs enumerated through DXGI, IDXGIOutput5::DuplicateOutput1 asked for FP16 or
BGRA8 frames, each frame copied to a staging texture and mapped for reading. The
vtable positions below are the declaration order of d3d11.h and dxgi1_5.h; a wrong
one crashes the process, so run_self_test() exercises every call on a real desktop.

The first AcquireNextFrame after DuplicateOutput often returns an empty texture
(LastPresentTime 0: no desktop image presented since the duplication began), so
grab() keeps acquiring until a presented frame comes or the deadline passes.
Desktop Duplication is refused inside some remote sessions and on an output that
belongs to another adapter than the device, which is why every adapter gets its
own device.
"""
from __future__ import annotations

import ctypes
import sys
import time
import uuid
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_long,
    c_ubyte,
    c_uint,
    c_ulong,
    c_ushort,
    c_void_p,
    wintypes,
)
from dataclasses import dataclass

__all__ = ["DesktopDuplicator", "DuplicationError", "Frame", "OutputInfo", "list_outputs"]

# DXGI_FORMAT values the duplication may hand over
FORMAT_R16G16B16A16_FLOAT = 10
FORMAT_R10G10B10A2_UNORM = 24
FORMAT_R8G8B8A8_UNORM = 28
FORMAT_B8G8R8A8_UNORM = 87
FORMAT_NAMES = {
    FORMAT_R16G16B16A16_FLOAT: "rgba16f",
    FORMAT_R10G10B10A2_UNORM: "rgb10a2",
    FORMAT_R8G8B8A8_UNORM: "rgba8",
    FORMAT_B8G8R8A8_UNORM: "bgra8",
}
BYTES_PER_PIXEL = {
    FORMAT_R16G16B16A16_FLOAT: 8,
    FORMAT_R10G10B10A2_UNORM: 4,
    FORMAT_R8G8B8A8_UNORM: 4,
    FORMAT_B8G8R8A8_UNORM: 4,
}

_D3D_DRIVER_TYPE_UNKNOWN = 0
_D3D11_SDK_VERSION = 7
_D3D11_USAGE_STAGING = 3
_D3D11_CPU_ACCESS_READ = 0x20000
_D3D11_MAP_READ = 1

_S_OK = 0
_DXGI_ERROR_NOT_FOUND = -2005270526          # 0x887A0002
_DXGI_ERROR_UNSUPPORTED = -2005270524        # 0x887A0004
_DXGI_ERROR_NOT_CURRENTLY_AVAILABLE = -2005270494  # 0x887A0022
_DXGI_ERROR_ACCESS_LOST = -2005270490        # 0x887A0026
_DXGI_ERROR_WAIT_TIMEOUT = -2005270489       # 0x887A0027


class DuplicationError(RuntimeError):
    """Desktop Duplication could not be set up or lost its desktop."""


class _GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]

    @classmethod
    def of(cls, text: str) -> _GUID:
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


_IID_IDXGIFactory1 = _GUID.of("770aae78-f26f-4dba-a829-253c83d1b387")
_IID_IDXGIOutput1 = _GUID.of("00cddea8-939b-4b83-a340-a685226666cc")
_IID_IDXGIOutput5 = _GUID.of("80a07424-ab52-42eb-833c-0c42fd282d98")
_IID_ID3D11Texture2D = _GUID.of("6f15aaf2-d208-4e89-9ab4-489535d34f9c")


class _DXGI_RATIONAL(Structure):
    _fields_ = [("Numerator", c_uint), ("Denominator", c_uint)]


class _DXGI_MODE_DESC(Structure):
    _fields_ = [("Width", c_uint), ("Height", c_uint), ("RefreshRate", _DXGI_RATIONAL),
                ("Format", c_uint), ("ScanlineOrdering", c_uint), ("Scaling", c_uint)]


class _DXGI_OUTDUPL_DESC(Structure):
    _fields_ = [("ModeDesc", _DXGI_MODE_DESC), ("Rotation", c_uint),
                ("DesktopImageInSystemMemory", wintypes.BOOL)]


class _DXGI_OUTPUT_DESC(Structure):
    _fields_ = [("DeviceName", wintypes.WCHAR * 32), ("DesktopCoordinates", wintypes.RECT),
                ("AttachedToDesktop", wintypes.BOOL), ("Rotation", c_uint), ("Monitor", c_void_p)]


class _DXGI_OUTDUPL_POINTER_POSITION(Structure):
    _fields_ = [("Position", wintypes.POINT), ("Visible", wintypes.BOOL)]


class _DXGI_OUTDUPL_FRAME_INFO(Structure):
    _fields_ = [("LastPresentTime", ctypes.c_longlong), ("LastMouseUpdateTime", ctypes.c_longlong),
                ("AccumulatedFrames", c_uint), ("RectsCoalesced", wintypes.BOOL),
                ("ProtectedContentMaskedOut", wintypes.BOOL),
                ("PointerPosition", _DXGI_OUTDUPL_POINTER_POSITION),
                ("TotalMetadataBufferSize", c_uint), ("PointerShapeBufferSize", c_uint)]


class _DXGI_SAMPLE_DESC(Structure):
    _fields_ = [("Count", c_uint), ("Quality", c_uint)]


class _D3D11_TEXTURE2D_DESC(Structure):
    _fields_ = [("Width", c_uint), ("Height", c_uint), ("MipLevels", c_uint), ("ArraySize", c_uint),
                ("Format", c_uint), ("SampleDesc", _DXGI_SAMPLE_DESC), ("Usage", c_uint),
                ("BindFlags", c_uint), ("CPUAccessFlags", c_uint), ("MiscFlags", c_uint)]


class _D3D11_MAPPED_SUBRESOURCE(Structure):
    _fields_ = [("pData", c_void_p), ("RowPitch", c_uint), ("DepthPitch", c_uint)]


def _call(obj: c_void_p, index: int, restype, *argtypes):
    """The COM method at vtable position *index* of *obj*, ready to call with
    the interface pointer supplied."""
    vtable = ctypes.cast(obj, POINTER(c_void_p))[0]
    fn = ctypes.cast(vtable, POINTER(c_void_p))[index]
    proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    method = proto(fn)
    return lambda *args: method(obj, *args)


def _release(obj: c_void_p | None) -> None:
    if obj is not None and obj.value:
        _call(obj, 2, c_ulong)()
        obj.value = None


def _query_interface(obj: c_void_p, iid: _GUID) -> c_void_p | None:
    out = c_void_p()
    hr = _call(obj, 0, c_long, POINTER(_GUID), POINTER(c_void_p))(byref(iid), byref(out))
    return out if hr == _S_OK and out.value else None


@dataclass
class OutputInfo:
    """A monitor as DXGI lists it: its adapter and output indexes, the GDI device
    name (\\\\.\\DISPLAY1, which the DisplayConfig API also uses) and its desktop
    rectangle in physical pixels."""
    adapter: int
    output: int
    device_name: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass
class Frame:
    """One desktop image: tightly packed rows of *width* pixels in *format*
    (a FORMAT_NAMES key), *bytes_per_pixel* each."""
    width: int
    height: int
    format: int
    data: bytes

    @property
    def format_name(self) -> str:
        return FORMAT_NAMES.get(self.format, str(self.format))

    @property
    def bytes_per_pixel(self) -> int:
        return BYTES_PER_PIXEL.get(self.format, 4)

    @property
    def stride(self) -> int:
        return self.width * self.bytes_per_pixel


def _dxgi_factory() -> c_void_p:
    factory = c_void_p()
    hr = ctypes.windll.dxgi.CreateDXGIFactory1(byref(_IID_IDXGIFactory1), byref(factory))
    if hr != _S_OK or not factory.value:
        raise DuplicationError(f"CreateDXGIFactory1 failed: 0x{hr & 0xFFFFFFFF:08X}")
    return factory


def _enum_adapter(factory: c_void_p, index: int) -> c_void_p | None:
    adapter = c_void_p()
    hr = _call(factory, 12, c_long, c_uint, POINTER(c_void_p))(index, byref(adapter))
    if hr == _DXGI_ERROR_NOT_FOUND or hr != _S_OK:
        return None
    return adapter


def _enum_output(adapter: c_void_p, index: int) -> c_void_p | None:
    output = c_void_p()
    hr = _call(adapter, 7, c_long, c_uint, POINTER(c_void_p))(index, byref(output))
    if hr != _S_OK:
        return None
    return output


def _output_desc(output: c_void_p) -> _DXGI_OUTPUT_DESC:
    desc = _DXGI_OUTPUT_DESC()
    hr = _call(output, 7, c_long, POINTER(_DXGI_OUTPUT_DESC))(byref(desc))
    if hr != _S_OK:
        raise DuplicationError(f"IDXGIOutput::GetDesc failed: 0x{hr & 0xFFFFFFFF:08X}")
    return desc


def list_outputs() -> list[OutputInfo]:
    """Every output attached to the desktop, across adapters."""
    if sys.platform != "win32":
        return []
    found: list[OutputInfo] = []
    factory = _dxgi_factory()
    try:
        a = 0
        while True:
            adapter = _enum_adapter(factory, a)
            if adapter is None:
                break
            try:
                o = 0
                while True:
                    output = _enum_output(adapter, o)
                    if output is None:
                        break
                    try:
                        desc = _output_desc(output)
                        if desc.AttachedToDesktop:
                            r = desc.DesktopCoordinates
                            found.append(OutputInfo(a, o, desc.DeviceName, r.left, r.top, r.right, r.bottom))
                    finally:
                        _release(output)
                    o += 1
            finally:
                _release(adapter)
            a += 1
    finally:
        _release(factory)
    return found


class DesktopDuplicator:
    """Duplicates one output. Make one per burst, grab() as often as wanted,
    close() when done. Preferred formats: FP16 first, so an HDR desktop comes
    as linear scRGB, then BGRA8."""

    PREFERRED_FORMATS = (FORMAT_R16G16B16A16_FLOAT, FORMAT_B8G8R8A8_UNORM)

    def __init__(self, info: OutputInfo):
        self.info = info
        self._factory: c_void_p | None = None
        self._adapter: c_void_p | None = None
        self._output: c_void_p | None = None
        self._device: c_void_p | None = None
        self._context: c_void_p | None = None
        self._dup: c_void_p | None = None
        self._staging: c_void_p | None = None
        self._staging_desc: _D3D11_TEXTURE2D_DESC | None = None
        self.format = 0
        self.width = 0
        self.height = 0
        try:
            self._open()
        except Exception:
            self.close()
            raise

    def _open(self) -> None:
        self._factory = _dxgi_factory()
        self._adapter = _enum_adapter(self._factory, self.info.adapter)
        if self._adapter is None:
            raise DuplicationError(f"adapter {self.info.adapter} is gone")
        self._output = _enum_output(self._adapter, self.info.output)
        if self._output is None:
            raise DuplicationError(f"output {self.info.output} of adapter {self.info.adapter} is gone")
        device = c_void_p()
        context = c_void_p()
        hr = ctypes.windll.d3d11.D3D11CreateDevice(
            self._adapter, _D3D_DRIVER_TYPE_UNKNOWN, None, 0, None, 0, _D3D11_SDK_VERSION,
            byref(device), None, byref(context))
        if hr != _S_OK:
            raise DuplicationError(f"D3D11CreateDevice failed: 0x{hr & 0xFFFFFFFF:08X}")
        self._device, self._context = device, context
        dup = c_void_p()
        hr = _DXGI_ERROR_UNSUPPORTED
        # DuplicateOutput1 (Windows 10 1703 on) takes the format list that lets
        # an HDR desktop come as FP16; it is refused in a remote session, where
        # the older DuplicateOutput still works, so that is the fallback
        output5 = _query_interface(self._output, _IID_IDXGIOutput5)
        if output5 is not None:
            formats = (c_uint * len(self.PREFERRED_FORMATS))(*self.PREFERRED_FORMATS)
            try:
                hr = _call(output5, 26, c_long, c_void_p, c_uint, c_uint, POINTER(c_uint), POINTER(c_void_p))(
                    self._device, 0, len(self.PREFERRED_FORMATS), formats, byref(dup))
            finally:
                _release(output5)
        if hr == _DXGI_ERROR_UNSUPPORTED or output5 is None:
            output1 = _query_interface(self._output, _IID_IDXGIOutput1)
            if output1 is None:
                raise DuplicationError("IDXGIOutput1 is not available (Windows 8 or later is needed)")
            try:
                hr = _call(output1, 22, c_long, c_void_p, POINTER(c_void_p))(self._device, byref(dup))
            finally:
                _release(output1)
        if hr != _S_OK or not dup.value:
            reason = {
                _DXGI_ERROR_UNSUPPORTED: "not supported on this output (a remote session, or another adapter's monitor)",
                _DXGI_ERROR_NOT_CURRENTLY_AVAILABLE: "too many applications already duplicate this desktop",
            }.get(hr, f"0x{hr & 0xFFFFFFFF:08X}")
            raise DuplicationError(f"DuplicateOutput failed: {reason}")
        self._dup = dup
        desc = _DXGI_OUTDUPL_DESC()
        _call(self._dup, 7, None, POINTER(_DXGI_OUTDUPL_DESC))(byref(desc))
        self.format = desc.ModeDesc.Format
        self.width = desc.ModeDesc.Width
        self.height = desc.ModeDesc.Height
        if self.format not in BYTES_PER_PIXEL:
            raise DuplicationError(f"desktop format {self.format} is not one this reader handles")

    def grab(self, deadline_s: float = 1.0) -> Frame | None:
        """The next presented desktop image, or None when none came within
        *deadline_s* seconds. Raises DuplicationError when the desktop was lost
        (resolution or HDR switch, another app took exclusive mode): make a new
        duplicator then."""
        if self._dup is None:
            raise DuplicationError("closed")
        end = time.monotonic() + deadline_s
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return None
            info = _DXGI_OUTDUPL_FRAME_INFO()
            resource = c_void_p()
            hr = _call(self._dup, 8, c_long, c_uint, POINTER(_DXGI_OUTDUPL_FRAME_INFO), POINTER(c_void_p))(
                int(min(remaining, 1.0) * 1000), byref(info), byref(resource))
            if hr == _DXGI_ERROR_WAIT_TIMEOUT:
                continue
            if hr == _DXGI_ERROR_ACCESS_LOST:
                raise DuplicationError("desktop lost (mode or HDR change); reopen the duplicator")
            if hr != _S_OK:
                raise DuplicationError(f"AcquireNextFrame failed: 0x{hr & 0xFFFFFFFF:08X}")
            try:
                if info.LastPresentTime == 0:
                    continue  # only the pointer moved: no new desktop image
                return self._read(resource)
            finally:
                _release(resource)
                _call(self._dup, 14, c_long)()

    def _read(self, resource: c_void_p) -> Frame:
        texture = _query_interface(resource, _IID_ID3D11Texture2D)
        if texture is None:
            raise DuplicationError("the desktop resource is not a 2D texture")
        try:
            desc = _D3D11_TEXTURE2D_DESC()
            _call(texture, 10, None, POINTER(_D3D11_TEXTURE2D_DESC))(byref(desc))
            self._ensure_staging(desc)
            _call(self._context, 47, None, c_void_p, c_void_p)(self._staging, texture)
            mapped = _D3D11_MAPPED_SUBRESOURCE()
            hr = _call(self._context, 14, c_long, c_void_p, c_uint, c_uint, c_uint,
                       POINTER(_D3D11_MAPPED_SUBRESOURCE))(self._staging, 0, _D3D11_MAP_READ, 0, byref(mapped))
            if hr != _S_OK:
                raise DuplicationError(f"Map failed: 0x{hr & 0xFFFFFFFF:08X}")
            try:
                bpp = BYTES_PER_PIXEL[desc.Format]
                row_bytes = desc.Width * bpp
                if mapped.RowPitch == row_bytes:
                    data = ctypes.string_at(mapped.pData, row_bytes * desc.Height)
                else:
                    rows = []
                    for y in range(desc.Height):
                        rows.append(ctypes.string_at(mapped.pData + y * mapped.RowPitch, row_bytes))
                    data = b"".join(rows)
            finally:
                _call(self._context, 15, None, c_void_p, c_uint)(self._staging, 0)
            return Frame(desc.Width, desc.Height, desc.Format, data)
        finally:
            _release(texture)

    def _ensure_staging(self, desc: _D3D11_TEXTURE2D_DESC) -> None:
        current = self._staging_desc
        if current is not None and (current.Width, current.Height, current.Format) == (desc.Width, desc.Height, desc.Format):
            return
        _release(self._staging)
        self._staging = None
        staging = _D3D11_TEXTURE2D_DESC()
        staging.Width, staging.Height = desc.Width, desc.Height
        staging.MipLevels, staging.ArraySize = 1, 1
        staging.Format = desc.Format
        staging.SampleDesc.Count, staging.SampleDesc.Quality = 1, 0
        staging.Usage = _D3D11_USAGE_STAGING
        staging.BindFlags, staging.MiscFlags = 0, 0
        staging.CPUAccessFlags = _D3D11_CPU_ACCESS_READ
        out = c_void_p()
        hr = _call(self._device, 5, c_long, POINTER(_D3D11_TEXTURE2D_DESC), c_void_p, POINTER(c_void_p))(
            byref(staging), None, byref(out))
        if hr != _S_OK or not out.value:
            raise DuplicationError(f"CreateTexture2D (staging) failed: 0x{hr & 0xFFFFFFFF:08X}")
        self._staging, self._staging_desc = out, staging

    def close(self) -> None:
        for name in ("_staging", "_dup", "_context", "_device", "_output", "_adapter", "_factory"):
            _release(getattr(self, name))
            setattr(self, name, None)
        self._staging_desc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def run_self_test(out_path: str | None = None) -> int:
    """List the outputs, duplicate each, grab a frame and report it; with
    *out_path*, save the first output's frame as a PNG through Qt (the
    conversion banner_capture uses). Exit code 0 when every output gave a frame."""
    outputs = list_outputs()
    print(f"outputs: {len(outputs)}")
    for o in outputs:
        print(f"  adapter {o.adapter} output {o.output} {o.device_name} {o.width}x{o.height} at ({o.left},{o.top})")
    rc = 0
    for o in outputs:
        t0 = time.perf_counter()
        try:
            with DesktopDuplicator(o) as dup:
                t1 = time.perf_counter()
                print(f"{o.device_name}: duplicating as {FORMAT_NAMES.get(dup.format)} {dup.width}x{dup.height}, "
                      f"opened in {(t1 - t0) * 1000:.0f} ms")
                frame = dup.grab(deadline_s=2.0)
                t2 = time.perf_counter()
                if frame is None:
                    print("  no presented frame within 2 s")
                    rc = 1
                    continue
                peak = max(frame.data[: frame.stride * min(frame.height, 64)])
                print(f"  frame {frame.width}x{frame.height} {frame.format_name} {len(frame.data)} bytes "
                      f"in {(t2 - t1) * 1000:.0f} ms, peak byte in the first rows {peak}")
                if out_path and o is outputs[0]:
                    from gui.banner_burst import frame_to_image
                    image = frame_to_image(frame, sdr_white_nits=80.0)
                    image.save(out_path, "PNG")
                    print(f"  wrote {out_path} ({image.width()}x{image.height()})")
        except DuplicationError as exc:
            print(f"{o.device_name}: {exc}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(run_self_test(sys.argv[1] if len(sys.argv) > 1 else None))
