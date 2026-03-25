"""Native filesystem runtime functions for Comp.

Low-level OS operations callable via py.call from Comp code.
These functions deal in Python primitives — the Comp-side VFS
layer (nativefs.comp) handles entry assembly and stashes handles.

Functions return plain Python types (str, dict, list, None) or
DirHandle objects (opaque to Comp, round-trips through @py handles).
"""

import os
import stat
import sys


# ---------------------------------------------------------------------------
# DirHandle — opaque wrapper for OS directory handles
# ---------------------------------------------------------------------------

class DirHandle:
    """Opaque wrapper around a raw OS directory handle.

    On POSIX this wraps an integer file descriptor.
    On Windows this wraps an NT HANDLE value.
    Comp code never inspects this — it just stashes it and passes
    it back to runtime functions via py.call.
    """

    __slots__ = ("raw", "path", "closed")

    def __init__(self, raw, path):
        self.raw = raw
        self.path = path
        self.closed = False

    def __repr__(self):
        return f"<DirHandle path={self.path!r} closed={self.closed}>"


# ---------------------------------------------------------------------------
# Platform-specific backend
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wintypes

    _kernel32 = ctypes.windll.kernel32
    _ntdll = ctypes.windll.ntdll

    _ntdll.NtCreateFile.restype = ctypes.c_uint32
    _ntdll.NtQueryDirectoryFile.restype = ctypes.c_uint32
    _ntdll.NtReadFile.restype = ctypes.c_uint32
    _ntdll.NtWriteFile.restype = ctypes.c_uint32
    _ntdll.NtClose.restype = ctypes.c_uint32

    _STATUS_SUCCESS = 0
    _STATUS_NO_MORE_FILES = 0x80000006

    _FILE_LIST_DIRECTORY = 0x00000001
    _FILE_READ_DATA = 0x00000001
    _FILE_WRITE_DATA = 0x00000002
    _SYNCHRONIZE = 0x00100000
    _FILE_READ_ATTRIBUTES = 0x00000080

    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _FILE_SHARE_DELETE = 0x00000004

    _FILE_OPEN = 1
    _FILE_CREATE = 2
    _FILE_OVERWRITE_IF = 5

    _FILE_DIRECTORY_FILE = 0x00000001
    _FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    _FILE_NON_DIRECTORY_FILE = 0x00000040

    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _OBJ_CASE_INSENSITIVE = 0x00000040

    _FileDirectoryInformation = 1

    class _NtUnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", ctypes.c_wchar_p),
        ]

    class _NtObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(_NtUnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class _NtIoStatusBlock(ctypes.Structure):
        class _Status(ctypes.Union):
            _fields_ = [
                ("Status", ctypes.c_long),
                ("Pointer", ctypes.c_void_p),
            ]
        _fields_ = [
            ("u", _Status),
            ("Information", ctypes.c_size_t),
        ]

    class _NtFileDirectoryInformation(ctypes.Structure):
        _fields_ = [
            ("NextEntryOffset", wintypes.ULONG),
            ("FileIndex", wintypes.ULONG),
            ("CreationTime", ctypes.c_int64),
            ("LastAccessTime", ctypes.c_int64),
            ("LastWriteTime", ctypes.c_int64),
            ("ChangeTime", ctypes.c_int64),
            ("EndOfFile", ctypes.c_int64),
            ("AllocationSize", ctypes.c_int64),
            ("FileAttributes", wintypes.ULONG),
            ("FileNameLength", wintypes.ULONG),
            ("FileName", ctypes.c_wchar * 1),
        ]

    class _NtFileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("CreationTime", ctypes.c_int64),
            ("LastAccessTime", ctypes.c_int64),
            ("LastWriteTime", ctypes.c_int64),
            ("ChangeTime", ctypes.c_int64),
            ("FileAttributes", wintypes.DWORD),
        ]

    class _NtFileStandardInfo(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_int64),
            ("EndOfFile", ctypes.c_int64),
            ("NumberOfLinks", wintypes.DWORD),
            ("DeletePending", wintypes.BOOLEAN),
            ("Directory", wintypes.BOOLEAN),
        ]

    def _nt_make_oa(name, root_handle):
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)
        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = root_handle if root_handle is not None else 0
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None
        return us_buf, us, oa

    def _nt_open_dir(name, root_handle):
        us_buf, us, oa = _nt_make_oa(name, root_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN,
            _FILE_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile failed: 0x{status:08X} for {name!r}")
        return handle.value

    def _nt_list_dir(handle):
        buf_size = 65536
        buf = ctypes.create_string_buffer(buf_size)
        iosb = _NtIoStatusBlock()
        entries = []
        restart = True
        while True:
            status = _ntdll.NtQueryDirectoryFile(
                handle, None, None, None, ctypes.byref(iosb),
                buf, buf_size, _FileDirectoryInformation, False, None, restart,
            )
            restart = False
            if status == _STATUS_NO_MORE_FILES:
                break
            if status != _STATUS_SUCCESS:
                raise OSError(f"NtQueryDirectoryFile failed: 0x{status:08X}")
            offset = 0
            while True:
                entry = _NtFileDirectoryInformation.from_buffer_copy(buf, offset)
                name_len = entry.FileNameLength // 2
                name = ctypes.wstring_at(
                    ctypes.addressof(buf) + offset + _NtFileDirectoryInformation.FileName.offset,
                    name_len,
                )
                if name not in (".", ".."):
                    attrs = entry.FileAttributes
                    if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
                        etype = "link"
                    elif attrs & _FILE_ATTRIBUTE_DIRECTORY:
                        etype = "dir"
                    else:
                        etype = "file"
                    modified = (entry.LastWriteTime - 116444736000000000) / 10000000
                    entries.append({
                        "name": name, "entry-type": etype,
                        "size": entry.EndOfFile, "modified": modified,
                    })
                if entry.NextEntryOffset == 0:
                    break
                offset += entry.NextEntryOffset
        return entries

    def _nt_stat(parent_handle, name):
        us_buf, us, oa = _nt_make_oa(name, parent_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN, _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"stat failed: 0x{status:08X} for {name!r}")
        try:
            basic_info = _NtFileBasicInfo()
            std_info = _NtFileStandardInfo()
            _kernel32.GetFileInformationByHandleEx(
                handle.value, 0, ctypes.byref(basic_info), ctypes.sizeof(basic_info),
            )
            _kernel32.GetFileInformationByHandleEx(
                handle.value, 1, ctypes.byref(std_info), ctypes.sizeof(std_info),
            )
            attrs = basic_info.FileAttributes
            if attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
                etype = "link"
            elif std_info.Directory:
                etype = "dir"
            else:
                etype = "file"
            modified = (basic_info.LastWriteTime - 116444736000000000) / 10000000
            return {
                "name": name, "entry-type": etype,
                "size": std_info.EndOfFile, "modified": modified,
            }
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_read_file(parent_handle, name):
        us_buf, us, oa = _nt_make_oa(name, parent_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_READ_DATA | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0, _FILE_SHARE_READ, _FILE_OPEN,
            _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"read failed: 0x{status:08X} for {name!r}")
        try:
            chunks = []
            read_buf = ctypes.create_string_buffer(65536)
            while True:
                read_iosb = _NtIoStatusBlock()
                rstat = _ntdll.NtReadFile(
                    handle.value, None, None, None,
                    ctypes.byref(read_iosb), read_buf, len(read_buf), None, None,
                )
                n = read_iosb.Information
                if n > 0:
                    chunks.append(bytes(read_buf[:n]))
                if rstat == _STATUS_SUCCESS and n < len(read_buf):
                    break
                if rstat not in (_STATUS_SUCCESS, 0x00000103):
                    break
            return b"".join(chunks)
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_write_file(parent_handle, name, data):
        us_buf, us, oa = _nt_make_oa(name, parent_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_WRITE_DATA | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0, 0, _FILE_OVERWRITE_IF,
            _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"write failed: 0x{status:08X} for {name!r}")
        try:
            buf = ctypes.create_string_buffer(data)
            write_iosb = _NtIoStatusBlock()
            wstat = _ntdll.NtWriteFile(
                handle.value, None, None, None,
                ctypes.byref(write_iosb), buf, len(data), None, None,
            )
            if wstat != _STATUS_SUCCESS:
                raise OSError(f"NtWriteFile failed: 0x{wstat:08X}")
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_mkdir(parent_handle, name):
        us_buf, us, oa = _nt_make_oa(name, parent_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_LIST_DIRECTORY | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_CREATE,
            _FILE_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"mkdir failed: 0x{status:08X} for {name!r}")
        _ntdll.NtClose(handle.value)

    def _nt_remove(parent_handle, name):
        us_buf, us, oa = _nt_make_oa(name, parent_handle)
        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()
        _FILE_DELETE_ON_CLOSE = 0x00001000
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            0x00010000 | _SYNCHRONIZE,
            ctypes.byref(oa), ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN,
            _FILE_DELETE_ON_CLOSE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"remove failed: 0x{status:08X} for {name!r}")
        _ntdll.NtClose(handle.value)

    def _nt_close(handle):
        _ntdll.NtClose(handle)

    _backend_open_root = lambda path: _nt_open_dir(path, None)
    _backend_open_at = lambda name, parent: _nt_open_dir(name, parent)
    _backend_list_dir = _nt_list_dir
    _backend_stat = _nt_stat
    _backend_read_file = _nt_read_file
    _backend_write_file = _nt_write_file
    _backend_mkdir = _nt_mkdir
    _backend_remove = _nt_remove
    _backend_close = _nt_close

