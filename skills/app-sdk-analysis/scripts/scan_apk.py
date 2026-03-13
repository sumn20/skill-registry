#!/usr/bin/env python3
"""
scan_apk.py — APK 一站式扫描工具

功能：
  1. 列出所有 .so 文件（按架构分组 + 去重）
  2. 提取并解析 AndroidManifest.xml（AXML 格式）
  3. 扫描 assets/ 目录结构
  4. 匹配已知 SDK 特征（基于 .so 文件名 + Manifest 组件）
  5. 输出结构化 JSON 结果供报告生成使用

用法：
  python3 scan_apk.py <path_to_apk> [--json] [--aapt <path_to_aapt>]

  --json    输出 JSON 格式（默认输出人类可读文本）
  --aapt    指定 aapt 可执行文件路径，若存在则用 aapt 获取精确基本信息
"""

import sys
import os
import json
import zipfile
import subprocess
import tempfile
import re
import argparse
from pathlib import Path

# 导入同目录下的 parse_manifest
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from parse_manifest import parse_axml


# === 已知 SDK 特征库 ===
# 格式: { "特征关键字": ("SDK名称", "分类") }
# 这里是常见的高价值SDK，完整规则在 references/ 下
KNOWN_SO_SIGNATURES = {
    # RTC / 音视频
    'ZegoExpressEngine': ('即构 ZEGO RTC', '🎥 音视频'),
    'zego': ('即构 ZEGO', '🎥 音视频'),
    'agora': ('声网 Agora', '🎥 音视频'),
    'agora_rtc': ('声网 Agora RTC', '🎥 音视频'),
    'trtc': ('腾讯 TRTC', '🎥 音视频'),
    'liteav': ('腾讯 LiteAV', '🎥 音视频'),
    'bytertc': ('火山引擎 RTC', '🎥 音视频'),
    'lkjingle_peerconnection': ('LiveKit WebRTC', '🎥 音视频'),
    'webrtc': ('WebRTC', '🎥 音视频'),
    'ijkplayer': ('IJKPlayer', '🎥 音视频'),
    'ijkffmpeg': ('IJKPlayer FFmpeg', '🎥 音视频'),
    'ijksdl': ('IJKPlayer SDL', '🎥 音视频'),
    'fmod': ('FMOD 音频引擎', '🎥 音视频'),
    'alivc': ('阿里云播放器', '🎥 音视频'),
    'pag': ('PAG 动效', '🎥 音视频'),

    # 广告
    'ttad': ('穿山甲广告', '📢 广告'),
    'pangle': ('Pangle 广告', '📢 广告'),
    'BaiduMobAd': ('百度联盟广告', '📢 广告'),
    'gdtadv2': ('优量汇广告', '📢 广告'),
    'gdt': ('优量汇广告', '📢 广告'),
    'ksad': ('快手广告', '📢 广告'),

    # 推送
    'hms': ('华为 HMS', '📲 推送'),
    'mipush': ('小米推送', '📲 推送'),
    'heytap': ('OPPO 推送', '📲 推送'),
    'vivopush': ('vivo 推送', '📲 推送'),

    # 社交
    'wechat': ('微信 SDK', '👥 社交'),
    'weibo': ('微博 SDK', '👥 社交'),

    # 安全
    'securitybody': ('阿里安全', '🔒 安全'),
    'toyger': ('DTF 人脸识别', '🔒 安全'),

    # 存储
    'mmkv': ('MMKV', '💾 存储'),

    # 崩溃监控
    'bugly': ('腾讯 Bugly', '⚠️ 崩溃监测'),
    'crashlytics': ('Firebase Crashlytics', '⚠️ 崩溃监测'),

    # 数据分析
    'umeng': ('友盟统计', '📊 数据分析'),
    'sensors': ('神策分析', '📊 数据分析'),
    'thinkingdata': ('数数科技', '📊 数据分析'),
    'growingio': ('GrowingIO', '📊 数据分析'),

    # 支付
    'alipay': ('支付宝', '💳 支付'),

    # 地图
    'amap': ('高德地图', '📍 地图定位'),
    'baidumap': ('百度地图', '📍 地图定位'),
    'tencentmap': ('腾讯地图', '📍 地图定位'),

    # 通用框架
    'flutter': ('Flutter', '⚙️ 开发框架'),
    'reactnative': ('React Native', '⚙️ 开发框架'),
    'hermes': ('Hermes JS 引擎', '⚙️ 开发框架'),

    # 网络
    'cronet': ('Cronet', '🌐 网络通信'),
    'mars': ('微信 Mars', '🌐 网络通信'),
}

