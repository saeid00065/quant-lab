# ایده‌های معاملاتی از SSRN
بازیابی: 2026-10-30 UTC — منبع: Crossref (پیشوند DOI `10.2139`) + WebSearch برای نقد/replication — queryها: ۱۸ query پیش‌فرض (`--default --since 2010 --rows 40`، فایل `papers.json`) + ۶ query هدفمند (`--rows 25 --out research/ssrn/extra`): "gold intraday returns time of day"، "London fix foreign exchange month-end"، "currency intraday patterns trading hours"، "pre-FOMC announcement drift"، "bitcoin intraday seasonality"، "turn of the month effect" — مقاله‌های یافته/غربال‌شده: **827 یکتا / 801 کنار گذاشته، 26 کاندید** (جزئیات غربال پایین صفحه).

> **هشدار:** هیچ‌کدام از این‌ها edge نیست. هر عدد Sharpe/بازده در این فایل «ادعای مقاله» است، نه نتیجه Quant Lab. هیچ PDF یا متن کاملی خوانده نشد (ssrn.com درخواست خودکار را رد می‌کند)؛ همه موارد **فقط abstract** (از Crossref) به‌علاوه خلاصه‌های WebSearch از منابع ثانویه است. تا ایجنت `edge` آزمون‌های اجباری را اجرا نکند، هیچ ایده‌ای تأییدشده نیست.

## مقیاس امتیاز (هر معیار ۰ تا ۵، وزن برابر، کل از ۲۵)
- **ش = شواهد:** طول نمونه، چند بازار، خارج از نمونه، replication مستقل، نشریه داوری‌شده. (تعداد ارجاع Crossref برای مقاله‌های SSRN بسیار ناقص است و فقط به‌عنوان نشانه ضعیف استفاده شد.)
- **م = مکانیزم:** طرف مقابل مشخص و دلیل ساختاری/رفتاری پایدار.
- **ه = تحمل هزینه:** turnover کم یا ادعای سود پس از هزینه واقعی.
- **آ = قابلیت آزمون در Quant Lab:** داده واقعاً موجود (پایین) و پشتیبانی موتور.
- **پ = پوسیدگی (معکوس):** ۵ = نشانه‌ای از ضعیف‌شدن نیست؛ ۱ = شواهد صریح ناپدیدشدن.
- تساوی امتیاز: اول «شواهد»، بعد «قابلیت آزمون».

## وضعیت داده و موتور (بررسی‌شده 2026-10-30)
- `data/processed/histdata/XAUUSD_1m.parquet`: 6,167,812 کندل 1 دقیقه، 2009-03-15 تا 2026-10-23 UTC، **یک جریان قیمت (bid)، حجم همیشه 0** → اسپرد باید مفروض و صریح باشد.
- `scripts/get_histdata.py`: همین قالب برای EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD (هنوز دانلود نشده‌اند).
- `data/raw/dukascopy/XAUUSD/{BID,ASK}`: فقط پوشه‌های 2019، 2025، 2026 (حدود 0.8 MB) — برای کالیبره‌کردن اسپرد مفید است، نه برای بک‌تست کامل.
- `data/raw/yahoo/GLD_1d_…csv` (2005–2026). از طریق `src/data_loader.fetch_yfinance_ohlcv` هر ETF روزانه (SPY، TLT، IEF، XL*) قابل دریافت است؛ **داده درون‌روزی SPY/فیوچرز/VIX/کریپتو وجود ندارد** و دانلودری برای آن نیست.
- موتور `src/backtest.py`: **تک‌دارایی، فقط long/flat (شورت ندارد)**، اجرای `close` یا `open_next`، هزینه به‌صورت bps در هر fill؛ stop/limit درون‌کندلی، چنددارایی و long-short ندارد. ایده‌های درون‌روزی یا شورت نیاز به اسکریپت تحقیقاتی جدا (مثل `research/gld_overnight/analyze.py`) یا توسعه موتور دارند.
- **هشدار نشت پژوهشی:** آزمون GLD شب/روز (`research/gld_overnight`) کل دوره 2005–2026 طلا، شامل بخش آزمون نهایی 2022–2026، را دیده است. هر ایده‌ای روی طلا در همین بازه داده **مستقل** محسوب نمی‌شود؛ باید صریح ثبت شود.