else:
    _O_RDONLY = os.O_RDONLY
    _O_WRONLY = os.O_WRONLY
    _O_CREAT = os.O_CREAT
    _O_TRUNC = os.O_TRUNC
    _O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)

    def _posix_open_root(path):
        return os.open(path, _O_RDONLY | _O_DIRECTORY)

    def _posix_open_at(name, parent_fd):
        return os.open(name, _O_RDONLY | _O_DIRECTORY, dir_fd=parent_fd)

    def _posix_list_dir(fd):
        entries = []
        with os.scandir(fd) as it:
            for entry in it:
                st = entry.stat(follow_symlinks=False)
                mode = st.st_mode
                if stat.S_ISLNK(mode):
                    etype = "link"
                elif stat.S_ISDIR(mode):
                    etype = "dir"
                elif stat.S_ISREG(mode):
                    etype = "file"
                else:
                    etype = "missing"
                entries.append({
                    "name": entry.name, "entry-type": etype,
                    "size": st.st_size, "modified": st.st_mtime,
                })
        return entries

    def _posix_stat(parent_fd, name):
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        mode = st.st_mode
        if stat.S_ISLNK(mode):
            etype = "link"
        elif stat.S_ISDIR(mode):
            etype = "dir"
        elif stat.S_ISREG(mode):
            etype = "file"
        else:
            etype = "missing"
        return {
            "name": name, "entry-type": etype,
            "size": st.st_size, "modified": st.st_mtime,
        }

    def _posix_read_file(parent_fd, name):
        fd = os.open(name, _O_RDONLY, dir_fd=parent_fd)
        try:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)

    def _posix_write_file(parent_fd, name, data):
        fd = os.open(name, _O_WRONLY | _O_CREAT | _O_TRUNC, 0o666, dir_fd=parent_fd)
        try:
            written = 0
            while written < len(data):
                n = os.write(fd, data[written:])
                written += n
        finally:
            os.close(fd)

    def _posix_mkdir(parent_fd, name):
        os.mkdir(name, 0o777, dir_fd=parent_fd)

    def _posix_remove(parent_fd, name):
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISDIR(st.st_mode):
            os.rmdir(name, dir_fd=parent_fd)
        else:
            os.unlink(name, dir_fd=parent_fd)

    def _posix_close(fd):
        os.close(fd)

    _backend_open_root = _posix_open_root
    _backend_open_at = _posix_open_at
    _backend_list_dir = _posix_list_dir
    _backend_stat = _posix_stat
    _backend_read_file = _posix_read_file
    _backend_write_file = _posix_write_file
    _backend_mkdir = _posix_mkdir
    _backend_remove = _posix_remove
    _backend_close = _posix_close


