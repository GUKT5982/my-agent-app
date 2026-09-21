# Form Field Mapper

ฟอร์มจริงของแต่ละบริษัทตั้งชื่อฟิลด์กันคนละแบบ (`qty1`, `Description 1`, `NET TOTAL`)
ซึ่ง `fill_pdf_form` จับคู่เองไม่ได้ เพราะมันเทียบจากชื่อที่ normalize แล้วเท่านั้น
หน้านี้ให้จับคู่ชื่อพวกนั้นกับค่าที่ระบบแกะได้ แล้ว export เป็น `form_mapping.json`

## วิธีใช้

```powershell
# 1. dump ชื่อฟิลด์จริงของฟอร์ม
python scripts/inspect_form_fields.py path/to/real_form.pdf
```

สคริปต์จะบอกทันทีว่าฟอร์มนี้มีกี่ฟิลด์ และ **โค้ดปัจจุบันจับคู่ได้เองกี่ฟิลด์** พร้อมเขียนไฟล์
`real_form.fields.json`

2. เปิด `static/field-mapper/index.html` (ดับเบิลคลิกได้เลย) แล้วลากไฟล์นั้นมาวาง
3. กด **รับคำแนะนำทั้งหมด** — หน้านี้เดาให้จากคำที่ใช้กันทั่วไป (`vendor`/`supplier` → `vendor_name`,
   `qty1` → `item_1_qty`) แล้วค่อยแก้ทีละตัวที่เดาผิด
4. ถ้าฟอร์มมีหลายแถวรายการ จับคู่แถวแรกให้ถูก แล้วกด **ใช้รูปแบบกับทุกแถว** — ระบบจะไล่แถวที่เหลือให้
5. กด **ดาวน์โหลด form_mapping.json**

## เอาไปใช้จริง

ส่ง path ของไฟล์เข้า context ตอนเรียก graph:

```json
{ "form_mapping_path": "config/form_mapping.json" }
```

`fill_form` จะอ่านไฟล์นี้ก่อน แล้วค่อย fallback ไปจับคู่ตามชื่อแบบเดิมสำหรับฟิลด์ที่ไม่ได้ระบุไว้
ถ้าไฟล์หายหรือพัง จะไม่ทำให้ทั้ง run ล้ม แต่จะขึ้นเป็น warning ใน `fill_warnings` แล้วกรอกแบบเดิมแทน

รูปแบบไฟล์:

```json
{
  "version": 1,
  "form": "real_form.pdf",
  "fields": {
    "Description 1": "item_1_desc",
    "qty1": "item_1_qty",
    "NET TOTAL": "grand_total"
  }
}
```

ชื่อทางซ้ายคือชื่อ widget ในฟอร์ม ทางขวาคือ key ที่ `quote_fields_to_form_values` ผลิตออกมา
(`vendor_name`, `quote_no`, `quote_date`, `buyer_name`, `subtotal`, `vat`, `grand_total`
และ `item_<n>_desc` / `_qty` / `_price` / `_amount`)

## หมายเหตุ

- การจับคู่ที่ทำค้างไว้ถูกจำใน `localStorage` ต่อหนึ่งฟอร์ม เปิดใหม่แล้วทำต่อได้
- ฟิลด์ที่ไม่ได้จับคู่จะไม่ถูกกรอก — ปล่อยว่างไว้ได้ถ้าเป็นช่องที่คนต้องเซ็นเอง เช่น `PreparedBy`
- section **ค่าที่ยังไม่มีที่ลง** บอกว่าข้อมูลตัวไหนที่ระบบแกะได้แต่ฟอร์มไม่มีช่องรองรับ
