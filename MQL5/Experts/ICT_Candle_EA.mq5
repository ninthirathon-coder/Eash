//+------------------------------------------------------------------+
//|                                              ICT_Candle_EA.mq5   |
//|  EA เทรดตามเทคนิค ICT + ยืนยันด้วยการอ่านแท่งเทียน                 |
//|                                                                  |
//|  ลำดับการตัดสินใจ:                                                |
//|   1) HTF Bias      : โครงสร้างตลาด (BOS/CHoCH) บน TF ใหญ่          |
//|   2) Liquidity     : PDH/PDL, Asian High/Low, Swing High/Low      |
//|   3) Sweep         : ไส้แท่งกวาด liquidity แล้วปิดกลับเข้ามา         |
//|   4) Candlestick   : Pin bar / Engulfing / Morning-Evening Star   |
//|   5) MSS           : ปิดทะลุ swing ฝั่งตรงข้ามด้วยแท่ง displacement |
//|   6) FVG           : ตั้ง Limit ที่ FVG (ขอบ หรือ CE 50%)          |
//|   7) Premium/Disc. : ซื้อในโซน discount / ขายในโซน premium         |
//|   8) Kill Zone     : เข้าเฉพาะช่วง London / New York (เวลา NY)    |
//+------------------------------------------------------------------+
#property copyright   "Eash"
#property version     "1.00"
#property description "ICT: HTF bias + Liquidity sweep + MSS/Displacement + FVG + Candlestick confirmation"

#include <Trade/Trade.mqh>

//--- enums
enum ENUM_BIAS_MODE
  {
   BIAS_STRUCTURE         = 0, // โครงสร้างตลาด HTF
   BIAS_STRUCTURE_AND_EMA = 1, // โครงสร้าง + EMA ต้องตรงกัน
   BIAS_NONE              = 2  // ไม่ใช้ Bias (เทรดทั้งสองฝั่ง)
  };

enum ENUM_ENTRY_MODE
  {
   ENTRY_FVG_EDGE = 0, // Limit ที่ขอบ FVG
   ENTRY_FVG_CE   = 1, // Limit ที่ CE (กึ่งกลาง FVG)
   ENTRY_MARKET   = 2, // Market ทันทีเมื่อเกิด MSS
   ENTRY_FVG_PA   = 3  // รอราคาเทส FVG + แท่งเทียนปฏิเสธ แล้วเข้า Market
  };

enum ENUM_TP_MODE
  {
   TP_FIXED_RR           = 0, // RR คงที่
   TP_OPPOSITE_LIQUIDITY = 1  // liquidity ฝั่งตรงข้าม (ถ้า RR ไม่ถึงใช้ RR คงที่)
  };

enum ENUM_PD_MODE
  {
   PD_OFF = 0, // ไม่กรอง
   PD_LEG = 1, // ขาที่ displacement (sweep -> high/low ของขา)
   PD_HTF = 2  // Dealing range บน HTF
  };

//--- inputs
input group "=== ทั่วไป ==="
input long            InpMagic             = 20261110;   // Magic number
input ENUM_TIMEFRAMES InpEntryTF           = PERIOD_M5;  // TF เข้าเทรด (LTF)
input ENUM_TIMEFRAMES InpHTF               = PERIOD_H1;  // TF หา Bias (HTF)
input string          InpComment           = "ICT-EA";   // คอมเมนต์ออเดอร์
input int             InpATRPeriod         = 14;         // ATR period (TF เข้าเทรด)

input group "=== ความเสี่ยง ==="
input double          InpRiskPercent       = 1.0;        // ความเสี่ยงต่อไม้ (% ของ Equity)
input double          InpFixedLots         = 0.0;        // Lot คงที่ (>0 = ใช้แทน %Risk)
input ENUM_TP_MODE    InpTPMode            = TP_FIXED_RR;// วิธีตั้ง TP
input double          InpRR                = 2.0;        // RR คงที่
input double          InpMinRR             = 1.5;        // RR ขั้นต่ำที่ยอมเข้า
input double          InpSLBufferATR       = 0.10;       // ระยะเผื่อ SL หลังไส้ sweep (x ATR)
input double          InpMaxSLATR          = 3.0;        // SL กว้างสุด (x ATR) เกินนี้ไม่เข้า
input int             InpMaxSpreadPoints   = 40;         // Spread สูงสุด (points)
input int             InpMaxTradesPerDay   = 2;          // จำนวนไม้สูงสุด/วัน (0=ไม่จำกัด)
input double          InpMaxDailyLossPct   = 3.0;        // ขาดทุนสูงสุด/วัน % (0=ปิด)
input bool            InpOneTradeAtATime   = true;       // ถือได้ทีละ 1 ออเดอร์

input group "=== จัดการออเดอร์ ==="
input double          InpBE_R              = 1.0;        // เลื่อน SL กันทุนเมื่อได้กำไร (R) 0=ปิด
input double          InpBEPlusPoints      = 10;         // กันทุนบวกเพิ่ม (points)
input double          InpPartialPct        = 50;         // ปิดบางส่วนตอนกันทุน (%) 0=ไม่ปิด
input bool            InpStructureTrail    = true;       // เลื่อน SL ตาม swing หลังกันทุน
input int             InpPendingExpiryBars = 12;         // Limit หมดอายุหลังกี่แท่ง

input group "=== HTF Bias ==="
input ENUM_BIAS_MODE  InpBiasMode          = BIAS_STRUCTURE; // วิธีหา Bias
input int             InpHTFSwingStrength  = 3;          // ความแรง swing บน HTF (แท่งซ้าย/ขวา)
input int             InpHTFBars           = 300;        // จำนวนแท่ง HTF ที่ใช้วิเคราะห์
input int             InpHTFEMAPeriod      = 50;         // EMA period (โหมด Structure+EMA)
input bool            InpTradeWhenNeutral  = false;      // เทรดเมื่อ Bias เป็นกลาง

input group "=== Premium / Discount ==="
input ENUM_PD_MODE    InpPDMode            = PD_LEG;     // ตัวกรอง Premium/Discount
input int             InpPDRangeBars       = 30;         // จำนวนแท่ง HTF สำหรับ Dealing range (โหมด HTF)