# ---------------------------------------------------------------------------
# Public API — called via py.call from nativefs.comp
# ---------------------------------------------------------------------------

def getcwd():
    """Return the current working directory with forward slashes."""
    return os.getcwd().replace("\\", "/")


def open_root(path):
    """Open an absolute path as a DirHandle.

    Handles Windows drive letter normalization and path forms.
    Returns a DirHandle wrapping the OS directory handle.
    """
    path = path.replace("\\", "/")
    if sys.platform == "win32":
        if len(path) >= 2 and path[1] == ":":
            fs_root = path[0].upper() + ":/"
            rest = path[3:] if len(path) > 3 else ""
        elif len(path) >= 3 and path[0] == "/" and path[2] == "/":
            fs_root = path[1].upper() + ":/"
            rest = path[3:] if len(path) > 3 else ""
        elif path.startswith("/"):
            drive = os.path.splitdrive(os.getcwd())[0]
            fs_root = drive + "/"
            rest = path[1:]
        else:
            raise ValueError(f"not an absolute path: {path!r}")
        nt_path = "\\??\\" + fs_root.replace("/", "\\")
        raw = _backend_open_root(nt_path)
    else:
        if not path.startswith("/"):
            raise ValueError(f"not an absolute path: {path!r}")
        fs_root = "/"
        rest = path[1:]
        raw = _backend_open_root(fs_root)

    handle = DirHandle(raw, fs_root)

    segments = [s for s in rest.split("/") if s]
    for seg in segments:
        try:
            child_raw = _backend_open_at(seg, handle.raw)
        except OSError as e:
            raise OSError(f"cannot navigate through '{seg}': {e}")
        child_path = handle.path.rstrip("/") + "/" + seg
        handle = DirHandle(child_raw, child_path)

    return handle


