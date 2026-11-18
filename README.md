<div dir="rtl" align="right">

<h1>تستر سرورهای Cisco AnyConnect و دسترسی YouTube</h1>

<p>ابزاری خط فرمان به زبان Python برای اتصال ترتیبی به فهرستی از سرورهای Cisco AnyConnect با <code>openconnect</code> و بررسی وضعیت اتصال به YouTube از هر سرور. ابزار نتایج را در قالب JSON ذخیره می‌کند و سرورهای موفق را بر اساس زمان اجرا مرتب می‌کند. این پروژه همچنین امکان کشف زیردامنه‌ها و افزودن دستی سرورها را دارد.</p>

<p><strong>توجه:</strong> این ابزار خودش کلاینت گرافیکی یا سرویس VPN دائمی نیست. برای هر سرور یک اتصال موقت برقرار می‌کند، وضعیت شبکه را بررسی می‌کند و سپس اتصال را می‌بندد. اتصال‌ها به‌صورت ترتیبی اجرا می‌شوند، چون هر اتصال می‌تواند مسیرهای شبکهٔ سیستم را تغییر دهد.</p>

<h2>قابلیت‌ها</h2>
<ul>
  <li>تست DNS، اتصال VPN، و دسترسی DNS/TCP/HTTPS به YouTube.</li>
  <li>ثبت IP خروجی مشاهده‌شده و جزئیات هر تست.</li>
  <li>گزارش JSON کامل و فهرست سرورهای موفق مرتب‌شده بر اساس زمان.</li>
  <li>کشف زیردامنه‌ها با استفاده از crt.sh، الگوهای نام و واژه‌نامه، و بررسی زنده‌بودن با DNS/TCP.</li>
  <li>مدیریت فهرست سرورها در <code>domains.txt</code> یا از طریق آرگومان خط فرمان.</li>
  <li>تنظیم DNS و مسیر شبکهٔ رابط تونل در Windows (با دسترسی Administrator).</li>
</ul>

<h2>پیش‌نیازها</h2>
<ul>
  <li>Python نسخهٔ 3.10 یا جدیدتر.</li>
  <li><code>openconnect</code> نصب‌شده و در <code>PATH</code>.</li>
  <li>اعتبارنامهٔ معتبر VPN برای اجرای تست اتصال.</li>
  <li>دسترسی Administrator در Windows یا دسترسی root در Linux برای برقراری/تنظیم تونل.</li>
</ul>

<p>در Linux، <code>openconnect</code> را از مدیر بستهٔ توزیع خود نصب کنید. در Windows نیز نسخهٔ مناسب OpenConnect را نصب کنید و مطمئن شوید فرمان <code>openconnect</code> از PowerShell قابل اجراست. برای آزمودن نصب:</p>

</div>

```bash
openconnect --version
```

<div dir="rtl" align="right">

<h2>نصب و پیکربندی</h2>

<p>مخزن را دریافت کنید، وابستگی‌های Python را نصب کنید و فایل نمونهٔ متغیرهای محیطی را به <code>.env</code> کپی کنید:</p>

</div>

```bash
git clone https://github.com/avangardistic/ipbaz-ciscoAnyConnect-ping-tester.git
cd ipbaz-ciscoAnyConnect-ping-tester
python -m pip install -r requirements.txt
```

<div dir="rtl" align="right">
<p>در Windows (PowerShell):</p>
</div>

```powershell
Copy-Item .env.example .env
```

<div dir="rtl" align="right">
<p>در Linux یا macOS:</p>
</div>

```bash
cp .env.example .env
```

<div dir="rtl" align="right">
<p>فایل <code>.env</code> را با ویرایشگر متن باز کنید و اطلاعات VPN خود را وارد کنید:</p>
</div>

```dotenv
VPN_USERNAME=نام_کاربری
VPN_PASSWORD=گذرواژه

# اختیاری:
# VPN_CERT_HASH=pin-sha256:...
# VPN_SCRIPT=/path/to/vpnc-script
# VPN_DOMAINS=server1.example.com,server2.example.com
# CONNECT_TIMEOUT=35
# YOUTUBE_TIMEOUT=12
# VPN_RETRIES=0
```