input group "=== Liquidity / Sweep ==="
input bool            InpUsePDHL           = true;       // ใช้ Previous Day High/Low
input bool            InpUseAsianRange     = true;       // ใช้ Asian session High/Low
input bool            InpUseSwingLiquidity = true;       // ใช้ Swing High/Low บน LTF
input int             InpSwingStrength     = 3;          // ความแรง swing LTF (แท่งซ้าย/ขวา)
input int             InpSwingLookback     = 80;         // มองย้อนหา swing (แท่ง)
input int             InpSetupExpiryBars   = 20;         // setup หมดอายุถ้าไม่เกิด MSS ภายใน (แท่ง)

input group "=== Multi-TF Sweep (เบรค TF เล็ก -> เช็ค TF ใหญ่ขึ้น 1 ขั้น) ==="
input bool            InpMTFSweep          = true;        // ใช้ sweep หลาย TF (swing TF เล็ก ต้องถูกยืนยันด้วยแท่ง TF ใหญ่ขึ้น 1 ขั้น)
input ENUM_TIMEFRAMES InpMTF1              = PERIOD_M15;  // TF ขั้นที่ 1 (ยืนยัน swing ของ TF เข้าเทรด)
input ENUM_TIMEFRAMES InpMTF2              = PERIOD_H1;   // TF ขั้นที่ 2 (ยืนยัน swing ของขั้นที่ 1)
input ENUM_TIMEFRAMES InpMTF3              = PERIOD_H4;   // TF ขั้นที่ 3 (ยืนยัน swing ของขั้นที่ 2)

input group "=== MSS / Displacement / FVG ==="
input int             InpMSSStrength       = 2;          // ความแรง swing ที่ใช้เป็นระดับ MSS
input double          InpDisplacementATR   = 1.0;        // ตัวแท่ง displacement ขั้นต่ำ (x ATR)
input double          InpMinFVGATR         = 0.15;       // ขนาด FVG ขั้นต่ำ (x ATR)
input int             InpFVGWaitBars       = 3;          // รอ FVG หลัง MSS ได้กี่แท่ง
input ENUM_ENTRY_MODE InpEntryMode         = ENTRY_FVG_PA; // วิธีเข้า
input int             InpPAWaitBars        = 12;         // รอ PA ใน FVG ได้กี่แท่ง (โหมด FVG+PA)

input group "=== แท่งเทียนยืนยัน ==="
input bool            InpRequireCandle     = true;       // ต้องมีแท่งเทียนกลับตัวหลัง sweep
input bool            InpUsePinBar         = true;       // Pin bar / Hammer / Shooting star
input bool            InpUseEngulfing      = true;       // Engulfing
input bool            InpUseStar           = true;       // Morning / Evening star
input int             InpSweepPABars       = 2;          // PA ต้องเกิดภายในกี่แท่งหลัง sweep (0=เมื่อไรก็ได้ก่อน MSS)
input double          InpPinWickRatio      = 2.0;        // ไส้ต่อเนื้อเทียนขั้นต่ำของ Pin bar

input group "=== Kill Zones (เวลานิวยอร์ก) ==="
input int             InpServerMinusNY     = 7;          // เวลาเซิร์ฟเวอร์ - เวลา NY (ชม.) ส่วนใหญ่ = 7
input bool            InpLondonKZ          = true;       // London Kill Zone
input double          InpLondonStart       = 2.0;        // London เริ่ม (ชม. NY)
input double          InpLondonEnd         = 5.0;        // London จบ (ชม. NY)
input bool            InpNYKZ              = true;       // New York Kill Zone
input double          InpNYStart           = 7.0;        // NY เริ่ม (ชม. NY)
input double          InpNYEnd             = 10.0;       // NY จบ (ชม. NY)
input int             InpAsiaStartNY       = 20;         // Asian range เริ่ม (ชม. NY, วันก่อน)
input int             InpAsiaEndNY         = 0;          // Asian range จบ (ชม. NY)

input group "=== แสดงผล ==="
input bool            InpDraw              = true;       // วาด sweep / FVG บนกราฟ
input bool            InpShowPanel         = true;       // แสดงสถานะมุมซ้ายบน

//--- types
struct SSetup
  {
   bool     active;
   int      dir;        // +1 buy, -1 sell
   double   level;      // ระดับ liquidity ที่ถูกกวาด
   string   levelName;
   double   extreme;    // จุดสุดของไส้ sweep
   double   mssLevel;   // ระดับที่ต้องปิดทะลุเพื่อเป็น MSS
   bool     mssDone;
   bool     candleOk;
   datetime sweepTime;
   int      age;
   int      mssAge;
   double   legFav;     // high ของขาขึ้น (buy) / low ของขาลง (sell) นับจาก sweep
   bool     zoneArmed;  // โหมด FVG+PA: เจอ FVG แล้ว รอ PA
   double   zTop;
   double   zBot;
   int      zAge;
  };

//--- globals
CTrade   trade;
int      hATR      = INVALID_HANDLE;
int      hEMA      = INVALID_HANDLE;
datetime g_lastBar = 0;
MqlRates g_r[];
double   g_atr     = 0;
int      g_bias    = 0;
SSetup   g_setup[2];          // [0]=buy, [1]=sell
string   g_status  = "";
const string PFX   = "ICTEA_";
ulong    g_partialDone[];     // ticket ที่ปิดบางส่วนแล้ว (กันปิดซ้ำ)

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpEntryTF != PERIOD_CURRENT && InpHTF != PERIOD_CURRENT &&
      PeriodSeconds(InpHTF) <= PeriodSeconds(InpEntryTF))
      Print("คำเตือน: HTF ควรใหญ่กว่า TF เข้าเทรด");

   hATR = iATR(_Symbol, InpEntryTF, InpATRPeriod);
   hEMA = iMA(_Symbol, InpHTF, InpHTFEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hEMA == INVALID_HANDLE)
     {
      Print("สร้าง indicator ไม่สำเร็จ");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);

   ArraySetAsSeries(g_r, true);
   ResetSetup(g_setup[0]);
   ResetSetup(g_setup[1]);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hATR != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hEMA != INVALID_HANDLE) IndicatorRelease(hEMA);
   ObjectsDeleteAll(0, PFX);
   Comment("");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   ManageOpenPositions();

   datetime t = iTime(_Symbol, InpEntryTF, 0);
   if(t == 0 || t == g_lastBar)
      return;
   g_lastBar = t;
   OnNewBar();
  }

