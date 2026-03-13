#!/usr/bin/env python3
"""TRTC 通话详情 URL 获取 + 深度排查脚本

通过 Playwright 持久化浏览器上下文调用 TRTC 内网 API，获取通话详情并排查问题。

功能:
  1. getRoomList → 获取 CommId，拼接通话详情页 URL
  2. getUserInfo → 获取双端设备/网络/TinyId 信息
  3. getElasticSearchData(detail_event) → 双端事件列表
  4. getElasticSearchData(aCapEnergy/aPlayEnergy) → 音频音量数据
  5. 基于真实数据推断排查结论

用法:
  python3 get_detail_url.py --sdkappid 1600092866 --room ic4ex78iy6lqp1 \
    --start-ts 1772553600 --end-ts 1772557200 \
    --sender 14205825 --receiver 15778221 \
    --description "听不到对方声音"

输出: JSON 格式结果（stdout），包含 detail_url + conclusion
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

TRTC_MONITOR_HOST = 'trtc-monitor.woa.com'
TRTC_API_HOST = 'avmonitor.trtc.woa.com'
PW_USER_DATA_DIR = os.path.expanduser('~/.trtc-dashboard-profile')


# ═══════════════════════════════════════════════════════════
# URL 构造
# ═══════════════════════════════════════════════════════════

def build_roomlist_api_url(sdkappid, room, start_ts, end_ts, userid=''):
    url = (
        f"https://{TRTC_API_HOST}/getRoomList"
        f"?SdkAppId={sdkappid}"
        f"&StartTs={start_ts}"
        f"&EndTs={end_ts}"
        f"&SourceType=0"
        f"&CallStatus=0"
        f"&PageIndex=0"
        f"&PageSize=20"
    )
    if room:
        url += f"&RoomNum={room}"
    if userid:
        url += f"&UserId={userid}"
    return url


def build_detail_url(comm_id, room_num, room_str, create_time,
                     destroy_time, duration, finished, sdkappid, env):
    return (
        f"https://{TRTC_MONITOR_HOST}/trtc/monitor/call-details"
        f"?commId={comm_id}"
        f"&userId="
        f"&roomNum={room_num}"
        f"&roomStr={room_str}"
        f"&createTime={create_time}"
        f"&destroyTime={destroy_time}"
        f"&duration={duration}"
        f"&finished={'true' if finished else 'false'}"
        f"&sdkAppid={sdkappid}"
        f"&environment={env}"
    )


def build_search_url(sdkappid, room, userid, env, start_ts, end_ts):
    url = (
        f"https://{TRTC_MONITOR_HOST}/"
        f"?sdkAppId={sdkappid}"
        f"&environment={env}"
        f"&startTs={start_ts * 1000}"
        f"&endTs={end_ts * 1000}"
    )
    if room:
        url += f"&roomNum={room}"
    if userid:
        url += f"&userId={userid}"
    return url


def build_user_detail_url(comm_id, room_num, room_str, create_time,
                          destroy_time, duration, finished, sdkappid, env,
                          send_user_id, recv_user_id, user_count):
    """构造用户级通话详情页 URL (call-details-user)"""
    return (
        f"https://{TRTC_MONITOR_HOST}/trtc/monitor/call-details-user"
        f"?commId={comm_id}"
        f"&userId="
        f"&roomNum={room_num}"
        f"&roomStr={room_str}"
        f"&createTime={create_time}"
        f"&destroyTime={destroy_time}"
        f"&duration={duration}"
        f"&finished={'true' if finished else 'false'}"
        f"&sdkAppid={sdkappid}"
        f"&environment={env}"
        f"&receiveUserId={recv_user_id}"
        f"&sendUserId={send_user_id}"
        f"&service=trtc"
        f"&startTime={create_time}"
        f"&endTime={destroy_time}"
        f"&userNum={user_count}"
    )


# ═══════════════════════════════════════════════════════════
# 房间信息提取
# ═══════════════════════════════════════════════════════════

def extract_room_info(room, room_str_fallback):
    def get(r, *keys):
        for k in keys:
            v = r.get(k)
            if v is not None:
                return v
        return None

    return {
        'comm_id': get(room, 'CommId', 'commId', 'comm_id') or '',
        'room_num': get(room, 'RoomNum', 'roomNum', 'room_num') or '',
        'room_str': get(room, 'RoomStr', 'roomStr', 'room_str') or room_str_fallback,
        'create_time': get(room, 'CreateTs', 'CreateTime', 'createTime') or 0,
        'destroy_time': get(room, 'DestroyTs', 'DestroyTime', 'destroyTime') or 0,
        'duration': get(room, 'Duration', 'duration') or 0,
        'finished': get(room, 'Finished', 'finished', 'IsFinished') if get(room, 'Finished', 'finished', 'IsFinished') is not None else True,
        'user_count': get(room, 'UserNum', 'UserCount', 'userCount', 'user_count') or 0,
    }


# ═══════════════════════════════════════════════════════════
# 事件分析引擎（复用 soul-ticket-dashboard 的成熟逻辑）
# ═══════════════════════════════════════════════════════════

def _ms_to_time(ts_ms):
    if ts_ms > 1e12:
        return datetime.fromtimestamp(ts_ms / 1000).strftime('%H:%M:%S')
    return datetime.fromtimestamp(ts_ms).strftime('%H:%M:%S')


def analyze_events(events):
    """分析事件列表，返回 {findings, flags}"""
    findings = []
    flags = {
        'enter_room_ok': False, 'first_audio': False, 'exit_normal': False,
        'has_bg_switch': False, 'bg_no_return': False,
        'has_mute': False, 'has_capture_interrupt': False,
        'capture_interrupt_recovered': False,
        'has_start_local_audio': False, 'has_stop_local_audio': False,
        'capture_start_failed': False, 'no_mic_permission': False,
        'bg_capture_silent': False, 'timeout_exit': False,
        'sample_rate_changed': False,
        'mic_volume_zero': False,  # 麦克风软件音量被设置为0
    }

    bg_enter = None
    bg_return = False
    sample_rate_changes = []

    for ev in events:
        v = ev.get('V', 0)
        t = ev.get('T', 0)
        p1 = ev.get('Para1')
        p2 = ev.get('Para2')

        if v == 5003:
            flags['enter_room_ok'] = True
        elif v == 5009:
            flags['first_audio'] = True
        elif v == 7001:
            flags['exit_normal'] = True
            if p1 == 2:
                flags['timeout_exit'] = True
                findings.append(f'超时退房({_ms_to_time(t)})')
        elif v == 2001:
            flags['has_bg_switch'] = True
            if p1 == 1:
                bg_enter = t
                bg_return = False
                findings.append(f'APP切后台({_ms_to_time(t)})')
            elif p1 == 0:
                bg_return = True
                if bg_enter:
                    bg_dur = (t - bg_enter) / 1000
                    findings.append(f'APP回前台({_ms_to_time(t)},后台{bg_dur:.0f}秒)')
                bg_enter = None
        elif v == 3001:
            if p1 == 1:  # 停止采集
                flags['has_mute'] = True
                findings.append(f'停止采集音频({_ms_to_time(t)})')
        elif v == 3011:
            if p1 == 1:
                flags['has_mute'] = True
                findings.append(f'mute静音({_ms_to_time(t)})')
            elif p1 == 0:
                findings.append(f'取消mute({_ms_to_time(t)})')
        elif v == 3007:
            # 音频接口切换 / 麦克风软件音量变化
            # Para1=0 表示麦克风软件音量被设置为0
            if p1 == 0:
                flags['mic_volume_zero'] = True
                flags['has_mute'] = True  # 等效 mute
                findings.append(f'麦克风软件音量设置为0({_ms_to_time(t)})')
        elif v == 3005:
            flags['has_capture_interrupt'] = True
            findings.append(f'采集打断开始({_ms_to_time(t)})')
        elif v == 3006:
            flags['capture_interrupt_recovered'] = True
            findings.append(f'采集打断恢复({_ms_to_time(t)})')
        elif v == 3013:
            flags['capture_start_failed'] = True
            findings.append(f'采集启动失败({_ms_to_time(t)})')
        elif v == 3014 and p1 == 0:
            flags['no_mic_permission'] = True
            findings.append(f'无麦克风权限({_ms_to_time(t)})')
        elif v == 6001:
            flags['has_start_local_audio'] = True
        elif v == 6002:
            flags['has_stop_local_audio'] = True
        elif v == 3008:
            sample_rate_changes.append({'t': t, 'rate': p1})

    # 采样率变化
    if len(sample_rate_changes) >= 2:
        for i in range(1, len(sample_rate_changes)):
            if sample_rate_changes[i - 1]['rate'] != sample_rate_changes[i]['rate']:
                flags['sample_rate_changed'] = True
                findings.append(
                    f"采样率变更{sample_rate_changes[i-1]['rate']}→{sample_rate_changes[i]['rate']}Hz"
                )
                break

    # 切后台后未回来
    if bg_enter and not bg_return:
        flags['bg_no_return'] = True
        if flags['exit_normal']:
            findings.append('在后台状态下退出通话')

    # 后台采集无声
    if flags['has_bg_switch'] and not flags['has_start_local_audio']:
        flags['bg_capture_silent'] = True

    if not flags['enter_room_ok']:
        findings.append('未成功进入房间')
    if not flags['first_audio']:
        findings.append('未发送首帧音频')
    if flags['has_capture_interrupt'] and not flags['capture_interrupt_recovered']:
        findings.append('采集打断未恢复')

    return {'findings': findings, 'flags': flags}


def analyze_audio_metrics(cap_energy, play_energy):
    """分析音频采集/播放音量数据"""
    findings = []
    cap_stats = {'zero_pct': 0, 'avg': 0, 'total': 0, 'silent': False, 'weak': False}
    play_stats = {'zero_pct': 0, 'avg': 0, 'total': 0, 'silent': False, 'weak': False}

    if cap_energy:
        vals = [c['V'] for c in cap_energy if c.get('V') is not None]
        if vals:
            cap_stats['total'] = len(vals)
            zeros = sum(1 for v in vals if v == 0)
            cap_stats['zero_pct'] = round(zeros / len(vals) * 100, 1)
            cap_stats['avg'] = round(sum(vals) / len(vals), 1)
            if cap_stats['zero_pct'] > 80:
                cap_stats['silent'] = True
                findings.append(f'发送端采集无声(音量{cap_stats["zero_pct"]:.0f}%为零)')
            elif cap_stats['zero_pct'] > 50:
                findings.append(f'发送端采集间歇性静音({cap_stats["zero_pct"]:.0f}%为零)')
            elif 0 < cap_stats['avg'] < 200:
                cap_stats['weak'] = True
                findings.append(f'发送端采集弱音(平均音量{cap_stats["avg"]:.0f})')

    if play_energy:
        vals = [c['V'] for c in play_energy if c.get('V') is not None]
        if vals:
            play_stats['total'] = len(vals)
            zeros = sum(1 for v in vals if v == 0)
            play_stats['zero_pct'] = round(zeros / len(vals) * 100, 1)
            play_stats['avg'] = round(sum(vals) / len(vals), 1)
            if play_stats['zero_pct'] > 80:
                play_stats['silent'] = True
                findings.append(f'接收端播放无声(音量{play_stats["zero_pct"]:.0f}%为零)')
            elif play_stats['zero_pct'] > 50:
                findings.append(f'接收端播放间歇性静音({play_stats["zero_pct"]:.0f}%为零)')

    return {'findings': findings, 'cap_stats': cap_stats, 'play_stats': play_stats}


# ═══════════════════════════════════════════════════════════
# 结论推断引擎（基于真实数据，非猜测）
# ═══════════════════════════════════════════════════════════

def infer_conclusion(sender_flags, receiver_flags,
                     cap_stats, play_stats,
                     user_count, sender_platform, receiver_platform,
                     sender_has_info):
    """基于深度分析数据推断结论。返回 (conclusion, tag)"""
    sf = sender_flags or {}
    rf = receiver_flags or {}

    def peer_label():
        return sender_platform if sender_platform != '未知' else 'android'

    def peer_cn():
        p = peer_label()
        return '安卓' if p.lower() == 'android' else p

    # 1. 房间只有一个人
    if user_count == 1:
        return '房内只有一个人', '房间只有一个人'
    if not sender_has_info and cap_stats.get('total', 0) == 0:
        return '房内只有一个人', '房间只有一个人'

    # 2. 超时退房
    if sf.get('timeout_exit'):
        if sf.get('has_mute'):
            return '超时退房+mute静音', '断连超时退房'
        return f'{peer_label()} 上行端超时退房', '断连超时退房'
    if rf.get('timeout_exit'):
        return '接收端超时退房', '断连超时退房'
    if sf and not sf.get('enter_room_ok') and not sf.get('first_audio') and sf.get('exit_normal'):
        return f'{peer_label()} 上行端超时退房', '断连超时退房'

    # 3. 无麦克风权限
    if sf.get('no_mic_permission'):
        return f'{peer_label()} 无采集权限', '没有麦克风权限'
    if rf.get('no_mic_permission'):
        return f'接收端无采集权限', '没有麦克风权限'
    if rf and rf.get('enter_room_ok') and not rf.get('first_audio'):
        if rf.get('capture_start_failed') or rf.get('has_capture_interrupt'):
            return '接收端无采集权限', '没有麦克风权限'

    # 4. 采集启动失败
    if sf.get('capture_start_failed'):
        if sf.get('has_capture_interrupt'):
            return f'{peer_label()}采集启动失败，疑似有系统电话抢占', None
        return f'{peer_label()} 启动采集失败', None

    # 5. 采集无声（音量数据优先）
    if cap_stats.get('silent'):
        if sf.get('has_bg_switch') and not sf.get('has_start_local_audio'):
            p = peer_label()
            if p.lower() in ('android', '未知'):
                return 'android 后台采集无声', '安卓后台采集无声'
            return 'iOS 切后台未执行 startLocalAudio', '未调用startlocalaudio'
        if sf.get('has_bg_switch'):
            p = peer_label()
            if p.lower() in ('android', '未知'):
                return 'android 后台采集无声', '安卓后台采集无声'
            return f'{p} 后台采集无声', '后台采集无声'
        return f'{peer_cn()}采集无声', None

    # 6. 采集弱音
    if cap_stats.get('weak'):
        p = peer_cn()
        if p == 'iOS':
            return 'iOS端采集声音很小 无异常 怀疑当时没说话', None
        return f'{p}采集弱音？', None

    # 7. mute / 停止采集 / 麦克风软件音量为0
    # 判定规则（与 soul-ticket-dashboard 一致）：
    # - 采集音量avg > 2000 且 zero_pct < 20% → mute 只是短暂的，跳过
    # - 采集音量avg < 500 → mute+疑似没讲话
    # - 其他（包括 500~2000）→ mute 是主因
    if sf.get('has_mute'):
        cap_avg = cap_stats.get('avg', 0)
        cap_total = cap_stats.get('total', 0)
        cap_zero = cap_stats.get('zero_pct', 0)

        if sf.get('capture_start_failed'):
            pass  # 采集启动失败优先（已在 #4 处理）
        elif sf.get('mic_volume_zero'):
            # 麦克风软件音量被设置为0 → 明确的停止采集行为
            return f'{peer_label()}上行端麦克风音量被设为0，停止采集', 'mute操作'
        elif cap_total > 0 and cap_avg > 2000 and cap_zero < 20:
            pass  # 采集音量正常 → mute只是短暂的，跳过
        elif cap_total > 0 and cap_avg < 500:
            return 'mute静音+疑似没有人讲话', 'mute操作'
        elif cap_total == 0:
            return f'{peer_label()}上行端 mute 静音', 'mute操作'
        else:
            # 有采集数据且音量不太高（500~2000）→ mute 是主因
            return f'{peer_label()}上行端 mute 静音', 'mute操作'

    # 8. 后台采集问题
    if sf.get('has_bg_switch'):
        p = peer_label()
        cap_avg = cap_stats.get('avg', 0)
        cap_total = cap_stats.get('total', 0)
        cap_zero = cap_stats.get('zero_pct', 0)
        if not (cap_total > 0 and cap_avg > 1000 and cap_zero < 30):
            if not sf.get('has_start_local_audio'):
                if p.lower() in ('android', '未知'):
                    return 'android 后台采集无声', '安卓后台采集无声'
                return 'iOS 切后台未执行 startLocalAudio', '未调用startlocalaudio'
            elif sf.get('bg_no_return'):
                return f'{p} 后台采集无声', '后台采集无声'

    # 9. 采集打断
    if sf.get('has_capture_interrupt') and not sf.get('capture_interrupt_recovered', False):
        return f'{peer_label()}上行端采播打断', '正常采集打断事件'

    # 10. 疑似没讲话（只有在排除了所有异常事件后才走到这里）
    cap_avg = cap_stats.get('avg', 0)
    cap_total = cap_stats.get('total', 0)
    if cap_total > 0 and 0 < cap_avg < 1500:
        return '疑似没讲话', None
    if cap_total == 0 and play_stats.get('total', 0) > 0:
        return '疑似没讲话', None

    # 11. 双端数据都空
    if cap_stats.get('total', 0) == 0 and play_stats.get('total', 0) == 0:
        return '疑似没讲话', None

    return '数据正常', None


def detect_platform(user_info):
    """从 getUserInfo 返回的数据中检测平台"""
    if not user_info:
        return '未知'
    os_name = str(user_info.get('Os', '') or '').lower()
    dev = str(user_info.get('DeviceType', '') or '').lower()
    if 'ios' in os_name or 'iphone' in dev or 'ipad' in dev:
        return 'iOS'
    if 'android' in os_name:
        return 'android'
    if dev and any(k in dev for k in ['iphone', 'ipad', 'ipod']):
        return 'iOS'
    if dev:
        return 'android'
    return '未知'


# ═══════════════════════════════════════════════════════════
# 深度分析：调用 API 获取事件+音量数据
# ═══════════════════════════════════════════════════════════

def fetch_deep_analysis(fetch_fn, room_info, sdkappid,
                        send_user_id, recv_user_id):
    """获取深度分析数据"""
    comm_id = room_info['comm_id']
    create_ts = room_info['create_time']
    destroy_ts = room_info['destroy_time']
    room_num = room_info['room_num']

    result = {
        'users': {},
        'sender_analysis': {'findings': [], 'flags': {}},
        'receiver_analysis': {'findings': [], 'flags': {}},
        'audio_analysis': {'findings': [], 'cap_stats': {}, 'play_stats': {}},
    }

    # 1. getUserInfo — 双端
    for uid in [send_user_id, recv_user_id]:
        if not uid:
            continue
        try:
            url = (
                f"https://{TRTC_API_HOST}/getUserInfo"
                f"?SdkAppId={sdkappid}"
                f"&CommId={comm_id}"
                f"&StartTs={create_ts}"
                f"&EndTs={destroy_ts}"
                f"&UserId={uid}"
            )
            data = fetch_fn(url)
            user_list = data.get('Response', {}).get('UserList', [])
            if user_list:
                result['users'][uid] = user_list[0]
                log(f"  getUserInfo({uid}): TinyId={user_list[0].get('TinyId','?')}, "
                    f"Os={user_list[0].get('Os','?')}, Device={user_list[0].get('DeviceType','?')}")
            else:
                log(f"  getUserInfo({uid}): 无数据")
        except Exception as e:
            log(f"  getUserInfo({uid}) 失败: {e}")
        time.sleep(0.1)

    # 2. detail_event — 双端
    for uid, role in [(send_user_id, 'sender'), (recv_user_id, 'receiver')]:
        if not uid:
            continue
        tiny_id = result['users'].get(uid, {}).get('TinyId', '')
        if not tiny_id:
            log(f"  {role}({uid}) 无 TinyId，跳过事件分析")
            continue
        try:
            url = (
                f"https://{TRTC_API_HOST}/getElasticSearchData"
                f"?StartTs={create_ts}&EndTs={destroy_ts}"
                f"&CommId={comm_id}&UserId={uid}&TinyId={tiny_id}"
                f"&RoomNum={room_num}"
                f"&IndexType=event&DataType=detail_event"
            )
            data = fetch_fn(url)
            resp_data = data.get('Response', {}).get('Data', [])
            if resp_data:
                events = resp_data[0].get('Content', [])
                analysis = analyze_events(events)
                result[f'{role}_analysis'] = analysis
                log(f"  {role}({uid}) 事件: {len(events)}条, 发现: {len(analysis['findings'])}项")
            else:
                log(f"  {role}({uid}) 事件: 无数据")
        except Exception as e:
            log(f"  {role}({uid}) 事件分析失败: {e}")
        time.sleep(0.1)

    # 3. aCapEnergy — 发送端上行采集音量
    send_tiny = result['users'].get(send_user_id, {}).get('TinyId', '')
    cap_energy = []
    if send_user_id and send_tiny:
        try:
            url = (
                f"https://{TRTC_API_HOST}/getElasticSearchData"
                f"?StartTs={create_ts}&EndTs={destroy_ts}"
                f"&CommId={comm_id}&UserId={send_user_id}&TinyId={send_tiny}"
                f"&RoomNum={room_num}"
                f"&IndexType=up&DataType=aCapEnergy"
            )
            data = fetch_fn(url)
            resp_data = data.get('Response', {}).get('Data', [])
            if resp_data:
                cap_energy = resp_data[0].get('Content', [])
                log(f"  发送端采集音量: {len(cap_energy)}个采样点")
        except Exception as e:
            log(f"  发送端采集音量获取失败: {e}")

    # 4. aPlayEnergy — 接收端下行播放音量
    recv_tiny = result['users'].get(recv_user_id, {}).get('TinyId', '')
    play_energy = []
    if recv_user_id and recv_tiny:
        try:
            url = (
                f"https://{TRTC_API_HOST}/getElasticSearchData"
                f"?StartTs={create_ts}&EndTs={destroy_ts}"
                f"&CommId={comm_id}&UserId={recv_user_id}&TinyId={recv_tiny}"
                f"&RoomNum={room_num}"
                f"&IndexType=down&DataType=aPlayEnergy"
            )
            data = fetch_fn(url)
            resp_data = data.get('Response', {}).get('Data', [])
            if resp_data:
                play_energy = resp_data[0].get('Content', [])
                log(f"  接收端播放音量: {len(play_energy)}个采样点")
        except Exception as e:
            log(f"  接收端播放音量获取失败: {e}")

    result['audio_analysis'] = analyze_audio_metrics(cap_energy, play_energy)

    return result


# ═══════════════════════════════════════════════════════════
# 页面事件抓取：从 call-details-user 页面抓取详细事件列表
# ═══════════════════════════════════════════════════════════

def fetch_page_events(page, user_detail_url):
    """打开用户级通话详情页，点击"查看详细事件"按钮，抓取完整事件列表。

    Args:
        page: Playwright page 对象（已登录）
        user_detail_url: call-details-user 页面 URL

    Returns:
        dict: {'sender_events': [...], 'receiver_events': [...]}
              每个事件格式: {'time': '2026-03-12 16:38:17.670', 'event': '停止采集音频'}
    """
    result = {'sender_events': [], 'receiver_events': []}

    try:
        log("  [页面事件] 打开用户级详情页...")
        page.goto(user_detail_url, timeout=30000, wait_until='networkidle')
        time.sleep(3)

        # 点击"查看详细事件"按钮
        btn = page.locator('button:has-text("查看详细事件")')
        if btn.count() == 0:
            log("  [页面事件] 未找到\"查看详细事件\"按钮，跳过")
            return result

        btn.click()
        log("  [页面事件] 已点击\"查看详细事件\"按钮，等待加载...")
        time.sleep(5)

        # 弹窗内有多个 table：
        # - table[0]/[1]: 顶部通话概览表
        # - table[2]: 发送端表头（时间/事件）
        # - table[3]: 发送端事件数据行
        # - table[4]: 接收端表头（时间/事件）
        # - table[5]: 接收端事件数据行
        tables = page.query_selector_all('table')
        log(f"  [页面事件] 找到 {len(tables)} 个 table")

        for table_idx, key in [(3, 'sender_events'), (5, 'receiver_events')]:
            if table_idx >= len(tables):
                continue
            tbl = tables[table_idx]
            rows = tbl.query_selector_all('tr')
            for row in rows:
                cells = row.query_selector_all('td')
                if len(cells) >= 2:
                    time_text = cells[0].inner_text().strip()
                    event_text = cells[1].inner_text().strip()
                    result[key].append({'time': time_text, 'event': event_text})

        log(f"  [页面事件] 发送端 {len(result['sender_events'])} 条, "
            f"接收端 {len(result['receiver_events'])} 条")
    except Exception as e:
        log(f"  [页面事件] 抓取失败: {e}")

    return result


def analyze_page_events(page_events, role='sender'):
    """分析从页面抓取的详细事件列表，提取 API 未涵盖的关键信息。

    Args:
        page_events: [{'time': '...', 'event': '...'}, ...]
        role: 'sender' 或 'receiver'

    Returns:
        dict: {
            'findings': [...],         # 关键发现列表
            'audio_mute_periods': [],   # 静音时段 [{'start': '...', 'end': '...'}]
            'flags': {                  # 补充标志位
                'page_stop_capture': bool,   # 停止采集音频
                'page_mic_volume_zero': bool, # 麦克风软件音量=0
                'page_sys_play_vol_zero': bool, # 系统播放设备音量=0
                'page_bluetooth': bool,       # 使用蓝牙耳机
                'page_bluetooth_disconnect': bool, # 蓝牙断开
                'page_enter_room_fail': bool, # 进房失败
                'page_timeout_exit': bool,    # 超时退房
                'page_room_enter_count': int, # 进房次数
            }
        }
    """
    findings = []
    flags = {
        'page_stop_capture': False,
        'page_mic_volume_zero': False,
        'page_sys_play_vol_zero': False,
        'page_bluetooth': False,
        'page_bluetooth_disconnect': False,
        'page_enter_room_fail': False,
        'page_timeout_exit': False,
        'page_room_enter_count': 0,
    }
    audio_mute_periods = []
    mute_start = None

    for ev in page_events:
        t = ev['time']
        e = ev['event']

        # 进出房
        if '进入房间成功' in e:
            flags['page_room_enter_count'] += 1
        elif '进入房间失败' in e:
            flags['page_enter_room_fail'] = True
            findings.append(f'进入房间失败({t})')
        elif '超时退房' in e:
            flags['page_timeout_exit'] = True
            findings.append(f'超时退房({t})')

        # 音频采集
        if '停止采集音频' in e:
            flags['page_stop_capture'] = True
            mute_start = t
        elif '开始采集音频' in e:
            if mute_start:
                audio_mute_periods.append({'start': mute_start, 'end': t})
                mute_start = None

        # 麦克风音量
        if '麦克风软件音量被设置为0' in e:
            flags['page_mic_volume_zero'] = True

        # 系统播放设备音量
        if '系统播放设备音量为0' in e:
            flags['page_sys_play_vol_zero'] = True
            findings.append(f'系统播放设备音量为0({t})')

        # 蓝牙
        if '连上蓝牙耳机' in e:
            flags['page_bluetooth'] = True
        if '断开蓝牙耳机' in e:
            flags['page_bluetooth_disconnect'] = True
            findings.append(f'蓝牙耳机断开({t})')

    # 未恢复的静音
    if mute_start:
        audio_mute_periods.append({'start': mute_start, 'end': '通话结束'})

    # 汇总发现
    if flags['page_stop_capture']:
        count = sum(1 for ev in page_events if '停止采集音频' in ev['event'])
        findings.insert(0, f'停止采集音频 x{count} 次')
    if flags['page_mic_volume_zero']:
        count = sum(1 for ev in page_events if '麦克风软件音量被设置为0' in ev['event'])
        findings.insert(0, f'麦克风软件音量=0 x{count} 次')
    if flags['page_sys_play_vol_zero']:
        count = sum(1 for ev in page_events if '系统播放设备音量为0' in ev['event'])
        findings.insert(0, f'系统播放设备音量=0 x{count} 次')
    if flags['page_room_enter_count'] > 2:
        findings.insert(0, f'频繁进出房间({flags["page_room_enter_count"]}次)')

    return {
        'findings': findings,
        'audio_mute_periods': audio_mute_periods,
        'flags': flags,
    }


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description='TRTC 通话详情 URL + 深度排查')
    parser.add_argument('--sdkappid', required=True, help='SDK App ID')
    parser.add_argument('--room', default='', help='房间号 (roomNum)')
    parser.add_argument('--userid', default='', help='用户ID (可选，用于搜索)')
    parser.add_argument('--start-ts', required=True, type=int, help='开始时间戳(秒)')
    parser.add_argument('--end-ts', required=True, type=int, help='结束时间戳(秒)')
    parser.add_argument('--environment', default='', help='环境: inland/intl')
    parser.add_argument('--sender', default='', help='发送端 userId (被投诉方)')
    parser.add_argument('--receiver', default='', help='接收端 userId (反馈方)')
    parser.add_argument('--description', default='', help='问题描述')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    args = parser.parse_args()

    sdkappid = args.sdkappid.strip()
    room = args.room.strip()
    userid = args.userid.strip()
    start_ts = args.start_ts
    end_ts = args.end_ts
    sender = args.sender.strip()
    receiver = args.receiver.strip()
    description = args.description.strip()

    # 自动判断环境
    if args.environment:
        env = args.environment
    elif sdkappid.startswith('200'):
        env = 'intl'
    else:
        env = 'inland'

    search_url = build_search_url(sdkappid, room, userid, env, start_ts, end_ts)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({
            'success': False,
            'error': 'playwright 未安装，请运行: pip install playwright && playwright install chromium',
            'search_url': search_url,
        }))
        sys.exit(1)

    api_url = build_roomlist_api_url(sdkappid, room, start_ts, end_ts, userid)
    log("正在启动浏览器...")

    with sync_playwright() as pw:
        # 清理残留锁文件
        for lock in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
            lock_path = os.path.join(PW_USER_DATA_DIR, lock)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except OSError:
                    pass

        browser = pw.chromium.launch_persistent_context(
            user_data_dir=PW_USER_DATA_DIR,
            headless=args.headless,
            args=['--disable-blink-features=AutomationControlled'],
            viewport={'width': 1280, 'height': 800},
        )
        page = browser.new_page()

        # 检查登录态
        page.goto(f'https://{TRTC_MONITOR_HOST}/', timeout=30000, wait_until='domcontentloaded')
        time.sleep(3)

        current_url = page.url
        if 'passport.woa.com' in current_url or 'login' in current_url.lower():
            if args.headless:
                log("headless 模式下登录态失效，请先用非 headless 模式运行一次。")
                browser.close()
                print(json.dumps({
                    'success': False,
                    'error': '登录态失效，请先运行一次非 headless 模式完成 OA 登录',
                    'search_url': search_url,
                }))
                sys.exit(1)

            log("\n" + "=" * 50)
            log("需要 OA 登录！请在弹出的浏览器窗口中完成 iOA 验证")
            log("=" * 50 + "\n")

            try:
                page.wait_for_url(f'https://{TRTC_MONITOR_HOST}/**', timeout=300000)
                log("登录成功！Cookie 已保存。\n")
                time.sleep(2)
            except Exception:
                log("登录超时（5分钟）。")
                browser.close()
                print(json.dumps({
                    'success': False,
                    'error': '登录超时',
                    'search_url': search_url,
                }))
                sys.exit(1)
        else:
            log("已有登录态，直接使用。")

        # fetch 工具函数
        def fetch_json(url):
            resp = page.evaluate("""
                async (url) => {
                    const resp = await fetch(url, { credentials: 'include' });
                    return await resp.text();
                }
            """, url)
            return json.loads(resp)

        log(f"查询通话记录: sdkAppId={sdkappid} room={room}")

        # Step 1: getRoomList
        try:
            data = fetch_json(api_url)
        except Exception as e:
            browser.close()
            print(json.dumps({
                'success': False,
                'error': f'getRoomList 调用失败: {e}',
                'search_url': search_url,
            }))
            sys.exit(1)

        # 解析房间列表
        resp = data.get('Response', data)
        room_list = resp.get('RoomList', resp.get('roomList', []))
        if not room_list and 'Data' in resp:
            room_list = resp['Data'] if isinstance(resp['Data'], list) else []

        if not room_list:
            browser.close()
            print(json.dumps({
                'success': False,
                'error': '未找到通话记录，请检查参数和时间范围',
                'search_url': search_url,
                'rooms_count': 0,
            }))
            sys.exit(0)

        # 取第一条有效记录
        room_info = None
        for r in room_list:
            info = extract_room_info(r, room)
            if info['comm_id']:
                room_info = info
                break

        if not room_info:
            browser.close()
            print(json.dumps({
                'success': False,
                'error': '通话记录中无有效 CommId',
                'search_url': search_url,
                'rooms_count': len(room_list),
            }))
            sys.exit(0)

        detail_url = build_detail_url(
            room_info['comm_id'], room_info['room_num'], room_info['room_str'],
            room_info['create_time'], room_info['destroy_time'],
            room_info['duration'], room_info['finished'], sdkappid, env
        )
        log(f"CommId: {room_info['comm_id']}, 时长: {room_info['duration']}秒")

        # Step 2: 深度分析（如果提供了 sender/receiver）
        deep_result = None
        conclusion = None
        tag = None

        if sender or receiver:
            log(f"\n开始深度分析: sender={sender}, receiver={receiver}")
            deep_result = fetch_deep_analysis(
                fetch_json, room_info, sdkappid, sender, receiver
            )

            # 推断结论
            sender_platform = detect_platform(deep_result['users'].get(sender))
            receiver_platform = detect_platform(deep_result['users'].get(receiver))
            sender_has_info = bool(deep_result['users'].get(sender))

            sender_analysis = deep_result.get('sender_analysis', {})
            receiver_analysis = deep_result.get('receiver_analysis', {})
            audio_analysis = deep_result.get('audio_analysis', {})

            conclusion, tag = infer_conclusion(
                sender_analysis.get('flags'),
                receiver_analysis.get('flags'),
                audio_analysis.get('cap_stats', {}),
                audio_analysis.get('play_stats', {}),
                room_info['user_count'],
                sender_platform,
                receiver_platform,
                sender_has_info,
            )
            log(f"\n结论(API数据): {conclusion}")
            if tag:
                log(f"标签: {tag}")

            # Step 3: 从页面抓取详细事件列表（补充 API 缺失的事件）
            if sender and receiver:
                user_detail_url = build_user_detail_url(
                    room_info['comm_id'], room_info['room_num'],
                    room_info['room_str'], room_info['create_time'],
                    room_info['destroy_time'], room_info['duration'],
                    room_info['finished'], sdkappid, env,
                    sender, receiver, room_info['user_count'],
                )
                log(f"\n抓取页面详细事件...")
                page_events = fetch_page_events(page, user_detail_url)

                page_sender_analysis = None
                page_receiver_analysis = None
                if page_events['sender_events']:
                    page_sender_analysis = analyze_page_events(
                        page_events['sender_events'], 'sender')
                    log(f"  发送端页面事件发现: {page_sender_analysis['findings'][:5]}")
                if page_events['receiver_events']:
                    page_receiver_analysis = analyze_page_events(
                        page_events['receiver_events'], 'receiver')
                    log(f"  接收端页面事件发现: {page_receiver_analysis['findings'][:5]}")

                deep_result['page_events'] = {
                    'sender': page_sender_analysis,
                    'receiver': page_receiver_analysis,
                }

                # 用页面事件补充结论判断
                # 如果页面发现接收端"系统播放设备音量为0"，这比 API 结论优先
                if page_receiver_analysis and page_receiver_analysis['flags'].get('page_sys_play_vol_zero'):
                    conclusion = '接收端系统播放设备音量为0，听不到声音'
                    tag = '接收端播放音量为0'
                    log(f"  [页面事件覆盖] 新结论: {conclusion}")
                # 如果页面发现发送端有多次停止采集+麦克风音量为0
                elif page_sender_analysis and page_sender_analysis['flags'].get('page_stop_capture'):
                    sf_page = page_sender_analysis['flags']
                    # 检查是否有恢复（有 audio_mute_periods 说明有恢复）
                    periods = page_sender_analysis.get('audio_mute_periods', [])
                    all_recovered = all(p['end'] != '通话结束' for p in periods)
                    if not all_recovered:
                        conclusion = f'{sender_platform}上行端停止采集音频未恢复'
                        tag = '停止采集未恢复'
                        log(f"  [页面事件覆盖] 新结论: {conclusion}")
                    elif periods and len(periods) > 3:
                        conclusion = f'{sender_platform}上行端反复静音/取消静音({len(periods)}次)，属于应用层mute控制'
                        tag = 'mute操作'
                        log(f"  [页面事件补充] 新结论: {conclusion}")

                log(f"\n最终结论: {conclusion}")

        browser.close()

        # 构造输出
        output = {
            'success': True,
            'detail_url': detail_url,
            'search_url': search_url,
            'room_info': {
                'comm_id': room_info['comm_id'],
                'room_num': room_info['room_num'],
                'room_str': room_info['room_str'],
                'create_time': room_info['create_time'],
                'destroy_time': room_info['destroy_time'],
                'duration': room_info['duration'],
                'user_count': room_info['user_count'],
            },
            'rooms_count': len(room_list),
        }

        if deep_result:
            sender_analysis = deep_result.get('sender_analysis', {})
            receiver_analysis = deep_result.get('receiver_analysis', {})
            audio_analysis = deep_result.get('audio_analysis', {})

            output['deep_analysis'] = {
                'sender': {
                    'user_id': sender,
                    'platform': detect_platform(deep_result['users'].get(sender)),
                    'device': deep_result['users'].get(sender, {}).get('DeviceType', ''),
                    'os': deep_result['users'].get(sender, {}).get('Os', ''),
                    'findings': sender_analysis.get('findings', []),
                    'flags': sender_analysis.get('flags', {}),
                },
                'receiver': {
                    'user_id': receiver,
                    'platform': detect_platform(deep_result['users'].get(receiver)),
                    'device': deep_result['users'].get(receiver, {}).get('DeviceType', ''),
                    'os': deep_result['users'].get(receiver, {}).get('Os', ''),
                    'findings': receiver_analysis.get('findings', []),
                    'flags': receiver_analysis.get('flags', {}),
                },
                'audio': {
                    'cap_stats': audio_analysis.get('cap_stats', {}),
                    'play_stats': audio_analysis.get('play_stats', {}),
                    'findings': audio_analysis.get('findings', []),
                },
            }

            # 添加页面事件分析结果
            page_ev = deep_result.get('page_events', {})
            if page_ev:
                if page_ev.get('sender'):
                    output['deep_analysis']['sender']['page_events'] = {
                        'findings': page_ev['sender'].get('findings', []),
                        'flags': page_ev['sender'].get('flags', {}),
                        'audio_mute_periods': page_ev['sender'].get('audio_mute_periods', []),
                    }
                if page_ev.get('receiver'):
                    output['deep_analysis']['receiver']['page_events'] = {
                        'findings': page_ev['receiver'].get('findings', []),
                        'flags': page_ev['receiver'].get('flags', {}),
                    }

        if conclusion:
            output['conclusion'] = conclusion
        if tag:
            output['tag'] = tag
        if description:
            output['description'] = description

        print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