<div dir="rtl" align="right">

<p><strong>امنیت:</strong> فایل <code>.env</code> شامل اطلاعات محرمانه است و در <code>.gitignore</code> قرار دارد؛ آن را منتشر یا commit نکنید. از رمز عبور نمونه در <code>.env.example</code> استفاده نکنید. در صورت نیاز به اعتبارسنجی گواهی، مقدار <code>VPN_CERT_HASH</code> را فقط از منبع قابل اعتماد دریافت کنید. اگر مقدار آن تنظیم نشود، کد فعلی OpenConnect را با گزینهٔ <code>--no-cert-check</code> اجرا می‌کند؛ بنابراین اعتبار گواهی سرور تأیید نمی‌شود.</p>

<h3>انتخاب دامنه‌ها</h3>
<p>فهرست <code>domains.txt</code> را ویرایش کنید؛ هر خط یک دامنه و خط‌هایی که با <code>#</code> شروع می‌شوند توضیح هستند. اولویت انتخاب دامنه‌ها به این ترتیب است:</p>
<ol>
  <li><code>VPN_DOMAINS</code> در محیط یا فایل <code>.env</code>؛ دامنه‌ها را با کاما جدا کنید.</li>
  <li>فایل <code>domains.txt</code>، اگر موجود و غیرخالی باشد.</li>
  <li>فهرست پیش‌فرض داخل برنامه.</li>
</ol>

<h2>اجرا</h2>
<p>در Windows، PowerShell را با گزینهٔ <strong>Run as Administrator</strong> باز کنید. در Linux با دسترسی root اجرا کنید؛ برای نمونه:</p>

</div>

```bash
sudo python run.py
```

<div dir="rtl" align="right">
<p>Windows (PowerShell مدیریتی):</p>
</div>

```powershell
python run.py
```

<div dir="rtl" align="right">
<p>برای دیدن گزینه‌های تست:</p>
</div>

```bash
python run.py --help
```

<div dir="rtl" align="right">

<h3>گزینه‌های پرکاربرد تست</h3>
<ul>
  <li><code>--domain example.com</code> — تست دامنهٔ مشخص؛ برای چند دامنه، گزینه را تکرار کنید.</li>
  <li><code>--retries 2</code> — تعداد تلاش‌های مجدد پس از تلاش اول.</li>
  <li><code>--output results.json</code> — مسیر فایل نتایج JSON.</li>
  <li><code>--best best_servers.txt</code> — مسیر فهرست سرورهای موفق.</li>
  <li><code>--skip-precheck</code> — رد کردن بررسی اولیهٔ نصب OpenConnect و دسترسی Administrator/root؛ این گزینه نیاز واقعی برنامه به OpenConnect و دسترسی مناسب را برطرف نمی‌کند.</li>
</ul>

</div>

```bash
python run.py --domain mcis1.apibaz.org --domain tci.apibaz.org --retries 1
python run.py --output output/results.json --best output/best.txt
```

<div dir="rtl" align="right">

<h2>کشف و مدیریت دامنه‌ها</h2>
<p>کشف دامنه به اعتبارنامهٔ VPN نیاز ندارد، اما برای پرس‌وجو از crt.sh و بررسی DNS/TCP به اینترنت دسترسی دارد. این عملیات فقط نام‌های دامنهٔ قابل‌دسترسی را می‌یابد؛ موفقیت در کشف، به معنی کارکرد VPN یا دسترسی YouTube نیست.</p>

</div>

```bash
# کشف پیش‌فرض برای apibaz.org؛ خروجی در discovered.json
python run.py discover

# ذخیرهٔ دامنه‌های زنده به domains.txt
python run.py discover --save

# تعیین دامنهٔ پایه، دامنه‌های کاندید بیشتر، و timeout هر بررسی
python run.py discover --base example.org --max-n 100 --timeout 5

# غیرفعال‌کردن منبع یا روش کشف مشخص
python run.py discover --no-crtsh --no-patterns

# افزودن یک یا چند دامنه به domains.txt بدون اجرای کشف
python run.py add-domain server1.example.com server2.example.com
```

