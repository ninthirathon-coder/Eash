# Project notes for Claude

## MCP servers (.mcp.json)
- **playwright** – ควบคุมเบราว์เซอร์ (คลิก กรอกฟอร์ม แคปหน้าจอ)
- **chrome-devtools** – ตรวจเว็บ: console, network, performance
- **firecrawl** – ดึงเนื้อหาเว็บเป็น markdown (ต้องมี `FIRECRAWL_API_KEY`)
- **perplexity** – ค้นเว็บแบบสด (ต้องมี `PERPLEXITY_API_KEY`)

API key อ่านจาก environment variable เท่านั้น ห้ามใส่ค่าจริงลงใน `.mcp.json` หรือไฟล์ใดๆ ที่ commit

## HyperFrames (ทำวิดีโอจาก HTML)
เป็น CLI ไม่ใช่ MCP — เรียกผ่าน `npx hyperframes`:
- `npx hyperframes init my-video` – สร้างโปรเจกต์วิดีโอ
- `npx hyperframes preview` – ดูตัวอย่าง
- `npx hyperframes lint ./my-video --json` – ตรวจ composition
- `npx hyperframes render -o output.mp4` – render เป็น MP4

`preview` รันค้างจนกด Ctrl+C ให้รันเป็น background process
