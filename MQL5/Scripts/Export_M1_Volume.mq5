//+------------------------------------------------------------------+
//| Export_M1_Volume.mq5                                             |
//| ส่งออกแท่ง M1 ของกราฟที่เปิดอยู่ (พร้อม tick volume + spread) เป็น CSV |
//| ไฟล์จะอยู่ที่: File > Open Data Folder > MQL5 > Files             |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version "1.00"

input datetime InpFrom = D'2015.01.01';   // เริ่มวันที่
input datetime InpTo   = D'2030.01.01';   // ถึงวันที่ (เกินวันนี้ได้)

void OnStart()
  {
   string fn = _Symbol + "_M1_" + AccountInfoString(ACCOUNT_SERVER) + ".csv";
   int fh = FileOpen(fn, FILE_WRITE | FILE_ANSI | FILE_TXT);
   if(fh == INVALID_HANDLE) { Print("เปิดไฟล์ไม่ได้ ", GetLastError()); return; }
   FileWriteString(fh, "time,open,high,low,close,tick_volume,spread\n");
   int gmt = (int)(TimeTradeServer() - TimeGMT());
   PrintFormat("server GMT offset now = %+.1f h", gmt / 3600.0);
   long total = 0;
   MqlRates r[];
   // ทีละเดือน: CopyRates ก้อนใหญ่เกินจะล้ม
   for(datetime a = InpFrom; a < InpTo; a += 31 * 86400)
     {
      datetime b = MathMin(a + 31 * 86400, InpTo) - 1;
      int n = -1;
      for(int k = 0; k < 20 && n < 0; k++) { n = CopyRates(_Symbol, PERIOD_M1, a, b, r); if(n < 0) Sleep(500); }
      for(int i = 0; i < n; i++)
        {
         FileWriteString(fh, StringFormat("%s,%.*f,%.*f,%.*f,%.*f,%I64d,%d\n", TimeToString(r[i].time, TIME_DATE | TIME_MINUTES),
                         _Digits, r[i].open, _Digits, r[i].high, _Digits, r[i].low, _Digits, r[i].close, r[i].tick_volume, r[i].spread));
        }
      if(n > 0) total += n;
      Comment("Export ", _Symbol, " ", TimeToString(a, TIME_DATE), "  bars ", total);
     }
   FileClose(fh);
   Comment("");
   PrintFormat("เสร็จ: %I64d แท่ง -> MQL5\\Files\\%s", total, fn);
  }
