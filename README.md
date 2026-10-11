# 线报监测助手

定时抓取公开优惠信息源 → 关键词/价格过滤 → 去重 → 推送到飞书群。
**只做「监测 + 提醒」，不自动下单、不自动领券。**

---

## 快速开始

```bash
# 1. 先空跑看看抓到了什么（不推送、不写库）
python run.py --dry-run

# 2. 正常跑一轮（按 config.yaml 推送）
python run.py

# 3. 常驻模式，每 300 秒一轮
python run.py --loop 300
```

Windows 下直接双击 `run.bat` 也行（会跑一轮并停住给你看结果）。

---

## 目录结构

```
linebao-monitor/
├── config.yaml          # 唯一需要改的文件：源、关键词、推送
├── run.py               # 启动入口
├── run.bat              # Windows 双击运行
├── requirements.txt
├── data/
│   └── seen.db          # 去重库（SQLite，自动生成）
└── src/
    ├── config.py        # 配置加载
    ├── sources.py       # 抓取（RSS + 网页）
    ├── filters.py       # 过滤（关键词/正则/价格）
    ├── store.py         # 去重
    ├── main.py          # 主流程
    └── notifiers/       # 推送通道：console / feishu / wecom
```

---

## 配置说明（config.yaml）

### 加信息源

**RSS 源**（推荐，最省事）：

```yaml
sources:
  rss:
    - name: "某站优惠"
      url: "https://example.com/feed.xml"
      enabled: true
```

**网页源**（没有 RSS 的站点，自己配 CSS 选择器）：

```yaml
sources:
  web:
    - name: "某聚合站"
      url: "https://example.com/latest"
      item_selector: "ul.news-list > li"   # 每条线报的外层
      title_selector: "a.title"            # 标题
      link_selector: "a.title"             # 链接（默认同标题）
      time_selector: "span.time"           # 时间（可选）
      enabled: true
```

> 找选择器：浏览器 F12 → 右键目标元素 → Copy → Copy selector。

### 过滤规则

```yaml
filters:
  include_keywords:
    - "免费"            # 普通词 = 子串匹配
    - "/0\\.01|1分/"    # /正则/ = 正则匹配（精确，避免 "31元" 命中 "1元"）
  exclude_keywords:
    - "免费加工"         # 挡掉服务类误命中
  max_price: 0          # >0 时只推不超过该价格的（如 9.9）
```

**命中逻辑**：先看排除词，命中直接丢；再看包含词，命中任一才通过；最后看价格上限。

### 推送

```yaml
notify:
  channels:
    - type: "console"   # 本机调试用，建议一直开着
      enabled: true
    - type: "feishu"
      enabled: true
      webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/你的token"
      secret: ""        # 没开签名校验就留空
```

**飞书机器人怎么建**：
飞书群 → 设置 → 群机器人 → 添加「自定义机器人」→ 复制 Webhook 地址 → 粘到上面。

---

## 怎么让它定时跑

### ⭐ 方案一：青龙面板（推荐，7×24 首选）

青龙本质是带 Web UI 的定时任务调度器，天生干这个。完整步骤见 **[DEPLOY-QINGLONG.md](DEPLOY-QINGLONG.md)**。

速记：Docker 起面板 → 脚本传进 `/ql/data/scripts/linebao-monitor/` → 依赖管理粘 `requirements.txt` → 定时任务 `python3 /ql/data/scripts/linebao-monitor/run.py`。

⚠️ 镜像**必须**用 `whyour/qinglong:debian`（alpine 装不上 lxml）。
飞书 webhook 走环境变量 `LINEBAO_FEISHU_WEBHOOK`，脚本会自动启用该通道。

### 方案二：Windows 计划任务（电脑开着就行）

```bat
schtasks /create /tn "线报监测" /sc minute /mo 10 ^
  /tr "\"<venv>\Scripts\python.exe\" \"<项目路径>\run.py\""
```

或直接用 `run.py --loop 600` 挂一个常驻进程。

### 方案三：云函数 / 轻量服务器（不想折腾 Docker 时）

把整个目录打包上传，设置定时触发器（如每 5 分钟）执行 `python run.py`。
腾讯云 SCF、阿里云函数计算都有免费额度，国内节点抓国内源无障碍。

### ⚠️ GitHub Actions 不推荐

runner 在境外，抓国内电商/聚合站可能超时或被地域限制，且调度不保证准点（最小 5 分钟）。

---

## 已知限制（重要，别抱幻想）

1. **不是「全网实时」。** 本工具是定时轮询公开源，延迟分钟级到小时级。
2. **真·「一分钱 / 免费领」基本抓不到。** 实测没得比等聚合源发的是「打折商品」；标题里出现的「免费」多是「免费加工/免费安装」这类服务。
   真正的 0.01 元购、免费派样只存在于**电商官方试用中心、新人专享、品牌派样**，**它们没有公开 RSS**。
3. **大厂反爬凶。** 什么值得买主站、RSSHub 公共实例实测返回 403/JS 挑战页。要稳定拿京东/淘宝的数据，得走**官方联盟 API**（需资质）。
4. **境外源不稳。** V2EX 实测时通时断，失败会自动跳过，不影响其他源。
5. **去重按「标题+链接」**，源站改标题会被当成新条目。

---

## 依赖

```
feedparser, requests, beautifulsoup4, lxml, PyYAML
```

安装：

```bash
pip install -r requirements.txt
```
