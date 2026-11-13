//+------------------------------------------------------------------+
//|                                         ICT_Wyckoff_Gold_EA.mq5  |
//|  XAUUSD: ระบบ Order Block H1 (ค่าเริ่มต้น) หรือโมเดล ICT เดิม         |
//|                                                                  |
//|  ระบบ Order Block H1 (InpStrategy = STRAT_OB)                       |
//|   1) โซน OB บน H1 ที่ยังไม่ถูกปิดหลุด                                |
//|   2) ราคาแทงทะลุขอบโซน แล้วบนกราฟ (แนะนำ M1) ปิดทะลุ swing high        |
//|      ก่อนจุดต่ำสุดครบ 2 ขั้น ด้วย tick volume เหนือค่าเฉลี่ย 30 แท่ง     |
//|   3) Limit ที่ขั้นแรก, SL ใต้ higher low, TP ที่ hidden zone H4/H1      |
//|   4) เข้าได้ 08:00-11:00 นิวยอร์ก ถือข้ามวันได้                         |
//|                                                                  |
//|  โมเดลเดิม (InpStrategy = STRAT_ICT): ICT 2022 + Wyckoff Spring/UTAD  |
//|                                                                  |
//|  ลำดับ: กวาดสภาพคล่องใน Kill Zone -> Displacement + MSS ทิ้ง FVG   |
//|        -> Limit ที่ FVG -> SL เลยจุดกวาด -> TP ที่สภาพคล่องฝั่งตรงข้าม |
//|                                                                  |
//|  ตรรกะเดียวกับ backtest/engine.py  สัญญาณคิดตอนแท่งปิดของ timeframe  |
//|  ที่แปะ EA (แนะนำ M5 ตามเอกสาร หรือ M1/M3 ถ้าต้องการ SL สั้น)         |
//|  ฝั่ง Sell ใช้ราคากลับเครื่องหมาย (p' = -p) จึงเขียนโค้ดฝั่ง Buy ชุดเดียว |
//+------------------------------------------------------------------+
#property version   "1.10"
#property description "Order Block H1 + ยืนยัน 2 ขั้น (ค่าเริ่มต้น) / ICT 2022 Model + Wyckoff (XAUUSD). ไม่ใช่คำแนะนำการลงทุน"

#include <Trade/Trade.mqh>

enum ENUM_FIB_SET
  {
   FIB_SET_OTE     = 0, // ชุด OTE: 0, 0.21, 0.295, 0.38, 0.5, 0.62, 0.705, 0.79, 1, -0.27, 1.27
   FIB_SET_QUARTER = 1  // ชุด Quarter: 0, 0.25, 0.5, 0.75, 1 พร้อมขอบ Buy/Sell ห่าง 0.059
  };

enum ENUM_STRATEGY
  {
   STRAT_OB  = 0, // Order Block H1 + ยืนยัน 2 ขั้น + hidden zone
   STRAT_ICT = 1  // โมเดลเดิม: ICT 2022 / Wyckoff / Quarter Zone / Silver Bullet
  };

enum ENUM_OB_SL
  {
   OB_SL_HL   = 0, // ใต้ higher low หลังจุดต่ำสุด
   OB_SL_LOW  = 1, // ใต้จุดต่ำสุดของการกลับตัว
   OB_SL_ZONE = 2  // ใต้ขอบโซน H1
  };

input group "=== ระบบ ==="
input ENUM_STRATEGY InpStrategy = STRAT_OB; // ระบบที่ใช้เทรด

input group "=== Order Block H1 (ใช้เมื่อเลือกระบบ Order Block) ==="
input int    InpObStart       = 800;    // เวลาเข้าได้ เริ่ม (นิวยอร์ก HHMM)
input int    InpObEnd         = 1100;   // เวลาเข้าได้ จบ (นิวยอร์ก HHMM)
input int    InpObBreakBars   = 3;      // โซน: ต้องปิดทะลุแท่ง OB ภายในกี่แท่ง H1
input double InpObDisp        = 1.5;    // โซน: ตัวแท่งของขาที่ทะลุ >= กี่เท่าของค่าเฉลี่ย 20 แท่ง H1
input int    InpObMaxAgeH     = 120;    // โซน: อายุสูงสุด (ชั่วโมง)
input int    InpObMaxZones    = 6;      // โซน: จำนวนสูงสุดต่อฝั่ง
input int    InpObLookbackH   = 200;    // โซน: ย้อนหาจากแท่ง H1 กี่แท่ง
input int    InpObSteps       = 2;      // ยืนยันกลับตัว: ต้องปิดทะลุ swing high กี่ขั้น
input int    InpObStepStrength = 2;     // ยืนยันกลับตัว: ความแรง swing (แท่งซ้าย/ขวา)
input double InpObVolMult     = 1.0;    // ยืนยันกลับตัว: tick volume แท่งที่ทะลุ > ค่าเฉลี่ย x เท่านี้ (0 = ปิด)
input int    InpObVolBars     = 30;     // ยืนยันกลับตัว: จำนวนแท่งของค่าเฉลี่ย volume
input int    InpObSetupMaxH   = 12;     // ยืนยันกลับตัว: ต้องเกิดภายในกี่ชั่วโมงหลังแทงโซน
input int    InpObRetestStep  = 1;      // จุดเข้า: Limit ที่ขั้นนี้ (1 = ขั้นแรก, 0 = Market ทันที)
input int    InpObPendingMin  = 120;    // จุดเข้า: Limit รอได้กี่นาทีหลังหมดเวลาเทรด
input ENUM_OB_SL InpObSlMode  = OB_SL_HL; // SL
input double InpObSlBuf       = 0.2;    // SL: ระยะเผื่อ (x ช่วงแท่งเฉลี่ย 20 แท่ง)
input double InpObMinRiskA    = 2.0;    // SL: ระยะขั้นต่ำ (x ช่วงแท่งเฉลี่ย 20 แท่ง)
input bool   InpObTpHidden    = true;   // TP: ที่ hidden zone ของ TF ใหญ่
input ENUM_TIMEFRAMES InpHzTF1 = PERIOD_H4; // TP: TF ใหญ่ที่หา hidden zone ตัวที่ 1
input ENUM_TIMEFRAMES InpHzTF2 = PERIOD_H1; // TP: TF ใหญ่ที่หา hidden zone ตัวที่ 2
input int    InpHzBars        = 3;      // TP: hidden zone = ไส้ซ้อนกันอย่างน้อยกี่แท่ง
input int    InpHzLookback    = 300;    // TP: ย้อนหา hidden zone กี่แท่ง
input double InpObMinRR       = 2.0;    // TP: RR ขั้นต่ำถึง hidden zone
input double InpObRR          = 3.0;    // TP: ถ้าไม่มี hidden zone ใช้ RR คงที่ (0 = ไม่เข้า)
input bool   InpObHoldOvernight = true; // ถือข้ามวัน (ไม่ปิดตาม InpEodExit)
input int    InpObMaxTradesDay = 5;     // จำนวนไม้สูงสุดต่อวัน
input int    InpObMaxLossesDay = 3;     // แพ้ครบกี่ไม้แล้วหยุดวันนั้น

input group "=== เวลา (ใส่เป็นเวลานิวยอร์ก HHMM) ==="
input int    InpServerMinusNY = 7;      // เวลาเซิร์ฟเวอร์โบรกเกอร์ ลบ เวลานิวยอร์ก (ชม.) โบรก GMT+2/+3 = 7
input int    InpAsiaStart     = 2000;   // Asia เริ่ม
input int    InpAsiaEnd       = 0;      // Asia จบ
input int    InpLondonStart   = 200;    // London Kill Zone เริ่ม
input int    InpLondonEnd     = 500;    // London Kill Zone จบ
input int    InpNYStart       = 700;    // New York AM Kill Zone เริ่ม
input int    InpNYEnd         = 1000;   // New York AM Kill Zone จบ
input bool   InpTradeLondon   = true;   // เทรด London Kill Zone
input bool   InpTradeNY       = true;   // เทรด New York AM Kill Zone
input int    InpNewsStart     = 815;    // งดช่วงข่าว เริ่ม
input int    InpNewsEnd       = 845;    // งดช่วงข่าว จบ
input int    InpEodExit       = 1600;   // ปิดทุกไม้เวลา (-1 = ถือข้ามวัน)
input bool   InpSkipNfpDay    = true;   // งดศุกร์แรกของเดือน (NFP)
input string InpNoTradeDates  = "";     // วันงดเทรด เช่น 2026.12.16;2027.01.27 (FOMC)

input group "=== สัญญาณ ==="
input bool   InpUseModel2022  = true;   // 2022 Mentorship Model (กวาด -> MSS -> FVG)
input bool   InpUseSilverBullet = false;// Silver Bullet: FVG แรกในชั่วโมงที่ชี้ไปทางเป้า
input int    InpSb1Start      = 300;    // Silver Bullet #1 เริ่ม (ยาว 1 ชม., -1 = ปิด)
input int    InpSb2Start      = 1000;   // Silver Bullet #2 เริ่ม
input int    InpSb3Start      = 1400;   // Silver Bullet #3 เริ่ม
input double InpSbTp1R        = 0.0;    // Silver Bullet: แบ่งปิดเมื่อกำไรกี่ R (0 = ไม่ใช้)
input bool   InpUseBias       = true;   // ICT: เทรดตาม bias รายวันเท่านั้น
input bool   InpUseIctLevels  = true;   // กวาด Asia / PDH-PDL / London
input bool   InpUseSwingLevels= true;   // กวาดจุดสูง-ต่ำเก่าบน H1
input int    InpSwingLookback = 48;     // จำนวนแท่ง H1 ที่ใช้หาจุดสูง-ต่ำเก่า
input int    InpSwingMax      = 2;      // จำนวนจุดต่อฝั่ง
input bool   InpUseWyckoff    = true;   // Wyckoff: กวาดขอบกรอบ H1 (Spring / UTAD)
input int    InpMaxMssMin     = 120;    // MSS ต้องเกิดภายในกี่นาทีหลังจุดกวาด
input double InpDispMult      = 1.5;    // ตัวแท่ง displacement >= กี่เท่าของค่าเฉลี่ย 20 แท่ง
input double InpMinFvg        = 0.2;    // FVG ขั้นต่ำ (เท่าของ A = ค่าเฉลี่ย high-low 20 แท่ง)
input bool   InpRequireDiscount = false;// จุดเข้าต้องอยู่ต่ำกว่า 50% ของขา displacement
input bool   InpEntryCE       = false;  // เข้าที่ CE 50% ของ FVG (false = ขอบช่อง)

input group "=== กรอบ Wyckoff บน H1 ==="
input int    InpWyBars        = 72;     // จำนวนแท่ง H1 ของกรอบ
input double InpWyMinWidth    = 3.0;    // ความกว้างกรอบขั้นต่ำ (เท่าของ high-low H1 เฉลี่ย)
input double InpWyMaxDrift    = 0.5;    // |ปิดสุดท้าย - ปิดแรก| / ความกว้างกรอบ สูงสุด
input int    InpWyMinTouches  = 2;      // จำนวนครั้งขั้นต่ำที่แตะขอบบนและขอบล่าง

