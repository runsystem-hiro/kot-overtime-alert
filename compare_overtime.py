import os
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import jpholiday
from slack_notifier import SlackNotifier

# .env 読み込み
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'log')
NOTIFIED_FLAG_PATH = os.path.join(BASE_DIR, '.notified_flag')

# 設定
API_BASE_URL = os.getenv("API_BASE_URL")
API_ENDPOINT = os.getenv("API_ENDPOINT")
API_TOKEN = os.getenv("API_TOKEN")
TARGET_KEY = os.getenv("TARGET_KEY")
DIVISION_ID = os.getenv("DIVISION_ID")
OVERTIME_TARGET = int(os.getenv("OVERTIME_TARGET", "600"))
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_DM_EMAILS = os.getenv("SLACK_DM_EMAILS", "").split(",")


def get_month_string(offset_months=0, format_str="%Y-%m"):
    target_date = datetime.today() + relativedelta(months=offset_months)
    return target_date.strftime(format_str)


def get_overtime_for_month(year_month: str):
    url = f"{API_BASE_URL}{API_ENDPOINT}/{year_month}"
    params = {"division": DIVISION_ID}
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        for record in data:
            if record.get("employeeKey") == TARGET_KEY:
                return record.get("overtime", 0)
    return None


def minutes_to_hhmm(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


def calc_percentage(numerator, denominator):
    if denominator == 0:
        return 0
    return round((numerator / denominator) * 100)


def already_notified_this_week() -> bool:
    if not os.path.exists(NOTIFIED_FLAG_PATH):
        return False
    with open(NOTIFIED_FLAG_PATH, "r", encoding="utf-8") as f:
        saved = f.read().strip()
    saved_date = datetime.strptime(saved, "%Y-%m-%d")
    return saved_date.isocalendar()[1] == datetime.today().isocalendar()[1]


def set_notified_flag_today():
    with open(NOTIFIED_FLAG_PATH, "w", encoding="utf-8") as f:
        f.write(datetime.today().strftime("%Y-%m-%d"))


def should_notify(percent_target: int) -> bool:
    today = datetime.today()
    weekday = today.weekday()
    hour = today.hour
    minute = today.minute

    if weekday >= 5 or jpholiday.is_holiday(today):
        return False

    if weekday == 4 and hour == 21 and minute == 30:
        return True

    if percent_target >= 90:
        return True

    if percent_target >= 80 and not already_notified_this_week():
        return True

    return False


def append_or_replace_log_line(summary_line: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'notify_history.log')
    today_str = datetime.today().strftime("%Y-%m-%d")

    lines = []
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(today_str):
            lines[i] = summary_line + "\n"
            updated = True
            break

    if not updated:
        lines.append(summary_line + "\n")

    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def log_no_notification(reason: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'notify_history.log')
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    new_line = f"{today_str} {time_str} | 通知なし: {reason}"

    lines = []
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(today_str):
            lines[i] = new_line + "\n"
            updated = True
            break

    if not updated:
        lines.append(new_line + "\n")

    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    this_month_ym = get_month_string(0, "%Y-%m")
    last_month_ym = get_month_string(-1, "%Y-%m")
    this_month_label = get_month_string(0, "%Y/%m")
    last_month_label = get_month_string(-1, "%Y/%m")

    overtime_this = get_overtime_for_month(this_month_ym)
    overtime_last = get_overtime_for_month(last_month_ym)

    if overtime_this is not None and overtime_last is not None:
        now = datetime.now()
        percent_vs_last = calc_percentage(overtime_this, overtime_last)
        percent_target = calc_percentage(overtime_this, OVERTIME_TARGET)

        # レポート文字列作成
        report_lines = [
            f"📆 今月({this_month_label}) 残業: {minutes_to_hhmm(overtime_this)}（{overtime_this}分）",
            f"📆 前月({last_month_label}) 残業: {minutes_to_hhmm(overtime_last)}（{overtime_last}分）"
        ]

        if overtime_this <= OVERTIME_TARGET:
            remaining = OVERTIME_TARGET - overtime_this
            report_lines.append(f"📊 前月比: {percent_vs_last}% ⏳ 上限まであと {minutes_to_hhmm(remaining)}（{remaining}分）")
        else:
            over_minutes = overtime_this - OVERTIME_TARGET
            report_lines.append(f"📊 前月比: {percent_vs_last}% 🚨 上限超過: +{minutes_to_hhmm(over_minutes)}（{over_minutes}分）抑制失敗")

        # アラートレベル表示
        if percent_target >= 100:
            report_lines.append("🚨 アラート: 上限100%超過")
        elif percent_target >= 90:
            report_lines.append("⚠️ 警告: 90%超過")
        elif percent_target >= 80:
            report_lines.append("⚠️ 注意: 80%超過")
        elif percent_target >= 50:
            report_lines.append("📘 備考: 50%超過")
        else:
            report_lines.append("✅ 問題なし")

        report = "\n".join(report_lines)
        print(report)

        if should_notify(percent_target):
            for email in SLACK_DM_EMAILS:
                notifier = SlackNotifier(bot_token=SLACK_BOT_TOKEN, user_email=email.strip())
                notifier.send_message(report)

            log_time = now.strftime("%Y-%m-%d %H:%M")
            if overtime_this <= OVERTIME_TARGET:
                diff = OVERTIME_TARGET - overtime_this
                log_line = f"{log_time} | 残業: {minutes_to_hhmm(overtime_this)}（{overtime_this}分） | 上限まであと {minutes_to_hhmm(diff)}（{diff}分）"
            else:
                diff = overtime_this - OVERTIME_TARGET
                log_line = f"{log_time} | 残業: {minutes_to_hhmm(overtime_this)}（{overtime_this}分） | 上限超過: +{minutes_to_hhmm(diff)}（{diff}分）"

            log_line += f" | 前月比: {percent_vs_last}%"

            if percent_target >= 100:
                log_line += " | 🚨 アラート: 上限100%超過"
            elif percent_target >= 90:
                log_line += " | ⚠️ 警告: 90%超過"
            elif percent_target >= 80:
                log_line += " | ⚠️ 注意: 80%超過"
            elif percent_target >= 50:
                log_line += " | 📘 備考: 50%超過"
            else:
                log_line += " | ✅ 問題なし"

            append_or_replace_log_line(log_line)

            if 80 <= percent_target < 90:
                set_notified_flag_today()
        else:
            today = datetime.today()
            if today.weekday() >= 5:
                reason = f"{'土曜' if today.weekday() == 5 else '日曜'}のため通知対象外（weekday={today.weekday()}）"
            elif jpholiday.is_holiday(today):
                reason = "祝日のため通知対象外"
            elif percent_target < 80:
                reason = f"残業比率 {percent_target}% が通知閾値未満"
            else:
                reason = "通知条件未達（定期時間外かつ通知済）"

            print(f"⏳ 通知スキップ: {reason}")
            log_no_notification(reason)
    else:
        print("⚠ 残業時間が取得できませんでした。")


if __name__ == "__main__":
    main()
