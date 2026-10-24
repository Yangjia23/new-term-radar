# 从一个竞品站找到同一作者的其他站

做梗站的人通常一个梗开一个站，几天一个。找到他手上的全部站，就知道他跟了哪些词、多快能跟上；他新注册的域名，也能反过来当雷达的提前信号。

下面的方法在三个作者身上实际跑通过（2026-10-23、10-24）。

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

**作者 C**：从 toctocdance.com 查起（2026-10-24，Codex 查，主 agent 抽查复核）

20 个站，NS 都是 rita + shane，注册商都是 Spaceship，Next.js 站，统计用 `r.analytic.app/api/script.js?siteId=…`（每站 siteId 不同）。串起来的证据：同一对 NS，加上**同一批 Next.js 构建文件**（chunk 文件名是内容哈希，名字相同说明是同一份代码构建出来的；抽查 carjumpai.com、walkawayexplosion.com、bulin47dembow.com，与 toctocdance.com 的 28 个文件分别有 14、23、23 个同名）。Codex 还报告 aidamehombro.com 直接引用 `assets.bulin47dembow.com` 的视频，主 agent 复核时没取到页面，未确认。

| 注册 (UTC) | 域名 | 跟的词 |
|---|---|---|
| 10-01 | gasstationdance.com | gas station dance（另一版构建，chunk 不共享） |
| 10-02 | carjumpai.com | car jump |
| 10-07 | aiaptmv.com | APT MV |
| 10-08 | aialorsondanse.com | alors on danse |
| 10-08 | burningbridgesaivideo.com | burning bridges |
| 10-08 | rumpelstiltskinai.com | rumpelstiltskin |
| 10-09 | toctocdance.com | toc toc |
| 10-09 | walkawayexplosion.com | walk away explosion |
| 10-10 | bulin47dembow.com | bulin 47 |
| 10-10 | smalltownboydanceai.com | smalltown boy dance |
| 10-11 | unoreversecar.com | uno reverse car |
| 10-12 | putaringonitdog.video | put a ring on it dog |
| 10-12 | venomcarai.com | venom car |
| 10-14 | catclappingmeme.video | cat clapping |
| 10-15 | crazyfrogaitrend.video | crazy frog |
| 10-15 | maiorlazerai.video | maior lazer |
| 10-19 | a2oliteai.video | a2o lite |
| 10-19 | millionairein30days.video | millionaire in 30 days |
| 10-20 | aidamehombro.com | dame hombro |
| 10-21 | moneyflexai.video | money flex |

三周 20 个站，几乎每天一个，是目前找到的最快的作者。toctocdance.com 就是 toc toc 的第一个站（10-09），比雷达推出 toc toc（10-21）早 12 天。他跟的 20 个词里，有 11 个从没进过雷达的词库（walk away explosion、venom car、uno reverse car、money flex、millionaire in 30 days、smalltown boy、maior lazer、alors on danse、gas station dance、APT MV、put a ring on it dog），说明他有雷达没有的来源。

**没找到其他站的**：dimedimebaby.co（10-20 · Spaceship，NS brenda + lou，Google 项目号 248474538179，GA G-Q679N27QG5，标题 "Bby Wow AI Video Generator"）。Codex 查了 10,806 个候选，没有第二个站命中这对 NS 或这个 Google 项目号。

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

至少两项对得上才算同一个人。Next.js 站可以比对首页引用的 `/_next/static/chunks/*.js` 文件名，同名多就是同一份构建（作者 C 就是这样确认的）。

至少两项对得上才算同一个人：

- NS 对 + 页面指纹（作者 A）
- NS 对 + Google 项目号 + favicon（作者 B）
- NS 对 + 同一批构建文件（作者 C）

只有 NS 对上的（roadsterai.io）记为「很可能」。

## 局限

- 只能确认雷达见过的词。作者给一个雷达还没见过的词开站，这套方法发现不了。
- NS 对不能反查：Cloudflare 不提供「这对 NS 下有哪些域名」。
- 想看到作者注册的所有 .com，需要 ICANN CZDS 的完整 zone 文件（免费，要申请）；.io 这类国家后缀不在 CZDS 里。

## 顺带发现的其他指纹

- aibbywow.com（NS ram + aliza）：自建 Plausible `stats.mywind.best`，脚本 `pa-rCMZOqXPGCq_RZ_rnFCYD`，可以顺着它查这个作者
- toctocdance.app（NS art + chin，GA G-Y6MENWTWEM）、rumpelstiltskin.live（NS mitchell + venus）文案和作者 C 相近，基础设施不同，不是同一人
- 同类站但 NS 不同（别的作者）：enzocelebration.com（carrera + drew）、bbywowai.com（tony + vita）、hotellobbymaker.app（keaton + macy）、hotellobbyai.com（kobe + ullis）、hotellobby.ai（gwen + jihoon）、windowpeeperaivideo.com（aaron + candy）、bbywowgenerator.com（damian + georgia）

## 可以做进雷达的

每次运行，把新出现的需求词按第 2 步拼写法，查 NS 是否命中已知作者的 NS 对（kallie + scott、grant + audrey），再查 `/api/config/public` 比对 Google 项目号。他一注册，当天就能知道这个词被一个跟得快的人看中了。DNS 和这个接口都免费。
