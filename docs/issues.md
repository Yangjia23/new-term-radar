# 待解决问题

先讨论清楚，后面统一修改。数据来自 state/radar.db（截至 2026-10-24 00:00 UTC 的 sources 运行）和 10/19 起各次运行的 report.md。

## 处理情况（10-24）

| # | 问题 | 处理 |
|---|---|---|
| 1 | 触发中断 | 真正原因：仓库的 GitHub Actions 被关了（Worker 日志：`422 Actions has been disabled for this repository`），不是 token。用户已重新打开，验证运行 40099705072 成功。触发改为每天 4 次（北京 08/12/17/21 点）；Worker 派发失败时直接发飞书（已部署，飞书 secret 已配） |
| 2 | 推送太多 | 推送只认数据：AI 版（TikTok）、新域名波次、需求词 9 种域名里近 30 天注册 ≥2 个；泛词由需求词提取一并去掉；首个域名超过 14 天或曲线已回落的不推；rising、pages 不再推送 |
| 3 | 同梗多名 | 需求词相同（或一个名字原样包含在另一个里）的合成一张卡；模型知道最近推过哪些梗，同一个梗换说法会归到已推的名字 |
| 4 | 首推/再推 | 推送台账 `state/pushed.json.gz`；首次部署时用 radar.db 里已推过的词初始化。再推只在播放 ×3、账号 ×2 或多注册 3 个域名时，标 📈 升温 |
| 5 | CT 那一行 | 删掉 CT，换成 RDAP 查 9 种写法的注册日期（免费、无 key） |
| 6 | 需求词 | radar/core.py：DeepSeek 按分层拆词，读 AI 版视频的字幕和标签，给出需求词或判定「不是一个梗」 |
| 7 | 打分 | 卡片上不再有分数；judge 只在内部决定什么进观察列表 |
| 8 | 卡片格式 | 两行：名字 + 标签（🆕首推/📈升温、类型、上升中），一行数字 |

用 10-19～10-23 的真实数据回放（真实 DeepSeek + RDAP）：原来推 129 条，现在推 38 条。漏推的已知真梗：perdon、prank edit capcut arrest、tlc no scrubs 被判成「不是一个梗」，c walk、imael angel 没数据（证据不够）。

## 1. 定时触发中断

- 现象：2026-10-24 北京时间 08:00（UTC 00:00）之后没有任何运行。
- 原因：Cloudflare Worker `new-term-radar-trigger` 的 cron 照常触发，但从 UTC 00:30 起每次都是 `scriptThrewException`，调 GitHub dispatch 失败；最可能是 Worker 里的 fine-grained `GITHUB_TOKEN` 到期。
- 处理：10/24 12:40 UTC 换了新 token（`wrangler secret put GITHUB_TOKEN`），等 13:30 UTC 那次 searchwords 验证。
- 换 token 后没有修好：13:30 UTC 那次仍是 `scriptThrewException`，具体报错还在查（wrangler tail 走代理会断开，不走代理才能连上；Observability 查询接口 OAuth 无权限）。
- 遗留：
  - Worker 失败时没有任何告警，这次是人工发现的。
  - 漏跑的 16:00 UTC sources 和 09:15 UTC daily 没有补。
  - 新 token 的有效期要记下来，到期前换。

## 2. 推送量太大，有用的只占约 1/3

推送条数（signals 含 demand/domain/rising/pages，judge ≥ 0.4）：

| 日期 | 条数 | demand | domain | rising | pages |
|---|---|---|---|---|---|
| 10/21 | 41 | 26 | 14 | 1 | 0 |
| 10/22 | 27 | 20 | 1 | 1 | 6 |
| 10/23 | 39 | 28 | 10 | 1 | 0 |

人工粗分 10/23 的 39 条：新的模板/梗词约 12 个，同一个梗重复约 8 条，噪音约 19 条。用户每天还要逐条判断。

噪音的几类：