input group "=== ออเดอร์ ==="
input double InpSlBuffer      = 0.5;    // เผื่อ SL เลยจุดกวาด (เท่าของ A)
input double InpMinRisk       = 2.0;    // ระยะ SL ขั้นต่ำ (เท่าของ A)
input double InpMaxRisk       = 12.0;   // ระยะ SL สูงสุด (เท่าของ A)
input double InpMinRR         = 2.0;    // Risk:Reward ขั้นต่ำถึงเป้า (โหมดเป้าจากกรอบแนะนำ 0.8)
input bool   InpTpFromRange   = false;  // เป้าจากกรอบราคา: TP1 = swing H1 ก่อนจุดกลับตัว, TP2 = ขอบ dealing range
input int    InpTpSwingStrength = 2;    // เป้าจากกรอบ: ความแรง swing H1 ที่ใช้เป็น TP1
input int    InpRangeLookback = 3000;   // เป้าจากกรอบ: ย้อนหาจุดที่โซนเกิดไม่เกินกี่แท่ง
input bool   InpSlBeyondZone  = false;  // SL พ้นโซนที่ถูกกวาด (x ATR H1) แทนการชิดไส้
input double InpSlZoneAtr     = 1.5;    // SL พ้นโซน: ระยะ (x ATR H1)
input double InpSlZoneMax     = 2.5;    // SL พ้นโซน: เพดานระยะ SL (x ATR H1)
input double InpFallbackRR    = 0.0;    // ถ้าไม่มีเป้าสภาพคล่อง ใช้ RR คงที่ (0 = ไม่เข้า)
input int    InpOrderGrace    = 60;     // นาทีที่ออเดอร์รอได้หลังหมด Kill Zone
input bool   InpPartialAtTp1  = true;   // ปิด 50% ที่ TP1 แล้วเลื่อน SL เท่าทุน
input bool   InpExitOnFvgFail = true;   // แท่งปิดทะลุ FVG สวนทาง -> ปิดเอง

input group "=== Fibonacci: TF ใหญ่บอกเทรนด์หลัก, TF เล็กหาจังหวะเข้า ==="
input bool   InpHtfFib        = false;  // TF ใหญ่: เทรดตามเทรนด์หลัก และราคาต้องย่อเข้าโซนของขาใหญ่
input ENUM_TIMEFRAMES InpHtfTF = PERIOD_H1; // TF ใหญ่หลักที่ใช้ตี Fibonacci / Quarter Zone
input int    InpHtfStrength   = 3;      // ความแรง swing บน TF ใหญ่ (แท่งซ้าย/ขวา)
input double InpHtfMinRetr    = 0.5;    // ราคาต้องย่ออย่างน้อยระดับนี้ของขาใหญ่ (0.5 = ครึ่ง Discount/Premium, 0 = ดูเทรนด์อย่างเดียว)
input double InpHtfMaxRetr    = 1.0;    // ราคาย่อได้ไม่เกินระดับนี้
input bool   InpLtfFib        = false;  // TF เล็ก: เข้าที่ระดับ Fibonacci ของขา displacement (แทนขอบ FVG)
input double InpFibEntry      = 0.705;  // ระดับเข้า
input bool   InpFibNeedFvg    = false;  // โซน 0.62-0.79 ต้องมี FVG ซ้อนอยู่
input bool   InpFibTp         = false;  // TP1 = ระดับ 0 (ปลายขา), TP2 = ระดับส่วนขยาย
input double InpFibTpExt      = 0.27;   // ส่วนขยายของ TP2 (0.27 = ระดับ -0.27)
input bool   InpQuarterZones  = false;  // Quarter Zone: ขอบกรอบ 0/0.25/0.5/0.75/1 ของขา TF ใหญ่เป็นจุดรอ แล้วยืนยันบน TF เล็ก
input double InpQzBand        = 0.059;  // Quarter Zone: ขอบกรอบห่างจากเส้นกลาง (สัดส่วนของขา)
input ENUM_TIMEFRAMES InpQzConfTF1 = PERIOD_H4;  // Quarter Zone: TF ที่ดูควบตัวที่ 1
input ENUM_TIMEFRAMES InpQzConfTF2 = PERIOD_M15; // Quarter Zone: TF ที่ดูควบตัวที่ 2
input int    InpQzMinConf     = 0;      // Quarter Zone: ขอบของ TF หลักต้องอยู่ในกรอบของ TF ควบอย่างน้อยกี่ TF (0 = ไม่ดูควบ)
input bool   InpQzMidTrend    = true;   // Quarter Zone: กรอบ 0.5 เข้าตามเทรนด์หลักของ TF ใหญ่เท่านั้น
input bool   InpQzCtLtf       = true;   // Quarter Zone: ไม้สวนเทรนด์หลักใช้ TP ตามขาของ TF เล็ก (ระดับ 0 และส่วนขยาย)
input bool   InpDrawFib       = false;  // วาด Fibonacci ของขา TF ใหญ่และ TF เล็กบนกราฟ
input ENUM_FIB_SET InpFibSet  = FIB_SET_OTE; // ชุดระดับที่ใช้วาด

input group "=== ตัวเลือกจาก ICT_TopDown (ปิดไว้เป็นค่าเริ่มต้น) ==="
input bool   InpPersistZones  = false;  // เก็บโซนข้ามวันจนกว่าจะถูกแตะ
input int    InpSweepPaBars   = 0;      // ต้องมีแท่งกลับตัวภายในกี่แท่งจากจุดสุดของไส้ (0 = ไม่บังคับ, แนะนำ 3)
input bool   InpRequireReclaim = false; // แท่ง MSS ต้องปิดกลับเหนือโซนที่ถูกกวาด
input double InpMssVolMult    = 0.0;    // tick volume แท่ง MSS > ค่าเฉลี่ย 50 แท่ง x เท่านี้ (0 = ปิด)
input bool   InpEntryPA       = false;  // รอแท่งปฏิเสธใน FVG แล้วเข้า Market (แทนการตั้ง Limit)
input int    InpPaWait        = 10;     // รอแท่งปฏิเสธใน FVG ได้กี่แท่ง
input double InpPinWickRatio  = 2.0;    // ไส้/เนื้อ ขั้นต่ำของ Pin bar
input int    InpMaxSpreadPoints = 0;    // spread สูงสุด (points, 0 = ปิด, แนะนำ 60)
input double InpMaxSpreadToSL = 0.0;    // spread / ระยะ SL สูงสุด (0 = ปิด, แนะนำ 0.2)
input double InpRiskLondon    = 0.0;    // ความเสี่ยงไม้ช่วง London % (0 = ใช้ค่าปกติ, แนะนำ 1.5)
input double InpMaxDailyLossPct = 0.0;  // หยุดเมื่อขาดทุนของวันถึง % นี้ (0 = ปิด, แนะนำ 3)
input int    InpBePlusPoints  = 0;      // กันทุนบวก (points) หลังถึง TP1 (แนะนำ 10)
input bool   InpDraw          = false;  // วาดจุดกวาดและ FVG
input bool   InpShowPanel     = false;  // แสดงแผงสถานะ

input group "=== ความเสี่ยง ==="
input double InpRiskPct       = 1.0;    // ความเสี่ยงต่อไม้ (% ของ equity)
input int    InpMaxTradesDay  = 2;      // จำนวนไม้สูงสุดต่อวัน
input int    InpMaxLossesDay  = 2;      // แพ้ครบกี่ไม้แล้วหยุดวันนั้น
input long   InpMagic         = 20261111;

#define BARS    3500
#define TAG_ASIA  1
#define TAG_LON   2
#define TAG_PD    3
#define TAG_SWING 4
#define TAG_WYCK  5
#define TAG_SB    6
#define TAG_QZ    7
#define TAG_OB    8

struct SObZone
  {
   int               d;
   double            lo;      // ราคา'
   double            hi;      // ราคา'
   datetime          from;    // เวลาที่เริ่มใช้ได้
   datetime          t;       // เวลาแท่ง OB
  };

struct SObSetup
  {
   int               d;
   bool              active;
   double            zlo, zhi;
   datetime          zt;
   double            ext;     // จุดต่ำสุด'
   datetime          extT;
   double            st[8];   // ระดับของแต่ละขั้น'
   int               nst;
  };

SObZone  g_ob[];
SObSetup g_os[2];
double   g_obUsed[];
datetime g_lastObH1 = 0;
bool     g_noTrade  = false;

struct SLevel
  {
   double            price;   // ราคา' (กลับเครื่องหมายแล้วสำหรับฝั่ง Sell)
   int               tag;
   double            tp1;
   double            tp2;
   bool              swept;
   bool              ltfTp;   // true = ใช้เป้าตามขาของ TF เล็กแทนเป้าที่มากับระดับ
  };

struct SSide
  {
   int               d;
   SLevel            lv[];
   double            tg[];    // เป้าสภาพคล่องฝั่งตรงข้าม (ราคา') เรียงจากใกล้ไปไกล
   bool              hasExt;
   double            ext;
   datetime          extTime;
   bool              hasMss;
   double            mss;
   bool              fired;
   bool              cand;    // เจอแท่งกลับตัวใกล้ปลายไส้แล้ว
   int               lvl;
  };

CTrade   trade;
SSide    g_s[2];
MqlRates r[];
datetime g_lastBar = 0;
datetime g_day     = 0;
bool     g_dayOk   = false;
int      g_bias    = 0;
double   g_pdh     = 0, g_pdl = 0;
int      g_kz      = 0;       // 0 = นอก Kill Zone, 1 = London, 2 = New York
int      g_kzEnd   = 0;
// สถานะของออเดอร์/ไม้ปัจจุบัน
int      g_dir     = 0;
double   g_tp1     = 0;       // ราคา'
double   g_tp2     = 0;       // ราคา'
double   g_fvgLo   = 0;       // ราคา'
int      g_expire  = 0;
bool     g_be      = false;
// รอแท่งปฏิเสธใน FVG (โหมด InpEntryPA)
bool     g_waitPA  = false;
int      g_wAge    = 0;
double   g_wEntry  = 0, g_wSl = 0, g_wExt = 0;   // ราคา'
int      g_wTag    = 0;
// โซนที่เก็บข้ามวัน (ราคาจริง)
double   g_zHi[], g_zLo[];
int      g_zHiTag[], g_zLoTag[];
int      g_curMod  = 0;
string   g_status  = "";
#define  PFX  "ICTWY_"
#define  ZCAP 64
double   g_cancelAt = 0;      // ราคา' ที่ถ้าถึงก่อนเข้าให้ยกเลิกออเดอร์
// Silver Bullet
int      g_sbWin   = -1;      // นาทีเริ่มของชั่วโมงปัจจุบัน (-1 = นอกช่วง)
bool     g_sbDone  = false;
double   g_sbTg0[], g_sbTg1[]; // เป้า' ฝั่ง Buy / Sell
MqlRates gh[];                // แท่ง H1
int      g_hi      = 0;       // จำนวนแท่ง H1 ที่ปิดแล้วก่อนแท่งปัจจุบัน

//+------------------------------------------------------------------+
//| เวลา                                                              |
//+------------------------------------------------------------------+
datetime T7(const datetime server) { return (datetime)(server + (7 - InpServerMinusNY) * 3600); }   // เวลานิวยอร์ก + 7 ชม.
int      ModOf(const datetime t7)  { return (int)((t7 % 86400) / 60); }
datetime DayOf(const datetime t7)  { return (datetime)(t7 - t7 % 86400); }
int      NyMod(const int hhmm)     { return ((hhmm / 100) * 60 + hhmm % 100 + 420) % 1440; }

double Hd(const int d, const MqlRates &b) { return d == 1 ? b.high  : -b.low;   }
double Ld(const int d, const MqlRates &b) { return d == 1 ? b.low   : -b.high;  }
double Cd(const int d, const MqlRates &b) { return d == 1 ? b.close : -b.close; }
double Od(const int d, const MqlRates &b) { return d == 1 ? b.open  : -b.open;  }

//+------------------------------------------------------------------+
// ความยาวช่วงเวลา (นาที) จากค่า HHMM สองค่า
int WindowMin(const int fromHHMM, const int toHHMM) { return (NyMod(toHHMM) - NyMod(fromHHMM) + 1440) % 1440; }