<div dir="rtl" align="right">

<p>برای مشاهدهٔ همهٔ گزینه‌های کشف:</p>
</div>

```bash
python run.py discover --help
```

<div dir="rtl" align="right">

<h2>خروجی‌ها</h2>
<ul>
  <li><code>results.json</code> — زمان اجرا، تعداد کل، تعداد تست‌های موفق و جزئیات وضعیت هر دامنه.</li>
  <li><code>best_servers.txt</code> — سرورهایی که بررسی YouTube را با موفقیت گذرانده‌اند، به ترتیب زمان تست.</li>
  <li><code>discovered.json</code> — خروجی کشف دامنه؛ نام‌ها و نتیجهٔ بررسی دامنه‌های زنده.</li>
  <li>لاگ و فایل‌های موقت OpenConnect — در زمان اجرا ساخته می‌شوند؛ لاگ‌ها در الگوی <code>*.log</code> نادیده گرفته می‌شوند.</li>
</ul>

<p>کد خروجی دستور تست <code>0</code> است اگر دست‌کم یک سرور YouTube را با موفقیت باز کند، <code>1</code> اگر هیچ‌کدام موفق نشوند، و <code>2</code>/<code>3</code> برای خطای پیش‌بررسی/پیکربندی. دستور کشف نیز در صورت یافتن دامنهٔ زنده <code>0</code> و در غیر این صورت <code>1</code> برمی‌گرداند.</p>

<h2>عیب‌یابی</h2>
<ul>
  <li><strong>OpenConnect پیدا نشد:</strong> نصب را بررسی کنید و مطمئن شوید مسیر اجرایی آن در <code>PATH</code> است.</li>
  <li><strong>نیاز به Administrator/root:</strong> ترمینال را با دسترسی مدیریتی باز کنید؛ تغییر رابط تونل و مسیر شبکه ممکن است به این دسترسی نیاز داشته باشد.</li>
  <li><strong>اطلاعات ورود تنظیم نشده:</strong> نام کاربری و گذرواژه را در <code>.env</code> بررسی کنید.</li>
  <li><strong>اتصال VPN برقرار است ولی YouTube در دسترس نیست:</strong> جزئیات DNS/TCP/HTTP و IP خروجی را در <code>results.json</code> ببینید. شکست HTTP ممکن است ناشی از محدودیت شبکه یا پاسخ ضدربات باشد.</li>
  <li><strong>بررسی شبکه در Windows:</strong> اسکریپت <code>diagnose.ps1</code> آداپترها، مسیرهای پیش‌فرض، DNS و اتصال TCP به پورت 443 را نمایش می‌دهد. آن را از PowerShell اجرا کنید.</li>
</ul>

<h2>اجرای تست‌های پروژه</h2>
<p>تست‌ها با pytest اجرا می‌شوند و تست‌های واحد شبکه را mock می‌کنند؛ اجرای آن‌ها به اتصال VPN واقعی نیاز ندارد.</p>

</div>

```bash
python -m pytest
```

<div dir="rtl" align="right">

<h2>ساختار پروژه</h2>
<ul>
  <li><code>run.py</code> — نقطهٔ ورود CLI.</li>
  <li><code>vpn_tester/cli.py</code> — فرمان‌های تست، کشف و افزودن دامنه.</li>
  <li><code>vpn_tester/config.py</code> — بارگذاری تنظیمات و فهرست دامنه.</li>
  <li><code>vpn_tester/vpn.py</code> — مدیریت نشست OpenConnect.</li>
  <li><code>vpn_tester/youtube.py</code> — بررسی DNS، TCP، HTTPS و IP خروجی.</li>
  <li><code>vpn_tester/discovery.py</code> — کشف و بررسی دامنه‌ها.</li>
  <li><code>tests/</code> — تست‌های واحد.</li>
</ul>

<hr>
<p>این پروژه مستقل و جامعه‌محور است و وابستگی یا تأیید رسمی Cisco یا YouTube را ادعا نمی‌کند. فقط سامانه‌ها و دامنه‌هایی را بررسی کنید که مجاز به استفاده از آن‌ها هستید.</p>

</div>
