#!/usr/bin/env python3
"""
parse_manifest.py — Android Binary XML (AXML) Manifest 解析器

用途：从 APK 中提取的 AndroidManifest.xml（二进制格式）中解析出：
  - 所有字符串（包名、组件、权限等）
  - Activities / Services / Providers / Receivers 组件列表
  - SDK 相关的包名路径

用法：
  python3 parse_manifest.py <path_to_binary_AndroidManifest.xml>

输出格式为结构化文本，供上层分析脚本消费。
"""

import sys
import struct
import re
from collections import defaultdict


# === AXML 常量 ===
CHUNK_AXML_FILE = 0x00080003
CHUNK_STRING_POOL = 0x001C0001
CHUNK_RESOURCE_MAP = 0x00080180
CHUNK_START_NAMESPACE = 0x00100100
CHUNK_END_NAMESPACE = 0x00100101
CHUNK_START_TAG = 0x00100102
CHUNK_END_TAG = 0x00100103
CHUNK_TEXT = 0x00100104


def read_u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]

def read_u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]

def read_i32(data, offset):
    return struct.unpack_from('<i', data, offset)[0]


def decode_string_pool(data, offset):
    """解析 AXML 字符串池，返回字符串列表。"""
    chunk_type = read_u32(data, offset)
    chunk_size = read_u32(data, offset + 4)
    string_count = read_u32(data, offset + 8)
    # style_count = read_u32(data, offset + 12)
    flags = read_u32(data, offset + 16)
    strings_start = read_u32(data, offset + 20)
    # styles_start = read_u32(data, offset + 24)

    is_utf8 = (flags & (1 << 8)) != 0

    # 读取字符串偏移表
    offsets = []
    for i in range(string_count):
        offsets.append(read_u32(data, offset + 28 + i * 4))

    strings = []
    pool_start = offset + strings_start

    for i in range(string_count):
        str_offset = pool_start + offsets[i]
        try:
            if is_utf8:
                # UTF-8: 先跳过字符数，再读字节数
                char_len = data[str_offset]
                if char_len & 0x80:
                    str_offset += 2
                else:
                    str_offset += 1
                byte_len = data[str_offset]
                if byte_len & 0x80:
                    byte_len = ((byte_len & 0x7F) << 8) | data[str_offset + 1]
                    str_offset += 2
                else:
                    str_offset += 1
                s = data[str_offset:str_offset + byte_len].decode('utf-8', errors='replace')
            else:
                # UTF-16
                char_len = read_u16(data, str_offset)
                if char_len & 0x8000:
                    char_len = ((char_len & 0x7FFF) << 16) | read_u16(data, str_offset + 2)
                    str_offset += 4
                else:
                    str_offset += 2
                raw = data[str_offset:str_offset + char_len * 2]
                s = raw.decode('utf-16-le', errors='replace')
            strings.append(s)
        except Exception:
            strings.append(f'<decode_error_{i}>')

    return strings, chunk_size


def parse_axml(filepath):
    """完整解析 AXML 文件，返回结构化数据。"""
    with open(filepath, 'rb') as f:
        data = f.read()

    if len(data) < 8:
        print("ERROR: File too small", file=sys.stderr)
        return None

    magic = read_u32(data, 0)
    file_size = read_u32(data, 4)

    if magic != CHUNK_AXML_FILE:
        print(f"WARNING: Not standard AXML (magic=0x{magic:08X}), attempting fallback parse",
              file=sys.stderr)

    # 解析字符串池
    strings = []
    offset = 8
    while offset < len(data) - 8:
        chunk_type = read_u32(data, offset)
        chunk_size = read_u32(data, offset + 4)
        if chunk_size < 8:
            break
        if chunk_type == CHUNK_STRING_POOL:
            strings, _ = decode_string_pool(data, offset)
            break
        offset += chunk_size

    if not strings:
        # Fallback: 暴力提取可读字符串
        print("WARNING: String pool not found, using fallback extraction", file=sys.stderr)
        strings = fallback_extract_strings(data)

    # 分类提取
    result = classify_strings(strings)
    return result