int OnInit()
  {
   // กันค่าเวลาผิดรูปแบบ: ต้องเป็น HHMM เช่น 200 = 02:00 (ถ้าใส่ 2 จะกลายเป็น 00:02)
   if(InpStrategy == STRAT_OB && WindowMin(InpObStart, InpObEnd) < 30)
     {
      Alert("ICT_Wyckoff_Gold_EA: เวลาเทรดต้องใส่แบบ HHMM เช่น 800-1100 (ค่าปัจจุบัน ", InpObStart, "-", InpObEnd, ")");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpStrategy == STRAT_ICT && ((InpTradeLondon && WindowMin(InpLondonStart, InpLondonEnd) < 30) || (InpTradeNY && WindowMin(InpNYStart, InpNYEnd) < 30)))
     {
      Alert("ICT_Wyckoff_Gold_EA: เวลา Kill Zone ต้องใส่แบบ HHMM เช่น London 200-500, New York 700-1000 (ค่าปัจจุบัน ",
            InpLondonStart, "-", InpLondonEnd, " / ", InpNYStart, "-", InpNYEnd, ") กด Reset ในแท็บ Inputs");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(PeriodSeconds(_Period) > 900)
      Print("ICT_Wyckoff_Gold_EA: คำเตือน - EA คิดสัญญาณจาก timeframe ของกราฟ ควรใช้ M1 / M3 / M5 (ปัจจุบัน ", EnumToString(_Period), ") บน timeframe ใหญ่แทบไม่มีสัญญาณ");
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(30);
   g_s[0].d = 1;
   g_s[1].d = -1;
   ResetSide(g_s[0]);
   ResetSide(g_s[1]);
   g_os[0].d = 1;
   g_os[1].d = -1;
   g_os[0].active = false;
   g_os[1].active = false;
   return INIT_SUCCEEDED;
  }

void ResetSide(SSide &s)
  {
   ArrayResize(s.lv, 0);
   ArrayResize(s.tg, 0);
   s.hasExt = false;
   s.hasMss = false;
   s.fired  = false;
   s.cand   = false;
   s.lvl    = -1;
  }

//+------------------------------------------------------------------+
//| ออเดอร์/สถานะของ EA                                                |
//+------------------------------------------------------------------+
ulong FindPosition()
  {
   for(int k = PositionsTotal() - 1; k >= 0; k--)
     {
      ulong t = PositionGetTicket(k);
      if(t > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return t;
     }
   return 0;
  }

ulong FindPending()
  {
   for(int k = OrdersTotal() - 1; k >= 0; k--)
     {
      ulong t = OrderGetTicket(k);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         return t;
     }
   return 0;
  }

void DeletePending()
  {
   ulong t = FindPending();
   if(t > 0)
      trade.OrderDelete(t);
  }

void ClosePosition()
  {
   ulong t = FindPosition();
   if(t > 0)
      trade.PositionClose(t);
  }

// นับจำนวนไม้ที่เปิดและจำนวนไม้ที่แพ้ของวันเทรดนี้
void DayCounters(int &trades, int &losses, double &dayPl)
  {
   trades = 0;
   losses = 0;
   dayPl  = 0;
   datetime from = (datetime)(g_day - (7 - InpServerMinusNY) * 3600);
   if(!HistorySelect(from, TimeCurrent() + 3600))
      return;
   ulong  ids[];
   double pl[];
   int n = HistoryDealsTotal();
   for(int k = 0; k < n; k++)
     {
      ulong deal = HistoryDealGetTicket(k);
      if(deal == 0 || HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
         continue;
      ulong pid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      int idx = -1;
      for(int q = 0; q < ArraySize(ids); q++)
         if(ids[q] == pid)
           {
            idx = q;
            break;
           }
      if(idx < 0)
        {
         idx = ArraySize(ids);
         ArrayResize(ids, idx + 1);
         ArrayResize(pl, idx + 1);
         ids[idx] = pid;
         pl[idx]  = 0;
        }
      if(HistoryDealGetInteger(deal, DEAL_ENTRY) == DEAL_ENTRY_IN)
         trades++;
      pl[idx] += HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP) + HistoryDealGetDouble(deal, DEAL_COMMISSION);
     }
   for(int q = 0; q < ArraySize(ids); q++)
     {
      dayPl += pl[q];
      if(pl[q] < 0 && !PositionSelectByTicket(ids[q]))
         losses++;
     }
  }

// ครบไม้ / แพ้ครบ / ถึงเพดานขาดทุนของวันแล้วหรือยัง
bool DayLimitHit()
  {
   int trades, losses;
   double dayPl;
   DayCounters(trades, losses, dayPl);
   int maxT = InpStrategy == STRAT_OB ? InpObMaxTradesDay : InpMaxTradesDay;
   int maxL = InpStrategy == STRAT_OB ? InpObMaxLossesDay : InpMaxLossesDay;
   if(trades >= maxT || losses >= maxL)
      return true;
   if(InpMaxDailyLossPct > 0)
     {
      double startBal = AccountInfoDouble(ACCOUNT_BALANCE) - dayPl;
      if(startBal > 0 && dayPl <= -InpMaxDailyLossPct / 100.0 * startBal)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| แท่งกลับตัว: Pin bar / Engulfing / Morning-Evening star            |
//+------------------------------------------------------------------+
bool PA(const int i, const int d)
  {
   if(i < 2)
      return false;
   double o = r[i].open, h = r[i].high, l = r[i].low, c = r[i].close;
   double rg = h - l;
   if(rg > 0)
     {
      double bd = MathAbs(c - o);
      double up = h - MathMax(o, c), dn = MathMin(o, c) - l;
      double wick = d == 1 ? dn : up, opp = d == 1 ? up : dn;
      if(wick >= InpPinWickRatio * MathMax(bd, rg * 0.1) && wick >= 0.55 * rg && opp <= 0.25 * rg)
         return true;
     }
   double po = r[i - 1].open, pc = r[i - 1].close;
   double cb = d * (c - o), pb = d * (po - pc);
   if(cb > 0 && pb > 0 && (d == 1 ? (c > po && o <= pc) : (c < po && o >= pc)))
      return true;
   double o1 = r[i - 2].open, c1 = r[i - 2].close, r1 = r[i - 2].high - r[i - 2].low;
   double b1 = d * (o1 - c1);
   if(r1 > 0 && b1 >= 0.5 * r1 && MathAbs(pc - po) <= 0.3 * b1 && cb > 0)
     {
      double mid = (o1 + c1) / 2;
      return d == 1 ? c > mid : c < mid;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| โซนที่เก็บข้ามวัน                                                  |
//+------------------------------------------------------------------+
void ZoneMerge(double &store[], int &stag[], const double &px[], const int &tg[])
  {
   for(int k = 0; k < ArraySize(px); k++)
     {
      bool has = false;
      for(int q = 0; q < ArraySize(store) && !has; q++)
         if(store[q] == px[k])
            has = true;
      if(has)
         continue;
      int n = ArraySize(store);
      if(n >= ZCAP)
        {
         ArrayRemove(store, 0, 1);
         ArrayRemove(stag, 0, 1);
         n--;
        }
      ArrayResize(store, n + 1);
      ArrayResize(stag, n + 1);
      store[n] = px[k];
      stag[n]  = tg[k];
     }
  }

void ZonePrune(const int i)
  {
   for(int k = ArraySize(g_zHi) - 1; k >= 0; k--)
      if(r[i].high > g_zHi[k])
        {
         ArrayRemove(g_zHi, k, 1);
         ArrayRemove(g_zHiTag, k, 1);
        }
   for(int k = ArraySize(g_zLo) - 1; k >= 0; k--)
      if(r[i].low < g_zLo[k])
        {
         ArrayRemove(g_zLo, k, 1);
         ArrayRemove(g_zLoTag, k, 1);
        }
  }

//+------------------------------------------------------------------+
//| วาดบนกราฟ / แผงสถานะ                                               |
//+------------------------------------------------------------------+
// วาด Fibonacci: ระดับ 1 ที่ต้นขา (t1, p1) ระดับ 0 ที่ปลายขา (t2, p2)
void DrawFib(const string id, const datetime t1, const double p1, const datetime t2, const double p2)
  {
   if(!InpDrawFib)
      return;
   string nm = PFX + "fib" + id;
   ObjectDelete(0, nm);
   if(!ObjectCreate(0, nm, OBJ_FIBO, 0, t1, p1, t2, p2))
      return;
   double lv[];
   color  lc[];
   string lt[];
   if(InpFibSet == FIB_SET_QUARTER)
     {
      double v[14] = {-0.059, 0.059, 0.191, 0.25, 0.309, 0.441, 0.5, 0.559, 0.691, 0.75, 0.809, 0.941, 1, 1.059};
      string t[14] = {"Buy(Demand)", "Sell(Supply)", "Buy(Demand)", "", "Sell(Demand)", "Buy(Demand)", "EQ", "Sell(Supply)",
                      "Buy(Supply)", "", "Sell(Supply)", "Buy(Supply)", "", "Sell(Supply)"};
      ArrayResize(lv, 14);
      ArrayResize(lc, 14);
      ArrayResize(lt, 14);
      for(int k = 0; k < 14; k++)
        {
         lv[k] = v[k];
         lt[k] = t[k];
         lc[k] = StringFind(t[k], "Buy") == 0 ? clrDodgerBlue : StringFind(t[k], "Sell") == 0 ? clrTomato : t[k] == "EQ" ? clrGold : clrGray;
        }
     }
   else
     {
      double v[11] = {0, 0.21, 0.295, 0.38, 0.5, 0.62, 0.705, 0.79, 1, -0.27, 1.27};
      color  c[11] = {clrGray, clrYellow, clrYellow, clrYellow, clrRed, clrDodgerBlue, clrDodgerBlue, clrDodgerBlue, clrGray, clrGray, clrSilver};
      ArrayResize(lv, 11);
      ArrayResize(lc, 11);
      ArrayResize(lt, 11);
      for(int k = 0; k < 11; k++)
        {
         lv[k] = v[k];
         lc[k] = c[k];
         lt[k] = "";
        }
     }
   int nl = ArraySize(lv);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clrGray);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, nm, OBJPROP_RAY_RIGHT, true);
   ObjectSetInteger(0, nm, OBJPROP_LEVELS, nl);
   for(int k = 0; k < nl; k++)
     {
      ObjectSetDouble(0, nm, OBJPROP_LEVELVALUE, k, lv[k]);
      ObjectSetInteger(0, nm, OBJPROP_LEVELCOLOR, k, lc[k]);
      ObjectSetInteger(0, nm, OBJPROP_LEVELSTYLE, k, STYLE_SOLID);
      ObjectSetString(0, nm, OBJPROP_LEVELTEXT, k, (lt[k] == "" ? "" : lt[k] + "  ") + DoubleToString(lv[k], 3) + "  %$");
     }
  }

//+------------------------------------------------------------------+
//| Fibonacci บน TF ใหญ่: เทรนด์หลักจากโครงสร้าง + ระดับที่ราคาย่อเข้ามา   |
//| คืนเทรนด์ (1 / -1 / 0), retr = ระดับที่ราคาอยู่ในขาใหญ่ของทิศ d       |
//| (0 = ปลายขา, 1 = ต้นขา, -1 = หาขาไม่ได้)                            |
//+------------------------------------------------------------------+
int HtfFib(const int i, const int d, double &retr)
  {
   retr = -1;
   MqlRates h[];
   int n = CopyRates(_Symbol, InpHtfTF, 0, 330, h);
   if(n < 40)
      return 0;
   ArraySetAsSeries(h, false);
   long ps = PeriodSeconds(InpHtfTF);
   datetime bucket = (datetime)(r[i].time - r[i].time % ps);
   int cut = n;                                   // จำนวนแท่ง TF ใหญ่ที่ปิดแล้วก่อนแท่งที่มี r[i]
   while(cut > 0 && h[cut - 1].time >= bucket)
      cut--;
   int st = InpHtfStrength;
   int a = MathMax(cut - 300, st);
   int trend = 0;
   double sh = 0, sl = 0;
   bool shB = true, slB = true;
   for(int j = a + st; j < cut; j++)
     {
      int k = j - st;
      if(k - st >= 0)
        {
         bool isH = true, isL = true;
         for(int q = 1; q <= st; q++)
           {
            if(!(h[k].high > h[k - q].high && h[k].high > h[k + q].high))
               isH = false;
            if(!(h[k].low < h[k - q].low && h[k].low < h[k + q].low))
               isL = false;
           }
         if(isH)
           {
            sh = h[k].high;
            shB = false;
           }
         if(isL)
           {
            sl = h[k].low;
            slB = false;
           }
        }
      if(!shB && h[j].close > sh)
        {
         trend = 1;
         shB = true;
        }
      if(!slB && h[j].close < sl)
        {
         trend = -1;
         slB = true;
        }
     }
   for(int k = cut - st - 1; k > a; k--)          // swing low' ล่าสุด = ต้นขา
     {
      bool sw = true;
      for(int q = 1; q <= st && sw; q++)
         if(!(Ld(d, h[k]) < Ld(d, h[k - q]) && Ld(d, h[k]) < Ld(d, h[k + q])))
            sw = false;
      if(!sw)
         continue;
      double lo = Ld(d, h[k]), hi = -DBL_MAX;
      datetime hiT = h[k].time;
      for(int q = k; q < cut; q++)
         if(Hd(d, h[q]) > hi)
           {
            hi = Hd(d, h[q]);
            hiT = h[q].time;
           }
      for(int q = i; q >= 0 && DayOf(T7(r[q].time)) == g_day; q--)
         if(Hd(d, r[q]) > hi)
           {
            hi = Hd(d, r[q]);
            hiT = r[q].time;
           }
      if(hi > lo)
        {
         retr = (hi - Cd(d, r[i])) / (hi - lo);
         if(trend == d)
            DrawFib("H", h[k].time, d * lo, hiT, d * hi);
        }
      break;
     }
   return trend;
  }

void DrawSweep(const datetime t, const double level)
  {
   if(!InpDraw)
      return;
   string nm = PFX + "sw" + IntegerToString((long)t) + DoubleToString(level, 2);
   if(ObjectCreate(0, nm, OBJ_TREND, 0, t - 30 * PeriodSeconds(), level, t + 5 * PeriodSeconds(), level))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, clrGold);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
     }
  }

void DrawFVG(const int d, const datetime t, const double a, const double b)
  {
   if(!InpDraw)
      return;
   string nm = PFX + "fvg" + IntegerToString((long)t) + "_" + IntegerToString(d);
   if(ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t, a, t + 20 * PeriodSeconds(), b))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, d == 1 ? clrMediumSeaGreen : clrIndianRed);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
     }
  }

