//+------------------------------------------------------------------+
//|                                             ICT_TopDown_EA.mq5   |
//|  Top-down ICT: โซน TF ใหญ่ -> ยืนยันการกลับตัวบน M1                |
//|                                                                  |
//|  1) โซน      : Swing H1 / Swing H4 ที่ยังไม่ถูกแตะ + PDH/PDL        |
//|  2) Sweep    : ราคา M1 แทงผ่านโซน (ลึกไม่เกิน 3 ATR M5)            |
//|  3) PA       : แท่งเทียนกลับตัวบน M1 ภายใน 3 แท่งจากจุดสุดของไส้     |
//|  4) MSS      : M1 ปิดกลับเหนือโซน + ทะลุ swing M1 ด้วย displacement |
//|  5) FVG + PA : รอราคาย่อเข้า FVG M1 แล้วเกิดแท่งปฏิเสธ -> Market     |
//|  6) SL       : พ้นโซน TF ใหญ่ 1.5 x ATR ของ TF โซน                 |
//|  7) TP       : swing ก่อนจุดกลับตัว บน TF ของโซน (ต้นขาที่ลงมากวาด) |
//|  8) จัดการ   : 1R -> ปิด 50% + กันทุน                              |
//|  ตรรกะเดียวกับ backtest/sim_m1.py                                  |
//+------------------------------------------------------------------+
#property copyright   "Eash"
#property version     "1.20"
#property description "ICT top-down: HTF zones (H1/H4 swings, PDH/PDL) confirmed on M1; SL beyond the HTF zone; TP at the swing before the reversal"

#include <Trade/Trade.mqh>

enum ENUM_TD_BIAS
  {
   TD_BIAS_NONE = 0, // ไม่ใช้ (ค่าที่ backtest)
   TD_BIAS_H1   = 1, // ตามโครงสร้าง H1
   TD_BIAS_H4   = 2, // ตามโครงสร้าง H4
   TD_BIAS_BOTH = 3  // H1 และ H4 ต้องตรงกัน
  };

enum ENUM_TD_TP
  {
   TD_TP_SWING = 0, // swing ก่อนจุดกลับตัว (ICT)
   TD_TP_RR    = 1  // RR คงที่
  };

input group "=== ทั่วไป ==="
input long            InpMagic            = 20261111;   // Magic number
input string          InpComment          = "ICT-TD";   // คอมเมนต์ออเดอร์

input group "=== ความเสี่ยง ==="
input double          InpRiskPercent      = 1.0;        // ความเสี่ยงต่อไม้ (% Equity)
input double          InpFixedLots        = 0.0;        // Lot คงที่ (>0 = ใช้แทน %Risk)
input int             InpMaxTradesPerDay  = 2;          // ไม้สูงสุดต่อวัน
input double          InpMaxDailyLossPct  = 3.0;        // ขาดทุนสูงสุดต่อวัน % (0=ปิด)
input int             InpMaxSpreadPoints  = 60;         // spread สูงสุด (points)

input group "=== โซน TF ใหญ่ ==="
input bool            InpUseH1Zones       = true;       // Swing H1
input bool            InpUseH4Zones       = true;       // Swing H4
input bool            InpUsePDZones       = true;       // PDH / PDL
input int             InpZoneSwingStrength = 3;         // ความแรง swing ของโซน (แท่งซ้าย/ขวา)
input ENUM_TD_BIAS    InpBias             = TD_BIAS_NONE; // ตัวกรองเทรนด์
input int             InpServerMinusNY    = 7;          // เวลาเซิร์ฟเวอร์ - เวลา NY (ชม.)

input group "=== ยืนยันบน M1 ==="
input double          InpMaxDepthATR5     = 3.0;        // ไส้แทงเลยโซนได้ไม่เกิน (x ATR M5) ไม่งั้น = เบรคจริง
input int             InpSetupExpiryM1    = 30;         // ต้องเกิด MSS ภายในกี่แท่ง M1
input int             InpSweepPABars      = 3;          // PA กลับตัวต้องเกิดภายในกี่แท่งจากจุดสุดของไส้ (0=ไม่บังคับ)
input int             InpMSSStrength      = 2;          // ความแรง swing M1 ที่ใช้เป็นระดับ MSS
input double          InpDisplacementATR1 = 1.0;        // เนื้อแท่ง displacement ขั้นต่ำ (x ATR M1)
input double          InpMinFVGATR1       = 0.3;        // ขนาด FVG ขั้นต่ำ (x ATR M1)
input int             InpFVGWaitM1        = 5;          // รอ FVG หลัง MSS ได้กี่แท่ง
input int             InpPAWaitM1         = 10;         // รอ PA ใน FVG ได้กี่แท่ง (backtest: สั้นกว่า = ดีกว่า)
input bool            InpUsePinBar        = true;       // PA: Pin bar
input bool            InpUseEngulfing     = true;       // PA: Engulfing
input bool            InpUseStar          = true;       // PA: Morning / Evening star
input double          InpPinWickRatio     = 2.0;        // ไส้/เนื้อ ขั้นต่ำของ Pin bar

