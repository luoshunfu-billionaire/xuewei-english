# 安卓 App 打包与维护说明

学位英语学习系统的安卓离线版，基于 Capacitor 8 打包，数据全部内置，进度存手机本地（localStorage）。

## 日常重新打包（更新了题库/词库/前端后）

```bash
py -3 _build_app.py          # 1. 把 页面/static/词库题库 拷到 app/
npx cap sync android         # 2. 把 app/ 同步进安卓工程（漏了这步打出来的还是旧页面！）
cd android
export JAVA_HOME="D:/dev/jdk-21"   # Capacitor 8 需要 JDK 21
./gradlew.bat assembleRelease      # 3. 构建（sdk 路径在 android/local.properties）
# APK 产出：android/app/build/outputs/apk/release/app-release.apk
```

发 APK 到手机（微信/网盘），直接覆盖安装即可，**进度不会丢**（同一签名覆盖安装保留数据）。

## 关键文件（勿删，务必备份）

| 文件 | 作用 |
|---|---|
| `xuewei-release.keystore` | 发布签名证书（**已提交 git**，换电脑可同签名覆盖安装）。**丢失 = 无法覆盖安装，只能卸载重装、进度清零** |
| `keystore.properties` | 签名密码（**已提交 git**），与 keystore 一起用 |
| `android/` | Capacitor 安卓工程源码（**已提交**；`build/`、`.gradle/`、`local.properties` 仍忽略） |
| `_build_app.py` | Web 资源 → app/ 的拷贝脚本 |
| `capacitor.config.json` | Capacitor 配置（appId、webDir） |

仍建议把 keystore 和 properties 再复制一份到网盘/移动硬盘。

## 换电脑后首次打包

```bash
git pull
npm install
py -3 _build_app.py
npx cap sync android
# 按本机路径写 android/local.properties（sdk.dir=...），并设置 JAVA_HOME 为 JDK 21
cd android
./gradlew.bat assembleRelease
```

`app/`、`node_modules/`、APK 产物不进 git：分别用 `_build_app.py` / `npm install` / gradle 生成。

## 环境（一次性搭建）

- Node 24；**JDK 21**（Capacitor 8 要求；本机曾用 `D:/dev/jdk-21`，构建前设 `JAVA_HOME`）
- Android SDK（cmdline-tools + platform-36 + build-tools 36；本机曾用 `D:/dev/android-sdk`）
- Capacitor 依赖在 `node_modules/`（`npm install` 可恢复）
- SDK 路径写在 `android/local.properties` 的 `sdk.dir`（该文件按机器本地生成，不提交）
- Gradle 下载地址已换成腾讯镜像（`android/gradle/wrapper/gradle-wrapper.properties`）

## 手机端说明

- **连接电脑同步**：打开 App → 在选择用户页填写电脑启动窗口显示的地址（如 `http://192.168.1.8:5000`）→ 点「连接」。手机与电脑须同一 Wi-Fi；地址会记住，下次自动连
- **仅本机**：不填地址也可点「新建并进入」，进度只存在手机；可用导出/导入迁移
- **发音**：App 用系统 TTS。翻到新词会自动读；也可点 🔊。若无声：设置 → 搜索「文字转语音」→ 确认默认引擎可用（小米可用小爱；或装「Google 语音服务」并下载英语语音包）
- **进度迁移**：今日 → 设置 → 导出进度备份（App 内会调起系统分享，可发微信/保存网盘）；另一台设备导入即可
- **PDF 资料**：连上电脑后可在「资料」页打开；未连接时手机版不含 PDF
- **断网**：词库/题库/复习资料仍可用（本地内置）

## 与电脑版的关系

- 电脑双击 bat 启动服务器 → 浏览器访问走服务器同步
- App 配置电脑地址并连接成功 → 与网页共用同一用户进度
- App 未配置或连接失败 → 纯本地模式，同步标识显示「本地」
