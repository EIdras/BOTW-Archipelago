"""Read-only access to another process's memory (Windows, 64-bit).

Used to locate BOTW's GameData flag tables inside Cemu's emulated RAM.
Read-only on purpose: this spike only answers "can we see the flags", nothing
here writes to the game.
"""
import ctypes, ctypes.wintypes as w

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
READABLE = (0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80)   # R, RW, WC, XR, XRW, XWC


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong),
                ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", w.DWORD),
                ("__alignment1", w.DWORD),
                ("RegionSize", ctypes.c_ulonglong),
                ("State", w.DWORD),
                ("Protect", w.DWORD),
                ("Type", w.DWORD),
                ("__alignment2", w.DWORD)]


k32.OpenProcess.restype = w.HANDLE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [w.HANDLE, ctypes.c_ulonglong,
                               ctypes.POINTER(MEMORY_BASIC_INFORMATION64), ctypes.c_size_t]
k32.ReadProcessMemory.restype = w.BOOL
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_ulonglong, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = w.BOOL
k32.WriteProcessMemory.argtypes = [w.HANDLE, ctypes.c_ulonglong, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [w.HANDLE]


class Process:
    def __init__(self, pid: int, writable: bool = False):
        self.pid = pid
        self.writable = writable
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if writable:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.h = k32.OpenProcess(access, False, pid)
        if not self.h:
            raise OSError(ctypes.get_last_error(),
                          f"OpenProcess({pid}) failed - run this shell as the same user as Cemu")

    def close(self):
        if self.h:
            k32.CloseHandle(self.h); self.h = None

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    def regions(self, min_size=0):
        """Yield (base, size) of committed readable regions."""
        addr, mbi = 0, MEMORY_BASIC_INFORMATION64()
        while addr < (1 << 47):
            if not k32.VirtualQueryEx(self.h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base, size = mbi.BaseAddress, mbi.RegionSize
            if size == 0:
                break
            if (mbi.State == MEM_COMMIT and (mbi.Protect & READABLE)
                    and not (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS))
                    and size >= min_size):
                yield base, size
            addr = base + size

    def read(self, address: int, size: int) -> bytes | None:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.h, address, buf, size, ctypes.byref(got))
        if not ok or got.value == 0:
            return None
        return buf.raw[:got.value]

    def write(self, address: int, data: bytes) -> bool:
        """Write bytes into the target process. Requires writable=True."""
        if not self.writable:
            raise PermissionError("Process was opened read-only; pass writable=True")
        buf = ctypes.create_string_buffer(data, len(data))
        put = ctypes.c_size_t(0)
        ok = k32.WriteProcessMemory(self.h, address, buf, len(data), ctypes.byref(put))
        return bool(ok) and put.value == len(data)
