# 部署到 GitHub Actions（免费 7×24，不用电脑）

**为什么选它**：你的源只剩 Telegram（境外）。GitHub Actions 的服务器本来就在境外，
**访问 Telegram 是直连，不需要任何代理**——国内云反而要自己搭代理，更麻烦。

成本：**0 元**。不用买服务器、不用装 Docker、不用常开电脑。

---

## 一、建仓库

1. 打开 https://github.com/new
2. 仓库名随便，比如 `linebao-monitor`
3. **推荐选 Public**（Actions 无限免费）；Private 也行，但每月只有 2000 分钟免费额度
4. 点 Create repository

---

## 二、上传项目文件

在项目目录执行（把 `<你的用户名>` 换成你的 GitHub 用户名）：

```bash
cd linebao-monitor
git init
git add .
git commit -m "线报监测助手"
git branch -M main
git remote add origin https://github.com/<你的用户名>/linebao-monitor.git
git push -u origin main
```

> ⚠️ **`.env` 不会被上传**（`.gitignore` 已排除），里面的飞书密钥不会泄露。
> 如果 git 提示要加 `.env`，**停下来**，别加。

---

## 三、配置飞书密钥（关键一步）

1. 进入仓库 → **Settings** → 左侧 **Secrets and variables** → **Actions**
2. 点 **New repository secret**
3. 添加两条：

| Name | Secret |
|---|---|
| `LINEBAO_FEISHU_WEBHOOK` | 你的飞书群机器人 Webhook 地址 |
| `LINEBAO_FEISHU_SECRET` | 没开签名校验就留空 / 不建这条也行 |

> 密钥存在 GitHub 的加密存储里，**不会出现在代码、日志、仓库历史中**。

---

## 四、验证

1. 仓库 → **Actions** 标签页
2. 左侧选「线报监测」→ 右侧 **Run workflow** → 点绿色按钮
3. 等十几秒，点进这次运行，看 **运行监测** 那一步的日志
4. 应该能看到 `[telegram] 今日有羊毛 -> N 条` 和 `飞书推送成功`
5. 手机飞书应该收到消息

跑通后，它就会**每 30 分钟自动跑一次**，跟你电脑开不开机没关系了。

---

## ⚠️ 必须知道的限制

1. **不准点**。GitHub 的定时任务在高峰期可能延迟 5~15 分钟，甚至偶尔跳过。
   线报本来就讲究时效，这点要接受；想要准点就得上云服务器。
2. **cron 用 UTC**。`*/30 * * * *` 是「每 30 分钟」，与时区无关，不用换算。
3. **去重库靠 cache**。GitHub 的 cache 可能过期或被淘汰（7 天不访问会清理），
   万一丢了，下一轮会把最近的线报当新的重推一次——**不影响正确性，只是偶尔重复**。
4. **境外访问国内源会被反爬**（比如没得比、什么值得买）。
   所以如果以后你把国内源开回来，可能会拿不到数据——**国内源适合跑在本地/国内云**。
5. **Public 仓库的代码是公开的**。密钥在 Secrets 里安全，但 `config.yaml`、你的频道列表
   别人能看到。介意的话就用 Private。

---

## 两个方案怎么分工（推荐做法）

| 场景 | 跑在哪 |
|---|---|
| **Telegram 线报**（境外） | **GitHub Actions**（直连，不用代理） |
| 国内源（没得比等，如以后要开） | 本机计划任务（国内直连，走代理反而被拦） |

**也就是说，两套可以同时跑，各管各的。**
