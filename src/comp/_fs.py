"""Filesystem internal module for Comp.

Provides low-level, capability-based filesystem operations using:
- POSIX (Linux/macOS): os.open / os.openat with file descriptors
- Windows: ctypes.windll.ntdll with NT native API (NtCreateFile, NtReadFile, etc.)

All directory access flows through handles opened from a root path, preventing
path-traversal attacks and TOCTOU races.

The internal module registers as "fs-native" and provides these callables:
- open-root: Open a directory handle for an absolute path
- cwd: Get current working directory as a directory handle
- list-at: List directory entries for a handle
- open-at: Open a sub-directory relative to an existing handle
- stat-at: Get metadata for a named entry relative to a handle
- read-at: Read a file's bytes relative to a handle
- write-at: Write bytes to a file relative to a handle
- mkdir-at: Create a directory relative to a handle
- remove-at: Remove a file or directory entry relative to a handle
- path-of: Get the stored absolute path for a handle
- close-dir: Explicitly close a directory handle (handles are also auto-closed)
"""

__all__ = []

import os
import stat
import sys

import datetime as _datetime

import comp
import comp._internal
import comp._interp

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_fail(message, tag=None):
    """Raise a comp failure with the given message.

    Args:
        message: (str) Human-readable description
        tag: (comp.Tag | None) Failure tag; defaults to tag_fail_value
    """
    if tag is None:
        tag = comp.tag_fail_value
    fail_val = comp._interp._make_fail_value(message, tag=tag)
    raise comp.CompFail(fail_val)


def _extract_name_arg(args_val):
    """Extract the first positional string argument from args_val.

    Args:
        args_val: (Value) Arguments struct

    Returns:
        (str) The name string

    Raises:
        comp.CompFail: If arg is missing or not a string
    """
    try:
        name_val = args_val.positional(0)
    except (TypeError, IndexError):
        _make_fail("expected a name argument (text)")
    if name_val is None or not isinstance(name_val.data, str):
        _make_fail("expected a name argument (text)")
    return name_val.data


