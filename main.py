import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import Interaction
from datetime import datetime, timedelta
import random
import config
from sheets.connector import reminder_sheet, theme_sheet
import os
from flask import Flask
import threading

# ======================
# 🤖 Bot本体の設定
# ======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ======================
# 📅 /remind コマンド
# ======================
@tree.command(name="remind", description="指定日時にリマインダーを登録します")
@app_commands.describe(
    date="日時を YYYY/MM/DD HH:MM 形式で入力（例: 2025/04/01 10:00）",
    message="通知内容"
)
async def remind(interaction: Interaction, date: str, message: str):
    try:
        dt = datetime.strptime(date, "%Y/%m/%d %H:%M")
        now = datetime.now().replace(microsecond=0)

        if dt < now:
            await interaction.response.send_message(
                f"⚠️ 過去の日時（{dt.strftime('%Y-%m-%d %H:%M:%S')}）は登録できません！"
            )
            return

        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        channel_id = str(interaction.channel.id)

        reminder_sheet.append_row([formatted, message, channel_id, "FALSE"])

        await interaction.response.send_message(
            f"✅ リマインダーを登録しました！\n📅 {formatted}\n📝 {message}"
        )

    except ValueError:
        await interaction.response.send_message(
            "❌ 日時の形式が正しくありません\n例: `2025/04/05 21:00`"
        )

# ======================
# 🎲 /theme コマンド
# ======================
@tree.command(name="theme", description="Google Sheetsからランダムなお題を生成します")
async def theme(interaction: Interaction):
    await interaction.response.send_message("お題を取得中...")

    try:
        rows = theme_sheet.get_all_values()
        columns = list(zip(*rows[1:]))

        a_column = [cell for cell in columns[0] if cell.strip()]
        b_column = [cell for cell in columns[1] if cell.strip()]
        c_column = [cell for cell in columns[2] if cell.strip()]

        random_a = random.choice(a_column)
        random_b = random.choice(b_column)
        random_c = random.choice(c_column)

        await interaction.followup.send(f"ランダムなお題：\n1: {random_a}\n2: {random_b}\n3: {random_c}")
    except Exception as e:
        await interaction.followup.send(f"❌ お題の取得に失敗しました: {e}")

# ======================
# ⏰ リマインダー通知機能
# ======================
@tasks.loop(minutes=1)
async def check_reminders():
    now = datetime.now()

    try:
        records = reminder_sheet.get_all_records()
    except Exception as e:
        print(f"❌ Google Sheets 読み込み失敗: {e}")
        return

    for idx, row in enumerate(records, start=2):
        if row["is_sent"] == "TRUE":
            continue

        try:
            reminder_time = datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"⚠️ 無効な日付形式: {row['datetime']}")
            continue

        notify_time = reminder_time - timedelta(minutes=5)
        diff = abs((notify_time - now).total_seconds())

        if diff <= 60:
            try:
                channel_id = int(row["channel_id"])
                channel = bot.get_channel(channel_id)

                if channel:
                    bot_name = bot.user.name
                    await channel.send(
                        f"@everyone\n🔔 {bot_name}からのお知らせ！\n📝 「{row['message']}」（{row['datetime']}）"
                    )
                    reminder_sheet.update_cell(idx, 4, "TRUE")
                else:
                    print(f"❌ チャンネルID {channel_id} が見つかりません")
            except Exception as e:
                print(f"❌ 通知中にエラー発生: {e}")

# ======================
# 🚀 Bot起動処理
# ======================
@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user}")
    try:
        await tree.sync()
        print("✅ Slash commands synced!")
        if not check_reminders.is_running():
            check_reminders.start()
            print("⏰ リマインダー通知ループを開始しました")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ======================
# 🌐 Flask ルート (Koyeb対応)
# ======================
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# ======================
# ▶️ 実行
# ======================
def run_flask():
    app.run(host="0.0.0.0", port=8000)  # Koyebはポート固定

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(config.DISCORD_TOKEN)