| رتبه | ایده | دارایی/تایم‌فریم | امتیاز (ش/م/ه/آ/پ = کل) | ادعای مقاله | وضعیت replication | مقاله |
|---|---|---|---|---|---|---|
| 1 | اثر آغاز ماه (Turn-of-the-Month) | SPY روزانه | 4/3/4/5/3 = **19** | بازده شاخص در روزهای آخر/اول ماه متمرکز است؛ در 36 از 55 شاخص (Giovanis) | McConnell–Xu: پایدار 1987–2005؛ Atlanta Fed: در فیوچرز S&P پس از 1990 ناپدید؛ مطالعه SPY 2001–2011: هنوز هست ولی زودتر | [2457394](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2457394) |
| 2 | ارز در ساعات کاری کشور خودش ضعیف می‌شود | EURUSD و ماژورها، 1m→جلسه | 3/4/3/5/3 = **18** | EUR/USD: «استراتژی ساده سودآور» (Breedon–Ranaldo، JMCB 2013) | Zhang 2018 روی 16 ارز (2010–2015) الگوی مشابه یافت؛ پس از 2015 نامعلوم | [2099321](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2099321) |
| 3 | بازده اوراق خزانه در روزهای پایانی ماه | TLT/IEF روزانه | 3/4/4/4/3 = **18** | لانگ فقط چند روز آخر ماه، Sharpe سالانه حدود 1 (اوراق نقدی) | replication مستقل یافت نشد | [3440417](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3440417) |
| 4 | مومنتوم سری زمانی / روند تک‌دارایی | XAUUSD، ماژورهای FX، GLD روزانه | 4/3/4/4/2 = **17** | مثبت در 1960–2015 و «crisis alpha» (Hamill و همکاران) | Huang و همکاران (JFE 2020): شواهد دارایی‌به‌دارایی ضعیف؛ Lim 2026: روی 7 ماژور FX پس از 2015 منفی | [2831926](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2831926) |
| 5 | مومنتوم درون‌روزی بازار (بقیه روز → 30 دقیقه آخر) | XAUUSD/FX 1m | 4/3/2/4/3 = **16** | SPY 1993–2013 (Gao و همکاران، JFE 2018)؛ بیش از 60 فیوچرز 1974–2020 (Baltussen و همکاران، JFE 2021) | در آمریکا replicate شد؛ در آسیا-اقیانوسیه ضعیف‌تر؛ در RUB/USD هم دیده شد | [2440866](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866)، [3760365](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3760365) |
| 6 | جریان پوشش ریسک سهام در fix ساعت 4 لندن، پایان ماه | ماژورهای FX 1m + بازده ماهانه شاخص سهام | 3/4/3/4/2 = **16** | بازده سهام در ماه، جهت موقت ارز را در fix پایان ماه پیش‌بینی می‌کند (Melvin–Prins، JFM 2015) | Colla و همکاران 2024: front-running پیش از fix؛ تفسیرهای بازار می‌گویند سیگنال اغلب کار نمی‌کند | [2019274](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2019274) |
| 7 | بازده شبانه در برابر روزانه سهام | SPY روزانه (open/close) | 4/3/1/5/3 = **16** | بیشتر بازده سهام در شب به دست می‌آید؛ مکانیزم خرده‌فروشی (Ahn و همکاران 2024، کره) | در بسیاری بازارها گزارش شده؛ آزمون عملی NIFTY (Kamath 2026) بر سر اصطکاک | [4752520](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4752520) |
| 8 | رانش پیش از FOMC | SPY روزانه | 4/3/4/3/1 = **15** | بیش از 80% صرف ریسک سهام 1994–2011 در 24 ساعت پیش از FOMC (Lucca–Moench) | Kurov و همکاران 2021: پس از 2015 عملاً ناپدید | [2024459](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2024459) |
| 9 | واکنش بیش از حد در FX و الگوی روز بعد | EURUSD, USDJPY, … روزانه + 1h | 2/2/2/5/3 = **14** | تفاوت معنادار رفتار ساعتی در روزهای واکنش بیش از حد و پس از آن، 2008–2018 | replication مستقل یافت نشد | [3362142](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142) |
| 10 | مومنتوم درون‌روزی «noise area» (Zarattini) | SPY 1m (اصلی)؛ تطبیق با XAUUSD | 4/3/2/2/2 = **13** | SPY 2007–2024: Sharpe 1.33 پس از هزینه | دو replication مستقل درون‌نمونه را بازتولید کردند؛ خارج از نمونه 2024–2026: Sharpe حدود 0.35–0.39؛ PBO حدود 40% | [4824172](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172) |
| 11 | بیس فیوچرز VIX (شورت در contango) | فیوچرز VIX + هج با ES | 3/4/3/1/2 = **13** | «بسیار سودآور و مقاوم به هزینه» 2006–2011 | Donninger 2014 الگو را تأیید کرد؛ رویداد 2018 (فروپاشی XIV) ریسک دم را نشان داد | [2094510](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2094510) |
| 12 | مومنتوم 30 دقیقه باز شدن لندن در FX | 5 جفت FX، M5 | 2/2/1/5/3 = **13** | سیگنال در 5 از 6 ابزار معنادار، ولی پس از هزینه فقط USDJPY مثبت (OOS 2019–2024) | این خودش آزمون مستقل اثر Gao/Baltussen است؛ داوری نشده | [7008318](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7008318) |
| 13 | چرخه مومنتوم درون‌ماهی سکتورها | 9 ETF سکتوری + SPY روزانه | 2/3/2/3/3 = **13** | long-short: 5.99% سالانه، Sharpe 0.55 (1998–2026) | replication یافت نشد؛ نویسندگان از Quantpedia هستند | [7313598](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7313598) |
| 14 | pairs trading هم‌انباشتگی در FX | 7 جفت USD روزانه | 2/2/3/3/3 = **13** | Sharpe بالاتر از قانون ساده در همه آستانه‌ها با 2–5 bp هزینه (2007–2025)، ادعای نسبی | replication یافت نشد | [4771108](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4771108) |
| 15 | عدم تقارن درون‌روزی (open/high/low) → بازده روز بعد | SPY روزانه | 1/2/2/5/3 = **13** | رابطه معکوس با بازده درون‌روزی روز بعد، بیش از دو دهه (توصیفی) | replication یافت نشد؛ تک‌نویسنده، 2026 | [6074846](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6074846) |