//+------------------------------------------------------------------+
void OnNewBar()
  {
   int need = MathMax(InpSwingLookback + 20, 400);
   if(CopyRates(_Symbol, InpEntryTF, 0, need, g_r) < 50)
      return;

   double a[];
   ArraySetAsSeries(a, true);
   if(CopyBuffer(hATR, 0, 1, 1, a) != 1 || a[0] <= 0)
      return;
   g_atr    = a[0];
   g_status = "";

   ManagePendingOrders();
   TrailByStructure();

   g_bias = GetHTFBias();

   // อัปเดต setup เดิมก่อน แล้วค่อยหา sweep ใหม่
   if(g_setup[0].active) UpdateSetup(g_setup[0]);
   if(g_setup[1].active) UpdateSetup(g_setup[1]);
   DetectSweep(+1);
   DetectSweep(-1);

   if(InpShowPanel)
      ShowPanel();
  }

//==================================================================//
//                         HTF BIAS                                  //
//==================================================================//
int GetHTFBias()
  {
   if(InpBiasMode == BIAS_NONE)
      return 0;

   MqlRates h[];
   ArraySetAsSeries(h, true);
   int n = CopyRates(_Symbol, InpHTF, 0, InpHTFBars, h);
   int s = InpHTFSwingStrength;
   if(n < 4 * s + 10)
      return 0;

   // เดินจากอดีตมาปัจจุบัน: swing ที่ยืนยันแล้ว + การปิดทะลุ (BOS/CHoCH) = เปลี่ยนเทรนด์
   int    trend = 0;
   double lastSH = 0, lastSL = 0;
   bool   shBroken = true, slBroken = true;
   for(int j = n - 1 - 2 * s; j >= 1; j--)
     {
      int k = j + s;
      if(IsSwingHigh(h, k, s)) { lastSH = h[k].high; shBroken = false; }
      if(IsSwingLow(h, k, s))  { lastSL = h[k].low;  slBroken = false; }
      if(!shBroken && h[j].close > lastSH) { trend = +1; shBroken = true; }
      if(!slBroken && h[j].close < lastSL) { trend = -1; slBroken = true; }
     }

   if(InpBiasMode == BIAS_STRUCTURE_AND_EMA && trend != 0)
     {
      double e[];
      ArraySetAsSeries(e, true);
      if(CopyBuffer(hEMA, 0, 1, 1, e) != 1)
         return 0;
      if(trend > 0 && h[1].close < e[0]) trend = 0;
      if(trend < 0 && h[1].close > e[0]) trend = 0;
     }
   return trend;
  }

bool BiasAllows(int dir)
  {
   if(InpBiasMode == BIAS_NONE) return true;
   if(g_bias == dir)            return true;
   if(g_bias == 0 && InpTradeWhenNeutral) return true;
   return false;
  }

//==================================================================//
//                    SWINGS / LIQUIDITY                             //
//==================================================================//
bool IsSwingHigh(const MqlRates &r[], int i, int s)
  {
   int n = ArraySize(r);
   if(i - s < 1 || i + s >= n) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].high >= r[i].high || r[i + k].high > r[i].high)
         return false;
   return true;
  }

bool IsSwingLow(const MqlRates &r[], int i, int s)
  {
   int n = ArraySize(r);
   if(i - s < 1 || i + s >= n) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].low <= r[i].low || r[i + k].low < r[i].low)
         return false;
   return true;
  }

// liquidity ยังไม่ถูกแตะ ตั้งแต่ shift lastShift ถึงแท่ง 2
bool IsFresh(double L, int lastShift, int dir)
  {
   int n = ArraySize(g_r);
   for(int k = 2; k <= lastShift && k < n; k++)
     {
      if(dir > 0 && g_r[k].low  < L) return false;
      if(dir < 0 && g_r[k].high > L) return false;
     }
   return true;
  }

void AddLevel(double &lv[], string &nm[], int &fs[], double price, string name, int fromShift)
  {
   if(price <= 0) return;
   int k = ArraySize(lv);
   ArrayResize(lv, k + 1);
   ArrayResize(nm, k + 1);
   ArrayResize(fs, k + 1);
   lv[k] = price;
   nm[k] = name;
   fs[k] = fromShift;
  }

bool GetAsianRange(double &hi, double &lo, int &lastShift)
  {
   long off   = (long)InpServerMinusNY * 3600;
   long ny    = (long)TimeCurrent() - off;
   long nyMid = ny - (ny % 86400);
   long endT  = nyMid + (long)InpAsiaEndNY * 3600;
   long stT   = nyMid + (long)InpAsiaStartNY * 3600;
   if(stT >= endT) stT -= 86400;
   if(ny < endT) return false;            // session ยังไม่จบ

   datetime sStart = (datetime)(stT + off);
   datetime sEnd   = (datetime)(endT + off);
   hi = -DBL_MAX; lo = DBL_MAX; lastShift = -1;
   int n = ArraySize(g_r);
   for(int i = 1; i < n; i++)
     {
      if(g_r[i].time >= sEnd)  continue;
      if(g_r[i].time < sStart) break;
      if(lastShift < 0) lastShift = i;
      hi = MathMax(hi, g_r[i].high);
      lo = MathMin(lo, g_r[i].low);
     }
   return (lastShift > 0 && hi > lo);
  }

// dir>0 => เก็บ sell-side liquidity (lows) ; dir<0 => buy-side liquidity (highs)
void CollectLiquidity(int dir, double &lv[], string &nm[], int &fs[])
  {
   ArrayResize(lv, 0); ArrayResize(nm, 0); ArrayResize(fs, 0);
   int n = ArraySize(g_r);

   if(InpUsePDHL)
     {
      datetime d0 = iTime(_Symbol, PERIOD_D1, 0);
      int fsDay   = iBarShift(_Symbol, InpEntryTF, d0, false);
      if(d0 > 0 && fsDay >= 1)
        {
         if(dir > 0) AddLevel(lv, nm, fs, iLow(_Symbol, PERIOD_D1, 1),  "PDL", fsDay);
         else        AddLevel(lv, nm, fs, iHigh(_Symbol, PERIOD_D1, 1), "PDH", fsDay);
        }
     }

   if(InpUseAsianRange)
     {
      double hi, lo; int ls;
      if(GetAsianRange(hi, lo, ls))
        {
         if(dir > 0) AddLevel(lv, nm, fs, lo, "Asian Low",  ls - 1);
         else        AddLevel(lv, nm, fs, hi, "Asian High", ls - 1);
        }
     }

   if(InpUseSwingLiquidity)
     {
      int s = InpSwingStrength;
      for(int i = s + 2; i <= InpSwingLookback && i < n - s; i++)
        {
         if(dir > 0 && IsSwingLow(g_r, i, s))  AddLevel(lv, nm, fs, g_r[i].low,  "Swing Low",  i - 1);
         if(dir < 0 && IsSwingHigh(g_r, i, s)) AddLevel(lv, nm, fs, g_r[i].high, "Swing High", i - 1);
        }
     }
  }

