"""
Determine whether the target is being run under QEMU.
"""

import os
from typing import Any
from typing import Optional

import gdb
import psutil

import pwndbg.gdblib.remote

# TODO: `import pwndbg.gdblib.events` leads to a circular import
from pwndbg.gdblib.events import start


@pwndbg.lib.cache.cache_until("stop")
def is_qemu() -> bool:
    if not pwndbg.gdblib.remote.is_remote():
        return False

    # Example:
    # pwndbg> maintenance packet Qqemu.sstepbits
    # sending: "Qqemu.sstepbits"
    # received: "ENABLE=1,NOIRQ=2,NOTIMER=4"
    response = gdb.execute("maintenance packet Qqemu.sstepbits", to_string=True, from_tty=False)

    return "ENABLE=" in response


@pwndbg.lib.cache.cache_until("stop")
def is_usermode() -> bool:
    if not pwndbg.gdblib.remote.is_remote():
        return False

    # There is also 'qAttached' - maybe we can use it too?
    # for qemu user though it returned "0"?
    # Try with:
    #    qemu-x86_64 -g 1234 `which ps`
    #    gdb -nx `which ps` -ex 'target remote :1234'
    response = gdb.execute("maintenance packet qOffsets", to_string=True, from_tty=False)

    return "Text=" in response


@pwndbg.lib.cache.cache_until("stop")
def is_qemu_usermode() -> bool:
    """Returns ``True`` if the target remote is being run under
    QEMU usermode emulation."""

    return is_qemu() and is_usermode()


@pwndbg.lib.cache.cache_until("stop")
def is_qemu_kernel() -> bool:
    return is_qemu() and not is_usermode()


@start
@pwndbg.lib.cache.cache_until("stop")
def root() -> Optional[Any]:
    if not is_qemu_usermode():
        return None

    binfmt_root = "/etc/qemu-binfmt/%s/" % pwndbg.gdblib.arch.qemu

    if not os.path.isdir(binfmt_root):
        return None

    gdb.execute("set sysroot " + binfmt_root, from_tty=False)

    return binfmt_root


@pwndbg.lib.cache.cache_until("start")
def pid():
    """Find the PID of the qemu usermode binary which we are
    talking to.
    """
    # Find all inodes in our process which are connections.
    targets = set(c.raddr for c in psutil.Process().connections())

    # No targets? :(
    if not targets:
        return 0

    for process in psutil.process_iter():
        if not process.name().startswith("qemu"):
            continue

        try:
            connections = process.connections()
        except Exception:
            continue

        for c in connections:
            if c.laddr in targets:
                return process.pid
