//+------------------------------------------------------------------+
//| Export_M1_Volume.mq5  v1.10                                      |
//| ส่งออกแท่ง M1 ของกราฟที่เปิดอยู่ (tick volume + spread) เป็น CSV   |
//| แยกไฟล์ปีละ 1 ไฟล์ (ไฟล์เล็ก ส่งง่าย)                            |
//| ไฟล์อยู่ที่: File > Open Data Folder > MQL5 > Files               |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version "1.10"

input int InpFromYear = 2022;   // เริ่มปี
input int InpToYear   = 2026;   // ถึงปี

void OnStart()
  {
   PrintFormat("server GMT offset now = %+.1f h", (double)(TimeTradeServer() - TimeGMT()) / 3600.0);
   long grand = 0;
   MqlRates r[];
   for(int y = InpFromYear; y <= InpToYear; y++)
     {
      string fn = StringFormat("%s_M1_%d.csv", _Symbol, y);
      int fh = FileOpen(fn, FILE_WRITE | FILE_ANSI | FILE_TXT);
      if(fh == INVALID_HANDLE) { Print("เปิดไฟล์ไม่ได้ ", GetLastError()); return; }
      FileWriteString(fh, "time,open,high,low,close,vol,spread\n");   // time = yyyymmddHHMM (เวลาเซิร์ฟเวอร์)
      long total = 0;
      for(int m = 1; m <= 12; m++)
        {
         datetime a = StringToTime(StringFormat("%d.%02d.01 00:00", y, m));
         datetime b = StringToTime(StringFormat("%d.%02d.01 00:00", m == 12 ? y + 1 : y, m == 12 ? 1 : m + 1)) - 1;
         int n = -1;
         for(int k = 0; k < 20 && n < 0; k++) { n = CopyRates(_Symbol, PERIOD_M1, a, b, r); if(n < 0) Sleep(500); }
         for(int i = 0; i < n; i++)
           {
            MqlDateTime d; TimeToStruct(r[i].time, d);
            FileWriteString(fh, StringFormat("%04d%02d%02d%02d%02d,%.2f,%.2f,%.2f,%.2f,%I64d,%d\n", d.year, d.mon, d.day, d.hour, d.min,
                            r[i].open, r[i].high, r[i].low, r[i].close, r[i].tick_volume, r[i].spread));
           }
         if(n > 0) total += n;
         Comment("Export ", _Symbol, " ", y, "/", m, "  bars ", total);
        }
      FileClose(fh);
      if(total == 0) FileDelete(fn);
      PrintFormat("%d: %I64d แท่ง -> MQL5\\Files\\%s", y, total, fn);
      grand += total;
     }
   Comment("");
   PrintFormat("เสร็จ รวม %I64d แท่ง", grand);
  }