// ระดับ MSS = swing ฝั่งตรงข้ามล่าสุดก่อน sweep ที่ยังไม่ถูกปิดทะลุ
double FindMSSLevel(int dir, double closeRef, int startShift = 2)
  {
   int n = ArraySize(g_r);
   for(int i = startShift; i <= InpSwingLookback && i < n; i++)
     {
      if(dir > 0 && IsSwingHigh(g_r, i, InpMSSStrength) && g_r[i].high > closeRef) return g_r[i].high;
      if(dir < 0 && IsSwingLow(g_r, i, InpMSSStrength)  && g_r[i].low  < closeRef) return g_r[i].low;
     }
   // fallback: high/low สุดของ 5 แท่งก่อน sweep
   double v = (dir > 0) ? -DBL_MAX : DBL_MAX;
   for(int i = startShift; i <= startShift + 4 && i < n; i++)
      v = (dir > 0) ? MathMax(v, g_r[i].high) : MathMin(v, g_r[i].low);
   if(dir > 0 && v > closeRef) return v;
   if(dir < 0 && v < closeRef) return v;
   return 0;
  }

//==================================================================//
//                       CANDLESTICK PATTERNS                        //
//==================================================================//
bool IsPinBar(const MqlRates &r, int dir)
  {
   double rng = r.high - r.low;
   if(rng <= 0) return false;
   double body = MathAbs(r.close - r.open);
   double up   = r.high - MathMax(r.open, r.close);
   double dn   = MathMin(r.open, r.close) - r.low;
   double wick = (dir > 0) ? dn : up;
   double opp  = (dir > 0) ? up : dn;
   return (wick >= InpPinWickRatio * MathMax(body, rng * 0.1) && wick >= 0.55 * rng && opp <= 0.25 * rng);
  }

bool IsEngulfing(const MqlRates &c, const MqlRates &p, int dir)
  {
   double cb = dir * (c.close - c.open);   // แท่งปัจจุบันไปทาง dir
   double pb = dir * (p.open - p.close);   // แท่งก่อนหน้าสวนทาง dir
   if(cb <= 0 || pb <= 0) return false;
   if(dir > 0) return (c.close > p.open && c.open <= p.close);
   return (c.close < p.open && c.open >= p.close);
  }

// Morning star (dir>0) / Evening star (dir<0) ; i = แท่งที่ 3 (ล่าสุด)
bool IsStar(int i, int dir)
  {
   if(i + 2 >= ArraySize(g_r)) return false;
   MqlRates c1 = g_r[i + 2];
   MqlRates c2 = g_r[i + 1];
   MqlRates c3 = g_r[i];
   double r1 = c1.high - c1.low;
   double b1 = dir * (c1.open - c1.close);
   if(r1 <= 0 || b1 < 0.5 * r1) return false;
   double b2 = MathAbs(c2.close - c2.open);
   if(b2 > 0.3 * b1) return false;
   double b3 = dir * (c3.close - c3.open);
   if(b3 <= 0) return false;
   double mid = (c1.open + c1.close) / 2.0;
   return (dir > 0) ? (c3.close > mid) : (c3.close < mid);
  }

bool CandleSignal(int dir, int i)
  {
   if(i + 2 >= ArraySize(g_r)) return false;
   if(InpUsePinBar    && IsPinBar(g_r[i], dir))                return true;
   if(InpUseEngulfing && IsEngulfing(g_r[i], g_r[i + 1], dir)) return true;
   if(InpUseStar      && IsStar(i, dir))                       return true;
   return false;
  }

// แท่ง displacement: เนื้อเทียนใหญ่ (x ATR) และเนื้อ >= 50% ของแท่ง
bool HasDisplacement(int dir, datetime since)
  {
   for(int i = 1; i <= 3 && i < ArraySize(g_r); i++)
     {
      if(g_r[i].time < since) break;
      double body = dir * (g_r[i].close - g_r[i].open);
      double rng  = g_r[i].high - g_r[i].low;
      if(rng > 0 && body >= InpDisplacementATR * g_atr && body / rng >= 0.5)
         return true;
     }
   return false;
  }

//==================================================================//
//                           SETUP LOGIC                             //
//==================================================================//
void ResetSetup(SSetup &s)
  {
   s.active    = false;
   s.dir       = 0;
   s.level     = 0;
   s.levelName = "";
   s.extreme   = 0;
   s.mssLevel  = 0;
   s.mssDone   = false;
   s.candleOk  = false;
   s.sweepTime = 0;
   s.age       = 0;
   s.mssAge    = 0;
   s.legFav    = 0;
   s.zoneArmed = false;
   s.zTop      = 0;
   s.zBot      = 0;
   s.zAge      = 0;
  }

string TFName(ENUM_TIMEFRAMES tf)
  {
   string n = EnumToString(tf);
   return StringSubstr(n, 7);                       // "PERIOD_M15" -> "M15"
  }

bool IsSwingLowFrom(const MqlRates &r[], int i, int s, int minIdx)
  {
   if(i - s < minIdx || i + s >= ArraySize(r)) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].low <= r[i].low || r[i + k].low < r[i].low) return false;
   return true;
  }

bool IsSwingHighFrom(const MqlRates &r[], int i, int s, int minIdx)
  {
   if(i - s < minIdx || i + s >= ArraySize(r)) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].high >= r[i].high || r[i + k].high > r[i].high) return false;
   return true;
  }