# Manifest 组件特征（包名前缀 -> SDK 名称）
KNOWN_COMPONENT_PREFIXES = {
    'com.zego.': ('即构 ZEGO', '🎥 音视频'),
    'io.agora.': ('声网 Agora', '🎥 音视频'),
    'com.tencent.liteav': ('腾讯 LiteAV/TRTC', '🎥 音视频'),
    'io.livekit.': ('LiveKit', '🎥 音视频'),
    'com.bytedance.rtc': ('火山引擎 RTC', '🎥 音视频'),
    'com.ss.android.lark.': ('飞书/字节系', '⚙️ 开发框架'),
    'com.umeng.': ('友盟', '📊 数据分析'),
    'com.alibaba.': ('阿里系', '📦 其他'),
    'com.huawei.hms': ('华为 HMS', '📲 推送'),
    'com.xiaomi.push': ('小米推送', '📲 推送'),
    'com.heytap.msp': ('OPPO 推送', '📲 推送'),
    'com.vivo.push': ('vivo 推送', '📲 推送'),
    'com.meizu.cloud.pushsdk': ('魅族推送', '📲 推送'),
    'com.tencent.bugly': ('腾讯 Bugly', '⚠️ 崩溃监测'),
    'com.tencent.mm.opensdk': ('微信 SDK', '👥 社交'),
    'com.tencent.tauth': ('QQ SDK', '👥 社交'),
    'com.sina.weibo': ('微博 SDK', '👥 社交'),
    'com.alipay.': ('支付宝', '💳 支付'),
    'com.bytedance.sdk.openadsdk': ('穿山甲广告', '📢 广告'),
    'com.baidu.mobads': ('百度联盟广告', '📢 广告'),
    'com.qq.e.': ('优量汇广告', '📢 广告'),
    'com.beizi.': ('贝兹广告', '📢 广告'),
    'com.kwad.': ('快手广告', '📢 广告'),
    'com.geetest.': ('极验', '🔒 安全'),
    'com.sensorsdata.': ('神策分析', '📊 数据分析'),
    'cn.thinkingdata.': ('数数科技', '📊 数据分析'),
    'com.growingio.': ('GrowingIO', '📊 数据分析'),
}


def scan_so_files(apk_path):
    """扫描 APK 中的所有 .so 文件。"""
    so_files = {}  # {架构: [文件名列表]}
    all_so_names = set()

    with zipfile.ZipFile(apk_path, 'r') as zf:
        for entry in zf.namelist():
            if entry.endswith('.so'):
                parts = entry.split('/')
                if len(parts) >= 3 and parts[0] == 'lib':
                    arch = parts[1]
                    name = parts[-1]
                    so_files.setdefault(arch, []).append(name)
                    all_so_names.add(name)
                elif entry.endswith('.so'):
                    # .so 在非标准路径
                    so_files.setdefault('other', []).append(entry)
                    all_so_names.add(os.path.basename(entry))

    return so_files, sorted(all_so_names)


def scan_assets(apk_path):
    """扫描 APK 的 assets/ 目录结构。"""
    assets = []
    with zipfile.ZipFile(apk_path, 'r') as zf:
        for entry in zf.namelist():
            if entry.startswith('assets/'):
                assets.append(entry)
    return assets