# ---------------------------------------------------------------------------
# Backend protocol
#
# Each backend implements the same set of functions that the module
# registration glues together.  The functions receive raw Python state
# (file descriptors / HANDLE values) rather than Comp Values, keeping the
# OS-specific code clean.
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    # -----------------------------------------------------------------------
    # Windows backend – NT native API via ctypes.windll.ntdll / kernel32
    # -----------------------------------------------------------------------

    import ctypes
    import ctypes.wintypes as wintypes

    _kernel32 = ctypes.windll.kernel32
    _ntdll = ctypes.windll.ntdll

    # Ensure NTSTATUS returns as unsigned
    _ntdll.NtCreateFile.restype = ctypes.c_uint32
    _ntdll.NtQueryDirectoryFile.restype = ctypes.c_uint32
    _ntdll.NtReadFile.restype = ctypes.c_uint32
    _ntdll.NtWriteFile.restype = ctypes.c_uint32
    _ntdll.NtClose.restype = ctypes.c_uint32

    # NT status
    _STATUS_SUCCESS = 0
    _STATUS_NO_MORE_FILES = 0x80000006
    _STATUS_NO_SUCH_FILE = 0xC000000F

    # Desired access masks
    _FILE_LIST_DIRECTORY = 0x00000001
    _FILE_READ_DATA = 0x00000001
    _FILE_WRITE_DATA = 0x00000002
    _FILE_ADD_FILE = 0x00000002
    _SYNCHRONIZE = 0x00100000
    _FILE_READ_ATTRIBUTES = 0x00000080
    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000

    # Share modes
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _FILE_SHARE_DELETE = 0x00000004

    # Create disposition
    _FILE_OPEN = 1
    _FILE_CREATE = 2
    _FILE_OPEN_IF = 3
    _FILE_OVERWRITE_IF = 5

    # Create options
    _FILE_DIRECTORY_FILE = 0x00000001
    _FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    _FILE_NON_DIRECTORY_FILE = 0x00000040

    # File attributes
    _FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _OBJ_CASE_INSENSITIVE = 0x00000040

    # Open directories via kernel32.CreateFileW
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _OPEN_EXISTING = 3

    # FileInformationClass for NtQueryDirectoryFile
    _FileDirectoryInformation = 1
    _FileBasicInformation = 4
    _FileStandardInformation = 5
    _FileNameInformation = 9

    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class _NtUnicodeString(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", ctypes.c_wchar_p),
        ]

    class _NtObjectAttributes(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(_NtUnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class _NtIoStatusBlock(ctypes.Structure):  # noqa: N801
        class _Status(ctypes.Union):  # noqa: N801
            _fields_ = [
                ("Status", ctypes.c_long),
                ("Pointer", ctypes.c_void_p),
            ]
        _fields_ = [
            ("u", _Status),
            ("Information", ctypes.c_size_t),
        ]

    class _NtFileDirectoryInformation(ctypes.Structure):  # noqa: N801
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
            ("FileName", ctypes.c_wchar * 1),  # variable-length, read manually
        ]

    class _NtFileBasicInfo(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("CreationTime", ctypes.c_int64),
            ("LastAccessTime", ctypes.c_int64),
            ("LastWriteTime", ctypes.c_int64),
            ("ChangeTime", ctypes.c_int64),
            ("FileAttributes", wintypes.DWORD),
        ]

    class _NtFileStandardInfo(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("AllocationSize", ctypes.c_int64),
            ("EndOfFile", ctypes.c_int64),
            ("NumberOfLinks", wintypes.DWORD),
            ("DeletePending", wintypes.BOOLEAN),
            ("Directory", wintypes.BOOLEAN),
        ]

    def _nt_open_dir(name, root_handle):
        """Open a directory handle via NtCreateFile.

        Args:
            name: (str) Directory name (relative to root if root_handle given)
            root_handle: (HANDLE | None) Parent directory handle, or None for absolute

        Returns:
            (HANDLE) NT file handle

        Raises:
            OSError: If the open fails
        """
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

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None,  # AllocationSize
            0,     # FileAttributes
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN,
            _FILE_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None,  # EaBuffer
            0,     # EaLength
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile failed with status 0x{status:08X} for {name!r}")
        return handle.value

    def _nt_open_root(path):
        """Open a filesystem root on Windows.

        Accepts a root path like 'C:/' and converts to NT-style.

        Args:
            path: (str) Root path (e.g. "C:/")

        Returns:
            (HANDLE) NT file handle for the directory
        """
        nt_path = "\\??\\" + path.replace("/", "\\")
        return _nt_open_dir(nt_path, None)

    def _nt_list_dir(handle):
        """Enumerate directory entries for a handle.

        Args:
            handle: (HANDLE) NT directory file handle

        Returns:
            (list of dict) Each dict has: name, entry_type, size, modified
        """
        buf_size = 65536
        buf = ctypes.create_string_buffer(buf_size)
        iosb = _NtIoStatusBlock()
        entries = []

        restart = True
        while True:
            status = _ntdll.NtQueryDirectoryFile(
                handle,
                None,   # Event
                None,   # ApcRoutine
                None,   # ApcContext
                ctypes.byref(iosb),
                buf,
                buf_size,
                _FileDirectoryInformation,
                False,  # ReturnSingleEntry
                None,   # FileName
                restart,
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
                    # Windows FILETIME is 100-nanosecond intervals since Jan 1, 1601
                    # Convert to Unix epoch seconds
                    modified = (entry.LastWriteTime - 116444736000000000) / 10000000
                    entries.append({
                        "name": name,
                        "entry_type": etype,
                        "size": entry.EndOfFile,
                        "modified": modified,
                    })
                if entry.NextEntryOffset == 0:
                    break
                offset += entry.NextEntryOffset

        return entries

    def _nt_stat(parent_handle, name):
        """Get metadata for a named entry relative to a parent handle.

        Opens the entry without requiring it to be a directory, so this
        works correctly for both files and directories.

        Args:
            parent_handle: (HANDLE) NT parent directory handle
            name: (str) Entry name within the directory

        Returns:
            (dict) Metadata: name, entry_type, size, modified
        """
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)

        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = parent_handle
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        # Open without _FILE_DIRECTORY_FILE to allow both files and directories
        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_READ_ATTRIBUTES | _SYNCHRONIZE,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN,
            _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile (stat) failed: 0x{status:08X} for {name!r}")

        try:
            basic_info = _NtFileBasicInfo()
            std_info = _NtFileStandardInfo()

            _kernel32.GetFileInformationByHandleEx(
                handle.value,
                0,  # FileBasicInfo
                ctypes.byref(basic_info),
                ctypes.sizeof(basic_info),
            )
            _kernel32.GetFileInformationByHandleEx(
                handle.value,
                1,  # FileStandardInfo
                ctypes.byref(std_info),
                ctypes.sizeof(std_info),
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
                "name": name,
                "entry_type": etype,
                "size": std_info.EndOfFile,
                "modified": modified,
            }
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_read_file(parent_handle, name):
        """Read a file's bytes relative to a parent directory handle.

        Args:
            parent_handle: (HANDLE) NT parent directory handle
            name: (str) File name

        Returns:
            (bytes) File contents
        """
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)

        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = parent_handle
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_READ_DATA | _SYNCHRONIZE,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ,
            _FILE_OPEN,
            _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile (read) failed: 0x{status:08X} for {name!r}")

        try:
            chunks = []
            read_buf = ctypes.create_string_buffer(65536)
            while True:
                read_iosb = _NtIoStatusBlock()
                rstat = _ntdll.NtReadFile(
                    handle.value,
                    None, None, None,
                    ctypes.byref(read_iosb),
                    read_buf,
                    len(read_buf),
                    None, None,
                )
                n = read_iosb.Information
                if n > 0:
                    chunks.append(bytes(read_buf[:n]))
                if rstat == 0x00000000 and n < len(read_buf):
                    break
                if rstat not in (_STATUS_SUCCESS, 0x00000103):  # STATUS_PENDING
                    break
            return b"".join(chunks)
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_write_file(parent_handle, name, data):
        """Write bytes to a file relative to a parent directory handle.

        Args:
            parent_handle: (HANDLE) NT parent directory handle
            name: (str) File name
            data: (bytes) Content to write
        """
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)

        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = parent_handle
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_WRITE_DATA | _SYNCHRONIZE,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None, 0,
            0,
            _FILE_OVERWRITE_IF,
            _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile (write) failed: 0x{status:08X} for {name!r}")

        try:
            buf = ctypes.create_string_buffer(data)
            write_iosb = _NtIoStatusBlock()
            wstat = _ntdll.NtWriteFile(
                handle.value,
                None, None, None,
                ctypes.byref(write_iosb),
                buf,
                len(data),
                None, None,
            )
            if wstat != _STATUS_SUCCESS:
                raise OSError(f"NtWriteFile failed: 0x{wstat:08X}")
        finally:
            _ntdll.NtClose(handle.value)

    def _nt_mkdir(parent_handle, name):
        """Create a directory relative to a parent handle.

        Args:
            parent_handle: (HANDLE) NT parent directory handle
            name: (str) New directory name
        """
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)

        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = parent_handle
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            _FILE_LIST_DIRECTORY | _SYNCHRONIZE,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_CREATE,
            _FILE_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile (mkdir) failed: 0x{status:08X} for {name!r}")
        _ntdll.NtClose(handle.value)

    def _nt_remove(parent_handle, name):
        """Remove a file or empty directory relative to a parent handle.

        Args:
            parent_handle: (HANDLE) NT parent directory handle
            name: (str) Entry to remove
        """
        us_buf = ctypes.create_unicode_buffer(name)
        us = _NtUnicodeString()
        us.Length = len(name) * 2
        us.MaximumLength = (len(name) + 1) * 2
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)

        oa = _NtObjectAttributes()
        oa.Length = ctypes.sizeof(_NtObjectAttributes)
        oa.RootDirectory = parent_handle
        oa.ObjectName = ctypes.pointer(us)
        oa.Attributes = _OBJ_CASE_INSENSITIVE
        oa.SecurityDescriptor = None
        oa.SecurityQualityOfService = None

        iosb = _NtIoStatusBlock()
        handle = wintypes.HANDLE()

        # FILE_DELETE_ON_CLOSE flag
        file_delete_on_close = 0x00001000

        status = _ntdll.NtCreateFile(
            ctypes.byref(handle),
            0x00010000 | _SYNCHRONIZE,  # DELETE | SYNCHRONIZE
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None, 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            _FILE_OPEN,
            file_delete_on_close | _FILE_SYNCHRONOUS_IO_NONALERT,
            None, 0,
        )
        if status != _STATUS_SUCCESS:
            raise OSError(f"NtCreateFile (remove) failed: 0x{status:08X} for {name!r}")
        _ntdll.NtClose(handle.value)

    def _nt_close(handle):
        """Close an NT handle.

        Args:
            handle: (HANDLE) NT handle to close
        """
        _ntdll.NtClose(handle)

    # Wrap the platform-specific functions
    _backend_open_root = _nt_open_root

    def _backend_open_at(name, parent):
        return _nt_open_dir(name, parent)

    _backend_list_dir = _nt_list_dir
    _backend_stat_at = _nt_stat
    _backend_read_file = _nt_read_file
    _backend_write_file = _nt_write_file
    _backend_mkdir = _nt_mkdir
    _backend_remove = _nt_remove
    _backend_close = _nt_close
    _path_separator = "/"