void Panel()
  {
   if(!InpShowPanel)
      return;
   if(InpStrategy == STRAT_OB)
     {
      Comment(ObPanelText() + (g_status != "" ? "สถานะ: " + g_status : ""));
      return;
     }
   string txt = "ICT + Wyckoff Gold EA\n";
   txt += "Bias: " + (g_bias == 1 ? "Buy" : g_bias == -1 ? "Sell" : "-") + (g_dayOk ? "" : "  (วันนี้งดเทรด)") + "\n";
   txt += "Kill Zone: " + (g_kz == 1 ? "London" : g_kz == 2 ? "New York" : "-") + "\n";
   for(int si = 0; si < 2; si++)
     {
      txt += si == 0 ? "Buy : " : "Sell: ";
      txt += IntegerToString(ArraySize(g_s[si].lv)) + " ระดับ";
      if(g_s[si].hasExt)
         txt += " | กวาดแล้ว " + DoubleToString(MathAbs(g_s[si].ext), _Digits) + (g_s[si].fired ? " | MSS" : " | รอ MSS");
      txt += "\n";
     }
   if(g_waitPA)
      txt += "รอแท่งปฏิเสธใน FVG (" + IntegerToString(g_wAge) + "/" + IntegerToString(InpPaWait) + ")\n";
   if(g_status != "")
      txt += "สถานะ: " + g_status;
   Comment(txt);
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PFX);
   if(InpShowPanel)
      Comment("");
  }

//+------------------------------------------------------------------+
//| Bias รายวัน (วันเทรดเริ่ม 17:00 นิวยอร์ก)                            |
//+------------------------------------------------------------------+
bool ComputeBias()
  {
   MqlRates h[];
   int n = CopyRates(_Symbol, PERIOD_H1, 0, 200, h);
   if(n < 60)
      return false;
   ArraySetAsSeries(h, false);
   double hi[2], lo[2], cl[2];
   int found = -1;
   datetime cur = g_day;
   for(int k = n - 1; k >= 0; k--)
     {
      datetime dk = DayOf(T7(h[k].time));
      if(dk >= g_day)
         continue;
      if(dk != cur)
        {
         found++;
         if(found > 1)
            break;
         cur = dk;
         hi[found] = h[k].high;
         lo[found] = h[k].low;
         cl[found] = h[k].close;
        }
      else
        {
         hi[found] = MathMax(hi[found], h[k].high);
         lo[found] = MathMin(lo[found], h[k].low);
        }
     }
   if(found < 1)
      return false;
   // [0] = เมื่อวาน, [1] = วันก่อนเมื่อวาน
   bool up = hi[0] > hi[1], dn = lo[0] < lo[1];
   if(up && !dn)
      g_bias = cl[0] > hi[1] ? 1 : -1;          // ปิดทะลุ = ไปต่อ, ไส้ทะลุแล้วปิดกลับ = กลับตัว
   else if(dn && !up)
      g_bias = cl[0] < lo[1] ? -1 : 1;
   else if(up && dn)
      g_bias = cl[0] > hi[1] ? 1 : (cl[0] < lo[1] ? -1 : 0);
   else
      g_bias = 0;                               // inside day
   g_pdh = hi[0];
   g_pdl = lo[0];
   return true;
  }

bool IsNoTradeDate(const datetime day)
  {
   MqlDateTime s;
   TimeToStruct(day, s);
   if(InpSkipNfpDay && s.day_of_week == 5 && s.day <= 7)
      return true;
   return StringFind(InpNoTradeDates, TimeToString(day, TIME_DATE)) >= 0;
  }

//+------------------------------------------------------------------+
//| ระดับสภาพคล่องตอนเข้า Kill Zone                                    |
//+------------------------------------------------------------------+
void AddLevel(SSide &s, const double price, const int tag, const double tp1, const double tp2)
  {
   int k = ArraySize(s.lv);
   ArrayResize(s.lv, k + 1);
   s.lv[k].price = price;
   s.lv[k].tag   = tag;
   s.lv[k].tp1   = tp1;
   s.lv[k].tp2   = tp2;
   s.lv[k].swept = false;
   s.lv[k].ltfTp = false;
  }

void AddHL(double &px[], int &tg[], const double price, const int tag)
  {
   int k = ArraySize(px);
   ArrayResize(px, k + 1);
   ArrayResize(tg, k + 1);
   px[k] = price;
   tg[k] = tag;
  }

// สภาพคล่องที่ยังไม่ถูกกวาด ณ แท่ง i (ราคาจริง) และจุดสูง/ต่ำของวันนี้ก่อนแท่ง i
void CollectLiquidity(const int i, const bool withLon, double &highs[], int &htag[], double &lows[], int &ltag[], double &tH, double &tL)
  {
   ArrayResize(highs, 0);
   ArrayResize(lows, 0);
   ArrayResize(htag, 0);
   ArrayResize(ltag, 0);
   int asiaA = NyMod(InpAsiaStart), asiaB = NyMod(InpAsiaEnd);
   int lonA = NyMod(InpLondonStart), lonB = NyMod(InpLondonEnd);
   double aH = -DBL_MAX, aL = DBL_MAX, aaH = -DBL_MAX, aaL = DBL_MAX;   // Asia และหลัง Asia
   double lH = -DBL_MAX, lL = DBL_MAX, alH = -DBL_MAX, alL = DBL_MAX;   // London และหลัง London
   tH = -DBL_MAX;                                                       // ทั้งวันก่อนแท่ง i
   tL = DBL_MAX;
   bool hasAsia = false, hasLon = false;
   for(int k = i - 1; k >= 0; k--)
     {
      datetime t7 = T7(r[k].time);
      if(DayOf(t7) != g_day)
         break;
      int m = ModOf(t7);
      tH = MathMax(tH, r[k].high);
      tL = MathMin(tL, r[k].low);
      if(m >= asiaA && m < asiaB)
        {
         hasAsia = true;
         aH = MathMax(aH, r[k].high);
         aL = MathMin(aL, r[k].low);
        }
      if(m >= asiaB)
        {
         aaH = MathMax(aaH, r[k].high);
         aaL = MathMin(aaL, r[k].low);
        }
      if(m >= lonA && m < lonB)
        {
         hasLon = true;
         lH = MathMax(lH, r[k].high);
         lL = MathMin(lL, r[k].low);
        }
      if(m >= lonB)
        {
         alH = MathMax(alH, r[k].high);
         alL = MathMin(alL, r[k].low);
        }
     }
   if(hasAsia)
     {
      if(aH > aaH)
         AddHL(highs, htag, aH, TAG_ASIA);
      if(aL < aaL)
         AddHL(lows, ltag, aL, TAG_ASIA);
     }
   if(withLon && hasLon)
     {
      if(lH > alH)
         AddHL(highs, htag, lH, TAG_LON);
      if(lL < alL)
         AddHL(lows, ltag, lL, TAG_LON);
     }
   if(g_pdh > tH)
      AddHL(highs, htag, g_pdh, TAG_PD);
   if(g_pdl < tL)
      AddHL(lows, ltag, g_pdl, TAG_PD);

   // --- แท่ง H1 ที่ปิดแล้วก่อนเข้า Kill Zone ---
   int hn = CopyRates(_Symbol, PERIOD_H1, 0, 300, gh);
   int hi = 0;                                   // จำนวนแท่ง H1 ที่ปิดแล้ว
   if(hn > 0)
     {
      ArraySetAsSeries(gh, false);
      datetime hourStart = (datetime)(r[i].time - r[i].time % 3600);
      hi = hn;
      while(hi > 0 && gh[hi - 1].time >= hourStart)
         hi--;
     }
   if(InpUseSwingLevels && hi >= InpSwingLookback)
     {
      int a = hi - InpSwingLookback, nh = 0, nl = 0;
      for(int k = hi - 3; k >= a + 2; k--)
        {
         if(nh < InpSwingMax && gh[k].high > MathMax(MathMax(gh[k - 2].high, gh[k - 1].high), MathMax(gh[k + 1].high, gh[k + 2].high)))
           {
            double mx = -DBL_MAX;
            for(int q = k + 1; q < hi; q++)
               mx = MathMax(mx, gh[q].high);
            if(gh[k].high > mx)
              {
               AddHL(highs, htag, gh[k].high, TAG_SWING);
               nh++;
              }
           }
         if(nl < InpSwingMax && gh[k].low < MathMin(MathMin(gh[k - 2].low, gh[k - 1].low), MathMin(gh[k + 1].low, gh[k + 2].low)))
           {
            double mn = DBL_MAX;
            for(int q = k + 1; q < hi; q++)
               mn = MathMin(mn, gh[q].low);
            if(gh[k].low < mn)
              {
               AddHL(lows, ltag, gh[k].low, TAG_SWING);
               nl++;
              }
           }
        }
     }
   g_hi = hi;
  }