input group "=== SL / TP ==="
input double          InpSLZoneATR        = 1.5;        // SL พ้นโซน (x ATR ของ TF โซน)
input double          InpSLBufATR1        = 0.5;        // ระยะเผื่อหลังไส้ M1 (x ATR M1) ใช้ถ้าไส้ลึกกว่าโซน
input double          InpMaxM1SLATR5      = 3.0;        // คัด setup: SL ตามโครงสร้าง M1 ต้องไม่เกิน (x ATR M5)
input double          InpMaxSpreadToSL    = 0.2;        // คัด setup: spread / SL โครงสร้าง M1 ไม่เกิน
input ENUM_TD_TP      InpTPMode           = TD_TP_SWING;// วิธีตั้ง TP
input int             InpTPSwingStrength  = 2;          // ความแรง swing ที่ใช้เป็น TP
input double          InpMinRR            = 0.8;        // RR ขั้นต่ำ
input double          InpFixedRR          = 2.0;        // RR (โหมด RR คงที่)

input group "=== จัดการออเดอร์ ==="
input bool            InpUseTP2           = true;       // TP1 = swing (ปิดบางส่วน+กันทุน), TP2 = ขอบ dealing range
input double          InpTP1ClosePct      = 50;         // ปิดที่ TP1 กี่ %
input double          InpBE_R             = 1.0;        // (เมื่อไม่ใช้ TP2) ถึงกี่ R แล้วกันทุน 0=ปิด
input double          InpPartialPct       = 50;         // ปิดบางส่วนตอนกันทุน (%)
input int             InpBEPlusPoints     = 10;         // กันทุนบวก (points) ทอง 2 ทศนิยม: 10 = $0.10

input group "=== Kill Zones (เวลา NY) ==="
input bool            InpLondonKZ         = true;       // London 02:00-05:00
input bool            InpNYKZ             = true;       // New York 07:00-10:00
input double          InpLondonStart      = 2.0;
input double          InpLondonEnd        = 5.0;
input double          InpNYStart          = 7.0;
input double          InpNYEnd            = 10.0;
input bool            InpSkipMonday       = true;       // ไม่เทรดวันจันทร์ (เวลา NY)

input group "=== แสดงผล ==="
input bool            InpDraw             = true;       // วาด sweep / FVG
input bool            InpShowPanel        = true;       // แสดงสถานะ

//--- types
struct SZone
  {
   double   price;
   int      tf;       // 1=H1 2=H4 3=PDH/PDL
   datetime formed;
  };

struct STD
  {
   bool     active;
   int      dir;
   double   level;
   int      tf;
   double   ext;
   datetime extT;
   int      age;
   int      phase;     // 0 รอ MSS, 1 รอ FVG, 2 รอ PA ใน FVG
   double   mss;
   int      mAge;
   double   zT, zB;
   int      zAge;
   bool     cand;
   datetime formed;   // เวลาที่โซนเกิด (ใช้หาขอบ dealing range สำหรับ TP2)
  };

//--- globals
CTrade   trade;
int      hA1 = INVALID_HANDLE, hA5 = INVALID_HANDLE, hAH1 = INVALID_HANDLE, hAH4 = INVALID_HANDLE;
MqlRates g_r[];                 // M1 series
datetime g_lastM1 = 0, g_lastH1 = 0, g_lastH4 = 0, g_lastD1 = 0;
SZone    g_lows[], g_highs[];
STD      g_s[2];                // 0 buy, 1 sell
double   g_a1, g_a5, g_aH1, g_aH4;
string   g_status = "";
const string PFX = "ICTTD_";
const int ZCAP = 64;

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| EA นี้เทรดเฉพาะทองคำ (XAUUSD / GOLD) เท่านั้น                         |
//+------------------------------------------------------------------+
bool IsGoldSymbol()
  {
   string s = _Symbol;
   StringToUpper(s);
   return (StringFind(s, "XAU") >= 0 || StringFind(s, "GOLD") >= 0);
  }