- 2a. 泛词、常青词：halloween costume、amapiano、hangover、jasonderulo、lamine yamal、2026recap、edit tutorial、genderswap、art style、football edits。
- 2b. 已过气：通知里自己写着「已回落」还推，例如 cake or real、blue collar、babytrend、jeanphil、anime eye（10/23 有 6 条）。目标是越早越好，过气的词没有价值。
- 2c. 垃圾域名：tmcvideo、motion、halal trade、detector360、hivideostudio、viralaivideoplaybook、troquevande、brumzelquix、vitre、membrance，都是通用工具站或随机字符串，不是梗。
- 2d. rising 和 pages 两个来源几乎没有命中：iman gadzhi、インムキング 踊ら せ 方、vikas edit、foto banyak、magic light、fire text、character reference sheets、halloween costume ideas。

## 3. 同一个梗以多个名字重复推送

同一个 trend 换个名字就当新词再推一次：

- toc toc：toc toc / toc toc dance / my door toc toc / toc trend toc toc
- window peeper：window peeper / peeper guide window peeper / learn this window peeper / mr bean（证据是 window peeper 的视频）
- broom：broom riding / one photo broom flying / witch broom crash
- 其他：my girl couple / my girl original couple；talk dirt / fan debiao talk dirty；hit the road dude / hittheroad；imael angel / bad times imael angel；damon salvatore / damon salvatore church scene；mr bean / filtromrbean；unforgettable 24 car trend / unforgettablecar；anime star eye / anime eye；ozil / ozil goal / ozilgoal

来源：domain 的拼写形式（hittheroad）和 demand 的空格形式（hit the road dude）没有合并；TikTok 字幕里抽出的 AI 版名字和观察词不一致，各算一个词。

## 4. 分不清首推还是再推

- 同一个名字会被推两次。window peeper 10/21 第一次推（run 39653414209，模板号 3 个账号），10/23 01:30 UTC 又推（run 39995703934，从观察词 `windowpeepertendenc` 搜到 AI 版，18 个账号、66 万播放），卡片和首推一模一样。
- 没有「这个梗已经推过」的记录，卡片上也没有首推/再推的标记，看不到「首推于哪天、比上次涨了多少」。
- 真正的升温不会专门提醒；重推只是碰巧发生。

## 5. 「已有 N 个站上线（查了 N 个域名）」这一行不可靠

实现见 radar/ct.py：Cert Spotter 查 CT 证书（免费、无 key、有频率限制，429 就停）；每个词查 3 个、每次运行最多 9 个（config `ct`）。域名信号的词查它自己的新域名；其他词把名字去空格后拼 `{名}ai.com`、`{名}.ai`、`{名}.com`。

- 5a. 后缀不够：这几天的梗站多用 .lol / .xyz / .video / .app / .io / .net / .online（carjumpai.lol、teslaflyingcarai.video、roadsteraivideo.xyz），只查 .com/.ai，「还没有站上线」多半是漏查。
- 5b. 写法不够：只拼「名字ai」，没有「ai名字」（aipolarbeartrend.lol）、「名字video」「名字dance」「名字trend」；长名字（pink blush ratatata）几乎不会有人注册完全一样的写法。
- 5c. 每次运行只有前 3 个推送词有这一行，后面的没有，卡片之间不一致。
- 5d. 每小时的 searchwords 不调 CT（只有 sources 和 daily 调 `_live`），而 demand 推送大多出自 searchwords，所以大部分卡片都没有这一行。
- 5e. 有证书不等于梗站：`{名}.com` 可能是多年前的老站，也会算「已上线」，「最早」日期可能早得离谱。

## 6. 拿原始词查域名没有意义，要先找到真正的需求词

用户提的查法（2026-10-24）：

1. 先查需求词本身：`{词}.com / .app / .org`
2. 再查 `{词}ai.com / .app / .org`
3. 如果是视频类的词，再查 `{词}video.com / .app / .org`

前提是先找到真正的需求词，而不是拿雷达抓到的原始词直接去拼域名。

10-24 用 RDAP（免费、无 key：.com 走 Verisign、.org 走 PIR、.app 走 Google Registry）实测三个词的注册日期：