// เช็คว่าแท่ง cfTF ที่เพิ่งปิด กวาด swing ของ lvTF แล้วปิดกลับหรือไม่
// cf[0] = แท่ง cfTF ที่เพิ่งปิด, cf[1] = แท่งก่อนหน้า
bool MTFSweep(ENUM_TIMEFRAMES lvTF, ENUM_TIMEFRAMES cfTF, int dir, double &level, MqlRates &cf[])
  {
   // แท่ง cfTF ที่มีแท่ง M5 ล่าสุดอยู่ ต้องปิดพอดีตอนนี้
   if(iTime(_Symbol, cfTF, 0) <= g_r[1].time) return false;
   ArraySetAsSeries(cf, true);
   if(CopyRates(_Symbol, cfTF, 1, 2, cf) != 2) return false;

   MqlRates lr[];
   ArraySetAsSeries(lr, true);
   int n = CopyRates(_Symbol, lvTF, 0, InpSwingLookback + 2 * InpSwingStrength + 50, lr);
   if(n < 20) return false;
   int kb = 0;                                      // แท่ง lvTF ล่าสุดที่จบก่อนแท่งยืนยันเริ่ม
   while(kb < n && lr[kb].time >= cf[0].time) kb++;
   if(kb >= n) return false;

   bool found = false;
   for(int q = kb + InpSwingStrength; q < n - InpSwingStrength && q <= kb + InpSwingLookback; q++)
     {
      double L;
      if(dir > 0)
        {
         if(!IsSwingLowFrom(lr, q, InpSwingStrength, kb)) continue;
         L = lr[q].low;
         if(!(cf[0].low < L && cf[0].close > L)) continue;
        }
      else
        {
         if(!IsSwingHighFrom(lr, q, InpSwingStrength, kb)) continue;
         L = lr[q].high;
         if(!(cf[0].high > L && cf[0].close < L)) continue;
        }
      bool fresh = true;
      for(int k = kb; k < q; k++)
         if((dir > 0 && lr[k].low < L) || (dir < 0 && lr[k].high > L)) { fresh = false; break; }
      if(!fresh) continue;
      if(!found || (dir > 0 ? L < level : L > level)) { level = L; found = true; }
     }
   return found;
  }

void DetectSweep(int dir)
  {
   int idx = (dir > 0) ? 0 : 1;
   if(g_setup[idx].active) return;
   if(!BiasAllows(dir))    return;

   MqlRates b = g_r[1];
   bool   found = false;
   double best  = 0;
   string bestName = "";
   int    extShift = 1;          // shift ของแท่ง M5 ที่เป็นจุดสุดของ sweep
   bool   htfCandle = false;     // แท่ง TF ใหญ่ที่ยืนยันเป็น PA เองหรือไม่

   if(!InpMTFSweep)
     {
      double lv[]; string nm[]; int fs[];
      CollectLiquidity(dir, lv, nm, fs);
      for(int j = 0; j < ArraySize(lv); j++)
        {
         double L = lv[j];
         bool swept = (dir > 0) ? (b.low < L && b.close > L) : (b.high > L && b.close < L);
         if(!swept) continue;
         if(!IsFresh(L, fs[j], dir)) continue;
         // เลือกระดับที่ลึกที่สุด (liquidity ใหญ่สุดที่ถูกกวาด)
         if(!found || (dir > 0 ? L < best : L > best))
           {
            found = true; best = L; bestName = nm[j];
           }
        }
     }
   else
     {
      // swing บน TF[k] นับเป็น sweep เมื่อแท่ง TF[k+1] ที่เพิ่งปิด แทงไส้ผ่านแล้ว "ปิดกลับ"
      // ถ้าแท่ง TF[k+1] ปิดทะลุ = TF เล็กเบรคจริง -> ระดับนั้นใช้ไม่ได้ ไปดู swing ของ TF[k+1] แทน
      ENUM_TIMEFRAMES chain[4];
      chain[0] = InpEntryTF; chain[1] = InpMTF1; chain[2] = InpMTF2; chain[3] = InpMTF3;
      for(int k = 0; k < 3; k++)
        {
         double L = 0; MqlRates cf[];
         if(!MTFSweep(chain[k], chain[k + 1], dir, L, cf)) continue;
         if(!found || (dir > 0 ? L < best : L > best))
           {
            found = true; best = L;
            bestName = "Swing " + TFName(chain[k]) + " (ยืนยัน " + TFName(chain[k + 1]) + ")";
            // หาแท่ง M5 ที่เป็นจุดสุดของไส้ภายในแท่ง TF ใหญ่
            extShift = 1;
            for(int i = 1; i < ArraySize(g_r) && g_r[i].time >= cf[0].time; i++)
               if((dir > 0 && g_r[i].low < g_r[extShift].low) || (dir < 0 && g_r[i].high > g_r[extShift].high))
                  extShift = i;
            htfCandle = IsPinBar(cf[0], dir) || IsEngulfing(cf[0], cf[1], dir);
           }
        }
     }
   if(!found) return;

   double mss = FindMSSLevel(dir, b.close, extShift + 1);
   if(mss == 0) return;

   SSetup s;
   ResetSetup(s);
   s.active    = true;
   s.dir       = dir;
   s.level     = best;
   s.levelName = bestName;
   s.extreme   = (dir > 0) ? g_r[extShift].low : g_r[extShift].high;
   s.mssLevel  = mss;
   s.sweepTime = g_r[extShift].time;
   s.legFav    = (dir > 0) ? -DBL_MAX : DBL_MAX;
   for(int i = 1; i <= extShift; i++)
      s.legFav = (dir > 0) ? MathMax(s.legFav, g_r[i].high) : MathMin(s.legFav, g_r[i].low);
   // PA ที่ sweep: แท่ง M5 ช่วงไส้ (ภายใน InpSweepPABars แท่ง) หรือแท่ง TF ใหญ่ที่ยืนยันเป็น pin/engulfing เอง
   s.candleOk  = htfCandle;
   int lastSh  = (InpSweepPABars <= 0) ? 1 : MathMax(1, extShift - InpSweepPABars);
   for(int i = extShift; i >= lastSh; i--)
      if(CandleSignal(dir, i)) s.candleOk = true;
   g_setup[idx] = s;

   DrawSweep(s);
   PrintFormat("[%s] Sweep %s @ %s | MSS level %s | candle=%s",
               dir > 0 ? "BUY" : "SELL", bestName, DoubleToString(best, _Digits),
               DoubleToString(mss, _Digits), s.candleOk ? "yes" : "no");
  }