int OnInit()
  {
   if(!IsGoldSymbol())
     {
      Alert(MQLInfoString(MQL_PROGRAM_NAME), ": เทรดเฉพาะทองคำ (XAUUSD/GOLD) - ไม่ทำงานบน ", _Symbol);
      return(INIT_FAILED);
     }
   hA1  = iATR(_Symbol, PERIOD_M1, 14);
   hA5  = iATR(_Symbol, PERIOD_M5, 14);
   hAH1 = iATR(_Symbol, PERIOD_H1, 14);
   hAH4 = iATR(_Symbol, PERIOD_H4, 14);
   if(hA1 == INVALID_HANDLE || hA5 == INVALID_HANDLE || hAH1 == INVALID_HANDLE || hAH4 == INVALID_HANDLE)
      return(INIT_FAILED);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   trade.SetTypeFillingBySymbol(_Symbol);
   ArraySetAsSeries(g_r, true);
   ArrayResize(g_lows, 0);
   ArrayResize(g_highs, 0);
   Reset(g_s[0]);
   Reset(g_s[1]);
   g_lastH1 = iTime(_Symbol, PERIOD_H1, 0);
   g_lastH4 = iTime(_Symbol, PERIOD_H4, 0);
   g_lastD1 = 0;                                   // ใส่ PDH/PDL ทันทีที่เริ่ม
   SeedZones();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   IndicatorRelease(hA1); IndicatorRelease(hA5); IndicatorRelease(hAH1); IndicatorRelease(hAH4);
   ObjectsDeleteAll(0, PFX);
   Comment("");
  }

void OnTick()
  {
   ManagePositions();
   datetime t = iTime(_Symbol, PERIOD_M1, 0);
   if(t == 0 || t == g_lastM1) return;
   g_lastM1 = t;
   OnNewM1();
  }

//==================================================================//
//                            helpers                               //
//==================================================================//
double Buf(int h, int shift)
  {
   double b[];
   if(CopyBuffer(h, 0, shift, 1, b) != 1) return 0;
   return b[0];
  }

int Sh(datetime t) { return iBarShift(_Symbol, PERIOD_M1, t, false); }

double NP(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

// swing บนอาร์เรย์ series: ใหม่กว่า (i-k) ต้องต่ำกว่า/สูงกว่าแบบ strict, เก่ากว่า (i+k) ห้ามเกิน
bool SwHi(const MqlRates &r[], int i, int s, int minIdx)
  {
   if(i - s < minIdx || i + s >= ArraySize(r)) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].high >= r[i].high || r[i + k].high > r[i].high) return false;
   return true;
  }

bool SwLo(const MqlRates &r[], int i, int s, int minIdx)
  {
   if(i - s < minIdx || i + s >= ArraySize(r)) return false;
   for(int k = 1; k <= s; k++)
      if(r[i - k].low <= r[i].low || r[i + k].low < r[i].low) return false;
   return true;
  }

bool IsPin(const MqlRates &b, int d)
  {
   double rng = b.high - b.low;
   if(rng <= 0) return false;
   double body = MathAbs(b.close - b.open);
   double up = b.high - MathMax(b.open, b.close), dn = MathMin(b.open, b.close) - b.low;
   double wick = d > 0 ? dn : up, opp = d > 0 ? up : dn;
   return wick >= InpPinWickRatio * MathMax(body, rng * 0.1) && wick >= 0.55 * rng && opp <= 0.25 * rng;
  }

bool IsEngulf(const MqlRates &c, const MqlRates &p, int d)
  {
   double cb = d * (c.close - c.open), pb = d * (p.open - p.close);
   if(cb <= 0 || pb <= 0) return false;
   if(d > 0) return c.close > p.open && c.open <= p.close;
   return c.close < p.open && c.open >= p.close;
  }

bool IsStar(const MqlRates &r[], int i, int d)
  {
   if(i + 2 >= ArraySize(r)) return false;
   MqlRates c1 = r[i + 2];
   MqlRates c2 = r[i + 1];
   MqlRates c3 = r[i];
   double r1 = c1.high - c1.low, b1 = d * (c1.open - c1.close);
   if(r1 <= 0 || b1 < 0.5 * r1) return false;
   if(MathAbs(c2.close - c2.open) > 0.3 * b1) return false;
   if(d * (c3.close - c3.open) <= 0) return false;
   double mid = (c1.open + c1.close) / 2.0;
   return d > 0 ? c3.close > mid : c3.close < mid;
  }

bool PA(const MqlRates &r[], int i, int d)
  {
   if(i + 2 >= ArraySize(r)) return false;
   if(InpUsePinBar    && IsPin(r[i], d))              return true;
   if(InpUseEngulfing && IsEngulf(r[i], r[i + 1], d)) return true;
   if(InpUseStar      && IsStar(r, i, d))             return true;
   return false;
  }

void Reset(STD &s)
  {
   s.active = false; s.dir = 0; s.level = 0; s.tf = 0; s.ext = 0; s.extT = 0; s.age = 0; s.phase = 0;
   s.mss = 0; s.mAge = 0; s.zT = 0; s.zB = 0; s.zAge = 0; s.cand = false; s.formed = 0;
  }

string TFName(int tf) { return tf == 1 ? "H1" : tf == 2 ? "H4" : "PDH/PDL"; }

