//+------------------------------------------------------------------+
//|                                         ICT_Wyckoff_Gold_EA.mq5  |
//|  ICT 2022 Mentorship Model + Wyckoff Spring/UTAD สำหรับ XAUUSD     |
//|                                                                  |
//|  ลำดับ: กวาดสภาพคล่องใน Kill Zone -> Displacement + MSS ทิ้ง FVG   |
//|        -> Limit ที่ FVG -> SL เลยจุดกวาด -> TP ที่สภาพคล่องฝั่งตรงข้าม |
//|                                                                  |
//|  ตรรกะเดียวกับ backtest/engine.py  สัญญาณคิดตอนแท่งปิดของ timeframe  |
//|  ที่แปะ EA (แนะนำ M5 ตามเอกสาร หรือ M1/M3 ถ้าต้องการ SL สั้น)         |
//|  ฝั่ง Sell ใช้ราคากลับเครื่องหมาย (p' = -p) จึงเขียนโค้ดฝั่ง Buy ชุดเดียว |
//+------------------------------------------------------------------+
#property version   "1.00"
#property description "ICT 2022 Model + Wyckoff Spring/UTAD (XAUUSD). ไม่ใช่คำแนะนำการลงทุน"

#include <Trade/Trade.mqh>

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

struct SLevel
  {
   double            price;   // ราคา' (กลับเครื่องหมายแล้วสำหรับฝั่ง Sell)
   int               tag;
   double            tp1;
   double            tp2;
   bool              swept;
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
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(30);
   g_s[0].d = 1;
   g_s[1].d = -1;
   ResetSide(g_s[0]);
   ResetSide(g_s[1]);
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
   if(trades >= InpMaxTradesDay || losses >= InpMaxLossesDay)
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
   if(InpTpFromRange)
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
      if(s.lv[s.lvl].tag == TAG_WYCK)
        {
         tp1 = s.lv[s.lvl].tp1;                     // กลางกรอบ
         tp2 = s.lv[s.lvl].tp2;                     // ขอบกรอบฝั่งตรงข้าม
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
   PlaceOrder(d, ent, sl, tp1, tp2, fvgLo, g_kzEnd + InpOrderGrace, tp1, s.lv[s.lvl].tag);
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
      g_dayOk = ComputeBias() && !IsNoTradeDate(day);
     }

   // ---------- จัดการตอนแท่งปิด ----------
   int newsA = NyMod(InpNewsStart), newsB = NyMod(InpNewsEnd);
   if(FindPosition() > 0)
     {
      if(InpEodExit >= 0 && endm >= NyMod(InpEodExit))
         ClosePosition();
      else if(g_dir != 0 && InpExitOnFvgFail && !g_be && Cd(g_dir, r[i]) < g_fvgLo)
         ClosePosition();                        // แท่งปิดสวนทะลุ FVG ที่ใช้เข้า
     }
   else if(FindPending() > 0)
     {
      if(g_dir == 0 || Cd(g_dir, r[i]) < g_fvgLo || endm >= g_expire || (endm >= newsA && endm < newsB))
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
