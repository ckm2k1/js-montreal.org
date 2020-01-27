import re
from datetime import datetime, timezone

mem_size_units = {
    '': 1,
    'E': 1000 * 1000 * 1000 * 1000 * 1000 * 1000,
    'P': 1000 * 1000 * 1000 * 1000 * 1000,
    'T': 1000 * 1000 * 1000 * 1000,
    'G': 1000 * 1000 * 1000,
    'M': 1000 * 1000,
    'K': 1000,
    'Ei': 1024 * 1024 * 1024 * 1024 * 1024 * 1024,
    'Pi': 1024 * 1024 * 1024 * 1024 * 1024,
    'Ti': 1024 * 1024 * 1024 * 1024,
    'Gi': 1024 * 1024 * 1024,
    'Mi': 1024 * 1024,
    'Ki': 1024
}

cpu_size_units = {'': 1, 'm': 0.001}


def get_now():
    """Facilitates testing."""
    dt = datetime.utcnow()
    return dt.replace(tzinfo=timezone.utc)


def get_now_isoformat():
    """Facilitates testing."""
    return get_now().isoformat()


def memory_str_to_nbytes(mem_size_str):
    m = re.search(r"^(\d+)(.*)$", str(mem_size_str))
    if not m:
        raise ValueError("No match for memory allocatable")

    if not m.group(2) in mem_size_units:
        raise ValueError("Unexpected memory size unit " + m.group(2))

    mem_size_bytes = int(m.group(1)) * mem_size_units[m.group(2)]
    return mem_size_bytes


def cpu_str_to_ncpu(cpu_str):
    m = re.search(r"^([\d.]+)(.*)$", str(cpu_str))
    if not m:
        raise ValueError("No match for cpu allocatable")

    if not m.group(2) in cpu_size_units:
        raise ValueError("Unexpected cpu size unit " + m.group(2))

    cpu_size = float(m.group(1)) * cpu_size_units[m.group(2)]
    return cpu_size