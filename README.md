# 通知スクリプト仕様書

## 概要

このスクリプトは、King of Time API から前月・今月の残業時間を取得し、Slack に通知を行うものです。残業時間が所定の閾値を超えた場合や、金曜の定時など、特定の条件に基づいて通知が実行されます。また、通知の有無に関係なくログが日次で1行記録されます。

---

## 通知条件

| 条件                      | 通知有無 | 備考 |
|---------------------------|----------|------|
| 土日                      | 通知しない | - |
| 祝日                     | 通知しない | `jpholiday` ライブラリで判定 |
| 金曜21:30                | 通知する | 毎週定期通知 |
| 残業比率 ≥ 90%         | 通知する | 毎日通知 |
| 残業比率 ≥ 80% かつ未通知 | 通知する | 週1回のみ（`.notified_flag` により制御） |
| 残業比率 < 80%           | 通知しない | - |

---

## 通知内容（Slack）

Slack通知には以下のようなフォーマットで送信されます：

```log
📆 今月(2025/05) 残業: 12:00（720分）
📆 前月(2025/04) 残業: 10:00（600分）
📊 前月比: 120% 🚨 上限超過: +2:00（120分）抑制失敗
🚨 アラート: 上限100%超過
```

---

## ログ仕様

- ファイル：`log/notify_history.log`
- ログパスは `compare_overtime.py` のあるディレクトリを基準に自動的に決定されます。
- フォーマット：1日1行、既存の日付があれば上書き
- 通知された場合：

  ```log
  2025-05-10 21:30 | 残業: 12:00（720分） | 上限超過: +2:00（120分） | 前月比: 120% | 🚨 アラート: 上限100%超過
  ```

- 通知されなかった場合：

  ```log
  2025-05-11 08:00 | 通知なし: 土曜のため通知対象外（weekday=6）
  ```

---

## `.env` 設定例

```env
API_BASE_URL=https://api.kingtime.jp/v1.0
API_ENDPOINT=/monthly-workings
API_TOKEN=...
TARGET_KEY=...
DIVISION_ID=300
OVERTIME_TARGET=600
SLACK_BOT_TOKEN=xoxb...
SLACK_DM_EMAILS=user1@example.com,user2@example.com
```

---

## cron設定例（通知条件に基づく実行）

### 毎日 9:00 に実行（90%以上通知 or 80%以上未通知用）

```cron
0 9 * * * /usr/bin/python3 /home/pi/kot-overtime-alert/compare_overtime.py >> /home/pi/kot-overtime-alert/log/cron.log 2>&1

# 仮想環境内の場合
0 9 * * * /home/pi/kot-overtime-alert/.venv/bin/python /home/pi/kot-overtime-alert/compare_overtime.py >> /home/pi/kot-overtime-alert/log/cron.log 2>&1

```

### 毎週金曜 21:30 に実行（定期通知用）

```cron
30 21 * * 5 /usr/bin/python3 /home/pi/kot-overtime-alert/compare_overtime.py >> /home/pi/kot-overtime-alert/log/cron.log 2>&1

# 仮想環境内の場合
30 21 * * 5 /home/pi/kot-overtime-alert/.venv/bin/python /home/pi/kot-overtime-alert/compare_overtime.py >> /home/pi/kot-overtime-alert/log/cron.log 2>&1
```

---

## ファイル構成（推奨）

```text

kot-overtime-alert/
├── compare_overtime.py
├── slack_notifier.py
├── .env
├── .notified_flag
└── log/
       └── notify_history.log

```

---

## 補足

- `.notified_flag` は週1回通知済みを記録する内部ファイルです。
- `jpholiday` により日本の祝日も自動判定されます。
- Slack送信は `slack_sdk` を使用し、`SlackNotifier` クラスでラップされています。
- ログ出力は常に `compare_overtime.py` があるディレクトリ配下の `log/` に作成されるように制御されています。

---