void SetupKillZone(const int i)
  {
   double highs[], lows[], tH, tL;
   int    htag[], ltag[];
   CollectLiquidity(i, g_kz == 2, highs, htag, lows, ltag, tH, tL);
   if(InpPersistZones)
     {
      ZoneMerge(g_zHi, g_zHiTag, highs, htag);
      ZoneMerge(g_zLo, g_zLoTag, lows, ltag);
      ArrayCopy(highs, g_zHi);
      ArrayCopy(htag, g_zHiTag);
      ArrayCopy(lows, g_zLo);
      ArrayCopy(ltag, g_zLoTag);
      ArrayResize(highs, ArraySize(g_zHi));
      ArrayResize(htag, ArraySize(g_zHi));
      ArrayResize(lows, ArraySize(g_zLo));
      ArrayResize(ltag, ArraySize(g_zLo));
     }
   int hi = g_hi;
   for(int si = 0; si < 2; si++)
     {
      int d = g_s[si].d;
      // เป้า = สภาพคล่องฝั่งตรงข้าม เรียงจากใกล้ไปไกล
      int nt = (d == 1) ? ArraySize(highs) : ArraySize(lows);
      ArrayResize(g_s[si].tg, nt);
      for(int k = 0; k < nt; k++)
         g_s[si].tg[k] = (d == 1) ? highs[k] : -lows[k];
      if(nt > 1)
         ArraySort(g_s[si].tg);
      if(InpUseIctLevels && (!InpUseBias || g_bias == d))
        {
         int nm = (d == 1) ? ArraySize(lows) : ArraySize(highs);
         for(int k = 0; k < nm; k++)
           {
            int tag = (d == 1) ? ltag[k] : htag[k];
            if(tag == TAG_SWING && !InpUseSwingLevels)
               continue;
            AddLevel(g_s[si], (d == 1) ? lows[k] : -highs[k], tag, 0, 0);
           }
        }
     }
   // --- กรอบ Wyckoff ---
   if(InpUseWyckoff && hi >= InpWyBars)
     {
      int a = hi - InpWyBars;
      double rh = -DBL_MAX, rl = DBL_MAX, sum = 0;
      for(int k = a; k < hi; k++)
        {
         rh = MathMax(rh, gh[k].high);
         rl = MathMin(rl, gh[k].low);
         sum += gh[k].high - gh[k].low;
        }
      double w = rh - rl;
      bool ok = w >= InpWyMinWidth * sum / InpWyBars && MathAbs(gh[hi - 1].close - gh[a].close) <= InpWyMaxDrift * w;
      if(ok)
        {
         double upZone = rh - 0.25 * w, dnZone = rl + 0.25 * w;
         int ups = 0, dns = 0, state = 0;
         for(int k = a; k < hi; k++)
           {
            if(gh[k].high >= upZone && state != 1)
              {
               ups++;
               state = 1;
              }
            else if(gh[k].low <= dnZone && state != -1)
              {
               dns++;
               state = -1;
              }
           }
         if(ups >= InpWyMinTouches && dns >= InpWyMinTouches)
           {
            double mid = (rl + rh) / 2;
            AddLevel(g_s[0], rl, TAG_WYCK, mid, rh);       // Spring -> Buy
            AddLevel(g_s[1], -rh, TAG_WYCK, -mid, -rl);    // UTAD -> Sell
           }
        }
     }
   if(InpQuarterZones && i > 0)
      AddQuarterZones(i);
  }

//+------------------------------------------------------------------+
//| Quarter Zone: กรอบของ TF ใหญ่ = swing low / swing high ล่าสุด        |
//| ขอบล่างของกรอบฝั่ง Discount (ต่ำกว่า 0.5) = จุดหา Buy               |
//| ขอบบนของกรอบฝั่ง Premium (สูงกว่า 0.5) = จุดหา Sell                  |
//| เป้า: TP1 = ขอบอีกฝั่งของกรอบเดียวกัน, TP2 = ขอบของกรอบถัดไป           |
//| ต้องมีการยืนยันบน TF เล็ก (กวาดขอบ -> MSS -> FVG) จึงเข้า             |
//+------------------------------------------------------------------+
// กรอบของ TF ที่ระบุ: swing low และ swing high ล่าสุดที่ยืนยันแล้ว
bool QzRange(const ENUM_TIMEFRAMES tf, const int i, double &lo, double &hi, datetime &loT, datetime &hiT)
  {
   MqlRates h[];
   int n = CopyRates(_Symbol, tf, 0, 330, h);
   if(n < 40)
      return false;
   ArraySetAsSeries(h, false);
   long ps = PeriodSeconds(tf);
   datetime bucket = (datetime)(r[i].time - r[i].time % ps);
   int cut = n;
   while(cut > 0 && h[cut - 1].time >= bucket)
      cut--;
   int st = InpHtfStrength;
   lo = 0;
   hi = 0;
   loT = 0;
   hiT = 0;
   bool hasLo = false, hasHi = false;
   for(int k = cut - st - 1; k > MathMax(cut - 300, st) && !(hasLo && hasHi); k--)
     {
      bool isH = true, isL = true;
      for(int q = 1; q <= st; q++)
        {
         if(!(h[k].high > h[k - q].high && h[k].high > h[k + q].high))
            isH = false;
         if(!(h[k].low < h[k - q].low && h[k].low < h[k + q].low))
            isL = false;
        }
      if(isH && !hasHi)
        {
         hi = h[k].high;
         hiT = h[k].time;
         hasHi = true;
        }
      if(isL && !hasLo)
        {
         lo = h[k].low;
         loT = h[k].time;
         hasLo = true;
        }
     }
   return hasLo && hasHi && hi > lo;
  }

// จำนวน TF ควบที่ราคานี้อยู่ในกรอบ Quarter ฝั่งเดียวกัน (Buy: กรอบ 0-0.5, Sell: กรอบ 0.5-1)
int QzConf(const int i, const double price, const int d)
  {
   ENUM_TIMEFRAMES tfs[2];
   tfs[0] = InpQzConfTF1;
   tfs[1] = InpQzConfTF2;
   int cnt = 0;
   for(int t = 0; t < 2; t++)
     {
      if(tfs[t] == PERIOD_CURRENT || tfs[t] == InpHtfTF || (t == 1 && tfs[1] == tfs[0]))
         continue;
      double lo, hi;
      datetime loT, hiT;
      if(!QzRange(tfs[t], i, lo, hi, loT, hiT))
         continue;
      double pos = (price - lo) / (hi - lo);
      for(int k = 0; k < 3; k++)
        {
         double c = (d == 1) ? 0.25 * k : 0.5 + 0.25 * k;
         if(MathAbs(pos - c) <= InpQzBand)
           {
            cnt++;
            break;
           }
        }
     }
   return cnt;
  }

// ดูควบหลาย TF: ลบขอบ Quarter Zone ที่ไม่ตรงกับกรอบของ TF ควบ
void QzFilterConf(const int i)
  {
   for(int si = 0; si < 2; si++)
     {
      int d = g_s[si].d;
      for(int k = ArraySize(g_s[si].lv) - 1; k >= 0; k--)
         if(g_s[si].lv[k].tag == TAG_QZ && QzConf(i, d * g_s[si].lv[k].price, d) < InpQzMinConf)
            ArrayRemove(g_s[si].lv, k, 1);
     }
  }

void AddQuarterZones(const int i)
  {
   double lo, hi;
   datetime loT, hiT;
   if(!QzRange(InpHtfTF, i, lo, hi, loT, hiT))
      return;
   double rg = hi - lo, b = InpQzBand, px = r[i - 1].close;
   double retr;
   int trend = HtfFib(i, 1, retr);                      // เทรนด์หลักของ TF ใหญ่
   double cb[3] = {0.0, 0.25, 0.5}, cs[3] = {1.0, 0.75, 0.5};
   int nq = InpQzMidTrend ? 2 : 3;                      // กรอบ 0.5 แยกไปทำด้านล่างเมื่อเล่นตามเทรนด์
   for(int k = 0; k < nq; k++)
     {
      double e = lo + (cb[k] - b) * rg;                 // ขอบล่างของกรอบฝั่ง Discount -> Buy
      if(px > e)
        {
         AddLevel(g_s[0], e, TAG_QZ, lo + (cb[k] + b) * rg, lo + (cb[k] + 0.25 - b) * rg);
         g_s[0].lv[ArraySize(g_s[0].lv) - 1].ltfTp = InpQzCtLtf && trend == -1;
        }
      e = lo + (cs[k] + b) * rg;                        // ขอบบนของกรอบฝั่ง Premium -> Sell
      if(px < e)
        {
         AddLevel(g_s[1], -e, TAG_QZ, -(lo + (cs[k] - b) * rg), -(lo + (cs[k] - 0.25 + b) * rg));
         g_s[1].lv[ArraySize(g_s[1].lv) - 1].ltfTp = InpQzCtLtf && trend == 1;
        }
     }
   if(InpQzMidTrend && trend == 1)                      // กรอบ 0.5: Buy ตามเทรนด์ขาขึ้น ทั้งสองขอบ
     {
      if(px > lo + (0.5 - b) * rg)
         AddLevel(g_s[0], lo + (0.5 - b) * rg, TAG_QZ, lo + (0.5 + b) * rg, lo + (0.75 - b) * rg);
      if(px > lo + (0.5 + b) * rg)
         AddLevel(g_s[0], lo + (0.5 + b) * rg, TAG_QZ, lo + (0.75 - b) * rg, lo + (0.75 + b) * rg);
     }
   else if(InpQzMidTrend && trend == -1)                // กรอบ 0.5: Sell ตามเทรนด์ขาลง ทั้งสองขอบ
     {
      if(px < lo + (0.5 + b) * rg)
         AddLevel(g_s[1], -(lo + (0.5 + b) * rg), TAG_QZ, -(lo + (0.5 - b) * rg), -(lo + (0.25 + b) * rg));
      if(px < lo + (0.5 - b) * rg)
         AddLevel(g_s[1], -(lo + (0.5 - b) * rg), TAG_QZ, -(lo + (0.25 + b) * rg), -(lo + (0.25 - b) * rg));
     }
   if(InpQzMinConf > 0)
      QzFilterConf(i);
   // วาดกรอบ: ระดับ 0 ที่ swing low, ระดับ 1 ที่ swing high
   DrawFib("Q", hiT, hi, loT, lo);
  }

