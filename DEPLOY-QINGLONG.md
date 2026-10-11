# 部署到青龙面板

青龙面板（QingLong）本质是一个带 Web UI 的定时任务调度器，**天生就是干这个的**。
比在 Windows 上挂计划任务正规，也不用自己写 crontab。

---

## 一、适不适合？——适合

| 你的需求 | 青龙能否满足 |
|---|---|
| 7×24 定时跑 | ✅ 内置调度器，支持 cron |
| 改配置不用改代码 | ✅ `config.yaml` 在线编辑 |
| 装 Python 依赖 | ✅ 依赖管理页，粘贴 requirements.txt 一键装 |
| 看运行日志 | ✅ 每次执行输出都在面板里 |
| 推送到飞书 | ✅ 用脚本自带的 feishu 通道（webhook 走环境变量） |

**不用改一行业务代码**——脚本是标准 CLI，路径也是自适应的（内部用 `__file__` 定位项目根目录）。

---

## 二、部署青龙（Docker Compose）

> ⚠️ **镜像必须选 `debian`。** 本项目依赖 `lxml`（含 C 扩展），alpine 镜像用的是 musl libc，装 lxml 大概率编译失败。这是最容易翻车的一步。

```yaml
services:
  qinglong:
    image: whyour/qinglong:debian      # ← 必须 debian，不要 latest
    container_name: qinglong
    restart: unless-stopped
    ports:
      - "5700:5700"
    environment:
      TZ: Asia/Shanghai
    volumes:
      - ./data:/ql/data
```

```bash
docker compose up -d
# 浏览器打开 http://<你的IP>:5700，按提示初始化账号密码
```

---

## 三、把脚本放进去

### 方式 A：直接上传（简单）

1. 面板 → 脚本管理 → 新建文件夹 `linebao-monitor`
2. 把项目里的 `run.py`、`config.yaml`、`src/` 整个传进去
3. 最终路径形如 `/ql/data/scripts/linebao-monitor/`

### 方式 B：Git 订阅（推荐，便于更新）

1. 面板 → 定时任务 → 添加订阅
2. 填仓库地址（**末尾要加 `.git`**）、分支、检查频率
3. 拉取后同样落在 `/ql/data/scripts/linebao-monitor/`

---

## 四、装依赖

面板 → 依赖管理 → 新建依赖 → 类型选 **Python3** → 把 `requirements.txt` 内容整体粘进去：

```
feedparser requests beautifulsoup4 lxml PyYAML
```

> Python3 依赖**不要**勾「自动拆分」（那是 Node.js 用的）。

---

## 五、建定时任务

面板 → 定时任务 → 新建任务：

| 项 | 值 |
|---|---|
| 名称 | `线报监测` |
| 命令 | `python3 /ql/data/scripts/linebao-monitor/run.py` |
| 定时规则 | `*/10 * * * *`（每 10 分钟） |

> 先手动点一次「运行」看日志，确认没报错，再交给定时。

---

## 六、配飞书推送（走环境变量，不用改 config）

面板 → 环境变量 → 新建：

| 名称 | 值 |
|---|---|
| `LINEBAO_FEISHU_WEBHOOK` | 你的飞书群机器人 Webhook 地址 |
| `LINEBAO_FEISHU_SECRET` | 开了签名校验才填，否则留空 |

然后把 `config.yaml` 里 feishu 的 `enabled` 改成 `true`（**webhook 留空即可**，脚本会去读环境变量）。

> 为什么用环境变量：青龙拉取的脚本可能被覆盖，把密钥写在 config 里会丢，也会随仓库泄露。

---

## 七、验证

手动运行一次，日志里应该能看到：

```
[rss] 没得比·最新 -> 80 条
[rss] 没得比·精选 -> 80 条
...
[html] 已生成预览: /ql/data/scripts/linebao-monitor/data/preview.html
本轮: 抓取 350 | 过滤通过 279 | 新增 279 | 已推送 20
```

---

## ⚠️ 坑与安全（必读）

1. **别把 5700 端口裸开公网。** 青龙历史上有多个 RCE / 认证绕过漏洞（2.20.1 及更早版本有认证绕过风险，请用 **2.20.2+**）。放公网必须加反代认证 + 强密码。
2. **首次运行会推 20 条**（去重库是空的）。之后每轮只推增量。嫌多就把 `max_push_per_run` 调小。
3. **去重库 `data/seen.db` 必须落在持久化目录**。放 `/ql/data/scripts/...` 下天然持久化；**别放 `/tmp`**，否则每轮都当新线报重推。
4. **alpine 镜像 + lxml = 装不上**，务必用 debian 镜像（见第二节）。
5. **青龙生态里大量脚本是「自动签到 / 自动领券」这类灰色脚本。** 本项目不是——它只做「监测 + 推送」，不碰账号、不自动操作。导入来源不明的脚本前请自行判断风险。
6. **境外源（V2EX）在服务器上可能更不稳**，失败会自动跳过，属预期行为，不影响其他源。
