# Backend Biznes Mantiqlari va To'liq Funksional Spetsifikatsiyasi
(Backend Business Logic & Complete Functional Specification)

Ushbu hujjat **mandarin_foto_hisobot** tizimining backend qismidagi barcha operatsiyalar, matematik hisob-kitoblar, ma'lumotlar oqimi, xavfsizlik va integratsiya mantiqlarining to'liq va o'zgarmas qo'llanmasidir.

---

## 1. Domain Strukturasi va Ierarxiya

Tizim yuklar monitoringi va hisob-kitobini quyidagi 4 bosqichli ierarxiya asosida yuritadi:

```
[Kargo (Konteyner/Partiya)]  Masalan: KARGO-01, KARGO-02
         │
         ▼
[Reys (Transport safari)]   Masalan: REYS-42, REYS-43
         │
         ▼
[Tovar turi (Mahsulot)]     14 ta standart tur (akb, triton, mandarin, ...)
         │
         ▼
[Karobka (Tarozi yozuvi)]    Shtrix-kod (boxCode), Og'irlik, Karobka og'irligi, Rasmlar
```

---

## 2. Vazn Terminologiyasi va Hisob-kitob Formulalari

Tizimda og'irliklar quyidagi qat'iy standart asosida hisoblanadi:

1. **Og'irlik (Gross weight, $W$):** Tarozida ko'rsatilgan umumiy vazn (mahsulot + quti).
2. **Karobka og'irligi (Tare weight, $T$):** Bo'sh qutining o'z og'irligi (koeffitsient).
   - `none`: Karobka og'irligi ayirilmaydi ($T = 0$).
   - `fixed`: Oldindan belgilangan standart koeffitsient (masalan: `0.94`, `1.22`, `1.4`, `1.0`).
   - `custom`: Operator tomonidan qo'lda kiritilgan maxsus og'irlik (tasdiqlash modali orqali so'raladi).
3. **Toza vazn (Net weight, $N$):** Mahsulotning sof og'irligi:
   $$N = \max(0, W - T)$$
   Agar $T > W$ bo'lsa, xatolik qaytariladi (`400 Bad Request: koeffitsient og'irlikdan katta`).

---

## 3. Asosiy Operatsion Oqimlar (Workflows)

### A. Reys Hisoboti va Ombor Balansi (Inventory)
- Har bir saqlangan karobka yozuvi bo'yicha toza vazn ($N$) tegishli `(report_id, tovar_turi)` bo'yicha ombor qoldig'iga qo'shiladi:
  $$\text{Inventory}(t) \leftarrow \text{Inventory}(t) + N$$
- Har bir yozuv `activity` jadvaliga yoziladi.
- Operator yozuvni tahrirlasa (`edit_reys`) yoki o'chirsa (`delete_entry`), eski va yangi vaznlar orasidagi farq ($\Delta$) hisoblanib, ombor qoldig'i avtomatik to'g'rilanadi:
  $$\text{Inventory}(t) \leftarrow \text{Inventory}(t) - N_{\text{eski}} + N_{\text{yangi}}$$
- Agar o'chirish yoki tahrirlash natijasida ombor balansi manfiyga tushib ketadigan bo'lsa, tranzaksiya bekor qilinadi va `409 InsufficientStock` xatosi qaytariladi.

### B. Adashgan Yuklar (Adjustment / Transfer)
- Bir tovar turidan boshqa tovar turiga og'irlik ko'chirish:
  - Manba tovar turi ($T_{\text{from}}$) qoldig'i tekshiriladi: $\text{Inventory}(T_{\text{from}}) \ge W_{\text{adjust}}$ bo'lishi shart.
  - Manbadan ayiriladi: $\text{Inventory}(T_{\text{from}}) \leftarrow \text{Inventory}(T_{\text{from}}) - W_{\text{adjust}}$
  - Qabul qiluvchiga qo'shiladi: $\text{Inventory}(T_{\text{to}}) \leftarrow \text{Inventory}(T_{\text{to}}) + W_{\text{adjust}}$
  - Agar manbada yetarli vazn bo'lmasa, `409 InsufficientStock` beriladi.
  - Tahrirlanganda (`edit_adjust`) eski ko'chirish to'liq bekor qilinib, yangi qiymat qo'llanadi.

### C. Obshiy Ves Oqimi
Umumiy tortish 4 ta mustaqil bo'limga ega:
1. **Top (`action = 'top'`):**
   - Karobka kodi majburiy (`code_required = true`).
   - Karobka og'irligi koeffitsienti kiritilishi mumkin, lekin sof vazn doimo umumiy og'irlikka teng saqlanadi ($N = W$).
   - `POST /api/reports/{id}/zero-top-coefficients`: Top yozuvlaridagi barcha koeffitsientlarni 0 qilib, sof vaznni umumiy vaznga to'liq tenglashtirish funksiyasi.
2. **Topdan chiqgan (`action = 'topchiqgan'`):** Kod ixtiyoriy, vazn kiritiladi.
3. **Bizda qoladigan (`action = 'bizda'`):** Kod ixtiyoriy, vazn kiritiladi.
4. **Bizdan chiqgan (`action = 'chiqgan'`):** Kod ixtiyoriy, vazn kiritiladi.

### D. Kargolar va Reyslar Savatchasi (Recycle Bin & 30-Day Retention)
- **Kargo o'chirilganda (ADR-003):**
  - Kargo konteyneri savatchaga o'tadi (`deleted_at = now`).
  - Kargo ichidagi barcha reyslar va kiritilgan yozuvlar arxivlanadi/nollanadi.
  - Kargo tiklanganda barcha reyslar va ularning sof vaznlari asl holiga qaytadi.
- **Reys o'chirilganda:**
  - Kargo ichidagi aynan shu 1 ta reys savatchaga o'tadi.
- **30 kunlik qoida:**
  - O'chirilgan barcha kargo va reyslar savatchada 30 kun saqlanadi (`daysRemaining = 30 - (now - deleted_at)`).
  - Admin istalgan paytda "Tiklash" (Restore) yoki "Butunlay o'chirish" (Hard Delete) qilishi mumkin.
  - 30 kundan oshgan o'chirilgan yozuvlar avtomatik tozalanadi.

---

## 4. Multi-Photo va Tezkor Rejim (Fast Mode)

1. **Bir nechta rasm saqlash (Multi-Photo):**
   - 1 ta karobka uchun 1 tadan 10 tagacha rasm olish mumkin (`MAX_PHOTOS = 10`, har biri 12 MB gacha).
   - Rasmlar indeks bo'yicha saqlanadi (`idx: 0, 1, 2...`).
   - Saqlash usuli: Cloudflare R2 buluti (`storage_backend = 'r2'`) yoki lokal disk (`data/photos/<entry_id>/<idx>`) va SQLite BLOB fallback.
2. **Tezkor Rejim (Fast Mode):**
   - Rasm olingandan so'ng darhol kursor `Karobka kodi` maydoniga avtomatik fokuslanadi.
   - Saqlash tugmasi bosilgandan keyin yangi karobka uchun avtomatik kamera ochiladi yoki fokus koddagi holatda qoladi.

---

## 5. Telegram Integratsiyasi va Outbox Pattern

Xabarlarni Telegramga uzluksiz va ishonchli yetkazish:
- **5 ta mustaqil Telegram kanali:**
  1. `BOT_KARGOLARGA_TARQATISH_CHANNEL_ID`: Reyslar va adashgan yuklar uchun.
  2. `BOT_TOP_TYPE_CHANNEL_ID`: "Top" bo'limi uchun.
  3. `BOT_TOPDAN_CHIQGAN_CHANNEL_ID`: "Topdan chiqgan" uchun.
  4. `BOT_BIZDA_QOLADIGAN_CHANNEL_ID`: "Bizda qoladigan" uchun.
  5. `BOT_BIZDAN_CHIQGAN_CHANNEL_ID`: "Bizdan chiqgan" uchun.
- **Outbox Navbati (`send_queue`):**
  - Har bir saqlangan yozuv navbatga qo'yiladi (`status = 'pending'`).
  - Fon rejimida ishlaydigan `outbox.worker()` navbatni o'qiydi.
  - 1 ta rasm bo'lsa: `bot.send_photo`.
  - Bir nechta rasm bo'lsa: `bot.send_media_group`.
  - Har bir yuborilgan rasmning Telegramdagi `file_id` si bazada saqlanadi (qayta yuklamasdan Telegram CDN orqali tezkor yuborish uchun).
  - Xatolik bo'lsa, eksponentsial kechikish bilan qayta urinadi: `[5, 15, 30, 60, 120, 300, 600, 900]` sek.
- **Ommaviy yuborish (`POST /api/send-bulk`):**
  - "Yuborilmaganlarni yuborish" (`mode = 'unsent'`).
  - "Yuborilganlarni qayta yuborish" (`mode = 'sent'`).
  - "Tanlanganlarni yuborish" (`entry_ids = [...]`).

---

## 6. Excel Eksport Mantiqi

`assets/` papkasidagi shablonlar asosida `openpyxl` kutubxonasi orqali shakllantiriladi:
1. **Kargolarga tarqatish (`shablon.xlsx`):** Har bir tovar turi bo'yicha alohida ustunlarga `=18.5-0.5` kabi formulalarni joylaydi va avtomatik yig'indi hisoblaydi.
2. **Obshiy ves (`obshiy_ves_shablon.xlsx`):** Top, Topdan chiqgan, Bizda qoladigan, Bizdan chiqgan bo'limlarini alohida jadvallarga jamlaydi.
3. **Umumiy hisobot (`umumiy_hisobot_shabloni.xlsx`):** Barcha bo'limlarning umumiy xulosaviy balansi.
4. **Sana bo'yicha eksport:** Bugun, Kecha, 1 haftalik, 1 oylik va erkin tanlangan sana oralig'i (`startDate` - `endDate`) bo'yicha filtrlash.

---

## 7. Autentifikatsiya va Xavfsizlik

1. **Telegram Mini App:**
   - So'rovdagi `initData` bot tokeni asosida HMAC-SHA256 orqali tekshiriladi.
   - Foydalanuvchi `ADMIN_IDS` ro'yxatida bo'lishi shart.
2. **Standalone Brauzer:**
   - Admin login va 4 xonali PIN parol: `ADMIN_CREDENTIALS` (PBKDF2-HMAC-SHA256, 200,000 iteratsiya).
   - Muvaffaqiyatli kirilganda `reys_session` nomli xavfsiz cookie beriladi (`httpOnly`, `Secure`, `SameSite=Strict`).
   - WebAuthn (Passkeys): FIDO2 barmoq izi / FaceID orqali biometrik parolsiz kirish.
3. **Xavfsizlik choralari:**
   - Body size limiter: 62 MB dan katta so'rovlar xotiraga kirmasdan 413 beradi.
   - Fixed-window rate limiter: IP bo'yicha daqiqasiga 30-80 so'rov limiti.
   - DB Size Guard: Neon PostgreSQL 500 MB limitidan oshib ketmasligi uchun 350 MB va 420 MB ogohlantirishlar.