//==================================================================//
//                       zones (TF ใหญ่)                             //
//==================================================================//
void PushZone(SZone &arr[], double price, int tf, datetime formed)
  {
   int n = ArraySize(arr);
   if(n >= ZCAP) { ArrayRemove(arr, 0, 1); n--; }
   ArrayResize(arr, n + 1);
   arr[n].price = price; arr[n].tf = tf; arr[n].formed = formed;
  }

// ตอนเริ่ม EA: เติม swing H1/H4 ที่ยังไม่ถูกแตะจากประวัติ
void SeedZones()
  {
   ENUM_TIMEFRAMES tfs[2] = {PERIOD_H1, PERIOD_H4};
   for(int t = 0; t < 2; t++)
     {
      if((t == 0 && !InpUseH1Zones) || (t == 1 && !InpUseH4Zones)) continue;
      MqlRates r[];
      ArraySetAsSeries(r, true);
      int n = CopyRates(_Symbol, tfs[t], 1, 300, r);
      int s = InpZoneSwingStrength;
      for(int i = n - 1 - s; i >= s; i--)              // เก่า -> ใหม่
        {
         if(SwLo(r, i, s, 0))
           {
            bool fresh = true;
            for(int k = i - 1; k >= 0; k--) if(r[k].low < r[i].low) { fresh = false; break; }
            if(fresh) PushZone(g_lows, r[i].low, t + 1, r[i].time);
           }
         if(SwHi(r, i, s, 0))
           {
            bool fresh = true;
            for(int k = i - 1; k >= 0; k--) if(r[k].high > r[i].high) { fresh = false; break; }
            if(fresh) PushZone(g_highs, r[i].high, t + 1, r[i].time);
           }
        }
     }
  }

void AddHTFSwing(ENUM_TIMEFRAMES tf, int tag)
  {
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int s = InpZoneSwingStrength;
   if(CopyRates(_Symbol, tf, 1, 2 * s + 2, r) < 2 * s + 1) return;
   int k = s;                                       // shift (s+1) บนกราฟ = index s ในอาร์เรย์นี้
   if(SwLo(r, k, s, 0) && !(g_r[1].low < r[k].low))   PushZone(g_lows,  r[k].low,  tag, r[k].time);
   if(SwHi(r, k, s, 0) && !(g_r[1].high > r[k].high)) PushZone(g_highs, r[k].high, tag, r[k].time);
  }

void UpdateZones()
  {
   datetime d0 = iTime(_Symbol, PERIOD_D1, 0);
   if(InpUsePDZones && d0 != g_lastD1)
     {
      g_lastD1 = d0;
      PushZone(g_lows,  iLow(_Symbol, PERIOD_D1, 1),  3, iTime(_Symbol, PERIOD_D1, 1));
      PushZone(g_highs, iHigh(_Symbol, PERIOD_D1, 1), 3, iTime(_Symbol, PERIOD_D1, 1));
     }
   datetime h1 = iTime(_Symbol, PERIOD_H1, 0);
   if(h1 != g_lastH1) { g_lastH1 = h1; if(InpUseH1Zones) AddHTFSwing(PERIOD_H1, 1); }
   datetime h4 = iTime(_Symbol, PERIOD_H4, 0);
   if(h4 != g_lastH4) { g_lastH4 = h4; if(InpUseH4Zones) AddHTFSwing(PERIOD_H4, 2); }
  }

// โซนที่ถูกแทงในแท่ง M1 ล่าสุด -> ลบออก และคืนโซนที่ลึกที่สุด
bool TakeZones(SZone &arr[], int d, SZone &best)
  {
   bool found = false;
   for(int i = ArraySize(arr) - 1; i >= 0; i--)
     {
      bool hit = d > 0 ? g_r[1].low < arr[i].price : g_r[1].high > arr[i].price;
      if(!hit) continue;
      if(!found || (d > 0 ? arr[i].price < best.price : arr[i].price > best.price) ||
         (arr[i].price == best.price && arr[i].tf > best.tf))
        { best = arr[i]; found = true; }
      ArrayRemove(arr, i, 1);
     }
   return found;
  }

//==================================================================//
//                         bias (optional)                           //
//==================================================================//
int StructTrend(ENUM_TIMEFRAMES tf)
  {
   MqlRates h[];
   ArraySetAsSeries(h, true);
   int n = CopyRates(_Symbol, tf, 0, 300, h), s = 3;
   if(n < 4 * s + 10) return 0;
   int trend = 0; double sh = 0, sl = 0; bool shB = true, slB = true;
   for(int j = n - 1 - 2 * s; j >= 1; j--)
     {
      int k = j + s;
      if(SwHi(h, k, s, 1)) { sh = h[k].high; shB = false; }
      if(SwLo(h, k, s, 1)) { sl = h[k].low;  slB = false; }
      if(!shB && h[j].close > sh) { trend = 1;  shB = true; }
      if(!slB && h[j].close < sl) { trend = -1; slB = true; }
     }
   return trend;
  }

