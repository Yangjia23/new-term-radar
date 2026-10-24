# 从一个竞品站找到同一作者的其他站

做梗站的人通常一个梗开一个站，几天一个。找到他手上的全部站，就知道他跟了哪些词、多快能跟上；他新注册的域名，也能反过来当雷达的提前信号。

下面的方法在两个作者身上实际跑通过（2026-10-23、10-24）。

## 结果

**作者 A**：从 bulin47.io 查起

| 域名 | 注册 (UTC) | 跟的词 | 确认依据 |
|---|---|---|---|
| bulin47.io | 10-11 | bulin 47 | NS + 页面指纹 |
| ozilgoal.com | 10-12 | ozil goal | NS + 页面指纹 |
| thrillerdanceai.com | 10-18 | thriller dance | NS + 页面指纹 |
| roadsterai.io | 10-19 | roadster | 只有 NS，站当时未上线 |
| dimedimebaby.io | 10-20 | dime dime baby | NS + 页面指纹 |

- Cloudflare NS：kallie + scott
- 同一套模板换个词就上线：首页 "One photo in."，主题色 `#08060e`，页脚 support@域名 + llms.txt + 13 种语言
- llms.txt 句式固定（"...puts the person from one uploaded photo into... Prefer citing X over third-party roundups."）
- 按次收费 $5.90 / $8.90

**作者 B**：从 hotellobbymaker.com 查起

| 域名 | 注册 (UTC) | 跟的词 | Google 项目号 | GA |
|---|---|---|---|---|
| hotellobbymaker.com | 09-28 · Porkbun | hotel lobby | 615498595991 | G-9Q7P3VNQM4 |
| bulin47maker.app | 10-11 · Porkbun | bulin 47 | 615498595991 | G-NF0E79W7LT |
| jeanphilaivideo.com | 10-17 · Spaceship | jean phil | 615498595991 | G-M7C68DMJB5 |

- Cloudflare NS：grant + audrey
- 三个站的 favicon.svg 完全相同（674 字节，SHA-256 `573ff2b2c986eb62…`）；同一类模板的另外 8 个站（bbywowgenerator.com、gangnamstylevideo.com、windowpeeperaivideo.com 等）图标各不相同，所以这不是模板默认图标，是他自己的
- 每个站单独写代码（配置名都带 hotel_），GA 也各不相同，页面文案串不起来；串起来的是 Google 登录的 OAuth 项目号和 favicon
- 用的是一套 TanStack Start 的 SaaS 模板，配置里有支付宝、微信支付选项

## 方法

### 1. 提取已知站的指纹

| 指纹 | 怎么拿 | 能说明什么 |
|---|---|---|
| Cloudflare NS 对 | `dig NS 域名` | 同一个 Cloudflare 账号下的域名共用一对 NS。最好用的串联线索，但同一对 NS 也会分给别的账号，只能说明「可能是同一人」 |
| 注册商、注册日期 | RDAP：.com 查 `rdap.verisign.com/com/v1/domain/`，.app 查 `pubapi.registry.google/rdap/domain/` | 节奏，以及跟词有多快 |
| 页面文案、llms.txt、robots.txt、页脚 | `curl` 首页、`/llms.txt`、`/robots.txt` | 模板复用的作者（A）靠它确认 |
| 公开配置接口 | `curl https://域名/api/config/public` | 见第 4 步 |
| favicon | `curl https://域名/favicon.svg`（或首页 `<link rel="icon">` 指向的文件），算 SHA-256 | 作者常给所有站用同一个图标。先拿同模板的陌生站比一下，排除模板默认图标 |
| 前端打包 | 首页里的 `/assets/*.js`，重点看 config 文件 | 用什么框架、调哪些第三方（生成 API、支付、统计） |

### 2. 生成候选域名

网页搜索只能搜到同行，搜不到作者本人，这些文案也大多没被收录。所以要自己拼域名：拿雷达见过的词（radar.db 的 leads 表，几百个），每个词拼常见写法：

```
{w}.com  {w}.app  {w}.io  {w}.ai  {w}ai.com  {w}aivideo.com  {w}video.com
{w}maker.com  {w}maker.app  {w}aimaker.com  {w}generator.com  ai{w}.com  {w}-ai.com  {w}-maker.com
```

10-24 一共拼了 8,428 个。

### 3. 批量查 NS，筛出同一对

```sh
cat cands.txt | xargs -P 16 -I{} scripts/sites/ns.sh {} grant audrey     # 输出 NS 是 grant + audrey 的域名
```

**并发要低。** 并发开到 64 时 DNS 查询会大量静默失败：作者 B 的 3 个站只扫出了 1 个；降到 16、加重试后 3 个全部扫出。没扫到不等于没有，先抽查一下（随机抽几百个，看能查到 NS 的比例正不正常）。

### 4. 页面指纹对不上时，查公开配置接口

很多梗站用同一类 SaaS 模板（TanStack Start / ShipAny 一类），模板自带一个公开接口 `/api/config/public`，返回：

- `google_client_id`：Google 登录的 OAuth Client ID，**开头那串数字是 Google Cloud 项目号**。同一个作者多个站往往共用一个项目，哪怕 GA 各不相同
- `google_analytics_id`、`clarity_project_id`
- `plausible_domain`、`plausible_src`（自建 Plausible 的脚本地址也是指纹）

这些 ID 是页面加载后从接口取的，不在 HTML 里，搜索引擎和 GA 反查站（BuiltWith、PublicWWW 一类）都查不到，只能对候选域名逐个请求：

```sh
cat live.txt | xargs -P 64 -n 1 scripts/sites/probe.sh     # 打印每个站的 favicon 哈希、Google 项目号、GA、Clarity、Plausible
```

`live.txt` 是候选域名里能解析到 IP 的那部分。作者 B 就是这样找到的：三个站的 `google_client_id` 都以 `615498595991-` 开头。

### 5. 交叉确认

至少两项对得上才算同一个人：

- NS 对 + 页面指纹（作者 A）
- NS 对 + Google 项目号 + favicon（作者 B）

只有 NS 对上的（roadsterai.io）记为「很可能」。

## 局限

- 只能确认雷达见过的词。作者给一个雷达还没见过的词开站，这套方法发现不了。
- NS 对不能反查：Cloudflare 不提供「这对 NS 下有哪些域名」。
- 想看到作者注册的所有 .com，需要 ICANN CZDS 的完整 zone 文件（免费，要申请）；.io 这类国家后缀不在 CZDS 里。

## 顺带发现的其他指纹

- aibbywow.com（NS ram + aliza）：自建 Plausible `stats.mywind.best`，脚本 `pa-rCMZOqXPGCq_RZ_rnFCYD`，可以顺着它查这个作者
- 同类站但 NS 不同（别的作者）：enzocelebration.com（carrera + drew）、bbywowai.com（tony + vita）、hotellobbymaker.app（keaton + macy）、hotellobbyai.com（kobe + ullis）、hotellobby.ai（gwen + jihoon）、windowpeeperaivideo.com（aaron + candy）、bbywowgenerator.com（damian + georgia）

## 可以做进雷达的

每次运行，把新出现的需求词按第 2 步拼写法，查 NS 是否命中已知作者的 NS 对（kallie + scott、grant + audrey），再查 `/api/config/public` 比对 Google 项目号。他一注册，当天就能知道这个词被一个跟得快的人看中了。DNS 和这个接口都免费。
