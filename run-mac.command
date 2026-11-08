#!/bin/bash
# Double-click this file in Finder to fix the Persian fonts installed for your user.
cd "$(dirname "$0")" || exit 1

echo "== اصلاح فونت‌های فارسی برای Word مک =="
echo
echo "لطفاً قبل از ادامه، Word و بقیه‌ی برنامه‌های Office را ببندید."
read -r -p "برای ادامه Enter را بزنید (برای لغو Ctrl+C) ... "

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 پیدا نشد. ابتدا دستور  xcode-select --install  را در Terminal اجرا کنید و دوباره امتحان کنید."
  read -r -p "Enter برای خروج"
  exit 1
fi

VENV="$HOME/.persian-font-fix-venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "در حال آماده‌سازی (فقط بار اول)..."
  python3 -m venv "$VENV" && "$VENV/bin/python" -m pip install -q fonttools || {
    echo "نصب fonttools ناموفق بود. اتصال اینترنت را بررسی کنید."
    read -r -p "Enter برای خروج"
    exit 1
  }
fi

"$VENV/bin/python" fix_persian_fonts.py "$@"
echo
read -r -p "تمام شد. Enter برای بستن پنجره"
