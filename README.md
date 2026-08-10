# 学位英语学习系统

电脑版 + 安卓离线 App。学习进度在 `users/`，多电脑用 git 同步。

## 电脑端启动

双击 `启动学习系统.bat`，浏览器打开启动窗口提示的地址（默认 `http://localhost:5000`）。

## 换电脑 / 拉代码后

```bash
git pull
npm install                 # 仅打包 App 时需要
py -3 _build_app.py         # 生成 app/（不进 git，约 1.4MB，由页面/词库/题库拷贝而来）
```

- 只学不用打包：`git pull` 后直接跑 bat 即可
- 要打安卓包：生成 `app/` 后按 `APP打包说明.md` 继续（`npx cap sync android` → gradle）

## 提交学习进度

双击 `提交进度.bat`，或：

```bash
git add users/
git commit -m "学习进度"
git pull --rebase
git push
```

## 相关说明

- 安卓打包与签名：`APP打包说明.md`
- 学习计划 / 进度档案：`学习计划.md`、`学习进度.md`