---

## 1. اثر آغاز ماه (Turn-of-the-Month) روی SPY
- **مقاله:** Calendar Effects and Seasonality on Returns and Volatility، Eleftherios Giovanis، 2014 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2457394 ؛ مکمل: Vojtko & Dujava 2026 (سکتورها، [7313598](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7313598))؛ McConnell & Xu (CRSP 1987–2005، از طریق WebSearch، SSRN 917884)
- **مکانیزم:** جریان‌های نقدی منظم (حقوق، واریز صندوق بازنشستگی، ریبالانس پایان ماه، window dressing) در چند روز خرید متمرکز ایجاد می‌کنند. طرف مقابل: نقدینگی‌دهنده‌هایی که برای جذب این جریان قابل پیش‌بینی پاداش می‌گیرند.
- **قانون تقریبی:** لانگ SPY از close روز معاملاتی 1- (آخرین روز ماه) تا close روز +3 ماه بعد؛ بقیه زمان نقد. (ابهام‌ها برای دروازه ابهام: پنجره دقیق (-1..+3 یا -4..+3 که بعضی منابع می‌گویند «زودتر شده»)، اجرا در close با MOC یا open روز بعد، بازده نقد، هزینه هر fill، تقویم NYSE برای «روز معاملاتی».)
- **ادعا:** Giovanis: بیشتر اثرهای تقویمی در سطح جهانی رد می‌شوند، **به‌جز TOM** که در 36 از 55 شاخص وجود دارد (bootstrap؛ بدون هزینه). McConnell–Xu: پایدار در 1987–2005 و ناشی از small-cap یا پایان فصل نیست.
- **نقد و replication:** Atlanta Fed (Maberly & Waggoner 2000): در فیوچرز S&P 500 پس از 1990 ناپدید شد. یک مطالعه روی SPY (2001–2011): هنوز هست ولی زودتر رخ می‌دهد. آزمون SPY برای 2012–2026 پیدا نشد. ← خطر انتخاب پنجره پس از دیدن داده بالاست.
- **داده لازم و وضعیت در Quant Lab:** SPY روزانه از yfinance (همان مسیر GLD). موتور: long/flat با اجرای `close` یا `open_next` کافی است. حدود 12 معامله رفت‌وبرگشت در سال → از 1993 حدود 400 معامله.
- **قدم بعد:** ارسال به `edge` با پنجره **ازپیش‌ثبت‌شده** (-1..+3)، معیار پوچ = پنجره‌های تصادفی 5 روزه با همان تعداد روز حضور در بازار، هزینه 1/2/5 bp، تقسیم زمانی قفل‌شده. پیشنهاد: آزمون جانبی روی GLD/TLT فقط به‌عنوان آزمون اکتشافی (مقاله‌ای برایش نیست).
- **منبع خوانده‌شده:** abstract فقط (+ خلاصه WebSearch)