bool BiasOK(int d)
  {
   if(InpBias == TD_BIAS_NONE) return true;
   if((InpBias == TD_BIAS_H1 || InpBias == TD_BIAS_BOTH) && StructTrend(PERIOD_H1) != d) return false;
   if((InpBias == TD_BIAS_H4 || InpBias == TD_BIAS_BOTH) && StructTrend(PERIOD_H4) != d) return false;
   return true;
  }

//==================================================================//
//                          main loop                                //
//==================================================================//
void OnNewM1()
  {
   if(CopyRates(_Symbol, PERIOD_M1, 0, 400, g_r) < 200) return;
   g_a1 = Buf(hA1, 1); g_a5 = Buf(hA5, 1); g_aH1 = Buf(hAH1, 1); g_aH4 = Buf(hAH4, 1);
   if(g_a1 <= 0 || g_a5 <= 0 || g_aH1 <= 0 || g_aH4 <= 0) return;
   g_status = "";

   UpdateZones();

   // โซนที่ถูกแทง -> setup ใหม่
   for(int sd = 0; sd < 2; sd++)
     {
      int d = sd == 0 ? 1 : -1;
      SZone z;
      bool hit = (sd == 0) ? TakeZones(g_lows, d, z) : TakeZones(g_highs, d, z);
      if(!hit || g_s[sd].active) continue;
      if(!BiasOK(d)) continue;
      STD s; Reset(s);
      s.active = true; s.dir = d; s.level = z.price; s.tf = z.tf; s.formed = z.formed;
      s.ext = d > 0 ? g_r[1].low : g_r[1].high; s.extT = g_r[1].time; s.age = -1;
      g_s[sd] = s;
      DrawSweep(s);
     }

   for(int sd = 0; sd < 2; sd++)
      if(g_s[sd].active) Progress(g_s[sd]);

   if(InpShowPanel) Panel();
  }

void Progress(STD &s)
  {
   int d = s.dir;
   MqlRates b = g_r[1];
   s.age++;

   if(s.phase == 0)
     {
      if(s.age > InpSetupExpiryM1) { Reset(s); return; }
      if((d > 0 && b.low < s.ext) || (d < 0 && b.high > s.ext)) { s.ext = d > 0 ? b.low : b.high; s.extT = b.time; s.mss = 0; }
      if(d * (s.level - s.ext) > InpMaxDepthATR5 * g_a5) { Reset(s); return; }   // ลึกเกิน = เบรคจริง
      int es = Sh(s.extT);
      if(PA(g_r, 1, d) && (InpSweepPABars <= 0 || es - 1 <= InpSweepPABars)) s.cand = true;
      if(s.mss == 0)
        {
         for(int j = es + 1; j <= es + 119 && j < ArraySize(g_r); j++)
           {
            if(d > 0 && SwHi(g_r, j, InpMSSStrength, 1) && g_r[j].high > s.level) { s.mss = g_r[j].high; break; }
            if(d < 0 && SwLo(g_r, j, InpMSSStrength, 1) && g_r[j].low  < s.level) { s.mss = g_r[j].low;  break; }
           }
         if(s.mss == 0) return;
        }
      bool reclaimed = d > 0 ? b.close > s.level : b.close < s.level;
      bool broke     = d > 0 ? b.close > s.mss   : b.close < s.mss;
      if(!(reclaimed && broke)) return;
      bool disp = false;
      for(int i = 1; i <= 3; i++)
        {
         if(i > es) break;
         double body = d * (g_r[i].close - g_r[i].open), rng = g_r[i].high - g_r[i].low;
         if(rng > 0 && body >= InpDisplacementATR1 * g_a1 && body / rng >= 0.5) { disp = true; break; }
        }
      if(!disp) return;
      if(InpSweepPABars > 0 && !s.cand) { Reset(s); return; }
      s.phase = 1; s.mAge = 0;
      return;
     }

   if(s.phase == 1)
     {
      s.mAge++;
      if(s.mAge > InpFVGWaitM1) { Reset(s); return; }
      if((d > 0 && b.low < s.ext) || (d < 0 && b.high > s.ext)) { Reset(s); return; }
      int es = Sh(s.extT);
      for(int i = 1; i <= 6; i++)
        {
         if(i + 1 > es) break;
         double gT, gB;
         if(d > 0) { if(g_r[i].low <= g_r[i + 2].high) continue; gT = g_r[i].low; gB = g_r[i + 2].high; }
         else      { if(g_r[i].high >= g_r[i + 2].low) continue; gT = g_r[i + 2].low; gB = g_r[i].high; }
         if(gT - gB < InpMinFVGATR1 * g_a1) continue;
         if((d > 0 && gB <= s.ext) || (d < 0 && gT >= s.ext)) continue;
         bool filled = false;
         for(int k = 1; k < i; k++)
            if((d > 0 && g_r[k].low <= gB) || (d < 0 && g_r[k].high >= gT)) filled = true;
         if(filled) continue;
         s.phase = 2; s.zT = gT; s.zB = gB; s.zAge = 0;
         DrawFVG(d, g_r[i + 2].time, gT, gB);
         break;
        }
      return;
     }

   // phase 2: รอ PA ใน FVG
   s.zAge++;
   if(s.zAge > InpPAWaitM1) { Reset(s); return; }
   if((d > 0 && (b.close < s.zB || b.low < s.ext)) || (d < 0 && (b.close > s.zT || b.high > s.ext))) { Reset(s); return; }
   bool touched = d > 0 ? b.low <= s.zT : b.high >= s.zB;
   if(!touched || !PA(g_r, 1, d)) { g_status = "รอ PA ใน FVG"; return; }
   int res = Enter(s);
   if(res != 0) Reset(s);
  }