//+------------------------------------------------------------------+
//| คำนวณ lot จากระยะ Stop Loss                                        |
//+------------------------------------------------------------------+
double CalcLot(const ENUM_ORDER_TYPE type, const double entry, const double sl)
  {
   double loss = 0;
   if(!OrderCalcProfit(type, _Symbol, 1.0, entry, sl, loss) || loss >= 0)
      return 0;
   bool   inLon = g_curMod >= NyMod(InpLondonStart) && g_curMod < NyMod(InpLondonEnd);
   double riskPct = (inLon && InpRiskLondon > 0) ? InpRiskLondon : InpRiskPct;
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * riskPct / 100.0;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lot  = MathFloor(riskMoney / (-loss) / step + 1e-9) * step;
   if(lot < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      return 0;                                  // SL กว้างเกินทุน -> ข้าม setup
   return MathMin(lot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
  }

//+------------------------------------------------------------------+
//| เกิด MSS แล้ว: หา FVG, จุดเข้า, SL, TP แล้ววางออเดอร์                  |
//+------------------------------------------------------------------+
void TrySetup(SSide &s, const int i, const int endm)
  {
   if(FindPending() > 0 || FindPosition() > 0 || g_waitPA)
      return;
   if(DayLimitHit())
     {
      g_status = "ครบไม้ / ถึงเพดานขาดทุนของวัน";
      return;
     }
   if((endm >= NyMod(InpNewsStart) && endm < NyMod(InpNewsEnd)) || endm >= g_kzEnd)
      return;
   int d = s.d, e = -1;
   for(int k = i; k >= 0; k--)
      if(r[k].time == s.extTime)
        {
         e = k;
         break;
        }
   if(e < 120)
      return;
   double avgBody = 0, A = 0;
   for(int k = e - 20; k < e; k++)
     {
      avgBody += MathAbs(r[k].close - r[k].open);
      A += r[k].high - r[k].low;
     }
   avgBody /= 20;
   A /= 20;
   double legBody = -DBL_MAX, legHigh = -DBL_MAX;
   for(int k = e; k <= i; k++)
     {
      legBody = MathMax(legBody, Cd(d, r[k]) - Od(d, r[k]));
      legHigh = MathMax(legHigh, Hd(d, r[k]));
     }
   if(legBody < InpDispMult * avgBody)
      return;                                    // ไม่มี Displacement
   double eq = (legHigh + s.ext) / 2;
   if(InpHtfFib)
     {
      double retr;
      int ht = HtfFib(i, d, retr);
      if(ht != d || retr < 0 || retr < InpHtfMinRetr || retr > InpHtfMaxRetr)
        {
         g_status = "TF ใหญ่: เทรนด์ไม่ตรง หรือราคายังไม่เข้าโซน Fibonacci";
         return;
        }
     }
   double ent = 0, fvgLo = 0;
   bool found = false;
   for(int j = i; j > e && !found; j--)          // FVG จากบนลงล่าง
     {
      double gLo = Hd(d, r[j - 2]), gHi = Ld(d, r[j]);
      if(gHi - gLo < InpMinFvg * A)
         continue;
      double ce = (gLo + gHi) / 2;
      bool filled = false;
      for(int q = j + 1; q <= i; q++)
         if(Ld(d, r[q]) <= ce)
            filled = true;                       // ถูกเติมเกินครึ่งแล้ว
      if(filled)
         continue;
      double x = InpEntryCE ? ce : gHi;
      if(InpRequireDiscount && x > eq)
        {
         if(ce <= eq)
            x = ce;
         else
            continue;
        }
      ent = x;
      fvgLo = gLo;
      found = true;
     }
   if(InpLtfFib)
     {
      double rg = legHigh - s.ext;
      double zHi = legHigh - 0.62 * rg, zLo = legHigh - 0.79 * rg;
      if(InpFibNeedFvg && (!found || fvgLo > zHi || ent < zLo))
         found = false;                           // ไม่มี FVG ซ้อนโซน 0.62-0.79
      else
        {
         ent   = legHigh - InpFibEntry * rg;
         fvgLo = s.ext;
         found = true;
        }
      DrawFib("L" + IntegerToString((long)r[i].time), s.extTime, d * s.ext, r[i].time, d * legHigh);
     }
   if(!found)
      return;
   // แท่ง H1: he = แท่งที่มีจุดสุดของไส้
   MqlRates h[];
   int hn = CopyRates(_Symbol, PERIOD_H1, 0, 400, h);
   ArraySetAsSeries(h, false);
   int he = -1;
   for(int k = hn - 1; k >= 0; k--)
      if(h[k].time <= r[e].time)
        {
         he = k;
         break;
        }
   double level = s.lv[s.lvl].price;
   double sl = s.ext - InpSlBuffer * A;
   double risk;
   if(InpSlBeyondZone && he >= 15)
     {
      double aH1 = 0;
      for(int k = he - 14; k < he; k++)
         aH1 += h[k].high - h[k].low;
      aH1 /= 14;
      sl = MathMin(sl, level - InpSlZoneAtr * aH1);   // พ้นโซน หรือหลังไส้ถ้าไส้ลึกกว่า
      risk = ent - sl;
      if(risk <= 0 || risk > InpSlZoneMax * aH1)
         return;
     }
   else
     {
      risk = ent - sl;
      if(risk < InpMinRisk * A || risk > InpMaxRisk * A)
         return;
     }
   double tp1 = 0, tp2 = 0;
   if(InpFibTp)
     {
      tp1 = legHigh;                               // ระดับ 0
      tp2 = legHigh + InpFibTpExt * (legHigh - s.ext);   // ระดับ -0.27
      if(tp2 - ent < InpMinRR * risk)
         return;
     }
   else if(InpTpFromRange)
     {
      // TP1 = swing H1 ล่าสุดก่อนจุดกลับตัวที่อยู่เหนือจุดเข้า
      if(he < 0)
         return;
      bool got = false;
      int ts = InpTpSwingStrength;
      for(int k = he - 1; k > MathMax(he - 300, ts) && !got; k--)
        {
         if(k + ts > he)
            continue;
         double v = Hd(d, h[k]);
         if(v <= ent)
            continue;
         bool sw = true;
         for(int q = 1; q <= ts && sw; q++)
            if(!(v > Hd(d, h[k + q]) && v >= Hd(d, h[k - q])))
               sw = false;
         if(sw)
           {
            tp1 = v;
            got = true;
           }
        }
      if(!got || tp1 - ent < InpMinRR * risk)
         return;
      // TP2 = ขอบ dealing range: จุดสูงสุดตั้งแต่โซนเกิดจนถึงจุดกวาด
      int j = e - 1, lim = MathMax(e - InpRangeLookback, 0);
      while(j > lim && Ld(d, r[j]) > level)
         j--;
      double edge = -DBL_MAX;
      for(int k = j; k <= e; k++)
         edge = MathMax(edge, Hd(d, r[k]));
      tp2 = (edge > tp1) ? edge : tp1;
     }
   else
     {
      if(s.lv[s.lvl].tag == TAG_WYCK || s.lv[s.lvl].tag == TAG_QZ)
        {
         tp1 = s.lv[s.lvl].tp1;                     // กลางกรอบ
         tp2 = s.lv[s.lvl].tp2;                     // ขอบกรอบฝั่งตรงข้าม
         if(s.lv[s.lvl].ltfTp)                      // ไม้สวนเทรนด์หลัก: เป้าตามขาของ TF เล็ก
           {
            tp1 = legHigh;
            tp2 = legHigh + InpFibTpExt * (legHigh - s.ext);
           }
         if(tp2 - ent < InpMinRR * risk)
            return;
        }
      else
        {
         double dayHi = -DBL_MAX;
         for(int k = i; k >= 0 && DayOf(T7(r[k].time)) == g_day; k--)
            dayHi = MathMax(dayHi, Hd(d, r[k]));
         bool has = false;
         for(int k = 0; k < ArraySize(s.tg); k++)
            if(s.tg[k] > dayHi && s.tg[k] - ent >= InpMinRR * risk)
              {
               tp2 = s.tg[k];
               has = true;
               break;
              }
         if(!has)
           {
            if(InpFallbackRR <= 0)
               return;                              // ไม่มีเป้า = ไม่เข้า
            tp2 = ent + InpFallbackRR * risk;
           }
         tp1 = legHigh;
         for(int j = e - 1; j > MathMax(e - 96, 1); j--)   // จุดสูงย่อยฝั่งตรงข้ามตัวแรก
            if(Hd(d, r[j]) > legHigh && Hd(d, r[j]) > Hd(d, r[j - 1]) && Hd(d, r[j]) > Hd(d, r[j + 1]))
              {
               tp1 = Hd(d, r[j]);
               break;
              }
        }
      tp1 = MathMin(MathMax(tp1, ent + risk), tp2);
     }

   DrawFVG(d, r[i].time, d * ent, d * fvgLo);
   if(InpEntryPA)
     {
      // ไม่ตั้ง Limit: รอราคาย่อเข้า FVG แล้วเกิดแท่งปฏิเสธ จึงเข้า Market
      g_waitPA = true;
      g_wAge   = 0;
      g_dir    = d;
      g_wEntry = ent;
      g_wSl    = sl;
      g_wExt   = s.ext;
      g_wTag   = s.lv[s.lvl].tag;
      g_tp1    = tp1;
      g_tp2    = tp2;
      g_fvgLo  = fvgLo;
      g_expire = g_kzEnd + InpOrderGrace;
      return;
     }
   PlaceOrder(d, ent, sl, tp1, tp2, fvgLo, g_kzEnd + InpOrderGrace, InpLtfFib ? tp2 : tp1, s.lv[s.lvl].tag);
  }

//+------------------------------------------------------------------+
//| วางออเดอร์ (ราคาทุกตัวเป็นราคา' ของทิศ d)                            |
//+------------------------------------------------------------------+
bool PlaceOrder(const int d, const double ent, const double sl, const double tp1, const double tp2,
                const double fvgLo, const int expire, const double cancelAt, const int tag)
  {
   int    dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pEnt = NormalizeDouble(d * ent, dg), pSl = NormalizeDouble(d * sl, dg), pTp = NormalizeDouble(d * tp2, dg);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(InpMaxSpreadPoints > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints)
     {
      g_status = "spread สูง";
      return false;
     }
   if(InpMaxSpreadToSL > 0 && ent - sl > 0 && (ask - bid) / (ent - sl) > InpMaxSpreadToSL)
     {
      g_status = "spread เทียบ SL สูง";
      return false;
     }
   double lot = CalcLot(d == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, pEnt, pSl);
   if(lot <= 0)
      return false;
   string cm = "ICTWY " + IntegerToString(tag);
   bool ok;
   if(d == 1)
      ok = (ask <= pEnt) ? trade.Buy(lot, _Symbol, 0, pSl, pTp, cm) : trade.BuyLimit(lot, pEnt, _Symbol, pSl, pTp, ORDER_TIME_GTC, 0, cm);
   else
      ok = (bid >= pEnt) ? trade.Sell(lot, _Symbol, 0, pSl, pTp, cm) : trade.SellLimit(lot, pEnt, _Symbol, pSl, pTp, ORDER_TIME_GTC, 0, cm);
   if(!ok)
     {
      Print("วางออเดอร์ไม่สำเร็จ: ", trade.ResultRetcodeDescription());
      return false;
     }
   g_dir      = d;
   g_tp1      = tp1;
   g_tp2      = tp2;
   g_fvgLo    = fvgLo;
   g_expire   = expire;
   g_cancelAt = cancelAt;
   g_be       = false;
   return true;
  }

//+------------------------------------------------------------------+
//| Silver Bullet: FVG แรกที่เกิดในชั่วโมงและชี้ไปทางเป้าสภาพคล่อง         |
//+------------------------------------------------------------------+
void SilverBullet(const int i, const int mod, const int endm)
  {
   int win = -1;
   int st[3];
   st[0] = InpSb1Start;
   st[1] = InpSb2Start;
   st[2] = InpSb3Start;
   for(int k = 0; k < 3; k++)
      if(st[k] >= 0 && mod >= NyMod(st[k]) && mod < NyMod(st[k]) + 60)
         win = NyMod(st[k]);
   if(win != g_sbWin)
     {
      g_sbWin  = win;
      g_sbDone = false;
      if(win >= 0)
        {
         double highs[], lows[], tH, tL;
         int    htag[], ltag[];
         CollectLiquidity(i, mod >= NyMod(InpLondonEnd), highs, htag, lows, ltag, tH, tL);
         int nh = ArraySize(highs), nl = ArraySize(lows);
         ArrayResize(g_sbTg0, nh + 1);
         ArrayResize(g_sbTg1, nl + 1);
         for(int k = 0; k < nh; k++)
            g_sbTg0[k] = highs[k];
         g_sbTg0[nh] = tH;
         for(int k = 0; k < nl; k++)
            g_sbTg1[k] = -lows[k];
         g_sbTg1[nl] = -tL;
         ArraySort(g_sbTg0);
         ArraySort(g_sbTg1);
        }
     }
   if(win < 0 || g_sbDone || i < 22 || FindPending() > 0 || FindPosition() > 0)
      return;
   if(ModOf(T7(r[i - 1].time)) < win || endm >= win + 60)
      return;                                    // แท่งกลางของ FVG ต้องอยู่ในชั่วโมง
   if(endm >= NyMod(InpNewsStart) && endm < NyMod(InpNewsEnd))
      return;
   if(DayLimitHit() || g_waitPA)
      return;
   double A = 0;
   for(int k = i - 22; k < i - 2; k++)
      A += r[k].high - r[k].low;
   A /= 20;
   for(int si = 0; si < 2; si++)
     {
      int d = (si == 0) ? 1 : -1;
      if(InpUseBias && g_bias != d)
         continue;
      double gLo = Hd(d, r[i - 2]), gHi = Ld(d, r[i]);
      if(gHi - gLo < InpMinFvg * A)
         continue;
      double ent = InpEntryCE ? (gLo + gHi) / 2 : gHi;
      double sl = Ld(d, r[i - 2]) - InpSlBuffer * A;   // หลังแท่งที่ 1 ของช่อง
      double risk = ent - sl;
      if(risk < InpMinRisk * A || risk > InpMaxRisk * A)
         continue;
      double dayHi = -DBL_MAX;
      for(int k = i; k >= 0 && DayOf(T7(r[k].time)) == g_day; k--)
         dayHi = MathMax(dayHi, Hd(d, r[k]));
      double tp2 = 0;
      bool has = false;
      int nt = (d == 1) ? ArraySize(g_sbTg0) : ArraySize(g_sbTg1);
      for(int k = 0; k < nt && !has; k++)
        {
         double tgt = (d == 1) ? g_sbTg0[k] : g_sbTg1[k];
         if(tgt >= dayHi && tgt - ent >= InpMinRR * risk)
           {
            tp2 = tgt;
            has = true;
           }
        }
      if(!has)
         continue;
      double tp1 = (InpSbTp1R > 0) ? MathMin(ent + InpSbTp1R * risk, tp2) : tp2;
      if(PlaceOrder(d, ent, sl, tp1, tp2, gLo, win + 60, tp2, TAG_SB))
        {
         g_sbDone = true;
         return;
        }
     }
  }

//+------------------------------------------------------------------+
//| ระบบ Order Block H1                                                |
//| 1) โซน: แท่งสวนทางแท่งสุดท้ายบน H1 ก่อนขาที่ปิดทะลุมันด้วยแรง         |
//| 2) ราคาแทงทะลุขอบโซน แล้วบน TF ของกราฟต้องปิดทะลุ swing high          |
//|    ก่อนจุดต่ำสุดครบ InpObSteps ขั้น ด้วย tick volume เหนือค่าเฉลี่ย     |
//| 3) ตั้ง Limit รอราคาย่อกลับมาที่ขั้นที่ทะลุ, SL ใต้ swing low           |
//| 4) TP ที่ hidden zone ของ TF ใหญ่ (ไส้ซ้อนกันหลายแท่ง) ที่ให้ RR ถึง     |
//| ฝั่ง Sell ใช้ราคากลับเครื่องหมายเหมือนส่วนอื่นของ EA                    |
//+------------------------------------------------------------------+
bool InWindow(const int m, const int a, const int b) { return a <= b ? (m >= a && m <= b) : (m >= a || m <= b); }

bool ObUsed(const double lo)
  {
   for(int k = 0; k < ArraySize(g_obUsed); k++)
      if(MathAbs(g_obUsed[k] - lo) < _Point * 0.5)
         return true;
   return false;
  }

// สร้างรายการโซน Order Block จากแท่ง H1 ที่ปิดแล้ว (เรียกทุกครั้งที่ขึ้นแท่ง H1 ใหม่)
void ObBuildZones()
  {
   ArrayResize(g_ob, 0);
   MqlRates h[];
   int n = CopyRates(_Symbol, PERIOD_H1, 1, InpObLookbackH + 30, h);
   if(n < 40)
      return;
   ArraySetAsSeries(h, false);
   for(int si = 0; si < 2; si++)
     {
      int d = si == 0 ? 1 : -1;
      int first = ArraySize(g_ob);
      for(int k = 20; k < n - 1; k++)
        {
         if(Cd(d, h[k]) - Od(d, h[k]) >= 0)
            continue;                            // ต้องเป็นแท่งสวนทาง
         double avg = 0;
         for(int q = k - 20; q < k; q++)
            avg += MathAbs(h[q].close - h[q].open);
         avg /= 20;
         for(int m = k + 1; m <= MathMin(k + InpObBreakBars, n - 1); m++)
           {
            if(Cd(d, h[m]) <= Hd(d, h[k]))
               continue;
            double mx = -DBL_MAX;                // แรงของขาที่ปิดทะลุ
            for(int q = k + 1; q <= m; q++)
               mx = MathMax(mx, Cd(d, h[q]) - Od(d, h[q]));
            if(mx >= InpObDisp * avg)
              {
               double lo = Ld(d, h[k]), hi = Hd(d, h[k]);
               bool alive = true;                // แท่ง H1 ปิดหลุดโซนแล้ว = โซนใช้ไม่ได้
               for(int q = m + 1; q < n && alive; q++)
                  if(Cd(d, h[q]) < lo)
                     alive = false;
               datetime from = h[m].time + 3600;
               if(alive && h[n - 1].time + 3600 - from <= (long)InpObMaxAgeH * 3600 && !ObUsed(lo))
                 {
                  int z = ArraySize(g_ob);
                  ArrayResize(g_ob, z + 1);
                  g_ob[z].d = d;
                  g_ob[z].lo = lo;
                  g_ob[z].hi = hi;
                  g_ob[z].from = from;
                  g_ob[z].t = h[k].time;
                 }
              }
            break;
           }
        }
      while(ArraySize(g_ob) - first > InpObMaxZones)   // เก็บเฉพาะโซนล่าสุด
         ArrayRemove(g_ob, first, 1);
     }
  }

// ขั้นของการกลับตัว: swing high ก่อนจุดต่ำสุด เรียงจากใกล้ไปไกล แต่ละขั้นสูงกว่าขั้นก่อน
void ObSteps(const int si, const int e)
  {
   int d = g_os[si].d, st = InpObStepStrength;
   g_os[si].nst = 0;
   double last = -DBL_MAX;
   for(int j = e - st - 1; j > MathMax(e - 180, st) && g_os[si].nst < MathMin(InpObSteps, 8); j--)
     {
      double v = Hd(d, r[j]);
      if(v <= last)
         continue;
      bool sw = true;
      for(int q = 1; q <= st && sw; q++)
         if(!(v > Hd(d, r[j - q]) && v > Hd(d, r[j + q])))
            sw = false;
      if(sw)
        {
         last = v;
         g_os[si].st[g_os[si].nst] = v;
         g_os[si].nst++;
        }
     }
  }

int BarIdx(const datetime t, const int i)
  {
   for(int k = i; k >= 0; k--)
      if(r[k].time <= t)
         return k;
   return 0;
  }

// Hidden zone: แท่งบน TF ใหญ่ทิ้งไส้ซ้อนกันอย่างน้อย InpHzBars แท่ง และยังไม่ถูกปิดทะลุ
// คืน TP' = ขอบใกล้ของโซนที่อยู่ใกล้ที่สุดและให้ RR ถึง InpObMinRR
bool HiddenTarget(const int d, const double ent, const double risk, double &tp)
  {
   ENUM_TIMEFRAMES tfs[2];
   tfs[0] = InpHzTF1;
   tfs[1] = InpHzTF2;
   bool found = false;
   double best = DBL_MAX;
   for(int t = 0; t < 2; t++)
     {
      if(tfs[t] == PERIOD_CURRENT || (t == 1 && tfs[1] == tfs[0]))
         continue;
      MqlRates h[];
      int n = CopyRates(_Symbol, tfs[t], 1, InpHzLookback, h);
      if(n < InpHzBars + 2)
         continue;
      ArraySetAsSeries(h, false);
      for(int k = 0; k + InpHzBars <= n; k++)
        {
         double zl = -DBL_MAX, zh = DBL_MAX;
         for(int q = k; q < k + InpHzBars; q++)
           {
            zl = MathMax(zl, MathMax(Od(d, h[q]), Cd(d, h[q])));   // ตัวแท่ง
            zh = MathMin(zh, Hd(d, h[q]));                         // ปลายไส้
           }
         if(zh <= zl || zl <= ent || zl - ent < InpObMinRR * risk || zl >= best)
            continue;
         bool broken = false;
         for(int q = k + InpHzBars; q < n && !broken; q++)
            if(Cd(d, h[q]) > zh)
               broken = true;
         if(broken)
            continue;
         best = zl;
         found = true;
        }
     }
   tp = best;
   return found;
  }

bool PosIsOB()
  {
   ulong t = FindPosition();
   return t > 0 && PositionSelectByTicket(t) && StringFind(PositionGetString(POSITION_COMMENT), "ICTWY " + IntegerToString(TAG_OB)) == 0;
  }

void ObProcess(const int i, const int mod, const int endm)
  {
   datetime h1 = iTime(_Symbol, PERIOD_H1, 0);
   if(h1 != g_lastObH1)
     {
      g_lastObH1 = h1;
      ObBuildZones();
     }
   if(i < 40)
      return;
   double A = 0;
   for(int k = i - 20; k < i; k++)
      A += r[k].high - r[k].low;
   A /= 20;
   bool inWin = InWindow(endm, NyMod(InpObStart), NyMod(InpObEnd));
   for(int si = 0; si < 2; si++)
     {
      int d = g_os[si].d;
      if(g_os[si].active)
        {
         bool alive = false;
         for(int k = 0; k < ArraySize(g_ob) && !alive; k++)
            if(g_ob[k].d == d && MathAbs(g_ob[k].lo - g_os[si].zlo) < _Point * 0.5)
               alive = true;
         if(!alive || r[i].time - g_os[si].extT > (long)InpObSetupMaxH * 3600)
            g_os[si].active = false;
        }
      if(!g_os[si].active)
        {
         int best = -1;                          // โซนที่ถูกแทงทะลุในแท่งนี้
         for(int k = 0; k < ArraySize(g_ob); k++)
            if(g_ob[k].d == d && g_ob[k].from <= r[i].time && Ld(d, r[i]) < g_ob[k].lo &&
               (best < 0 || g_ob[k].lo > g_ob[best].lo))
               best = k;
         if(best < 0)
            continue;
         g_os[si].active = true;
         g_os[si].zlo = g_ob[best].lo;
         g_os[si].zhi = g_ob[best].hi;
         g_os[si].zt  = g_ob[best].t;
         g_os[si].ext = Ld(d, r[i]);
         g_os[si].extT = r[i].time;
         ObSteps(si, i);
         continue;
        }
      if(Ld(d, r[i]) < g_os[si].ext)             // ทำจุดต่ำใหม่: นับขั้นใหม่
        {
         g_os[si].ext = Ld(d, r[i]);
         g_os[si].extT = r[i].time;
         ObSteps(si, i);
         continue;
        }
      int ns = g_os[si].nst;
      if(ns < MathMin(InpObSteps, 8) || ns == 0 || Cd(d, r[i]) <= g_os[si].st[ns - 1] || Cd(d, r[i]) <= g_os[si].zlo)
         continue;                               // ยังปิดทะลุไม่ครบทุกขั้น
      if(InpObVolMult > 0 && i > InpObVolBars)
        {
         double av = 0;
         for(int k = i - InpObVolBars; k < i; k++)
            av += (double)r[k].tick_volume;
         av /= InpObVolBars;
         if(av > 0 && (double)r[i].tick_volume <= InpObVolMult * av)
           {
            g_status = "ทะลุครบ " + IntegerToString(ns) + " ขั้นแล้ว แต่ volume ต่ำกว่าค่าเฉลี่ย";
            continue;
           }
        }
      if(!inWin)
        {
         g_status = "มี setup แต่อยู่นอกเวลาเทรด";
         continue;
        }
      if(g_noTrade || g_waitPA || FindPending() > 0 || FindPosition() > 0)
         continue;
      if(DayLimitHit())
        {
         g_status = "ครบไม้ / ถึงเพดานขาดทุนของวัน";
         continue;
        }
      double ent;
      if(InpObRetestStep > 0)
         ent = g_os[si].st[MathMin(InpObRetestStep, ns) - 1];   // รอย่อกลับมาที่ขั้นที่ทะลุ
      else
         ent = d * (d == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID));
      int e = BarIdx(g_os[si].extT, i);
      double sl;
      if(InpObSlMode == OB_SL_LOW)
         sl = g_os[si].ext - InpObSlBuf * A;
      else if(InpObSlMode == OB_SL_HL && e < i)
        {
         double hl = DBL_MAX;                    // higher low หลังจุดต่ำสุด
         for(int k = e + 1; k <= i; k++)
            hl = MathMin(hl, Ld(d, r[k]));
         sl = hl - InpObSlBuf * A;
        }
      else
         sl = g_os[si].zlo - InpObSlBuf * A;
      double risk = ent - sl;
      if(risk <= 0 || risk < InpObMinRiskA * A)
         continue;
      double tp = 0;
      if(!(InpObTpHidden && HiddenTarget(d, ent, risk, tp)))
        {
         if(InpObRR <= 0)
           {
            g_status = "ไม่มี hidden zone ที่ให้ RR ถึง";
            continue;
           }
         tp = ent + InpObRR * risk;
        }
      if(PlaceOrder(d, ent, sl, tp, tp, sl, NyMod(InpObEnd) + InpObPendingMin, tp, TAG_OB))
        {
         int u = ArraySize(g_obUsed);
         ArrayResize(g_obUsed, u + 1);
         g_obUsed[u] = g_os[si].zlo;
         DrawFVG(d, g_os[si].zt, d * g_os[si].zhi, d * g_os[si].zlo);
         DrawSweep(r[i].time, d * tp);
         g_os[si].active = false;
         ObBuildZones();
        }
     }
  }

string ObPanelText()
  {
   int nb = 0, ns = 0;
   for(int k = 0; k < ArraySize(g_ob); k++)
      if(g_ob[k].d == 1)
         nb++;
      else
         ns++;
   string txt = "ICT Gold EA: Order Block H1\n";
   txt += "โซน OB ที่รอ: Buy " + IntegerToString(nb) + " | Sell " + IntegerToString(ns) + "\n";
   txt += "เวลาเทรด: " + (InWindow(g_curMod + PeriodSeconds(_Period) / 60, NyMod(InpObStart), NyMod(InpObEnd)) ? "ใช่" : "ไม่ใช่") + "\n";
   for(int si = 0; si < 2; si++)
     {
      txt += si == 0 ? "Buy : " : "Sell: ";
      if(g_os[si].active)
        {
         txt += "แทงโซน " + DoubleToString(MathAbs(g_os[si].zlo), _Digits) + " | ขั้น ";
         for(int k = 0; k < g_os[si].nst; k++)
            txt += DoubleToString(MathAbs(g_os[si].st[k]), _Digits) + " ";
        }
      else
         txt += "-";
      txt += "\n";
     }
   return txt;
  }

//+------------------------------------------------------------------+
//| ทุก tick: ยกเลิกออเดอร์ถ้าราคาถึง TP1 ก่อนเข้า, แบ่งปิดที่ TP1          |
//+------------------------------------------------------------------+
void ManageOnTick()
  {
   if(g_dir == 0 || g_waitPA)
      return;
   double px = g_dir * (g_dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK));
   ulong pos = FindPosition();
   if(pos == 0)
     {
      if(FindPending() == 0)
         g_dir = 0;                              // ไม้ปิดไปแล้ว
      else if(px >= g_cancelAt)
         DeletePending();                        // ราคาไปถึงเป้าก่อนย่อมาเข้า
      return;
     }
   if(g_be || px < g_tp1)
      return;
   g_be = true;
   if(!PositionSelectByTicket(pos))
      return;
   double vol  = PositionGetDouble(POSITION_VOLUME);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double tp   = PositionGetDouble(POSITION_TP);
   if(InpPartialAtTp1 && g_tp1 < g_tp2)
     {
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double half = MathFloor(vol / 2 / step + 1e-9) * step;
      if(half >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
         trade.PositionClosePartial(pos, half);
     }
   if(PositionSelectByTicket(pos))
      trade.PositionModify(pos, NormalizeDouble(open + g_dir * InpBePlusPoints * _Point, _Digits), tp);   // เลื่อน SL มาที่จุดเข้า (บวกระยะกันทุน)
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   ManageOnTick();
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == g_lastBar)
      return;
   g_lastBar = bt;
   OnNewBar();
  }