def open_child(parent_handle, name):
    """Open a child directory relative to parent_handle.

    Supports multi-segment paths: "a/b/c" navigates through each segment.
    Returns a new DirHandle for the final directory.
    """
    segments = [s for s in name.replace("\\", "/").split("/") if s]
    current = parent_handle
    for seg in segments:
        raw = _backend_open_at(seg, current.raw)
        child_path = current.path.rstrip("/") + "/" + seg
        current = DirHandle(raw, child_path)
    return current


def stat_entry(parent_handle, name):
    """Stat a named child relative to parent_handle.

    Returns a dict with name, entry-type, size, modified.
    Returns None if the child does not exist.
    """
    try:
        return _backend_stat(parent_handle.raw, name)
    except OSError:
        return None


def read_file(parent_handle, name):
    """Read a file relative to parent_handle. Returns text (UTF-8)."""
    data = _backend_read_file(parent_handle.raw, name)
    return data.decode("utf-8")


def write_file(parent_handle, name, content):
    """Write text content to a file relative to parent_handle."""
    _backend_write_file(parent_handle.raw, name, content.encode("utf-8"))


def list_dir(dir_handle):
    """List children of a directory. Returns list of dicts."""
    return _backend_list_dir(dir_handle.raw)


def mkdir(parent_handle, name):
    """Create a directory relative to parent_handle."""
    _backend_mkdir(parent_handle.raw, name)


def remove(parent_handle, name):
    """Remove a file or empty directory relative to parent_handle."""
    _backend_remove(parent_handle.raw, name)


def close(dir_handle):
    """Close a directory handle."""
    if not dir_handle.closed:
        try:
            _backend_close(dir_handle.raw)
        except OSError:
            pass
        dir_handle.closed = True


def handle_path(dir_handle):
    """Return the path of a directory handle."""
    return dir_handle.path