//==================================================================//
//                             entry                                 //
//==================================================================//
bool InKZ()
  {
   if(!InpLondonKZ && !InpNYKZ) return true;
   MqlDateTime dt;
   TimeToStruct((datetime)((long)TimeCurrent() - (long)InpServerMinusNY * 3600), dt);
   double h = dt.hour + dt.min / 60.0;
   if(InpLondonKZ && h >= InpLondonStart && h < InpLondonEnd) return true;
   if(InpNYKZ && h >= InpNYStart && h < InpNYEnd) return true;
   return false;
  }

bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) return true;
     }
   return false;
  }

void TodayStats(int &trades, double &pl)
  {
   trades = 0; pl = 0;
   if(!HistorySelect(iTime(_Symbol, PERIOD_D1, 0), TimeCurrent() + 60)) return;
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong dl = HistoryDealGetTicket(i);
      if(dl == 0 || HistoryDealGetString(dl, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(dl, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetInteger(dl, DEAL_ENTRY) == DEAL_ENTRY_IN) trades++;
      pl += HistoryDealGetDouble(dl, DEAL_PROFIT) + HistoryDealGetDouble(dl, DEAL_SWAP) + HistoryDealGetDouble(dl, DEAL_COMMISSION);
     }
  }

double CalcLots(double dist)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double v = InpFixedLots;
   if(v <= 0)
     {
      double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(ts <= 0 || tv <= 0 || dist <= 0) return 0;
      v = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0 / (dist / ts * tv);
     }
   if(step <= 0) step = 0.01;
   v = MathFloor(v / step + 1e-9) * step;
   if(v < vmin) return 0;
   return NormalizeDouble(MathMin(v, vmax), (int)MathMax(0, MathCeil(-MathLog10(step) - 1e-9)));
  }

// TP แบบ ICT: swing ล่าสุดก่อนจุดกลับตัว บน TF ของโซน (PDH/PDL ใช้ H1)
double SwingTarget(const STD &s, double entry, double spread)
  {
   ENUM_TIMEFRAMES tf = (s.tf == 2) ? PERIOD_H4 : PERIOD_H1;
   int gS = iBarShift(_Symbol, tf, s.extT, false);     // แท่ง TF ใหญ่ที่มีจุดสุดของไส้
   if(gS < 0) return 0;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, tf, gS, 305, r);           // r[0] = แท่งที่มีจุดสุดของไส้
   int ts = InpTPSwingStrength;
   for(int k = 1; k < n - ts && k <= 300; k++)
     {
      if(s.dir > 0 && SwHi(r, k, ts, 0) && r[k].high > entry)          return r[k].high;
      if(s.dir < 0 && SwLo(r, k, ts, 0) && r[k].low + spread < entry)  return r[k].low + spread;
     }
   return 0;
  }

// ขอบ dealing range: สูงสุด (Buy) / ต่ำสุด (Sell) ตั้งแต่โซนเกิดจนถึงจุดสุดของไส้
double RangeEdge(const STD &s, double spread)
  {
   int d = s.dir;
   double ex = d > 0 ? -DBL_MAX : DBL_MAX;
   int hFrom = iBarShift(_Symbol, PERIOD_H1, s.formed, false);
   int hTo   = iBarShift(_Symbol, PERIOD_H1, s.extT, false);
   if(hFrom < 0 || hTo < 0) return 0;
   if(hFrom > hTo)                                   // แท่ง H1 ที่จบก่อนแท่งที่มีจุดสุดของไส้
     {
      int cnt = hFrom - hTo;
      int k = d > 0 ? iHighest(_Symbol, PERIOD_H1, MODE_HIGH, cnt, hTo + 1) : iLowest(_Symbol, PERIOD_H1, MODE_LOW, cnt, hTo + 1);
      if(k >= 0) ex = d > 0 ? iHigh(_Symbol, PERIOD_H1, k) : iLow(_Symbol, PERIOD_H1, k);
     }
   datetime hs = (datetime)MathMax((long)iTime(_Symbol, PERIOD_H1, hTo), (long)s.formed);   // ส่วนที่เหลือดูบน M1 ถึงจุดสุดของไส้
   int mFrom = iBarShift(_Symbol, PERIOD_M1, hs, false), mTo = Sh(s.extT);
   if(mFrom >= mTo && mTo >= 0)
     {
      int cnt = mFrom - mTo + 1;
      int k = d > 0 ? iHighest(_Symbol, PERIOD_M1, MODE_HIGH, cnt, mTo) : iLowest(_Symbol, PERIOD_M1, MODE_LOW, cnt, mTo);
      if(k >= 0)
        {
         double v = d > 0 ? iHigh(_Symbol, PERIOD_M1, k) : iLow(_Symbol, PERIOD_M1, k);
         ex = d > 0 ? MathMax(ex, v) : MathMin(ex, v);
        }
     }
   if(ex == DBL_MAX || ex == -DBL_MAX) return 0;
   return d > 0 ? ex : ex + spread;
  }

