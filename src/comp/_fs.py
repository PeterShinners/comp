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
        us.Buffer = us_buf

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
        """Open the root absolute path on Windows.

        Converts the Win32 path to an NT-style \\??\\-prefixed path.

        Args:
            path: (str) Absolute Win32 path (e.g. "C:\\Users\\alice")

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
        us.Buffer = us_buf

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
        us.Buffer = us_buf

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
        us.Buffer = us_buf

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
        us.Buffer = us_buf

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
        us.Buffer = us_buf

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
    _path_separator = "\\"

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
    """Filesystem native backend: open-root, cwd, open-at, list-at, stat-at, read-at, write-at, mkdir-at, remove-at, path-of, close-dir."""

    dir_tag = module.add_tag("dir")

    # ------------------------------------------------------------------
    # Internal helpers – closures over dir_tag and module
    # ------------------------------------------------------------------

    def _make_dir_handle(raw_handle, path, is_root=False):
        """Wrap a raw OS handle into a Comp handle#dir Value.

        Args:
            raw_handle: OS handle (int fd or Windows HANDLE)
            path: (str) Absolute path
            is_root: (bool) Whether this is a root-opened handle

        Returns:
            (Value) A handle#dir value
        """
        state = _DirState(raw_handle, path, is_root)
        handle = comp.HandleInstance(
            tag=dir_tag,
            module_id=module.token,
            private_data=comp.Value(state),
        )
        return comp.Value(handle)

    def _unwrap_dir_handle(val, op_name):
        """Extract _DirState from a handle#dir Value.

        Args:
            val: (Value) A handle#dir value
            op_name: (str) Operation name for error messages

        Returns:
            (_DirState) The directory state

        Raises:
            comp.CompFail: If val is not a valid, open handle#dir
        """
        inst = val.data
        if not isinstance(inst, comp.HandleInstance):
            _make_fail(f"{op_name}: expected handle#dir, got {val.format()}")
        if inst.tag is not dir_tag:
            _make_fail(f"{op_name}: expected handle#dir, got handle#{inst.tag.qualified}")
        if inst.released:
            _make_fail(f"{op_name}: handle#dir has been released")
        if inst.private_data is None:
            _make_fail(f"{op_name}: handle#dir has no state")
        state = inst.private_data.data
        if not isinstance(state, _DirState):
            _make_fail(f"{op_name}: handle#dir has unexpected internal state")
        if state.closed:
            _make_fail(f"{op_name}: handle#dir is already closed")
        return state

    def _entry_to_value(entry_dict, parent_path, fs_type_tag):
        """Convert an OS entry metadata dict to a Comp struct Value.

        Args:
            entry_dict: (dict) with name, entry_type, size, modified
            parent_path: (str) Absolute path of the parent directory
            fs_type_tag: (Tag) The fs-type tag for this entry

        Returns:
            (Value) Comp struct suitable for the entry shape
        """
        etype_str = entry_dict.get("entry_type", "missing")
        etype_tag = _entry_type_tags.get(etype_str, _entry_type_tags["missing"])
        sep = _path_separator
        name = entry_dict["name"]
        path = parent_path.rstrip(sep) + sep + name
        return comp.Value.from_python({
            "fs-type": comp.Value(fs_type_tag),
            "entry-type": comp.Value(etype_tag),
            "name": name,
            "path": path,
            "size": entry_dict.get("size", 0),
            "modified": entry_dict.get("modified", 0.0),
        })

    # ------------------------------------------------------------------
    # Tags for entry-type (dir, file, link, missing) and fs-type (disk)
    # ------------------------------------------------------------------
    _disk_tag = module.add_tag("disk")
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
    # Callable implementations
    # ------------------------------------------------------------------

    def _open_root(input_val, args_val, frame):
        """Open a directory at an absolute path, returning a handle#dir.

        Input ($): text — the absolute path to open
        Args: none

        Returns:
            (Value) handle#dir

        Usage from Comp:
            !my root ["/home/user" | fs.open-root]
        """
        if not isinstance(input_val.data, str):
            _make_fail("open-root: input must be a text path")
        path = input_val.data
        try:
            raw = _backend_open_root(path)
        except OSError as e:
            _make_fail(f"open-root: {e}", tag=comp.tag_fail_value)
        return _make_dir_handle(raw, path, is_root=True)

    def _cwd(input_val, args_val, frame):
        """Open the current working directory, returning a handle#dir.

        Input ($): ignored (pass nil)
        Args: none

        Returns:
            (Value) handle#dir for the cwd

        Usage from Comp:
            !my here [nil | fs.cwd]
        """
        path = os.getcwd()
        try:
            raw = _backend_open_root(path)
        except OSError as e:
            _make_fail(f"cwd: {e}", tag=comp.tag_fail_value)
        return _make_dir_handle(raw, path, is_root=True)

    def _open_at(input_val, args_val, frame):
        """Open a sub-directory relative to a handle#dir.

        Input ($): handle#dir — parent directory handle
        Args: first positional text — sub-directory name

        Returns:
            (Value) handle#dir for the sub-directory

        Usage from Comp:
            !my sub [$dir | fs.open-at "subdir"]
        """
        state = _unwrap_dir_handle(input_val, "open-at")
        name = _extract_name_arg(args_val)
        try:
            raw = _backend_open_at(name, state.raw_handle)
        except OSError as e:
            _make_fail(f"open-at: {e}", tag=comp.tag_fail_value)
        child_path = state.path.rstrip(_path_separator) + _path_separator + name
        return _make_dir_handle(raw, child_path)

    def _list_at(input_val, args_val, frame):
        """List directory entries relative to a handle#dir.

        Input ($): handle#dir

        Returns:
            (Value) struct of entry metadata structs (unnamed fields)

        Usage from Comp:
            !my entries [$dir | fs.list-at]
        """
        state = _unwrap_dir_handle(input_val, "list-at")
        try:
            entries = _backend_list_dir(state.raw_handle)
        except OSError as e:
            _make_fail(f"list-at: {e}", tag=comp.tag_fail_value)

        items = {}
        for e in entries:
            key = comp.Unnamed()
            items[key] = _entry_to_value(e, state.path, _disk_tag)
        return comp.Value(items)

    def _stat_at(input_val, args_val, frame):
        """Get metadata for a named entry relative to a handle#dir.

        Input ($): handle#dir
        Args: first positional text — entry name

        Returns:
            (Value) entry metadata struct

        Usage from Comp:
            !my info [$dir | fs.stat-at "notes.txt"]
        """
        state = _unwrap_dir_handle(input_val, "stat-at")
        name = _extract_name_arg(args_val)
        try:
            info = _backend_stat_at(state.raw_handle, name)
        except OSError as e:
            _make_fail(f"stat-at: {e}", tag=comp.tag_fail_value)
        return _entry_to_value(info, state.path, _disk_tag)

    def _read_at(input_val, args_val, frame):
        """Read a file's contents as text relative to a handle#dir.

        Input ($): handle#dir
        Args: first positional text — file name

        Returns:
            (Value) text content (UTF-8 decoded)

        Usage from Comp:
            !my text [$dir | fs.read-at "readme.txt"]
        """
        state = _unwrap_dir_handle(input_val, "read-at")
        name = _extract_name_arg(args_val)
        try:
            data = _backend_read_file(state.raw_handle, name)
        except OSError as e:
            _make_fail(f"read-at: {e}", tag=comp.tag_fail_value)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            _make_fail(f"read-at: file is not valid UTF-8: {e}")
        return comp.Value.from_python(text)

    def _write_at(input_val, args_val, frame):
        """Write text to a file relative to a handle#dir.

        Input ($): handle#dir
        Args:
            first positional text — file name
            second positional text — content to write

        Returns:
            (Value) nil

        Usage from Comp:
            [$dir | fs.write-at "out.txt" "hello world"]
        """
        state = _unwrap_dir_handle(input_val, "write-at")
        name = _extract_name_arg(args_val)
        try:
            content_val = args_val.positional(1)
        except (TypeError, IndexError):
            _make_fail("write-at: expected content argument (text)")
        if content_val is None or not isinstance(content_val.data, str):
            _make_fail("write-at: content must be text")
        data = content_val.data.encode("utf-8")
        try:
            _backend_write_file(state.raw_handle, name, data)
        except OSError as e:
            _make_fail(f"write-at: {e}", tag=comp.tag_fail_value)
        return comp.Value.from_python(None)

    def _mkdir_at(input_val, args_val, frame):
        """Create a directory relative to a handle#dir.

        Input ($): handle#dir
        Args: first positional text — directory name to create

        Returns:
            (Value) nil

        Usage from Comp:
            [$dir | fs.mkdir-at "new-folder"]
        """
        state = _unwrap_dir_handle(input_val, "mkdir-at")
        name = _extract_name_arg(args_val)
        try:
            _backend_mkdir(state.raw_handle, name)
        except OSError as e:
            _make_fail(f"mkdir-at: {e}", tag=comp.tag_fail_value)
        return comp.Value.from_python(None)

    def _remove_at(input_val, args_val, frame):
        """Remove a file or empty directory relative to a handle#dir.

        Input ($): handle#dir
        Args: first positional text — entry name to remove

        Returns:
            (Value) nil

        Usage from Comp:
            [$dir | fs.remove-at "old-file.txt"]
        """
        state = _unwrap_dir_handle(input_val, "remove-at")
        name = _extract_name_arg(args_val)
        try:
            _backend_remove(state.raw_handle, name)
        except OSError as e:
            _make_fail(f"remove-at: {e}", tag=comp.tag_fail_value)
        return comp.Value.from_python(None)

    def _path_of(input_val, args_val, frame):
        """Get the absolute path stored in a handle#dir.

        Input ($): handle#dir

        Returns:
            (Value) text path

        Usage from Comp:
            !my path [$dir | fs.path-of]
        """
        state = _unwrap_dir_handle(input_val, "path-of")
        return comp.Value.from_python(state.path)

    def _close_dir(input_val, args_val, frame):
        """Explicitly close a handle#dir, releasing the OS resource.

        Input ($): handle#dir

        Returns:
            (Value) nil

        Usage from Comp:
            [$dir | fs.close-dir]
        """
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
        """Auto-close a handle#dir when it is dropped.

        Called automatically by the interpreter when a handle goes out of scope.
        Delegates to close-dir behavior.
        """
        return _close_dir(input_val, args_val, frame)

    def _exists_at(input_val, args_val, frame):
        """Check if a named entry exists relative to a handle#dir.

        Input ($): handle#dir
        Args: first positional text — entry name

        Returns:
            (Value) bool.true if the entry exists, bool.false otherwise

        Usage from Comp:
            !my found [$dir | fsn.exists-at "notes.txt"]
        """
        state = _unwrap_dir_handle(input_val, "exists-at")
        name = _extract_name_arg(args_val)
        try:
            _backend_stat_at(state.raw_handle, name)
            return comp.Value(comp.tag_true)
        except OSError:
            return comp.Value(comp.tag_false)

    def _basename_of(input_val, args_val, frame):
        """Return the last path component (basename) of a path string.

        Works with both "/" and "\\" separators.

        Input ($): text path

        Returns:
            (Value) text basename

        Usage from Comp:
            !my name ["/home/user/docs" | fsn.basename-of]
        """
        if not isinstance(input_val.data, str):
            _make_fail("basename-of: input must be text")
        path = input_val.data
        # Find the last occurrence of either separator
        sep_idx = max(path.rfind("/"), path.rfind("\\"))
        if sep_idx < 0:
            return comp.Value.from_python(path)
        return comp.Value.from_python(path[sep_idx + 1:])

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    module.add_callable("open-root", _open_root, input_shape=comp.shape_text)
    module.add_callable("cwd", _cwd)
    module.add_callable("open-at", _open_at)
    module.add_callable("list-at", _list_at)
    module.add_callable("stat-at", _stat_at)
    module.add_callable("exists-at", _exists_at)
    module.add_callable("read-at", _read_at)
    module.add_callable("write-at", _write_at)
    module.add_callable("mkdir-at", _mkdir_at)
    module.add_callable("remove-at", _remove_at)
    module.add_callable("path-of", _path_of)
    module.add_callable("basename-of", _basename_of, input_shape=comp.shape_text, pure=True)
    module.add_callable("close-dir", _close_dir)
    module.add_callable("drop-dir&", _drop_handle)