else:
    # -----------------------------------------------------------------------
    # POSIX backend – os.open / os.openat with integer file descriptors
    # -----------------------------------------------------------------------

    _O_RDONLY = os.O_RDONLY
    _O_WRONLY = os.O_WRONLY
    _O_CREAT = os.O_CREAT
    _O_TRUNC = os.O_TRUNC
    _O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)  # not on macOS

    def _posix_open_root(path):
        """Open a directory at an absolute path on POSIX.

        Args:
            path: (str) Absolute directory path

        Returns:
            (int) File descriptor for the directory
        """
        flags = _O_RDONLY | _O_DIRECTORY
        return os.open(path, flags)

    def _posix_open_at(name, parent_fd):
        """Open a sub-directory relative to parent_fd.

        Args:
            name: (str) Sub-directory name
            parent_fd: (int) Parent directory file descriptor

        Returns:
            (int) File descriptor for the sub-directory
        """
        flags = _O_RDONLY | _O_DIRECTORY
        return os.open(name, flags, dir_fd=parent_fd)

    def _posix_list_dir(fd):
        """List entries in a directory given its file descriptor.

        Args:
            fd: (int) Directory file descriptor

        Returns:
            (list of dict) Each dict has: name, entry_type, size, modified
        """
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
                    "name": entry.name,
                    "entry_type": etype,
                    "size": st.st_size,
                    "modified": st.st_mtime,
                })
        return entries

    def _posix_stat_at(parent_fd, name):
        """Get metadata for a named entry relative to a parent fd.

        Args:
            parent_fd: (int) Parent directory file descriptor
            name: (str) Entry name

        Returns:
            (dict) Metadata: name, entry_type, size, modified
        """
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
            "name": name,
            "entry_type": etype,
            "size": st.st_size,
            "modified": st.st_mtime,
        }

    def _posix_read_file(parent_fd, name):
        """Read a file's bytes relative to a parent directory fd.

        Args:
            parent_fd: (int) Parent directory file descriptor
            name: (str) File name

        Returns:
            (bytes) File contents
        """
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
        """Write bytes to a file relative to a parent directory fd.

        Args:
            parent_fd: (int) Parent directory file descriptor
            name: (str) File name
            data: (bytes) Content to write
        """
        flags = _O_WRONLY | _O_CREAT | _O_TRUNC
        fd = os.open(name, flags, 0o666, dir_fd=parent_fd)
        try:
            written = 0
            while written < len(data):
                n = os.write(fd, data[written:])
                written += n
        finally:
            os.close(fd)

    def _posix_mkdir(parent_fd, name):
        """Create a directory relative to a parent fd.

        Args:
            parent_fd: (int) Parent directory file descriptor
            name: (str) New directory name
        """
        os.mkdir(name, 0o777, dir_fd=parent_fd)

    def _posix_remove(parent_fd, name):
        """Remove a file or empty directory relative to a parent fd.

        Args:
            parent_fd: (int) Parent directory file descriptor
            name: (str) Entry to remove
        """
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISDIR(st.st_mode):
            os.rmdir(name, dir_fd=parent_fd)
        else:
            os.unlink(name, dir_fd=parent_fd)

    def _posix_close(fd):
        """Close a file descriptor.

        Args:
            fd: (int) File descriptor
        """
        os.close(fd)

    _backend_open_root = _posix_open_root
    _backend_open_at = _posix_open_at
    _backend_list_dir = _posix_list_dir
    _backend_stat_at = _posix_stat_at
    _backend_read_file = _posix_read_file
    _backend_write_file = _posix_write_file
    _backend_mkdir = _posix_mkdir
    _backend_remove = _posix_remove
    _backend_close = _posix_close
    _path_separator = "/"