void UpdateSetup(SSetup &s)
  {
   s.age++;
   if(s.age > InpSetupExpiryBars && !s.zoneArmed) { ResetSetup(s); return; }

   int dir    = s.dir;
   MqlRates b = g_r[1];

   if(!s.mssDone)
     {
      // ปิดเลยระดับที่ถูกกวาด = ไม่ใช่ sweep แต่เป็นการเบรคจริง -> ยกเลิก
      if((dir > 0 && b.close < s.level) || (dir < 0 && b.close > s.level))
        { ResetSetup(s); return; }

      if(dir > 0 && b.low  < s.extreme) s.extreme = b.low;
      if(dir < 0 && b.high > s.extreme) s.extreme = b.high;

      // PA กลับตัวต้องเกิดใกล้ sweep (แท่ง sweep เอง หรือภายใน InpSweepPABars แท่ง)
      int sinceSweep = iBarShift(_Symbol, InpEntryTF, s.sweepTime, false) - 1;
      if(CandleSignal(dir, 1) && (InpSweepPABars <= 0 || sinceSweep <= InpSweepPABars)) s.candleOk = true;

      bool broke = (dir > 0) ? (b.close > s.mssLevel) : (b.close < s.mssLevel);
      if(broke && HasDisplacement(dir, s.sweepTime))
        {
         if(InpRequireCandle && !s.candleOk)
           {
            Print("MSS เกิดแต่ไม่มีแท่งเทียนยืนยัน -> ข้าม setup");
            ResetSetup(s);
            return;
           }
         s.mssDone = true;
         s.mssAge  = 0;
         PrintFormat("[%s] MSS ยืนยันที่ %s", dir > 0 ? "BUY" : "SELL", DoubleToString(s.mssLevel, _Digits));
        }
     }
   else
     {
      s.mssAge++;
      // ราคากลับไปทำจุดสุดใหม่เลย sweep = setup เสีย
      if((dir > 0 && b.low < s.extreme) || (dir < 0 && b.high > s.extreme))
        { ResetSetup(s); return; }
     }

   if(dir > 0) s.legFav = MathMax(s.legFav, b.high);
   else        s.legFav = MathMin(s.legFav, b.low);

   if(s.mssDone)
     {
      if(InpEntryMode == ENTRY_FVG_PA && s.zoneArmed)
        {
         // รอราคาย่อกลับมาเทส FVG แล้วเกิดแท่งเทียนปฏิเสธ (PA) ก่อนเข้า
         s.zAge++;
         if(s.zAge > InpPAWaitBars) { ResetSetup(s); return; }
         if((dir > 0 && b.close < s.zBot) || (dir < 0 && b.close > s.zTop))
           { Print("ปิดทะลุ FVG -> ยกเลิก setup"); ResetSetup(s); return; }
         bool touched = (dir > 0) ? (b.low <= s.zTop) : (b.high >= s.zBot);
         if(!touched)              { g_status = "รอราคาเทส FVG"; return; }
         if(!CandleSignal(dir, 1)) { g_status = "เทส FVG แล้ว รอแท่งเทียนปฏิเสธ"; return; }
         TryEntry(s);
         return;
        }
      if(s.mssAge > InpFVGWaitBars) { ResetSetup(s); return; }
      TryEntry(s);
     }
  }

bool FindFVG(const SSetup &s, double &top, double &bot, datetime &t)
  {
   int dir = s.dir;
   int n   = ArraySize(g_r);
   for(int i = 1; i <= 6 && i + 2 < n; i++)
     {
      if(g_r[i + 1].time < s.sweepTime) break;     // FVG ต้องเกิดหลัง sweep
      double gTop, gBot;
      if(dir > 0)
        {
         if(g_r[i].low <= g_r[i + 2].high) continue;
         gTop = g_r[i].low;  gBot = g_r[i + 2].high;
        }
      else
        {
         if(g_r[i].high >= g_r[i + 2].low) continue;
         gTop = g_r[i + 2].low; gBot = g_r[i].high;
        }
      if(gTop - gBot < InpMinFVGATR * g_atr) continue;
      if(dir > 0 && gBot <= s.extreme) continue;
      if(dir < 0 && gTop >= s.extreme) continue;

      bool filled = false;                           // ถูกปิด gap ไปแล้วหรือยัง
      for(int k = 1; k < i; k++)
        {
         if(dir > 0 && g_r[k].low  <= gBot) filled = true;
         if(dir < 0 && g_r[k].high >= gTop) filled = true;
        }
      if(filled) continue;

      top = gTop; bot = gBot; t = g_r[i + 2].time;
      return true;
     }
   return false;
  }

