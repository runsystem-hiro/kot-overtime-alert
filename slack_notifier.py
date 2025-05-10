#!/usr/bin/env python3
import os
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackNotifier:
    def __init__(self, bot_token: str, user_email: str = None):
        self.client = WebClient(token=bot_token)
        self.user_email = user_email
        self.user_id = self._get_user_id() if user_email else None

    def _get_user_id(self):
        try:
            response = self.client.users_lookupByEmail(email=self.user_email)
            return response["user"]["id"]
        except SlackApiError as e:
            print(f"[Slackエラー] ユーザーID取得失敗: {e.response['error']}")
            return None

    def _get_dm_channel_id(self):
        try:
            conv = self.client.conversations_open(users=self.user_id)
            return conv["channel"]["id"]
        except SlackApiError as e:
            print(f"[Slackエラー] DMチャンネルオープン失敗: {e.response['error']}")
            return None

    def send_message(self, message: str, channel_id: str = None, thread_ts: str = None) -> str:
        try:
            if not channel_id and not self.user_id:
                raise ValueError("送信先が指定されていません")

            channel = channel_id or self._get_dm_channel_id()
            response = self.client.chat_postMessage(
                channel=channel,
                text=message,
                thread_ts=thread_ts
            )
            ts = response["ts"]
            print(f"[✅] メッセージ送信成功（ts={ts}）")
            return ts
        except SlackApiError as e:
            print(f"[Slackエラー] メッセージ送信失敗: {e.response['error']}")
            return ""

    def send_file(self, filepath: str, title: str = "", comment: str = "",
                  channel_id: str = None, thread_ts: str = None) -> bool:
        if not os.path.exists(filepath):
            print(f"[エラー] ファイルが存在しません: {filepath}")
            return False

        try:
            channel = channel_id or self._get_dm_channel_id()
            rendered_comment = self._render_template(comment)
            rendered_title = self._render_template(title)

            self.client.files_upload_v2(
                channel=channel,
                file=filepath,
                title=rendered_title,
                filename=os.path.basename(filepath),
                initial_comment=rendered_comment,
                thread_ts=thread_ts
            )
            print(f"[✅] ファイル送信成功: {os.path.basename(filepath)}")
            return True
        except SlackApiError as e:
            print(f"[Slackエラー] ファイル送信失敗: {e.response['error']}")
            return False

    def send_files(self, filepaths: list, title_template: str = "", comment_template: str = "",
                   channel_id: str = None, thread_ts: str = None) -> list:
        results = []
        for path in filepaths:
            success = self.send_file(
                filepath=path,
                title=title_template,
                comment=comment_template,
                channel_id=channel_id,
                thread_ts=thread_ts
            )
            results.append((path, success))
        return results

    def _render_template(self, text: str) -> str:
        now = datetime.now()
        return text.format(
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S")
        )