## 2. ضعف ارز در ساعات کاری کشور خودش (time-of-day در FX)
- **مقاله:** Intraday Patterns in FX Returns and Order Flow، Francis Breedon & Angelo Ranaldo، 2012 (JMCB 2013) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2099321 (Crossref abstract ندارد؛ abstract از SNB working paper 2011-04 از طریق WebSearch). مکمل: Hao Zhang 2018، [3138756](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3138756)
- **مکانیزم:** فعالان هر منطقه در ساعات کاری خودشان خریدار خالص ارز خارجی هستند (واردات، سرمایه‌گذاری خارجی، هج) → ارز محلی در ساعات اروپا ضعیف و در ساعات آمریکا (پس از بسته‌شدن لندن) قوی‌تر. طرف مقابل: market makerهایی که موجودی را شبانه نگه می‌دارند. Zhang همین الگو را در 16 ارز، حتی کشورهای دارای کنترل سرمایه، دیده است.
- **قانون تقریبی:** EURUSD: شورت EUR (= فروش EURUSD) در ساعات اروپا و لانگ EUR در ساعات بعدازظهر آمریکا؛ یا نسخه long-only با جفت معکوس. (ابهام‌ها: مرز دقیق جلسه‌ها در UTC با تغییر DST، یک یا دو معامله در روز، اسپرد bid/ask در مرز جلسه‌ها (HistData فقط bid دارد)، نیاز موتور به شورت یا تعریف «لانگ USD».)
- **ادعا:** «در EUR/USD یک استراتژی ساده سودآور» (داده یک market maker؛ بازه و هزینه در abstract مشخص نیست). Zhang: 2010–2015، توصیفی، بدون هزینه.
- **نقد و replication:** Zhang 2018 تأیید جزئی است، از داده دیگر. نقدی پیدا نشد، و آزمون پس از 2015 هم پیدا نشد.
- **داده لازم و وضعیت در Quant Lab:** `get_histdata.py --symbols EURUSD GBPUSD USDJPY …` (1m، از حدود 2000/2009). برای اسپرد، Dukascopy bid/ask جفت‌ها لازم است (فعلاً فقط XAUUSD جزئی). موتور شورت ندارد → اسکریپت تحقیقاتی جدا مثل `gld_overnight/analyze.py`.
- **قدم بعد:** ارسال به `edge`. ابتدا آمار توصیفی بازده جلسه‌ها (بدون معامله) روی بخش «تحقیق»، سپس قانون ثابت. **ریسک:** حرکت هر جلسه چند bp است و اسپرد EURUSD حدود 0.5–1 bp در هر fill است؛ فشار هزینه تعیین‌کننده است.
- **منبع خوانده‌شده:** abstract فقط

## 3. بازده اوراق خزانه در روزهای پایانی ماه
- **مقاله:** Predictable End-of-Month Treasury Returns، Jonathan Hartley & Krista Schwarz، 2019 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3440417
- **مکانیزم:** ریبالانس شاخص اوراق در پایان ماه (افزایش duration شاخص) و خرید بیمه‌گرهای عمر → تقاضای موقت و قابل پیش‌بینی. طرف مقابل: صندوق‌های شاخصی که باید در تاریخ مشخص بخرند. این مکانیزم ساختاری و قابل راستی‌آزمایی است.
- **قانون تقریبی:** لانگ اوراق بلندمدت (TLT یا IEF) در «چند روز آخر» ماه، بقیه زمان نقد. (ابهام‌ها: تعداد دقیق روزها (abstract فقط «چند روز آخر» می‌گوید)، ETF به‌جای اوراق نقدی (اثر ممکن است در قیمت ETF متفاوت باشد)، بازده نقد/repo، اجرای close.)
- **ادعا:** Sharpe سالانه حدود 1 برای لانگ چند روز آخر هر ماه؛ بازده در بقیه ماه تفاوت معناداری با صفر ندارد (اوراق نقدی خزانه؛ بازه و هزینه در abstract ذکر نشده).
- **نقد و replication:** replication مستقل یا رد پیدا نشد (فقط یک جست‌وجو انجام شد). شناخته‌شده بودن پدیده در بین معامله‌گران اوراق محتمل است.
- **داده لازم و وضعیت در Quant Lab:** TLT/IEF روزانه از yfinance (از 2002). موتور long/flat کافی است. **محدودیت:** TLT یک کوپن ماهانه دارد (تاریخ ex-dividend نزدیک آغاز ماه)؛ داده خام بدون تعدیل باعث سوگیری می‌شود و نیاز به total return دارد.
- **قدم بعد:** ارسال به `edge` با پنجره ازپیش‌ثبت‌شده (مثلاً 3 روز آخر)، معیار پوچ = پنجره‌های تصادفی هم‌طول، و حل‌کردن مسئله تعدیل سود ETF پیش از هر چیز.
- **منبع خوانده‌شده:** abstract فقط