void TryEntry(SSetup &s)
  {
   bool armOnly = (InpEntryMode == ENTRY_FVG_PA && !s.zoneArmed);   // แค่บันทึก FVG ยังไม่เข้า
   string why;
   if(!armOnly && !CanOpenNewTrade(why)) { g_status = why; return; }

   int    dir = s.dir;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double mkt = (dir > 0) ? ask : bid;

   double   top = 0, bot = 0;
   datetime fvgT = 0;
   bool     hasFVG;
   if(InpEntryMode == ENTRY_FVG_PA && s.zoneArmed)
     { top = s.zTop; bot = s.zBot; hasFVG = true; fvgT = s.sweepTime; }
   else
      hasFVG = FindFVG(s, top, bot, fvgT);

   double entry;
   if(InpEntryMode == ENTRY_MARKET)
      entry = mkt;
   else if(InpEntryMode == ENTRY_FVG_PA)
     {
      if(!hasFVG) return;
      entry = mkt;
     }
   else
     {
      if(!hasFVG) return;                            // รอ FVG แท่งถัดไป
      if(InpEntryMode == ENTRY_FVG_EDGE) entry = (dir > 0) ? top : bot;
      else                               entry = (top + bot) / 2.0;
     }

   // --- Premium / Discount
   if(InpPDMode == PD_LEG && InpEntryMode != ENTRY_MARKET)
     {
      // ให้เข้าเฉพาะส่วนของ FVG ที่อยู่ในโซน discount (buy) / premium (sell) ของขา displacement
      double eq = (s.extreme + s.legFav) / 2.0;
      if(dir > 0) { if(bot > eq) { g_status = "FVG อยู่ใน premium"; return; } if(InpEntryMode != ENTRY_FVG_PA) entry = MathMin(entry, eq); }
      else        { if(top < eq) { g_status = "FVG อยู่ใน discount"; return; } if(InpEntryMode != ENTRY_FVG_PA) entry = MathMax(entry, eq); }
     }
   else if(InpPDMode == PD_HTF)
     {
      double eq = HTFEquilibrium();
      if(eq > 0 && ((dir > 0 && entry > eq) || (dir < 0 && entry < eq)))
        { g_status = "ราคาอยู่ผิดโซน P/D (HTF)"; return; }
     }

   if(armOnly)
     {
      s.zoneArmed = true; s.zTop = top; s.zBot = bot; s.zAge = 0;
      DrawFVG(dir, fvgT, top, bot);
      g_status = "เจอ FVG แล้ว รอ PA";
      return;
     }

   double sl = s.extreme - dir * InpSLBufferATR * g_atr;

   // ถ้าราคาปัจจุบันอยู่ในโซนเข้าแล้ว -> เข้า market
   bool isMarket = (InpEntryMode == ENTRY_MARKET || InpEntryMode == ENTRY_FVG_PA) || (dir > 0 ? ask <= entry : bid >= entry);
   if(isMarket) entry = mkt;

   entry = NP(entry);
   sl    = NP(sl);
   double risk = dir * (entry - sl);
   if(risk <= 0) { ResetSetup(s); return; }
   if(risk > InpMaxSLATR * g_atr) { Print("SL กว้างเกิน -> ข้าม"); ResetSetup(s); return; }

   double stops = StopsDistance();
   if(risk <= stops) return;

   double tp = CalcTP(dir, entry, risk);
   if(dir * (tp - entry) / risk < InpMinRR - 1e-9) { g_status = "RR ไม่ถึง"; return; }
   tp = NP(tp);

   double lots = CalcLots(entry, sl);
   if(lots <= 0) { Print("คำนวณ lot ไม่ได้/ต่ำกว่าขั้นต่ำ"); ResetSetup(s); return; }

   string cmt = InpComment + " " + s.levelName;
   bool ok;
   if(isMarket)
      ok = (dir > 0) ? trade.Buy(lots, _Symbol, 0, sl, tp, cmt)
                     : trade.Sell(lots, _Symbol, 0, sl, tp, cmt);
   else
     {
      if(dir * (mkt - entry) <= stops) return;      // ใกล้ราคาเกินไปสำหรับ limit
      ok = (dir > 0) ? trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt)
                     : trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);
     }

   if(ok && (trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_PLACED))
     {
      PrintFormat("[%s] %s lots=%.2f entry=%s SL=%s TP=%s (sweep %s)",
                  dir > 0 ? "BUY" : "SELL", isMarket ? "MARKET" : "LIMIT", lots,
                  DoubleToString(entry, _Digits), DoubleToString(sl, _Digits),
                  DoubleToString(tp, _Digits), s.levelName);
      if(hasFVG) DrawFVG(dir, fvgT, top, bot);
      ResetSetup(s);
     }
   else
      PrintFormat("ส่งออเดอร์ไม่สำเร็จ: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }

double HTFEquilibrium()
  {
   int hi = iHighest(_Symbol, InpHTF, MODE_HIGH, InpPDRangeBars, 1);
   int lo = iLowest(_Symbol, InpHTF, MODE_LOW, InpPDRangeBars, 1);
   if(hi < 0 || lo < 0) return 0;
   return (iHigh(_Symbol, InpHTF, hi) + iLow(_Symbol, InpHTF, lo)) / 2.0;
  }

double CalcTP(int dir, double entry, double risk)
  {
   double fixedTP = entry + dir * InpRR * risk;
   if(InpTPMode == TP_FIXED_RR) return fixedTP;

   // หา liquidity ฝั่งตรงข้ามที่ใกล้ที่สุดที่ให้ RR >= ขั้นต่ำ
   double lv[]; string nm[]; int fs[];
   CollectLiquidity(-dir, lv, nm, fs);
   double best = 0;
   for(int j = 0; j < ArraySize(lv); j++)
     {
      double rr = dir * (lv[j] - entry) / risk;
      if(rr < InpMinRR) continue;
      if(best == 0 || dir * (lv[j] - best) < 0) best = lv[j];
     }
   return (best != 0) ? best : fixedTP;
  }

//==================================================================//
//                         RISK / FILTERS                            //
//==================================================================//
bool InKillZone()
  {
   if(!InpLondonKZ && !InpNYKZ) return true;
   datetime ny = (datetime)((long)TimeCurrent() - (long)InpServerMinusNY * 3600);
   MqlDateTime dt;
   TimeToStruct(ny, dt);
   double h = dt.hour + dt.min / 60.0;
   if(InpLondonKZ && h >= InpLondonStart && h < InpLondonEnd) return true;
   if(InpNYKZ     && h >= InpNYStart     && h < InpNYEnd)     return true;
   return false;
  }

bool HasExposure()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         return true;
     }
   return false;
  }

void GetTodayStats(int &trades, double &closedPL, double &floatingPL)
  {
   trades = 0; closedPL = 0; floatingPL = 0;
   datetime dayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(HistorySelect(dayStart, TimeCurrent() + 60))
     {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0) continue;
         if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol) continue;
         if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
         long entryType = HistoryDealGetInteger(d, DEAL_ENTRY);
         if(entryType == DEAL_ENTRY_IN) trades++;
         closedPL += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_COMMISSION);
        }
     }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         floatingPL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   // pending ที่รออยู่นับเป็นไม้ด้วย
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         trades++;
     }
  }

bool CanOpenNewTrade(string &why)
  {
   if(!InKillZone()) { why = "นอก Kill Zone"; return false; }

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints) { why = "Spread สูง"; return false; }

   if(InpOneTradeAtATime && HasExposure()) { why = "มีออเดอร์อยู่แล้ว"; return false; }

   int trades; double closedPL, floatPL;
   GetTodayStats(trades, closedPL, floatPL);
   if(InpMaxTradesPerDay > 0 && trades >= InpMaxTradesPerDay) { why = "ครบจำนวนไม้วันนี้"; return false; }

   if(InpMaxDailyLossPct > 0)
     {
      double startBal = AccountInfoDouble(ACCOUNT_BALANCE) - closedPL;
      if(startBal > 0 && (closedPL + floatPL) <= -InpMaxDailyLossPct / 100.0 * startBal)
        { why = "ถึงลิมิตขาดทุนรายวัน"; return false; }
     }
   why = "";
   return true;
  }

double NP(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

double StopsDistance()
  {
   long st = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long fr = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return (double)MathMax((double)st, (double)fr) * _Point;
  }

double NormalizeLots(double v)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   v = MathFloor(v / step + 1e-9) * step;
   if(v < vmin) return 0;
   if(v > vmax) v = vmax;
   int digits = (int)MathMax(0, MathCeil(-MathLog10(step) - 1e-9));
   return NormalizeDouble(v, digits);
  }

