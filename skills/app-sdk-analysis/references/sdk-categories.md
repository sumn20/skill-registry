# SDK 分类定义

## 16 大 SDK 分类

### 🎥 音视频 (video)
视频播放器、音频处理、直播SDK、视频编解码、RTC实时通信

**常见 SDK：**
- **声网 Agora** — 全球领先RTC PaaS，标识：`libagora-rtc-sdk.so`, `io.agora.rtc`
- **腾讯 TRTC** — 腾讯实时音视频，标识：`libliteavsdk.so`, `com.tencent.trtc`
- **即构 ZEGO** — 实时音视频PaaS，标识：`libzego-express-engine.so`, `im.zego`
- **火山引擎 RTC (ByteRTC)** — 字节跳动音视频，标识：`libbytertc_sdk.so`, `com.bytedance.rtc`
- **网易云信 RTC** — 网易音视频通信，标识：`libnertc_engine.so`, `com.netease.nimlib`
- **融云 RTC** — IM+RTC一体化，标识：`librong_rtc.so`, `io.rong`
- **阿里云 RTC** — 阿里实时通信，标识：`libAliRTCSdk.so`, `com.alivc.rtc`
- **ExoPlayer** — Google开源播放器，标识：`com.google.android.exoplayer`
- **IJKPlayer** — B站开源播放器，标识：`libijkffmpeg.so`, `libijkplayer.so`
- **FFmpeg** — 音视频编解码，标识：`libffmpeg.so`, `libavcodec.so`
- **WebRTC** — 标准WebRTC，标识：`libwebrtc.so`, `org.webrtc`

### 👥 社交分享 (social)
社交登录、分享SDK、社交媒体集成

**常见 SDK：**
- 微信 OpenSDK — `libwechatxlog.so`, `com.tencent.mm.opensdk`
- QQ互联 — `com.tencent.connect`, `com.tencent.open`
- 微博 SDK — `com.sina.weibo.sdk`
- Facebook SDK — `com.facebook.share`
- Twitter/X SDK — `com.twitter`
- Line SDK — `jp.line.android.sdk`

### 🌐 网络通信 (network)
网络请求、HTTP客户端、WebSocket等

**常见 SDK：**
- OkHttp — `okhttp3`
- Retrofit — `retrofit2`
- Volley — `com.android.volley`
- gRPC — `io.grpc`
- MQTT — Eclipse Paho

### 📢 广告 (ads)
广告SDK、广告网络、广告投放平台

**常见 SDK：**
- Google AdMob — `com.google.android.gms.ads`
- 穿山甲(CSJ) — `com.bytedance.sdk.openadsdk`
- 优量汇(GDT) — `com.qq.e.ads`
- 快手广告 — `com.kwad.sdk`
- Unity Ads — `com.unity3d.ads`
- AppLovin — `com.applovin`
- ironSource — `com.ironsource`
- Mintegral — `com.mbridge.msdk`

### 📊 数据分析 (analytics)
用户分析、埋点跟踪、数据统计

**常见 SDK：**
- Google Analytics / Firebase Analytics — `com.google.firebase.analytics`
- 友盟 — `com.umeng`
- GrowingIO — `com.growingio`
- 神策 — `com.sensorsdata`
- AppsFlyer — `com.appsflyer`
- Adjust — `com.adjust.sdk`

### 📲 消息推送 (push)
推送通知服务

**常见 SDK：**
- Firebase Cloud Messaging — `com.google.firebase.messaging`
- 极光推送 — `cn.jpush`
- 个推 — `com.igexin`
- 华为推送 — `com.huawei.hms.push`
- 小米推送 — `com.xiaomi.mipush`
- OPPO推送 — `com.heytap.msp`
- vivo推送 — `com.vivo.push`

### 💳 支付 (payment)
支付SDK、支付网关

**常见 SDK：**
- 支付宝 — `com.alipay.sdk`
- 微信支付 — `com.tencent.mm.opensdk` (WXPayEntryActivity)
- Google Pay — `com.google.android.gms.wallet`
- PayPal — `com.paypal`
- Stripe — `com.stripe`

### 📍 地图定位 (map)
地图服务、定位SDK、导航

**常见 SDK：**
- 高德地图 — `com.amap`, `libAMapSDK_cl_v9.so`
- 百度地图 — `com.baidu.mapapi`, `libBaiduMapSDK.so`
- 腾讯地图 — `com.tencent.map`
- Google Maps — `com.google.android.gms.maps`

### 🖼️ 图片处理 (image)
图片加载、图片处理、图片编辑

**常见 SDK：**
- Glide — `com.bumptech.glide`
- Picasso — `com.squareup.picasso`
- Fresco — `com.facebook.fresco`
- Coil — `coil`

### 💾 数据存储 (database)
数据库、本地存储、缓存库

**常见 SDK：**
- Room — `androidx.room`
- Realm — `io.realm`
- GreenDAO — `org.greenrobot.greendao`
- SQLCipher — `net.sqlcipher`
- MMKV — `com.tencent.mmkv`

### 🔒 安全加密 (security)
加密算法、安全认证、反作弊

**常见 SDK：**
- 梆梆安全 — `com.secneo`
- 爱加密 — `com.ijiami`
- 360加固 — `com.qihoo`
- 网易易盾 — `com.netease.nis`

### ⚠️ 崩溃监测 (crash)
崩溃日志、错误追踪、异常监测

**常见 SDK：**
- Firebase Crashlytics — `com.google.firebase.crashlytics`
- Bugly — `com.tencent.bugly`
- Sentry — `io.sentry`
- ACRA — `org.acra`

### 🤖 人工智能 (ai)
机器学习、NLP、人脸识别、AI模型

**常见 SDK：**
- TensorFlow Lite — `org.tensorflow.lite`
- ML Kit — `com.google.mlkit`
- 百度AI — `com.baidu.aip`
- 商汤 — `com.sensetime`
- 旷视 — `com.megvii`

### ⚙️ 开发框架 (framework)
应用框架、依赖注入、ORM框架

**常见 SDK：**
- Flutter — `libflutter.so`, `io.flutter`
- React Native — `libreactnativejni.so`, `com.facebook.react`
- Unity — `libunity.so`, `com.unity3d`
- Kotlin — `kotlin.`
- RxJava — `io.reactivex`
- Dagger/Hilt — `dagger.hilt`

### 🔧 系统功能 (system)
系统接口、系统工具

**常见 SDK：**
- AndroidX — `androidx.`
- Google Play Services — `com.google.android.gms`
- Jetpack Compose — `androidx.compose`

### 📦 其他 (other)
其他未分类的SDK