| 写法 | bulin47 | ozilgoal | dimedimebaby |
|---|---|---|---|
| .com | 10-10 | 10-12 | 10-19 |
| .app | 10-10 | 10-13 | 10-19 |
| .org | 10-10 | 10-13 | 10-20 |
| ai.com | 10-09 | 10-12 | 10-19 |
| ai.app | 10-10 | 10-13 | 10-20 |
| ai.org | 10-10 | 10-12 | 10-20 |
| video.com | 10-10 | 10-16 | 10-21 |
| video.app | 10-11 | 10-16 | 未注册 |
| video.org | 10-11 | 10-20 | 未注册 |

- 一个词火起来后，`.com` 和 `ai.com` 最先被注册，两三天内 9 种写法基本全被抢光；video 类写法晚 1～4 天。
- RDAP 给的是注册日期，比 CT 证书（建站上线才签发）早，也不受 WhoisDS 抽样的影响。

雷达抓到的却多是原始词或变体，不是需求词：

| 需求词 | 雷达实际抓到的词（首次日期） |
|---|---|
| dime dime baby | baby wow karol g（10-19）、bby wow song lyric、bby wow dj、bby wow、dancing and eating；dime dime baby 本身 10-21 才出现 |
| bulin 47 | bullyn 47、bullyn47、bulin 47 freestyle、plantilla viral dame hombro、dame hombro、damn hombro |
| ozil goal | ozilgoal（10-16，域名信号）、ozil goal（10-17）、ozil、enzo fernandez、enzo fernandez celebration |

- dime dime baby：10-19 雷达已经在观察「baby wow karol g」，dimedimebaby.com 也是 10-19 注册的。如果当天就能把原始词换成需求词「dime dime baby」再查域名，当天就能确认，比实际推送（10-21）早 2 天。
- 拿原始词拼域名（babywowkarolg.com、plantillaviraldamehombro.com）永远查不到东西。现在 CT 那一行查不到站，这也是原因之一（见第 5 条）。

### 拆词方法（参考哥飞群里的分享）

把长词按层拆开，标出每层是什么，再找真正被搜的核心。例：`bungie destiny 2 unvaulting update` 是公司 + 游戏 + 事件，核心是 `unvaulting update`；`deepinfer deepseek` 的核心是 `deepinfer`。

套到梗词上的分层：

| 层 | 例子 | 处理 |
|---|---|---|
| 平台/功能词 | trend、tiktok、capcut、plantilla、template、filter、tutorial、viral、original、dance、edit、ai | 去掉 |
| 人物/艺人/球员 | karol g、enzo fernandez、jason derulo | 背景，一般不是需求词 |
| 歌词片段/动作描述 | baby wow、dame hombro、dancing and eating | 线索，要追到它属于哪个梗 |
| 梗本身的名字（歌名、片段名、动作名） | dime dime baby、bulin 47、ozil goal | 需求词 |

三个例子：`baby wow karol g` → 歌词 + 艺人 → dime dime baby；`plantilla viral dame hombro` → 模板 + 修饰 + 歌词 → bulin 47；`enzo fernandez celebration` → 球员 + 动作 → ozil goal。

只去掉修饰词还不够：从「baby wow」到「dime dime baby」，得知道这首歌叫什么。两种办法配合：

1. 统计 AI 版视频字幕和标签里出现最多的名字（做 AI 版的人会写 `#dimedimebaby`、`dime dime baby ai`）。watch.py 的 `_AI_NAME` 已经在抽名字，但还没有统计出现次数。
2. 让模型按上表拆词，标出每层并给出核心词，再用 Google 补全「核心词 ai」确认有人在搜。

拆出需求词后，按上面的规则查 9 种写法；近几天有几种写法集中注册，就说明需求成立。

待讨论：两种办法的结果不一致时以哪个为准；模板号标签（`#bailedimedime`）和多个变体的公共部分怎么用。

## 7. 推送卡片上的「评分」不是热度，也不是可信度