# ---------------------------------------------------------------------------
# Handle state
#
# Each `handle#dir` wraps a _DirState struct that holds the raw OS handle
# and metadata.  This is stored as handle.private_data so the Comp `!pull`
# instruction can retrieve it.
# ---------------------------------------------------------------------------

class _DirState:
    """Private state stored inside a dir handle.

    Args:
        raw_handle: (int or HANDLE) OS file descriptor or Windows handle
        path: (str) Absolute path of this directory
        is_root: (bool) True if this handle was opened as a filesystem root
    """

    __slots__ = ("raw_handle", "path", "is_root", "closed")

    def __init__(self, raw_handle, path, is_root=False):
        self.raw_handle = raw_handle
        self.path = path
        self.is_root = is_root
        self.closed = False

    def __repr__(self):
        return f"<_DirState path={self.path!r} closed={self.closed}>"


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

@comp._internal.register_internal_module("fs-native")
def _create_fs_module(module):
    """Entry-centric filesystem native backend.

    Provides the low-level operations that the fs stdlib module wraps.
    All operations revolve around entry values — structs with entry-type,
    name, root fields plus internal _handle/_parent fields for capability
    tracking.
    """

    dir_tag = module.add_tag("dir")

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------
    _dir_etype_tag = module.add_tag("entry-type.dir")
    _file_etype_tag = module.add_tag("entry-type.file")
    _link_etype_tag = module.add_tag("entry-type.link")
    _missing_etype_tag = module.add_tag("entry-type.missing")

    _entry_type_tags = {
        "dir": _dir_etype_tag,
        "file": _file_etype_tag,
        "link": _link_etype_tag,
        "missing": _missing_etype_tag,
    }

    # ------------------------------------------------------------------
    # Struct field keys (pre-allocated for efficiency)
    # ------------------------------------------------------------------
    _key_entry_type = comp.Value.from_python("entry-type")
    _key_name = comp.Value.from_python("name")
    _key_path = comp.Value.from_python("path")
    _key_root = comp.Value.from_python("root")
    _key_vfs = comp.Value.from_python("vfs")
    _key_handle = comp.Value.from_python("handle")
    _key_parent = comp.Value.from_python("parent")
    _key_size = comp.Value.from_python("size")
    _key_modified = comp.Value.from_python("modified")

    # Datetime struct keys (matching time.comp date-time shape)
    _key_year = comp.Value.from_python("year")
    _key_month = comp.Value.from_python("month")
    _key_day = comp.Value.from_python("day")
    _key_hour = comp.Value.from_python("hour")
    _key_minute = comp.Value.from_python("minute")
    _key_second = comp.Value.from_python("second")
    _key_zone = comp.Value.from_python("zone")
    _key_offset_sec = comp.Value.from_python("offset-sec")
    _utc_zone_val = comp.Value({
        _key_name: comp.Value.from_python("UTC"),
        _key_offset_sec: comp.Value.from_python(0),
    })

    # ------------------------------------------------------------------
    # Handle helpers
    # ------------------------------------------------------------------

    def _make_dir_handle(raw_handle, path, is_root=False):
        """Wrap a raw OS handle into a Comp handle#dir Value."""
        state = _DirState(raw_handle, path, is_root)
        handle = comp.HandleInstance(
            tag=dir_tag,
            module_id=module.token,
            private_data=comp.Value(state),
        )
        return comp.Value(handle)

    def _unwrap_dir_handle(val, op_name):
        """Extract _DirState from a handle#dir Value."""
        inst = val.data
        if not isinstance(inst, comp.HandleInstance):
            _make_fail(f"{op_name}: expected handle#dir, got {val.format()}")
        if inst.tag is not dir_tag:
            _make_fail(f"{op_name}: expected handle#dir, got handle#{inst.tag.qualified}")
        if inst.released:
            _make_fail(f"{op_name}: handle has been released")
        if inst.private_data is None:
            _make_fail(f"{op_name}: handle has no state")
        state = inst.private_data.data
        if not isinstance(state, _DirState):
            _make_fail(f"{op_name}: handle has unexpected internal state")
        if state.closed:
            _make_fail(f"{op_name}: handle is closed")
        return state

    # ------------------------------------------------------------------
    # Entry helpers
    # ------------------------------------------------------------------

    def _get_entry_handle(entry_val, op_name):
        """Extract _DirState from a dir entry's stashed handle."""
        if not isinstance(entry_val.data, dict):
            _make_fail(f"{op_name}: expected entry struct")
        if entry_val.stash is None:
            _make_fail(f"{op_name}: entry has no directory handle (not a navigable directory)")
        mod_stash = entry_val.stash.get(module.token)
        if mod_stash is None or not isinstance(mod_stash.data, dict):
            _make_fail(f"{op_name}: entry has no directory handle (not a navigable directory)")
        handle_val = mod_stash.data.get(_key_handle)
        if handle_val is None:
            _make_fail(f"{op_name}: entry has no directory handle (not a navigable directory)")
        return _unwrap_dir_handle(handle_val, op_name)

    def _get_parent_from_stash(entry_val):
        """Get the parent entry Value from the stash."""
        if entry_val.stash is None:
            return None
        mod_stash = entry_val.stash.get(module.token)
        if mod_stash is None or not isinstance(mod_stash.data, dict):
            return None
        return mod_stash.data.get(_key_parent)

    def _set_parent_stash(entry_val, parent_val, handle_val=None):
        """Store the parent entry and optional handle in the stash."""
        if entry_val.stash is None:
            entry_val.stash = {}
        stash_data = {_key_parent: parent_val}
        if handle_val is not None:
            stash_data[_key_handle] = handle_val
        entry_val.stash[module.token] = comp.Value(stash_data)

    def _get_entry_parent_handle(entry_val, op_name):
        """Extract _DirState from an entry's parent's _handle field."""
        if not isinstance(entry_val.data, dict):
            _make_fail(f"{op_name}: expected entry struct")
        parent_val = _get_parent_from_stash(entry_val)
        if parent_val is None or not isinstance(parent_val.data, dict):
            _make_fail(f"{op_name}: entry has no parent (is this a root?)")
        return _get_entry_handle(parent_val, op_name)

    def _get_entry_name(entry_val, op_name):
        """Extract the name string from an entry."""
        if not isinstance(entry_val.data, dict):
            _make_fail(f"{op_name}: expected entry struct")
        name_val = entry_val.data.get(_key_name)
        if name_val is None or not isinstance(name_val.data, str):
            _make_fail(f"{op_name}: entry has no valid name")
        return name_val.data

    _nil_val = comp.Value(comp.tag_nil)

    def _epoch_to_datetime(epoch_secs):
        """Convert epoch seconds to a Comp date-time struct Value."""
        dt = _datetime.datetime.fromtimestamp(epoch_secs, tz=_datetime.timezone.utc)
        return comp.Value({
            _key_year: comp.Value.from_python(dt.year),
            _key_month: comp.Value.from_python(dt.month),
            _key_day: comp.Value.from_python(dt.day),
            _key_hour: comp.Value.from_python(dt.hour),
            _key_minute: comp.Value.from_python(dt.minute),
            _key_second: comp.Value.from_python(dt.second),
            _key_zone: _utc_zone_val,
        })

    def _make_root_entry(handle_val, path):
        """Create a root entry value.

        Root entries have root pointing to themselves and vfs=nil
        (to be set by the backend). Handle is stored in stash.
        """
        name = path.rstrip("/").rsplit("/", 1)[-1] or path
        entry = {
            _key_entry_type: comp.Value(_dir_etype_tag),
            _key_name: comp.Value.from_python(name),
            _key_path: comp.Value.from_python(path),
            _key_root: _nil_val,  # placeholder, set to self below
            _key_vfs: _nil_val,
        }
        result = comp.Value(entry)
        result.data[_key_root] = result  # root references itself
        _set_parent_stash(result, _nil_val, handle_val)
        return result

    def _make_child_entry(parent_entry, etype_tag, name, handle_val=None, extra_meta=None):
        """Create a child entry value.

        The root field is inherited from the parent (root entries point
        to themselves, so $.root always reaches a root-entry).
        Parent and handle are stored in stash, not in the visible struct.
        """
        root_val = parent_entry.data.get(_key_root, parent_entry)

        # Compute path from parent
        parent_path_val = parent_entry.data.get(_key_path)
        if parent_path_val and isinstance(parent_path_val.data, str):
            child_path = parent_path_val.data.rstrip("/") + "/" + name
        else:
            child_path = name

        entry = {
            _key_entry_type: comp.Value(etype_tag),
            _key_name: comp.Value.from_python(name),
            _key_path: comp.Value.from_python(child_path),
            _key_root: root_val,
        }
        if extra_meta:
            entry.update(extra_meta)
        result = comp.Value(entry)
        _set_parent_stash(result, parent_entry, handle_val)
        return result

    def _entry_is_struct(val):
        """Check if a value looks like an entry struct."""
        return isinstance(val.data, dict) and _key_entry_type in val.data

    # ------------------------------------------------------------------
    # Callable implementations
    # ------------------------------------------------------------------

    def _open_root(input_val, args_val, frame):
        """Open an absolute path as a root entry.

        Resolves the path from the real filesystem root (/ or C:/).
        Navigates down through segments, returning the final entry
        with root pointing to the filesystem root.

        Input ($): text path
        Args: optional :vfs=<tag> to set on the root entry
        Returns: entry (dir)
        """
        if not isinstance(input_val.data, str):
            _make_fail("open: input must be a text path")
        path = input_val.data.replace("\\", "/")

        # Determine the filesystem root and remaining segments
        if sys.platform == "win32":
            # Handle various path forms: C:/..., /C/..., /Users/...
            if len(path) >= 2 and path[1] == ":":
                # C:/Users/... -> root="C:/", segments from rest
                fs_root = path[0].upper() + ":/"
                rest = path[3:] if len(path) > 3 else ""
            elif len(path) >= 3 and path[0] == "/" and path[2] == "/":
                # /c/Users/... (MSYS2 style) -> C:/
                fs_root = path[1].upper() + ":/"
                rest = path[3:] if len(path) > 3 else ""
            elif path.startswith("/"):
                # /Users/... -> use current drive
                drive = os.path.splitdrive(os.getcwd())[0]
                fs_root = drive + "/"
                rest = path[1:]
            else:
                _make_fail(f"open: not an absolute path: {path!r}")
        else:
            if not path.startswith("/"):
                _make_fail(f"open: not an absolute path: {path!r}")
            fs_root = "/"
            rest = path[1:]

        # Open the filesystem root
        try:
            raw = _backend_open_root(fs_root)
        except OSError as e:
            _make_fail(f"open: {e}")
        handle_val = _make_dir_handle(raw, fs_root, is_root=True)
        root_entry = _make_root_entry(handle_val, fs_root)

        # Set vfs tag from named arg if provided
        if isinstance(args_val.data, dict):
            vfs_val = args_val.data.get(comp.Value.from_python("vfs-tag"))
            if vfs_val is not None:
                root_entry.data[_key_vfs] = vfs_val

        # Navigate down through path segments
        segments = [s for s in rest.split("/") if s]
        if not segments:
            return root_entry

        current_entry = root_entry
        current_state = _unwrap_dir_handle(handle_val, "open")

        for seg in segments:
            try:
                raw = _backend_open_at(seg, current_state.raw_handle)
            except OSError as e:
                _make_fail(f"open: cannot navigate through '{seg}': {e}")
            child_path = current_state.path.rstrip("/") + "/" + seg
            child_handle = _make_dir_handle(raw, child_path)
            current_entry = _make_child_entry(current_entry, _dir_etype_tag, seg, child_handle)
            current_state = _unwrap_dir_handle(child_handle, "open")

        return current_entry

    def _cwd(input_val, args_val, frame):
        """Return the current working directory as a text path.

        Input ($): ignored
        Returns: text path (forward slashes)
        """
        return comp.Value.from_python(os.getcwd().replace("\\", "/"))

    def _entry_at(input_val, args_val, frame):
        """Look up a named child of a directory entry.

        Stats the child to determine its type. Returns a missing entry
        if the child does not exist. For dir children, opens a handle
        so the entry is navigable.

        Supports multi-segment paths: "a/b/file.txt" navigates through
        intermediate directories.

        Input ($): entry (dir with handle)
        Args: first positional text — child name or path
        Returns: entry
        """
        state = _get_entry_handle(input_val, "at")
        name = _extract_name_arg(args_val)

        # Split multi-segment paths
        segments = [s for s in name.replace("\\", "/").split("/") if s]
        if not segments:
            _make_fail("at: name cannot be empty")

        current_entry = input_val
        current_state = state

        # Navigate intermediate segments (must be existing dirs)
        for seg in segments[:-1]:
            try:
                info = _backend_stat_at(current_state.raw_handle, seg)
            except OSError as e:
                _make_fail(f"at: cannot navigate through '{seg}': {e}")
            if info.get("entry_type") != "dir":
                _make_fail(f"at: '{seg}' is not a directory")
            try:
                raw = _backend_open_at(seg, current_state.raw_handle)
            except OSError as e:
                _make_fail(f"at: cannot open directory '{seg}': {e}")
            child_path = current_state.path.rstrip("/") + "/" + seg
            handle_val = _make_dir_handle(raw, child_path)
            current_entry = _make_child_entry(current_entry, _dir_etype_tag, seg, handle_val)
            current_state = _unwrap_dir_handle(handle_val, "at")

        # Stat the final segment
        final_name = segments[-1]
        try:
            info = _backend_stat_at(current_state.raw_handle, final_name)
        except OSError:
            return _make_child_entry(current_entry, _missing_etype_tag, final_name)

        etype_tag = _entry_type_tags.get(info.get("entry_type", "missing"), _missing_etype_tag)
        extra = {}
        if "size" in info:
            extra[_key_size] = comp.Value.from_python(info["size"])
        if "modified" in info:
            extra[_key_modified] = _epoch_to_datetime(info["modified"])

        # For dirs, open a handle so the entry is navigable
        handle_val = None
        if etype_tag is _dir_etype_tag:
            try:
                raw = _backend_open_at(final_name, current_state.raw_handle)
                child_path = current_state.path.rstrip("/") + "/" + final_name
                handle_val = _make_dir_handle(raw, child_path)
            except OSError:
                pass
        return _make_child_entry(current_entry, etype_tag, final_name, handle_val, extra)

    def _entry_file(input_val, args_val, frame):
        """Ensure a file entry exists within a directory.

        If the name exists as a file, returns the entry. If nothing exists,
        creates an empty file. Fails if something exists with a different type.

        Input ($): entry (dir with handle)
        Args: first positional text — file name
        Returns: entry (file)
        """
        state = _get_entry_handle(input_val, "file")
        name = _extract_name_arg(args_val)

        try:
            info = _backend_stat_at(state.raw_handle, name)
            etype = info.get("entry_type", "missing")
            if etype != "file":
                _make_fail(f"file: '{name}' exists but is a {etype}, not a file")
            extra = {}
            if "size" in info:
                extra[_key_size] = comp.Value.from_python(info["size"])
            if "modified" in info:
                extra[_key_modified] = _epoch_to_datetime(info["modified"])
            return _make_child_entry(input_val, _file_etype_tag, name, extra_meta=extra)
        except OSError:
            pass

        # File doesn't exist — create empty file
        try:
            _backend_write_file(state.raw_handle, name, b"")
        except OSError as e:
            _make_fail(f"file: cannot create '{name}': {e}")
        return _make_child_entry(input_val, _file_etype_tag, name)

    def _entry_dir(input_val, args_val, frame):
        """Ensure a directory entry exists within a directory.

        If the name exists as a directory, opens and returns it. If nothing
        exists, creates the directory. Fails if something exists with a
        different type.

        Supports multi-segment paths: "a/b/c" ensures each segment exists
        as a directory.

        Input ($): entry (dir with handle)
        Args: first positional text — directory name or path
        Returns: entry (dir with handle)
        """
        state = _get_entry_handle(input_val, "dir")
        name = _extract_name_arg(args_val)

        # Split multi-segment paths
        segments = [s for s in name.replace("\\", "/").split("/") if s]
        if not segments:
            _make_fail("dir: name cannot be empty")

        current_entry = input_val
        current_state = state

        for seg in segments:
            # Check if it exists
            try:
                info = _backend_stat_at(current_state.raw_handle, seg)
                etype = info.get("entry_type", "missing")
                if etype != "dir":
                    _make_fail(f"dir: '{seg}' exists but is a {etype}, not a directory")
            except OSError:
                # Doesn't exist — create it
                try:
                    _backend_mkdir(current_state.raw_handle, seg)
                except OSError as e:
                    _make_fail(f"dir: cannot create '{seg}': {e}")

            # Open a handle for navigation
            try:
                raw = _backend_open_at(seg, current_state.raw_handle)
            except OSError as e:
                _make_fail(f"dir: cannot open '{seg}': {e}")
            child_path = current_state.path.rstrip("/") + "/" + seg
            handle_val = _make_dir_handle(raw, child_path)
            current_entry = _make_child_entry(current_entry, _dir_etype_tag, seg, handle_val)
            current_state = _unwrap_dir_handle(handle_val, "dir")

        return current_entry

    def _entry_read(input_val, args_val, frame):
        """Read the content of a file entry as text.

        Input ($): entry (file, with parent that has a handle)
        Returns: text (UTF-8 decoded content)
        """
        parent_state = _get_entry_parent_handle(input_val, "read")
        name = _get_entry_name(input_val, "read")
        try:
            data = _backend_read_file(parent_state.raw_handle, name)
        except OSError as e:
            _make_fail(f"read: {e}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            _make_fail(f"read: file is not valid UTF-8: {e}")
        return comp.Value.from_python(text)

    def _entry_write(input_val, args_val, frame):
        """Write text content to a file entry.

        Creates the file if it does not exist; overwrites if it does.

        Input ($): entry (file, with parent that has a handle)
        Args: first positional text — content to write
        Returns: nil
        """
        parent_state = _get_entry_parent_handle(input_val, "write")
        name = _get_entry_name(input_val, "write")
        try:
            content_val = args_val.positional(0)
        except (TypeError, IndexError):
            _make_fail("write: expected content argument (text)")
        if content_val is None or not isinstance(content_val.data, str):
            _make_fail("write: content must be text")
        data = content_val.data.encode("utf-8")
        try:
            _backend_write_file(parent_state.raw_handle, name, data)
        except OSError as e:
            _make_fail(f"write: {e}")
        return comp.Value.from_python(None)

    def _entry_list(input_val, args_val, frame):
        """List all children of a directory entry.

        Returns entries with whatever metadata the backend provides cheaply
        (on Windows: size+modified; on Linux: entry-type from d_type).
        Listed entries have _parent set to the input dir entry so that
        read/write/remove work on them directly.

        Input ($): entry (dir with handle)
        Returns: struct of entry values (unnamed fields)
        """
        state = _get_entry_handle(input_val, "list")
        try:
            entries = _backend_list_dir(state.raw_handle)
        except OSError as e:
            _make_fail(f"list: {e}")

        items = {}
        for e in entries:
            key = comp.Unnamed()
            etype_tag = _entry_type_tags.get(e.get("entry_type", "missing"), _missing_etype_tag)
            extra = {}
            if "size" in e:
                extra[_key_size] = comp.Value.from_python(e["size"])
            if "modified" in e:
                extra[_key_modified] = _epoch_to_datetime(e["modified"])
            items[key] = _make_child_entry(input_val, etype_tag, e["name"], extra_meta=extra)
        return comp.Value(items)

    def _entry_remove(input_val, args_val, frame):
        """Remove a file or empty directory.

        Input ($): entry (with parent that has a handle)
        Returns: nil
        """
        parent_state = _get_entry_parent_handle(input_val, "remove")
        name = _get_entry_name(input_val, "remove")
        try:
            _backend_remove(parent_state.raw_handle, name)
        except OSError as e:
            _make_fail(f"remove: {e}")
        return comp.Value.from_python(None)

    def _entry_meta(input_val, args_val, frame):
        """Return an enriched copy of an entry with full stat metadata.

        Re-stats the entry and returns a new entry value with size,
        modified, and any other metadata the backend provides.

        Input ($): entry (with parent in stash)
        Returns: entry (enriched with metadata fields)
        """
        parent_state = _get_entry_parent_handle(input_val, "meta")
        name = _get_entry_name(input_val, "meta")
        try:
            info = _backend_stat_at(parent_state.raw_handle, name)
        except OSError as e:
            _make_fail(f"meta: {e}")

        etype_tag = _entry_type_tags.get(info.get("entry_type", "missing"), _missing_etype_tag)
        extra = {}
        if "size" in info:
            extra[_key_size] = comp.Value.from_python(info["size"])
        if "modified" in info:
            extra[_key_modified] = _epoch_to_datetime(info["modified"])

        parent_val = _get_parent_from_stash(input_val)
        # Get handle from stash for dir entries
        handle_val = None
        if input_val.stash:
            mod_stash = input_val.stash.get(module.token)
            if mod_stash and isinstance(mod_stash.data, dict):
                handle_val = mod_stash.data.get(_key_handle)
        return _make_child_entry(
            parent_val,
            etype_tag, name, handle_val, extra,
        )

    def _entry_up(input_val, args_val, frame):
        """Return the parent entry.

        Returns nil for root entries.

        Input ($): entry
        Returns: entry (parent) or nil
        """
        if not isinstance(input_val.data, dict):
            _make_fail("up: expected entry struct")
        parent_val = _get_parent_from_stash(input_val)
        if parent_val is None:
            return _nil_val
        return parent_val

    def _entry_refresh(input_val, args_val, frame):
        """Return a fresh entry with the same identity but no cached metadata.

        The new entry has an empty known-children cache. Other holders of
        the old entry are unaffected (snapshot semantics).

        Input ($): entry
        Returns: entry (fresh, same capability)
        """
        if not isinstance(input_val.data, dict):
            _make_fail("refresh: expected entry struct")
        entry = {}
        for key in (_key_entry_type, _key_name, _key_path, _key_root, _key_vfs):
            val = input_val.data.get(key)
            if val is not None:
                entry[key] = val
        result = comp.Value(entry)
        if input_val.stash:
            result.stash = dict(input_val.stash)
        return result

    def _close_dir(input_val, args_val, frame):
        """Explicitly close a handle#dir, releasing the OS resource."""
        inst = input_val.data
        if not isinstance(inst, comp.HandleInstance):
            _make_fail("close-dir: expected handle#dir")
        if inst.tag is not dir_tag:
            _make_fail(f"close-dir: expected handle#dir, got handle#{inst.tag.qualified}")
        if inst.released:
            return comp.Value.from_python(None)
        if inst.private_data is None:
            return comp.Value.from_python(None)
        state = inst.private_data.data
        if isinstance(state, _DirState) and not state.closed:
            try:
                _backend_close(state.raw_handle)
            except OSError:
                pass
            state.closed = True
        return comp.Value.from_python(None)

    def _drop_handle(input_val, args_val, frame):
        """Auto-close a handle#dir when it is dropped."""
        return _close_dir(input_val, args_val, frame)

    def _basename_of(input_val, args_val, frame):
        """Return the last path component (basename) of a path string."""
        if not isinstance(input_val.data, str):
            _make_fail("basename-of: input must be text")
        path = input_val.data
        sep_idx = max(path.rfind("/"), path.rfind("\\"))
        if sep_idx < 0:
            return comp.Value.from_python(path)
        return comp.Value.from_python(path[sep_idx + 1:])

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    module.add_callable("open-root", _open_root, input_shape=comp.shape_text)
    module.add_callable("cwd", _cwd)
    module.add_callable("entry-at", _entry_at)
    module.add_callable("entry-file", _entry_file)
    module.add_callable("entry-dir", _entry_dir)
    module.add_callable("entry-read", _entry_read)
    module.add_callable("entry-write", _entry_write)
    module.add_callable("entry-list", _entry_list)
    module.add_callable("entry-remove", _entry_remove)
    module.add_callable("entry-meta", _entry_meta)
    module.add_callable("entry-up", _entry_up)
    module.add_callable("entry-refresh", _entry_refresh)
    module.add_callable("basename-of", _basename_of, input_shape=comp.shape_text, pure=True)
    module.add_callable("close-dir", _close_dir)
    module.add_callable("drop-dir&", _drop_handle)