def get_apk_info_via_aapt(apk_path, aapt_path):
    """用 aapt 获取精确的 APK 基本信息。"""
    try:
        result = subprocess.run(
            [aapt_path, 'dump', 'badging', apk_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        info = {}

        # 解析 package 行
        pkg_match = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", output)
        if pkg_match:
            info['package'] = pkg_match.group(1)
            info['version_code'] = pkg_match.group(2)
            info['version_name'] = pkg_match.group(3)

        # SDK 版本
        sdk_match = re.search(r"sdkVersion:'(\d+)'", output)
        if sdk_match:
            info['min_sdk'] = sdk_match.group(1)
        target_match = re.search(r"targetSdkVersion:'(\d+)'", output)
        if target_match:
            info['target_sdk'] = target_match.group(1)

        # 应用名
        label_match = re.search(r"application-label(?:-zh)?:'([^']+)'", output)
        if label_match:
            info['app_name'] = label_match.group(1)

        # 原始平台
        native_match = re.findall(r"native-code: '([^']+)'", output)
        if native_match:
            info['native_code'] = native_match

        return info
    except Exception as e:
        print(f"WARNING: aapt failed: {e}", file=sys.stderr)
        return {}


def match_sdk_from_so(so_names):
    """从 .so 文件名匹配已知 SDK。"""
    matched = {}  # { SDK名: {category, evidence: []} }

    for so_name in so_names:
        name_lower = so_name.lower().replace('lib', '').replace('.so', '')
        for keyword, (sdk_name, category) in KNOWN_SO_SIGNATURES.items():
            if keyword.lower() in name_lower:
                if sdk_name not in matched:
                    matched[sdk_name] = {'category': category, 'evidence': []}
                matched[sdk_name]['evidence'].append(f'.so: {so_name}')
                break  # 每个 .so 只匹配第一个

    return matched


def match_sdk_from_manifest(manifest_result):
    """从 Manifest 组件匹配已知 SDK。"""
    matched = {}

    if not manifest_result:
        return matched

    all_components = (
        manifest_result.get('activities', []) +
        manifest_result.get('services', []) +
        manifest_result.get('providers', []) +
        manifest_result.get('receivers', []) +
        manifest_result.get('sdk_packages', [])
    )

    for component in all_components:
        for prefix, (sdk_name, category) in KNOWN_COMPONENT_PREFIXES.items():
            if component.startswith(prefix) or component.lower().startswith(prefix.lower()):
                if sdk_name not in matched:
                    matched[sdk_name] = {'category': category, 'evidence': []}
                if len(matched[sdk_name]['evidence']) < 5:  # 限制证据数量
                    matched[sdk_name]['evidence'].append(f'manifest: {component}')
                break

    return matched


def merge_sdk_results(*results):
    """合并多个来源的 SDK 匹配结果。"""
    merged = {}
    for result in results:
        for sdk_name, info in result.items():
            if sdk_name not in merged:
                merged[sdk_name] = {'category': info['category'], 'evidence': []}
            merged[sdk_name]['evidence'].extend(info['evidence'])
    return merged


def find_aapt():
    """自动查找系统中的 aapt 工具。"""
    # 常见路径
    search_paths = [
        os.path.expanduser('~/Library/Android/sdk/build-tools'),
        '/usr/local/lib/android/sdk/build-tools',
        os.environ.get('ANDROID_HOME', '') + '/build-tools',
    ]

    for base in search_paths:
        if not os.path.isdir(base):
            continue
        # 取最新版本
        versions = sorted(os.listdir(base), reverse=True)
        for ver in versions:
            aapt_path = os.path.join(base, ver, 'aapt')
            if os.path.isfile(aapt_path) and os.access(aapt_path, os.X_OK):
                return aapt_path
    return None


def main():
    parser = argparse.ArgumentParser(description='APK 一站式扫描工具')
    parser.add_argument('apk', help='APK 文件路径')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    parser.add_argument('--aapt', help='aapt 可执行文件路径（自动检测）')
    args = parser.parse_args()

    apk_path = args.apk
    if not os.path.isfile(apk_path):
        print(f"ERROR: File not found: {apk_path}", file=sys.stderr)
        sys.exit(1)

    apk_size = os.path.getsize(apk_path)

    # 1. 用 aapt 获取基本信息
    aapt_path = args.aapt or find_aapt()
    basic_info = {}
    if aapt_path:
        basic_info = get_apk_info_via_aapt(apk_path, aapt_path)

    # 2. 扫描 .so 文件
    so_by_arch, all_so_names = scan_so_files(apk_path)

    # 3. 提取并解析 Manifest
    manifest_result = None
    with zipfile.ZipFile(apk_path, 'r') as zf:
        if 'AndroidManifest.xml' in zf.namelist():
            with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as tmp:
                tmp.write(zf.read('AndroidManifest.xml'))
                tmp_path = tmp.name
            try:
                manifest_result = parse_axml(tmp_path)
            finally:
                os.unlink(tmp_path)

    # 4. 扫描 assets
    assets = scan_assets(apk_path)

    # 5. SDK 匹配
    sdk_from_so = match_sdk_from_so(all_so_names)
    sdk_from_manifest = match_sdk_from_manifest(manifest_result)
    all_sdks = merge_sdk_results(sdk_from_so, sdk_from_manifest)

    # 按分类分组
    sdks_by_category = {}
    for sdk_name, info in sorted(all_sdks.items()):
        cat = info['category']
        sdks_by_category.setdefault(cat, []).append({
            'name': sdk_name,
            'evidence': info['evidence']
        })

    # 6. 组装结果
    result = {
        'basic_info': {
            **basic_info,
            'apk_size_mb': round(apk_size / (1024 * 1024), 1),
            'file_count': sum(len(v) for v in so_by_arch.values()) if so_by_arch else 0,
        },
        'architectures': {arch: len(files) for arch, files in so_by_arch.items()},
        'so_files': all_so_names,
        'so_count': len(all_so_names),
        'manifest': {
            'activities': sorted(set(manifest_result.get('activities', []))) if manifest_result else [],
            'services': sorted(set(manifest_result.get('services', []))) if manifest_result else [],
            'providers': sorted(set(manifest_result.get('providers', []))) if manifest_result else [],
            'receivers': sorted(set(manifest_result.get('receivers', []))) if manifest_result else [],
            'permissions': sorted(set(manifest_result.get('permissions', []))) if manifest_result else [],
            'sdk_packages': manifest_result.get('sdk_packages', []) if manifest_result else [],
        },
        'assets_count': len(assets),
        'sdks': sdks_by_category,
        'sdk_total': len(all_sdks),
    }

    # 7. 输出
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text_report(result)


def print_text_report(result):
    """输出人类可读的文本报告。"""
    info = result['basic_info']
    print("=" * 70)
    print("  APK SCAN REPORT")
    print("=" * 70)

    print(f"\n📦 基本信息:")
    if info.get('app_name'):
        print(f"  应用名称: {info['app_name']}")
    if info.get('package'):
        print(f"  包名: {info['package']}")
    if info.get('version_name'):
        print(f"  版本: {info['version_name']} (code: {info.get('version_code', 'N/A')})")
    print(f"  APK 大小: {info['apk_size_mb']} MB")
    if info.get('min_sdk'):
        print(f"  Min SDK: {info['min_sdk']}")
    if info.get('target_sdk'):
        print(f"  Target SDK: {info['target_sdk']}")
    if info.get('native_code'):
        print(f"  架构: {', '.join(info['native_code'])}")

    print(f"\n📚 架构分布:")
    for arch, count in result['architectures'].items():
        print(f"  {arch}: {count} 个 .so")

    print(f"\n🔧 .so 文件 ({result['so_count']} 个去重):")
    for so in result['so_files']:
        print(f"  {so}")

    manifest = result['manifest']
    print(f"\n📋 Manifest 组件:")
    print(f"  Activities: {len(manifest['activities'])}")
    print(f"  Services: {len(manifest['services'])}")
    print(f"  Providers: {len(manifest['providers'])}")
    print(f"  Receivers: {len(manifest['receivers'])}")
    print(f"  Permissions: {len(manifest['permissions'])}")
    print(f"  SDK Packages: {len(manifest['sdk_packages'])}")

    print(f"\n🔍 识别 SDK ({result['sdk_total']} 个):")
    for category in sorted(result['sdks'].keys()):
        sdks = result['sdks'][category]
        print(f"\n  {category}:")
        for sdk in sdks:
            evidence_str = '; '.join(sdk['evidence'][:3])
            print(f"    • {sdk['name']}")
            print(f"      证据: {evidence_str}")

    print(f"\n📁 Assets 文件数: {result['assets_count']}")
    print(f"\n{'=' * 70}")


if __name__ == '__main__':
    main()