来源是 radar/judge.py：DeepSeek（config `judge.model` = deepseek-chat，`focus` = trends）读「词 + 最多 3 条出处（每条截 160 字）」，回答「这个词有多像一个被人翻拍成 AI 视频的梗」，给 0～1 分，每 25 个词调一次。用到的门槛：

- ≥ 0.4 才推送（`judge.min_score`）
- ≥ 0.6 进观察列表（`watch.min_score`）
- ≥ 0.7 去 TikTok 搜 AI 版（`watch.tiktok_min`）
- 观察列表里的词转成 demand 推送时，取「当前分」和「进观察列表时的分」中较大的那个（`floor`），所以分数只升不降

问题：

- 7a. 分数完全是模型凭感觉给的，没用任何数据：AI 版账号数、播放量、域名注册、Google 补全都不参与打分。0.9 不代表比 0.7 火，也不代表更可信。
- 7b. 只问了「像不像一个梗的名字」，没问「是不是需求词」（第 6 条）、「新不新」（第 2b 条）、「是不是泛词」（第 2a 条）。所以 gangnam style 0.9、genderswap 0.85、halloween 0.7、edit tutorial 0.7、mr bean 0.7 都能推出去。
- 7c. 0.4 的门槛太低，提示词里说「不确定就给 0.3～0.5」，等于不确定的也推了：waves、machine heart、hambo、troquevande、brumzelquix、vikas edit 都是 0.4。
- 7d. 出处只给 3 条、每条 160 字，模型能看到的信息很少；分数只有 0.4/0.6/0.7/0.8/0.85/0.9 几档，没有校准过，每次运行重新打分，结果也不稳定。
- 7e. 卡片上直接写「评分 0.85」，看起来像优先级，其实不是，会误导判断。

用户决定（10-24）：不再打分。卡片上不显示分数；推不推由数据规则决定（AI 版账号数和播放量、需求词域名注册、Google 补全、是否过气），具体规则待定。去掉 judge 后，泛词和非梗词怎么过滤也待定。

## 8. 推送卡片太乱，废话多

现在每个词 4 行：「**1. 词** 🎬 评分 0.85」、「为什么：」接一长串信号原文（「TikTok 模板号:2 个账号在用 #xxx」「弱需求:Google 补全只有…需人工判断 · 10-06 起涨,已回落」）、「现在：」CT/Dreamina、「去看：」三个链接。信息堆在一起，读一条要花很久。

用户给的参考格式（截图）：

```
kimi k 3.1 pro  [AI] [新词] [上升中]
10/23 出现（1 天）· 10/23 爆发 · 自身近 7 天 从 0 起量
```

- 第一行：词 + 几个标签（类型、首推/升温、上升中/已回落）
- 第二行：日期和一句话的量变，不写解释性文字
- 不显示评分（第 7 条）

套到梗词上可能的写法（待定）：

```
dime dime baby  [视频] [🆕首推] [上升中]
AI 版 10/14 出现（7 天）· 域名 10/19 起注册 6/9 · AI 版 18 个账号 66 万播放
```

用户意见（10-24）：截图只是参考，格式由我来设计；首推、升温直接用标签表示，不用分段。

待定：第二行放哪几个数；链接（TikTok、Trends、已有的站）怎么放。

## 待讨论的修改方向（未定）

- 推送台账：每个梗一条记录（主名、别名、首推日期、首推时的账号数和播放量）；没推过的标 🆕 首推，推过且明显上涨的标 📈 升温（附首推日期和增幅），没变化的不推。升温阈值待定。
- 合并同梗：同一批 TikTok 视频或账号、同一个观察词、名字互相包含、拼写形式相同，都算一个梗。
- 过滤：「已回落」或两周前就起涨的不推；judge 加一问「具体的梗/模板，还是泛主题」。
- 域名：只推标题像某个梗的模板视频生成器的站。
- rising、pages 不再单独推送，只进日报。
- 推送形式：每小时零散推送改成每天 1～2 次汇总，分「今日新词」「升温中」两段，按 AI 版账号数 × 播放量排序。
- 需要用户标出这几天「推得对」的词，作为规则回放的标准答案。