## 4. مومنتوم سری زمانی / پیروی از روند روی تک‌دارایی
- **مقاله:** Trend Following: Equity and Bond Crisis Alpha، Hamill, Rattray & van Hemert، 2016 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2831926 ؛ همچنین Baltas & Kosowski 2011 ([1968996](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1968996))، Marshall و همکاران 2013 درباره TSMOM در برابر MA ([2225551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2225551))
- **مکانیزم:** کم‌واکنشی و سپس بیش‌واکنشی، و هج‌کننده‌هایی که جهت روند را تقویت می‌کنند؛ پرداخت شبیه straddle بلند (چولگی مثبت).
- **قانون تقریبی:** لانگ اگر بازده 12 ماهه (یا قیمت بالای MA بلند) مثبت است، در غیر این صورت نقد (موتور فعلی شورت ندارد)؛ ریبالانس ماهانه؛ اندازه‌گذاری با هدف نوسان اختیاری. (ابهام‌ها: lookback، ریبالانس، هدف نوسان، نسخه long/flat در برابر long/short، دارایی‌ها.)
- **ادعا:** مثبت و پایدار پیش و پس از 1985 در اوراق، کالا، ارز و سهام (1960–2015)، قوی در بدترین دوره‌های سهام و اوراق؛ هزینه در abstract مشخص نیست.
- **نقد و replication:** Huang, Li, Wang & Zhou (JFE 2020): در رگرسیون دارایی‌به‌دارایی شواهد کمی هست و قانون «میانگین تاریخی» تقریباً همان نتیجه را می‌دهد. Hutchinson و همکاران 2022: قواعد تکنیکال FX از Sharpe 0.66 درون‌نمونه به 0.06 خارج از نمونه رسیدند. Lim 2026 ([6871118](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6871118)): TSMOM روی 7 ماژور FX در 2005–2026 پس از هزینه معنادار نیست و پس از 2015 منفی است. Zoicas-Ienciu 2017: سود روند ناپایدار است و به دوره ارزیابی حساس است.
- **داده لازم و وضعیت در Quant Lab:** GLD روزانه (موجود)، XAUUSD 1m→روزانه (موجود)، ماژورهای FX (قابل دانلود). سبد 55 فیوچرز مقاله در دسترس نیست. **توان آماری تک‌دارایی پایین است**: یک دارایی با lookback 12 ماهه، تعداد تصمیم مستقل کمی دارد.
- **قدم بعد:** فقط اگر کاربر تنوع چنددارایی (طلا + 7 ارز) را بپذیرد ارسال شود. ابهام long/flat در برابر long/short باید پیش از آزمون حل شود. داده طلا قبلاً در مطالعه GLD دیده شده است.
- **منبع خوانده‌شده:** abstract فقط

## 5. مومنتوم درون‌روزی بازار (بقیه روز ← 30 دقیقه آخر)
- **مقاله:** Market Intraday Momentum، Gao, Han, Li & Zhou، 2014 (JFE 2018) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866 ؛ Hedging Demand and Market Intraday Momentum، Baltussen, Da, Lammers & Martens، 2021 (JFE) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3760365 ؛ نمونه FX: Elaut و همکاران 2015 ([2694985](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2694985))
- **مکانیزم:** هج گامای منفی (market makerهای آپشن و ETFهای اهرمی) در جهت حرکت روز معامله می‌کند. توضیح دیگر: معامله‌گران دیرمطلع و ریبالانس نامنظم. در RUB/USD با ریسک‌گریزی نقدینگی‌دهنده‌ها نسبت به نگهداری شبانه سازگار بود.
- **قانون تقریبی:** اگر بازده از close دیروز تا 30 دقیقه پیش از close امروز مثبت است، لانگ در 30 دقیقه آخر، و بسته‌شدن در close. (ابهام‌ها: «close» برای طلای اسپات 24 ساعته چیست؟ (close فیوچرز COMEX در 13:30 ET، شروع وقفه 17:00 ET، یا fix لندن)؛ شورت؛ آستانه؛ اسپرد در 30 دقیقه آخر.)
- **ادعا:** Gao: SPY 1993–2013، R² خارج از نمونه حدود 1.2%، «اقتصادی معنادار». Baltussen: «قوی همه‌جا» در بیش از 60 فیوچرز سهام، اوراق، کالا و ارز، 1974–2020، با بازگشت در روزهای بعد.
- **نقد و replication:** Limkriangkrai و همکاران 2023: در آمریکا replicate شد، در 5 بازار آسیا-اقیانوسیه کمتر فراگیر است و در دوره COVID ضعیف‌تر بود. یک آزمون QuantConnect بازده کمتری گزارش کرد (غیررسمی). Seeck 2026 (ردیف 12) در FX خرده‌فروشی، پس از هزینه فقط USDJPY را مثبت یافت. replication پس از 2020 (دوره 0DTE) پیدا نشد.
- **داده لازم و وضعیت در Quant Lab:** XAUUSD 1m موجود؛ ماژورهای FX قابل دانلود. یک معامله کوتاه در روز → فشار هزینه زیاد. نیاز به اسکریپت درون‌روزی دارد (موتور bar-level فقط اجرای close/open_next دارد).
- **قدم بعد:** ارسال به `edge` **پس از** تعیین «close» طلا با کاربر (ترجیحاً close فیوچرز COMEX، نزدیک‌ترین به مقاله Baltussen). هشدار هم‌پوشانی داده با مطالعه GLD.
- **منبع خوانده‌شده:** abstract فقط

