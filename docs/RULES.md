# Loyiha Qoidalari va Standartlari (Project Rules & Guidelines)

Ushbu hujjat **mandarin_foto_hisobot** tizimining barcha qismlari (frontend, backend, UI/UX) uchun qat'iy va o'zgarmas qoidalar to'plamidir. Kelgusidagi har qanday o'zgarishlar va yangi modullar ushbu qoidalarga 100% muvofiq bo'lishi shart.

---

## 1. UI/UX: 320px Ultra-Mobil Moslashuvchanlik Standarti (Majburiy)

> [!IMPORTANT]
> **Tizimning barcha interfeysi 320px ekran kengligigacha (iPhone SE 1-avlod, kichik Android smartfonlar) to'liq moslashuvchan (fully responsive) bo'lishi shart.**

### Qat'iy talablar:
1. **Gorizontal skroll bo'lmasligi (Zero Horizontal Overflow):**
   - Hech qanday sahifada, modalda yoki kartochkada 320px ekran kengligida gorizontal skroll (`overflow-x`) paydo bo'lishiga yo'l qo'yilmaydi.
   - Tashqi konteynerlar `px-2.5 sm:px-4` yoki `px-2` kabi ixcham chekka masofalariga ega bo'lishi kerak.
2. **Tipografiya va Tugmalar moslashuvchanligi:**
   - 320px ekranlarda matn o'lchamlari `text-xs`, `text-[11px]` yoki `text-[10px]` dan oqilona foydalanishi lozim.
   - Tugmalar guruhi (masalan, karobka og'irligi variantlari) 320px da sig'ishi uchun `grid-cols-3` yoki `flex-wrap` tarzida joylashtiriladi, tugma paddinglari `py-2 px-1 text-[11px]` bo'ladi.
   - Sarlavhalar va badjlar `flex-wrap` yoki `truncate` / `min-w-0` orqali sig'diriladi.
3. **Modallar va Popoverlar:**
   - Har bir modal oynasi `max-w-[300px]` yoki `max-w-sm` chegarasida bo'lib, 320px ekran kengligida ekranning 92-95% qismidan oshmasligi va chekkalarga yopishib qolmasligi shart.
4. **Ixchamlik (Compact Design):**
   - Ombor va tarozi operatorlari uchun har bir vertikal piksel qimmatli. Keraksiz katta bo'shliqlar, baland bo'sh bloklar va uzun izohlar o'rniga ixcham, tushunarli piktogrammalar (icons) va qisqa matnlardan foydalaniladi.

---

## 2. Foto Hisobot va Yuklanmalar Qoidalari (Multi-Photo)

1. **Har bir karobka uchun 1 tadan ko'p rasm olish:**
   - Operator bitta karobka uchun bir nechta rasm olishi mumkin (masalan: tarozidagi og'irlik ko'rsatkichi, karobka shtrix-kodi/markirovkasi, tovar sifati).
   - Tizim 1 ta emas, balki bir nechta fotosuratlarni saqlaydi (`photoUrls: string[]`).
2. **Kamerada ketma-ket kadr olish:**
   - To'liq ekranli kamera rejimida har bir kadr olinganda kamera darhol yopilib qolmasdan, bir nechta rasmni ketma-ket olishga imkon berishi kerak. Olingan rasmlar soni ko'rsatiladi va operator "Tayyor" tugmasini bosganda formaga qaytiladi.
3. **Rasmlarni kattalashtirish (Lightbox) va o'chirish:**
   - Olingan barcha fotosuratlar miniatyura (thumbnail) shaklida ko'rsatiladi.
   - Har qanday rasm bosilganda butun ekranga ochiladi (fullscreen lightbox).
   - Xato yoki xira olingan rasmni bittalab o'chirish (trash tugmasi) imkoniyati bo'lishi kerak.

---

## 3. Terminologiya va Nomlash Qoidalari

1. **Vazn nomlari:**
   - "Brutto" so'zi o'rniga faqat **"Og'irlik"** (yoki "Yuk og'irligi") ishlatiladi.
   - "Tara" so'zi o'rniga hamma joyda faqat **"Karobka og'irligi"** deb yoziladi.
   - "Netto" o'rniga **"Toza vazn"** ishlatiladi.
2. **Maxsus karobka og'irligi tasdiqlash:**
   - Agar foydalanuvchi "O'zim kiritaman" orqali maxsus og'irlik kiritsa, uni saqlab qolish uchun oddiy chekbox emas, balki zamonaviy chiroyli tasdiqlash modali orqali so'raladi (*"Karobka og'irligi ({val} kg) saqlansinmi?"*).

---

## 4. Tezkor Rejim (Fast Mode) Qoidalari

1. **Avtomatik fokus:**
   - Rasm olingandan yoki galereyadan tanlangandan so'ng darhol kursor **"Karobka kodi"** maydoniga avtomatik fokuslanishi shart.
   - Saqlash amalga oshirilgandan keyin ham Fast Mode da kursor yana yangi karobka kiritish uchun fokuslanadi.

---

## 5. Entry (Kiritish va Ro'yxat) Sahifalarida Navbar va MobileNav Yashirilishi

1. **To'liq e'tibor va toza ekran:**
   - `/entry/` bilan bog'liq bo'lgan barcha sahifalarda (`/reports/reys/:id/entry/:catId` va `/list`):
     - Yuqoridagi global `Navbar` ("Mandarin Logistics | Standalone Web") butunlay yashiriladi.
     - Pastdagi `MobileNav` navigatsiya paneli butunlay yashiriladi.
     - Sahifaning o'zining ixcham maxsus headeri (Ortga qaytish, Reys kodi, Yuklanganlar, Fast Mode, Kamera) eng yuqorida turadi.
   - Bu operator uchun butun ekran bo'ylab keng maydon yaratadi, tarozi oldida tezkor ishlash paytida tasodifiy boshqa sahifalarga o'tib ketish xavfini 100% bartaraf etadi.