double CalcLots(double entry, double sl)
  {
   if(InpFixedLots > 0) return NormalizeLots(InpFixedLots);
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double dist      = MathAbs(entry - sl);
   if(dist <= 0 || tickSize <= 0 || tickValue <= 0) return 0;
   double lossPerLot = dist / tickSize * tickValue;
   return NormalizeLots(riskMoney / lossPerLot);
  }

//==================================================================//
//                       TRADE MANAGEMENT                            //
//==================================================================//
void ManageOpenPositions()
  {
   if(InpBE_R <= 0) return;
   double stops = StopsDistance();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double vol  = PositionGetDouble(POSITION_VOLUME);
      if(sl <= 0) continue;

      double risk = dir * (open - sl);              // > 0 = SL ยังอยู่ฝั่งขาดทุน
      if(risk <= 0) continue;                        // กันทุนไปแล้ว

      double price  = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profit = dir * (price - open);
      if(profit < InpBE_R * risk) continue;

      double newSL = NP(open + dir * InpBEPlusPoints * _Point);
      if(dir * (price - newSL) <= stops) continue;

      // ปิดบางส่วน (ครั้งเดียวต่อออเดอร์)
      if(InpPartialPct > 0 && !PartialDone(tk))
        {
         MarkPartial(tk);
         double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double cv   = NormalizeLots(vol * InpPartialPct / 100.0);
         if(cv >= vmin && vol - cv >= vmin - 1e-9)
            trade.PositionClosePartial(tk, cv);
        }

      if(PositionSelectByTicket(tk))
         trade.PositionModify(tk, newSL, tp);
     }
  }

bool PartialDone(ulong tk)
  {
   for(int i = 0; i < ArraySize(g_partialDone); i++)
      if(g_partialDone[i] == tk) return true;
   return false;
  }

void MarkPartial(ulong tk)
  {
   int n = ArraySize(g_partialDone);
   if(n > 200) { ArrayRemove(g_partialDone, 0, 100); n = ArraySize(g_partialDone); }
   ArrayResize(g_partialDone, n + 1);
   g_partialDone[n] = tk;
  }

void TrailByStructure()
  {
   if(!InpStructureTrail) return;
   double stops = StopsDistance();
   int    n     = ArraySize(g_r);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      if(sl <= 0 || dir * (sl - open) < 0) continue; // trail เฉพาะหลังกันทุนแล้ว

      double newSL = 0;
      for(int k = 2; k < InpSwingLookback && k < n; k++)
        {
         if(dir > 0 && IsSwingLow(g_r, k, InpSwingStrength))  { newSL = g_r[k].low  - InpSLBufferATR * g_atr; break; }
         if(dir < 0 && IsSwingHigh(g_r, k, InpSwingStrength)) { newSL = g_r[k].high + InpSLBufferATR * g_atr; break; }
        }
      if(newSL <= 0) continue;
      newSL = NP(newSL);

      double price = (dir > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(dir * (newSL - sl) > _Point && dir * (price - newSL) > stops)
         trade.PositionModify(tk, newSL, tp);
     }
  }

void ManagePendingOrders()
  {
   int maxAge = InpPendingExpiryBars * PeriodSeconds(InpEntryTF);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;

      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      long     type  = OrderGetInteger(ORDER_TYPE);
      double   tp    = OrderGetDouble(ORDER_TP);
      double   bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double   ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      bool expired = (InpPendingExpiryBars > 0 && TimeCurrent() - setup > maxAge);
      // ราคาวิ่งไปถึง TP ก่อนเข้า = พลาดแล้ว ยกเลิก
      bool ranAway = (tp > 0) && ((type == ORDER_TYPE_BUY_LIMIT && bid >= tp) || (type == ORDER_TYPE_SELL_LIMIT && ask <= tp));
      if(expired || ranAway)
         trade.OrderDelete(tk);
     }
  }

//==================================================================//
//                             DRAWING                               //
//==================================================================//
void DrawSweep(const SSetup &s)
  {
   if(!InpDraw) return;
   string nm = PFX + "sw_" + IntegerToString((long)s.sweepTime) + "_" + IntegerToString(s.dir);
   double p  = s.extreme;
   if(ObjectCreate(0, nm, s.dir > 0 ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, s.sweepTime, p))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, s.dir > 0 ? clrDodgerBlue : clrOrangeRed);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR, s.dir > 0 ? ANCHOR_TOP : ANCHOR_BOTTOM);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, "Sweep " + s.levelName);
     }
   string ln = nm + "_lvl";
   if(ObjectCreate(0, ln, OBJ_TREND, 0, s.sweepTime - 10 * PeriodSeconds(InpEntryTF), s.level, s.sweepTime, s.level))
     {
      ObjectSetInteger(0, ln, OBJPROP_COLOR, clrGold);
      ObjectSetInteger(0, ln, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, ln, OBJPROP_RAY_RIGHT, false);
      ObjectSetString(0, ln, OBJPROP_TOOLTIP, s.levelName);
     }
  }

void DrawFVG(int dir, datetime t, double top, double bot)
  {
   if(!InpDraw) return;
   string nm = PFX + "fvg_" + IntegerToString((long)t) + "_" + IntegerToString(dir);
   datetime t2 = t + 20 * PeriodSeconds(InpEntryTF);
   if(ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t, top, t2, bot))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, dir > 0 ? clrMediumSeaGreen : clrIndianRed);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, dir > 0 ? "Bullish FVG" : "Bearish FVG");
     }
  }

void ShowPanel()
  {
   string b = (g_bias > 0) ? "BULLISH" : (g_bias < 0) ? "BEARISH" : "NEUTRAL";
   string txt = "ICT Candle EA\n";
   txt += "HTF Bias (" + EnumToString(InpHTF) + "): " + b + "\n";
   txt += "Kill Zone: " + (InKillZone() ? "YES" : "no") + "\n";
   for(int i = 0; i < 2; i++)
     {
      SSetup s = g_setup[i];
      txt += (i == 0 ? "Buy setup : " : "Sell setup: ");
      if(!s.active) txt += "-\n";
      else
         txt += "sweep " + s.levelName + (s.zoneArmed ? " | รอ PA ใน FVG" : s.mssDone ? " | MSS OK" : " | รอ MSS") +
                (s.candleOk ? " | candle OK" : " | รอแท่งเทียน") + "\n";
     }
   if(g_status != "") txt += "สถานะ: " + g_status + "\n";
   Comment(txt);
  }
//+------------------------------------------------------------------+