## 6. جریان هج سهام در fix ساعت 4 لندن، پایان ماه
- **مقاله:** Exchange Rates, Equity Hedging, and the London 4pm Fix، Michael Melvin & John Prins، 2012 (JFM 2015) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2019274 ؛ مرتبط: Colla, Distaso & Vitale 2024 ([4819478](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4819478))
- **مکانیزم:** مدیران سبد سهام خارجی ریسک ارزی را به‌صورت passive در fix پایان ماه هج می‌کنند. اگر سهام خارجی در ماه بالا رفته باشد، باید ارز خارجی بیشتری بفروشند → فشار موقت و قابل پیش‌بینی. طرف مقابل: هج‌کننده‌های اجباری و غیرحساس به قیمت.
- **قانون تقریبی:** در آخرین روز معاملاتی ماه، اگر بازده ماهانه سهام اروپا/جهان نسبت به آمریکا مثبت است، فروش EUR (یا خرید USD) پیش از پنجره fix (مثلاً 15:00 → 16:00 لندن) و بستن پس از fix. (ابهام‌ها: کدام شاخص سهام، آستانه، پنجره ورود/خروج، تغییر پنجره fix از 1 دقیقه به 5 دقیقه در 2015، ساعت fix به UTC با DST.)
- **ادعا:** هج‌کردن «اثر قوی ولی موقت» بر نرخ ارز در fix پایان ماه دارد؛ اندازه سود و هزینه در abstract نیست.
- **نقد و replication:** Colla و همکاران: front-running توسط دلال‌ها پیش از fix (EBS، EURUSD) → بخشی از اثر احتمالاً زودتر قیمت‌گذاری می‌شود. منابع بازار (FXStreet، The Full FX) می‌گویند سیگنال «اغلب کار نمی‌کند». شناخته‌شده و شلوغ است.
- **داده لازم و وضعیت در Quant Lab:** FX 1m (قابل دانلود) + بازده ماهانه شاخص سهام (yfinance، مثلاً SPY و VGK/EZU). حدود 12 رویداد در سال → از 2009 حدود 200 رویداد؛ **توان آماری کم**.
- **قدم بعد:** ارسال به `edge` به‌عنوان آزمون رویدادی با معیار پوچ = همان پنجره در روزهای غیرپایان ماه. انتظار کم.
- **منبع خوانده‌شده:** abstract فقط

## 7. بازده شبانه در برابر روزانه سهام (SPY)
- **مقاله:** Retail Ebb and Flow and the Overnight–Intraday Return Gap، Ahn, Fan, Noh & Park، 2024 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4752520 ؛ مرتبط: Bogousslavsky 2016 ([2869624](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2869624))، Kamath 2026 درباره NIFTY ([7010198](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7010198))
- **مکانیزم:** خرده‌فروشان در open خریدار خالص و در close فروشنده خالص‌اند (ابزار علّی: قیمت اسمی سهم)؛ آربیتراژگرها به دلیل مارجین شبانه و هزینه قرض پوزیشن را پیش از close می‌بندند.
- **قانون تقریبی:** دقیقاً همان قانون پیش‌ثبت‌شده GLD: خرید در close و فروش در open روز بعد، روی SPY. (ابهام‌ها: MOC/MOO و اسپرد واقعی SPY، سود نقدی SPY (برخلاف GLD سود می‌دهد → باید تعدیل شود)، بازه.)
- **ادعا:** در بیشتر بازارهای سهام، میانگین بازده شبانه «به‌طور قابل‌توجه» از روزانه بیشتر است (کره، داده سطح سرمایه‌گذار).
- **نقد و replication:** پدیده در ادبیات بسیار تکرار شده؛ پرسش اصلی **اصطکاک** است (Kamath روی NIFTY). در مطالعه GLD خودمان، شب درون‌نمونه بدون هزینه بالاتر بود ولی با 1 bp هزینه رد شد (کتاب: `research/gld_overnight`).
- **داده لازم و وضعیت در Quant Lab:** SPY روزانه از yfinance؛ اسکریپت `research/gld_overnight/analyze.py` تقریباً بدون تغییر قابل استفاده است. داده **مستقل** از طلا است.
- **قدم بعد:** ارسال به `edge` با SPEC جدید پیش‌ثبت‌شده (کپی ساختار GLD، تقسیم زمانی جدید). انتظار: احتمالاً مانند GLD در هزینه شکست می‌خورد (ه = 1).
- **منبع خوانده‌شده:** abstract فقط

## 8. رانش پیش از FOMC
- **مقاله:** The Pre-FOMC Announcement Drift، David Lucca & Emanuel Moench، 2012 (JF 2015) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2024459 ؛ نقد: Kurov, Wolfe & Gilbert، The Disappearing Pre-FOMC Announcement Drift (FRL 2021) — [3134546](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3134546)
- **مکانیزم:** نامشخص؛ نویسندگان می‌گویند هیچ توضیحی از نظر کمی کافی نیست. بعداً به کاهش عدم قطعیت نسبت داده شد.
- **قانون تقریبی:** لانگ شاخص سهام از 14:00 ET روز قبل تا 14:00 ET روز اعلام FOMC؛ با داده روزانه: close روز قبل → close روز اعلام. (ابهام‌ها: تقویم FOMC (باید از Fed گرفته شود)، جلسات اضطراری، تقریب روزانه.)
- **ادعا:** 1994–2011: بیش از 80% صرف ریسک سهام آمریکا در 24 ساعت پیش از FOMC. در سایر کلاس‌های دارایی دیده نشد.
- **نقد و replication:** Kurov و همکاران: **پس از 2015 عملاً ناپدید شد**. Ben Dor & Rosa: در 2011–2017 drift دیده نشد.
- **داده لازم و وضعیت در Quant Lab:** SPY روزانه (yfinance) + تقویم FOMC (موجود نیست، دستی). 8 رویداد در سال.
- **قدم بعد:** اولویت پایین. فقط به‌عنوان آزمون «آیا بازگشته است؟» روی 2016 به بعد، و فقط اگر کاربر بخواهد.
- **منبع خوانده‌شده:** abstract فقط