// 0 = ยังเข้าไม่ได้ (รอ), 1 = เข้าแล้ว, -1 = ยกเลิก setup
int Enter(STD &s)
  {
   if(InpSkipMonday)
     {
      MqlDateTime ny;
      TimeToStruct((datetime)((long)TimeCurrent() - (long)InpServerMinusNY * 3600), ny);
      if(ny.day_of_week == 1) { g_status = "วันจันทร์: ไม่เทรด"; return -1; }
     }
   if(!InKZ())      { g_status = "PA เกิดนอก Kill Zone"; return 0; }
   if(HasPosition()) { g_status = "มีออเดอร์อยู่แล้ว"; return 0; }
   long spPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(InpMaxSpreadPoints > 0 && spPts > InpMaxSpreadPoints) { g_status = "spread สูง"; return 0; }
   int trades; double pl;
   TodayStats(trades, pl);
   if(InpMaxTradesPerDay > 0 && trades >= InpMaxTradesPerDay) { g_status = "ครบไม้วันนี้"; return 0; }
   if(InpMaxDailyLossPct > 0)
     {
      double startBal = AccountInfoDouble(ACCOUNT_BALANCE) - pl;
      if(startBal > 0 && pl <= -InpMaxDailyLossPct / 100.0 * startBal) { g_status = "ถึงลิมิตขาดทุนวันนี้"; return 0; }
     }

   int d = s.dir;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   double entry = d > 0 ? ask : bid;

   // คัด setup ด้วย SL ตามโครงสร้าง M1
   double slM1 = s.ext - d * InpSLBufATR1 * g_a1;
   double r1 = d * (entry - slM1);
   if(r1 <= 0 || r1 > InpMaxM1SLATR5 * g_a5 || spread / r1 > InpMaxSpreadToSL) return -1;

   // SL จริง: พ้นโซน TF ใหญ่ (หรือหลังไส้ ถ้าไส้ลึกกว่า)
   double az = (s.tf == 1) ? g_aH1 : g_aH4;
   double sl = s.level - d * InpSLZoneATR * az;
   if(d * (slM1 - sl) < 0) sl = slM1;
   double risk = d * (entry - sl);
   if(risk <= 0) return -1;

   double tp;
   if(InpTPMode == TD_TP_SWING)
     {
      tp = SwingTarget(s, entry, spread);
      if(tp == 0) return -1;
     }
   else tp = entry + d * InpFixedRR * risk;
   if(d * (tp - entry) / risk < InpMinRR) return -1;

   // TP1 / TP2: เป้าแรก = swing (ปิดบางส่วน + กันทุน), เป้าสุดท้าย = ขอบ dealing range ถ้าไกลกว่า
   double tp1 = tp;
   string tag = "";
   if(InpUseTP2)
     {
      double tp2 = RangeEdge(s, spread);
      if(tp2 != 0 && d * (tp2 - tp1) > 0) { tp = tp2; tag = "|T1=" + DoubleToString(NP(tp1), _Digits); }
      else tag = "|NB";                               // ไม่มีเป้าที่สอง: ถือถึง TP ไม่กันทุน (ตาม backtest)
     }

   double lots = CalcLots(risk);
   if(lots <= 0) return -1;
   sl = NP(sl); tp = NP(tp);
   string cmt = InpComment + tag;
   bool ok = d > 0 ? trade.Buy(lots, _Symbol, 0, sl, tp, cmt) : trade.Sell(lots, _Symbol, 0, sl, tp, cmt);
   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
     {
      PrintFormat("[%s] zone %s %.2f | lots %.2f entry %.2f SL %.2f TP1 %.2f TP %.2f RR1 %.2f",
                  d > 0 ? "BUY" : "SELL", TFName(s.tf), s.level, lots, entry, sl, tp1, tp, d * (tp1 - entry) / risk);
      return 1;
     }
   PrintFormat("ส่งออเดอร์ไม่สำเร็จ %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   return 0;
  }

//==================================================================//
//                        position management                        //
//==================================================================//
// อ่าน TP1 จากคอมเมนต์ออเดอร์ ("...|T1=2034.55") ; -1 = ไม่กันทุน ("|NB") ; 0 = ไม่มีข้อมูล (ใช้กฎ 1R)
double ParseTP1(string cmt)
  {
   if(StringFind(cmt, "|NB") >= 0) return -1;
   int p = StringFind(cmt, "|T1=");
   if(p < 0) return 0;
   return StringToDouble(StringSubstr(cmt, p + 4));
  }

void ManagePositions()
  {
   long stLvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double stops = (double)stLvl * _Point;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      int d = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP), vol = PositionGetDouble(POSITION_VOLUME);
      if(sl <= 0) continue;
      double risk = d * (open - sl);
      if(risk <= 0) continue;                                     // กันทุนแล้ว
      double px = d > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double tp1 = ParseTP1(PositionGetString(POSITION_COMMENT));
      double closePct = InpPartialPct;
      if(tp1 < 0) continue;                                       // ไม่มี TP2: ถือถึง TP
      if(tp1 > 0)
        {
         if(d * (px - tp1) < 0) continue;                          // ยังไม่ถึง TP1
         closePct = InpTP1ClosePct;
        }
      else
        {
         if(InpBE_R <= 0 || d * (px - open) < InpBE_R * risk) continue;
        }
      double newSL = NP(open + d * InpBEPlusPoints * _Point);
      if(d * (px - newSL) <= stops) continue;
      // เลื่อน SL กันทุนก่อน -> สำเร็จแล้วค่อยปิดบางส่วน
      // (ถ้าเลื่อน SL ไม่สำเร็จ จะไม่ปิดบางส่วน และลองใหม่ tick ถัดไป จึงไม่มีการปิดซ้ำ)
      if(!trade.PositionModify(tk, newSL, tp) || trade.ResultRetcode() != TRADE_RETCODE_DONE)
        {
         PrintFormat("เลื่อน SL กันทุนไม่สำเร็จ #%I64u: %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         continue;
        }
      if(closePct > 0)
        {
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         if(step <= 0) step = 0.01;
         double cv = MathFloor(vol * closePct / 100.0 / step + 1e-9) * step;
         if(cv >= vmin && vol - cv >= vmin - 1e-9)
           {
            cv = NormalizeDouble(cv, (int)MathMax(0, MathCeil(-MathLog10(step) - 1e-9)));
            if(!trade.PositionClosePartial(tk, cv))
               PrintFormat("ปิดบางส่วนไม่สำเร็จ #%I64u: %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
           }
        }
     }
  }

//==================================================================//
//                              drawing                              //
//==================================================================//
void DrawSweep(const STD &s)
  {
   if(!InpDraw) return;
   string nm = PFX + "sw" + IntegerToString((long)s.extT) + "_" + IntegerToString(s.dir);
   if(ObjectCreate(0, nm, OBJ_TREND, 0, s.extT - 30 * 60, s.level, s.extT + 5 * 60, s.level))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, clrGold);
      ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, nm, OBJPROP_WIDTH, 2);
      ObjectSetString(0, nm, OBJPROP_TOOLTIP, "Zone " + TFName(s.tf));
     }
  }