def fallback_extract_strings(data):
    """暴力提取 AXML 中的可读字符串（当正式解析失败时使用）。"""
    strings = []
    i = 0
    while i < len(data) - 4:
        # 尝试 UTF-8 模式
        strlen = data[i] | (data[i + 1] << 8)
        if 3 < strlen < 300 and i + 2 + strlen <= len(data):
            try:
                s = data[i + 2:i + 2 + strlen].decode('utf-8', errors='strict')
                if s.isprintable() and not s.isspace():
                    strings.append(s)
                    i += 2 + strlen
                    continue
            except (UnicodeDecodeError, ValueError):
                pass
        i += 1
    return strings


def classify_strings(strings):
    """将字符串分类为组件、包名、权限等。"""
    result = {
        'activities': [],
        'services': [],
        'providers': [],
        'receivers': [],
        'permissions': [],
        'sdk_packages': set(),
        'meta_data_keys': [],
        'all_strings': strings,
    }

    # Android 组件通常以大写字母 + 包名形式出现
    component_pattern = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*\.[A-Z]\w+$')
    package_pattern = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$')

    for s in strings:
        s_stripped = s.strip()
        if not s_stripped:
            continue

        # 分类组件
        if component_pattern.match(s_stripped):
            lower = s_stripped.lower()
            if 'activity' in lower:
                result['activities'].append(s_stripped)
            elif 'service' in lower:
                result['services'].append(s_stripped)
            elif 'provider' in lower:
                result['providers'].append(s_stripped)
            elif 'receiver' in lower or 'broadcast' in lower:
                result['receivers'].append(s_stripped)

        # 权限
        if s_stripped.startswith('android.permission.') or s_stripped.endswith('.PERMISSION'):
            result['permissions'].append(s_stripped)

        # SDK 包名路径
        if package_pattern.match(s_stripped) and len(s_stripped) > 10:
            # 排除 Android 标准路径和应用自身包名
            if not s_stripped.startswith(('android.', 'java.', 'javax.', 'dalvik.')):
                result['sdk_packages'].add(s_stripped)

    result['sdk_packages'] = sorted(result['sdk_packages'])
    return result


def print_report(result):
    """输出结构化的分析报告。"""
    print("=" * 60)
    print(f"=== ACTIVITIES ({len(result['activities'])})")
    print("=" * 60)
    for a in sorted(set(result['activities'])):
        print(f"  {a}")

    print(f"\n{'=' * 60}")
    print(f"=== SERVICES ({len(result['services'])})")
    print("=" * 60)
    for s in sorted(set(result['services'])):
        print(f"  {s}")

    print(f"\n{'=' * 60}")
    print(f"=== PROVIDERS ({len(result['providers'])})")
    print("=" * 60)
    for p in sorted(set(result['providers'])):
        print(f"  {p}")

    print(f"\n{'=' * 60}")
    print(f"=== RECEIVERS ({len(result['receivers'])})")
    print("=" * 60)
    for r in sorted(set(result['receivers'])):
        print(f"  {r}")

    print(f"\n{'=' * 60}")
    print(f"=== PERMISSIONS ({len(result['permissions'])})")
    print("=" * 60)
    for p in sorted(set(result['permissions'])):
        print(f"  {p}")

    print(f"\n{'=' * 60}")
    print(f"=== SDK PACKAGES ({len(result['sdk_packages'])})")
    print("=" * 60)
    for pkg in result['sdk_packages']:
        print(f"  {pkg}")

    # 统计
    total = (len(result['activities']) + len(result['services']) +
             len(result['providers']) + len(result['receivers']))
    print(f"\n{'=' * 60}")
    print(f"=== SUMMARY")
    print(f"  Total strings in manifest: {len(result['all_strings'])}")
    print(f"  Components: {total}")
    print(f"  SDK packages: {len(result['sdk_packages'])}")
    print(f"  Permissions: {len(result['permissions'])}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <AndroidManifest.xml>")
        print("  Parses Android Binary XML and extracts components/SDK info.")
        sys.exit(1)

    filepath = sys.argv[1]
    result = parse_axml(filepath)
    if result:
        print_report(result)


if __name__ == '__main__':
    main()