## 9. واکنش بیش از حد در FX و الگوی درون‌روزی پس از آن
- **مقاله:** Price Overreactions in the Forex and Trading Strategies، Guglielmo Maria Caporale & Alex Plastun، 2019 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3362142
- **مکانیزم:** بیش‌واکنشی رفتاری و فشار نقدینگی موقت در روزهای حرکت غیرعادی.
- **قانون تقریبی:** روز «overreaction» = بازده روزانه بیش از میانگین + k×انحراف معیار در پنجره پویا. معامله در جهت/خلاف حرکت در ساعات بعدی یا روز بعد، طبق الگوی یافته‌شده. (ابهام‌ها: k، طول پنجره، جهت، ساعت ورود و خروج — abstract جزئیات ندارد و مقاله چند فرضیه را آزمون کرده است → **خطر data snooping**.)
- **ادعا:** تفاوت آماری معنادار بین دینامیک ساعتی روزهای overreaction و روزهای عادی، و الگوهای قابل تشخیص در روز بعد. EURUSD, USDJPY, USDCAD, AUDUSD, EURJPY، 2008–2018؛ هزینه در abstract نیست.
- **نقد و replication:** پیدا نشد. همین نویسندگان مقاله‌های مشابه زیادی روی بازارهای دیگر دارند (ریسک چندآزمونی).
- **داده لازم و وضعیت در Quant Lab:** FX 1m→1h/روزانه با `get_histdata.py`. پس از 2018 داده خارج از نمونه واقعی موجود است.
- **قدم بعد:** ارسال به `edge` فقط با یک قانون ثابت و داده **2019 تا 2026 به‌عنوان آزمون خارج از نمونه مقاله**.
- **منبع خوانده‌شده:** abstract فقط

## 10. مومنتوم درون‌روزی «noise area» (Zarattini, Aziz & Barbon)
- **مقاله:** Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)، Zarattini, Aziz & Barbon، 2024 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 ؛ replicationها: Delgado 2026 ([7323419](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7323419))، Paz 2026 ([7290621](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7290621))؛ تطبیق با NQ: Chuk 2026 ([7609644](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7609644))
- **مکانیزم:** همان مکانیزم ردیف 5 (عدم تعادل عرضه/تقاضا و هج گاما). ورود هنگام خروج قیمت از «noise area» حول open (بر اساس میانگین حرکت درون‌روزی 14 روز گذشته)، با trailing stop پویا (VWAP).
- **قانون تقریبی:** در بازه‌های 30 دقیقه‌ای، اگر قیمت بالای مرز بالایی noise area بود، لانگ؛ اگر زیر مرز پایینی، شورت؛ stop = max(مرز، VWAP)؛ بستن در close. (ابهام‌ها: برای طلا/FX «open» جلسه کدام است؟ VWAP بدون حجم (HistData حجم ندارد) ممکن نیست؛ تطبیق با طلا **فرضیه دیگری** است، نه replication.)
- **ادعا:** SPY 2007–2024: بازده کل 1,985%، سالانه 19.6%، Sharpe 1.33 **پس از هزینه** (ادعای مقاله).
- **نقد و replication:** Delgado و Paz هر دو درون‌نمونه را تقریباً دقیق بازتولید کردند. Paz: خارج از نمونه 2024-05 تا 2026-03 بازده 9.4% در برابر 29.5% buy-and-hold، Sharpe 0.39. Delgado: سپتامبر 2025 تا اوت 2026 بازده -8.1%؛ PBO حدود 38–41%. Chuk: روی NQ، یک واحد لغزش در stop، 22% edge را حذف می‌کند.
- **داده لازم و وضعیت در Quant Lab:** **داده 1m SPY/NQ موجود نیست** (yfinance فقط حدود 30 روز). XAUUSD 1m هست ولی حجم ندارد (VWAP ممکن نیست). موتور stop درون‌کندلی ندارد.
- **قدم بعد:** نیاز به داده SPY یا ES 1m (منبع پولی). بدون آن ارسال نشود. replicationهای موجود تصویر تحقیقاتی خوبی داده‌اند، و پوسیدگی پس از انتشار نشانه هشدار است.
- **منبع خوانده‌شده:** abstract فقط (هر چهار مقاله)

---