void DrawFVG(int d, datetime t, double top, double bot)
  {
   if(!InpDraw) return;
   string nm = PFX + "fvg" + IntegerToString((long)t) + "_" + IntegerToString(d);
   if(ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t, top, t + 20 * 60, bot))
     {
      ObjectSetInteger(0, nm, OBJPROP_COLOR, d > 0 ? clrMediumSeaGreen : clrIndianRed);
      ObjectSetInteger(0, nm, OBJPROP_FILL, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, true);
     }
  }

void Panel()
  {
   string ph[3] = {"รอ MSS", "รอ FVG", "รอ PA ใน FVG"};
   string txt = "ICT Top-down EA\n";
   txt += "โซนที่รอ: low " + IntegerToString(ArraySize(g_lows)) + " | high " + IntegerToString(ArraySize(g_highs)) + "\n";
   txt += "Kill Zone: " + (InKZ() ? "YES" : "no") + "\n";
   for(int i = 0; i < 2; i++)
     {
      txt += i == 0 ? "Buy : " : "Sell: ";
      txt += g_s[i].active ? ("โซน " + TFName(g_s[i].tf) + " " + DoubleToString(g_s[i].level, _Digits) + " | " + ph[g_s[i].phase]) : "-";
      txt += "\n";
     }
   if(g_status != "") txt += "สถานะ: " + g_status;
   Comment(txt);
  }
//+------------------------------------------------------------------+