void OnNewBar()
  {
   int n = CopyRates(_Symbol, _Period, 1, BARS, r);
   if(n < 300)
      return;
   ArraySetAsSeries(r, false);
   int i = n - 1;                                // แท่งที่เพิ่งปิด
   int tf = PeriodSeconds(_Period) / 60;
   datetime t7 = T7(r[i].time);
   int mod = ModOf(t7), endm = mod + tf;
   datetime day = DayOf(t7);
   g_curMod = mod;
   g_status = "";

   if(day != g_day)                              // ---------- วันใหม่ ----------
     {
      g_day = day;
      g_kz  = 0;
      g_sbWin = -1;
      ResetSide(g_s[0]);
      ResetSide(g_s[1]);
      DeletePending();
      g_waitPA = false;
      g_noTrade = IsNoTradeDate(day);
      g_dayOk = ComputeBias() && !g_noTrade;
     }

   // ---------- จัดการตอนแท่งปิด ----------
   int newsA = NyMod(InpNewsStart), newsB = NyMod(InpNewsEnd);
   if(FindPosition() > 0)
     {
      if(InpEodExit >= 0 && endm >= NyMod(InpEodExit) && !(InpObHoldOvernight && PosIsOB()))
         ClosePosition();
      else if(g_dir != 0 && InpExitOnFvgFail && !g_be && Cd(g_dir, r[i]) < g_fvgLo)
         ClosePosition();                        // แท่งปิดสวนทะลุ FVG ที่ใช้เข้า
     }
   else if(FindPending() > 0)
     {
      if(g_dir == 0 || Cd(g_dir, r[i]) < g_fvgLo || endm >= g_expire || (InpStrategy == STRAT_ICT && endm >= newsA && endm < newsB))
         DeletePending();
     }
   if(g_waitPA)                                  // ---------- รอแท่งปฏิเสธใน FVG ----------
     {
      int d = g_dir;
      g_wAge++;
      if(g_wAge > InpPaWait || Ld(d, r[i]) < g_wExt || Cd(d, r[i]) < g_fvgLo || endm >= g_expire || (endm >= newsA && endm < newsB))
         g_waitPA = false;
      else if(Ld(d, r[i]) <= g_wEntry && PA(i, d))
        {
         g_waitPA = false;
         double px = d * (d == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID));
         double risk = px - g_wSl;
         double tgt = InpTpFromRange ? g_tp1 : g_tp2;
         bool inKz = (mod >= NyMod(InpLondonStart) && endm <= NyMod(InpLondonEnd)) || (mod >= NyMod(InpNYStart) && endm <= NyMod(InpNYEnd));
         if(risk > 0 && tgt - px >= InpMinRR * risk && inKz && FindPosition() == 0 && !DayLimitHit())
            PlaceOrder(d, px, g_wSl, MathMax(g_tp1, px), g_tp2, g_fvgLo, g_expire, g_tp2 + 1, g_wTag);
        }
      if(!g_waitPA && FindPosition() == 0 && FindPending() == 0)
         g_dir = 0;
     }
   if(InpStrategy == STRAT_OB)
     {
      ObProcess(i, mod, endm);
      Panel();
      return;
     }
   if(!g_dayOk)
     {
      if(InpPersistZones)
         ZonePrune(i);
      Panel();
      return;
     }

   // ---------- เข้า/ออก Kill Zone ----------
   int lonA = NyMod(InpLondonStart), lonB = NyMod(InpLondonEnd), nyA = NyMod(InpNYStart), nyB = NyMod(InpNYEnd);
   int newKz = 0;
   if(InpTradeLondon && mod >= lonA && mod < lonB)
      newKz = 1;
   else if(InpTradeNY && mod >= nyA && mod < nyB)
      newKz = 2;
   if(newKz != g_kz)
     {
      g_kz = newKz;
      ResetSide(g_s[0]);
      ResetSide(g_s[1]);
      if(g_kz != 0)
        {
         g_kzEnd = (g_kz == 1) ? lonB : nyB;
         SetupKillZone(i);
        }
     }
   if(InpPersistZones)
      ZonePrune(i);
   if(InpUseSilverBullet)
      SilverBullet(i, mod, endm);
   if(g_kz == 0 || !InpUseModel2022)
     {
      Panel();
      return;
     }

   // ---------- ติดตามการกวาดสภาพคล่อง / MSS ----------
   for(int si = 0; si < 2; si++)
     {
      int d = g_s[si].d;
      if(ArraySize(g_s[si].lv) == 0)
         continue;
      double lo = Ld(d, r[i]);
      bool newExt = false;
      for(int k = 0; k < ArraySize(g_s[si].lv); k++)
         if(!g_s[si].lv[k].swept && lo < g_s[si].lv[k].price)
           {
            g_s[si].lv[k].swept = true;
            g_s[si].lvl = k;
            DrawSweep(r[i].time, MathAbs(g_s[si].lv[k].price));
            newExt = true;
           }
      if(g_s[si].hasExt && lo < g_s[si].ext)
         newExt = true;
      if(newExt && (!g_s[si].hasExt || lo < g_s[si].ext))
        {
         g_s[si].hasExt  = true;
         g_s[si].ext     = lo;
         g_s[si].extTime = r[i].time;
         g_s[si].fired   = false;
         g_s[si].hasMss  = false;
         g_s[si].cand    = InpSweepPaBars > 0 && PA(i, d);
         for(int j = i - 1; j > MathMax(i - 40, 1); j--)   // swing high ล่าสุดก่อนจุดกวาด
            if(Hd(d, r[j]) > Hd(d, r[j - 1]) && Hd(d, r[j]) > Hd(d, r[j + 1]) && Hd(d, r[j]) > Cd(d, r[i]))
              {
               g_s[si].mss = Hd(d, r[j]);
               g_s[si].hasMss = true;
               break;
              }
         continue;
        }
      if(!g_s[si].hasExt || g_s[si].fired || !g_s[si].hasMss)
         continue;
      if((int)((r[i].time - g_s[si].extTime) / 60) > InpMaxMssMin)
         continue;
      if(InpSweepPaBars > 0 && (int)((r[i].time - g_s[si].extTime) / PeriodSeconds()) <= InpSweepPaBars && PA(i, d))
         g_s[si].cand = true;
      if(Cd(d, r[i]) <= g_s[si].mss)
         continue;
      if(InpRequireReclaim && Cd(d, r[i]) <= g_s[si].lv[g_s[si].lvl].price)
         continue;                               // ยังไม่ปิดกลับเหนือโซน: รอแท่งถัดไป
      if(InpMssVolMult > 0 && i >= 51)
        {
         double av = 0;
         for(int k = i - 50; k < i; k++)
            av += (double)r[k].tick_volume;
         av /= 50;
         if(av > 0 && (double)r[i].tick_volume <= InpMssVolMult * av)
           {
            g_status = "MSS แต่ volume ต่ำกว่าค่าเฉลี่ย";
            continue;                            // รอแท่งถัดไป
           }
        }
      g_s[si].fired = true;                      // แท่งปิดทะลุ swing = Market Structure Shift
      if(InpSweepPaBars > 0 && !g_s[si].cand)
         continue;                               // ไม่มีแท่งกลับตัวใกล้ปลายไส้
      TrySetup(g_s[si], i, endm);
     }
   Panel();
  }
//+------------------------------------------------------------------+