## کاندیدهای دیگر (خارج از ۱۵ برتر، امتیاز ≤ 13)
| ایده | امتیاز | یادداشت | مقاله |
|---|---|---|---|
| بازگشت گپ FX خلاف روند | 1/2/2/5/3 = 13 | ادعای PF 1.59 و «هیچ سال زیان‌ده» در 26 سال؛ نویسنده ناشناس، داوری‌نشده؛ ادعا بیش از حد تمیز است | [6616479](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6616479) |
| فصلی‌بودن ساعتی طلا / لانگ بین fixهای لندن | 1/2/2/5/2 = 12 | Bell 2026: «سود قابل اتکا» در 2000–2010؛ پایان‌نامه CBS: طلا در ساعات آسیا بالا و بقیه روز پایین می‌رود، پس از هزینه ضعیف. fix در 2015 به LBMA Gold Price تغییر کرد. **با داده GLD دیده‌شده هم‌پوشانی دارد** | [6077836](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6077836) |
| BTC فقط 2 ساعت در روز (22:00–00:00 UTC) | 2/2/2/3/2 = 11 | Quantpedia: افت در 2022–2023؛ Schmidt & Kraft 2026: ساعت روز، حجم/نوسان را پیش‌بینی می‌کند ولی جهت را نه. داده کریپتو در لب نیست | [4081000](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4081000) |
| بازگشت 8–10 هفته‌ای کریپتو (cross-section) | 2/2/3/1/3 = 11 | 70 توکن Binance 2021–2026؛ نیاز به پنل و long-short | [6703978](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6703978) |
| مومنتوم cross-sectional کریپتو | 3/2/1/1/2 = 9 | replication پیش‌ثبت‌شده Arefev 2026: پس از هزینه از صفر قابل تمایز نیست | [7404139](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7404139) |
| Turn-of-the-candle در BTC | 2/1/0/2/2 = 7 | 0.58 bp در دقیقه؛ هزینه آن را می‌بلعد | [4090044](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4090044) |
| فصلی‌بودن تقویمی FX / ORB / breakout | — | خود نویسنده (Mahadzva 2026) نتیجه منفی یا ناقطعی گزارش داده؛ به‌عنوان هشدار روش‌شناسی مفید است | [7435081](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7435081)، [7434881](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7434881) |

## جزئیات غربال
- 700 مقاله (query پیش‌فرض) + 127 مقاله جدید از 146 نتیجه query هدفمند = **827 یکتا**؛ 266 مورد abstract در Crossref ندارند.
- غربال کلیدواژه‌ای (اسکریپت موقت در scratchpad، قابل تکرار): 52 مورد خارج از موضوع (انرژی، زیست‌شناسی، سیاست ارزی و …)، 129 مورد بدون قانون معاملاتی (نظری، روش‌شناسی، مدل‌سازی نوسان). 646 مورد باقی ماند.
- بازبینی دستی عنوان همه 646 مورد و abstract حدود 115 مورد: بیشتر به این دلایل کنار رفتند: نیاز به پنل سهام تکی/داده بنیادی (PEAD، factor timing، anomalyهای cross-sectional)، بازارهای غیرقابل دسترس (چین، هند، برزیل، آپشن، VIX)، مقاله‌های توصیفی بدون قانون، ML بدون قانون مشخص، و تکراری‌ها. **26 کاندید** باقی ماند (15 در جدول + 7 ردیف در «کاندیدهای دیگر»، که بعضی ردیف‌ها چند مقاله را پوشش می‌دهند).
- شمارش‌های غربال کلیدواژه‌ای تقریبی است؛ مرحله دستی قضاوت است و فقط عنوان/abstract را دیده است.

## منابع WebSearch (نقد/replication، منابع ثانویه)
- Gao و همکاران / APAC: https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf ، https://www.quantconnect.com/research/15348/intraday-etf-momentum/
- Kurov و همکاران (FOMC): https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf ، https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html
- Breedon–Ranaldo: https://www.snb.ch/en/publications/research/working-papers/2011/working_paper_2011_04 ، https://econpapers.repec.org/RePEc:wly:jmoncb:v:45:y:2013:i:5:p:953-965
- Melvin–Prins: https://ideas.repec.org/a/eee/finmar/v22y2015icp50-72.html ، https://thefullfx.com/what-happened-at-the-month-end-fix-12/
- طلا (ساعتی، fix): https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/ ، https://ideas.repec.org/a/wly/jfutmk/v34y2014i11p1003-1039.html
- Baltussen و همکاران: https://www3.nd.edu/~zda/intramom.pdf
- قواعد تکنیکال FX: https://hub.hku.hk/handle/10722/229640 ، https://repository.essex.ac.uk/18805/1/1-s2.0-S1057521916301958-main.pdf
- BTC فصلی: https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin
- TSMOM نقد: https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:3:p:774-794 ، https://alphaarchitect.com/an-empirical-challenge-for-trend-following/
- TOM: https://www.atlantafed.org/research/publications/wp/2000/11.aspx ، https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
