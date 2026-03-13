# RTC 供应商 SDK 识别特征

本文档用于在APK分析结果中识别具体的RTC音视频供应商。

## 声网 Agora

### Native Library 特征
- `libagora-rtc-sdk.so`
- `libagora-soundtouch.so`
- `libagora-fdkaac.so`
- `libagora-ffmpeg.so`
- `libagora-core.so`
- `libagora_ai_denoise_extension.so`
- `libagora_dav1d_extension.so`
- `libagora_video_process_extension.so`
- `libagora_segmentation_extension.so`

### Component 特征
- `io.agora.rtc.RtcEngine`
- `io.agora.rtc2.RtcEngine`
- `io.agora.mediaplayer`
- `io.agora.base`
- `io.agora.beautyapi`

### 判断结论
发现以上任意特征 → 该App使用 **声网 Agora** RTC 服务

---

## 腾讯 TRTC

### Native Library 特征
- `libliteavsdk.so`
- `libTXSoundTouch.so`
- `libtxffmpeg.so`
- `libtxsoundtouch.so`
- `libtraeiern.so`
- `libtxyvideo.so`
- `libTcVodPlayer.so`
- `libijkffmpeg_tx.so`

### Component 特征
- `com.tencent.trtc`
- `com.tencent.liteav`
- `com.tencent.rtmp`
- `com.tencent.avd`
- `com.tencent.live`

### 判断结论
发现以上任意特征 → 该App使用 **腾讯 TRTC** 音视频服务

---

## 即构 ZEGO

### Native Library 特征
- `libzego-express-engine.so`
- `libZegoExpressEngine.so`
- `libzego-effects.so`
- `libzego-asr.so`
- `libzego-white-board.so`
- `libzego-live-room.so`

### Component 特征
- `im.zego.zegoexpress`
- `im.zego.zego_express_engine`
- `im.zego.zegowhiteboard`
- `im.zego.callsdk`

### 判断结论
发现以上任意特征 → 该App使用 **即构 ZEGO** RTC 服务

---

## 火山引擎 RTC (ByteRTC)

### Native Library 特征
- `libbytertc_sdk.so`
- `libByteRTC.so`
- `libeffect.so` (字节美颜SDK)
- `libbytenn.so`
- `libpag.so`

### Component 特征
- `com.bytedance.rtc`
- `com.ss.bytertc`
- `com.bytedance.labcv`

### 判断结论
发现以上任意特征 → 该App使用 **火山引擎 RTC (ByteRTC)** 服务

---

## 网易云信 RTC

### Native Library 特征
- `libnertc_engine.so`
- `libnim_nertc.so`
- `libnim.so`
- `libnrtc_engine.so`
- `libNEPreprocessor.so`

### Component 特征
- `com.netease.nimlib`
- `com.netease.nertc`
- `com.netease.lava`

### 判断结论
发现以上任意特征 → 该App使用 **网易云信** 音视频服务

---

## 融云 RTC

### Native Library 特征
- `librong_rtc.so`
- `librong_beauty.so`
- `librong_rtc_gsl.so`

### Component 特征
- `io.rong.imlib`
- `io.rong.push`
- `cn.rongcloud.rtc`
- `io.rong.calllib`

### 判断结论
发现以上任意特征 → 该App使用 **融云** IM+RTC 服务

---

## 阿里云 RTC

### Native Library 特征
- `libAliRTCSdk.so`
- `libRTSSDK.so`
- `libalirtc.so`

### Component 特征
- `com.alivc.rtc`
- `com.alivc.player`
- `com.aliyun.rtc`

### 判断结论
发现以上任意特征 → 该App使用 **阿里云 RTC** 服务

---

## 原生 WebRTC

### Native Library 特征
- `libwebrtc.so`
- `libjingle_peerconnection_so.so`

### Component 特征
- `org.webrtc.PeerConnection`
- `org.webrtc.EglBase`

### 判断结论
发现以上特征且无其他RTC供应商特征 → 该App使用 **原生 WebRTC** 自建方案

---

## 快速判断流程

```
1. 扫描 lib/ 目录下的 .so 文件名
2. 扫描 AndroidManifest.xml 中的组件名
3. 按以下优先级匹配:
   ├─ libagora*.so → 声网 Agora
   ├─ libliteavsdk.so / com.tencent.trtc → 腾讯 TRTC
   ├─ libzego*.so / im.zego → 即构 ZEGO
   ├─ libbytertc*.so / com.bytedance.rtc → 火山引擎 RTC
   ├─ libnertc*.so / com.netease → 网易云信
   ├─ librong*.so / io.rong → 融云
   ├─ libAliRTC*.so / com.alivc.rtc → 阿里云 RTC
   └─ libwebrtc.so / org.webrtc → 原生 WebRTC
4. 可能存在多RTC供应商共存（灾备/AB测试）
```

## 注意事项

- 部分App可能同时集成多个RTC SDK（用于灾备切换或AB测试）
- 大型互联网公司（字节、腾讯、阿里）的自有产品通常使用自研RTC方案
- 出海App可能使用不同于国内版的RTC供应商
- SDK版本升级可能导致.so文件名变化，需关注核心特征前缀
